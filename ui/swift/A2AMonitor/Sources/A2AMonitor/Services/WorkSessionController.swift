import Foundation
import Combine
import CryptoKit

@MainActor
final class WorkSessionController: ObservableObject {
    @Published private(set) var workers: [AgentWorker] = []
    @Published private(set) var workspaces: [Codebase] = []
    @Published private(set) var sessions: [WorkSession] = []
    @Published private(set) var isRefreshing = false
    @Published var errorMessage: String?
    private let client: A2AClient
    private var storageURL: URL?
    private var persistenceIdentity: String?

    init(client: A2AClient) { self.client = client }

    /// Persist only this signed-in account's conversations; never share across accounts/servers.
    func configurePersistence(userId: String?, serverURL: String) {
        let identity = "\(serverURL)|\(userId ?? "guest")"
        guard persistenceIdentity != identity else { return }
        persistenceIdentity = identity
        sessions = []
        storageURL = nil
        guard let userId, !userId.isEmpty else { return }
        do {
            let base = try FileManager.default.url(for: .applicationSupportDirectory,
                in: .userDomainMask, appropriateFor: nil, create: true).appendingPathComponent("WorkSessions")
            try FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
            let digest = SHA256.hash(data: Data("\(serverURL)|\(userId)".utf8)).map { String(format: "%02x", $0) }.joined()
            let url = base.appendingPathComponent(digest + ".json")
            storageURL = url
            if FileManager.default.fileExists(atPath: url.path) {
                sessions = try JSONDecoder().decode([WorkSession].self, from: Data(contentsOf: url))
            }
        } catch { errorMessage = "Could not restore this account's work sessions: \(error.localizedDescription)" }
    }

    var onlineWorkers: [AgentWorker] { workers.filter { $0.isOnline && $0.supportsWorkSessions } }
    var taskOnlyWorkers: [AgentWorker] { workers.filter { $0.isOnline && !$0.supportsWorkSessions } }

    func projects(for worker: AgentWorker) -> [Codebase] {
        Self.selectableProjects(workspaces, for: worker)
    }

