import SwiftUI
import AVFoundation
import Speech

// MARK: - Voice Recording View (Full Screen Overlay)

/// Full-screen voice recording overlay that appears when user starts recording.
/// Shows live transcription, waveform visualization, and security context.
struct VoiceRecordingView: View {
    @Binding var isRecording: Bool
    @Binding var transcription: String
    @Binding var audioLevel: Float
    
    let environment: String
    let onComplete: (String) -> Void
    
    @State private var isListening = true
    @State private var waveformValues: [Float] = Array(repeating: 0.3, count: 20)
    @State private var waveformTimer: Timer?
    @State private var dragOffset: CGFloat = 0
    @State private var showCancelHint = false
    
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        ZStack {
            // Dark background
            Color.black.opacity(0.95)
                .ignoresSafeArea()
            
            VStack(spacing: 40) {
                // Cancel hint at top
                if showCancelHint {
                    HStack {
                        Image(systemName: "chevron.down")
                        Text("Swipe down to cancel")
                    }
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.5))
                    .transition(.opacity)
                }
                
                Spacer()
                
                // Waveform visualization
                WaveformView(levels: waveformValues)
                    .frame(height: 100)
                
                // Live transcription
                VStack(spacing: 16) {
                    Text(transcription.isEmpty ? "Listening..." : transcription)
                        .font(.title2)
                        .fontWeight(.medium)
                        .foregroundColor(.white)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                        .frame(minHeight: 100)
                        .animation(.easeInOut(duration: 0.2), value: transcription)
                    
                    // Listening indicator dots
                    if transcription.isEmpty {
                        ListeningIndicator()
                    }
                }
                
                Spacer()
                
                // Security context bar
                HStack(spacing: 8) {
                    Image(systemName: "lock.fill")
                        .foregroundColor(.green)
                    Text("Encrypted to \(environment)")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(Color.white.opacity(0.1))
                .cornerRadius(20)
                
                Spacer()
                
                // Bottom controls
                VStack(spacing: 24) {
                    // Send button
                    Button {
                        finishRecording()
                    } label: {
                        HStack(spacing: 12) {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.title2)
                            Text(transcription.isEmpty ? "Cancel" : "Send Command")
                                .fontWeight(.semibold)
                        }
                        .foregroundColor(.white)
                        .padding(.horizontal, 32)
                        .padding(.vertical, 16)
                        .background(
                            transcription.isEmpty
                                ? Color.white.opacity(0.2)
                                : Color.cyan
                        )
                        .cornerRadius(30)
                    }
                    .buttonStyle(.plain)
                    
                    // Instructions
                    Text("Tap to send or swipe down to cancel")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))
                }
                .padding(.bottom, 60)
            }
            .offset(y: dragOffset)
        }
        .gesture(
            DragGesture()
                .onChanged { gesture in
                    if gesture.translation.height > 0 {
                        dragOffset = gesture.translation.height
                        showCancelHint = gesture.translation.height > 30
                    }
                }
                .onEnded { gesture in
                    if gesture.translation.height > 100 {
                        // Swipe down to cancel
                        cancelRecording()
                    } else {
                        withAnimation(.spring()) {
                            dragOffset = 0
                            showCancelHint = false
                        }
                    }
                }
        )
        .onAppear {
            startListening()
        }
        .onDisappear {
            stopListening()
        }
    }
    
    // MARK: - Speech Recognition
    
    func startListening() {
        // Start waveform animation
        waveformTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { _ in
            withAnimation(.easeInOut(duration: 0.1)) {
                waveformValues = waveformValues.map { _ in Float.random(in: 0.2...1.0) }
            }
        }
        
        // Request speech recognition authorization
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                switch status {
                case .authorized:
                    startSpeechRecognition()
                case .denied, .restricted, .notDetermined:
                    // Fall back to placeholder
                    break
                @unknown default:
                    break
                }
            }
        }
    }
    
    func startSpeechRecognition() {
        #if os(iOS)
        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")),
              recognizer.isAvailable else {
            return
        }
        
        // Configure audio session
        let audioSession = AVAudioSession.sharedInstance()
        do {
            try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
            try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        } catch {
            print("Audio session setup failed: \(error)")
            return
        }
        
        // Create recognition request
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        
        // Create audio engine
        let audioEngine = AVAudioEngine()
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            request.append(buffer)
            
            // Calculate audio level for visualization
            let channelData = buffer.floatChannelData?[0]
            let frameLength = Int(buffer.frameLength)
            var sum: Float = 0
            for i in 0..<frameLength {
                sum += abs(channelData?[i] ?? 0)
            }
            let avg = sum / Float(frameLength)
            DispatchQueue.main.async {
                self.audioLevel = avg * 10 // Scale for visualization
            }
        }
        
        // Start recognition task
        recognizer.recognitionTask(with: request) { result, error in
            if let result = result {
                DispatchQueue.main.async {
                    self.transcription = result.bestTranscription.formattedString
                }
            }
            
            if error != nil || result?.isFinal == true {
                audioEngine.stop()
                inputNode.removeTap(onBus: 0)
            }
        }
        
        // Start audio engine
        audioEngine.prepare()
        do {
            try audioEngine.start()
        } catch {
            print("Audio engine failed to start: \(error)")
        }
        #endif
    }
    
    func stopListening() {
        waveformTimer?.invalidate()
        waveformTimer = nil
    }
    
    func finishRecording() {
        stopListening()
        
        if !transcription.isEmpty {
            onComplete(transcription)
        }
        
        dismiss()
    }
    
    func cancelRecording() {
        stopListening()
        transcription = ""
        
        withAnimation(.spring()) {
            dragOffset = 0
        }
        
        dismiss()
    }
}

// MARK: - Waveform Visualization

struct WaveformView: View {
    let levels: [Float]
    
    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<levels.count, id: \.self) { index in
                RoundedRectangle(cornerRadius: 2)
                    .fill(
                        LinearGradient(
                            colors: [Color.cyan, Color.blue],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                    .frame(width: 4, height: CGFloat(levels[index]) * 80 + 10)
                    .animation(.easeInOut(duration: 0.1), value: levels[index])
            }
        }
    }
}

// MARK: - Listening Indicator

struct ListeningIndicator: View {
    @State private var animationPhase = 0
    
    var body: some View {
        HStack(spacing: 8) {
            ForEach(0..<3, id: \.self) { index in
                Circle()
                    .fill(Color.cyan)
                    .frame(width: 8, height: 8)
                    .opacity(animationPhase == index ? 1.0 : 0.3)
            }
        }
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.3, repeats: true) { _ in
                withAnimation(.easeInOut(duration: 0.3)) {
                    animationPhase = (animationPhase + 1) % 3
                }
            }
        }
    }
}

// MARK: - Preview

#Preview {
    VoiceRecordingView(
        isRecording: .constant(true),
        transcription: .constant("Fix the bug in the login screen"),
        audioLevel: .constant(0.5),
        environment: "MyProject",
        onComplete: { _ in }
    )
}
