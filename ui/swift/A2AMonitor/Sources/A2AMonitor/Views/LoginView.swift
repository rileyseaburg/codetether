import SwiftUI

/// Login view with Liquid Glass styling for Keycloak authentication
/// Supports both authenticated and guest mode
struct LoginView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var viewModel: MonitorViewModel

    @State private var username = ""
    @State private var password = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showError = false
    @State private var rememberMe = true

    @AppStorage("serverURL") private var serverURL = "https://api.codetether.run"
    @AppStorage("lastUsername") private var lastUsername = ""
    @State private var showServerSettings = false

    var body: some View {
        ZStack {
            LiquidGradientBackground()

            ScrollView {
                VStack(spacing: 0) {
                    Spacer(minLength: 60)
                    logoSection
                    loginFormCard
                    Spacer(minLength: 40)
                    serverButton
                }
            }
        }
        .alert("Login Failed", isPresented: $showError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage ?? "Unknown error")
        }
        .sheet(isPresented: $showServerSettings) {
            ServerSettingsSheet(serverURL: $serverURL)
        }
        .onAppear {
            if !lastUsername.isEmpty && rememberMe {
                username = lastUsername
            }
        }
    }

    // MARK: - Logo Section

    private var logoSection: some View {
        VStack(spacing: 16) {
            Image(systemName: "cpu.fill")
                .font(.system(size: 64))
                .foregroundColor(.cyan)
                .shadow(color: .cyan.opacity(0.5), radius: 20)

            Text("A2A Monitor")
                .font(.largeTitle)
                .fontWeight(.bold)
                .foregroundColor(.white)

            Text("Agent Conversation Auditing & Control")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.7))
        }
        .padding(.bottom, 40)
    }

    // MARK: - Login Form Card

    private var loginFormCard: some View {
        VStack(spacing: 20) {
            emailField
            passwordField
            rememberMeToggle
            signInButton
            dividerView
            guestButton
            guestModeNote
        }
        .padding(28)
        .background(loginCardBackground)
        .padding(.horizontal, 24)
        .frame(maxWidth: 420)
    }

    private var loginCardBackground: some View {
        RoundedRectangle(cornerRadius: 24)
            .fill(Color.black.opacity(0.4))
            .overlay(
                RoundedRectangle(cornerRadius: 24)
                    .stroke(Color.white.opacity(0.2), lineWidth: 1)
            )
    }

    // MARK: - Email Field

    private var emailField: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Email")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.white.opacity(0.8))

            HStack(spacing: 12) {
                Image(systemName: "envelope.fill")
                    .foregroundColor(.white.opacity(0.6))
                    .frame(width: 20)
                TextField("email@example.com", text: $username)
                    .foregroundColor(.white)
                    .textContentType(.emailAddress)
                    #if os(iOS)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                    #endif
                    .disableAutocorrection(true)
            }
            .padding()
            .background(Color.white.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.white.opacity(0.3), lineWidth: 1)
            )
        }
    }

    // MARK: - Password Field

    private var passwordField: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Password")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.white.opacity(0.8))

            HStack(spacing: 12) {
                Image(systemName: "lock.fill")
                    .foregroundColor(.white.opacity(0.6))
                    .frame(width: 20)
                SecureField("Password", text: $password)
                    .foregroundColor(.white)
                    .textContentType(.password)
                    .onSubmit {
                        if !username.isEmpty && !password.isEmpty {
                            login()
                        }
                    }
            }
            .padding()
            .background(Color.white.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.white.opacity(0.3), lineWidth: 1)
            )
        }
    }

    // MARK: - Remember Me Toggle

    private var rememberMeToggle: some View {
        HStack {
            Toggle(isOn: $rememberMe) {
                Text("Remember me")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.8))
            }
            .toggleStyle(SwitchToggleStyle(tint: .cyan))
        }
    }

    // MARK: - Sign In Button

    private var signInButton: some View {
        Button(action: login) {
            HStack(spacing: 8) {
                if isLoading {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(0.8)
                } else {
                    Image(systemName: "arrow.right.circle.fill")
                    Text("Sign In")
                        .fontWeight(.bold)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(signInButtonBackground)
            .foregroundColor(.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .disabled(username.isEmpty || password.isEmpty || isLoading)
    }

    private var signInButtonBackground: some View {
        Group {
            if username.isEmpty || password.isEmpty {
                Color.white.opacity(0.2)
            } else {
                LinearGradient(
                    colors: [.cyan, .blue],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            }
        }
    }

    // MARK: - Divider

    private var dividerView: some View {
        HStack(spacing: 16) {
            Rectangle()
                .fill(Color.white.opacity(0.3))
                .frame(height: 1)
            Text("or")
                .font(.caption)
                .fontWeight(.medium)
                .foregroundColor(.white.opacity(0.6))
            Rectangle()
                .fill(Color.white.opacity(0.3))
                .frame(height: 1)
        }
    }

    // MARK: - Guest Button

    private var guestButton: some View {
        Button(action: continueAsGuest) {
            HStack(spacing: 8) {
                Image(systemName: "person.badge.clock.fill")
                Text("Continue as Guest")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.white.opacity(0.15))
            .foregroundColor(.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.white.opacity(0.3), lineWidth: 1)
            )
        }
    }

    private var guestModeNote: some View {
        Text("Guest mode won't sync across devices")
            .font(.caption)
            .foregroundColor(.white.opacity(0.5))
            .multilineTextAlignment(.center)
    }

    // MARK: - Server Button

    private var serverButton: some View {
        Button(action: { showServerSettings = true }) {
            HStack(spacing: 8) {
                Image(systemName: "server.rack")
                    .font(.caption)
                Text(cleanServerURL(serverURL))
                    .lineLimit(1)
            }
            .font(.subheadline)
            .fontWeight(.medium)
            .foregroundColor(.white.opacity(0.7))
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color.white.opacity(0.15))
            .clipShape(Capsule())
        }
        .padding(.bottom, 32)
    }

    // MARK: - Helpers

    private func cleanServerURL(_ url: String) -> String {
        url.replacingOccurrences(of: "http://", with: "")
           .replacingOccurrences(of: "https://", with: "")
    }

    private func login() {
        isLoading = true
        errorMessage = nil
        authService.updateBaseURL(serverURL)

        if rememberMe {
            lastUsername = username
        }

        Task {
            do {
                try await authService.login(username: username, password: password)
            } catch let error as AuthError {
                errorMessage = error.errorDescription
                showError = true
            } catch {
                errorMessage = error.localizedDescription
                showError = true
            }
            isLoading = false
        }
    }

    private func continueAsGuest() {
        authService.enableGuestMode()
        viewModel.updateServerURL(serverURL)
    }
}

// MARK: - Server Settings Sheet

struct ServerSettingsSheet: View {
    @Binding var serverURL: String
    @Environment(\.dismiss) private var dismiss
    @State private var tempURL: String = ""
    @State private var isChecking = false
    @State private var connectionStatus: ConnectionStatus = .unknown

    enum ConnectionStatus {
        case unknown, checking
        case success(String)
        case failure(String)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                LiquidGradientBackground()

                ScrollView {
                    VStack(spacing: 24) {
                        headerSection
                        urlInputSection
                        connectionStatusView
                        presetsSection
                        Spacer(minLength: 40)
                        actionButtons
                    }
                    .padding(24)
                }
            }
            .navigationTitle("Server")
            #if os(iOS)
            .navigationBarTitleDisplayModeInline()
            .toolbarBackground(.hidden, for: .navigationBar)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(.white)
                }
            }
            .onAppear {
                tempURL = serverURL
            }
        }
        #if os(macOS)
        .frame(minWidth: 450, minHeight: 500)
        #endif
    }

    private var headerSection: some View {
        VStack(spacing: 12) {
            Image(systemName: "server.rack")
                .font(.system(size: 48))
                .foregroundColor(.cyan)
                .shadow(color: .cyan.opacity(0.5), radius: 15)

            Text("Server Configuration")
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(.white)
        }
        .padding(.top, 20)
    }

    private var urlInputSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Server URL")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.white.opacity(0.8))

            HStack {
                TextField("https://api.codetether.run", text: $tempURL)
                    .foregroundColor(.white)
                    #if os(iOS)
                    .keyboardType(.URL)
                    .autocapitalization(.none)
                    #endif
                    .disableAutocorrection(true)
                    .onSubmit { checkConnection() }

                if case .checking = connectionStatus {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(0.8)
                }
            }
            .padding()
            .background(Color.white.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.white.opacity(0.3), lineWidth: 1)
            )
        }
    }

    @ViewBuilder
    private var connectionStatusView: some View {
        switch connectionStatus {
        case .unknown:
            EmptyView()
        case .checking:
            statusRow(icon: "antenna.radiowaves.left.and.right", text: "Checking...", color: .white)
        case .success(let message):
            statusRow(icon: "checkmark.circle.fill", text: message, color: .green)
        case .failure(let message):
            statusRow(icon: "xmark.circle.fill", text: message, color: .red)
        }
    }

    private func statusRow(icon: String, text: String, color: Color) -> some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(color)
            Text(text)
                .font(.subheadline)
                .foregroundColor(.white)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(color.opacity(0.2))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var presetsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quick Presets")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.white.opacity(0.8))

            HStack(spacing: 10) {
                PresetButton(title: "Local", icon: "laptopcomputer") {
                    tempURL = "http://localhost:8000"
                }
                PresetButton(title: "Docker", icon: "shippingbox") {
                    tempURL = "http://localhost:9000"
                }
                PresetButton(title: "CodeTether", icon: "cloud") {
                    tempURL = "https://api.codetether.run"
                }
            }
        }
    }

    private var actionButtons: some View {
        VStack(spacing: 12) {
            Button(action: checkConnection) {
                HStack {
                    Image(systemName: "antenna.radiowaves.left.and.right")
                    Text("Test Connection")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color.white.opacity(0.15))
                .foregroundColor(.white)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .disabled(tempURL.isEmpty || isChecking)

            Button(action: saveAndDismiss) {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                    Text("Save")
                        .fontWeight(.bold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(
                    LinearGradient(colors: [.cyan, .blue], startPoint: .leading, endPoint: .trailing)
                )
                .foregroundColor(.white)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .disabled(tempURL.isEmpty)
        }
    }

    private func saveAndDismiss() {
        serverURL = tempURL
        dismiss()
    }

    private func checkConnection() {
        connectionStatus = .checking
        isChecking = true

        Task {
            let service = AuthService(baseURL: tempURL)
            if let status = await service.checkAuthStatus() {
                if status.available {
                    connectionStatus = .success("Connected to \(status.realm ?? "server")")
                } else {
                    connectionStatus = .failure(status.message)
                }
            } else {
                await checkBasicHealth()
            }
            isChecking = false
        }
    }

    private func checkBasicHealth() async {
        guard let url = URL(string: tempURL)?.appendingPathComponent("/health") else {
            connectionStatus = .failure("Invalid URL")
            return
        }

        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                connectionStatus = .success("Server is healthy")
            } else {
                connectionStatus = .failure("Server returned error")
            }
        } catch {
            connectionStatus = .failure("Cannot connect to server")
        }
    }
}

