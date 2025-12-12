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
                        title: "No Active Sessions",
                        message: selectedCodebaseId.isEmpty ? "Select a codebase to view sessions" : "No sessions found for this codebase"
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

    @State private var draftMessage: String = ""
    @State private var isSending = false
    @State private var statusText: String?
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Session Header
                GlassCard(cornerRadius: 24, padding: 24) {
                    VStack(spacing: 16) {
                        HStack {
                            Image(systemName: "person.2")
                                .foregroundColor(Color.liquidGlass.primary)
                            Text("Session Details")
                                .font(.headline)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                        }
                        
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Title: \(session.title ?? "Untitled")")
                                .font(.subheadline)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                            
                            Text("Agent: \(session.agent ?? "build")")
                                .font(.subheadline)
                                .foregroundColor(Color.liquidGlass.textPrimary)

                            Text("Updated: \(session.updated ?? session.created ?? "")")
                                .font(.subheadline)
                                .foregroundColor(Color.liquidGlass.textMuted)
                        }
                    }
                }
                
                // Session Messages
                GlassCard(cornerRadius: 20, padding: 20) {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Session Messages")
                            .font(.headline)
                            .foregroundColor(Color.liquidGlass.textPrimary)

                        if viewModel.sessionMessages.isEmpty {
                            Text("No messages in this session")
                                .font(.caption)
                                .foregroundColor(Color.liquidGlass.textMuted)
                        } else {
                            ForEach(viewModel.sessionMessages, id: \.stableId) { msg in
                                SessionMessageBubble(message: msg)
                            }
                        }

                        Divider().background(Color.white.opacity(0.15))

                        VStack(spacing: 10) {
                            TextField("Reply to this session…", text: $draftMessage, axis: .vertical)
                                .textFieldStyle(.roundedBorder)

                            HStack {
                                Button {
                                    Task {
                                        await send()
                                    }
                                } label: {
                                    HStack {
                                        Image(systemName: "paperplane.fill")
                                        Text(isSending ? "Sending…" : "Send")
                                    }
                                }
                                .disabled(isSending || draftMessage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                                Spacer()

                                if let statusText {
                                    Text(statusText)
                                        .font(.caption2)
                                        .foregroundColor(Color.liquidGlass.textMuted)
                                }
                            }
                        }
                    }
                }
            }
            .padding(20)
        }
        .navigationTitle("Session Details")
        .task {
            await viewModel.loadSessionMessages(codebaseId: codebaseId, sessionId: session.id)
        }
    }

    private func send() async {
        let message = draftMessage.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty else { return }

        isSending = true
        statusText = nil
        let ok = await viewModel.sendSessionPrompt(codebaseId: codebaseId, sessionId: session.id, prompt: message, agent: session.agent ?? "build")
        if ok {
            draftMessage = ""
            statusText = "Sent"
            await viewModel.loadSessionMessages(codebaseId: codebaseId, sessionId: session.id)
            await viewModel.loadSessions(for: codebaseId)
        } else {
            statusText = "Failed"
        }
        isSending = false
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