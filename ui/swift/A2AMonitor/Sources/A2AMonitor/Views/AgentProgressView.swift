import SwiftUI
import Combine

// MARK: - Agent Progress View

/// Live agent progress view showing real-time agent activity with voice interrupt capability.
/// Displays current step, completed steps, elapsed time, and provides pause/stop controls.
struct AgentProgressView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    let task: AgentTask
    
    @State private var showingVoiceInterrupt = false
    @State private var currentStep: String = "Initializing agent..."
    @State private var currentStepDetail: String = ""
    @State private var completedSteps: [CompletedStep] = []
    @State private var elapsedTime: TimeInterval = 0
    @State private var isPaused = false
    @State private var showingStopConfirmation = false
    @State private var expandedSteps = false
    
    // Timer for elapsed time
    @State private var timer: Timer?
    @State private var stepStartTime: Date = Date()
    
    // Cancellables for SSE updates
    @State private var cancellables = Set<AnyCancellable>()
    
    var body: some View {
        ZStack {
            LiquidGradientBackground()
            
            ScrollView {
                VStack(spacing: 24) {
                    // Header with task description and progress
                    headerSection
                    
                    // Current step - prominent display
                    currentStepCard
                    
                    // Completed steps - collapsible list
                    completedStepsSection
                    
                    // Voice interrupt button
                    voiceInterruptSection
                    
                    // Action buttons
                    actionButtons
                    
                    Spacer(minLength: 100)
                }
                .padding()
            }
        }
        .navigationTitle("Agent Working")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: 12) {
                    // Pause/Resume button
                    Button {
                        togglePause()
                    } label: {
                        Image(systemName: isPaused ? "play.fill" : "pause.fill")
                            .foregroundColor(isPaused ? .green : .primary)
                    }
                    
                    // Stop button
                    Button {
                        showingStopConfirmation = true
                    } label: {
                        Image(systemName: "stop.fill")
                            .foregroundColor(.red)
                    }
                }
            }
        }
        .sheet(isPresented: $showingVoiceInterrupt) {
            VoiceInterruptSheet(task: task, onSend: { instruction in
                addVoiceInstruction(instruction)
            })
        }
        .alert("Stop Agent?", isPresented: $showingStopConfirmation) {
            Button("Cancel", role: .cancel) { }
            Button("Stop", role: .destructive) {
                stopAgent()
            }
        } message: {
            Text("This will interrupt the current task. Any unsaved progress may be lost.")
        }
        .onAppear {
            startTimer()
            subscribeToUpdates()
        }
        .onDisappear {
            stopTimer()
            cancellables.removeAll()
        }
    }
    
    // MARK: - Header Section
    
    private var headerSection: some View {
        GlassCard(cornerRadius: 20, padding: 20) {
            VStack(spacing: 16) {
                // Task description in quotes
                Text("\"\(task.title)\"")
                    .font(.headline)
                    .foregroundColor(Color.liquidGlass.textPrimary)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
                
                // Progress bar with animation
                progressBar
                
                // Stats row
                HStack(spacing: 24) {
                    // Time elapsed
                    VStack(spacing: 4) {
                        Text(formatTime(elapsedTime))
                            .font(.system(.title3, design: .monospaced))
                            .fontWeight(.semibold)
                            .foregroundColor(Color.liquidGlass.textPrimary)
                        Text("Elapsed")
                            .font(.caption2)
                            .foregroundColor(Color.liquidGlass.textMuted)
                            .textCase(.uppercase)
                    }
                    
                    Divider()
                        .frame(height: 30)
                    
                    // Steps completed
                    VStack(spacing: 4) {
                        Text("\(completedSteps.count)")
                            .font(.system(.title3, design: .rounded))
                            .fontWeight(.semibold)
                            .foregroundColor(Color.liquidGlass.textPrimary)
                        Text("Steps")
                            .font(.caption2)
                            .foregroundColor(Color.liquidGlass.textMuted)
                            .textCase(.uppercase)
                    }
                    
                    Divider()
                        .frame(height: 30)
                    
                    // Status
                    VStack(spacing: 4) {
                        StatusIndicator(status: isPaused ? .idle : .running, showLabel: false, size: 14)
                        Text(isPaused ? "Paused" : "Active")
                            .font(.caption2)
                            .foregroundColor(Color.liquidGlass.textMuted)
                            .textCase(.uppercase)
                    }
                }
            }
        }
    }
    
    private var progressBar: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                // Background track
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.white.opacity(0.2))
                    .frame(height: 8)
                
                // Progress fill with gradient
                RoundedRectangle(cornerRadius: 4)
                    .fill(
                        LinearGradient(
                            colors: [Color.cyan, Color.liquidGlass.primary],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(width: geo.size.width * progress, height: 8)
                    .animation(.spring(response: 0.5), value: progress)
                
                // Animated shimmer when active
                if !isPaused {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(
                            LinearGradient(
                                colors: [.clear, .white.opacity(0.3), .clear],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: geo.size.width * 0.3, height: 8)
                        .offset(x: shimmerOffset(width: geo.size.width))
                }
            }
        }
        .frame(height: 8)
    }
    
    @State private var shimmerPhase: CGFloat = 0
    
    private func shimmerOffset(width: CGFloat) -> CGFloat {
        let progressWidth = width * progress
        return (shimmerPhase * progressWidth) - width * 0.15
    }
    
    // MARK: - Current Step Card
    
    private var currentStepCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                HStack(spacing: 8) {
                    Image(systemName: "location.fill")
                        .foregroundColor(.cyan)
                    Text("Current Step")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(Color.liquidGlass.textSecondary)
                }
                
                Spacer()
                
                // Animated activity indicator
                if !isPaused {
                    ActivityPulse()
                }
            }
            
            // Main step description
            Text(currentStep)
                .font(.body)
                .fontWeight(.medium)
                .foregroundColor(Color.liquidGlass.textPrimary)
            
            // Step detail/substep
            if !currentStepDetail.isEmpty {
                HStack(spacing: 8) {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .cyan))
                        .scaleEffect(0.7)
                    
                    Text(currentStepDetail)
                        .font(.caption)
                        .foregroundColor(Color.liquidGlass.textSecondary)
                        .lineLimit(2)
                }
            }
            
            // Current step timer
            Text("Started \(formatTime(Date().timeIntervalSince(stepStartTime))) ago")
                .font(.caption2)
                .foregroundColor(Color.liquidGlass.textMuted)
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.cyan.opacity(0.1))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.cyan.opacity(0.3), lineWidth: 1)
                )
        )
        .overlay(
            // Pulsing border when active
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.cyan.opacity(isPaused ? 0 : 0.5), lineWidth: 2)
                .modifier(PulseAnimation())
                .opacity(isPaused ? 0 : 1)
        )
    }
    
    // MARK: - Completed Steps Section
    
    private var completedStepsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Section header with expand/collapse
            Button {
                withAnimation(.spring(response: 0.3)) {
                    expandedSteps.toggle()
                }
            } label: {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text("Completed Steps")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(Color.liquidGlass.textSecondary)
                    
                    Spacer()
                    
                    if !completedSteps.isEmpty {
                        Text("\(completedSteps.count)")
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(Color.green)
                            .clipShape(Capsule())
                        
                        Image(systemName: expandedSteps ? "chevron.up" : "chevron.down")
                            .foregroundColor(Color.liquidGlass.textMuted)
                            .font(.caption)
                    }
                }
            }
            .buttonStyle(.plain)
            
            // Steps list
            if expandedSteps || completedSteps.count <= 3 {
                if completedSteps.isEmpty {
                    Text("No steps completed yet")
                        .font(.caption)
                        .foregroundColor(Color.liquidGlass.textMuted)
                        .padding(.vertical, 8)
                } else {
                    ForEach(completedSteps.reversed().prefix(expandedSteps ? 20 : 3)) { step in
                        CompletedStepRow(step: step)
                    }
                    
                    if !expandedSteps && completedSteps.count > 3 {
                        Button {
                            withAnimation {
                                expandedSteps = true
                            }
                        } label: {
                            Text("Show \(completedSteps.count - 3) more...")
                                .font(.caption)
                                .foregroundColor(.cyan)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(Color.white.opacity(0.05))
        )
    }
    
    // MARK: - Voice Interrupt Section
    
    private var voiceInterruptSection: some View {
        Button {
            showingVoiceInterrupt = true
        } label: {
            HStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(Color.cyan.opacity(0.2))
                        .frame(width: 44, height: 44)
                    
                    Image(systemName: "mic.fill")
                        .font(.title3)
                        .foregroundColor(.cyan)
                }
                
                VStack(alignment: .leading, spacing: 2) {
                    Text("Add Voice Instructions")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundColor(Color.liquidGlass.textPrimary)
                    
                    Text("Tap to speak additional instructions to the agent")
                        .font(.caption)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .foregroundColor(Color.liquidGlass.textMuted)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(Color.white.opacity(0.08))
                    .overlay(
                        RoundedRectangle(cornerRadius: 16)
                            .stroke(Color.cyan.opacity(0.2), lineWidth: 1)
                    )
            )
        }
        .buttonStyle(.plain)
    }
    
    // MARK: - Action Buttons
    
    private var actionButtons: some View {
        HStack(spacing: 16) {
            // View changes/diff
            NavigationLink {
                AgentChangesView(task: task)
            } label: {
                Label("View Changes", systemImage: "eye")
                    .font(.subheadline)
                    .fontWeight(.medium)
            }
            .buttonStyle(.bordered)
            .tint(.cyan)
            
            // See output/code
            NavigationLink {
                if let codebaseId = task.codebaseId {
                    AgentOutputDetailView(codebaseId: codebaseId)
                }
            } label: {
                Label("See Output", systemImage: "doc.text")
                    .font(.subheadline)
                    .fontWeight(.medium)
            }
            .buttonStyle(.bordered)
            .tint(.white.opacity(0.3))
        }
    }
    
    // MARK: - Computed Properties
    
    private var progress: CGFloat {
        guard !completedSteps.isEmpty else { return 0.05 }
        // Estimate progress based on completed steps, capping at 95%
        return min(CGFloat(completedSteps.count) / 12.0, 0.95)
    }
    
    // MARK: - Helper Methods
    
    private func formatTime(_ interval: TimeInterval) -> String {
        let hours = Int(interval) / 3600
        let minutes = (Int(interval) % 3600) / 60
        let seconds = Int(interval) % 60
        
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, seconds)
        }
        return String(format: "%d:%02d", minutes, seconds)
    }
    
    private func startTimer() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            if !isPaused {
                elapsedTime += 1
                
                // Update shimmer animation
                withAnimation(.linear(duration: 1)) {
                    shimmerPhase = (shimmerPhase + 0.1).truncatingRemainder(dividingBy: 1.0)
                }
            }
        }
    }
    
    private func stopTimer() {
        timer?.invalidate()
        timer = nil
    }
    
    private func togglePause() {
        isPaused.toggle()
        
        if isPaused {
            pauseAgent()
        } else {
            resumeAgent()
        }
    }
    
    private func pauseAgent() {
        // Pause the running agent via interrupt
        guard let codebaseId = task.codebaseId,
              let codebase = viewModel.codebases.first(where: { $0.id == codebaseId }) else { return }
        
        Task {
            try? await viewModel.interruptAgent(codebase)
        }
    }
    
    private func resumeAgent() {
        // Resume the agent
        guard let codebaseId = task.codebaseId,
              let codebase = viewModel.codebases.first(where: { $0.id == codebaseId }) else { return }
        
        Task {
            try? await viewModel.triggerAgent(codebase: codebase, prompt: "Continue with the previous task")
        }
    }
    
    private func stopAgent() {
        guard let codebaseId = task.codebaseId,
              let codebase = viewModel.codebases.first(where: { $0.id == codebaseId }) else { return }
        
        Task {
            try? await viewModel.stopAgent(codebase)
        }
    }
    
    private func addVoiceInstruction(_ instruction: String) {
        // Add voice instruction as a new step hint
        guard let codebaseId = task.codebaseId,
              let codebase = viewModel.codebases.first(where: { $0.id == codebaseId }) else { return }
        
        Task {
            try? await viewModel.sendIntervention(agentId: codebase.id, message: instruction)
        }
    }
    
    private func subscribeToUpdates() {
        // Subscribe to agent output updates for this codebase
        guard let codebaseId = task.codebaseId else { return }
        
        // Observe output entries for this codebase
        viewModel.$agentOutputs
            .compactMap { $0[codebaseId] }
            .receive(on: DispatchQueue.main)
            .sink { outputs in
                processOutputUpdates(outputs)
            }
            .store(in: &cancellables)
    }
    
    private func processOutputUpdates(_ outputs: [OutputEntry]) {
        guard let latest = outputs.last else { return }
        
        // Update current step based on output type
        switch latest.type {
        case .stepStart:
            // Complete previous step if exists
            if !currentStep.isEmpty && currentStep != "Initializing agent..." {
                let stepDuration = Date().timeIntervalSince(stepStartTime)
                completedSteps.append(CompletedStep(
                    description: currentStep,
                    duration: stepDuration,
                    status: .completed
                ))
            }
            currentStep = latest.content
            currentStepDetail = ""
            stepStartTime = Date()
            
        case .toolRunning:
            currentStepDetail = latest.toolName.map { "Running \($0)..." } ?? latest.content
            
        case .toolCompleted:
            currentStepDetail = latest.toolName.map { "\($0) completed" } ?? "Tool completed"
            
        case .text, .reasoning:
            // Update detail with reasoning/text snippets
            if latest.content.count < 100 {
                currentStepDetail = latest.content
            }
            
        case .stepFinish:
            // Mark current step as completed
            let stepDuration = Date().timeIntervalSince(stepStartTime)
            completedSteps.append(CompletedStep(
                description: currentStep,
                duration: stepDuration,
                status: .completed
            ))
            currentStep = "Preparing next step..."
            currentStepDetail = ""
            stepStartTime = Date()
            
        case .error, .toolError:
            currentStepDetail = "Error: \(latest.content.prefix(50))..."
            
        default:
            break
        }
    }
}

