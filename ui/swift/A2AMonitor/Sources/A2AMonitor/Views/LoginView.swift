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
    
    @AppStorage("serverURL") private var serverURL = "https://a2a.quantum-forge.net"
    @AppStorage("lastUsername") private var lastUsername = ""
    @State private var showServerSettings = false
    
    var body: some View {
        ZStack {
            // Background - the liquid gradient
            LiquidGradientBackground()
            
            ScrollView {
                VStack(spacing: 0) {
                    Spacer(minLength: 60)
                    
                    // Logo and Title
                    VStack(spacing: 16) {
                        Image(systemName: "cpu.fill")
                            .font(.system(size: 64))
                            .foregroundStyle(
                                LinearGradient(
                                    colors: [.white, .cyan],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
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
                    
                    // Login Form Card
                    VStack(spacing: 20) {
                        // Email field
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Email")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(.white.opacity(0.8))
                            
                            HStack(spacing: 12) {
                                Image(systemName: "envelope.fill")
                                    .foregroundColor(.white.opacity(0.6))
                                    .frame(width: 20)
                                TextField("", text: $username, prompt: Text("email@example.com").foregroundColor(.white.opacity(0.4)))
                                    .foregroundColor(.white)
                                    .textContentType(.emailAddress)
                                    #if os(iOS)
                                    .keyboardType(.emailAddress)
                                    .autocapitalization(.none)
                                    #endif
                                    .disableAutocorrection(true)
                                    .submitLabel(.next)
                            }
                            .padding()
                            .background(Color.white.opacity(0.15))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(Color.white.opacity(0.3), lineWidth: 1)
                            )
                        }
                        
                        // Password field
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Password")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(.white.opacity(0.8))
                            
                            HStack(spacing: 12) {
                                Image(systemName: "lock.fill")
                                    .foregroundColor(.white.opacity(0.6))
                                    .frame(width: 20)
                                SecureField("", text: $password, prompt: Text("Password").foregroundColor(.white.opacity(0.4)))
                                    .foregroundColor(.white)
                                    .textContentType(.password)
                                    .submitLabel(.go)
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
                        
                        // Remember me toggle
                        HStack {
                            Toggle(isOn: $rememberMe) {
                                Text("Remember me")
                                    .font(.subheadline)
                                    .foregroundColor(.white.opacity(0.8))
                            }
                            .toggleStyle(SwitchToggleStyle(tint: .cyan))
                        }
                        
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
                                        .fontWeight(.bold)
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 16)
                            .background(
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
                            )
                            .foregroundColor(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .shadow(color: .cyan.opacity(username.isEmpty || password.isEmpty ? 0 : 0.4), radius: 12, y: 4)
                        }
                        .disabled(username.isEmpty || password.isEmpty || isLoading)
                        
                        // Divider
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
                        
                        // Continue without login
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
                        
                        Text("Guest mode won't sync across devices")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.5))
                            .multilineTextAlignment(.center)
                    }
                    .padding(28)
                    .background(
                        RoundedRectangle(cornerRadius: 24)
                            .fill(Color.black.opacity(0.3))
                            .background(
                                RoundedRectangle(cornerRadius: 24)
                                    .fill(.ultraThinMaterial)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 24))
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 24)
                            .stroke(Color.white.opacity(0.2), lineWidth: 1)
                    )
                    .padding(.horizontal, 24)
                    .frame(maxWidth: 420)
                    
                    Spacer(minLength: 40)
                    
                    // Server Settings
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
                        .overlay(
                            Capsule()
                                .stroke(Color.white.opacity(0.2), lineWidth: 1)
                        )
                    }
                    .padding(.bottom, 32)
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
            ZStack {
                // Background
                LiquidGradientBackground()
                
                ScrollView {
                    VStack(spacing: 24) {
                        // Icon
                        Image(systemName: "server.rack")
                            .font(.system(size: 48))
                            .foregroundStyle(
                                LinearGradient(colors: [.white, .cyan], startPoint: .top, endPoint: .bottom)
                            )
                            .shadow(color: .cyan.opacity(0.5), radius: 15)
                            .padding(.top, 30)
                        
                        Text("Server Configuration")
                            .font(.title2)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                        
                        // URL Input
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Server URL")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(.white.opacity(0.8))
                            
                            HStack {
                                TextField("", text: $tempURL, prompt: Text("https://a2a.quantum-forge.net").foregroundColor(.white.opacity(0.4)))
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
                        .padding(.horizontal)
                        
                        // Connection Status
                        connectionStatusView
                            .padding(.horizontal)
                        
                        // Quick presets
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Quick Presets")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(.white.opacity(0.8))
                                .padding(.horizontal)
                            
                            HStack(spacing: 10) {
                                PresetButton(title: "Local", icon: "laptopcomputer") {
                                    tempURL = "http://localhost:8000"
                                }
                                PresetButton(title: "Docker", icon: "shippingbox") {
                                    tempURL = "http://localhost:9000"
                                }
                                PresetButton(title: "Quantum Forge", icon: "cloud") {
                                    tempURL = "https://a2a.quantum-forge.net"
                                }
                            }
                            .padding(.horizontal)
                        }
                        
                        Spacer(minLength: 40)
                        
                        // Actions
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
                            
                            Button(action: {
                                serverURL = tempURL
                                dismiss()
                            }) {
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
                                .shadow(color: .cyan.opacity(0.4), radius: 10, y: 4)
                            }
                            .disabled(tempURL.isEmpty)
                        }
                        .padding(.horizontal)
                        .padding(.bottom, 30)
                    }
                }
            }
            .navigationTitle("Server")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(.white)
                }
            }
            .toolbarBackground(.hidden, for: .navigationBar)
            .onAppear {
                tempURL = serverURL
            }
        }
        #if os(macOS)
        .frame(minWidth: 450, minHeight: 500)
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
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    .scaleEffect(0.8)
                Text("Checking connection...")
                    .font(.subheadline)
                    .foregroundColor(.white.opacity(0.7))
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(Color.white.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        case .success(let message):
            HStack {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
                Text(message)
                    .font(.subheadline)
                    .foregroundColor(.white)
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(Color.green.opacity(0.2))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.green.opacity(0.5), lineWidth: 1)
            )
        case .failure(let message):
            HStack {
                Image(systemName: "xmark.circle.fill")
                    .foregroundColor(.red)
                Text(message)
                    .font(.subheadline)
                    .foregroundColor(.white)
            }
            .padding()
            .frame(maxWidth: .infinity)
            .background(Color.red.opacity(0.2))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.red.opacity(0.5), lineWidth: 1)
            )
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
                        connectionStatus = .success("Server is healthy")
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
                // Header
                HStack {
                    Image(systemName: "arrow.triangle.2.circlepath.circle.fill")
                        .font(.title2)
                        .foregroundColor(.cyan)
                    
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Synced Across Devices")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                        Text("\(syncState.activeDevices) active device\(syncState.activeDevices == 1 ? "" : "s")")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.6))
                    }
                    
                    Spacer()
                }
                
                Divider()
                    .background(Color.white.opacity(0.2))
                
                // Devices
                if !syncState.sessions.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(syncState.sessions) { session in
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
                    }
                }
                
                // Codebases
                if !syncState.codebases.isEmpty {
                    Divider()
                        .background(Color.white.opacity(0.2))
                    
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Your Codebases")
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(.white.opacity(0.7))
                        
                        ForEach(syncState.codebases) { codebase in
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
                    }
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
                    Image(systemName: "person.badge.clock.fill")
                        .font(.title3)
                    Text("Guest")
                        .font(.caption)
                        .fontWeight(.medium)
                } else if let user = authService.currentUser {
                    // Avatar with initials
                    ZStack {
                        Circle()
                            .fill(
                                LinearGradient(colors: [.cyan, .blue], startPoint: .topLeading, endPoint: .bottomTrailing)
                            )
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
                } else {
                    Image(systemName: "person.circle.fill")
                        .font(.title3)
                }
            }
            .foregroundColor(.white)
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
            ZStack {
                LiquidGradientBackground()
                
                ScrollView {
                    VStack(spacing: 24) {
                        // Profile Header
                        if let user = authService.currentUser {
                            VStack(spacing: 12) {
                                // Avatar
                                ZStack {
                                    Circle()
                                        .fill(
                                            LinearGradient(colors: [.cyan, .blue], startPoint: .topLeading, endPoint: .bottomTrailing)
                                        )
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
                                
                                // Role badges
                                HStack(spacing: 8) {
                                    ForEach(user.roles.prefix(3), id: \.self) { role in
                                        RoleBadge(role: role)
                                    }
                                }
                            }
                            .padding(.top, 30)
                        } else if authService.isGuestMode {
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
                                        Image(systemName: "person.badge.key.fill")
                                        Text("Sign In")
                                            .fontWeight(.bold)
                                    }
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(
                                        LinearGradient(colors: [.cyan, .blue], startPoint: .leading, endPoint: .trailing)
                                    )
                                    .foregroundColor(.white)
                                    .clipShape(RoundedRectangle(cornerRadius: 12))
                                    .shadow(color: .cyan.opacity(0.4), radius: 10, y: 4)
                                }
                            } else {
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
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 12)
                                            .stroke(Color.red.opacity(0.4), lineWidth: 1)
                                    )
                                }
                            }
                        }
                        .padding(.horizontal)
                        .padding(.bottom, 30)
                    }
                }
            }
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                        .foregroundColor(.white)
                }
            }
            .toolbarBackground(.hidden, for: .navigationBar)
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
        if role.contains("user") { return .cyan }
        return .white.opacity(0.6)
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
                .fontWeight(.medium)
        }
        .foregroundColor(color)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(color.opacity(0.2))
        .clipShape(Capsule())
        .overlay(
            Capsule()
                .stroke(color.opacity(0.4), lineWidth: 1)
        )
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthService())
        .environmentObject(MonitorViewModel())
}
