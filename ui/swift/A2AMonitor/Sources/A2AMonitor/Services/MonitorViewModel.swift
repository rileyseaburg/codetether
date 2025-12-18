import SwiftUI
import Combine

/// Main ViewModel for the A2A Monitor app
@MainActor
class MonitorViewModel: ObservableObject {
    // MARK: - Published State

    // Connection
    @Published var isConnected = false
    @Published var connectionError: String?

    // OpenCode
    @Published var openCodeStatus: OpenCodeStatus?
    @Published var codebases: [Codebase] = []
    @Published var availableModels: [AIModel] = []
    @Published var defaultModel: String?

    // Agents
    @Published var agents: [Agent] = []

    // Messages
    @Published var messages: [Message] = []
    @Published var totalStoredMessages: Int = 0
    @Published var messageFilter: MessageType?
    @Published var searchQuery: String = ""

    // Sessions
    @Published var sessions: [SessionSummary] = []
    @Published var selectedSessionsCodebaseId: String?
    @Published var sessionMessages: [SessionMessage] = []

    // Tasks
    @Published var tasks: [AgentTask] = []
    @Published var taskFilter: TaskStatus?

    // Agent Output
    @Published var agentOutputs: [String: [OutputEntry]] = [:]
    @Published var selectedCodebaseForOutput: String?
    @Published var autoScrollOutput = true

    // Statistics
    @Published var stats = MonitorStats()

    // UI State
    @Published var isLoading = false
    @Published var showingTriggerSheet = false
    @Published var showingTaskSheet = false
    @Published var showingRegisterSheet = false
    @Published var selectedCodebase: Codebase?

    // MARK: - Private

    private let client: A2AClient
    private var refreshTimer: Timer?
    private var cancellables = Set<AnyCancellable>()

    // MARK: - Settings

    @AppStorage("serverURL") var serverURL = "https://api.codetether.run" {
        didSet {
            client.updateBaseURL(serverURL)
        }
    }

    @AppStorage("refreshInterval") var refreshInterval: Double = 5.0

    // MARK: - Init

    init() {
        self.client = A2AClient(baseURL: UserDefaults.standard.string(forKey: "serverURL") ?? "https://api.codetether.run")
        setupCallbacks()
    }

    // MARK: - Auth Integration

    /// Set the auth service to enable authenticated requests
    func setAuthService(_ authService: AuthService) {
        client.authService = authService
        // Also sync the base URL
        client.updateBaseURL(serverURL)
    }

    /// Update server URL from login/settings
    func updateServerURL(_ url: String) {
        serverURL = url
        client.updateBaseURL(url)
    }

    // MARK: - Setup

    private func setupCallbacks() {
        client.onMessage = { [weak self] message in
            Task { @MainActor in
                self?.handleNewMessage(message)
            }
        }

        client.onAgentStatus = { [weak self] agent in
            Task { @MainActor in
                self?.updateAgentStatus(agent)
            }
        }
    }

    // MARK: - Connection

    func connect() {
        client.connectToMonitorStream()
        isConnected = true

        // Initial data load
        Task {
            await loadInitialData()
        }

        // Start refresh timer
        startRefreshTimer()
    }

    func disconnect() {
        client.disconnectStream()
        isConnected = false
        stopRefreshTimer()
    }

    func reconnect() {
        disconnect()
        connect()
    }

    // MARK: - Refresh Timer

