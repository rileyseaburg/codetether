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
    
    @AppStorage("serverURL") private var serverURL = "http://localhost:8000"
    @AppStorage("lastUsername") private var lastUsername = ""
    @State private var showServerSettings = false
    
    var body: some View {
        ZStack {
            // Background
            LiquidGradientBackground()
            
            VStack(spacing: 0) {
                Spacer()
                
                // Logo and Title
                VStack(spacing: 16) {
                    Image(systemName: "cpu.fill")
                        .font(.system(size: 64))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [.blue, .purple],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .shadow(color: .blue.opacity(0.3), radius: 20)
                    
                    Text("A2A Monitor")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    Text("Agent Conversation Auditing & Control")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.bottom, 40)
                
                // Login Form Card
                VStack(spacing: 24) {
                    // Email field
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Email")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(.secondary)
                        
                        HStack(spacing: 12) {
                            Image(systemName: "envelope")
                                .foregroundColor(.secondary)
                                .frame(width: 20)
                            TextField("email@example.com", text: $username)
                                .textContentType(.emailAddress)
                                #if os(iOS)
                                .keyboardType(.emailAddress)
                                .autocapitalization(.none)
                                #endif
                                .disableAutocorrection(true)
                                .submitLabel(.next)
                        }
                        .padding()
                        .background(.ultraThinMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.white.opacity(0.1), lineWidth: 1)
                        )
                    }
                    
                    // Password field
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Password")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(.secondary)
                        
                        HStack(spacing: 12) {
                            Image(systemName: "lock")
                                .foregroundColor(.secondary)
                                .frame(width: 20)
                            SecureField("Password", text: $password)
                                .textContentType(.password)
                                .submitLabel(.go)
                                .onSubmit {
                                    if !username.isEmpty && !password.isEmpty {
                                        login()
                                    }
                                }
                        }
                        .padding()
                        .background(.ultraThinMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.white.opacity(0.1), lineWidth: 1)
                        )
                    }
                    
                    // Remember me toggle
                    Toggle(isOn: $rememberMe) {
                        Text("Remember me")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .toggleStyle(SwitchToggleStyle(tint: .blue))
                    
                    // Login Button
                    Button(action: login) {
                        HStack(spacing: 8) {
                            if isLoading {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                    .scaleEffect(0.8)
                            } else {
                                Image(systemName: "arrow.right.circle.fill")
                                Text("Sign In")
                                    .fontWeight(.semibold)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(
                            LinearGradient(
                                colors: (username.isEmpty || password.isEmpty) ? [.gray, .gray.opacity(0.8)] : [.blue, .purple],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .foregroundColor(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .shadow(color: .blue.opacity(0.3), radius: 10, y: 5)
                    }
                    .disabled(username.isEmpty || password.isEmpty || isLoading)
                    
                    // Divider
                    HStack {
                        Rectangle()
                            .fill(Color.white.opacity(0.2))
                            .frame(height: 1)
                        Text("or")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        Rectangle()
                            .fill(Color.white.opacity(0.2))
                            .frame(height: 1)
                    }
                    
                    // Continue without login
                    Button(action: continueAsGuest) {
                        HStack(spacing: 8) {
                            Image(systemName: "person.badge.clock")
                            Text("Continue as Guest")
                                .fontWeight(.medium)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(.ultraThinMaterial)
                        .foregroundColor(.primary)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .stroke(Color.white.opacity(0.2), lineWidth: 1)
                        )
                    }
                    
                    Text("Guest mode works without authentication but won't sync across devices")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(24)
                .background(.ultraThinMaterial.opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: 24))
                .padding(.horizontal, 24)
                .frame(maxWidth: 420)
                
                Spacer()
                
                // Server Settings
                Button(action: { showServerSettings = true }) {
                    HStack(spacing: 6) {
                        Image(systemName: "server.rack")
                            .font(.caption2)
                        Text(cleanServerURL(serverURL))
                            .lineLimit(1)
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(.ultraThinMaterial.opacity(0.5))
                    .clipShape(Capsule())
                }
                .padding(.bottom, 24)
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
    
    private func cleanServerURL(_ url: String) -> String {
        url.replacingOccurrences(of: "http://", with: "")
           .replacingOccurrences(of: "https://", with: "")
    }
    
    private func login() {
        isLoading = true
        errorMessage = nil
        
        // Update auth service base URL
        authService.updateBaseURL(serverURL)
        
        // Save username if remember me
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
        // Set guest mode - bypass auth but still use the server
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
        case unknown
        case checking
        case success(String)
        case failure(String)
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // Icon
                Image(systemName: "server.rack")
                    .font(.system(size: 48))
                    .foregroundStyle(
                        LinearGradient(colors: [.blue, .purple], startPoint: .top, endPoint: .bottom)
                    )
                    .padding(.top, 20)
                
                Text("Server Configuration")
                    .font(.title2)
                    .fontWeight(.bold)
                
                // URL Input
                VStack(alignment: .leading, spacing: 8) {
                    Text("Server URL")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.secondary)
                    
                    HStack {
                        TextField("http://localhost:8000", text: $tempURL)
                            #if os(iOS)
                            .keyboardType(.URL)
                            .autocapitalization(.none)
                            #endif
                            .disableAutocorrection(true)
                            .onSubmit { checkConnection() }
                        
                        if case .checking = connectionStatus {
                            ProgressView()
                                .scaleEffect(0.8)
                        }
                    }
                    .padding()
                    .background(.ultraThinMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .padding(.horizontal)
                
                // Connection Status
                connectionStatusView
                    .padding(.horizontal)
                
                // Quick presets
                VStack(alignment: .leading, spacing: 8) {
                    Text("Quick Presets")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundColor(.secondary)
                    
                    HStack(spacing: 8) {
                        PresetButton(title: "Local", url: "http://localhost:8000") {
                            tempURL = "http://localhost:8000"
                        }
                        PresetButton(title: "Docker", url: "http://localhost:9000") {
                            tempURL = "http://localhost:9000"
                        }
                        PresetButton(title: "Quantum Forge", url: "https://a2a.quantum-forge.net") {
                            tempURL = "https://a2a.quantum-forge.net"
                        }
                    }
                }
                .padding(.horizontal)
                
                Spacer()
                
                // Actions
                HStack(spacing: 16) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .buttonStyle(.bordered)
                    
                    Button("Test Connection") {
                        checkConnection()
                    }
                    .buttonStyle(.bordered)
                    .disabled(tempURL.isEmpty || isChecking)
                    
                    Button("Save") {
                        serverURL = tempURL
                        dismiss()
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(tempURL.isEmpty)
                }
                .padding()
            }
            .navigationTitle("Server Settings")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
            .onAppear {
                tempURL = serverURL
            }
        }
        #if os(macOS)
        .frame(minWidth: 450, minHeight: 400)
        #endif
    }
    
    @ViewBuilder
    var connectionStatusView: some View {
        switch connectionStatus {
        case .unknown:
            EmptyView()
        case .checking:
            HStack {
                ProgressView()
                    .scaleEffect(0.8)
                Text("Checking connection...")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        case .success(let message):
            HStack {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
                Text(message)
                    .font(.caption)
                    .foregroundColor(.green)
            }
            .padding()
            .background(Color.green.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 8))
        case .failure(let message):
            HStack {
                Image(systemName: "xmark.circle.fill")
                    .foregroundColor(.red)
                Text(message)
                    .font(.caption)
                    .foregroundColor(.red)
            }
            .padding()
            .background(Color.red.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
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
                // Try basic health check
                do {
                    let url = URL(string: tempURL)!.appendingPathComponent("/health")
                    let (_, response) = try await URLSession.shared.data(from: url)
                    if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                        connectionStatus = .success("Server is healthy (no auth)")
                    } else {
                        connectionStatus = .failure("Server returned error")
                    }
                } catch {
                    connectionStatus = .failure("Cannot connect to server")
                }
            }
            isChecking = false
        }
    }
}

struct PresetButton: View {
    let title: String
    let url: String
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.caption)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(.ultraThinMaterial)
                .clipShape(Capsule())
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
                // Header
                HStack {
                    Image(systemName: "arrow.triangle.2.circlepath.circle.fill")
                        .font(.title2)
                        .foregroundColor(.blue)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Synced Across Devices")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                        Text("\(syncState.activeDevices) active device\(syncState.activeDevices == 1 ? "" : "s")")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                }
                
                Divider()
                
                // Devices
                if !syncState.sessions.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(syncState.sessions) { session in
                            HStack(spacing: 12) {
                                Image(systemName: deviceIcon(for: session.deviceInfo.deviceType))
                                    .font(.title3)
                                    .foregroundColor(.secondary)
                                    .frame(width: 24)
                                
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(session.deviceInfo.deviceName ?? "Unknown Device")
                                        .font(.subheadline)
                                    Text(session.deviceInfo.deviceType ?? "unknown")
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                                
                                Spacer()
                                
                                if session.sessionId == authService.currentUser?.sessionId {
                                    Text("This device")
                                        .font(.caption2)
                                        .foregroundColor(.white)
                                        .padding(.horizontal, 8)
                                        .padding(.vertical, 4)
                                        .background(Color.green)
                                        .clipShape(Capsule())
                                }
                            }
                        }
                    }
                }
                
                // Codebases
                if !syncState.codebases.isEmpty {
                    Divider()
                    
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Your Codebases")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(.secondary)
                        
                        ForEach(syncState.codebases) { codebase in
                            HStack(spacing: 10) {
                                Image(systemName: "folder.fill")
                                    .foregroundColor(.blue)
                                Text(codebase.codebaseName)
                                    .font(.subheadline)
                                Spacer()
                                Text(codebase.role)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 2)
                                    .background(Color.gray.opacity(0.2))
                                    .clipShape(Capsule())
                            }
                        }
                    }
                }
            }
            .padding()
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 16))
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
            HStack(spacing: 8) {
                if authService.isGuestMode {
                    Image(systemName: "person.badge.clock")
                        .font(.title3)
                    Text("Guest")
                        .font(.caption)
                } else if let user = authService.currentUser {
                    // Avatar with initials
                    ZStack {
                        Circle()
                            .fill(
                                LinearGradient(colors: [.blue, .purple], startPoint: .topLeading, endPoint: .bottomTrailing)
                            )
                            .frame(width: 28, height: 28)
                        
                        Text(initials(for: user.displayName))
                            .font(.caption2)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                    }
                    
                    Text(user.displayName)
                        .font(.caption)
                        .lineLimit(1)
                } else {
                    Image(systemName: "person.circle")
                        .font(.title3)
                }
            }
            .foregroundColor(.primary)
        }
        .sheet(isPresented: $showingProfile) {
            UserProfileSheet()
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
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Profile Header
                    if let user = authService.currentUser {
                        VStack(spacing: 12) {
                            // Avatar
                            ZStack {
                                Circle()
                                    .fill(
                                        LinearGradient(colors: [.blue, .purple], startPoint: .topLeading, endPoint: .bottomTrailing)
                                    )
                                    .frame(width: 80, height: 80)
                                
                                Text(initials(for: user.displayName))
                                    .font(.title)
                                    .fontWeight(.bold)
                                    .foregroundColor(.white)
                            }
                            
                            Text(user.displayName)
                                .font(.title2)
                                .fontWeight(.bold)
                            
                            Text(user.email)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                            
                            // Role badges
                            HStack(spacing: 8) {
                                ForEach(user.roles.prefix(3), id: \.self) { role in
                                    RoleBadge(role: role)
                                }
                            }
                        }
                        .padding(.top, 20)
                    } else if authService.isGuestMode {
                        VStack(spacing: 12) {
                            Image(systemName: "person.badge.clock.fill")
                                .font(.system(size: 60))
                                .foregroundColor(.secondary)
                            
                            Text("Guest Mode")
                                .font(.title2)
                                .fontWeight(.bold)
                            
                            Text("Sign in to sync across devices")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                        .padding(.top, 20)
                    }
                    
                    // Sync Status
                    if !authService.isGuestMode {
                        SyncStatusView()
                            .padding(.horizontal)
                    }
                    
                    // Actions
                    VStack(spacing: 12) {
                        if authService.isGuestMode {
                            Button {
                                authService.disableGuestMode()
                                dismiss()
                            } label: {
                                HStack {
                                    Image(systemName: "person.badge.key")
                                    Text("Sign In")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.blue)
                                .foregroundColor(.white)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                            }
                        } else {
                            Button(role: .destructive) {
                                Task {
                                    await authService.logout()
                                    dismiss()
                                }
                            } label: {
                                HStack {
                                    Image(systemName: "rectangle.portrait.and.arrow.right")
                                    Text("Sign Out")
                                }
                                .frame(maxWidth: .infinity)
                                .padding()
                                .background(Color.red.opacity(0.1))
                                .foregroundColor(.red)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                            }
                        }
                    }
                    .padding(.horizontal)
                }
            }
            .navigationTitle("Profile")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        #if os(macOS)
        .frame(minWidth: 400, minHeight: 500)
        #endif
    }
    
    private func initials(for name: String) -> String {
        let parts = name.split(separator: " ")
        if parts.count >= 2 {
            return String(parts[0].prefix(1) + parts[1].prefix(1)).uppercased()
        }
        return String(name.prefix(2)).uppercased()
    }
}

struct RoleBadge: View {
    let role: String
    
    var color: Color {
        if role.contains("admin") { return .orange }
        if role.contains("user") { return .blue }
        return .gray
    }
    
    var icon: String {
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
        }
        .foregroundColor(color)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.15))
        .clipShape(Capsule())
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthService())
        .environmentObject(MonitorViewModel())
}
