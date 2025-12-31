import SwiftUI

struct PlaybackView: View {
    let codebaseId: String
    let sessionId: String

    @State private var playbackMode: PlaybackMode = .verbatim
    @State private var isPlaying = false
    @State private var progress: Double = 0.0
    @State private var error: String?

    enum PlaybackMode: String, CaseIterable {
        case verbatim = "verbatim"
        case summary = "summary"

        var displayName: String {
            switch self {
            case .verbatim: return "Verbatim"
            case .summary: return "Summary"
            }
        }
    }

    var body: some View {
        VStack(spacing: 20) {
            VStack(spacing: 8) {
                Text("Session Playback")
                    .font(.headline)

                Text("Listen to \(playbackMode.displayName.lowercased()) of your conversation")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Picker("Playback Mode", selection: $playbackMode) {
                ForEach(PlaybackMode.allCases, id: \.self) { mode in
                    Text(mode.displayName).tag(mode)
                }
            }
            .pickerStyle(.segmented)

            Button {
                startPlayback()
            } label: {
                HStack(spacing: 8) {
                    if isPlaying {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Image(systemName: "play.fill")
                    }
                    Text(isPlaying ? "Playing..." : "Start Playback")
                }
                .font(.subheadline.weight(.medium))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Capsule().fill(Color.blue))
                .foregroundStyle(.white)
            }
            .disabled(isPlaying)

            if isPlaying {
                VStack(spacing: 8) {
                    ProgressView(value: progress)
                        .tint(.blue)

                    Text("\(Int(progress * 100))%")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            if let error = error {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 16).fill(Color(.systemBackground)))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.secondary.opacity(0.2), lineWidth: 1)
        )
    }

    private func startPlayback() {
        isPlaying = true
        progress = 0.0
        error = nil

        Task {
            do {
                try await simulatePlayback()
                isPlaying = false
            } catch {
                self.error = error.localizedDescription
                isPlaying = false
            }
        }
    }

    private func simulatePlayback() async throws {
        let totalSteps = 100
        for i in 0..<totalSteps {
            try await Task.sleep(nanoseconds: 100_000_000)
            progress = Double(i + 1) / Double(totalSteps)
        }
    }
}

struct PlaybackView_Previews: PreviewProvider {
    static var previews: some View {
        PlaybackView(codebaseId: "test-codebase", sessionId: "test-session")
            .padding()
    }
}
