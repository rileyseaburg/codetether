import SwiftUI

/// Agent Output View - Real-time streaming output from agents
struct AgentOutputView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @State private var isScrolledToBottom = true
    @State private var errorMessage: String?
    @State private var showingError = false
    @State private var showingExportConfirmation = false
    @State private var isInterrupting = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Top bar
            VStack(spacing: 12) {
                HStack {
                    // Agent selector
                    HStack(spacing: 8) {
                        Image(systemName: "terminal")
                            .foregroundColor(Color.liquidGlass.accent)
                        
                        Picker("Agent", selection: $viewModel.selectedCodebaseForOutput) {
                            Text("Select agent to view output...").tag(nil as String?)
                            ForEach(viewModel.codebases) { codebase in
                                HStack {
                                    StatusIndicator(status: codebase.status, showLabel: false, size: 8)
                                    Text(codebase.name)
                                    if codebase.status == .busy || codebase.status == .running {
                                        Text("Active")
                                            .font(.caption2)
                                            .foregroundColor(Color.liquidGlass.success)
                                    }
                                }
                                .tag(codebase.id as String?)
                            }
                        }
                        .pickerStyle(.menu)
                        .frame(maxWidth: 300)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color.white.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    
                    Spacer()
                    
                    // Controls
                    HStack(spacing: 12) {
                        // Auto-scroll toggle
                        Button {
                            viewModel.autoScrollOutput.toggle()
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: "scroll")
                                Text("Auto-scroll")
                                    .font(.caption)
                            }
                            .foregroundColor(viewModel.autoScrollOutput ? Color.liquidGlass.primary : Color.liquidGlass.textMuted)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(viewModel.autoScrollOutput ? Color.liquidGlass.primary.opacity(0.2) : Color.white.opacity(0.1))
                            .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                        
                        // Clear
                        Button {
                            if let codebaseId = viewModel.selectedCodebaseForOutput {
                                viewModel.clearOutput(for: codebaseId)
                            }
                        } label: {
                            Image(systemName: "trash")
                                .foregroundColor(Color.liquidGlass.textMuted)
                        }
                        .buttonStyle(.plain)
                        .disabled(viewModel.selectedCodebaseForOutput == nil)
                        .accessibilityLabel("Clear output")
                        
                        // Export
                        Button {
                            exportOutput()
                        } label: {
                            Image(systemName: "square.and.arrow.up")
                                .foregroundColor(Color.liquidGlass.textMuted)
                        }
                        .buttonStyle(.plain)
                        .disabled(viewModel.currentOutput.isEmpty)
                        .accessibilityLabel("Export output")
                    }
                }
            }
            .padding()
            .background(.ultraThinMaterial)
            
            // Output content
            if viewModel.selectedCodebaseForOutput == nil {
                // No agent selected
                VStack {
                    Spacer()
                    EmptyStateView(
                        icon: "terminal",
                        title: "Select a Project",
                        message: "Choose a project from the dropdown above to monitor its AI agent output. You'll see real-time logs, tool calls, and reasoning as the agent works."
                    )
                    Spacer()
                }
            } else if viewModel.currentOutput.isEmpty {
                // Agent selected but no output
                VStack {
                    Spacer()
                    EmptyStateView(
                        icon: "text.cursor",
                        title: "Waiting for Agent Activity",
                        message: "This project's agent isn't running right now. Go to the Agents tab and tap the bolt icon to trigger an agent with a prompt. Output will stream here in real-time."
                    )
                    Spacer()
                }
            } else {
                // Output stream
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 8) {
                            ForEach(viewModel.currentOutput) { entry in
                                OutputEntryView(entry: entry)
                                    .id(entry.id)
                            }
                        }
                        .padding()
                    }
                    .onChange(of: viewModel.currentOutput.count) { _, _ in
                        if viewModel.autoScrollOutput, let lastId = viewModel.currentOutput.last?.id {
                            withAnimation(.easeOut(duration: 0.2)) {
                                proxy.scrollTo(lastId, anchor: .bottom)
                            }
                        }
                    }
                }
                .background(Color.black.opacity(0.3))
            }
            
            // Bottom stats bar
            if let codebaseId = viewModel.selectedCodebaseForOutput,
               let codebase = viewModel.codebases.first(where: { $0.id == codebaseId }) {
                bottomStatsBar(codebase: codebase)
            }
        }
        .background(Color.clear)
        .navigationTitle("Agent Output")
        .alert("Error", isPresented: $showingError) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(errorMessage ?? "An unknown error occurred")
        }
        .alert("Exported", isPresented: $showingExportConfirmation) {
            Button("OK", role: .cancel) { }
        } message: {
            Text("Output copied to clipboard as JSON")
        }
    }
    
    // MARK: - Bottom Stats Bar
    
    func bottomStatsBar(codebase: Codebase) -> some View {
        HStack(spacing: 20) {
            // Status
            HStack(spacing: 8) {
                StatusIndicator(status: codebase.status, size: 10)
                Text(codebase.name)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(Color.liquidGlass.textPrimary)
            }
            
            Divider()
                .frame(height: 16)
            
            // Output count
            HStack(spacing: 4) {
                Image(systemName: "text.alignleft")
                    .font(.caption2)
                Text("\(viewModel.currentOutput.count) entries")
                    .font(.caption)
            }
            .foregroundColor(Color.liquidGlass.textMuted)
            
            // Tool calls
            let toolCalls = viewModel.currentOutput.filter { $0.type == .toolCompleted || $0.type == .toolRunning }.count
            if toolCalls > 0 {
                HStack(spacing: 4) {
                    Image(systemName: "wrench")
                        .font(.caption2)
                    Text("\(toolCalls) tools")
                        .font(.caption)
                }
                .foregroundColor(Color.liquidGlass.textMuted)
            }
            
            // Errors
            let errors = viewModel.currentOutput.filter { $0.type == .error || $0.type == .toolError }.count
            if errors > 0 {
                HStack(spacing: 4) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.caption2)
                    Text("\(errors) errors")
                        .font(.caption)
                }
                .foregroundColor(Color.liquidGlass.error)
            }
            
            Spacer()
            
            // Quick actions
            if codebase.status == .busy || codebase.status == .running {
                Button {
                    Task {
                        isInterrupting = true
                        do {
                            try await viewModel.interruptAgent(codebase)
                        } catch {
                            errorMessage = error.localizedDescription
                            showingError = true
                        }
                        isInterrupting = false
                    }
                } label: {
                    HStack(spacing: 4) {
                        if isInterrupting {
                            ProgressView()
                                .scaleEffect(0.7)
                        } else {
                            Image(systemName: "stop.fill")
                        }
                        Text(isInterrupting ? "Interrupting..." : "Interrupt")
                    }
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.error)
                }
                .buttonStyle(.plain)
                .disabled(isInterrupting)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }
    
    // MARK: - Export
    
    func exportOutput() {
        guard !viewModel.currentOutput.isEmpty,
              let codebaseId = viewModel.selectedCodebaseForOutput,
              let _ = viewModel.codebases.first(where: { $0.id == codebaseId }) else {
            return
        }
        
        let exportData = viewModel.currentOutput.map { entry in
            [
                "id": entry.id,
                "timestamp": ISO8601DateFormatter().string(from: entry.timestamp),
                "type": entry.type.rawValue,
                "content": entry.content,
                "toolName": entry.toolName ?? "",
                "toolOutput": entry.toolOutput ?? "",
                "error": entry.error ?? ""
            ]
        }
        
        do {
            let jsonData = try JSONSerialization.data(withJSONObject: exportData, options: .prettyPrinted)
            guard let jsonString = String(data: jsonData, encoding: .utf8) else {
                errorMessage = "Failed to convert export data to string"
                showingError = true
                return
            }
            #if os(macOS)
            let pasteboard = NSPasteboard.general
            pasteboard.clearContents()
            pasteboard.setString(jsonString, forType: .string)
            #else
            UIPasteboard.general.string = jsonString
            #endif
            showingExportConfirmation = true
        } catch {
            errorMessage = "Failed to export: \(error.localizedDescription)"
            showingError = true
        }
    }
}

