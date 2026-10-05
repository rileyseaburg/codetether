import Foundation
import Combine
import LiveKit
import AVFoundation

enum AgentState: String, Codable {
    case idle = "idle"
    case listening = "listening"
    case thinking = "thinking"
    case speaking = "speaking"
    case error = "error"
}

struct VoiceOption: Identifiable, Codable, Hashable {
    let id: String
    let name: String
    let description: String
    let provider: String?  // Made optional - backend doesn't always provide
    let model: String?     // Made optional - backend doesn't always provide
    let language: String?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case description
        case provider
        case model
        case language
    }
    
    // Provide defaults for display
    var displayProvider: String { provider ?? "Default" }
    var displayModel: String { model ?? "Standard" }
}

struct VoiceSession: Codable {
    let roomName: String
    let accessToken: String?
    let livekitUrl: String
    let voice: String?
    let mode: String?
    let playbackStyle: String?
    let expiresAt: String?
    let sessionId: String?

    enum CodingKeys: String, CodingKey {
        case roomName = "room_name"
        case accessToken = "access_token"
        case livekitUrl = "livekit_url"
        case voice
        case mode
        case playbackStyle = "playback_style"
        case expiresAt = "expires_at"
        case sessionId = "session_id"
    }
}

struct CreateSessionRequest: Codable {
    let codebaseId: String
    let sessionId: String?
    let voiceId: String
    let mode: String
    let playbackStyle: String

    enum CodingKeys: String, CodingKey {
        case codebaseId = "codebase_id"
        case sessionId = "session_id"
        case voiceId = "voice"
        case mode
        case playbackStyle = "playback_style"
    }
}

@MainActor
class VoiceSessionManager: ObservableObject {
    @Published var room: Room?
    @Published var agentState: AgentState = .idle
    @Published var isConnected = false
    @Published var isMuted: Bool = false
    @Published var currentVoice: VoiceOption?
    @Published var voices: [VoiceOption] = []
    @Published var error: String?
    @Published var currentRoomName: String?

    private let baseURL: URL
    private var cancellables = Set<AnyCancellable>()
    private var stateUpdateTask: Task<Void, Never>?
    private var authHeader: String?
    private var userId: String?

    init(baseURL: URL? = nil, authHeader: String? = nil) {
        if let url = baseURL {
            self.baseURL = url
        } else {
            // Safely parse URL from UserDefaults, falling back to default if invalid
            let urlString = UserDefaults.standard.string(forKey: "serverURL") ?? "https://api.codetether.run"
            self.baseURL = URL(string: urlString) ?? URL(string: "https://api.codetether.run")!
        }
        self.authHeader = authHeader
        self.userId = "user-\(UUID().uuidString.prefix(8))"
    }

    func setAuthHeader(_ header: String?) {
        self.authHeader = header
    }

    func startSession(
        codebaseId: String,
        sessionId: String?,
        voice: VoiceOption,
        mode: String = "chat",
        playbackStyle: String = "verbatim"
    ) async throws {
        error = nil
        currentVoice = voice

        #if os(iOS)
        // Check microphone permission (iOS only)
        let status = AVAudioSession.sharedInstance().recordPermission
        switch status {
        case .undetermined:
            let granted = await withCheckedContinuation { continuation in
                AVAudioSession.sharedInstance().requestRecordPermission { granted in
                    continuation.resume(returning: granted)
                }
            }
            if !granted { throw VoiceError.microphonePermissionDenied }
        case .denied:
            throw VoiceError.microphonePermissionDenied
        case .granted:
            break
        @unknown default:
            break
        }

        // Configure audio session (iOS only)
        do {
            let audioSession = AVAudioSession.sharedInstance()
            try audioSession.setCategory(.playAndRecord, mode: .voiceChat, options: [.defaultToSpeaker, .allowBluetooth])
            try audioSession.setActive(true)
        } catch {
            throw VoiceError.audioSessionFailed
        }
        #endif

        let request = CreateSessionRequest(
            codebaseId: codebaseId,
            sessionId: sessionId,
            voiceId: voice.id,
            mode: mode,
            playbackStyle: playbackStyle
        )

        let url = baseURL.appendingPathComponent("/v1/voice/sessions")
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let header = authHeader {
            urlRequest.setValue(header, forHTTPHeaderField: "Authorization")
        }

        urlRequest.httpBody = try JSONEncoder().encode(request)

        let (data, response) = try await URLSession.shared.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse, (200..<300).contains(httpResponse.statusCode) else {
            throw VoiceError.sessionCreationFailed
        }

        let session = try JSONDecoder().decode(VoiceSession.self, from: data)

        guard let accessToken = session.accessToken else {
            throw VoiceError.sessionCreationFailed
        }

        try await connectToLiveKit(url: session.livekitUrl, token: accessToken)

        currentRoomName = session.roomName
        startStateUpdates(roomName: session.roomName)
    }