// MARK: - Supporting Types

struct CompletedStep: Identifiable {
    let id = UUID()
    let description: String
    let duration: TimeInterval
    let status: StepStatus
    
    enum StepStatus {
        case completed
        case skipped
        case error
        
        var icon: String {
            switch self {
            case .completed: return "checkmark.circle.fill"
            case .skipped: return "arrow.right.circle.fill"
            case .error: return "exclamationmark.circle.fill"
            }
        }
        
        var color: Color {
            switch self {
            case .completed: return .green
            case .skipped: return .orange
            case .error: return .red
            }
        }
    }
}

// MARK: - Completed Step Row

struct CompletedStepRow: View {
    let step: CompletedStep
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: step.status.icon)
                .foregroundColor(step.status.color)
                .font(.caption)
            
            Text(step.description)
                .font(.subheadline)
                .foregroundColor(Color.liquidGlass.textPrimary)
                .lineLimit(2)
            
            Spacer()
            
            Text(formatDuration(step.duration))
                .font(.caption)
                .foregroundColor(Color.liquidGlass.textMuted)
                .monospacedDigit()
        }
        .padding(.vertical, 6)
    }
    
    private func formatDuration(_ interval: TimeInterval) -> String {
        if interval < 60 {
            return String(format: "%.0fs", interval)
        }
        let minutes = Int(interval) / 60
        let seconds = Int(interval) % 60
        return String(format: "%dm %ds", minutes, seconds)
    }
}

