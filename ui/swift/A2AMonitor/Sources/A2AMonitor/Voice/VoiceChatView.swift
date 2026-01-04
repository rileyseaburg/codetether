import SwiftUI
import LiveKit

struct VoiceChatView: View {
    @StateObject private var sessionManager: VoiceSessionManager
    @Environment(\.dismiss) private var dismiss
    @State private var isMuted = false

    init(codebaseId: String, sessionId: String?, voice: VoiceOption) {
        _sessionManager = StateObject(wrappedValue: VoiceSessionManager())
        self.codebaseId = codebaseId
        self.sessionId = sessionId
        self.voice = voice
    }

    private let codebaseId: String
    private let sessionId: String?
    private let voice: VoiceOption

    var body: some View {
        NavigationStack {
            VStack(spacing: 32) {
                VStack(spacing: 8) {
                    Text(voice.name)
                        .font(.title2)
                        .fontWeight(.semibold)

                    Text(voice.description)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 40)

                Spacer()

                ZStack {
                    Circle()
                        .fill(circleColor)
                        .frame(width: 180, height: 180)
                        .shadow(color: shadowColor, radius: 20, x: 0, y: 10)

                    Circle()
                        .fill(circleColor.opacity(0.3))
                        .frame(width: 220, height: 220)
                        .blur(radius: 10)
                }
                .scaleEffect(pulseScale)

                VStack(spacing: 12) {
                    Text(stateText)
                        .font(.headline)
                        .foregroundStyle(stateColor)

                    Text(stateDescription)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                HStack(spacing: 40) {
                    Button {
                        Task {
                            await sessionManager.toggleMute()
                            isMuted = sessionManager.isMuted
                        }
                    } label: {
                        Image(systemName: isMuted ? "mic.slash.fill" : "mic.fill")
                            .font(.title)
                            .foregroundStyle(isMuted ? .red : .primary)
                            .frame(width: 60, height: 60)
                            .background(Circle().fill(.ultraThinMaterial))
                    }

                    Button {
                        Task {
                            await sessionManager.endSession()
                            dismiss()
                        }
                    } label: {
                        Image(systemName: "phone.down.fill")
                            .font(.title)
                            .foregroundStyle(.red)
                            .frame(width: 60, height: 60)
                            .background(Circle().fill(.ultraThinMaterial))
                    }
                }
                .padding(.bottom, 40)
            }
            .padding()
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        Task {
                            await sessionManager.endSession()
                            dismiss()
                        }
                    }
                }
            }
        }
        .task {
            do {
                try await sessionManager.startSession(
                    codebaseId: codebaseId,
                    sessionId: sessionId,
                    voice: voice
                )
            } catch {
                print("Failed to start session: \(error)")
            }
        }
        .onDisappear {
            Task {
                await sessionManager.endSession()
            }
        }
    }

    private var circleColor: Color {
        switch sessionManager.agentState {
        case .idle: return .gray
        case .listening: return .blue
        case .thinking: return .orange
        case .speaking: return .green
        case .error: return .red
        }
    }

    private var shadowColor: Color {
        switch sessionManager.agentState {
        case .idle: return .gray.opacity(0.3)
        case .listening: return .blue.opacity(0.4)
        case .thinking: return .orange.opacity(0.4)
        case .speaking: return .green.opacity(0.4)
        case .error: return .red.opacity(0.4)
        }
    }

    private var stateText: String {
        switch sessionManager.agentState {
        case .idle: return "Ready"
        case .listening: return "Listening..."
        case .thinking: return "Thinking..."
        case .speaking: return "Speaking..."
        case .error: return "Error"
        }
    }

    private var stateColor: Color {
        switch sessionManager.agentState {
        case .idle: return .secondary
        case .listening: return .blue
        case .thinking: return .orange
        case .speaking: return .green
        case .error: return .red
        }
    }

    private var stateDescription: String {
        switch sessionManager.agentState {
        case .idle: return "Waiting to start"
        case .listening: return "Please speak"
        case .thinking: return "Processing your request"
        case .speaking: return "Agent is responding"
        case .error: return "Something went wrong"
        }
    }

    private var pulseScale: CGFloat {
        switch sessionManager.agentState {
        case .idle: return 1.0
        case .listening: return 1.0 + CGFloat(sin(Date.timeIntervalSinceReferenceDate * 3) * 0.05)
        case .thinking: return 1.0 + CGFloat(sin(Date.timeIntervalSinceReferenceDate * 1.5) * 0.03)
        case .speaking: return 1.0 + CGFloat(sin(Date.timeIntervalSinceReferenceDate * 4) * 0.08)
        case .error: return 1.0
        }
    }
}
