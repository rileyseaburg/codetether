import SwiftUI
import AVFoundation
#if os(iOS)
import UIKit
#endif

// MARK: - Command View (Voice-First Home Screen)

/// CommandView - The new voice-first home screen
/// Users COMMAND agents from their phone, not just monitor them.
/// The giant voice button is THE HERO - impossible to miss at 140pt.
struct CommandView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @StateObject private var voiceManager = VoiceSessionManager()
    
    @State private var isRecording = false
    @State private var audioLevel: Float = 0
    @State private var transcription = ""
    @State private var showingEnvironmentPicker = false
    @State private var selectedCodebaseId: String = ""
    
    var body: some View {
        ZStack {
            LiquidGradientBackground()
            
            VStack(spacing: 0) {
                // Top: Greeting + Environment selector
                topSection
                
                Spacer()
                
                // Center: GIANT voice button (hero)
                voiceButtonSection
                
                Spacer()
                
                // Bottom: Quick actions + Recent
                bottomSection
            }
            .padding()
        }
        // Full screen voice overlay when recording
        .fullScreenCover(isPresented: $isRecording) {
            VoiceRecordingView(
                isRecording: $isRecording,
                transcription: $transcription,
                audioLevel: $audioLevel,
                environment: currentCodebase?.name ?? "Unknown",
                onComplete: { command in
                    spawnAgent(with: command)
                }
            )
        }
        .onAppear {
            // Select first codebase by default
            if selectedCodebaseId.isEmpty, let first = viewModel.codebases.first {
                selectedCodebaseId = first.id
            }
        }
        .onChange(of: viewModel.codebases) { _, codebases in
            // Update selection if current is no longer valid
            if !codebases.contains(where: { $0.id == selectedCodebaseId }) {
                selectedCodebaseId = codebases.first?.id ?? ""
            }
        }
        .sheet(isPresented: $showingEnvironmentPicker) {
            EnvironmentPickerSheet(
                codebases: viewModel.codebases,
                selectedId: $selectedCodebaseId,
                isConnected: viewModel.isConnected
            )
        }
    }
    
    // MARK: - Top Section
    
    var topSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(greeting)
                .font(.title2)
                .fontWeight(.semibold)
                .foregroundColor(Color.liquidGlass.textPrimary)
            
            // Environment selector - shows which machine you're connected to
            EnvironmentSelectorButton(
                codebase: currentCodebase,
                isConnected: viewModel.isConnected,
                onTap: { showingEnvironmentPicker = true }
            )
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 20)
    }
    
    // MARK: - Voice Button Section (THE HERO)
    
    var voiceButtonSection: some View {
        VStack(spacing: 24) {
            // Voice button - 140pt, impossible to miss
            VoiceCommandButton(
                isRecording: $isRecording,
                audioLevel: audioLevel,
                isConnected: viewModel.isConnected && currentCodebase != nil
            )
            .frame(width: 140, height: 140)
            
            Text(buttonHintText)
                .font(.subheadline)
                .foregroundColor(Color.liquidGlass.textSecondary)
        }
    }
    
    var buttonHintText: String {
        if !viewModel.isConnected {
            return "Connecting..."
        }
        if currentCodebase == nil {
            return "Select a project first"
        }
        return isRecording ? "Listening..." : "Tap to speak"
    }
    
    // MARK: - Bottom Section
    
    var bottomSection: some View {
        VStack(spacing: 16) {
            // Quick action chips
            HStack(spacing: 12) {
                QuickActionChip(icon: "arrow.counterclockwise", title: "Last task") {
                    repeatLastTask()
                }
                QuickActionChip(icon: "ladybug", title: "Fix bug") {
                    startTemplatedTask(.fixBug)
                }
                QuickActionChip(icon: "sparkles", title: "Add feature") {
                    startTemplatedTask(.addFeature)
                }
            }
            
            // Recent command - one tap to repeat
            if let lastCommand = viewModel.lastCommand {
                RecentCommandRow(command: lastCommand) {
                    spawnAgent(with: lastCommand)
                }
            }
        }
        .padding(.bottom, 20)
    }
    
    // MARK: - Computed Properties
    
    var greeting: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 0..<12: return "Good morning"
        case 12..<17: return "Good afternoon"
        default: return "Good evening"
        }
    }
    
    var currentCodebase: Codebase? {
        viewModel.codebases.first(where: { $0.id == selectedCodebaseId })
            ?? viewModel.codebases.first
    }
    
    // MARK: - Actions
    
    func spawnAgent(with command: String) {
        guard let codebase = currentCodebase else { return }
        
        Task {
            do {
                try await viewModel.triggerAgent(
                    codebase: codebase,
                    prompt: command,
                    agent: "build",
                    model: "claude-sonnet-4"
                )
                // Save as last command
                viewModel.lastCommand = command
            } catch {
                print("Failed to spawn agent: \(error)")
            }
        }
    }
    
    func repeatLastTask() {
        if let last = viewModel.lastCommand {
            spawnAgent(with: last)
        }
    }
    
    func startTemplatedTask(_ template: TaskTemplate) {
        transcription = template.prompt
        isRecording = true
    }
}

