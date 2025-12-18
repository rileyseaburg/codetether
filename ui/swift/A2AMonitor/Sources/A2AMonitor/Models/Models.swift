import Foundation

// MARK: - Agent Models

struct Agent: Identifiable, Codable, Hashable {
    let id: String
    let name: String
    var status: AgentStatus
    var description: String?
    var url: String?
    var messagesCount: Int
    var lastSeen: Date?

    enum CodingKeys: String, CodingKey {
        case id, name, status, description, url
        case messagesCount = "messages_count"
        case lastSeen = "last_seen"
    }
}

enum AgentStatus: String, Codable, CaseIterable {
    case idle
    case running
    case busy
    case watching
    case error
    case disconnected
    case stopped
    case unknown

    var color: String {
        switch self {
        case .idle: return "gray"
        case .running: return "green"
        case .busy: return "yellow"
        case .watching: return "cyan"
        case .error: return "red"
        case .disconnected: return "gray"
        case .stopped: return "gray"
        case .unknown: return "gray"
        }
    }

    var icon: String {
        switch self {
        case .idle: return "circle"
        case .running: return "play.circle.fill"
        case .busy: return "clock.fill"
        case .watching: return "eye.fill"
        case .error: return "exclamationmark.circle.fill"
        case .disconnected: return "wifi.slash"
        case .stopped: return "stop.circle"
        case .unknown: return "questionmark.circle"
        }
    }

    // Handle unknown status values gracefully
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let rawValue = try container.decode(String.self)
        self = AgentStatus(rawValue: rawValue) ?? .unknown
    }
}

// MARK: - Codebase Models

struct Codebase: Identifiable, Codable, Hashable {
    let id: String
    let name: String
    let path: String
    var status: AgentStatus
    var description: String?
    var registeredAt: Date?
    var lastTriggered: Date?
    var sessionId: String?
    var pendingTasks: Int
    var workingTasks: Int

    enum CodingKeys: String, CodingKey {
        case id, name, path, status, description
        case registeredAt = "registered_at"
        case lastTriggered = "last_triggered"
        case sessionId = "session_id"
        case pendingTasks = "pending_tasks"
        case workingTasks = "working_tasks"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        path = try container.decode(String.self, forKey: .path)
        status = try container.decodeIfPresent(AgentStatus.self, forKey: .status) ?? .idle
        description = try container.decodeIfPresent(String.self, forKey: .description)
        registeredAt = try container.decodeIfPresent(Date.self, forKey: .registeredAt)
        lastTriggered = try container.decodeIfPresent(Date.self, forKey: .lastTriggered)
        sessionId = try container.decodeIfPresent(String.self, forKey: .sessionId)
        pendingTasks = try container.decodeIfPresent(Int.self, forKey: .pendingTasks) ?? 0
        workingTasks = try container.decodeIfPresent(Int.self, forKey: .workingTasks) ?? 0
    }

    init(id: String, name: String, path: String, status: AgentStatus = .idle, description: String? = nil) {
        self.id = id
        self.name = name
        self.path = path
        self.status = status
        self.description = description
        self.registeredAt = nil
        self.lastTriggered = nil
        self.sessionId = nil
        self.pendingTasks = 0
        self.workingTasks = 0
    }
}

// MARK: - Message Models

struct Message: Identifiable, Codable, Hashable {
    let id: String
    let timestamp: Date
    let type: MessageType
    let agentName: String
    let content: String
    var metadata: [String: String]?
    var isFlagged: Bool

    enum CodingKeys: String, CodingKey {
        case id, timestamp, type, content, metadata
        case agentName = "agent_name"
        case isFlagged = "is_flagged"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString
        timestamp = try container.decodeIfPresent(Date.self, forKey: .timestamp) ?? Date()
        type = try container.decodeIfPresent(MessageType.self, forKey: .type) ?? .agent
        agentName = try container.decodeIfPresent(String.self, forKey: .agentName) ?? "Unknown"
        content = try container.decodeIfPresent(String.self, forKey: .content) ?? ""
        metadata = try container.decodeIfPresent([String: String].self, forKey: .metadata)
        isFlagged = try container.decodeIfPresent(Bool.self, forKey: .isFlagged) ?? false
    }

