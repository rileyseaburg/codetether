import SwiftUI

struct AgentWorkspaceView: View {
    @ObservedObject var controller: WorkSessionController
    @EnvironmentObject private var auth: AuthService
    @EnvironmentObject private var monitor: MonitorViewModel
    @State private var showingNewSession = false
    @State private var preferredWorkerId: String?
    @State private var selectedSession: UUID?
    @State private var pendingSession: UUID?

    var body: some View {
        List {
            Section {
                Button {
                    preferredWorkerId = nil
                    showingNewSession = true
                } label: {
                    Label("New Work Session", systemImage: "plus.bubble.fill")
                        .font(.headline).padding(.vertical, 8)
                }
                .disabled(controller.onlineWorkers.isEmpty)
                .accessibilityIdentifier("agents.newSession")
                Text("Choose an online agent and a project, then tell it what to do. Keep chatting in the same work session.")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            if let error = controller.errorMessage {
                Section("Connection problem") {
                    Text(error).foregroundStyle(.red)
                    Button("Retry") { Task { await controller.refresh() } }
                }
            }
            Section("Online Agents · \(controller.onlineWorkers.count)") {
                if controller.isRefreshing && controller.workers.isEmpty { ProgressView("Finding agents…") }
                if !controller.isRefreshing && controller.onlineWorkers.isEmpty && controller.errorMessage == nil {
                    Text("No agents are currently online. Pull to refresh.").foregroundStyle(.secondary)
                }
                ForEach(controller.onlineWorkers) { worker in
                    Button {
                        preferredWorkerId = worker.workerId
                        showingNewSession = true
                    } label: {
                        HStack {
                            Image(systemName: worker.isHarvester ? "server.rack" : "desktopcomputer")
                                .foregroundStyle(.cyan)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(worker.name ?? worker.workerId).font(.headline)
                                Text("\(worker.isHarvester ? "Kubernetes harvester" : "Agent") · \(controller.projects(for: worker).count) projects")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Label("Online", systemImage: "circle.fill").font(.caption).foregroundStyle(.green)
                            Image(systemName: "chevron.right")
                        }.padding(.vertical, 5)
                    }
                    .accessibilityIdentifier("agents.worker.\(worker.workerId)")
                }
            }
            if !controller.taskOnlyWorkers.isEmpty {
                Section("Task-only workers") {
                    ForEach(controller.taskOnlyWorkers) { worker in
                        Text("\(worker.name ?? worker.workerId) — legacy protocol")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Text("These workers cannot safely continue conversations. Use an interactive agent above.").font(.caption)
                }
            }
            Section("Your Work Sessions") {
                if controller.sessions.isEmpty {
                    Text("Your sessions will appear here. Tap New Work Session to begin.").foregroundStyle(.secondary)
                }
                ForEach(controller.sessions) { session in
                    Button { selectedSession = session.id } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(session.title).font(.headline).lineLimit(2)
                            Text("\(session.workerName) · \(session.workspaceName)").font(.caption).foregroundStyle(.secondary)
                            Text(session.isRunning ? "Agent is working…" : "Open conversation")
                                .font(.caption).foregroundStyle(session.isRunning ? .orange : .cyan)
                        }.padding(.vertical, 4)
                    }
                    .accessibilityIdentifier("agents.session.\(session.id)")
                }
            }
        }
        .scrollContentBackground(.hidden)
        .navigationTitle("Agents")
        .refreshable { await controller.refresh() }
        .navigationDestination(item: $selectedSession) { id in WorkChatView(controller: controller, sessionId: id) }
        .sheet(isPresented: $showingNewSession, onDismiss: {
            if let pendingSession { selectedSession = pendingSession; self.pendingSession = nil }
        }) {
            NewWorkSessionView(controller: controller, preferredWorkerId: preferredWorkerId) { id in
                pendingSession = id
                showingNewSession = false
            }
        }
        .task(id: auth.currentUser?.userId) {
            controller.configurePersistence(userId: auth.currentUser?.userId, serverURL: monitor.serverURL)
            while !Task.isCancelled {
                await controller.refresh()
                do { try await Task.sleep(nanoseconds: 15_000_000_000) } catch { break }
            }
        }
    }
}

struct NewWorkSessionView: View {
    @ObservedObject var controller: WorkSessionController
    let preferredWorkerId: String?
    let onStarted: (UUID) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var workerId = ""
    @State private var workspaceId = ""
    @State private var prompt = ""
    @State private var model = ""
    @State private var sending = false
    @State private var error: String?
    private var worker: AgentWorker? {
        if !workerId.isEmpty { return controller.onlineWorkers.first { $0.workerId == workerId } }
        return controller.onlineWorkers.first { $0.workerId == preferredWorkerId }
            ?? controller.onlineWorkers.first
    }
    private var projects: [Codebase] { worker.map(controller.projects(for:)) ?? [] }
    private var project: Codebase? { workspaceId.isEmpty ? projects.first : projects.first { $0.id == workspaceId } }

