import Foundation
import Combine
import LiveKit

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
    let provider: String
    let model: String
    let language: String?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case description
        case provider
        case model
        case language
    }
}

struct VoiceSession: Codable {
    let sessionId: String
    let voiceId: String
    let livekitUrl: String
    let livekitToken: String
    let expiresAt: Date?

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case voiceId = "voice_id"
        case livekitUrl = "livekit_url"
        case livekitToken = "livekit_token"
        case expiresAt = "expires_at"
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
        case voiceId = "voice_id"
        case mode
        case playbackStyle = "playback_style"
    }
}

@MainActor
class VoiceSessionManager: ObservableObject {
    @Published var room: Room?
    @Published var agentState: AgentState = .idle
    @Published var isConnected = false
    @Published var currentVoice: VoiceOption?
    @Published var voices: [VoiceOption] = []
    @Published var error: String?

    private let baseURL: URL
    private var cancellables = Set<AnyCancellable>()
    private var stateUpdateTask: Task<Void, Never>?
    private var authHeader: String?

    init(baseURL: URL? = nil, authHeader: String? = nil) {
        if let url = baseURL {
            self.baseURL = url
        } else {
            let urlString = UserDefaults.standard.string(forKey: "serverURL") ?? "https://api.codetether.run"
            self.baseURL = URL(string: urlString)!
        }
        self.authHeader = authHeader
    }

    func setAuthHeader(_ header: String?) {
        self.authHeader = header
    }

    func startSession(
        codebaseId: String,
        sessionId: String?,
        voice: VoiceOption,
        mode: String = "voice",
        playbackStyle: String = "verbatim"
    ) async throws {
        error = nil
        currentVoice = voice

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

        try await connectToLiveKit(url: session.livekitUrl, token: session.livekitToken)

        startStateUpdates(sessionId: session.sessionId)
    }

    func endSession() async {
        stateUpdateTask?.cancel()
        stateUpdateTask = nil

        await disconnectFromLiveKit()

        agentState = .idle
        currentVoice = nil
        isConnected = false
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
        let lkURL = URL(string: url)!
        let connectOptions = ConnectOptions(
            name: "A2A Voice Chat",
            autoSubscribe: .subscribed
        )

        let rtcConfig = RTCConfiguration()
        rtcConfig.iceServers = [RTCIceServer(urlStrings: ["stun:stun.l.google.com:19302"])]

        let room = Room(
            RTCConfiguration: rtcConfig,
            delegate: self
        )

        try await room.connect(url: lkURL, token: token, connectOptions: connectOptions)
        self.room = room
        isConnected = true
    }

    private func disconnectFromLiveKit() async {
        await room?.disconnect()
        room = nil
    }

    private func startStateUpdates(sessionId: String) {
        stateUpdateTask = Task {
            while !Task.isCancelled {
                do {
                    let url = baseURL.appendingPathComponent("/v1/voice/sessions/\(sessionId)/state")
                    var urlRequest = URLRequest(url: url)

                    if let header = authHeader {
                        urlRequest.setValue(header, forHTTPHeaderField: "Authorization")
                    }

                    let (data, _) = try await URLSession.shared.data(for: urlRequest)

                    if let stateString = try? JSONDecoder().decode(String.self, from: data),
                       let state = AgentState(rawValue: stateString) {
                        agentState = state
                    }
                } catch {
                    break
                }

                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }
        }
    }
}

extension VoiceSessionManager: RoomDelegate {
    func room(_ room: Room, didUpdateConnectionState state: ConnectionState, reason: DisconnectReason?) {
        Task { @MainActor in
            self.isConnected = room.connectionState == .connected
        }
    }
}

enum VoiceError: LocalizedError {
    case sessionCreationFailed
    case connectionFailed

    var errorDescription: String? {
        switch self {
        case .sessionCreationFailed: return "Failed to create voice session"
        case .connectionFailed: return "Failed to connect to voice service"
        }
    }
}