    init(id: String = UUID().uuidString, timestamp: Date = Date(), type: MessageType, agentName: String, content: String, metadata: [String: String]? = nil) {
        self.id = id
        self.timestamp = timestamp
        self.type = type
        self.agentName = agentName
        self.content = content
        self.metadata = metadata
        self.isFlagged = false
    }
}

enum MessageType: String, Codable, CaseIterable {
    case agent
    case human
    case system
    case tool

    var color: String {
        switch self {
        case .agent: return "blue"
        case .human: return "orange"
        case .system: return "purple"
        case .tool: return "green"
        }
    }

    var icon: String {
        switch self {
        case .agent: return "cpu"
        case .human: return "person.fill"
        case .system: return "gearshape.fill"
        case .tool: return "wrench.fill"
        }
    }
}

// MARK: - Task Models

struct AgentTask: Identifiable, Codable, Hashable {
    let id: String
    let title: String
    var description: String
    var status: TaskStatus
    var priority: TaskPriority
    var codebaseId: String?
    var context: String?
    var result: String?
    var createdAt: Date
    var updatedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, title, description, status, priority, context, result
        case codebaseId = "codebase_id"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString
        title = try container.decodeIfPresent(String.self, forKey: .title) ?? "Untitled"
        description = try container.decodeIfPresent(String.self, forKey: .description) ?? ""
        status = try container.decodeIfPresent(TaskStatus.self, forKey: .status) ?? .pending
        priority = try container.decodeIfPresent(TaskPriority.self, forKey: .priority) ?? .normal
        codebaseId = try container.decodeIfPresent(String.self, forKey: .codebaseId)
        context = try container.decodeIfPresent(String.self, forKey: .context)
        result = try container.decodeIfPresent(String.self, forKey: .result)
        createdAt = try container.decodeIfPresent(Date.self, forKey: .createdAt) ?? Date()
        updatedAt = try container.decodeIfPresent(Date.self, forKey: .updatedAt)
    }

    init(id: String = UUID().uuidString, title: String, description: String, status: TaskStatus = .pending, priority: TaskPriority = .normal, codebaseId: String? = nil) {
        self.id = id
        self.title = title
        self.description = description
        self.status = status
        self.priority = priority
        self.codebaseId = codebaseId
        self.context = nil
        self.result = nil
        self.createdAt = Date()
        self.updatedAt = nil
    }
}

enum TaskStatus: String, Codable, CaseIterable {
    case pending
    case working
    case completed
    case failed
    case cancelled

    // Handle backend variants (e.g. Python/bridge may emit 'running') gracefully.
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let raw = try container.decode(String.self)
        if let exact = TaskStatus(rawValue: raw) {
            self = exact
            return
        }
        if raw == "running" {
            self = .working
            return
        }
        self = .pending
    }

    var color: String {
        switch self {
        case .pending: return "yellow"
        case .working: return "blue"
        case .completed: return "green"
        case .failed: return "red"
        case .cancelled: return "gray"
        }
    }

    var icon: String {
        switch self {
        case .pending: return "clock"
        case .working: return "arrow.triangle.2.circlepath"
        case .completed: return "checkmark.circle.fill"
        case .failed: return "xmark.circle.fill"
        case .cancelled: return "nosign"
        }
    }
}

enum TaskPriority: Int, Codable, CaseIterable {
    case low = 1
    case normal = 2
    case high = 3
    case urgent = 4

    var label: String {
        switch self {
        case .low: return "Low"
        case .normal: return "Normal"
        case .high: return "High"
        case .urgent: return "Urgent"
        }
    }

    var color: String {
        switch self {
        case .low: return "green"
        case .normal: return "yellow"
        case .high: return "orange"
        case .urgent: return "red"
        }
    }
}

// MARK: - Agent Output Models

struct OutputEntry: Identifiable, Hashable {
    let id: String
    let timestamp: Date
    let type: OutputType
    var content: String
    var toolName: String?
    var toolInput: String?
    var toolOutput: String?
    var error: String?
    var isStreaming: Bool
    var tokens: TokenInfo?
    var cost: Double?

    init(id: String = UUID().uuidString, timestamp: Date = Date(), type: OutputType, content: String, toolName: String? = nil) {
        self.id = id
        self.timestamp = timestamp
        self.type = type
        self.content = content
        self.toolName = toolName
        self.toolInput = nil
        self.toolOutput = nil
        self.error = nil
        self.isStreaming = false
        self.tokens = nil
        self.cost = nil
    }
}