    private func startRefreshTimer() {
        stopRefreshTimer()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: refreshInterval, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.refreshData()
            }
        }
    }

    private func stopRefreshTimer() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }

    // MARK: - Data Loading

    func loadInitialData() async {
        isLoading = true

        async let openCodeTask: () = loadOpenCodeStatus()
        async let codebasesTask: () = loadCodebases()
        async let modelsTask: () = loadModels()
        async let agentsTask: () = loadAgents()
        async let messagesTask: () = loadMessages()
        async let sessionsTask: () = loadSessions()
        async let tasksTask: () = loadTasks()
        async let countTask: () = loadMessageCount()

        _ = await (openCodeTask, codebasesTask, modelsTask, agentsTask, messagesTask, sessionsTask, tasksTask, countTask)

        isLoading = false
    }

    func refreshData() async {
        await loadCodebases()
        await loadModels()
        await loadAgents()
        await loadTasks()
        await loadMessageCount()
    }

    // MARK: - OpenCode

    func loadOpenCodeStatus() async {
        do {
            openCodeStatus = try await client.fetchOpenCodeStatus()
        } catch {
            print("Failed to load OpenCode status: \(error)")
        }
    }

    func loadCodebases() async {
        do {
            codebases = try await client.fetchCodebases()
        } catch {
            print("Failed to load codebases: \(error)")
        }
    }

    func loadModels() async {
        do {
            let response = try await client.fetchModels()
            availableModels = response.models
            defaultModel = response.default
        } catch {
            print("Failed to load models: \(error)")
            // Fallback models
            availableModels = [
                AIModel(id: "google/gemini-3-flash-preview", name: "Gemini 3 Flash (Preview)", provider: "Google", custom: nil, capabilities: nil),
                AIModel(id: "z-ai/coding-plain-v1", name: "Z.AI Coding Plain v1", provider: "Z.AI Coding Plan", custom: nil, capabilities: nil),
                AIModel(id: "z-ai/coding-plain-v2", name: "Z.AI Coding Plain v2", provider: "Z.AI Coding Plan", custom: nil, capabilities: nil),
                AIModel(id: "anthropic/claude-3-5-sonnet-20241022", name: "Claude 3.5 Sonnet", provider: "Anthropic", custom: nil, capabilities: nil),
                AIModel(id: "openai/gpt-4o", name: "GPT-4o", provider: "OpenAI", custom: nil, capabilities: nil),
            ]
        }
    }

    func registerCodebase(name: String, path: String, description: String?) async throws {
        let codebase = try await client.registerCodebase(name: name, path: path, description: description)
        codebases.append(codebase)
    }

    func unregisterCodebase(_ codebase: Codebase) async throws {
        try await client.unregisterCodebase(id: codebase.id)
        codebases.removeAll { $0.id == codebase.id }
    }

    func triggerAgent(codebase: Codebase, prompt: String, agent: String = "build", model: String? = nil) async throws {
        let response = try await client.triggerAgent(codebaseId: codebase.id, prompt: prompt, agent: agent, model: model)
        if !response.success {
            throw A2AError.interventionFailed
        }
        await loadCodebases()
    }

    func interruptAgent(_ codebase: Codebase) async throws {
        try await client.interruptAgent(codebaseId: codebase.id)
        await loadCodebases()
    }

    func stopAgent(_ codebase: Codebase) async throws {
        try await client.stopAgent(codebaseId: codebase.id)
        await loadCodebases()
    }

    func startWatchMode(_ codebase: Codebase) async throws {
        try await client.startWatchMode(codebaseId: codebase.id)
        await loadCodebases()
    }

    func stopWatchMode(_ codebase: Codebase) async throws {
        try await client.stopWatchMode(codebaseId: codebase.id)
        await loadCodebases()
    }

    // MARK: - Agents

    func loadAgents() async {
        do {
            agents = try await client.fetchAgents()
            stats.totalMessages = agents.reduce(0) { $0 + $1.messagesCount }
        } catch {
            print("Failed to load agents: \(error)")
        }
    }

    private func updateAgentStatus(_ agent: Agent) {
        if let index = agents.firstIndex(where: { $0.id == agent.id }) {
            agents[index] = agent
        } else {
            agents.append(agent)
        }
    }

    // MARK: - Messages

    func loadMessages(limit: Int = 100) async {
        do {
            messages = try await client.fetchMessages(limit: limit)
        } catch {
            print("Failed to load messages: \(error)")
        }
    }

    func loadMessageCount() async {
        do {
            totalStoredMessages = try await client.fetchMessageCount()
        } catch {
            print("Failed to load message count: \(error)")
        }
    }

    func searchMessages(query: String) async {
        guard !query.isEmpty else {
            await loadMessages()
            return
        }

        do {
            messages = try await client.searchMessages(query: query)
        } catch {
            print("Failed to search messages: \(error)")
        }
    }

    private func handleNewMessage(_ message: Message) {
        messages.insert(message, at: 0)
        stats.totalMessages += 1

        // If a task was started elsewhere (e.g., web UI) and the agent emits a message,
        // surface it as a local alert on mobile.
        NotificationService.shared.notifyIfNeeded(for: message)

        // Track tool calls
        if message.type == .tool {
            stats.toolCalls += 1
        }

        // Keep only latest 500 messages in memory
        if messages.count > 500 {
            messages = Array(messages.prefix(500))
        }
    }

    func flagMessage(_ message: Message) {
        if let index = messages.firstIndex(where: { $0.id == message.id }) {
            var updated = messages[index]
            updated.isFlagged = true
            messages[index] = updated
        }
    }

    var filteredMessages: [Message] {
        var result = messages

        if let filter = messageFilter {
            result = result.filter { $0.type == filter }
        }

        if !searchQuery.isEmpty {
            result = result.filter {
                $0.content.localizedCaseInsensitiveContains(searchQuery) ||
                $0.agentName.localizedCaseInsensitiveContains(searchQuery)
            }
        }

        return result
    }

    // MARK: - Sessions

    func loadSessions() async {
        // Best-effort: if a codebase is selected, load sessions for it. Otherwise,
        // leave sessions empty until the Sessions tab selects a codebase.
        guard let codebaseId = selectedSessionsCodebaseId ?? codebases.first?.id else {
            sessions = []
            return
        }
        await loadSessions(for: codebaseId)
    }

    func loadSessions(for codebaseId: String) async {
        selectedSessionsCodebaseId = codebaseId
        do {
            sessions = try await client.fetchSessions(codebaseId: codebaseId)
        } catch {
            print("Failed to load sessions for codebase \(codebaseId): \(error)")
            sessions = []
        }
    }

    func loadSessionMessages(codebaseId: String, sessionId: String, limit: Int = 100) async {
        do {
            sessionMessages = try await client.fetchSessionMessages(codebaseId: codebaseId, sessionId: sessionId, limit: limit)
        } catch {
            print("Failed to load session messages (codebase=\(codebaseId), session=\(sessionId)): \(error)")
            sessionMessages = []
        }
    }

    func sendSessionPrompt(codebaseId: String, sessionId: String, prompt: String, agent: String = "build", model: String? = nil) async -> Bool {
        do {
            return try await client.resumeSession(codebaseId: codebaseId, sessionId: sessionId, prompt: prompt, agent: agent, model: model)
        } catch {
            print("Failed to send session prompt: \(error)")
            return false
        }
    }

    func sendSessionPromptDetailed(
        codebaseId: String,
        sessionId: String,
        prompt: String,
        agent: String = "build",
        model: String? = nil
    ) async -> ResumeSessionResponse? {
        do {
            return try await client.resumeSessionDetailed(
                codebaseId: codebaseId,
                sessionId: sessionId,
                prompt: prompt,
                agent: agent,
                model: model
            )
        } catch {
            print("Failed to send session prompt (detailed): \(error)")
            return nil
        }
    }

    func fetchTask(taskId: String) async -> AgentTask? {
        do {
            return try await client.fetchTask(taskId: taskId)
        } catch {
            print("Failed to fetch task \(taskId): \(error)")
            return nil
        }
    }

    // MARK: - Tasks

    func loadTasks() async {
        do {
            tasks = try await client.fetchTasks()
        } catch {
            print("Failed to load tasks: \(error)")
        }
    }

    func createTask(codebase: Codebase, title: String, description: String, priority: TaskPriority, context: String?) async throws {
        let task = try await client.createTask(
            codebaseId: codebase.id,
            title: title,
            description: description,
            priority: priority,
            context: context
        )
        tasks.insert(task, at: 0)
    }

    func cancelTask(_ task: AgentTask) async throws {
        try await client.cancelTask(taskId: task.id)
        await loadTasks()
    }

    func startTask(_ task: AgentTask) async throws {
        guard let codebaseId = task.codebaseId,
              let codebase = codebases.first(where: { $0.id == codebaseId }) else {
            return
        }

        let prompt = """
        Task: \(task.title)

        Description: \(task.description)
        \(task.context != nil ? "\nContext: \(task.context!)" : "")
        """

        try await triggerAgent(codebase: codebase, prompt: prompt)
        await loadTasks()
    }

    var filteredTasks: [AgentTask] {
        guard let filter = taskFilter else { return tasks }
        return tasks.filter { $0.status == filter }
    }

    // MARK: - Agent Output

    func addOutputEntry(_ entry: OutputEntry, for codebaseId: String) {
        if agentOutputs[codebaseId] == nil {
            agentOutputs[codebaseId] = []
        }

        agentOutputs[codebaseId]?.append(entry)

        // Limit entries
        if let count = agentOutputs[codebaseId]?.count, count > 500 {
            agentOutputs[codebaseId]?.removeFirst()
        }

        // Update stats
        if entry.type == .toolCompleted {
            stats.toolCalls += 1
        }
        if entry.type == .error || entry.type == .toolError {
            stats.errors += 1
        }
        if let tokens = entry.tokens {
            stats.tokens += tokens.input + tokens.output
        }
    }

    func clearOutput(for codebaseId: String) {
        agentOutputs[codebaseId] = []
    }

    var currentOutput: [OutputEntry] {
        guard let codebaseId = selectedCodebaseForOutput else { return [] }
        return agentOutputs[codebaseId] ?? []
    }

    // MARK: - Intervention

    func sendIntervention(agentId: String, message: String) async throws {
        try await client.sendIntervention(agentId: agentId, message: message)
        stats.interventions += 1

        // Add to messages
        let interventionMessage = Message(
            type: .human,
            agentName: "Human Operator",
            content: "Intervention: \(message)",
            metadata: ["intervention": "true"]
        )
        handleNewMessage(interventionMessage)
    }

    // MARK: - Export

    func exportMessages() -> Data? {
        try? JSONEncoder().encode(messages)
    }

    func exportTasks() -> Data? {
        try? JSONEncoder().encode(tasks)
    }
}