// MARK: - Task Template

enum TaskTemplate {
    case fixBug
    case addFeature
    case explain
    case refactor
    
    var prompt: String {
        switch self {
        case .fixBug: return "Fix the bug in "
        case .addFeature: return "Add a feature that "
        case .explain: return "Explain how "
        case .refactor: return "Refactor "
        }
    }
}

// MARK: - Environment Selector Button

struct EnvironmentSelectorButton: View {
    let codebase: Codebase?
    let isConnected: Bool
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                // Connection status dot
                Circle()
                    .fill(statusColor)
                    .frame(width: 10, height: 10)
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(codebase?.name ?? "No project selected")
                        .font(.headline)
                        .foregroundColor(Color.liquidGlass.textPrimary)
                    
                    if let codebase = codebase {
                        Text("\(codebase.path) - \(statusText)")
                            .font(.caption)
                            .foregroundColor(Color.liquidGlass.textSecondary)
                            .lineLimit(1)
                    } else {
                        Text("Tap to select a project")
                            .font(.caption)
                            .foregroundColor(Color.liquidGlass.textSecondary)
                    }
                }
                
                Spacer()
                
                Image(systemName: "chevron.down")
                    .foregroundColor(Color.liquidGlass.textSecondary)
            }
            .padding()
            .background(Color.white.opacity(0.1))
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
    }
    
    var statusColor: Color {
        guard isConnected else { return .red }
        guard let codebase = codebase else { return .gray }
        
        switch codebase.status {
        case .running, .busy: return .green
        case .watching: return .cyan
        case .idle: return .gray
        default: return .orange
        }
    }
    
    var statusText: String {
        guard isConnected else { return "Offline" }
        guard let codebase = codebase else { return "Not selected" }
        return codebase.status.rawValue.capitalized
    }
}

// MARK: - Environment Picker Sheet