enum OutputType: String, Codable, CaseIterable {
    case text
    case reasoning
    case toolPending = "tool-pending"
    case toolRunning = "tool-running"
    case toolCompleted = "tool-completed"
    case toolError = "tool-error"
    case stepStart = "step-start"
    case stepFinish = "step-finish"
    case fileEdit = "file-edit"
    case command
    case status
    case diagnostics
    case error

    var label: String {
        switch self {
        case .text: return "Text"
        case .reasoning: return "Reasoning"
        case .toolPending: return "Tool Pending"
        case .toolRunning: return "Tool Running"
        case .toolCompleted: return "Tool Completed"
        case .toolError: return "Tool Error"
        case .stepStart: return "Step Start"
        case .stepFinish: return "Step Finish"
        case .fileEdit: return "File Edit"
        case .command: return "Command"
        case .status: return "Status"
        case .diagnostics: return "Diagnostics"
        case .error: return "Error"
        }
    }

    var icon: String {
        switch self {
        case .text: return "text.bubble"
        case .reasoning: return "brain"
        case .toolPending: return "clock"
        case .toolRunning: return "arrow.triangle.2.circlepath"
        case .toolCompleted: return "checkmark.circle"
        case .toolError: return "xmark.circle"
        case .stepStart: return "play.fill"
        case .stepFinish: return "stop.fill"
        case .fileEdit: return "doc.text"
        case .command: return "terminal"
        case .status: return "info.circle"
        case .diagnostics: return "magnifyingglass"
        case .error: return "exclamationmark.triangle"
        }
    }

    var color: String {
        switch self {
        case .text: return "teal"
        case .reasoning: return "yellow"
        case .toolPending: return "blue"
        case .toolRunning: return "orange"
        case .toolCompleted: return "green"
        case .toolError: return "red"
        case .stepStart: return "purple"
        case .stepFinish: return "purple"
        case .fileEdit: return "green"
        case .command: return "yellow"
        case .status: return "blue"
        case .diagnostics: return "cyan"
        case .error: return "red"
        }
    }
}

struct TokenInfo: Hashable {
    let input: Int
    let output: Int
}

// MARK: - Statistics

struct MonitorStats {
    var totalMessages: Int = 0
    var interventions: Int = 0
    var toolCalls: Int = 0
    var errors: Int = 0
    var tokens: Int = 0
    var averageResponseTime: Double = 0
    var responseTimes: [Double] = []

    mutating func addResponseTime(_ time: Double) {
        responseTimes.append(time)
        averageResponseTime = responseTimes.reduce(0, +) / Double(responseTimes.count)
    }
}

// MARK: - API Responses

struct OpenCodeStatus: Codable {
    let available: Bool
    let message: String?
    let opencodeBinary: String?

    enum CodingKeys: String, CodingKey {
        case available, message
        case opencodeBinary = "opencode_binary"
    }
}

struct TriggerResponse: Codable {
    let success: Bool
    let error: String?
    let sessionId: String?

    enum CodingKeys: String, CodingKey {
        case success, error
        case sessionId = "session_id"
    }
}

struct MessageCountResponse: Codable {
    let total: Int
}

// MARK: - OpenCode Extended Status

struct OpenCodeStatusExtended: Codable {
    let available: Bool
    let message: String?
    let opencodeBinary: String?
    let registeredCodebases: Int?
    let autoStart: Bool?

    enum CodingKeys: String, CodingKey {
        case available, message
        case opencodeBinary = "opencode_binary"
        case registeredCodebases = "registered_codebases"
        case autoStart = "auto_start"
    }
}

// MARK: - Agent Event (from SSE stream)

struct AgentEvent: Codable {
    let eventType: String
    let codebaseId: String
    let messageId: String?
    let sessionId: String?
    let partType: String?
    let text: String?
    let delta: String?
    let toolName: String?
    let callId: String?
    let status: String?
    let input: String?
    let output: String?
    let title: String?
    let error: String?
    let cost: Double?
    let tokens: TokenInfoResponse?
    let raw: [String: AnyCodable]?

    enum CodingKeys: String, CodingKey {
        case eventType = "event_type"
        case codebaseId = "codebase_id"
        case messageId = "message_id"
        case sessionId = "session_id"
        case partType = "part_type"
        case text, delta
        case toolName = "tool_name"
        case callId = "call_id"
        case status, input, output, title, error, cost, tokens, raw
    }
}

