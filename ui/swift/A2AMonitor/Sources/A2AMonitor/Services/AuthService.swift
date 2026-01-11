import Foundation
import Combine
#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

/// Authentication service for Keycloak OIDC integration
/// Manages user sessions, token refresh, and cross-device sync
@MainActor
class AuthService: ObservableObject {
    // MARK: - Published State

    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var isGuestMode = false
    @Published var currentUser: UserSession?
    @Published var syncState: SyncState?
    @Published var error: String?

    // Token state
    @Published private(set) var accessToken: String?
    @Published private(set) var refreshToken: String?
    @Published private(set) var tokenExpiresAt: Date?

    // MARK: - Private

    private var baseURL: URL
    private var session: URLSession
    private var refreshTask: Task<Void, Never>?
    private var cancellables = Set<AnyCancellable>()
    private var isRefreshing = false

    // Keychain keys
    private let accessTokenKey = "a2a_access_token"
    private let refreshTokenKey = "a2a_refresh_token"
    private let userIdKey = "a2a_user_id"
    private let sessionIdKey = "a2a_session_id"

    // MARK: - Device Info

    private var deviceId: String {
        #if os(iOS)
        return UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
        #elseif os(macOS)
        return getMacDeviceId()
        #else
        return UUID().uuidString
        #endif
    }

    private var deviceName: String {
        #if os(iOS)
        return UIDevice.current.name
        #elseif os(macOS)
        return Host.current().localizedName ?? "Mac"
        #else
        return "Unknown Device"
        #endif
    }

    private var deviceType: String {
        #if os(iOS)
        return UIDevice.current.userInterfaceIdiom == .pad ? "ipad" : "ios"
        #elseif os(macOS)
        return "macos"
        #elseif os(tvOS)
        return "tvos"
        #elseif os(watchOS)
        return "watchos"
        #else
        return "unknown"
        #endif
    }

    #if os(macOS)
    private func getMacDeviceId() -> String {
        // Try to get hardware UUID
        let platformExpert = IOServiceGetMatchingService(
            kIOMainPortDefault,
            IOServiceMatching("IOPlatformExpertDevice")
        )

        if platformExpert != 0 {
            if let serialNumberAsCFString = IORegistryEntryCreateCFProperty(
                platformExpert,
                kIOPlatformUUIDKey as CFString,
                kCFAllocatorDefault,
                0
            ) {
                IOObjectRelease(platformExpert)
                return serialNumberAsCFString.takeUnretainedValue() as? String ?? UUID().uuidString
            }
            IOObjectRelease(platformExpert)
        }
        return UUID().uuidString
    }
    #endif

    // MARK: - Init

    init(baseURL: String = "https://api.codetether.run") {
        self.baseURL = URL(string: baseURL)!

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        self.session = URLSession(configuration: config)

        // Try to restore session from keychain
        Task {
            await restoreSession()
        }
    }

    func updateBaseURL(_ url: String) {
        if let newURL = URL(string: url) {
            baseURL = newURL
        }
    }

    // MARK: - Authentication

    /// Login with username and password
    func login(username: String, password: String) async throws {
        isLoading = true
        error = nil

        defer { isLoading = false }

        let url = baseURL.appendingPathComponent("v1/auth/login")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "username": username,
            "password": password,
            "device_id": deviceId,
            "device_name": deviceName,
            "device_type": deviceType
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AuthError.invalidResponse
        }

        if httpResponse.statusCode == 401 {
            throw AuthError.invalidCredentials
        }

        guard httpResponse.statusCode == 200 else {
            if let errorJson = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = errorJson["detail"] as? String {
                throw AuthError.serverError(detail)
            }
            throw AuthError.serverError("Login failed with status \(httpResponse.statusCode)")
        }

        let loginResponse = try JSONDecoder().decode(LoginResponse.self, from: data)

        // Store tokens
        accessToken = loginResponse.accessToken
        refreshToken = loginResponse.refreshToken
        currentUser = loginResponse.session

