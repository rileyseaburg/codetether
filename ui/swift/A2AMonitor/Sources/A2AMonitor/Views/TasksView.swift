import SwiftUI

/// Tasks View - Manage task queue for agents
struct TasksView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @State private var showingCreateSheet = false
    @State private var errorMessage: String?
    @State private var showingError = false
    @State private var showingCopyConfirmation = false
    @State private var isPerformingAction = false
    @State private var showingCancelConfirmation = false
    @State private var taskToCancel: AgentTask?
    
    // Computed properties to help the type checker
    private var pendingCount: Int { viewModel.tasks.filter { $0.status == .pending }.count }
    private var workingCount: Int { viewModel.tasks.filter { $0.status == .working }.count }
    private var completedCount: Int { viewModel.tasks.filter { $0.status == .completed }.count }
    
    var body: some View {
        VStack(spacing: 0) {
            // Top bar with filters
            VStack(spacing: 12) {
                HStack {
                    Text("Task Queue")
                        .font(.headline)
                        .foregroundColor(Color.liquidGlass.textPrimary)
                    
                    Spacer()
                    
                    // Stats badges
                    statsBadges
                }
                
                HStack(spacing: 12) {
                    // Filters
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            FilterChip(title: "All", isSelected: viewModel.taskFilter == nil) {
                                viewModel.taskFilter = nil
                            }
                            
                            ForEach(TaskStatus.allCases, id: \.self) { status in
                                FilterChip(title: status.rawValue.capitalized, isSelected: viewModel.taskFilter == status) {
                                    viewModel.taskFilter = status
                                }
                            }
                        }
                    }
                    
                    Spacer()
                    
                    GlassButton("Create Task", icon: "plus", style: .primary) {
                        showingCreateSheet = true
                    }
                }
            }
            .padding()
            .background(.ultraThinMaterial)
            
            // Tasks list
            ScrollView {
                LazyVStack(spacing: 16) {
                    if viewModel.filteredTasks.isEmpty {
                        EmptyStateView(
                            icon: "checklist",
                            title: viewModel.taskFilter == nil ? "No Tasks in Queue" : "No \(viewModel.taskFilter?.rawValue.capitalized ?? "") Tasks",
                            message: viewModel.taskFilter == nil
                                ? "Tasks let you describe work for AI agents to complete. Create a task with a title and description, then an agent will pick it up and start working."
                                : "There are no tasks with this status. Try selecting a different filter or create a new task.",
                            action: { showingCreateSheet = true },
                            actionTitle: "Create New Task"
                        )
                        .padding(.top, 60)
                    } else {
                        ForEach(viewModel.filteredTasks) { task in
                            taskCard(for: task)
                        }
                    }
                }
                .padding()
            }
            .refreshable {
                await viewModel.refreshData()
            }
        }
        .background(Color.clear)
        .navigationTitle("Tasks")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button {
                    Task {
                        await viewModel.loadTasks()
                    }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
            }
        }
        .sheet(isPresented: $showingCreateSheet) {
            CreateTaskSheet()
        }
        .alert("Error", isPresented: $showingError) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(errorMessage ?? "An unknown error occurred")
        }
        .alert("Copied", isPresented: $showingCopyConfirmation) {
            Button("OK", role: .cancel) { }
        } message: {
            Text("Task ID copied to clipboard")
        }
        .confirmationDialog("Cancel Task", isPresented: $showingCancelConfirmation, presenting: taskToCancel) { task in
            Button("Cancel Task", role: .destructive) {
                Task {
                    isPerformingAction = true
                    do {
                        try await viewModel.cancelTask(task)
                    } catch {
                        errorMessage = error.localizedDescription
                        showingError = true
                    }
                    isPerformingAction = false
                }
            }
        } message: { task in
            Text("Are you sure you want to cancel \"\(task.title)\"? This cannot be undone.")
        }
        .overlay {
            if isPerformingAction {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
                    .overlay {
                        ProgressView()
                            .scaleEffect(1.5)
                            .tint(.white)
                    }
            }
        }
    }
    
    func copyTaskId(_ id: String) {
        #if os(macOS)
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(id, forType: .string)
        #else
        UIPasteboard.general.string = id
        #endif
        showingCopyConfirmation = true
    }
    
    // MARK: - Subviews
    
    private var statsBadges: some View {
        HStack(spacing: 8) {
            GlassBadge(
                text: "\(pendingCount) pending",
                color: Color.liquidGlass.warning
            )
            GlassBadge(
                text: "\(workingCount) working",
                color: Color.liquidGlass.info
            )
            GlassBadge(
                text: "\(completedCount) completed",
                color: Color.liquidGlass.success
            )
        }
    }
    
    @ViewBuilder
    private func taskCard(for task: AgentTask) -> some View {
        let canStart = task.status == .pending
        let canCancel = task.status == .pending || task.status == .working
        
        TaskCard(
            task: task,
            onStart: canStart ? { startTask(task) } : nil,
            onCancel: canCancel ? { confirmCancelTask(task) } : nil
        )
        .contextMenu {
            if canStart {
                Button {
                    startTask(task)
                } label: {
                    Label("Start Task", systemImage: "play.fill")
                }
            }
            
            if task.status != .completed && task.status != .cancelled {
                Button(role: .destructive) {
                    confirmCancelTask(task)
                } label: {
                    Label("Cancel Task", systemImage: "xmark.circle")
                }
            }
            
            Button {
                copyTaskId(task.id)
            } label: {
                Label("Copy ID", systemImage: "doc.on.doc")
            }
        }
    }
    
    private func startTask(_ task: AgentTask) {
        Task {
            isPerformingAction = true
            do {
                try await viewModel.startTask(task)
            } catch {
                errorMessage = error.localizedDescription
                showingError = true
            }
            isPerformingAction = false
        }
    }
    
    private func confirmCancelTask(_ task: AgentTask) {
        taskToCancel = task
        showingCancelConfirmation = true
    }
}