struct EnvironmentPickerSheet: View {
    let codebases: [Codebase]
    @Binding var selectedId: String
    let isConnected: Bool
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationStack {
            ZStack {
                LiquidGradientBackground()
                
                ScrollView {
                    VStack(spacing: 12) {
                        if codebases.isEmpty {
                            EmptyStateView(
                                icon: "folder.badge.plus",
                                title: "No Projects",
                                message: "Connect a project folder to start commanding agents."
                            )
                        } else {
                            ForEach(codebases) { codebase in
                                CodebasePickerRow(
                                    codebase: codebase,
                                    isSelected: codebase.id == selectedId,
                                    isConnected: isConnected
                                ) {
                                    selectedId = codebase.id
                                    dismiss()
                                }
                            }
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("Select Project")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}

struct CodebasePickerRow: View {
    let codebase: Codebase
    let isSelected: Bool
    let isConnected: Bool
    let onSelect: () -> Void
    
    var body: some View {
        Button(action: onSelect) {
            HStack(spacing: 16) {
                // Status indicator
                StatusIndicator(status: codebase.status, showLabel: false, size: 12)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(codebase.name)
                        .font(.headline)
                        .foregroundColor(Color.liquidGlass.textPrimary)
                    
                    Text(codebase.path)
                        .font(.caption)
                        .foregroundColor(Color.liquidGlass.textMuted)
                        .lineLimit(1)
                }
                
                Spacer()
                
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(Color.liquidGlass.primary)
                }
            }
            .padding()
            .background(isSelected ? Color.liquidGlass.primary.opacity(0.2) : Color.white.opacity(0.05))
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isSelected ? Color.liquidGlass.primary : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Voice Command Button (THE HERO - 140pt)

struct VoiceCommandButton: View {
    @Binding var isRecording: Bool
    var audioLevel: Float
    var isConnected: Bool
    
    @State private var isPressing = false
    @State private var pulseScale: CGFloat = 1.0
    
    var body: some View {
        ZStack {
            // Outer glow pulse (when idle and connected)
            if !isRecording && isConnected {
                Circle()
                    .fill(Color.cyan.opacity(0.2))
                    .scaleEffect(pulseScale)
                    .onAppear {
                        withAnimation(.easeInOut(duration: 2).repeatForever(autoreverses: true)) {
                            pulseScale = 1.15
                        }
                    }
            }
            
            // Main button
            Circle()
                .fill(
                    LinearGradient(
                        colors: isConnected
                            ? [Color.cyan.opacity(0.8), Color.blue.opacity(0.6)]
                            : [Color.gray.opacity(0.5), Color.gray.opacity(0.3)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    Circle()
                        .stroke(Color.white.opacity(0.3), lineWidth: 2)
                )
                .shadow(color: isConnected ? Color.cyan.opacity(0.5) : Color.clear, radius: isRecording ? 30 : 15)
                .scaleEffect(isPressing ? 1.1 : 1.0)
            
            // Microphone icon
            Image(systemName: isRecording ? "waveform" : "mic.fill")
                .font(.system(size: 50, weight: .medium))
                .foregroundColor(.white)
                .symbolEffect(.bounce, value: isRecording)
        }
        .opacity(isConnected ? 1.0 : 0.5)
        .onTapGesture {
            guard isConnected else { return }
            isRecording = true
            #if os(iOS)
            triggerHaptic(.medium)
            #endif
        }
        .onLongPressGesture(minimumDuration: 0.1, pressing: { pressing in
            guard isConnected else { return }
            withAnimation(.easeInOut(duration: 0.1)) {
                isPressing = pressing
            }
            #if os(iOS)
            if pressing {
                triggerHaptic(.medium)
            }
            #endif
        }) {
            guard isConnected else { return }
            isRecording = true
            #if os(iOS)
            triggerHaptic(.heavy)
            #endif
        }
    }
}

// MARK: - Quick Action Chip

struct QuickActionChip: View {
    let icon: String
    let title: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            VStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.title3)
                Text(title)
                    .font(.caption)
            }
            .foregroundColor(Color.liquidGlass.textPrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(Color.white.opacity(0.1))
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Recent Command Row

struct RecentCommandRow: View {
    let command: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack {
                Image(systemName: "clock.arrow.circlepath")
                    .foregroundColor(Color.liquidGlass.textSecondary)
                
                Text(command)
                    .lineLimit(1)
                    .foregroundColor(Color.liquidGlass.textPrimary)
                
                Spacer()
                
                Image(systemName: "arrow.right.circle.fill")
                    .foregroundColor(Color.liquidGlass.primary)
            }
            .font(.subheadline)
            .padding()
            .background(Color.white.opacity(0.05))
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Haptic Helper

#if os(iOS)
func triggerHaptic(_ style: UIImpactFeedbackGenerator.FeedbackStyle) {
    UIImpactFeedbackGenerator(style: style).impactOccurred()
}
#endif

// MARK: - Preview

#Preview {
    CommandView()
        .environmentObject(MonitorViewModel())
}