struct TokenInfoResponse: Codable, Hashable {
    let input: Int?
    let output: Int?
}

// MARK: - AnyCodable for raw JSON

struct AnyCodable: Codable, Hashable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let string = try? container.decode(String.self) {
            value = string
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues { $0.value }
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case let string as String: try container.encode(string)
        case let int as Int: try container.encode(int)
        case let double as Double: try container.encode(double)
        case let bool as Bool: try container.encode(bool)
        default: try container.encodeNil()
        }
    }

    static func == (lhs: AnyCodable, rhs: AnyCodable) -> Bool {
        String(describing: lhs.value) == String(describing: rhs.value)
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(String(describing: value))
    }
}

// MARK: - Session Message

// MARK: - Session Summary

/// A lightweight representation of an OpenCode session as returned by
/// `GET /v1/opencode/codebases/{codebase_id}/sessions`.
///
/// Note: the backend may return slightly different shapes depending on source
/// (worker sync vs local state vs direct OpenCode API), so decoding is tolerant.
struct SessionSummary: Identifiable, Codable, Hashable {
    let id: String
    let title: String?
    let agent: String?
    let messageCount: Int?
    let created: String?
    let updated: String?

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case agent
        case messageCount
        case message_count
        case created
        case created_at
        case updated
        case updated_at
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        id = (try? container.decode(String.self, forKey: .id)) ?? UUID().uuidString
        title = try? container.decodeIfPresent(String.self, forKey: .title)
        agent = try? container.decodeIfPresent(String.self, forKey: .agent)

        let mc1 = try? container.decodeIfPresent(Int.self, forKey: .messageCount)
        let mc2 = try? container.decodeIfPresent(Int.self, forKey: .message_count)
        messageCount = mc1 ?? mc2

        let c1 = try? container.decodeIfPresent(String.self, forKey: .created)
        let c2 = try? container.decodeIfPresent(String.self, forKey: .created_at)
        created = c1 ?? c2

        let u1 = try? container.decodeIfPresent(String.self, forKey: .updated)
        let u2 = try? container.decodeIfPresent(String.self, forKey: .updated_at)
        updated = u1 ?? u2
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)

        try container.encode(id, forKey: .id)
        try container.encodeIfPresent(title, forKey: .title)
        try container.encodeIfPresent(agent, forKey: .agent)
        try container.encodeIfPresent(messageCount, forKey: .messageCount)
        try container.encodeIfPresent(created, forKey: .created)
        try container.encodeIfPresent(updated, forKey: .updated)
    }
}

/// Response from `POST /v1/opencode/codebases/{codebase_id}/sessions/{session_id}/resume`.
///
/// For remote workers, the server queues a task and returns a `task_id`.
struct ResumeSessionResponse: Codable {
    let success: Bool
    let message: String?
    let taskId: String?
    let sessionId: String?
    let newSessionId: String?
    let activeSessionId: String?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case success
        case message
        case taskId = "task_id"
        case sessionId = "session_id"
        case newSessionId = "new_session_id"
        case activeSessionId = "active_session_id"
        case error
    }
}

struct SessionMessageInfo: Codable, Hashable {
    let role: String?
    let model: String?
    let content: AnyCodable?
}

struct SessionMessage: Codable, Identifiable {
    let id: String?
    let sessionID: String?
    let role: String?
    let info: SessionMessageInfo?
    let time: MessageTime?
    let model: String?
    let agent: String?
    let cost: Double?
    let tokens: TokenInfoResponse?
    let parts: [MessagePart]?

    var identifier: String {
        id ?? UUID().uuidString
    }

    /// A stable identifier for UI lists when `id` may be absent.
    var stableId: String {
        if let id {
            return id
        }
        let created = time?.created ?? ""
        let role = resolvedRole ?? ""
        let model = resolvedModel ?? ""
        let snippet = String(resolvedText.prefix(64))
        return "\(sessionID ?? "")|\(created)|\(role)|\(model)|\(snippet)"
    }

    /// Normalized role across backend shapes.
    var resolvedRole: String? {
        info?.role ?? role
    }

    /// True when the message should be rendered as a user/human message.
    var isUserMessage: Bool {
        let r = resolvedRole?.lowercased()
        return r == "user" || r == "human"
    }

    /// Normalized model across backend shapes.
    var resolvedModel: String? {
        info?.model ?? model
    }