        // Parse expiration - try with fractional seconds first, then without
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: loginResponse.expiresAt) {
            tokenExpiresAt = date
        } else {
            // Try without fractional seconds
            formatter.formatOptions = [.withInternetDateTime]
            tokenExpiresAt = formatter.date(from: loginResponse.expiresAt)
        }

        // Save to keychain
        saveToKeychain()

        isAuthenticated = true

        // Start token refresh timer
        scheduleTokenRefresh()

        // Load sync state
        await loadSyncState()
    }

    /// Refresh the access token
    func refreshAccessToken() async throws {
        // Prevent concurrent refresh attempts
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }

        guard let refresh = refreshToken else {
            throw AuthError.noRefreshToken
        }

        let url = baseURL.appendingPathComponent("v1/auth/refresh")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["refresh_token": refresh]
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AuthError.invalidResponse
        }

        if httpResponse.statusCode == 401 {
            // Refresh token expired, need to re-login
            await logout()
            throw AuthError.sessionExpired
        }

        guard httpResponse.statusCode == 200 else {
            throw AuthError.serverError("Token refresh failed")
        }

        let refreshResponse = try JSONDecoder().decode(RefreshResponse.self, from: data)

        accessToken = refreshResponse.accessToken
        refreshToken = refreshResponse.refreshToken
        currentUser = refreshResponse.session

        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        tokenExpiresAt = formatter.date(from: refreshResponse.expiresAt)

        saveToKeychain()
        scheduleTokenRefresh()
    }

    /// Logout and clear session
    func logout() async {
        // Call logout endpoint
        if let sessionId = currentUser?.sessionId {
            let url = baseURL.appendingPathComponent("v1/auth/logout")
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            
            // Add authorization header
            if let token = accessToken {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }

            let body = ["session_id": sessionId]
            request.httpBody = try? JSONEncoder().encode(body)

            _ = try? await session.data(for: request)
        }

        // Clear state
        accessToken = nil
        refreshToken = nil
        currentUser = nil
        syncState = nil
        tokenExpiresAt = nil
        isAuthenticated = false
        isGuestMode = false

        // Clear keychain
        clearKeychain()

        // Cancel refresh task
        refreshTask?.cancel()
        refreshTask = nil
    }

    // MARK: - Guest Mode

    /// Enable guest mode (no authentication, local-only)
    func enableGuestMode() {
        isGuestMode = true
        isAuthenticated = true
        currentUser = nil
        syncState = nil
    }

    /// Disable guest mode (return to login screen)
    func disableGuestMode() {
        isGuestMode = false
        isAuthenticated = false
    }

    // MARK: - Sync State

    /// Load synchronized state across all devices
    func loadSyncState() async {
        guard let userId = currentUser?.userId else { return }

        let url = baseURL.appendingPathComponent("v1/auth/sync")
        var components = URLComponents(url: url, resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "user_id", value: userId)]

        var request = URLRequest(url: components.url!)
        if let token = accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        do {
            let (data, response) = try await session.data(for: request)
            
            // Check HTTP status
            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("Sync state request failed with status: \(httpResponse.statusCode)")
                    return
                }
            }
            
            syncState = try JSONDecoder().decode(SyncState.self, from: data)
        } catch {
            print("Failed to load sync state: \(error)")
        }
    }

    /// Get all codebases associated with the current user
    func getUserCodebases() async throws -> [UserCodebaseAssociation] {
        guard let userId = currentUser?.userId else {
            throw AuthError.notAuthenticated
        }

        let url = baseURL.appendingPathComponent("v1/auth/user/\(userId)/codebases")
        var request = URLRequest(url: url)
        if let token = accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode([UserCodebaseAssociation].self, from: data)
    }

    /// Associate a codebase with the current user
    func associateCodebase(codebaseId: String, role: String = "owner") async throws {
        guard let userId = currentUser?.userId else {
            throw AuthError.notAuthenticated
        }

        let url = baseURL.appendingPathComponent("v1/auth/user/\(userId)/codebases")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let body = ["codebase_id": codebaseId, "role": role]
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw AuthError.serverError("Failed to associate codebase")
        }

        // Refresh sync state
        await loadSyncState()
    }

    /// Create an agent session for a codebase
    func createAgentSession(codebaseId: String, agentType: String = "build") async throws -> UserAgentSession {
        guard let userId = currentUser?.userId else {
            throw AuthError.notAuthenticated
        }

        var components = URLComponents(url: baseURL.appendingPathComponent("v1/auth/user/\(userId)/agent-sessions"), resolvingAgainstBaseURL: false)!
        components.queryItems = [
            URLQueryItem(name: "codebase_id", value: codebaseId),
            URLQueryItem(name: "agent_type", value: agentType),
            URLQueryItem(name: "device_id", value: deviceId)
        ]

        var request = URLRequest(url: components.url!)
        request.httpMethod = "POST"
        if let token = accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, _) = try await session.data(for: request)

        struct Response: Codable {
            let success: Bool
            let session: UserAgentSession
        }

        let response = try JSONDecoder().decode(Response.self, from: data)

        // Refresh sync state
        await loadSyncState()

        return response.session
    }

    /// Get all agent sessions for the current user
    func getUserAgentSessions() async throws -> [UserAgentSession] {
        guard let userId = currentUser?.userId else {
            throw AuthError.notAuthenticated
        }

        let url = baseURL.appendingPathComponent("v1/auth/user/\(userId)/agent-sessions")
        var request = URLRequest(url: url)
        if let token = accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode([UserAgentSession].self, from: data)
    }

    // MARK: - Auth Status

    /// Check if authentication service is available
    func checkAuthStatus() async -> AuthStatusResponse? {
        let url = baseURL.appendingPathComponent("v1/auth/status")

        do {
            let (data, _) = try await session.data(from: url)
            return try JSONDecoder().decode(AuthStatusResponse.self, from: data)
        } catch {
            print("Failed to check auth status: \(error)")
            return nil
        }
    }

    // MARK: - Token Management

    /// Get authorization header for API requests
    var authorizationHeader: String? {
        guard let token = accessToken else { return nil }
        return "Bearer \(token)"
    }

    /// Check if token needs refresh (within 60 seconds of expiry)
    var needsRefresh: Bool {
        guard let expires = tokenExpiresAt else {
            // If we have a token but no expiry, assume it needs refresh
            return accessToken != nil
        }
        return Date().addingTimeInterval(60) >= expires
    }

    private func scheduleTokenRefresh() {
        refreshTask?.cancel()

        guard let expires = tokenExpiresAt else { return }

        // Refresh 60 seconds before expiry
        let refreshTime = expires.addingTimeInterval(-60)
        let delay = max(0, refreshTime.timeIntervalSinceNow)

        refreshTask = Task {
            try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))

            guard !Task.isCancelled else { return }

            var retryCount = 0
            let maxRetries = 3

            while retryCount < maxRetries {
                do {
                    try await refreshAccessToken()
                    return // Success, exit
                } catch {
                    retryCount += 1
                    print("Token refresh attempt \(retryCount) failed: \(error)")

                    if retryCount < maxRetries {
                        // Exponential backoff: 2s, 4s, 8s
                        let backoffDelay = pow(2.0, Double(retryCount))
                        try? await Task.sleep(nanoseconds: UInt64(backoffDelay * 1_000_000_000))
                    }
                }
            }

            // Only logout after all retries exhausted
            print("Token refresh failed after \(maxRetries) attempts, logging out")
            await logout()
        }
    }

    // MARK: - Keychain

    private func saveToKeychain() {
        if let access = accessToken {
            KeychainHelper.save(key: accessTokenKey, value: access)
        }
        if let refresh = refreshToken {
            KeychainHelper.save(key: refreshTokenKey, value: refresh)
        }
        if let userId = currentUser?.userId {
            KeychainHelper.save(key: userIdKey, value: userId)
        }
        if let sessionId = currentUser?.sessionId {
            KeychainHelper.save(key: sessionIdKey, value: sessionId)
        }
    }

    private func clearKeychain() {
        KeychainHelper.delete(key: accessTokenKey)
        KeychainHelper.delete(key: refreshTokenKey)
        KeychainHelper.delete(key: userIdKey)
        KeychainHelper.delete(key: sessionIdKey)
    }

    private func restoreSession() async {
        guard let access = KeychainHelper.load(key: accessTokenKey),
              let refresh = KeychainHelper.load(key: refreshTokenKey) else {
            return
        }

        accessToken = access
        refreshToken = refresh

        // Try to refresh the token to verify it's still valid with retries
        var retryCount = 0
        let maxRetries = 3

        while retryCount < maxRetries {
            do {
                try await refreshAccessToken()
                isAuthenticated = true
                await loadSyncState()
                return // Success, exit
            } catch {
                retryCount += 1
                print("Session restore attempt \(retryCount) failed: \(error)")

                if retryCount < maxRetries {
                    // Exponential backoff: 2s, 4s, 8s
                    let backoffDelay = pow(2.0, Double(retryCount))
                    try? await Task.sleep(nanoseconds: UInt64(backoffDelay * 1_000_000_000))
                }
            }
        }

        // Only clear after all retries exhausted
        print("Session restore failed after \(maxRetries) attempts, clearing keychain")
        clearKeychain()
        accessToken = nil
        refreshToken = nil
    }
}

