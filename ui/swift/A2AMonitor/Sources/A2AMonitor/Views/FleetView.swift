import SwiftUI

/// FleetView - Unified insight into the codetether-agent control plane.
///
/// Surfaces the `/v1/agent/*` API that the rest of the app previously did not
/// reach: the classified worker fleet (Rust / legacy Python), Harvester
/// (KubeVirt persistent-workspace) workers, and the agent runtime session
/// store. This is the single place an operator can see "what is the agent
/// fleet doing right now".
struct FleetView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @State private var selectedSegment: FleetSegment = .workers
    @State private var isRefreshing = false

    enum FleetSegment: String, CaseIterable {
        case workers = "Workers"
        case harvester = "Harvester"
        case sessions = "Sessions"

        var icon: String {
            switch self {
            case .workers: return "cpu"
            case .harvester: return "server.rack"
            case .sessions: return "clock.arrow.circlepath"
            }
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            segmentedControl
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 8)

            content
        }
        .navigationTitle("Fleet")
        #if os(iOS)
        .navigationBarTitleDisplayModeLarge()
        #endif
        .task { await refresh() }
    }

    // MARK: - Segmented Control

    private var segmentedControl: some View {
        HStack(spacing: 4) {
            ForEach(FleetSegment.allCases, id: \.self) { segment in
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) { selectedSegment = segment }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: segment.icon)
                        Text(segment.rawValue)
                    }
                    .font(.subheadline.weight(.semibold))
                    .foregroundColor(selectedSegment == segment ? .black : .white.opacity(0.7))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(selectedSegment == segment ? Color.cyan : Color.clear)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(4)
        .background(Color.white.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Content

    @ViewBuilder
    private var content: some View {
        switch selectedSegment {
        case .workers: workersList
        case .harvester: harvesterList
        case .sessions: sessionsList
        }
    }

    private var workersList: some View {
        Group {
            if viewModel.agentWorkers.isEmpty {
                EmptyStateView(icon: "cpu", title: "No Workers", message: "No registered codetether-agent workers were found.")
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(viewModel.agentWorkers) { worker in
                            WorkerCard(worker: worker)
                        }
                    }
                    .padding(16)
                }
                .refreshable { await refresh() }
            }
        }
    }

    private var harvesterList: some View {
        Group {
            let harvesters = viewModel.harvesterWorkers
            if harvesters.isEmpty {
                EmptyStateView(icon: "server.rack", title: "No Harvester Workers", message: "No KubeVirt/Harvester persistent-workspace workers are registered.")
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(harvesters) { worker in
                            WorkerCard(worker: worker)
                        }
                    }
                    .padding(16)
                }
                .refreshable { await refresh() }
            }
        }
    }

    private var sessionsList: some View {
        Group {
            if viewModel.runtimeSessions.isEmpty {
                EmptyStateView(icon: "clock.arrow.circlepath", title: "No Runtime Sessions", message: "The agent runtime session store is empty or unavailable.")
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(viewModel.runtimeSessions) { session in
                            RuntimeSessionCard(session: session)
                        }
                    }
                    .padding(16)
                }
                .refreshable { await refresh() }
            }
        }
    }

    // MARK: - Data

    private func refresh() async {
        await viewModel.loadAgentWorkers()
        await viewModel.loadRuntimeSessions()
    }
}

// MARK: - Worker Card

struct WorkerCard: View {
    let worker: AgentWorker

    var body: some View {
        GlassCard(padding: 16) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: worker.workerRuntime.iconName)
                        .foregroundColor(.cyan)
                    Text(worker.name ?? worker.workerId)
                        .font(.headline)
                        .foregroundColor(.white)
                        .lineLimit(1)
                    Spacer()
                    GlassBadge(text: statusText, color: statusColor)
                }

                HStack(spacing: 8) {
                    GlassBadge(text: worker.displayLabel, color: worker.workerRuntime == .rust ? .orange : .gray)
                    if worker.isHarvester {
                        GlassBadge(text: "Harvester", color: .purple)
                    }
                }

                if let hostname = worker.hostname {
                    label("server.rack", hostname)
                }
                if !worker.models.isEmpty {
                    label("cube.box", worker.models.prefix(3).joined(separator: ", "))
                }
                if !worker.capabilities.isEmpty {
                    label("checkmark.seal", worker.capabilities.prefix(4).joined(separator: ", "))
                }
                if let lastSeen = worker.lastSeen {
                    label("clock", lastSeen)
                }
            }
        }
    }

    private func label(_ icon: String, _ text: String) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.caption2)
                .foregroundColor(.white.opacity(0.5))
            Text(text)
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
                .lineLimit(1)
        }
    }

    private var statusText: String {
        (worker.status ?? "unknown").capitalized
    }

    private var statusColor: Color {
        switch (worker.status ?? "").lowercased() {
        case "online", "active", "idle", "ready": return .green
        case "busy", "running": return .yellow
        case "offline", "disconnected", "error": return .red
        default: return .gray
        }
    }
}

// MARK: - Runtime Session Card

struct RuntimeSessionCard: View {
    let session: RuntimeSession

    var body: some View {
        GlassCard(padding: 16) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "bubble.left.and.text.bubble.right")
                        .foregroundColor(.cyan)
                    Text(session.title ?? "Untitled Session")
                        .font(.headline)
                        .foregroundColor(.white)
                        .lineLimit(1)
                }

                if let projectId = session.projectId {
                    label("folder", projectId)
                }
                if let directory = session.directory {
                    label("externaldrive", directory)
                }
                if let summary = session.summary?.text, !summary.isEmpty {
                    Text(summary)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                        .lineLimit(3)
                }
                if let updated = session.updatedDate {
                    label("clock", Self.formatter.localizedString(for: updated, relativeTo: Date()))
                }
            }
        }
    }

    private func label(_ icon: String, _ text: String) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.caption2)
                .foregroundColor(.white.opacity(0.5))
            Text(text)
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
                .lineLimit(1)
        }
    }

    private static let formatter = RelativeDateTimeFormatter()
}