// MARK: - Preset Button

struct PresetButton: View {
    let title: String
    let icon: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                Text(title)
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.white.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.white.opacity(0.2), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Sync Status View

struct SyncStatusView: View {
    @EnvironmentObject var authService: AuthService

    var body: some View {
        if let syncState = authService.syncState {
            VStack(alignment: .leading, spacing: 16) {
                syncHeader(activeDevices: syncState.activeDevices)

                Divider().background(Color.white.opacity(0.2))

                if !syncState.sessions.isEmpty {
                    sessionsSection(sessions: syncState.sessions)
                }

                if !syncState.codebases.isEmpty {
                    Divider().background(Color.white.opacity(0.2))
                    codebasesSection(codebases: syncState.codebases)
                }
            }
            .padding()
            .background(Color.white.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(Color.white.opacity(0.2), lineWidth: 1)
            )
        }
    }

    private func syncHeader(activeDevices: Int) -> some View {
        HStack {
            Image(systemName: "arrow.triangle.2.circlepath.circle.fill")
                .font(.title2)
                .foregroundColor(.cyan)

            VStack(alignment: .leading, spacing: 2) {
                Text("Synced Across Devices")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                Text("\(activeDevices) active device\(activeDevices == 1 ? "" : "s")")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
            }

            Spacer()
        }
    }