    var body: some View {
        NavigationStack {
            Form {
                Section("Where should the agent work?") {
                    Picker("Agent", selection: $workerId) {
                        ForEach(controller.onlineWorkers) { item in Text(item.name ?? item.workerId).tag(item.workerId) }
                    }.accessibilityIdentifier("workSession.agent")
                    Picker("Project", selection: Binding(get: { project?.id ?? "" }, set: { workspaceId = $0 })) {
                        ForEach(projects) { project in Text(project.name).tag(project.id) }
                    }.accessibilityIdentifier("workSession.project")
                    if let project {
                        Text(project.path).font(.caption).textSelection(.enabled)
                    } else {
                        Text("This agent has no registered project. Refresh the agent list or register a workspace before starting.")
                            .foregroundStyle(.orange)
                    }
                }
                Section("What do you want to work on?") {
                    TextEditor(text: $prompt).frame(minHeight: 140)
                        .overlay(alignment: .topLeading) {
                            if prompt.isEmpty {
                                Text("Describe what you want the agent to do…").foregroundStyle(.secondary)
                                    .padding(.top, 8).padding(.leading, 5).allowsHitTesting(false)
                            }
                        }
                        .accessibilityIdentifier("workSession.prompt")
                }
                Section("Model") {
                    TextField("Automatic, or provider/model", text: $model)
                        .autocorrectionDisabled().accessibilityIdentifier("workSession.model")
                    Text("Leave blank to use this agent's configured default.").font(.caption)
                }
                if let error { Section { Text(error).foregroundStyle(.red) } }
                Button {
                    guard let worker, let project else { return }
                    sending = true
                    Task {
                        defer { sending = false }
                        do { onStarted(try await controller.start(worker: worker, workspace: project, prompt: prompt, model: model)) }
                        catch { self.error = error.localizedDescription }
                    }
                } label: {
                    if sending { ProgressView("Starting…") }
                    else { Label("Start Session", systemImage: "paperplane.fill") }
                }
                .disabled(sending || prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || project == nil)
                .accessibilityIdentifier("workSession.start")
            }
            .navigationTitle("New Work Session")
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() }.disabled(sending) } }
            .onAppear { workerId = preferredWorkerId ?? controller.onlineWorkers.first?.workerId ?? ""; workspaceId = projects.first?.id ?? "" }
            .onChange(of: workerId) { _, _ in
                workspaceId = projects.first?.id ?? ""
                model = worker?.models.contains("github-copilot/gpt-5-mini") == true ? "github-copilot/gpt-5-mini" : ""
            }
        }
    }
}

struct WorkChatView: View {
    @ObservedObject var controller: WorkSessionController
    let sessionId: UUID
    @State private var draft = ""
    @State private var error: String?
    @State private var sending = false
    private var session: WorkSession? { controller.session(sessionId) }

    var body: some View {
        VStack(spacing: 0) {
            if let session {
                VStack(alignment: .leading, spacing: 3) {
                    Text(session.workerName).font(.headline)
                    Text(session.workspacePath).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                }.frame(maxWidth: .infinity, alignment: .leading).padding().background(.thinMaterial)
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 18) {
                            ForEach(session.turns) { turn in
                                VStack(alignment: .leading, spacing: 10) {
                                    Text("You").font(.caption).foregroundStyle(.secondary)
                                    Text(turn.prompt).textSelection(.enabled)
                                    Divider()
                                    Text(session.workerName).font(.caption).foregroundStyle(.cyan)
                                    if let response = turn.response, !response.isEmpty { Text(response).textSelection(.enabled).accessibilityIdentifier("workChat.response") }
                                    else if [.pending, .working].contains(turn.status) { ProgressView("Agent is working…") }
                                    if let failure = turn.error { Text(failure).foregroundStyle(.red) }
                                    if let id = turn.taskId { Text("Task \(id)").font(.caption2).foregroundStyle(.secondary).textSelection(.enabled) }
                                }.padding().frame(maxWidth: .infinity, alignment: .leading).background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12)).id(turn.id)
                            }
                        }.padding()
                    }
                    .onChange(of: session.turns.count) { _, _ in if let id = session.turns.last?.id { proxy.scrollTo(id, anchor: .bottom) } }
                }
                if let error { Text(error).font(.caption).foregroundStyle(.red).padding(.horizontal) }
                HStack(alignment: .bottom) {
                    TextField("Message this agent…", text: $draft, axis: .vertical).lineLimit(1...6)
                        .textFieldStyle(.roundedBorder).accessibilityIdentifier("workChat.message")
                    Button {
                        sending = true
                        Task { defer { sending = false }; do { try await controller.send(draft, to: sessionId); draft = ""; error = nil } catch { self.error = error.localizedDescription } }
                    } label: { Image(systemName: "arrow.up.circle.fill").font(.title) }
                    .disabled(sending || session.isRunning || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .accessibilityIdentifier("workChat.send")
                }.padding().background(.thinMaterial)
            }
        }
        .navigationTitle("Work Session")
        .task(id: session?.currentTaskId) {
            while !Task.isCancelled && session?.isRunning == true {
                do { try await controller.poll(sessionId); error = nil; try await Task.sleep(nanoseconds: 2_000_000_000) }
                catch is CancellationError { break }
                catch { self.error = error.localizedDescription; do { try await Task.sleep(nanoseconds: 5_000_000_000) } catch { break } }
            }
        }
    }
}