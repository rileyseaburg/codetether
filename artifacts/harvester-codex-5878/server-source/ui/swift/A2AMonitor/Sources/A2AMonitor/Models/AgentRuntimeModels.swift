import Foundation

// MARK: - Unified codetether-agent Runtime Models
//
// These models back the `/v1/agent/*` control-plane surface, giving the app
// deeper insight into the codetether-agent fleet than the `/v1/opencode/*`
// endpoints alone: runtime sessions (the harvester/agent session store),
// richly-classified workers, worker profiles, and per-worker agent definitions.

// MARK: - Runtime Session

/// A codetether-agent session as stored in the agent runtime session store
/// (surfaced by `GET /v1/agent/runtime/sessions`). Distinct from
/// `SessionSummary`, which models the opencode codebase session shape.
struct RuntimeSession: Codable, Identifiable, Hashable {
    let id: String
    let projectId: String?
    let directory: String?
    let title: String?
    let version: String?
    /// Server emits epoch milliseconds for runtime session timestamps.
    let createdAt: Double?
    let updatedAt: Double?
    let summary: RuntimeSessionSummary?

    enum CodingKeys: String, CodingKey {
        case id
        case projectId = "project_id"
        case directory
        case title
        case version
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case summary
    }

    var createdDate: Date? { Self.date(fromEpoch: createdAt) }
    var updatedDate: Date? { Self.date(fromEpoch: updatedAt) }

    private static func date(fromEpoch value: Double?) -> Date? {
        guard let value, value > 0 else { return nil }
        // Heuristic: values larger than ~year 2001 in seconds are milliseconds.
        let seconds = value > 1_000_000_000_000 ? value / 1000.0 : value
        return Date(timeIntervalSince1970: seconds)
    }
}

/// Free-form summary block attached to a runtime session. Decoded leniently
/// because the server stores arbitrary agent-generated summary metadata.
struct RuntimeSessionSummary: Codable, Hashable {
    let text: String?

    init(from decoder: Decoder) throws {
        // Accept either a bare string or an object with a `text`/`summary` key.
        if let single = try? decoder.singleValueContainer(),
           let str = try? single.decode(String.self) {
            text = str
            return
        }
        let container = try? decoder.container(keyedBy: DynamicKey.self)
        text = container?.firstString(of: ["text", "summary", "content"])
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(text)
    }
}

/// A message inside a runtime session (`GET /v1/agent/runtime/sessions/{id}/messages`).
struct RuntimeSessionMessage: Codable, Identifiable, Hashable {
    let id: String
    let sessionId: String?
    let role: String?
    let createdAt: Double?
    let model: String?
    let cost: Double?
    let tokens: Int?

    enum CodingKeys: String, CodingKey {
        case id
        case sessionId = "session_id"
        case role
        case createdAt = "created_at"
        case model
        case cost
        case tokens
    }
}

// MARK: - Runtime Session Responses

struct RuntimeSessionsResponse: Codable {
    let sessions: [RuntimeSession]
    let total: Int
    let limit: Int?
    let offset: Int?
}

struct RuntimeSessionResponse: Codable {
    let session: RuntimeSession
}

struct RuntimeSessionMessagesResponse: Codable {
    let messages: [RuntimeSessionMessage]
    let total: Int?
    let sessionId: String?

    enum CodingKeys: String, CodingKey {
        case messages
        case total
        case sessionId = "session_id"
    }
}

// MARK: - Worker Runtime Classification

enum WorkerRuntime: String, Codable {
    case rust
    case python
    case unknown

    init(from decoder: Decoder) throws {
        let raw = (try? decoder.singleValueContainer().decode(String.self)) ?? ""
        self = WorkerRuntime(rawValue: raw.lowercased()) ?? .unknown
    }

    var displayName: String {
        switch self {
        case .rust: return "Rust Worker"
        case .python: return "Legacy Python Worker"
        case .unknown: return "Worker"
        }
    }

    var iconName: String {
        switch self {
        case .rust: return "bolt.fill"
        case .python: return "tortoise.fill"
        case .unknown: return "questionmark.circle"
        }
    }
}