    private func sessionsSection(sessions: [UserSession]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(sessions) { session in
                sessionRow(session: session)
            }
        }
    }

    private func sessionRow(session: UserSession) -> some View {
        HStack(spacing: 12) {
            Image(systemName: deviceIcon(for: session.deviceInfo.deviceType))
                .font(.title3)
                .foregroundColor(.white.opacity(0.6))
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                Text(session.deviceInfo.deviceName ?? "Unknown Device")
                    .font(.subheadline)
                    .foregroundColor(.white)
                Text(session.deviceInfo.deviceType ?? "unknown")
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.5))
            }

            Spacer()

            if session.sessionId == authService.currentUser?.sessionId {
                Text("This device")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.green)
                    .clipShape(Capsule())
            }
        }
    }

    private func codebasesSection(codebases: [UserCodebaseAssociation]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Your Codebases")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.white.opacity(0.7))

            ForEach(codebases) { codebase in
                codebaseRow(codebase: codebase)
            }
        }
    }

    private func codebaseRow(codebase: UserCodebaseAssociation) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "folder.fill")
                .foregroundColor(.cyan)
            Text(codebase.codebaseName)
                .font(.subheadline)
                .foregroundColor(.white)
            Spacer()
            Text(codebase.role)
                .font(.caption)
                .foregroundColor(.white.opacity(0.6))
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(Color.white.opacity(0.15))
                .clipShape(Capsule())
        }
    }

    private func deviceIcon(for type: String?) -> String {
        switch type {
        case "ios": return "iphone"
        case "ipad": return "ipad"
        case "macos": return "laptopcomputer"
        case "linux": return "desktopcomputer"
        case "web": return "globe"
        default: return "desktopcomputer"
        }
    }
}

