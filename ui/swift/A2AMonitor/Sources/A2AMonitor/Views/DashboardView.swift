import SwiftUI

/// Main Dashboard View - Overview of all A2A Monitor activity
struct DashboardView: View {
    @EnvironmentObject var viewModel: MonitorViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                headerSection

                // Stats Grid
                statsGrid

                // Main Content Grid
                #if os(iOS)
                VStack(spacing: 20) {
                    activeAgentsSection
                    recentMessagesSection
                    taskQueueSection
                }
                #else
                HStack(alignment: .top, spacing: 20) {
                    VStack(spacing: 20) {
                        activeAgentsSection
                        taskQueueSection
                    }
                    .frame(maxWidth: .infinity)

                    recentMessagesSection
                        .frame(maxWidth: .infinity)
                }
                #endif
            }
            .padding(20)
        }
        .refreshable {
            await viewModel.refreshData()
        }
        .background(Color.clear)
        .navigationTitle("Dashboard")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                ConnectionStatusBadge()
            }

            ToolbarItem(placement: .automatic) {
                Link(destination: URL(string: "https://docs.codetether.run")!) {
                    Image(systemName: "book")
                }
                .accessibilityLabel("Documentation")
            }

            ToolbarItem(placement: .automatic) {
                Button {
                    Task {
                        await viewModel.refreshData()
                    }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .accessibilityLabel("Refresh")
            }
        }
    }

    // MARK: - Header Section

    var headerSection: some View {
        GlassCard(cornerRadius: 24, padding: 24) {
            HStack(spacing: 20) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("A2A Agent Monitor")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(Color.liquidGlass.textPrimary)

                    Text("Real-time Agent Conversation Auditing & Control")
                        .font(.subheadline)
                        .foregroundColor(Color.liquidGlass.textSecondary)
                }

                Spacer()

                // OpenCode Status
                if let status = viewModel.openCodeStatus {
                    HStack(spacing: 8) {
                        Circle()
                            .fill(status.available ? Color.liquidGlass.success : Color.liquidGlass.warning)
                            .frame(width: 10, height: 10)

                        VStack(alignment: .leading, spacing: 2) {
                            Text("OpenCode")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(Color.liquidGlass.textPrimary)

                            Text(status.available ? "Ready" : "Unavailable")
                                .font(.caption2)
                                .foregroundColor(Color.liquidGlass.textMuted)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color.white.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
        }
    }

    // MARK: - Stats Grid

    var statsGrid: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 140))], spacing: 16) {
            StatCard(
                title: "Active Agents",
                value: "\(viewModel.codebases.filter { $0.status == .running || $0.status == .busy }.count)",
                icon: "cpu",
                color: Color.liquidGlass.primary
            )

            StatCard(
                title: "Messages",
                value: formatNumber(viewModel.stats.totalMessages),
                icon: "bubble.left.and.bubble.right",
                color: Color.liquidGlass.info
            )

            StatCard(
                title: "Total Stored",
                value: formatNumber(viewModel.totalStoredMessages),
                icon: "cylinder",
                color: Color.liquidGlass.accent
            )

            StatCard(
                title: "Tool Calls",
                value: "\(viewModel.stats.toolCalls)",
                icon: "wrench.and.screwdriver",
                color: Color.liquidGlass.success
            )

            StatCard(
                title: "Interventions",
                value: "\(viewModel.stats.interventions)",
                icon: "hand.raised",
                color: Color.liquidGlass.warning
            )
        }
    }

    // MARK: - Active Agents Section

    var activeAgentsSection: some View {
        GlassCard(cornerRadius: 20, padding: 20) {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Image(systemName: "cpu")
                        .foregroundColor(Color.liquidGlass.primary)
                    Text("OpenCode Agents")
                        .font(.headline)
                        .foregroundColor(Color.liquidGlass.textPrimary)

                    Spacer()

                    GlassButton("Register", icon: "plus", style: .secondary) {
                        viewModel.showingRegisterSheet = true
                    }
                }

                if viewModel.codebases.isEmpty {
                    EmptyStateView(
                        icon: "folder",
                        title: "No Codebases",
                        message: "Register a codebase to start monitoring",
                        action: { viewModel.showingRegisterSheet = true },
                        actionTitle: "Register Codebase"
                    )
                } else {
                    ForEach(viewModel.codebases) { codebase in
                        CodebaseRow(codebase: codebase)
                    }
                }
            }
        }
        .sheet(isPresented: $viewModel.showingRegisterSheet) {
            RegisterCodebaseSheet()
        }
    }

    // MARK: - Recent Messages Section

    var recentMessagesSection: some View {
        GlassCard(cornerRadius: 20, padding: 20) {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Image(systemName: "bubble.left.and.bubble.right")
                        .foregroundColor(Color.liquidGlass.info)
                    Text("Recent Activity")
                        .font(.headline)
                        .foregroundColor(Color.liquidGlass.textPrimary)

                    Spacer()

                    NavigationLink(destination: MessagesView()) {
                        Text("View All")
                            .font(.caption)
                            .foregroundColor(Color.liquidGlass.primary)
                    }
                }

                if viewModel.messages.isEmpty {
                    EmptyStateView(
                        icon: "bubble.left.and.bubble.right",
                        title: "No Messages",
                        message: "Agent conversations will appear here"
                    )
                } else {
                    ForEach(viewModel.messages.prefix(5)) { message in
                        MessageRow(message: message)
                    }
                }
            }
        }
    }

    // MARK: - Task Queue Section

    var taskQueueSection: some View {
        GlassCard(cornerRadius: 20, padding: 20) {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Image(systemName: "checklist")
                        .foregroundColor(Color.liquidGlass.warning)
                    Text("Task Queue")
                        .font(.headline)
                        .foregroundColor(Color.liquidGlass.textPrimary)

                    Spacer()

                    HStack(spacing: 8) {
                        GlassBadge(
                            text: "\(viewModel.tasks.filter { $0.status == .pending }.count) pending",
                            color: Color.liquidGlass.warning
                        )
                        GlassBadge(
                            text: "\(viewModel.tasks.filter { $0.status == .working }.count) working",
                            color: Color.liquidGlass.info
                        )
                    }
                }

                if viewModel.tasks.isEmpty {
                    EmptyStateView(
                        icon: "checklist",
                        title: "No Tasks",
                        message: "Create a task to assign work to an agent"
                    )
                } else {
                    ForEach(viewModel.tasks.filter { $0.status == .pending || $0.status == .working }.prefix(5)) { task in
                        TaskRow(task: task)
                    }
                }
            }
        }
    }

    // MARK: - Helpers

    func formatNumber(_ num: Int) -> String {
        if num >= 1_000_000 {
            return String(format: "%.1fM", Double(num) / 1_000_000)
        } else if num >= 1_000 {
            return String(format: "%.1fK", Double(num) / 1_000)
        }
        return "\(num)"
    }
}

