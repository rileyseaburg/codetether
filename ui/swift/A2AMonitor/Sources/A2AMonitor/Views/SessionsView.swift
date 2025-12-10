import SwiftUI

/// Sessions View - Shows active sessions for a codebase
struct SessionsView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @State private var selectedSession: SessionMessage?
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
        .sheet(isPresented: $showingSessionDetail) {
            if let session = selectedSession {
                SessionDetailView(session: session)
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
                        value: "\(viewModel.sessions.filter { $0.parts != nil && !($0.parts?.isEmpty ?? true) }.count)",
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
                        message: "Start a new session to see activity here"
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
    let session: SessionMessage
    
    var body: some View {
        HStack(spacing: 12) {
            // Status indicator
            Circle()
                .fill(statusColor)
                .frame(width: 10, height: 10)
            
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(session.agent ?? "Unknown Agent")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(Color.liquidGlass.textPrimary)
                    
                    Spacer()
                    
                    Text(session.model ?? "Unknown Model")
                        .font(.caption2)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }
                
                Text(session.time?.created ?? "Unknown Time")
                    .font(.caption2)
                    .foregroundColor(Color.liquidGlass.textMuted)
                
                if let parts = session.parts, !parts.isEmpty {
                    Text("\(parts.count) messages")
                        .font(.caption2)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }
            }
            
            Spacer()
            
            // Session cost
            if let cost = session.cost {
                Text("$\(cost, specifier: "%.4f")")
                    .font(.caption2)
                    .foregroundColor(Color.liquidGlass.textMuted)
            }
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
    let session: SessionMessage
    
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
                            Text("Agent: \(session.agent ?? "Unknown")")
                                .font(.subheadline)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                            
                            Text("Model: \(session.model ?? "Unknown")")
                                .font(.subheadline)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                            
                            if let time = session.time {
                                Text("Started: \(time.created ?? "Unknown")")
                                    .font(.subheadline)
                                    .foregroundColor(Color.liquidGlass.textMuted)
                                
                                if let completed = time.completed {
                                    Text("Completed: \(completed)")
                                        .font(.subheadline)
                                        .foregroundColor(Color.liquidGlass.textMuted)
                                }
                            }
                            
                            if let cost = session.cost {
                                Text("Cost: $\(cost, specifier: "%.4f")")
                                    .font(.subheadline)
                                    .foregroundColor(Color.liquidGlass.textPrimary)
                            }
                        }
                    }
                }
                
                // Session Messages
                if let parts = session.parts, !parts.isEmpty {
                    GlassCard(cornerRadius: 20, padding: 20) {
                        VStack(alignment: .leading, spacing: 16) {
                            Text("Session Messages")
                                .font(.headline)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                            
                            ForEach(parts) { part in
                                MessagePartView(part: part)
                            }
                        }
                    }
                }
            }
            .padding(20)
        }
        .navigationTitle("Session Details")
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