    /// Best-effort message text extraction (parts first, then `info.content`).
    var resolvedText: String {
        if let parts {
            let text = parts.compactMap { $0.text }.joined()
            if !text.isEmpty {
                return text
            }
        }
        if let contentValue = info?.content?.value {
            if let s = contentValue as? String {
                return s
            }
            return String(describing: contentValue)
        }
        return ""
    }
}

struct MessageTime: Codable {
    let created: String?
    let completed: String?
}

struct MessagePart: Codable, Identifiable {
    let id: String?
    let type: String
    let text: String?
    let tool: String?
    let state: ToolState?

    var identifier: String {
        id ?? UUID().uuidString
    }

    var stableId: String {
        id ?? identifier
    }
}

struct ToolState: Codable {
    let status: String?
    let input: String?
    let output: String?
    let title: String?
    let error: String?
}

// MARK: - Agent Status Response

struct AgentStatusResponse: Codable {
    let id: String
    let name: String
    let path: String
    let status: String
    let opencodePort: Int?
    let sessionId: String?
    let watchMode: Bool
    let watchInterval: Int
    let workerId: String?
    let recentMessages: [SessionMessage]?

    enum CodingKeys: String, CodingKey {
        case id, name, path, status
        case opencodePort = "opencode_port"
        case sessionId = "session_id"
        case watchMode = "watch_mode"
        case watchInterval = "watch_interval"
        case workerId = "worker_id"
        case recentMessages = "recent_messages"
    }
}

// MARK: - Worker

struct Worker: Codable, Identifiable, Hashable {
    let workerId: String
    let name: String
    let capabilities: [String]
    let hostname: String?
    let registeredAt: String
    let lastSeen: String
    let status: String

    var id: String { workerId }

    enum CodingKeys: String, CodingKey {
        case workerId = "worker_id"
        case name, capabilities, hostname
        case registeredAt = "registered_at"
        case lastSeen = "last_seen"
        case status
    }
}

// MARK: - Watch Status

struct WatchStatus: Codable {
    let codebaseId: String
    let name: String
    let watchMode: Bool
    let status: String
    let interval: Int
    let pendingTasks: Int
    let runningTasks: Int

    enum CodingKeys: String, CodingKey {
        case codebaseId = "codebase_id"
        case name
        case watchMode = "watch_mode"
        case status, interval
        case pendingTasks = "pending_tasks"
        case runningTasks = "running_tasks"
    }
}

// MARK: - Server Stats

struct ServerStats: Codable {
    let totalMessages: Int
    let toolCalls: Int
    let errors: Int
    let tokens: Int
    let avgResponseTime: Double
    let activeAgents: Int
    let interventions: Int

    enum CodingKeys: String, CodingKey {
        case totalMessages = "total_messages"
        case toolCalls = "tool_calls"
        case errors, tokens
        case avgResponseTime = "avg_response_time"
        case activeAgents = "active_agents"
        case interventions
    }
}

// MARK: - AI Model

struct AIModel: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let provider: String
    let custom: Bool?
    let capabilities: AIModelCapabilities?

    struct AIModelCapabilities: Codable, Hashable {
        let reasoning: Bool?
        let attachment: Bool?
        let toolCall: Bool?

        enum CodingKeys: String, CodingKey {
            case reasoning, attachment
            case toolCall = "tool_call"
        }
    }

    var displayName: String {
        if custom == true {
            return "\(name) (Custom)"
        }
        return name
    }

    var providerIcon: String {
        switch provider.lowercased() {
        case let p where p.contains("anthropic"):
            return "brain"
        case let p where p.contains("openai"):
            return "sparkles"
        case let p where p.contains("google"):
            return "g.circle"
        case let p where p.contains("azure"):
            return "cloud"
        case let p where p.contains("deepseek"):
            return "magnifyingglass"
        case let p where p.contains("xai"):
            return "x.circle"
        case let p where p.contains("z.ai") || p.contains("glm"):
            return "wand.and.stars"
        default:
            return "cpu"
        }
    }
}

struct ModelsResponse: Codable {
    let models: [AIModel]
    let `default`: String?
}

// MARK: - Authentication Models

struct UserSession: Codable, Identifiable {
    let userId: String
    let email: String
    let username: String
    let name: String
    let sessionId: String
    let expiresAt: String
    let createdAt: String
    let lastActivity: String
    let deviceInfo: DeviceInfo
    let roles: [String]

