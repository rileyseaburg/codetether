import Foundation

struct AgentCallFailure {
    let title: String
    let message: String
    let canChooseModel: Bool

    init(_ detail: String) {
        let text = detail.lowercased()
        if text.contains("codex") && text.contains("backend is disabled") {
            title = "Selected backend is disabled"
            message = "The worker rejected its OpenAI Codex backend configuration. Choose a different provider/model, then retry. Your conversation is retained."
            canChooseModel = true
        } else if text.contains("model") && (text.contains("not found") || text.contains("not available") || text.contains("unsupported")) {
            title = "The worker rejected this model"
            message = "Refresh the advertised model list, choose another model, and retry."
            canChooseModel = true
        } else if text.contains("commit/push") || text.contains("non-fast-forward") {
            title = "Project automation failed"
            message = "The agent's Git finalization failed. Review the project changes and Git state before retrying; do not force-push."
            canChooseModel = false
        } else if text.contains("401") || text.contains("403") || text.contains("unauthorized") {
            title = "Access was rejected"
            message = "The platform or provider rejected access. Check your sign-in and this agent's provider configuration."
            canChooseModel = true
        } else {
            title = "The agent could not finish"
            message = "Review the details below. You can change the model or retry without discarding this conversation."
            canChooseModel = true
        }
    }
}