import SwiftUI

/// Agents View - Manage registered codebases and OpenCode agents
struct AgentsView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @State private var searchText = ""
    @State private var errorMessage: String?
    @State private var showingError = false
    @State private var isPerformingAction = false
    @State private var showingDeleteConfirmation = false
    @State private var codebaseToDelete: Codebase?
    
    @State private var selectedFilter: AgentStatus?
    
    var filteredCodebases: [Codebase] {
        var result = viewModel.codebases
        
        // Apply status filter
        if let filter = selectedFilter {
            result = result.filter { codebase in
                switch filter {
                case .running: return codebase.status == .running
                case .idle: return codebase.status == .idle
                case .error: return codebase.status == .error
                case .busy: return codebase.status == .busy
                case .watching: return codebase.status == .watching
                case .stopped: return codebase.status == .stopped
                }
            }
        }
        
        // Apply search filter
        if !searchText.isEmpty {
            result = result.filter { 
                $0.name.localizedCaseInsensitiveContains(searchText) ||
                $0.path.localizedCaseInsensitiveContains(searchText)
            }
        }
        
        return result
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header with OpenCode status
                openCodeStatusHeader
                
                // Search and filters
                HStack(spacing: 12) {
                    GlassSearchBar(text: $searchText, placeholder: "Search codebases...")
                    
                    GlassButton("Register", icon: "plus", style: .primary) {
                        viewModel.showingRegisterSheet = true
                    }
                }
                
                // Filter chips
                filterChips
                
                // Codebases list
                if filteredCodebases.isEmpty {
                    EmptyStateView(
                        icon: "folder.badge.plus",
                        title: "No Codebases Registered",
                        message: "Register a codebase to start managing AI agents",
                        action: { viewModel.showingRegisterSheet = true },
                        actionTitle: "Register Codebase"
                    )
                    .padding(.top, 40)
                } else {
                    LazyVStack(spacing: 16) {
                        ForEach(filteredCodebases) { codebase in
                            CodebaseCard(
                                codebase: codebase,
                                onTrigger: {
                                    viewModel.selectedCodebase = codebase
                                    viewModel.showingTriggerSheet = true
                                },
                                onWatch: {
                                    Task {
                                        isPerformingAction = true
                                        do {
                                            if codebase.status == .watching {
                                                try await viewModel.stopWatchMode(codebase)
                                            } else {
                                                try await viewModel.startWatchMode(codebase)
                                            }
                                        } catch {
                                            errorMessage = error.localizedDescription
                                            showingError = true
                                        }
                                        isPerformingAction = false
                                    }
                                },
                                onDelete: {
                                    codebaseToDelete = codebase
                                    showingDeleteConfirmation = true
                                }
                            )
                        }
                    }
                }
            }
            .padding(20)
        }
        .refreshable {
            await viewModel.refreshData()
        }
        .background(Color.clear)
        .navigationTitle("Agents")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button {
                    Task {
                        await viewModel.loadCodebases()
                    }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
            }
        }
        .sheet(isPresented: $viewModel.showingRegisterSheet) {
            RegisterCodebaseSheet()
        }
        .sheet(isPresented: $viewModel.showingTriggerSheet) {
            if let codebase = viewModel.selectedCodebase {
                TriggerAgentSheet(codebase: codebase)
            }
        }
        .alert("Error", isPresented: $showingError) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(errorMessage ?? "An unknown error occurred")
        }
        .confirmationDialog("Delete Codebase", isPresented: $showingDeleteConfirmation, presenting: codebaseToDelete) { codebase in
            Button("Delete", role: .destructive) {
                Task {
                    isPerformingAction = true
                    do {
                        try await viewModel.unregisterCodebase(codebase)
                    } catch {
                        errorMessage = error.localizedDescription
                        showingError = true
                    }
                    isPerformingAction = false
                }
            }
        } message: { codebase in
            Text("Are you sure you want to delete \"\(codebase.name)\"? This cannot be undone.")
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
    
    // MARK: - OpenCode Status Header
    
    var openCodeStatusHeader: some View {
        GlassCard(cornerRadius: 16, padding: 16) {
            HStack(spacing: 16) {
                Image(systemName: "terminal.fill")
                    .font(.title)
                    .foregroundColor(Color.liquidGlass.primary)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("OpenCode Integration")
                        .font(.headline)
                        .foregroundColor(Color.liquidGlass.textPrimary)
                    
                    if let status = viewModel.openCodeStatus {
                        HStack(spacing: 8) {
                            Circle()
                                .fill(status.available ? Color.liquidGlass.success : Color.liquidGlass.warning)
                                .frame(width: 8, height: 8)
                            
                            Text(status.available ? "Ready" : (status.message ?? "Unavailable"))
                                .font(.caption)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                        }
                        
                        if let binary = status.opencodeBinary {
                            Text("Binary: \(binary)")
                                .font(.caption2)
                                .foregroundColor(Color.liquidGlass.textMuted)
                        }
                    }
                }
                
                Spacer()
                
                // Stats
                VStack(alignment: .trailing, spacing: 4) {
                    Text("\(viewModel.codebases.count)")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(Color.liquidGlass.textPrimary)
                    
                    Text("Registered")
                        .font(.caption2)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }
                
                Divider()
                    .frame(height: 40)
                
                VStack(alignment: .trailing, spacing: 4) {
                    Text("\(viewModel.codebases.filter { $0.status == .running || $0.status == .busy || $0.status == .watching }.count)")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(Color.liquidGlass.success)
                    
                    Text("Active")
                        .font(.caption2)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }
            }
        }
    }
    
    // MARK: - Filter Chips
    
    var filterChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                FilterChip(title: "All", isSelected: selectedFilter == nil) {
                    selectedFilter = nil
                }
                
                ForEach(AgentStatus.allCases, id: \.self) { status in
                    FilterChip(title: status.rawValue.capitalized, isSelected: selectedFilter == status) {
                        selectedFilter = status
                    }
                }
            }
        }
    }
}