// MARK: - Auth Errors

enum AuthError: LocalizedError {
    case invalidCredentials
    case invalidResponse
    case serverError(String)
    case noRefreshToken
    case sessionExpired
    case notAuthenticated

    var errorDescription: String? {
        switch self {
        case .invalidCredentials:
            return "Invalid username or password"
        case .invalidResponse:
            return "Invalid server response"
        case .serverError(let message):
            return message
        case .noRefreshToken:
            return "No refresh token available"
        case .sessionExpired:
            return "Session expired. Please login again."
        case .notAuthenticated:
            return "Not authenticated"
        }
    }
}

// MARK: - Keychain Helper

struct KeychainHelper {
    @discardableResult
    static func save(key: String, value: String) -> Bool {
        guard let data = value.data(using: .utf8) else {
            print("Keychain save failed for \(key): unable to encode value")
            return false
        }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data
        ]

        let deleteStatus = SecItemDelete(query as CFDictionary)
        if deleteStatus != errSecSuccess && deleteStatus != errSecItemNotFound {
            print("Keychain delete failed for \(key): \(deleteStatus)")
        }

        let addStatus = SecItemAdd(query as CFDictionary, nil)
        if addStatus != errSecSuccess {
            print("Keychain save failed for \(key): \(addStatus)")
            return false
        }
        return true
    }

    static func load(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return nil
        }

        return value
    }

    @discardableResult
    static func delete(key: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key
        ]

        let status = SecItemDelete(query as CFDictionary)
        if status != errSecSuccess && status != errSecItemNotFound {
            print("Keychain delete failed for \(key): \(status)")
            return false
        }
        return true
    }
}