/// Detailed worker record from `GET /v1/agent/workers`, including the
/// server-inferred runtime classification and harvester annotations.
struct AgentWorker: Codable, Identifiable, Hashable {
    let workerId: String
    let name: String?
    let capabilities: [String]
    let hostname: String?
    let registeredAt: String?
    let lastSeen: String?
    let status: String?
    let models: [String]
    let workerRuntime: WorkerRuntime
    let workerRuntimeLabel: String?

    var id: String { workerId }

    enum CodingKeys: String, CodingKey {
        case workerId = "worker_id"
        case name
        case capabilities
        case hostname
        case registeredAt = "registered_at"
        case lastSeen = "last_seen"
        case status
        case models
        case workerRuntime = "worker_runtime"
        case workerRuntimeLabel = "worker_runtime_label"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        workerId = try c.decode(String.self, forKey: .workerId)
        name = try c.decodeIfPresent(String.self, forKey: .name)
        capabilities = (try? c.decodeIfPresent([String].self, forKey: .capabilities)) ?? []
        hostname = try? c.decodeIfPresent(String.self, forKey: .hostname)
        registeredAt = try? c.decodeIfPresent(String.self, forKey: .registeredAt)
        lastSeen = try? c.decodeIfPresent(String.self, forKey: .lastSeen)
        status = try? c.decodeIfPresent(String.self, forKey: .status)
        models = (try? c.decodeIfPresent([String].self, forKey: .models)) ?? []
        workerRuntime = (try? c.decodeIfPresent(WorkerRuntime.self, forKey: .workerRuntime)) ?? .unknown
        workerRuntimeLabel = try? c.decodeIfPresent(String.self, forKey: .workerRuntimeLabel)
    }

    /// True when this worker is a Harvester/KubeVirt persistent-workspace worker,
    /// inferred from its server-annotated capabilities or stable name prefix.
    var isHarvester: Bool {
        let lowered = capabilities.map { $0.lowercased() }
        if lowered.contains("harvester")
            || lowered.contains("persistent-workspace")
            || lowered.contains("persistent_workspace") {
            return true
        }
        let n = (name ?? workerId).lowercased()
        return n.hasPrefix("harvester") || n.contains("-harvester-")
    }

    var displayLabel: String {
        workerRuntimeLabel ?? workerRuntime.displayName
    }
}

// MARK: - Worker Profile

/// A reusable worker provisioning profile (`GET /v1/agent/worker-profiles`).
struct WorkerProfile: Codable, Identifiable, Hashable {
    let id: String
    let slug: String?
    let name: String?
    let description: String?
    let builtin: Bool?
    let defaultCapabilities: [String]

    enum CodingKeys: String, CodingKey {
        case id
        case slug
        case name
        case description
        case builtin
        case defaultCapabilities = "default_capabilities"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        slug = try? c.decodeIfPresent(String.self, forKey: .slug)
        name = try? c.decodeIfPresent(String.self, forKey: .name)
        description = try? c.decodeIfPresent(String.self, forKey: .description)
        builtin = try? c.decodeIfPresent(Bool.self, forKey: .builtin)
        defaultCapabilities = (try? c.decodeIfPresent([String].self, forKey: .defaultCapabilities)) ?? []
    }
}

// MARK: - Worker Agent Definition

/// A custom agent definition attached to a worker
/// (`GET /v1/agent/workers/{worker_id}/agents`).
struct WorkerAgentDefinition: Codable, Identifiable, Hashable {
    let id: String
    let name: String?
    let description: String?
    let mode: String?
    let model: String?
    let native: Bool?
    let hidden: Bool?
    let workerId: String?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case description
        case mode
        case model
        case native
        case hidden
        case workerId = "worker_id"
    }
}

// MARK: - Dynamic decoding helper

/// Coding key that accepts arbitrary string names; used for lenient decoding of
/// free-form server objects (e.g. runtime session summaries).
struct DynamicKey: CodingKey {
    var stringValue: String
    var intValue: Int?
    init?(stringValue: String) { self.stringValue = stringValue }
    init?(intValue: Int) { self.intValue = intValue; self.stringValue = String(intValue) }
}

private extension KeyedDecodingContainer where Key == DynamicKey {
    func firstString(of names: [String]) -> String? {
        for name in names {
            if let key = DynamicKey(stringValue: name),
               let value = try? decodeIfPresent(String.self, forKey: key) {
                return value
            }
        }
        return nil
    }
}
