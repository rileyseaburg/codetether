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
    
    var color: String {
        switch self {
        case .idle: return "gray"
        case .running: return "green"
        case .busy: return "yellow"
        case .watching: return "cyan"
        case .error: return "red"
        case .disconnected: return "gray"
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
        }
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
