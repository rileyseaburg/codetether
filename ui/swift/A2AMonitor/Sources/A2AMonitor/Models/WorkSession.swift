import Foundation

/// Local UI identity is separate from the worker's actual conversation ID.
struct WorkSession: Codable, Identifiable, Hashable {
    let id: UUID
    let workerId: String
    let workerName: String
    let workspaceId: String
    let workspaceName: String
    let workspacePath: String
    var model: String?
    var title: String
    var remoteSessionId: String?
    var turns: [WorkTurn]
    let createdAt: Date

    /// A2A worker protocol pins/resumes this client-created conversation identity.
    var contextId: String { "ios-" + id.uuidString.lowercased() }
    var currentTaskId: String? { turns.last?.taskId }
    var isRunning: Bool { turns.last.map { [.pending, .working].contains($0.status) } ?? false }
}

struct WorkTurn: Codable, Identifiable, Hashable {
    let id: UUID
    let prompt: String
    var taskId: String?
    var status: TaskStatus
    var response: String?
    var error: String?
}

enum WorkSessionError: LocalizedError {
    case missingSession, alreadyRunning, missingRemoteSession, wrongTask, emptyPrompt, selectModel, wrongProject
    var errorDescription: String? {
        switch self {
        case .missingSession: return "This work session is no longer available."
        case .alreadyRunning: return "The agent is still working. Wait for its response before sending another message."
        case .missingRemoteSession: return "The worker did not return a conversation ID. Start a new session rather than silently losing context."
        case .wrongTask: return "The server returned a different task. The conversation was not updated."
        case .emptyPrompt: return "Type a message for the agent."
        case .selectModel: return "Choose a model advertised by this agent before sending."
        case .wrongProject: return "This project is no longer assigned to the selected agent. Refresh and choose a project."
        }
    }
}