    static func selectableProjects(_ projects: [Codebase], for worker: AgentWorker) -> [Codebase] {
        func normalizedPath(_ path: String) -> String {
            var value = path
            while value.count > 1 && value.hasSuffix("/") { value.removeLast() }
            return value
        }
        let advertisedPaths = Set(worker.workspaces.map(normalizedPath))
        return projects.filter { project in
            if let owner = project.workerId, !owner.isEmpty {
                return owner == worker.workerId
            }
            // A shared clone root is not ownership of all historical descendants.
            // Only an exact advertised folder can supply a missing owner binding.
            return !project.path.isEmpty && advertisedPaths.contains(normalizedPath(project.path))
        }.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    func refresh() async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }
        do {
            async let online = client.fetchAgentWorkers(onlineOnly: true)
            async let projects = client.fetchCodebases()
            (workers, workspaces) = try await (online, projects)
            errorMessage = nil
        } catch { errorMessage = error.localizedDescription }
    }

    func session(_ id: UUID) -> WorkSession? { sessions.first { $0.id == id } }

    func start(worker: AgentWorker, workspace: Codebase, prompt: String, model: String?) async throws -> UUID {
        let text = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { throw WorkSessionError.emptyPrompt }
        let selected = model?.trimmingCharacters(in: .whitespacesAndNewlines)
        let resolved = selected.flatMap { $0.isEmpty ? nil : $0 } ?? WorkerModelOption.preferredID(in: worker.modelOptions)
        guard let resolved, worker.modelOptions.contains(where: { $0.id == resolved }) else { throw WorkSessionError.selectModel }
        guard projects(for: worker).contains(where: { $0.id == workspace.id }) else { throw WorkSessionError.wrongProject }
        let id = UUID()
        let session = WorkSession(id: id, workerId: worker.workerId, workerName: worker.name ?? worker.workerId,
            workspaceId: workspace.id, workspaceName: workspace.name, workspacePath: workspace.path,
            model: resolved, title: String(text.prefix(70)),
            remoteSessionId: nil, turns: [], createdAt: Date())
        sessions.insert(session, at: 0)
        do { try await send(text, to: id) }
        catch { sessions.removeAll { $0.id == id }; persist(); throw error }
        return id
    }

    func send(_ prompt: String, to id: UUID) async throws {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { throw WorkSessionError.missingSession }
        let text = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { throw WorkSessionError.emptyPrompt }
        let current = sessions[index]
        guard !current.isRunning else { throw WorkSessionError.alreadyRunning }
        guard let model = current.model, !model.isEmpty else { throw WorkSessionError.selectModel }
        let turnId = UUID()
        sessions[index].turns.append(WorkTurn(id: turnId, prompt: text, taskId: nil, status: .pending))
        do {
            let task = try await client.createTask(codebaseId: current.workspaceId, title: current.title,
                description: text, priority: .normal, context: nil, targetWorkerId: current.workerId,
                model: model, targetAgentName: current.workerName,
                resumeSessionId: current.turns.isEmpty ? nil : (current.remoteSessionId ?? current.contextId),
                contextId: current.contextId)
            guard let i = sessions.firstIndex(where: { $0.id == id }),
                  let t = sessions[i].turns.firstIndex(where: { $0.id == turnId }) else { return }
            sessions[i].turns[t].taskId = task.id
            sessions[i].turns[t].status = task.status
            sessions[i].remoteSessionId = task.sessionId ?? current.remoteSessionId
            persist()
        } catch {
            if let i = sessions.firstIndex(where: { $0.id == id }) {
                sessions[i].turns.removeAll { $0.id == turnId }
            }
            throw error
        }
    }

    func poll(_ id: UUID) async throws {
        guard let current = session(id), let taskId = current.currentTaskId else { return }
        let task = try await client.fetchTask(taskId: taskId)
        guard task.id == taskId else { throw WorkSessionError.wrongTask }
        guard let index = sessions.firstIndex(where: { $0.id == id }),
              let turn = sessions[index].turns.firstIndex(where: { $0.taskId == taskId }) else { return }
        if let remote = task.sessionId {
            if let expected = current.remoteSessionId, expected != remote {
                sessions[index].turns[turn].status = .failed
                sessions[index].turns[turn].error = "The worker did not resume the original conversation. Start a new session."
                persist()
                return
            }
            sessions[index].remoteSessionId = remote
        }
        let hasError = !(task.error?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true)
        sessions[index].turns[turn].status = task.status == .completed && hasError ? .failed : task.status
        sessions[index].turns[turn].response = task.result
        sessions[index].turns[turn].error = task.error
        persist()
    }

    func models(for id: UUID) -> [WorkerModelOption] {
        guard let current = session(id) else { return [] }
        return workers.first { $0.workerId == current.workerId }?.modelOptions ?? []
    }

    func selectModel(_ model: String, for id: UUID) throws {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { throw WorkSessionError.missingSession }
        guard !sessions[index].isRunning else { throw WorkSessionError.alreadyRunning }
        guard models(for: id).contains(where: { $0.id == model }) else { throw WorkSessionError.selectModel }
        sessions[index].model = model
        persist()
    }

    func retry(_ id: UUID) async throws {
        guard let current = session(id), let turn = current.turns.last else { throw WorkSessionError.missingSession }
        guard turn.status == .failed || turn.status == .cancelled else { throw WorkSessionError.alreadyRunning }
        // Preserve the failed turn and ID; retry creates a distinct task in the same conversation.
        try await send(turn.prompt, to: id)
    }

    func stop(_ id: UUID) async throws {
        guard let taskId = session(id)?.currentTaskId else { return }
        try await client.cancelTask(taskId: taskId)
        try await poll(id)
    }

    private func persist() {
        guard let storageURL else { return }
        do {
            let data = try JSONEncoder().encode(sessions)
            #if os(iOS)
            try data.write(to: storageURL, options: [.atomic, .completeFileProtection])
            #else
            try data.write(to: storageURL, options: .atomic)
            #endif
        } catch { errorMessage = "Could not save work sessions on this device: \(error.localizedDescription)" }
    }
}