// MARK: - Activity Pulse

struct ActivityPulse: View {
    @State private var isAnimating = false
    
    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3) { index in
                Circle()
                    .fill(Color.cyan)
                    .frame(width: 6, height: 6)
                    .scaleEffect(isAnimating ? 1.0 : 0.5)
                    .opacity(isAnimating ? 1.0 : 0.3)
                    .animation(
                        .easeInOut(duration: 0.6)
                        .repeatForever()
                        .delay(Double(index) * 0.2),
                        value: isAnimating
                    )
            }
        }
        .onAppear {
            isAnimating = true
        }
    }
}

// MARK: - Voice Interrupt Sheet

struct VoiceInterruptSheet: View {
    let task: AgentTask
    let onSend: (String) -> Void
    
    @Environment(\.dismiss) private var dismiss
    @State private var transcription = ""
    @State private var isRecording = false
    @State private var recordingTime: TimeInterval = 0
    @State private var recordingTimer: Timer?
    
    var body: some View {
        NavigationStack {
            ZStack {
                Color.liquidGlass.background.ignoresSafeArea()
                
                VStack(spacing: 32) {
                    // Header
                    VStack(spacing: 8) {
                        Text("Voice Interrupt")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(Color.liquidGlass.textPrimary)
                        
                        Text("Add instructions to the running task")
                            .font(.subheadline)
                            .foregroundColor(Color.liquidGlass.textSecondary)
                    }
                    
                    // Current task context
                    GlassCard(cornerRadius: 12, padding: 12) {
                        HStack {
                            Image(systemName: "target")
                                .foregroundColor(.cyan)
                            Text(task.title)
                                .font(.caption)
                                .foregroundColor(Color.liquidGlass.textSecondary)
                                .lineLimit(1)
                        }
                    }
                    
                    Spacer()
                    
                    // Voice recording button
                    VStack(spacing: 16) {
                        // Recording indicator
                        if isRecording {
                            HStack(spacing: 8) {
                                Circle()
                                    .fill(Color.red)
                                    .frame(width: 8, height: 8)
                                    .modifier(PulseAnimation())
                                
                                Text(formatRecordingTime(recordingTime))
                                    .font(.system(.body, design: .monospaced))
                                    .foregroundColor(Color.liquidGlass.textSecondary)
                            }
                        }
                        
                        // Main voice button
                        Button {
                            toggleRecording()
                        } label: {
                            ZStack {
                                // Outer glow when recording
                                if isRecording {
                                    Circle()
                                        .fill(Color.red.opacity(0.2))
                                        .frame(width: 120, height: 120)
                                        .modifier(PulseAnimation())
                                }
                                
                                // Main button
                                Circle()
                                    .fill(
                                        isRecording
                                            ? LinearGradient(colors: [.red, .red.opacity(0.8)], startPoint: .top, endPoint: .bottom)
                                            : LinearGradient(colors: [.cyan, Color.liquidGlass.primary], startPoint: .top, endPoint: .bottom)
                                    )
                                    .frame(width: 88, height: 88)
                                    .shadow(color: (isRecording ? Color.red : Color.cyan).opacity(0.4), radius: 20)
                                
                                // Icon
                                Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                                    .font(.system(size: 32))
                                    .foregroundColor(.white)
                            }
                        }
                        .buttonStyle(.plain)
                        
                        Text(isRecording ? "Tap to stop" : "Tap to speak")
                            .font(.caption)
                            .foregroundColor(Color.liquidGlass.textMuted)
                    }
                    
                    Spacer()
                    
                    // Transcription display
                    if !transcription.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Your instruction:")
                                .font(.caption)
                                .foregroundColor(Color.liquidGlass.textMuted)
                            
                            Text(transcription)
                                .font(.body)
                                .foregroundColor(Color.liquidGlass.textPrimary)
                                .padding()
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(Color.white.opacity(0.1))
                                .cornerRadius(12)
                        }
                    }
                    
                    // Alternative: type instruction
                    TextField("Or type your instruction...", text: $transcription)
                        .textFieldStyle(.plain)
                        .padding()
                        .background(Color.white.opacity(0.1))
                        .cornerRadius(12)
                        .foregroundColor(Color.liquidGlass.textPrimary)
                }
                .padding(24)
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(Color.liquidGlass.textSecondary)
                }
                
