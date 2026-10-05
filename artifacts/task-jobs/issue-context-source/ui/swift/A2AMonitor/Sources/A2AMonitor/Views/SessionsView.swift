import SwiftUI

/// Sessions View - Shows active sessions for a codebase
struct SessionsView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @State private var selectedCodebaseId: String = ""
    @State private var selectedSession: SessionSummary?
    @State private var showingSessionDetail = false

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header
                headerSection

                // Sessions List
                sessionsList
            }
            .padding(20)
        }
        .refreshable {
            await viewModel.refreshData()
        }
        .background(Color.clear)
        .navigationTitle("Sessions")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                ConnectionStatusBadge()
            }
        }
        .onAppear {
            // Pick a default codebase once we have codebases.
            if selectedCodebaseId.isEmpty, let first = viewModel.codebases.first {
                selectedCodebaseId = first.id
            }
            if !selectedCodebaseId.isEmpty {
                Task { await viewModel.loadSessions(for: selectedCodebaseId) }
            }
        }
        .sheet(isPresented: $showingSessionDetail) {
            if let session = selectedSession, !selectedCodebaseId.isEmpty {
                SessionDetailView(codebaseId: selectedCodebaseId, session: session)
                    .environmentObject(viewModel)
            }
        }
    }

    // MARK: - Header Section

    var headerSection: some View {
        GlassCard(cornerRadius: 24, padding: 24) {
            HStack(spacing: 20) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Active Sessions")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(Color.liquidGlass.textPrimary)

                    Text("Monitor and manage active agent sessions")
                        .font(.subheadline)
                        .foregroundColor(Color.liquidGlass.textSecondary)

                    if !viewModel.codebases.isEmpty {
                        Picker("Codebase", selection: $selectedCodebaseId) {
                            ForEach(viewModel.codebases) { cb in
                                Text(cb.name).tag(cb.id)
                            }
                        }
                        .pickerStyle(.menu)
                        .onChange(of: selectedCodebaseId) { _, newValue in
                            guard !newValue.isEmpty else { return }
                            Task {
                                await viewModel.loadSessions(for: newValue)
                            }
                        }
                    } else {
                        Text("No codebases available")
                            .font(.caption)
                            .foregroundColor(Color.liquidGlass.textMuted)
                    }
                }

                Spacer()

                // Session Stats
                HStack(spacing: 16) {
                    StatCard(
                        title: "Total Sessions",
                        value: "\(viewModel.sessions.count)",
                        icon: "person.2",
                        color: Color.liquidGlass.primary
                    )

                    StatCard(
                        title: "With Messages",
                        value: "\(viewModel.sessions.filter { ($0.messageCount ?? 0) > 0 }.count)",
                        icon: "text.bubble",
                        color: Color.liquidGlass.success
                    )

                    StatCard(
                        title: "Recent",
                        value: "\(min(viewModel.sessions.count, 10))",
                        icon: "clock.fill",
                        color: Color.liquidGlass.info
                    )
                }
            }
        }
    }

    // MARK: - Sessions List

    var sessionsList: some View {
        GlassCard(cornerRadius: 20, padding: 20) {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Image(systemName: "person.2")
                        .foregroundColor(Color.liquidGlass.primary)
                    Text("Recent Sessions")
                        .font(.headline)
                        .foregroundColor(Color.liquidGlass.textPrimary)

                    Spacer()
                }

                if viewModel.sessions.isEmpty {
                    EmptyStateView(
                        icon: "person.2",
                        title: "No Sessions Found",
                        message: selectedCodebaseId.isEmpty
                            ? "Select a project from the dropdown above to view its agent sessions."
                            : "This project has no recorded sessions yet. Sessions are created when you trigger an agent to work on your code. Go to the Agents tab to start one.",
                        action: selectedCodebaseId.isEmpty ? nil : { viewModel.showingRegisterSheet = true },
                        actionTitle: selectedCodebaseId.isEmpty ? nil : "Go to Agents"
                    )
                } else {
                    ForEach(viewModel.sessions) { session in
                        SessionRow(session: session)
                            .onTapGesture {
                                selectedSession = session
                                showingSessionDetail = true
                            }
                    }
                }
            }
        }
    }
}

// MARK: - Session Row

struct SessionRow: View {
    let session: SessionSummary