// MARK: - Codebase Row

struct CodebaseRow: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    let codebase: Codebase

    var body: some View {
        HStack(spacing: 12) {
            StatusIndicator(status: codebase.status, showLabel: false, size: 10)

            VStack(alignment: .leading, spacing: 2) {
                Text(codebase.name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(Color.liquidGlass.textPrimary)

                Text(codebase.path)
                    .font(.caption2)
                    .foregroundColor(Color.liquidGlass.textMuted)
                    .lineLimit(1)
            }

            Spacer()

            // Task badges
            if codebase.pendingTasks > 0 {
                GlassBadge(text: "\(codebase.pendingTasks)", color: Color.liquidGlass.warning)
            }

            // Quick actions
            Button {
                viewModel.selectedCodebase = codebase
                viewModel.showingTriggerSheet = true
            } label: {
                Image(systemName: "bolt.fill")
                    .foregroundColor(Color.liquidGlass.primary)
            }
            .buttonStyle(.plain)
        }
        .padding(12)
        .background(Color.white.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .sheet(isPresented: $viewModel.showingTriggerSheet) {
            if let codebase = viewModel.selectedCodebase {
                TriggerAgentSheet(codebase: codebase)
            }
        }
    }
}

// MARK: - Message Row

struct MessageRow: View {
    let message: Message

    var typeColor: Color {
        switch message.type {
        case .agent: return Color.liquidGlass.info
        case .human: return .orange
        case .system: return .purple
        case .tool: return Color.liquidGlass.success
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: message.type.icon)
                .foregroundColor(typeColor)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(message.agentName)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(Color.liquidGlass.textPrimary)

                    Spacer()

                    Text(message.timestamp, style: .time)
                        .font(.caption2)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }

                Text(message.content)
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.textSecondary)
                    .lineLimit(2)
            }
        }
        .padding(10)
        .background(Color.white.opacity(0.03))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

// MARK: - Task Row

struct TaskRow: View {
    let task: AgentTask

    var statusColor: Color {
        switch task.status {
        case .pending: return Color.liquidGlass.warning
        case .working: return Color.liquidGlass.info
        case .completed: return Color.liquidGlass.success
        case .failed: return Color.liquidGlass.error
        case .cancelled: return .gray
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: task.status.icon)
                .foregroundColor(statusColor)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                Text(task.title)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(Color.liquidGlass.textPrimary)
                    .lineLimit(1)

                Text(task.description)
                    .font(.caption2)
                    .foregroundColor(Color.liquidGlass.textMuted)
                    .lineLimit(1)
            }

            Spacer()

            GlassBadge(text: task.status.rawValue, color: statusColor)
        }
        .padding(10)
        .background(Color.white.opacity(0.03))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

// MARK: - Preview

#Preview {
    DashboardView()
        .environmentObject(MonitorViewModel())
        .background(LiquidGradientBackground())
}