// MARK: - Create Task Sheet

struct CreateTaskSheet: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @Environment(\.dismiss) var dismiss
    
    @State private var selectedCodebaseId: String = ""
    @State private var title = ""
    @State private var description = ""
    @State private var priority: TaskPriority = .normal
    @State private var context = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var selectedAgentType: String = "build"
    
    var body: some View {
        NavigationStack {
            ZStack {
                LiquidGradientBackground()
                
                ScrollView {
                    VStack(spacing: 24) {
                        // Header
                        VStack(spacing: 8) {
                            Image(systemName: "checklist")
                                .font(.system(size: 50))
                                .foregroundColor(Color.liquidGlass.primary)
                            
                            Text("Create Task")
                                .font(.title)
                                .fontWeight(.bold)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                        }
                        .padding(.top, 20)
                        
                        // Agent selection
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Assign to Agent")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                            
                            Picker("Agent", selection: $selectedCodebaseId) {
                                Text("Select Agent...").tag("")
                                ForEach(viewModel.codebases) { codebase in
                                    HStack {
                                        StatusIndicator(status: codebase.status, showLabel: false, size: 8)
                                        Text(codebase.name)
                                        if codebase.status == .watching {
                                            Image(systemName: "eye.fill")
                                                .font(.caption2)
                                        }
                                    }
                                    .tag(codebase.id)
                                }
                            }
                            .pickerStyle(.menu)
                            .padding(12)
                            .background(Color.white.opacity(0.1))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                        .padding(.horizontal)
                        
                        // Title
                        GlassTextField(
                            title: "Task Title",
                            placeholder: "e.g., Add user authentication",
                            text: $title
                        )
                        .padding(.horizontal)
                        
                        // Description
                        GlassTextField(
                            title: "Description",
                            placeholder: "Describe what you want the agent to do...",
                            text: $description,
                            isMultiline: true
                        )
                        .padding(.horizontal)
                        
                        // Priority
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Priority")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                            
                            HStack(spacing: 12) {
                                ForEach(TaskPriority.allCases, id: \.self) { p in
                                    PriorityButton(
                                        priority: p,
                                        isSelected: priority == p
                                    ) {
                                        priority = p
                                    }
                                }
                            }
                        }
                        .padding(.horizontal)
                        
                        // Agent Type
                        Section("Agent Type") {
                            Picker("Select Agent Type", selection: $selectedAgentType) {
                                Text("Build").tag("build")
                                Text("Plan").tag("plan")
                                Text("General").tag("general")
                                Text("Explore").tag("explore")
                            }
                        }
                        
                        // Context
                        GlassTextField(
                            title: "Additional Context (Optional)",
                            placeholder: "Any additional files, requirements, or context...",
                            text: $context,
                            isMultiline: true
                        )
                        .padding(.horizontal)
                        
                        if let error = errorMessage {
                            Text(error)
                                .font(.caption)
                                .foregroundColor(Color.liquidGlass.error)
                        }
                        
                        // Actions
                        HStack(spacing: 16) {
                            GlassButton("Cancel", style: .secondary) {
                                dismiss()
                            }
                            
                            GlassButton("Create Task", icon: "plus", style: .primary) {
                                createTask()
                            }
                            .disabled(selectedCodebaseId.isEmpty || title.isEmpty || description.isEmpty || isLoading)
                        }
                        .padding()
                    }
                }
            }
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
        }
    }
    
    func createTask() {
        guard let codebase = viewModel.codebases.first(where: { $0.id == selectedCodebaseId }) else {
            errorMessage = "Please select a valid agent"
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                try await viewModel.createTask(
                    codebase: codebase,
                    title: title,
                    description: description,
                    priority: priority,
                    context: context.isEmpty ? nil : context,
                    agentType: selectedAgentType
                )
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
}

// MARK: - Priority Button

struct PriorityButton: View {
    let priority: TaskPriority
    let isSelected: Bool
    let action: () -> Void
    
    var color: Color {
        switch priority {
        case .low: return Color.liquidGlass.success
        case .normal: return Color.liquidGlass.warning
        case .high: return .orange
        case .urgent: return Color.liquidGlass.error
        }
    }
    
    var icon: String {
        switch priority {
        case .low: return "arrow.down"
        case .normal: return "minus"
        case .high: return "arrow.up"
        case .urgent: return "exclamationmark"
        }
    }
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.caption)
                Text(priority.label)
                    .font(.caption2)
            }
            .foregroundColor(isSelected ? .white : color)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(isSelected ? color : Color.white.opacity(0.1))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(color.opacity(isSelected ? 0 : 0.5), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        TasksView()
            .environmentObject(MonitorViewModel())
            .background(LiquidGradientBackground())
    }
}