    var id: String { sessionId }

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case email, username, name
        case sessionId = "session_id"
        case expiresAt = "expires_at"
        case createdAt = "created_at"
        case lastActivity = "last_activity"
        case deviceInfo = "device_info"
        case roles
    }

    var isAdmin: Bool {
        roles.contains("a2a-admin")
    }

    var displayName: String {
        name.isEmpty ? username : name
    }
}

struct DeviceInfo: Codable, Hashable {
    let deviceId: String?
    let deviceName: String?
    let deviceType: String?
    let ipAddress: String?
    let userAgent: String?

    enum CodingKeys: String, CodingKey {
        case deviceId = "device_id"
        case deviceName = "device_name"
        case deviceType = "device_type"
        case ipAddress = "ip_address"
        case userAgent = "user_agent"
    }
}

struct LoginResponse: Codable {
    let success: Bool
    let session: UserSession
    let accessToken: String
    let refreshToken: String?
    let expiresAt: String

    enum CodingKeys: String, CodingKey {
        case success, session
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresAt = "expires_at"
    }
}

struct RefreshResponse: Codable {
    let success: Bool
    let session: UserSession
    let accessToken: String
    let refreshToken: String?
    let expiresAt: String

    enum CodingKeys: String, CodingKey {
        case success, session
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresAt = "expires_at"
    }
}

struct AuthStatusResponse: Codable {
    let available: Bool
    let message: String
    let keycloakUrl: String?
    let realm: String?
    let activeSessions: Int?
    let agentSessions: Int?

    enum CodingKeys: String, CodingKey {
        case available, message
        case keycloakUrl = "keycloak_url"
        case realm
        case activeSessions = "active_sessions"
        case agentSessions = "agent_sessions"
    }
}

struct UserCodebaseAssociation: Codable, Identifiable, Hashable {
    let userId: String
    let codebaseId: String
    let codebaseName: String
    let codebasePath: String
    let role: String
    let createdAt: String
    let lastAccessed: String

    var id: String { codebaseId }

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case codebaseId = "codebase_id"
        case codebaseName = "codebase_name"
        case codebasePath = "codebase_path"
        case role
        case createdAt = "created_at"
        case lastAccessed = "last_accessed"
    }
}

struct UserAgentSession: Codable, Identifiable, Hashable {
    let userId: String
    let sessionId: String
    let codebaseId: String
    let agentType: String
    let opencodeSessionId: String?
    let createdAt: String
    let lastActivity: String
    let deviceId: String?
    let messageCount: Int

    var id: String { sessionId }

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case sessionId = "session_id"
        case codebaseId = "codebase_id"
        case agentType = "agent_type"
        case opencodeSessionId = "opencode_session_id"
        case createdAt = "created_at"
        case lastActivity = "last_activity"
        case deviceId = "device_id"
        case messageCount = "message_count"
    }
}

struct SyncState: Codable {
    let userId: String
    let activeDevices: Int
    let sessions: [UserSession]
    let agentSessions: [UserAgentSession]
    let codebases: [UserCodebaseAssociation]
    let syncedAt: String

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case activeDevices = "active_devices"
        case sessions
        case agentSessions = "agent_sessions"
        case codebases
        case syncedAt = "synced_at"
    }
}

// MARK: - Agent Event SSE Delegate

class AgentEventSSEDelegate: NSObject, URLSessionDataDelegate {
    private var onEvent: (AgentEvent) -> Void
    private var buffer = ""

    init(onEvent: @escaping (AgentEvent) -> Void) {
        self.onEvent = onEvent
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard let string = String(data: data, encoding: .utf8) else { return }
        buffer += string
        processBuffer()
    }

    private func processBuffer() {
        let chunks = buffer.components(separatedBy: "\n\n")

        for i in 0..<(chunks.count - 1) {
            let chunk = chunks[i]
            var eventData = ""

            for line in chunk.components(separatedBy: "\n") {
                if line.hasPrefix("data:") {
                    eventData = String(line.dropFirst(5)).trimmingCharacters(in: .whitespaces)
                }
            }

            if !eventData.isEmpty {
                if let data = eventData.data(using: .utf8),
                   let event = try? JSONDecoder().decode(AgentEvent.self, from: data) {
                    onEvent(event)
                }
            }
        }

        buffer = chunks.last ?? ""
    }
}