    func endSession() async {
        stateUpdateTask?.cancel()
        stateUpdateTask = nil

        await disconnectFromLiveKit()

        await MainActor.run {
            self.agentState = .idle
            self.currentVoice = nil
            self.isConnected = false
            self.isMuted = false
            self.currentRoomName = nil
        }
    }
    
    func toggleMute() async {
        guard let room = room else { return }
        do {
            let newState = !isMuted
            try await room.localParticipant.setMicrophone(enabled: !newState)
            await MainActor.run {
                self.isMuted = newState
            }
        } catch {
            print("Failed to toggle mute: \(error)")
        }
    }

    func continueSession(roomName: String, voice: VoiceOption, userId: String? = nil) async throws {
        error = nil
        currentVoice = voice

        let userIdParam = userId ?? self.userId ?? "user-\(UUID().uuidString.prefix(8))"
        let url = baseURL.appendingPathComponent("/v1/voice/sessions/\(roomName)")
        var components = URLComponents(url: url, resolvingAgainstBaseURL: true)!
        components.queryItems = [URLQueryItem(name: "user_id", value: userIdParam)]

        var urlRequest = URLRequest(url: components.url!)

        if let header = authHeader {
            urlRequest.setValue(header, forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await URLSession.shared.data(for: urlRequest)

        guard let httpResponse = response as? HTTPURLResponse, (200..<300).contains(httpResponse.statusCode) else {
            throw VoiceError.sessionCreationFailed
        }

        let sessionInfo = try JSONDecoder().decode(VoiceSession.self, from: data)

        guard let accessToken = sessionInfo.accessToken else {
            throw VoiceError.connectionFailed
        }

        try await connectToLiveKit(url: sessionInfo.livekitUrl, token: accessToken)

        currentRoomName = roomName
        startStateUpdates(roomName: roomName)
    }

    func reconnect() async throws {
        guard let roomName = currentRoomName, let voice = currentVoice else {
            throw VoiceError.reconnectionFailed
        }

        try await continueSession(roomName: roomName, voice: voice, userId: userId)
    }

    func fetchVoices() async -> [VoiceOption] {
        do {
            let url = baseURL.appendingPathComponent("/v1/voice/voices")
            var urlRequest = URLRequest(url: url)

            if let header = authHeader {
                urlRequest.setValue(header, forHTTPHeaderField: "Authorization")
            }

            let (data, _) = try await URLSession.shared.data(for: urlRequest)
            let voiceOptions = try JSONDecoder().decode([VoiceOption].self, from: data)
            voices = voiceOptions
            return voiceOptions
        } catch {
            self.error = error.localizedDescription
            return []
        }
    }

    private func connectToLiveKit(url: String, token: String) async throws {
        let room = Room()
        room.add(delegate: self)

        try await room.connect(url: url, token: token)
        await MainActor.run {
            self.room = room
            self.isConnected = true
        }
    }

    private func disconnectFromLiveKit() async {
        await room?.disconnect()
        await MainActor.run {
            self.room = nil
        }
    }

    private func startStateUpdates(roomName: String) {
        stateUpdateTask = Task {
            var retryCount = 0
            let maxRetries = 3
            
            while !Task.isCancelled {
                do {
                    let url = baseURL.appendingPathComponent("/v1/voice/sessions/\(roomName)/state")
                    var urlRequest = URLRequest(url: url)

                    if let header = authHeader {
                        urlRequest.setValue(header, forHTTPHeaderField: "Authorization")
                    }

                    let (data, _) = try await URLSession.shared.data(for: urlRequest)

                    if let stateString = try? JSONDecoder().decode(String.self, from: data),
                       let state = AgentState(rawValue: stateString) {
                        await MainActor.run {
                            self.agentState = state
                        }
                    }
                    retryCount = 0 // Reset on success
                } catch {
                    retryCount += 1
                    if retryCount >= maxRetries {
                        await MainActor.run {
                            self.error = "Lost connection to voice session"
                            self.agentState = .error
                        }
                        break
                    }
                    // Wait longer before retry
                    try? await Task.sleep(nanoseconds: 2_000_000_000)
                    continue
                }

                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }
        }
    }
}

extension VoiceSessionManager: RoomDelegate {
    nonisolated func room(_ room: Room, didUpdateConnectionState connectionState: ConnectionState, from oldConnectionState: ConnectionState) {
        Task { @MainActor in
            self.isConnected = connectionState == .connected

            if connectionState == .disconnected {
                self.agentState = .idle
                self.error = "Connection lost"
            }
        }
    }
}

enum VoiceError: LocalizedError {
    case microphonePermissionDenied
    case audioSessionFailed
    case sessionCreationFailed
    case connectionFailed
    case reconnectionFailed

    var errorDescription: String? {
        switch self {
        case .microphonePermissionDenied: return "Microphone access denied. Please enable in Settings."
        case .audioSessionFailed: return "Failed to configure audio session."
        case .sessionCreationFailed: return "Failed to create voice session"
        case .connectionFailed: return "Failed to connect to voice service"
        case .reconnectionFailed: return "Failed to reconnect to voice session"
        }
    }
}