// MARK: - User Profile Button

struct UserProfileButton: View {
    @EnvironmentObject var authService: AuthService
    @State private var showingProfile = false

    var body: some View {
        Button(action: { showingProfile = true }) {
            profileContent
        }
        .sheet(isPresented: $showingProfile) {
            UserProfileSheet()
        }
    }

    @ViewBuilder
    private var profileContent: some View {
        if authService.isGuestMode {
            guestProfileContent
        } else if let user = authService.currentUser {
            userProfileContent(user: user)
        } else {
            Image(systemName: "person.circle.fill")
                .font(.title3)
                .foregroundColor(.white)
        }
    }

    private var guestProfileContent: some View {
        HStack(spacing: 8) {
            Image(systemName: "person.badge.clock.fill")
                .font(.title3)
            Text("Guest")
                .font(.caption)
                .fontWeight(.medium)
        }
        .foregroundColor(.white)
    }

    private func userProfileContent(user: UserSession) -> some View {
        HStack(spacing: 8) {
            ZStack {
                Circle()
                    .fill(LinearGradient(colors: [.cyan, .blue], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 28, height: 28)

                Text(initials(for: user.displayName))
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
            }

            Text(user.displayName)
                .font(.caption)
                .fontWeight(.medium)
                .lineLimit(1)
                .foregroundColor(.white)
        }
    }

    private func initials(for name: String) -> String {
        let parts = name.split(separator: " ")
        if parts.count >= 2 {
            return String(parts[0].prefix(1) + parts[1].prefix(1)).uppercased()
        }
        return String(name.prefix(2)).uppercased()
    }
}

// MARK: - User Profile Sheet

struct UserProfileSheet: View {
    @EnvironmentObject var authService: AuthService
    @Environment(\.dismiss) private var dismiss

    @AppStorage("notificationsEnabled") private var notificationsEnabled: Bool = true
    @AppStorage("notificationsAgentOnly") private var notificationsAgentOnly: Bool = true

