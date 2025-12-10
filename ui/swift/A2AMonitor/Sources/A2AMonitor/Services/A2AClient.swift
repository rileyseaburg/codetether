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
    
    // Auth service reference for adding authorization headers
    weak var authService: AuthService?
    
    var onMessage: ((Message) -> Void)?
    var onAgentStatus: ((Agent) -> Void)?
    var onStats: ((MonitorStats) -> Void)?
    
    init(baseURL: String = "http://localhost:8000") {
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
        
        // Using URLSession for SSE
        let delegate = SSEDelegate { [weak self] event in
            Task { @MainActor in
                self?.handleSSEEvent(event)
            }
        }
        
        let sseSession = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)
        eventSourceTask = sseSession.dataTask(with: request)
        eventSourceTask?.resume()
        
        isConnected = true
        connectionError = nil
    }
    
    func disconnectStream() {
        eventSourceTask?.cancel()
        eventSourceTask = nil
        isConnected = false
    }
    
    private func handleSSEEvent(_ event: SSEEvent) {
        switch event.event {
        case "message":
            if let data = event.data.data(using: .utf8),
               let message = try? JSONDecoder().decode(Message.self, from: data) {
                onMessage?(message)
            }
        case "agent_status":
            if let data = event.data.data(using: .utf8),
               let agent = try? JSONDecoder().decode(Agent.self, from: data) {
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
        return try JSONDecoder().decode([Agent].self, from: data)
    }
    
    func fetchMessages(limit: Int = 100) async throws -> [Message] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/monitor/messages"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        
        let request = authenticatedRequest(for: components.url!)
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode([Message].self, from: data)
    }
    
    func fetchMessageCount() async throws -> Int {
        let url = baseURL.appendingPathComponent("/v1/monitor/messages/count")
        let (data, _) = try await session.data(from: url)
        let response = try JSONDecoder().decode(MessageCountResponse.self, from: data)
        return response.total
    }
    
    func searchMessages(query: String, limit: Int = 100) async throws -> [Message] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/monitor/messages/search"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "limit", value: "\(limit)")
        ]
        
        let (data, _) = try await session.data(from: components.url!)
        
        struct SearchResponse: Codable {
            let results: [Message]
        }
        
        let response = try JSONDecoder().decode(SearchResponse.self, from: data)
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
            "timestamp": ISO8601DateFormatter().string(from: Date())
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
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(OpenCodeStatus.self, from: data)
    }
    
    func fetchModels() async throws -> ModelsResponse {
        let url = baseURL.appendingPathComponent("/v1/opencode/models")
        let request = authenticatedRequest(for: url)
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(ModelsResponse.self, from: data)
    }
    
    func fetchCodebases() async throws -> [Codebase] {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode([Codebase].self, from: data)
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
        
        let response = try JSONDecoder().decode(CodebaseResponse.self, from: data)
        return response.codebase
    }
    
    func unregisterCodebase(id: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(id)")
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        
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
        return try JSONDecoder().decode(TriggerResponse.self, from: data)
    }
    
    func interruptAgent(codebaseId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/interrupt")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (_, _) = try await session.data(for: request)
    }
    
    func stopAgent(codebaseId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/stop")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (_, _) = try await session.data(for: request)
    }
    
    func startWatchMode(codebaseId: String, interval: Int = 5) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/watch/start")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = ["interval": interval]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (_, _) = try await session.data(for: request)
    }
    
    func stopWatchMode(codebaseId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/watch/stop")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (_, _) = try await session.data(for: request)
    }
    
    // MARK: - Task API
    
    func fetchTasks() async throws -> [AgentTask] {
        let url = baseURL.appendingPathComponent("/v1/opencode/tasks")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode([AgentTask].self, from: data)
    }
    
    func createTask(codebaseId: String, title: String, description: String, priority: TaskPriority, context: String?) async throws -> AgentTask {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/tasks")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        var body: [String: Any] = [
            "title": title,
            "description": description,
            "priority": priority.rawValue
        ]
        if let context = context {
            body["context"] = context
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(AgentTask.self, from: data)
    }
    
    func cancelTask(taskId: String) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/tasks/\(taskId)/cancel")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        
        let (_, _) = try await session.data(for: request)
    }
    
    // MARK: - OpenCode Events SSE (Agent Output Streaming)
    
    func connectToAgentEvents(codebaseId: String, onEvent: @escaping (AgentEvent) -> Void) -> URLSessionDataTask? {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/events")
        var request = URLRequest(url: url)
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")
        
        let delegate = AgentEventSSEDelegate(onEvent: onEvent)
        let sseSession = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)
        let task = sseSession.dataTask(with: request)
        task.resume()
        return task
    }
    
    func fetchSessionMessages(codebaseId: String, limit: Int = 50) async throws -> [SessionMessage] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/messages"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        
        let (data, _) = try await session.data(from: components.url!)
        
        struct MessagesResponse: Codable {
            let messages: [SessionMessage]
            let sessionId: String?
            
            enum CodingKeys: String, CodingKey {
                case messages
                case sessionId = "session_id"
            }
        }
        
        let response = try JSONDecoder().decode(MessagesResponse.self, from: data)
        return response.messages
    }
    
    func fetchAgentStatus(codebaseId: String) async throws -> AgentStatusResponse {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/status")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(AgentStatusResponse.self, from: data)
    }
    
    func sendAgentMessage(codebaseId: String, message: String, agent: String? = nil) async throws -> TriggerResponse {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/message")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        var body: [String: Any] = ["message": message]
        if let agent = agent {
            body["agent"] = agent
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(TriggerResponse.self, from: data)
    }
    
    // MARK: - Worker API
    
    func fetchWorkers() async throws -> [Worker] {
        let url = baseURL.appendingPathComponent("/v1/opencode/workers")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode([Worker].self, from: data)
    }
    
    func registerWorker(workerId: String, name: String, capabilities: [String], hostname: String?) async throws -> Worker {
        let url = baseURL.appendingPathComponent("/v1/opencode/workers/register")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
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
        
        let response = try JSONDecoder().decode(WorkerResponse.self, from: data)
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
        return try JSONDecoder().decode(WatchStatus.self, from: data)
    }
    
    // MARK: - Monitor Stats
    
    func fetchStats() async throws -> ServerStats {
        let url = baseURL.appendingPathComponent("/v1/monitor/stats")
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(ServerStats.self, from: data)
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
    private var buffer = ""
    
    init(onEvent: @escaping (SSEEvent) -> Void) {
        self.onEvent = onEvent
    }
    
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard let string = String(data: data, encoding: .utf8) else { return }
        buffer += string
        processBuffer()
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
