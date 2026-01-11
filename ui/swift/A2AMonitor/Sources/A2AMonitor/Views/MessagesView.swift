import SwiftUI

/// Messages View - Real-time conversation monitoring
struct MessagesView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @State private var searchText = ""
    @State private var showingInterveneSheet = false
    @State private var selectedMessage: Message?
    @State private var showingExportConfirmation = false
    @State private var exportConfirmationMessage = ""
    @State private var showingCopyConfirmation = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Top bar with search and filters
            VStack(spacing: 12) {
                HStack(spacing: 12) {
                    GlassSearchBar(
                        text: $searchText,
                        placeholder: "Search messages...",
                        onSubmit: {
                            Task {
                                await viewModel.searchMessages(query: searchText)
                            }
                        }
                    )
                    
                    GlassButton("Search All", icon: "magnifyingglass", style: .secondary) {
                        Task {
                            await viewModel.searchMessages(query: searchText)
                        }
                    }
                }
                
                // Filters
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        FilterChip(title: "All", isSelected: viewModel.messageFilter == nil) {
                            viewModel.messageFilter = nil
                        }
                        
                        ForEach(MessageType.allCases, id: \.self) { type in
                            FilterChip(title: type.rawValue.capitalized, isSelected: viewModel.messageFilter == type) {
                                viewModel.messageFilter = type
                            }
                        }
                    }
                }
            }
            .padding()
            .background(.ultraThinMaterial)
            
            // Messages list
            ScrollView {
                LazyVStack(spacing: 12) {
                    if viewModel.filteredMessages.isEmpty {
                        EmptyStateView(
                            icon: "bubble.left.and.bubble.right",
                            title: "No Messages",
                            message: "Agent conversations will appear here in real-time"
                        )
                        .padding(.top, 60)
                    } else {
                        ForEach(viewModel.filteredMessages) { message in
                            MessageBubble(message: message)
                                .contextMenu {
                                    Button {
                                        viewModel.flagMessage(message)
                                    } label: {
                                        Label("Flag", systemImage: "flag")
                                    }
                                    
                                    Button {
                                        selectedMessage = message
                                        showingInterveneSheet = true
                                    } label: {
                                        Label("Intervene", systemImage: "hand.raised")
                                    }
                                    
                                    Button {
                                        copyToClipboard(message.content)
                                    } label: {
                                        Label("Copy", systemImage: "doc.on.doc")
                                    }
                                }
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
        .navigationTitle("Messages")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Menu {
                    Button {
                        exportJSON()
                    } label: {
                        Label("Export JSON", systemImage: "doc.text")
                    }
                    
                    Button {
                        exportCSV()
                    } label: {
                        Label("Export CSV", systemImage: "tablecells")
                    }
                    
                    Divider()
                    
                    Button {
                        Task {
                            await viewModel.loadMessages(limit: 500)
                        }
                    } label: {
                        Label("Load History", systemImage: "clock.arrow.circlepath")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
            
            ToolbarItem(placement: .automatic) {
                Button {
                    Task {
                        await viewModel.loadMessages()
                    }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
            }
        }
        .sheet(isPresented: $showingInterveneSheet) {
            InterventionSheet(relatedMessage: selectedMessage)
        }
        .alert("Exported", isPresented: $showingExportConfirmation) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(exportConfirmationMessage)
        }
        .alert("Copied", isPresented: $showingCopyConfirmation) {
            Button("OK", role: .cancel) { }
        } message: {
            Text("Message copied to clipboard")
        }
    }
    
    // MARK: - Export Functions
    
    func exportJSON() {
        guard let data = viewModel.exportMessages(),
              let jsonString = String(data: data, encoding: .utf8) else {
            exportConfirmationMessage = "Failed to export messages"
            showingExportConfirmation = true
            return
        }
        
        #if os(macOS)
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(jsonString, forType: .string)
        #else
        UIPasteboard.general.string = jsonString
        #endif
        exportConfirmationMessage = "JSON copied to clipboard (\(viewModel.messages.count) messages)"
        showingExportConfirmation = true
    }
    
    func exportCSV() {
        let header = "Timestamp,Type,Agent,Content\n"
        let rows = viewModel.messages.map { message in
            let content = message.content.replacingOccurrences(of: "\"", with: "\"\"")
            return "\"\(message.timestamp)\",\"\(message.type.rawValue)\",\"\(message.agentName)\",\"\(content)\""
        }.joined(separator: "\n")
        
        let csv = header + rows
        
        #if os(macOS)
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(csv, forType: .string)
        #else
        UIPasteboard.general.string = csv
        #endif
        exportConfirmationMessage = "CSV copied to clipboard (\(viewModel.messages.count) messages)"
        showingExportConfirmation = true
    }
    
    func copyToClipboard(_ text: String) {
        #if os(macOS)
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(text, forType: .string)
        #else
        UIPasteboard.general.string = text
        #endif
        showingCopyConfirmation = true
    }
}

// MARK: - Intervention Sheet

struct InterventionSheet: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @Environment(\.dismiss) var dismiss
    
    var relatedMessage: Message?
    
    @State private var selectedAgentId: String = ""
    @State private var message = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    
    var body: some View {
        NavigationStack {
            ZStack {
                LiquidGradientBackground()
                
                ScrollView {
                    VStack(spacing: 24) {
                        // Header
                        VStack(spacing: 8) {
                            Image(systemName: "hand.raised.fill")
                                .font(.system(size: 50))
                                .foregroundColor(Color.liquidGlass.warning)
                            
                            Text("Human Intervention")
                                .font(.title)
                                .fontWeight(.bold)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                            
                            Text("Send a message to an active agent")
                                .font(.subheadline)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                        }
                        .padding(.top, 20)
                        
                        // Agent selection
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Target Agent")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                            
                            Picker("Agent", selection: $selectedAgentId) {
                                Text("Select Agent...").tag("")
                                ForEach(viewModel.agents) { agent in
                                    HStack {
                                        StatusIndicator(status: agent.status, showLabel: false, size: 8)
                                        Text(agent.name)
                                    }
                                    .tag(agent.id)
                                }
                            }
                            .pickerStyle(.menu)
                            .padding(12)
                            .background(Color.white.opacity(0.1))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                        .padding(.horizontal)
                        
                        // Related message context
                        if let related = relatedMessage {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Context")
                                    .font(.caption)
                                    .fontWeight(.semibold)
                                    .foregroundColor(Color.liquidGlass.textMuted)
                                
                                Text(related.content.prefix(100) + (related.content.count > 100 ? "..." : ""))
                                    .font(.caption)
                                    .foregroundColor(Color.liquidGlass.textSecondary)
                                    .padding(12)
                                    .background(Color.white.opacity(0.05))
                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                            .padding(.horizontal)
                        }
                        
                        // Intervention message
                        GlassTextField(
                            title: "Message",
                            placeholder: "Enter your instruction or message...",
                            text: $message,
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
                            
                            GlassButton("Send Intervention", icon: "paperplane.fill", style: .primary) {
                                sendIntervention()
                            }
                            .disabled(selectedAgentId.isEmpty || message.isEmpty || isLoading)
                        }
                        .padding()
                    }
                }
            }
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .onAppear {
                if let related = relatedMessage {
                    message = "Regarding: \"\(related.content.prefix(50))...\"\n\n"
                }
            }
        }
    }
    
    func sendIntervention() {
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                try await viewModel.sendIntervention(agentId: selectedAgentId, message: message)
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        MessagesView()
            .environmentObject(MonitorViewModel())
            .background(LiquidGradientBackground())
    }
}