    var body: some View {
        NavigationStack {
            ZStack {
                LiquidGradientBackground()

                ScrollView {
                    VStack(spacing: 24) {
                        profileHeader

                        if !authService.isGuestMode {
                            SyncStatusView()
                                .padding(.horizontal)
                        }

                        notificationsSection

                        actionSection
                    }
                }
            }
            .navigationTitle("Profile")
            #if os(iOS)
            .navigationBarTitleDisplayModeInline()
            .toolbarBackground(.hidden, for: .navigationBar)
            #endif
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                        .foregroundColor(.white)
                }
            }
        }
        #if os(macOS)
        .frame(minWidth: 400, minHeight: 500)
        #endif
    }

    @ViewBuilder
    private var profileHeader: some View {
        if let user = authService.currentUser {
            authenticatedHeader(user: user)
        } else if authService.isGuestMode {
            guestHeader
        }
    }

    private func authenticatedHeader(user: UserSession) -> some View {
        VStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(LinearGradient(colors: [.cyan, .blue], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 80, height: 80)
                    .shadow(color: .cyan.opacity(0.5), radius: 15)

                Text(initials(for: user.displayName))
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
            }

            Text(user.displayName)
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(.white)

            Text(user.email)
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.7))

            HStack(spacing: 8) {
                ForEach(user.roles.prefix(3), id: \.self) { role in
                    RoleBadge(role: role)
                }
            }
        }
        .padding(.top, 30)
    }

    private var guestHeader: some View {
        VStack(spacing: 12) {
            Image(systemName: "person.badge.clock.fill")
                .font(.system(size: 60))
                .foregroundColor(.white.opacity(0.7))
                .shadow(color: .cyan.opacity(0.3), radius: 10)

            Text("Guest Mode")
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(.white)

            Text("Sign in to sync across devices")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.6))
        }
        .padding(.top, 30)
    }

    private var actionSection: some View {
        VStack(spacing: 12) {
            if authService.isGuestMode {
                signInButton
            } else {
                signOutButton
            }
        }
        .padding(.horizontal)
        .padding(.bottom, 30)
    }

    private var notificationsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: "bell.badge.fill")
                    .foregroundColor(.cyan)
                Text("Notifications")
                    .font(.headline)
                    .foregroundColor(.white)
                Spacer()
            }

            VStack(spacing: 10) {
                Toggle(isOn: $notificationsEnabled) {
                    Text("Alert on agent messages")
                        .foregroundColor(.white)
                }
                .tint(.cyan)
                .onChange(of: notificationsEnabled) { _, newValue in
                    guard newValue else { return }
                    Task {
                        await NotificationService.shared.requestAuthorizationIfNeeded()
                    }
                }

                Toggle(isOn: $notificationsAgentOnly) {
                    Text("Agent-only (ignore system/tool)")
                        .foregroundColor(.white)
                }
                .tint(.cyan)
                .disabled(!notificationsEnabled)

                Button {
                    Task {
                        await NotificationService.shared.requestAuthorizationIfNeeded()
                        await MainActor.run {
                            NotificationService.shared.sendTestNotification()
                        }
                    }
                } label: {
                    HStack {
                        Image(systemName: "bell")
                        Text("Test notification")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(Color.white.opacity(0.12))
                    .foregroundColor(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .disabled(!notificationsEnabled)
            }
            .padding(14)
            .background(Color.white.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
        .padding(.horizontal)
    }

    private var signInButton: some View {
        Button {
            authService.disableGuestMode()
            dismiss()
        } label: {
            HStack {
                Image(systemName: "person.badge.key.fill")
                Text("Sign In")
                    .fontWeight(.bold)
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(LinearGradient(colors: [.cyan, .blue], startPoint: .leading, endPoint: .trailing))
            .foregroundColor(.white)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }

    private var signOutButton: some View {
        Button {
            Task {
                await authService.logout()
                dismiss()
            }
        } label: {
            HStack {
                Image(systemName: "rectangle.portrait.and.arrow.right.fill")
                Text("Sign Out")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(Color.red.opacity(0.2))
            .foregroundColor(.red)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }

    private func initials(for name: String) -> String {
        let parts = name.split(separator: " ")
        if parts.count >= 2 {
            return String(parts[0].prefix(1) + parts[1].prefix(1)).uppercased()
        }
        return String(name.prefix(2)).uppercased()
    }
}

// MARK: - Role Badge

struct RoleBadge: View {
    let role: String

    private var color: Color {
        if role.contains("admin") { return .orange }
        if role.contains("user") { return .cyan }
        return .white.opacity(0.6)
    }

    private var icon: String {
        if role.contains("admin") { return "shield.fill" }
        if role.contains("user") { return "person.fill" }
        return "key.fill"
    }

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.caption2)
            Text(role.replacingOccurrences(of: "a2a-", with: ""))
                .font(.caption2)
                .fontWeight(.medium)
        }
        .foregroundColor(color)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(color.opacity(0.2))
        .clipShape(Capsule())
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthService())
        .environmentObject(MonitorViewModel())
}
