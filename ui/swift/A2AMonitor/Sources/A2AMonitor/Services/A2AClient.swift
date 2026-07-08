import Foundation
import Combine

/// A2A Server API Client with SSE support and authentication
@MainActor
class A2AClient: ObservableObject {
    @Published var isConnected = false
    @Published var connectionError: String?

    private var baseURL: URL
    private var eventSourceTask: URLSessionDataTask?
    private var session: URLSession
    private var cancellables = Set<AnyCancellable>()

    /// Shared JSON decoder configured for ISO 8601 dates from the server
    private let jsonDecoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let dateString = try container.decode(String.self)
            if let date = ServerDateParser.shared.date(from: dateString) {
                return date
            }
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode date: \(dateString)")
        }
        return decoder
    }()

    // Auth service reference for adding authorization headers
    weak var authService: AuthService?

    var onMessage: ((Message) -> Void)?
    var onAgentStatus: ((Agent) -> Void)?
    var onStats: ((MonitorStats) -> Void)?
    var onError: ((Error) -> Void)?
    var onDisconnect: (() -> Void)?

    // Reconnection state
    private var reconnectAttempts = 0
    private let maxReconnectAttempts = 5
    private var reconnectTask: Task<Void, Never>?
    private var sseSession: URLSession?

    /// Reusable ISO8601 formatter for outgoing timestamps (avoids per-call allocation).
    private static let iso8601Output = ISO8601DateFormatter()

    init(baseURL: String = "https://quantum-forge.codetether.run") {
        self.baseURL = URL(string: baseURL)!

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 300
        self.session = URLSession(configuration: config)
    }

    func updateBaseURL(_ url: String) {
        if let newURL = URL(string: url) {
            baseURL = newURL
        }
    }

    // MARK: - Auth Header Helper

    private func addAuthHeader(to request: inout URLRequest) {
        if let authHeader = authService?.authorizationHeader {
            request.setValue(authHeader, forHTTPHeaderField: "Authorization")
        }
    }

    private func authenticatedRequest(for url: URL) -> URLRequest {
        var request = URLRequest(url: url)
        addAuthHeader(to: &request)
        return request
    }

    // MARK: - SSE Connection

    func connectToMonitorStream() {
        disconnectStream()

        let url = baseURL.appendingPathComponent("/v1/monitor/stream")
        var request = URLRequest(url: url)
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")
        addAuthHeader(to: &request)

        // Track if we've received at least one event (for setting isConnected)
        var hasReceivedFirstEvent = false

        // Using URLSession for SSE
        let delegate = SSEDelegate(
            onEvent: { [weak self] event in
                Task { @MainActor in
                    guard let self = self else { return }
                    
                    // Set connected on first successful event
                    if !hasReceivedFirstEvent {
                        hasReceivedFirstEvent = true
                        self.isConnected = true
                        self.connectionError = nil
                        self.reconnectAttempts = 0  // Reset on successful connection
                    }
                    
                    self.handleSSEEvent(event)
                }
            },
            onError: { [weak self] error in
                Task { @MainActor in
                    guard let self = self else { return }
                    self.isConnected = false
                    self.connectionError = error.localizedDescription
                    self.onError?(error)
                    self.scheduleReconnect()
                }
            },
            onComplete: { [weak self] in
                Task { @MainActor in
                    guard let self = self else { return }
                    self.isConnected = false
                    self.onDisconnect?()
                    self.scheduleReconnect()
                }
            }
        )

        // Invalidate previous session before creating new one
        sseSession?.invalidateAndCancel()
        sseSession = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)
        eventSourceTask = sseSession?.dataTask(with: request)
        eventSourceTask?.resume()

        // Don't set isConnected = true here - wait for first event
        connectionError = nil
    }

    func disconnectStream() {
        reconnectTask?.cancel()
        reconnectTask = nil
        eventSourceTask?.cancel()
        eventSourceTask = nil
        sseSession?.invalidateAndCancel()
        sseSession = nil
        isConnected = false
        reconnectAttempts = 0
    }

    private func scheduleReconnect() {
        guard reconnectAttempts < maxReconnectAttempts else {
            connectionError = "Failed to reconnect after \(maxReconnectAttempts) attempts"
            return
        }

        reconnectTask?.cancel()
        reconnectTask = Task { [weak self] in
            guard let self = self else { return }
            let delay = pow(2.0, Double(self.reconnectAttempts)) // Exponential backoff: 1, 2, 4, 8, 16 seconds
            try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            guard !Task.isCancelled else { return }
            await MainActor.run {
                self.reconnectAttempts += 1
                self.connectToMonitorStream()
            }
        }
    }

    private func handleSSEEvent(_ event: SSEEvent) {
        switch event.event {
        case "message":
            if let data = event.data.data(using: .utf8),
               let message = try? jsonDecoder.decode(Message.self, from: data) {
                onMessage?(message)
            }
        case "agent_status":
            if let data = event.data.data(using: .utf8),
               let agent = try? jsonDecoder.decode(Agent.self, from: data) {
                onAgentStatus?(agent)
            }
        default:
            break
        }
    }

    // MARK: - REST API

    func fetchAgents() async throws -> [Agent] {
        let url = baseURL.appendingPathComponent("/v1/monitor/agents")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode([Agent].self, from: data)
    }

    func fetchMessages(limit: Int = 100) async throws -> [Message] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/monitor/messages"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]

        let request = authenticatedRequest(for: components.url!)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode([Message].self, from: data)
    }

    func fetchMessageCount() async throws -> Int {
        let url = baseURL.appendingPathComponent("/v1/monitor/messages/count")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        let response = try jsonDecoder.decode(MessageCountResponse.self, from: data)
        return response.total
    }

    func searchMessages(query: String, limit: Int = 100) async throws -> [Message] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/monitor/messages/search"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "limit", value: "\(limit)")
        ]

        let request = authenticatedRequest(for: components.url!)
        let (data, _) = try await session.data(for: request)

        struct SearchResponse: Codable {
            let results: [Message]
        }

        let response = try jsonDecoder.decode(SearchResponse.self, from: data)
        return response.results
    }

    func sendIntervention(agentId: String, message: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/monitor/intervene")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        let body: [String: Any] = [
            "agent_id": agentId,
            "message": message,
            "timestamp": Self.iso8601Output.string(from: Date())
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw A2AError.interventionFailed
        }
    }

    // MARK: - OpenCode API

    func fetchOpenCodeStatus() async throws -> OpenCodeStatus {
        let url = baseURL.appendingPathComponent("/v1/opencode/status")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(OpenCodeStatus.self, from: data)
    }

    func fetchModels() async throws -> ModelsResponse {
        let url = baseURL.appendingPathComponent("/v1/opencode/models")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(ModelsResponse.self, from: data)
    }

    func fetchCodebases() async throws -> [Codebase] {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode([Codebase].self, from: data)
    }

    func registerCodebase(name: String, path: String, description: String?) async throws -> Codebase {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        var body: [String: Any] = [
            "name": name,
            "path": path
        ]
        if let description = description {
            body["description"] = description
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await session.data(for: request)

        struct CodebaseResponse: Codable {
            let success: Bool
            let codebase: Codebase
        }

        let response = try jsonDecoder.decode(CodebaseResponse.self, from: data)
        return response.codebase
    }

    func unregisterCodebase(id: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(id)")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        addAuthHeader(to: &request)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw A2AError.deleteFailed
        }
    }

    func triggerAgent(codebaseId: String, prompt: String, agent: String = "build", model: String? = nil) async throws -> TriggerResponse {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/trigger")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        var body: [String: Any] = [
            "prompt": prompt,
            "agent": agent
        ]
        if let model = model, !model.isEmpty {
            body["model"] = model
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(TriggerResponse.self, from: data)
    }

    func interruptAgent(codebaseId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/interrupt")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        addAuthHeader(to: &request)

        let (_, _) = try await session.data(for: request)
    }

    func stopAgent(codebaseId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/stop")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        addAuthHeader(to: &request)

        let (_, _) = try await session.data(for: request)
    }

    func startWatchMode(codebaseId: String, interval: Int = 5) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/watch/start")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        let body: [String: Any] = ["interval": interval]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (_, _) = try await session.data(for: request)
    }

    func stopWatchMode(codebaseId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/watch/stop")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        addAuthHeader(to: &request)

        let (_, _) = try await session.data(for: request)
    }

    // MARK: - Task API

    func fetchSessions(codebaseId: String) async throws -> [SessionSummary] {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/sessions")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)

        struct SessionsResponse: Codable {
            let sessions: [SessionSummary]
        }

        let response = try jsonDecoder.decode(SessionsResponse.self, from: data)
        return response.sessions
    }

    func fetchSessionMessages(codebaseId: String, sessionId: String, limit: Int = 100) async throws -> [SessionMessage] {
        var components = URLComponents(
            url: baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/sessions/\(sessionId)/messages"),
            resolvingAgainstBaseURL: false
        )!
        components.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]

        let request = authenticatedRequest(for: components.url!)
        let (data, _) = try await session.data(for: request)

        struct MessagesResponse: Codable {
            let messages: [SessionMessage]
            let sessionId: String?

            enum CodingKeys: String, CodingKey {
                case messages
                case sessionId = "session_id"
            }
        }

        let response = try jsonDecoder.decode(MessagesResponse.self, from: data)
        return response.messages
    }

    func resumeSession(
        codebaseId: String,
        sessionId: String,
        prompt: String?,
        agent: String = "build",
        model: String? = nil
    ) async throws -> Bool {
        let response = try await resumeSessionDetailed(
            codebaseId: codebaseId,
            sessionId: sessionId,
            prompt: prompt,
            agent: agent,
            model: model
        )
        return response.success
    }

    func resumeSessionDetailed(
        codebaseId: String,
        sessionId: String,
        prompt: String?,
        agent: String = "build",
        model: String? = nil
    ) async throws -> ResumeSessionResponse {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/sessions/\(sessionId)/resume")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        var body: [String: Any] = [
            "prompt": prompt ?? NSNull(),
            "agent": agent,
        ]
        if let model {
            body["model"] = model
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw A2AError.invalidResponse
        }

        // Preferred: strongly-typed decode.
        if let decoded = try? jsonDecoder.decode(ResumeSessionResponse.self, from: data) {
            return decoded
        }

        // Fallback for unexpected shapes.
        if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let success = obj["success"] as? Bool {
            return ResumeSessionResponse(
                success: success,
                message: obj["message"] as? String,
                taskId: obj["task_id"] as? String,
                sessionId: obj["session_id"] as? String,
                newSessionId: obj["new_session_id"] as? String,
                activeSessionId: obj["active_session_id"] as? String,
                error: obj["error"] as? String
            )
        }

        return ResumeSessionResponse(success: true, message: nil, taskId: nil, sessionId: sessionId, newSessionId: nil, activeSessionId: sessionId, error: nil)
    }

    func fetchTasks() async throws -> [AgentTask] {
        let url = baseURL.appendingPathComponent("/v1/opencode/tasks")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode([AgentTask].self, from: data)
    }

    func fetchTask(taskId: String) async throws -> AgentTask {
        let url = baseURL.appendingPathComponent("/v1/opencode/tasks/\(taskId)")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(AgentTask.self, from: data)
    }

    func createTask(codebaseId: String, title: String, description: String, priority: TaskPriority, context: String?, agentType: String = "build") async throws -> AgentTask {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/tasks")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        var body: [String: Any] = [
            "title": title,
            "description": description,
            "priority": priority.rawValue,
            "agent_type": agentType
        ]
        if let context = context {
            body["context"] = context
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(AgentTask.self, from: data)
    }

    func cancelTask(taskId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/tasks/\(taskId)/cancel")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        addAuthHeader(to: &request)

        let (_, _) = try await session.data(for: request)
    }

    // MARK: - OpenCode Events SSE (Agent Output Streaming)

    func connectToAgentEvents(codebaseId: String, onEvent: @escaping (AgentEvent) -> Void) -> URLSessionDataTask? {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/events")
        var request = URLRequest(url: url)
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")
        addAuthHeader(to: &request)

        let delegate = AgentEventSSEDelegate(onEvent: onEvent)
        let sseSession = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)
        let task = sseSession.dataTask(with: request)
        task.resume()
        return task
    }

    func fetchSessionMessages(codebaseId: String, limit: Int = 50) async throws -> [SessionMessage] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/messages"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]

        let request = authenticatedRequest(for: components.url!)
        let (data, _) = try await session.data(for: request)

        struct MessagesResponse: Codable {
            let messages: [SessionMessage]
            let sessionId: String?

            enum CodingKeys: String, CodingKey {
                case messages
                case sessionId = "session_id"
            }
        }

        let response = try jsonDecoder.decode(MessagesResponse.self, from: data)
        return response.messages
    }

    func fetchAgentStatus(codebaseId: String) async throws -> AgentStatusResponse {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/status")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(AgentStatusResponse.self, from: data)
    }

    func sendAgentMessage(codebaseId: String, message: String, agent: String? = nil) async throws -> TriggerResponse {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/message")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        var body: [String: Any] = ["message": message]
        if let agent = agent {
            body["agent"] = agent
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(TriggerResponse.self, from: data)
    }

    // MARK: - Worker API

    func fetchWorkers() async throws -> [Worker] {
        let url = baseURL.appendingPathComponent("/v1/opencode/workers")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode([Worker].self, from: data)
    }

    func registerWorker(workerId: String, name: String, capabilities: [String], hostname: String?) async throws -> Worker {
        let url = baseURL.appendingPathComponent("/v1/opencode/workers/register")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        var body: [String: Any] = [
            "worker_id": workerId,
            "name": name,
            "capabilities": capabilities
        ]
        if let hostname = hostname {
            body["hostname"] = hostname
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, _) = try await session.data(for: request)

        struct WorkerResponse: Codable {
            let success: Bool
            let worker: Worker
        }

        let response = try jsonDecoder.decode(WorkerResponse.self, from: data)
        return response.worker
    }

    func unregisterWorker(workerId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/workers/\(workerId)/unregister")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let (_, _) = try await session.data(for: request)
    }

    func workerHeartbeat(workerId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/workers/\(workerId)/heartbeat")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let (_, _) = try await session.data(for: request)
    }

    // MARK: - Watch Mode Status

    func fetchWatchStatus(codebaseId: String) async throws -> WatchStatus {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/watch/status")
        let (data, _) = try await session.data(from: url)
        return try jsonDecoder.decode(WatchStatus.self, from: data)
    }

    // MARK: - Monitor Stats

    func fetchStats() async throws -> ServerStats {
        let url = baseURL.appendingPathComponent("/v1/monitor/stats")
        let (data, _) = try await session.data(from: url)
        return try jsonDecoder.decode(ServerStats.self, from: data)
    }

    // MARK: - Unified Agent Control Plane (/v1/agent)
    //
    // Deeper insight into the codetether-agent fleet: runtime sessions
    // (the harvester/agent session store), richly-classified workers,
    // worker profiles, and per-worker agent definitions.

    /// List codetether-agent runtime sessions, optionally filtered by project.
    func fetchRuntimeSessions(projectId: String? = nil, limit: Int = 50, offset: Int = 0) async throws -> RuntimeSessionsResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/agent/runtime/sessions"), resolvingAgainstBaseURL: false)!
        var items = [
            URLQueryItem(name: "limit", value: "\(limit)"),
            URLQueryItem(name: "offset", value: "\(offset)")
        ]
        if let projectId, !projectId.isEmpty {
            items.append(URLQueryItem(name: "project_id", value: projectId))
        }
        components.queryItems = items

        let request = authenticatedRequest(for: components.url!)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(RuntimeSessionsResponse.self, from: data)
    }

    /// Fetch a single runtime session's metadata.
    func fetchRuntimeSession(sessionId: String) async throws -> RuntimeSession {
        let url = baseURL.appendingPathComponent("/v1/agent/runtime/sessions/\(sessionId)")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(RuntimeSessionResponse.self, from: data).session
    }

    /// Fetch the message/turn history for a runtime session.
    func fetchRuntimeSessionMessages(sessionId: String, limit: Int = 50, offset: Int = 0) async throws -> [RuntimeSessionMessage] {
        var components = URLComponents(
            url: baseURL.appendingPathComponent("/v1/agent/runtime/sessions/\(sessionId)/messages"),
            resolvingAgainstBaseURL: false
        )!
        components.queryItems = [
            URLQueryItem(name: "limit", value: "\(limit)"),
            URLQueryItem(name: "offset", value: "\(offset)")
        ]

        let request = authenticatedRequest(for: components.url!)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(RuntimeSessionMessagesResponse.self, from: data).messages
    }

    /// List registered workers with the server's runtime classification and
    /// harvester annotations. `onlineOnly` and `excludeOfflineHours` mirror the
    /// server-side filters.
    func fetchAgentWorkers(search: String? = nil, onlineOnly: Bool = false, excludeOfflineHours: Int? = 24) async throws -> [AgentWorker] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/agent/workers"), resolvingAgainstBaseURL: false)!
        var items: [URLQueryItem] = []
        if let search, !search.isEmpty {
            items.append(URLQueryItem(name: "search", value: search))
        }
        if onlineOnly {
            items.append(URLQueryItem(name: "online_only", value: "true"))
        }
        if let excludeOfflineHours {
            items.append(URLQueryItem(name: "exclude_offline_hours", value: "\(excludeOfflineHours)"))
        }
        if !items.isEmpty { components.queryItems = items }

        let request = authenticatedRequest(for: components.url!)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode([AgentWorker].self, from: data)
    }

    /// Fetch a single worker's detailed record.
    func fetchAgentWorker(workerId: String) async throws -> AgentWorker {
        let url = baseURL.appendingPathComponent("/v1/agent/workers/\(workerId)")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode(AgentWorker.self, from: data)
    }

    /// List the agent definitions a specific worker supports.
    func fetchWorkerAgents(workerId: String) async throws -> [WorkerAgentDefinition] {
        let url = baseURL.appendingPathComponent("/v1/agent/workers/\(workerId)/agents")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode([WorkerAgentDefinition].self, from: data)
    }

    /// List reusable worker provisioning profiles (builtins + user-owned).
    func fetchWorkerProfiles(builtinOnly: Bool = false) async throws -> [WorkerProfile] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/agent/worker-profiles"), resolvingAgainstBaseURL: false)!
        if builtinOnly {
            components.queryItems = [URLQueryItem(name: "builtin_only", value: "true")]
        }
        let request = authenticatedRequest(for: components.url!)
        let (data, _) = try await session.data(for: request)
        return try jsonDecoder.decode([WorkerProfile].self, from: data)
    }

    // MARK: - Export

    func exportMessagesJSON(limit: Int = 10000, allMessages: Bool = false) async throws -> Data {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/monitor/export/json"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "limit", value: "\(limit)"),
            URLQueryItem(name: "all_messages", value: allMessages ? "true" : "false")
        ]

        let (data, _) = try await session.data(from: components.url!)
        return data
    }
}

