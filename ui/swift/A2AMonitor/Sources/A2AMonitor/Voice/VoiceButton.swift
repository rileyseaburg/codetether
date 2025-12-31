import SwiftUI

struct VoiceButton: View {
    let codebaseId: String?
    let sessionId: String?
    let mode: VoiceMode

    @State private var showVoiceSelector = false
    @State private var showVoiceChat = false
    @State private var selectedVoice: VoiceOption?
    @State private var voices: [VoiceOption] = []
    @State private var isLoading = false

    enum VoiceMode {
        case voice
        case voiceWithPlayback
    }

    var body: some View {
        Button {
            loadVoices()
            showVoiceSelector = true
        } label: {
            HStack(spacing: 8) {
                Image(systemName: "mic.fill")
                Text("Voice Chat")
            }
            .font(.subheadline.weight(.medium))
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Capsule().fill(Color.blue))
            .foregroundStyle(.white)
        }
        .sheet(isPresented: $showVoiceSelector) {
            VoiceSelectorSheet(
                voices: voices,
                selectedVoice: $selectedVoice,
                onDismiss: {
                    showVoiceSelector = false
                    if selectedVoice != nil {
                        showVoiceChat = true
                    }
                }
            )
            .presentationDetents([.medium, .large])
        }
        .fullScreenCover(isPresented: $showVoiceChat) {
            if let voice = selectedVoice, let codebase = codebaseId {
                VoiceChatView(
                    codebaseId: codebase,
                    sessionId: sessionId,
                    voice: voice
                )
            }
        }
        .onAppear {
            loadVoices()
        }
    }

    private func loadVoices() {
        guard voices.isEmpty && !isLoading else { return }
        isLoading = true

        Task {
            let manager = VoiceSessionManager()
            let fetchedVoices = await manager.fetchVoices()
            voices = fetchedVoices
            isLoading = false
        }
    }
}