                ToolbarItem(placement: .confirmationAction) {
                    Button("Send") {
                        onSend(transcription)
                        dismiss()
                    }
                    .fontWeight(.semibold)
                    .foregroundColor(.cyan)
                    .disabled(transcription.isEmpty)
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
    
    private func toggleRecording() {
        isRecording.toggle()
        
        if isRecording {
            startRecording()
        } else {
            stopRecording()
        }
    }
    
    private func startRecording() {
        recordingTime = 0
        recordingTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { _ in
            recordingTime += 0.1
        }
        
        // TODO: Integrate with actual speech recognition
        // For now, simulate with placeholder
    }
    
    private func stopRecording() {
        recordingTimer?.invalidate()
        recordingTimer = nil
        
        // TODO: Process actual transcription
        // For now, use typed text or simulate
        if transcription.isEmpty {
            transcription = "Voice instruction recorded" // Placeholder
        }
    }
    
    private func formatRecordingTime(_ time: TimeInterval) -> String {
        let minutes = Int(time) / 60
        let seconds = Int(time) % 60
        let tenths = Int((time.truncatingRemainder(dividingBy: 1)) * 10)
        return String(format: "%d:%02d.%d", minutes, seconds, tenths)
    }
}

// MARK: - Agent Changes View (Placeholder)

struct AgentChangesView: View {
    let task: AgentTask
    