// MARK: - SSE Support

struct SSEEvent {
    var event: String = ""
    var data: String = ""
    var id: String?
}

class SSEDelegate: NSObject, URLSessionDataDelegate {
    private var onEvent: (SSEEvent) -> Void
    private var onError: ((Error) -> Void)?
    private var onComplete: (() -> Void)?
    private var buffer = ""

    init(
        onEvent: @escaping (SSEEvent) -> Void,
        onError: ((Error) -> Void)? = nil,
        onComplete: (() -> Void)? = nil
    ) {
        self.onEvent = onEvent
        self.onError = onError
        self.onComplete = onComplete
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard let string = String(data: data, encoding: .utf8) else { return }
        buffer += string
        processBuffer()
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        if let error = error {
            // Ignore cancellation errors (user-initiated disconnect)
            if (error as NSError).code == NSURLErrorCancelled {
                return
            }
            onError?(error)
        } else {
            // Connection completed without error (server closed connection)
            onComplete?()
        }
    }

    func urlSession(_ session: URLSession, didBecomeInvalidWithError error: Error?) {
        if let error = error {
            onError?(error)
        }
    }

    private func processBuffer() {
        let lines = buffer.components(separatedBy: "\n\n")

        for i in 0..<(lines.count - 1) {
            let eventString = lines[i]
            var event = SSEEvent()

            for line in eventString.components(separatedBy: "\n") {
                if line.hasPrefix("event:") {
                    event.event = String(line.dropFirst(6)).trimmingCharacters(in: .whitespaces)
                } else if line.hasPrefix("data:") {
                    event.data += String(line.dropFirst(5)).trimmingCharacters(in: .whitespaces)
                } else if line.hasPrefix("id:") {
                    event.id = String(line.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                }
            }

            if !event.event.isEmpty || !event.data.isEmpty {
                onEvent(event)
            }
        }

        buffer = lines.last ?? ""
    }
}

// MARK: - Errors

enum A2AError: LocalizedError {
    case interventionFailed
    case deleteFailed
    case connectionFailed
    case invalidResponse

