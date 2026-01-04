import SwiftUI

struct VoiceSelectorSheet: View {
    let voices: [VoiceOption]
    @Binding var selectedVoice: VoiceOption?
    let onDismiss: () -> Void

    var body: some View {
        NavigationStack {
            List(voices, id: \.id, selection: $selectedVoice) { voice in
                HStack(spacing: 12) {
                    Image(systemName: "waveform")
                        .font(.title2)
                        .foregroundStyle(.blue)
                        .frame(width: 40, height: 40)
                        .background(Circle().fill(Color.blue.opacity(0.1)))

                    VStack(alignment: .leading, spacing: 4) {
                        Text(voice.name)
                            .font(.headline)

                        Text(voice.description)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)

                        HStack(spacing: 8) {
                            Text(voice.displayProvider)
                                .font(.caption2)
                                .foregroundStyle(.tertiary)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Capsule().fill(Color.secondary.opacity(0.2)))

                            if let language = voice.language {
                                Text(language)
                                    .font(.caption2)
                                    .foregroundStyle(.tertiary)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(Capsule().fill(Color.secondary.opacity(0.2)))
                            }
                        }
                    }

                    Spacer()

                    if selectedVoice?.id == voice.id {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.blue)
                    }
                }
                .padding(.vertical, 4)
                .contentShape(Rectangle())
                .onTapGesture {
                    selectedVoice = voice
                    onDismiss()
                }
            }
            .navigationTitle("Select Voice")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        onDismiss()
                    }
                }
            }
        }
    }
}