// MARK: - Output Type Filter

struct OutputTypeFilter: View {
    @Binding var selectedTypes: Set<OutputType>
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                FilterChip(title: "All", isSelected: selectedTypes.isEmpty) {
                    selectedTypes.removeAll()
                }
                
                ForEach([OutputType.text, .reasoning, .toolCompleted, .command, .error], id: \.self) { type in
                    FilterChip(title: type.label, isSelected: selectedTypes.contains(type)) {
                        if selectedTypes.contains(type) {
                            selectedTypes.remove(type)
                        } else {
                            selectedTypes.insert(type)
                        }
                    }
                }
            }
        }
    }
}

// MARK: - Live Indicator

struct LiveIndicator: View {
    @State private var isAnimating = false
    
    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(Color.liquidGlass.error)
                .frame(width: 8, height: 8)
                .scaleEffect(isAnimating ? 1.2 : 0.8)
            
            Text("LIVE")
                .font(.caption2)
                .fontWeight(.bold)
                .foregroundColor(Color.liquidGlass.error)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Color.liquidGlass.error.opacity(0.2))
        .clipShape(Capsule())
        .onAppear {
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                isAnimating = true
            }
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        AgentOutputView()
            .environmentObject(MonitorViewModel())
            .background(LiquidGradientBackground())
    }
}