    var errorDescription: String? {
        switch self {
        case .interventionFailed: return "Failed to send intervention"
        case .deleteFailed: return "Failed to delete resource"
        case .connectionFailed: return "Failed to connect to server"
        case .invalidResponse: return "Invalid response from server"
        }
    }
}

// MARK: - Date Parsing

/// Thread-safe server date parser that reuses cached `DateFormatter` instances
/// and remembers the last successful format so repeated decodes of large
/// payloads (hundreds of messages) skip re-trying every candidate format.
final class ServerDateParser {
    static let shared = ServerDateParser()

    private static let formats = [
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",  // Python isoformat with microseconds
        "yyyy-MM-dd'T'HH:mm:ss.SSS",      // With milliseconds
        "yyyy-MM-dd'T'HH:mm:ss",          // Without fractional seconds
        "yyyy-MM-dd'T'HH:mm:ssZ",         // With Z timezone
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSSZ",  // With microseconds and Z
        "yyyy-MM-dd'T'HH:mm:ss.SSSZ",     // With milliseconds and Z
    ]

    // Pre-built formatters, created once. Guarded by `lock` for thread safety
    // because JSONDecoder may decode off the main thread.
    private let lock = NSLock()
    private let formatters: [DateFormatter]
    private let isoFractional = ISO8601DateFormatter()
    private let isoPlain = ISO8601DateFormatter()
    private var lastGoodIndex = 0

    private init() {
        formatters = Self.formats.map { format in
            let f = DateFormatter()
            f.locale = Locale(identifier: "en_US_POSIX")
            f.timeZone = TimeZone(secondsFromGMT: 0)
            f.dateFormat = format
            return f
        }
        isoFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        isoPlain.formatOptions = [.withInternetDateTime]
    }

    func date(from string: String) -> Date? {
        lock.lock()
        defer { lock.unlock() }

        // Try the last successful format first.
        if let date = formatters[lastGoodIndex].date(from: string) {
            return date
        }

        for index in formatters.indices where index != lastGoodIndex {
            if let date = formatters[index].date(from: string) {
                lastGoodIndex = index
                return date
            }
        }

        if let date = isoFractional.date(from: string) { return date }
        if let date = isoPlain.date(from: string) { return date }
        return nil
    }
}