    var body: some View {
        ZStack {
            LiquidGradientBackground()
            
            VStack(spacing: 20) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.system(size: 60))
                    .foregroundColor(Color.liquidGlass.textMuted)
                
                Text("Changes Preview")
                    .font(.title2)
                    .fontWeight(.semibold)
                    .foregroundColor(Color.liquidGlass.textPrimary)
                
                Text("View file changes made by the agent")
                    .font(.body)
                    .foregroundColor(Color.liquidGlass.textSecondary)
                    .multilineTextAlignment(.center)
            }
            .padding()
        }
        .navigationTitle("Changes")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Agent Output Detail View (Placeholder)

struct AgentOutputDetailView: View {
    let codebaseId: String
    @EnvironmentObject var viewModel: MonitorViewModel
    
    var body: some View {
        ZStack {
            LiquidGradientBackground()
            
            ScrollView {
                LazyVStack(spacing: 12) {
                    let outputs = viewModel.agentOutputs[codebaseId] ?? []
                    
                    if outputs.isEmpty {
                        EmptyStateView(
                            icon: "doc.text",
                            title: "No Output Yet",
                            message: "Agent output will appear here as the task progresses."
                        )
                    } else {
                        ForEach(outputs) { entry in
                            OutputEntryView(entry: entry)
                        }
                    }
                }
                .padding()
            }
        }
        .navigationTitle("Agent Output")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Preview

#if DEBUG
struct AgentProgressView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationStack {
            AgentProgressView(task: AgentTask(
                id: "preview-task",
                title: "Fix the authentication bug in the login flow",
                description: "Users are reporting intermittent login failures",
                status: .working,
                priority: .high,
                codebaseId: "test-codebase"
            ))
            .environmentObject(MonitorViewModel())
        }
    }
}
#endif
