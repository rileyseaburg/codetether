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
                case .disconnected: return codebase.status == .disconnected
                case .unknown: return codebase.status == .unknown
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
                        title: searchText.isEmpty && selectedFilter == nil ? "No Projects Connected" : "No Matching Projects",
                        message: searchText.isEmpty && selectedFilter == nil
                            ? "Connect a folder containing your code project to start using AI agents. The folder path should point to the root of your project (where package.json, Cargo.toml, etc. lives)."
                            : "Try adjusting your search or filters to find what you're looking for.",
                        action: searchText.isEmpty && selectedFilter == nil ? { viewModel.showingRegisterSheet = true } : nil,
                        actionTitle: searchText.isEmpty && selectedFilter == nil ? "Connect Project Folder" : nil
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
    @State private var showingHelp = false
    
    // Validation states
    var nameValidation: (isValid: Bool, message: String?) {
        if name.isEmpty {
            return (false, nil)
        }
        if name.count < 2 {
            return (false, "Name should be at least 2 characters")
        }
        if name.count > 50 {
            return (false, "Name is too long (max 50 characters)")
        }
        return (true, nil)
    }
    
    var pathValidation: (isValid: Bool, message: String?) {
        if path.isEmpty {
            return (false, nil)
        }
        if !path.hasPrefix("/") && !path.hasPrefix("~") {
            return (false, "Path should start with / or ~")
        }
        if path.contains(" ") && !path.contains("\\ ") {
            return (false, "Spaces in path may cause issues")
        }
        return (true, nil)
    }
    
    var canSubmit: Bool {
        nameValidation.isValid && pathValidation.isValid && !isLoading
    }
    
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
                        
                        Text("Add a Project")
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundColor(Color.liquidGlass.textPrimary)
                        
                        // Explanation header
                        GlassCard(cornerRadius: 12, padding: 16) {
                            HStack(alignment: .top, spacing: 12) {
                                Image(systemName: "info.circle.fill")
                                    .foregroundColor(Color.liquidGlass.primary)
                                    .font(.title3)
                                
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("What's a project?")
                                        .font(.subheadline)
                                        .fontWeight(.semibold)
                                        .foregroundColor(Color.liquidGlass.textPrimary)
                                    
                                    Text("A project is a folder containing your code. Once registered, you can monitor and trigger AI agents to work on this code.")
                                        .font(.caption)
                                        .foregroundColor(Color.liquidGlass.textSecondary)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                        .padding(.horizontal)
                        
                        // Form
                        VStack(spacing: 20) {
                            // Name field with validation
                            VStack(alignment: .leading, spacing: 8) {
                                GlassTextField(
                                    title: "Project Name",
                                    placeholder: "e.g., My iOS App, Backend API",
                                    text: $name
                                )
                                
                                if let message = nameValidation.message {
                                    HStack(spacing: 4) {
                                        Image(systemName: "exclamationmark.circle.fill")
                                            .font(.caption2)
                                        Text(message)
                                            .font(.caption)
                                    }
                                    .foregroundColor(Color.liquidGlass.warning)
                                    .padding(.horizontal, 4)
                                }
                            }
                            
                            // Path field with validation
                            VStack(alignment: .leading, spacing: 8) {
                                GlassTextField(
                                    title: "Project Folder",
                                    placeholder: "e.g., ~/Projects/my-app or /Users/you/code/project",
                                    text: $path
                                )
                                
                                if let message = pathValidation.message {
                                    HStack(spacing: 4) {
                                        Image(systemName: "exclamationmark.circle.fill")
                                            .font(.caption2)
                                        Text(message)
                                            .font(.caption)
                                    }
                                    .foregroundColor(Color.liquidGlass.warning)
                                    .padding(.horizontal, 4)
                                } else if !path.isEmpty && pathValidation.isValid {
                                    HStack(spacing: 4) {
                                        Image(systemName: "checkmark.circle.fill")
                                            .font(.caption2)
                                        Text("Path looks valid")
                                            .font(.caption)
                                    }
                                    .foregroundColor(Color.liquidGlass.success)
                                    .padding(.horizontal, 4)
                                }
                            }
                            
                            GlassTextField(
                                title: "Description (Optional)",
                                placeholder: "What does this project do?",
                                text: $description,
                                isMultiline: true
                            )
                        }
                        .padding(.horizontal)
                        
                        // Help button
                        Button {
                            showingHelp = true
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "questionmark.circle")
                                Text("Need help finding your project folder?")
                            }
                            .font(.caption)
                            .foregroundColor(Color.liquidGlass.primary)
                        }
                        
                        if let error = errorMessage {
                            HStack(spacing: 8) {
                                Image(systemName: "xmark.circle.fill")
                                Text(error)
                            }
                            .font(.caption)
                            .foregroundColor(Color.liquidGlass.error)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(Color.liquidGlass.error.opacity(0.15))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .padding(.horizontal)
                        }
                        
                        // Actions
                        HStack(spacing: 16) {
                            GlassButton("Cancel", style: .secondary) {
                                dismiss()
                            }
                            .disabled(isLoading)
                            
                            GlassButton(
                                isLoading ? "Registering..." : "Add Project",
                                icon: isLoading ? nil : "plus",
                                style: .primary
                            ) {
                                register()
                            }
                            .disabled(!canSubmit)
                        }
                        .padding()
                    }
                }
                
                // Loading overlay
                if isLoading {
                    Color.black.opacity(0.3)
                        .ignoresSafeArea()
                        .overlay {
                            VStack(spacing: 16) {
                                ProgressView()
                                    .scaleEffect(1.2)
                                    .tint(.white)
                                Text("Adding project...")
                                    .font(.subheadline)
                                    .foregroundColor(.white)
                            }
                            .padding(24)
                            .background(.ultraThinMaterial)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                        }
                }
            }
            #if os(iOS)
            .navigationBarTitleDisplayModeInline()
            #endif
            .alert("Finding Your Project Folder", isPresented: $showingHelp) {
                Button("Got it", role: .cancel) { }
            } message: {
                Text("On Mac: Open Terminal, navigate to your project with 'cd', then type 'pwd' to see the full path.\n\nOn iOS: Use the path where your code is stored on the server running OpenCode.")
            }
        }
    }
    
    func register() {
        isLoading = true
        errorMessage = nil
        
        // Expand ~ to home directory path representation
        let expandedPath = path.hasPrefix("~") ? path : path
        
        Task {
            do {
                try await viewModel.registerCodebase(
                    name: name,
                    path: expandedPath,
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
    @State private var selectedModel: String = "claude-sonnet-4"
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showAdvancedOptions = false
    
    // Agent types with clear descriptions
    let agentTypes = [
        ("build", "Build", "Make changes to your code"),
        ("plan", "Plan", "Create a plan without making changes"),
        ("general", "General", "Answer questions about your code"),
        ("explore", "Explore", "Search and understand your codebase")
    ]
    
    // Prompt templates for quick start
    let promptTemplates = [
        ("Fix the bug in...", "wrench.and.screwdriver"),
        ("Add a new feature that...", "plus.circle"),
        ("Explain how the... works", "questionmark.circle"),
        ("Refactor the...", "arrow.triangle.2.circlepath")
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
    
    var selectedModelDisplay: String {
        if let model = viewModel.availableModels.first(where: { $0.id == selectedModel }) {
            return model.displayName
        }
        return selectedModel.isEmpty ? "Default" : selectedModel
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
                            
                            Text("Start AI Agent")
                                .font(.title)
                                .fontWeight(.bold)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                            
                            HStack(spacing: 6) {
                                Image(systemName: "folder.fill")
                                    .font(.caption)
                                Text(codebase.name)
                            }
                            .font(.subheadline)
                            .foregroundColor(Color.liquidGlass.textSecondary)
                        }
                        .padding(.top, 20)
                        
                        // Agent Type Selection - First and prominent
                        VStack(alignment: .leading, spacing: 12) {
                            Text("What do you want to do?")
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
                        
                        // Prompt Templates
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Quick Start")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                            
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 8) {
                                    ForEach(promptTemplates, id: \.0) { template in
                                        Button {
                                            prompt = template.0
                                        } label: {
                                            HStack(spacing: 6) {
                                                Image(systemName: template.1)
                                                    .font(.caption)
                                                Text(template.0)
                                                    .font(.caption)
                                            }
                                            .padding(.horizontal, 12)
                                            .padding(.vertical, 8)
                                            .background(
                                                prompt == template.0
                                                    ? Color.liquidGlass.primary.opacity(0.3)
                                                    : Color.white.opacity(0.1)
                                            )
                                            .foregroundColor(
                                                prompt == template.0
                                                    ? Color.liquidGlass.primary
                                                    : Color.liquidGlass.textSecondary
                                            )
                                            .clipShape(RoundedRectangle(cornerRadius: 20))
                                            .overlay(
                                                RoundedRectangle(cornerRadius: 20)
                                                    .stroke(
                                                        prompt == template.0
                                                            ? Color.liquidGlass.primary.opacity(0.5)
                                                            : Color.white.opacity(0.2),
                                                        lineWidth: 1
                                                    )
                                            )
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }
                                .padding(.horizontal, 1)
                            }
                        }
                        .padding(.horizontal)
                        
                        // Prompt - Larger and more prominent
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("Your Instructions")
                                    .font(.subheadline)
                                    .fontWeight(.semibold)
                                    .foregroundColor(Color.liquidGlass.textSecondary)
                                
                                Spacer()
                                
                                if !prompt.isEmpty {
                                    Text("\(prompt.count) chars")
                                        .font(.caption2)
                                        .foregroundColor(Color.liquidGlass.textMuted)
                                }
                            }
                            
                            TextEditor(text: $prompt)
                                .frame(minHeight: 140)
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
                                        if prompt.isEmpty {
                                            Text("Describe what you want the AI to do...\n\nBe specific about which files, features, or bugs you're referring to.")
                                                .foregroundColor(Color.liquidGlass.textMuted)
                                                .padding(.horizontal, 16)
                                                .padding(.vertical, 20)
                                        }
                                    },
                                    alignment: .topLeading
                                )
                        }
                        .padding(.horizontal)
                        
                        // Advanced Options (collapsed by default)
                        VStack(spacing: 12) {
                            Button {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    showAdvancedOptions.toggle()
                                }
                            } label: {
                                HStack {
                                    Image(systemName: "gearshape")
                                        .font(.caption)
                                    Text("Advanced Options")
                                        .font(.subheadline)
                                    Spacer()
                                    Image(systemName: showAdvancedOptions ? "chevron.up" : "chevron.down")
                                        .font(.caption)
                                }
                                .foregroundColor(Color.liquidGlass.textSecondary)
                                .padding(.horizontal)
                            }
                            .buttonStyle(.plain)
                            
                            if showAdvancedOptions {
                                VStack(alignment: .leading, spacing: 12) {
                                    HStack {
                                        Text("AI Model")
                                            .font(.caption)
                                            .foregroundColor(Color.liquidGlass.textMuted)
                                        
                                        Spacer()
                                        
                                        Text("Using: \(selectedModelDisplay)")
                                            .font(.caption)
                                            .foregroundColor(Color.liquidGlass.primary)
                                    }
                                    
                                    Menu {
                                        Button {
                                            selectedModel = "claude-sonnet-4"
                                        } label: {
                                            HStack {
                                                Text("Claude Sonnet 4")
                                                if selectedModel == "claude-sonnet-4" {
                                                    Image(systemName: "checkmark")
                                                }
                                            }
                                        }
                                        
                                        Button {
                                            selectedModel = ""
                                        } label: {
                                            HStack {
                                                Text("Server Default")
                                                if selectedModel.isEmpty {
                                                    Image(systemName: "checkmark")
                                                }
                                            }
                                        }
                                        
                                        Divider()
                                        
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
                                                            if selectedModel == model.id {
                                                                Image(systemName: "checkmark")
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
                                                Text(selectedModel.isEmpty ? "Server Default" : selectedModel)
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
                                .transition(.opacity.combined(with: .move(edge: .top)))
                            }
                        }
                        
                        if let error = errorMessage {
                            HStack(spacing: 8) {
                                Image(systemName: "xmark.circle.fill")
                                Text(error)
                            }
                            .font(.caption)
                            .foregroundColor(Color.liquidGlass.error)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(Color.liquidGlass.error.opacity(0.15))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .padding(.horizontal)
                        }
                        
                        // Actions
                        HStack(spacing: 16) {
                            GlassButton("Cancel", style: .secondary) {
                                dismiss()
                            }
                            .disabled(isLoading)
                            
                            GlassButton(
                                isLoading ? "Starting..." : "Start Agent",
                                icon: isLoading ? nil : "bolt.fill",
                                style: .primary
                            ) {
                                trigger()
                            }
                            .disabled(prompt.isEmpty || isLoading)
                        }
                        .padding()
                    }
                }
                
                // Loading overlay
                if isLoading {
                    Color.black.opacity(0.3)
                        .ignoresSafeArea()
                        .overlay {
                            VStack(spacing: 16) {
                                ProgressView()
                                    .scaleEffect(1.2)
                                    .tint(.white)
                                Text("Starting agent...")
                                    .font(.subheadline)
                                    .foregroundColor(.white)
                            }
                            .padding(24)
                            .background(.ultraThinMaterial)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                        }
                }
            }
            #if os(iOS)
            .navigationBarTitleDisplayModeInline()
            #endif
            .onAppear {
                // Set default model to claude-sonnet-4 if not already set
                if selectedModel.isEmpty {
                    selectedModel = "claude-sonnet-4"
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
        case "general": return "questionmark.bubble"
        case "explore": return "magnifyingglass"
        default: return "cpu"
        }
    }
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 6) {
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
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                    .minimumScaleFactor(0.9)
            }
            .frame(maxWidth: .infinity)
            .frame(minHeight: 90)
            .padding(.horizontal, 12)
            .padding(.vertical, 14)
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
