import Foundation
import Combine

/// A2A Server API Client with SSE support
@MainActor
class A2AClient: ObservableObject {
    @Published var isConnected = false
    @Published var connectionError: String?
    
    private var baseURL: URL
    private var eventSourceTask: URLSessionDataTask?
    private var session: URLSession
    private var cancellables = Set<AnyCancellable>()
    
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
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode([Agent].self, from: data)
    }
    
    func fetchMessages(limit: Int = 100) async throws -> [Message] {
        var components = URLComponents(url: baseURL.appendingPathComponent("/v1/monitor/messages"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        
        let (data, _) = try await session.data(from: components.url!)
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
        
        var body: [String: Any] = [
            "name": name,
            "path": path
        ]
        if let description = description {
            body["description"] = description
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(Codebase.self, from: data)
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
    
    func triggerAgent(codebaseId: String, prompt: String, agent: String = "build") async throws -> TriggerResponse {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/trigger")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "prompt": prompt,
            "agent": agent
        ]
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
    
    func startWatchMode(codebaseId: String, pollInterval: Double = 5.0) async throws {
        let url = baseURL.appendingPathComponent("/v1/opencode/codebases/\(codebaseId)/watch/start")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = ["poll_interval": pollInterval]
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