    var body: some View {
        HStack(spacing: 12) {
            // Status indicator
            Circle()
                .fill(statusColor)
                .frame(width: 10, height: 10)

            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(session.title ?? "Untitled Session")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(Color.liquidGlass.textPrimary)

                    Spacer()

                    Text(session.agent ?? "build")
                        .font(.caption2)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }

                Text(session.updated ?? session.created ?? "")
                    .font(.caption2)
                    .foregroundColor(Color.liquidGlass.textMuted)

                Text("\(session.messageCount ?? 0) messages")
                    .font(.caption2)
                    .foregroundColor(Color.liquidGlass.textMuted)
            }

            Spacer()
        }
        .padding(12)
        .background(Color.white.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    var statusColor: Color {
        // Determine status color based on session state
        // This would need to be enhanced with actual status information
        return Color.liquidGlass.info
    }
}

// MARK: - Session Detail View

struct SessionDetailView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    let codebaseId: String
    let session: SessionSummary

    /// Default model override (shared with web's key name).
    /// Empty string means: use server/model defaults.
    @AppStorage("codetether.model.default") private var modelOverride: String = ""

    /// Some resume paths can return a different session id (e.g. when OpenCode is started on-demand).
    /// We keep a local effective id so subsequent messages + refreshes hit the right session.
    @State private var effectiveSessionId: String

    @State private var draftMessage: String = ""
    @State private var isSending = false
    @State private var statusText: String?

    @State private var activeTaskId: String?
    @State private var activeTaskStatus: TaskStatus?
    @State private var taskPolling: Task<Void, Never>?

    init(codebaseId: String, session: SessionSummary) {
        self.codebaseId = codebaseId
        self.session = session
        _effectiveSessionId = State(initialValue: session.id)
    }

    var body: some View {
        VStack(spacing: 0) {
            if let activeTaskStatus, activeTaskStatus == .working || activeTaskStatus == .pending {
                HStack(spacing: 10) {
                    ProgressView()
                    Text("Agent is working in the background…")
                        .font(.caption)
                        .foregroundColor(Color.liquidGlass.textSecondary)
                    Spacer()
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(Color.white.opacity(0.06))
            }

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        if viewModel.sessionMessages.isEmpty {
                            EmptyStateView(
                                icon: "text.bubble",
                                title: "No Messages in Session",
                                message: "This session doesn't have any messages yet. Type a message below to start a conversation with the agent, or wait for the agent to respond if it's currently working."
                            )
                            .padding(.top, 30)
                        } else {
                            ForEach(viewModel.sessionMessages, id: \.stableId) { msg in
                                ChatBubbleRow(message: msg)
                                    .id(msg.stableId)
                            }
                        }

                        Color.clear
                            .frame(height: 1)
                            .id("__bottom")
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 12)
                }
                .onChange(of: viewModel.sessionMessages.count) { _, _ in
                    withAnimation(.easeOut(duration: 0.2)) {
                        proxy.scrollTo("__bottom", anchor: .bottom)
                    }
                }
                .task {
                    // Clear out any previous session's messages before loading.
                    await MainActor.run {
                        viewModel.sessionMessages = []
                    }
                    await viewModel.loadSessionMessages(codebaseId: codebaseId, sessionId: effectiveSessionId)
                    proxy.scrollTo("__bottom", anchor: .bottom)
                }
            }
        }
        .safeAreaInset(edge: .bottom) {
            composer
        }
        .navigationTitle(session.title ?? "Session")
        #if os(iOS)
        .navigationBarTitleDisplayModeInline()
        #endif
        .onDisappear {
            taskPolling?.cancel()
            taskPolling = nil
        }
    }

    private var composer: some View {
        VStack(spacing: 10) {
            if let statusText {
                Text(statusText)
                    .font(.caption2)
                    .foregroundColor(Color.liquidGlass.textMuted)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            HStack(spacing: 10) {
                Text("Model")
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.textMuted)

                TextField(viewModel.defaultModel ?? "Default (server)", text: $modelOverride)
                    .textFieldStyle(.roundedBorder)
                    .autocorrectionDisabled(true)
                    #if os(iOS)
                    .textInputAutocapitalization(.never)
                    #endif

                Menu {
                    Button("Default (server)") {
                        modelOverride = ""
                    }

                    let models = viewModel.availableModels
                        .sorted { $0.displayName.localizedCaseInsensitiveCompare($1.displayName) == .orderedAscending }
                    ForEach(models.prefix(40)) { model in
                        Button(model.displayName) {
                            modelOverride = model.id
                        }
                    }
                } label: {
                    Image(systemName: "list.bullet")
                        .font(.system(size: 14, weight: .semibold))
                        .padding(10)
                }
                .background(Color.white.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }

            HStack(alignment: .bottom, spacing: 10) {
                TextField("Message…", text: $draftMessage, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(1...6)

                Button {
                    Task { await send() }
                } label: {
                    Image(systemName: "paperplane.fill")
                        .font(.system(size: 16, weight: .semibold))
                        .padding(10)
                }
                .background(Color.liquidGlass.primary.opacity(0.2))
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .disabled(isSending || draftMessage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(.ultraThinMaterial)
    }

    private func send() async {
        let message = draftMessage.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty else { return }

        let trimmedModel = modelOverride.trimmingCharacters(in: .whitespacesAndNewlines)
        let model: String? = trimmedModel.isEmpty ? nil : trimmedModel

        isSending = true
        statusText = nil
        let resp = await viewModel.sendSessionPromptDetailed(
            codebaseId: codebaseId,
            sessionId: effectiveSessionId,
            prompt: message,
            agent: session.agent ?? "build",
            model: model
        )
        if let resp, resp.success {
            draftMessage = ""
            statusText = resp.taskId != nil ? "Queued" : "Sent"

            let nextSessionId = resp.activeSessionId ?? resp.newSessionId ?? resp.sessionId
            if let nextSessionId, !nextSessionId.isEmpty, nextSessionId != effectiveSessionId {
                effectiveSessionId = nextSessionId
                statusText = "Session resumed"
            }

            if let taskId = resp.taskId {
                startPolling(taskId: taskId)
            }
            await viewModel.loadSessionMessages(codebaseId: codebaseId, sessionId: effectiveSessionId)
            await viewModel.loadSessions(for: codebaseId)
        } else {
            statusText = "Failed"
        }
        isSending = false
    }

    private func startPolling(taskId: String) {
        activeTaskId = taskId
        activeTaskStatus = .pending

        taskPolling?.cancel()
        taskPolling = Task { @MainActor in
            // Poll task status and refresh messages while the agent runs.
            while !Task.isCancelled {
                if let task = await viewModel.fetchTask(taskId: taskId) {
                    activeTaskStatus = task.status

                    if task.status == .completed || task.status == .failed || task.status == .cancelled {
                        break
                    }
                }

                await viewModel.loadSessionMessages(codebaseId: codebaseId, sessionId: effectiveSessionId)
                try? await Task.sleep(nanoseconds: 1_500_000_000)
            }

            // One last refresh.
            await viewModel.loadSessionMessages(codebaseId: codebaseId, sessionId: effectiveSessionId)
            await viewModel.loadSessions(for: codebaseId)
        }
    }
}

// MARK: - Chat Bubble Row

struct ChatBubbleRow: View {
    let message: SessionMessage

    var body: some View {
        HStack {
            if message.isUserMessage { Spacer(minLength: 40) }

            SessionMessageBubble(message: message)
                .frame(maxWidth: 520, alignment: message.isUserMessage ? .trailing : .leading)

            if !message.isUserMessage { Spacer(minLength: 40) }
        }
    }
}

// MARK: - Session Message Bubble

struct SessionMessageBubble: View {
    let message: SessionMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Text(message.isUserMessage ? "👤 User" : "🤖 Assistant")
                    .font(.caption2)
                    .fontWeight(.semibold)
                    .foregroundColor(message.isUserMessage ? Color.liquidGlass.primary : Color.liquidGlass.textSecondary)

                if let model = message.resolvedModel, !model.isEmpty {
                    Text(model)
                        .font(.caption2)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }

                Spacer()

                if let t = message.time?.created, !t.isEmpty {
                    Text(t)
                        .font(.caption2)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }
            }

            let text = message.resolvedText
            if !text.isEmpty {
                Text(text)
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.textSecondary)
                    .padding(12)
                    .background(Color.white.opacity(message.isUserMessage ? 0.06 : 0.03))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            } else {
                Text("(no text)")
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.textMuted)
            }
        }
        .padding(12)
        .background(Color.white.opacity(0.02))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Message Part View

struct MessagePartView: View {
    let part: MessagePart

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: part.type == "text" ? "text.bubble" : "wrench")
                    .foregroundColor(Color.liquidGlass.info)
                Text(part.type.capitalized)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(Color.liquidGlass.textPrimary)
            }

            if let text = part.text {
                Text(text)
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.textSecondary)
                    .padding(12)
                    .background(Color.white.opacity(0.03))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            }

            if let tool = part.tool {
                Text("Tool: \(tool)")
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.textMuted)
            }

            if let state = part.state {
                Text("State: \(state.status ?? "Unknown")")
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.textMuted)
            }
        }
        .padding(12)
        .background(Color.white.opacity(0.02))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Preview

#Preview {
    SessionsView()
        .environmentObject(MonitorViewModel())
        .background(LiquidGradientBackground())
}