// MARK: - Register Codebase Sheet

struct RegisterCodebaseSheet: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @Environment(\.dismiss) var dismiss
    
    @State private var name = ""
    @State private var path = ""
    @State private var description = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    
    var body: some View {
        NavigationStack {
            ZStack {
                LiquidGradientBackground()
                
                ScrollView {
                    VStack(spacing: 24) {
                        // Icon
                        Image(systemName: "folder.badge.plus")
                            .font(.system(size: 60))
                            .foregroundColor(Color.liquidGlass.primary)
                            .padding(.top, 20)
                        
                        Text("Register Codebase")
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundColor(Color.liquidGlass.textPrimary)
                        
                        // Form
                        VStack(spacing: 16) {
                            GlassTextField(
                                title: "Name",
                                placeholder: "My Project",
                                text: $name
                            )
                            
                            GlassTextField(
                                title: "Absolute Path",
                                placeholder: "/home/user/projects/myproject",
                                text: $path
                            )
                            
                            GlassTextField(
                                title: "Description (Optional)",
                                placeholder: "Brief description of the project...",
                                text: $description,
                                isMultiline: true
                            )
                        }
                        .padding(.horizontal)
                        
                        if let error = errorMessage {
                            Text(error)
                                .font(.caption)
                                .foregroundColor(Color.liquidGlass.error)
                                .padding(.horizontal)
                        }
                        
                        // Actions
                        HStack(spacing: 16) {
                            GlassButton("Cancel", style: .secondary) {
                                dismiss()
                            }
                            
                            GlassButton("Register", icon: "plus", style: .primary) {
                                register()
                            }
                            .disabled(name.isEmpty || path.isEmpty || isLoading)
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
    
    func register() {
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                try await viewModel.registerCodebase(
                    name: name,
                    path: path,
                    description: description.isEmpty ? nil : description
                )
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
}

// MARK: - Trigger Agent Sheet

struct TriggerAgentSheet: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @Environment(\.dismiss) var dismiss
    
    let codebase: Codebase
    
    @State private var prompt = ""
    @State private var selectedAgent = "build"
    @State private var selectedModel: String = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    
    let agentTypes = [
        ("build", "Build", "Full access agent"),
        ("plan", "Plan", "Read-only analysis"),
        ("general", "General", "Multi-step tasks"),
        ("explore", "Explore", "Codebase search")
    ]
    
    // Group models by provider
    var modelsByProvider: [String: [AIModel]] {
        Dictionary(grouping: viewModel.availableModels) { $0.provider }
    }
    
    var sortedProviders: [String] {
        // Put custom/Azure first, then alphabetical
        let providers = Array(modelsByProvider.keys)
        return providers.sorted { p1, p2 in
            let isCustom1 = modelsByProvider[p1]?.first?.custom == true
            let isCustom2 = modelsByProvider[p2]?.first?.custom == true
            if isCustom1 && !isCustom2 { return true }
            if !isCustom1 && isCustom2 { return false }
            return p1 < p2
        }
    }
    
    var body: some View {
        NavigationStack {
            ZStack {
                LiquidGradientBackground()
                
                ScrollView {
                    VStack(spacing: 24) {
                        // Header
                        VStack(spacing: 8) {
                            Image(systemName: "bolt.fill")
                                .font(.system(size: 50))
                                .foregroundColor(Color.liquidGlass.primary)
                            
                            Text("Trigger Agent")
                                .font(.title)
                                .fontWeight(.bold)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                            
                            Text(codebase.name)
                                .font(.subheadline)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                        }
                        .padding(.top, 20)
                        
                        // Model Selection
                        VStack(alignment: .leading, spacing: 12) {
                            Text("AI Model")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                            
                            Menu {
                                Button("Default") {
                                    selectedModel = ""
                                }
                                
                                ForEach(sortedProviders, id: \.self) { provider in
                                    Section(provider) {
                                        ForEach(modelsByProvider[provider] ?? [], id: \.id) { model in
                                            Button {
                                                selectedModel = model.id
                                            } label: {
                                                HStack {
                                                    Image(systemName: model.providerIcon)
                                                    Text(model.name)
                                                    if model.custom == true {
                                                        Text("Custom")
                                                            .font(.caption2)
                                                            .foregroundColor(.secondary)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            } label: {
                                HStack {
                                    if let model = viewModel.availableModels.first(where: { $0.id == selectedModel }) {
                                        Image(systemName: model.providerIcon)
                                        Text(model.displayName)
                                    } else {
                                        Image(systemName: "cpu")
                                        Text(selectedModel.isEmpty ? "Default Model" : selectedModel)
                                    }
                                    Spacer()
                                    Image(systemName: "chevron.up.chevron.down")
                                        .font(.caption)
                                }
                                .padding()
                                .background(.ultraThinMaterial)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(.horizontal)
                        
                        // Agent Type Selection
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Agent Type")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                            
                            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                                ForEach(agentTypes, id: \.0) { type in
                                    AgentTypeButton(
                                        id: type.0,
                                        title: type.1,
                                        subtitle: type.2,
                                        isSelected: selectedAgent == type.0
                                    ) {
                                        selectedAgent = type.0
                                    }
                                }
                            }
                        }
                        .padding(.horizontal)
                        
                        // Prompt
                        GlassTextField(
                            title: "Prompt",
                            placeholder: "Enter your prompt for the AI agent...",
                            text: $prompt,
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
                            
                            GlassButton("Start Agent", icon: "bolt.fill", style: .primary) {
                                trigger()
                            }
                            .disabled(prompt.isEmpty || isLoading)
                        }
                        .padding()
                    }
                }
            }
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .onAppear {
                // Set default model
                if selectedModel.isEmpty, let defaultModel = viewModel.defaultModel {
                    selectedModel = defaultModel
                }
            }
        }
    }
    
    func trigger() {
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                try await viewModel.triggerAgent(
                    codebase: codebase,
                    prompt: prompt,
                    agent: selectedAgent,
                    model: selectedModel.isEmpty ? nil : selectedModel
                )
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
}

// MARK: - Agent Type Button

struct AgentTypeButton: View {
    let id: String
    let title: String
    let subtitle: String
    let isSelected: Bool
    let action: () -> Void
    
    var icon: String {
        switch id {
        case "build": return "hammer.fill"
        case "plan": return "doc.text.magnifyingglass"
        case "general": return "arrow.triangle.2.circlepath"
        case "explore": return "magnifyingglass"
        default: return "cpu"
        }
    }
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(isSelected ? .white : Color.liquidGlass.primary)
                
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(isSelected ? .white : Color.liquidGlass.textPrimary)
                
                Text(subtitle)
                    .font(.caption2)
                    .foregroundColor(isSelected ? .white.opacity(0.8) : Color.liquidGlass.textMuted)
            }
            .frame(maxWidth: .infinity)
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(isSelected ? Color.liquidGlass.primary : Color.white.opacity(0.1))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(isSelected ? Color.clear : Color.white.opacity(0.2), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Glass Text Field

struct GlassTextField: View {
    let title: String
    let placeholder: String
    @Binding var text: String
    var isMultiline: Bool = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(Color.liquidGlass.textSecondary)
            
            if isMultiline {
                TextEditor(text: $text)
                    .frame(minHeight: 100)
                    .padding(12)
                    .scrollContentBackground(.hidden)
                    .background(Color.white.opacity(0.1))
                    .foregroundColor(Color.liquidGlass.textPrimary)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.white.opacity(0.2), lineWidth: 1)
                    )
                    .overlay(
                        Group {
                            if text.isEmpty {
                                Text(placeholder)
                                    .foregroundColor(Color.liquidGlass.textMuted)
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 20)
                            }
                        },
                        alignment: .topLeading
                    )
            } else {
                TextField(placeholder, text: $text)
                    .textFieldStyle(.plain)
                    .padding(12)
                    .background(Color.white.opacity(0.1))
                    .foregroundColor(Color.liquidGlass.textPrimary)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.white.opacity(0.2), lineWidth: 1)
                    )
            }
        }
    }
}

// MARK: - Preview

#Preview {
    AgentsView()
        .environmentObject(MonitorViewModel())
        .background(LiquidGradientBackground())
}
