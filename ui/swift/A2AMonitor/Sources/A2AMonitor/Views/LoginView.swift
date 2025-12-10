import SwiftUI

/// Login view with Liquid Glass styling for Keycloak authentication
struct LoginView: View {
    @EnvironmentObject var authService: AuthService
    
    @State private var username = ""
    @State private var password = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showError = false
    
    @AppStorage("serverURL") private var serverURL = "http://localhost:8000"
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
                    
                    Text("A2A Monitor")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    Text("Sign in to sync across devices")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.bottom, 48)
                
                // Login Form
                VStack(spacing: 20) {
                    // Username field
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Email")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        HStack {
                            Image(systemName: "envelope")
                                .foregroundColor(.secondary)
                            TextField("email@example.com", text: $username)
                                .textContentType(.emailAddress)
                                #if os(iOS)
                                .keyboardType(.emailAddress)
                                .autocapitalization(.none)
                                #endif
                                .disableAutocorrection(true)
                        }
                        .padding()
                        .background(.ultraThinMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    
                    // Password field
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Password")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        HStack {
                            Image(systemName: "lock")
                                .foregroundColor(.secondary)
                            SecureField("Password", text: $password)
                                .textContentType(.password)
                        }
                        .padding()
                        .background(.ultraThinMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    
                    // Login Button
                    Button(action: login) {
                        HStack {
                            if isLoading {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                    .scaleEffect(0.8)
                            } else {
                                Text("Sign In")
                                    .fontWeight(.semibold)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(
                            LinearGradient(
                                colors: [.blue, .purple],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .foregroundColor(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(username.isEmpty || password.isEmpty || isLoading)
                    .opacity((username.isEmpty || password.isEmpty) ? 0.6 : 1)
                }
                .padding(.horizontal, 32)
                .frame(maxWidth: 400)
                
                Spacer()
                
                // Server Settings
                Button(action: { showServerSettings = true }) {
                    HStack {
                        Image(systemName: "server.rack")
                        Text("Server: \(serverURL)")
                            .lineLimit(1)
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
                .padding(.bottom, 32)
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
    }
    
    private func login() {
        isLoading = true
        errorMessage = nil
        
        // Update auth service base URL
        authService.updateBaseURL(serverURL)
        
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
}

// MARK: - Server Settings Sheet

struct ServerSettingsSheet: View {
    @Binding var serverURL: String
    @Environment(\.dismiss) private var dismiss
    @State private var tempURL: String = ""
    @State private var isChecking = false
    @State private var authStatus: AuthStatusResponse?
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Server URL") {
                    TextField("http://localhost:8000", text: $tempURL)
                        #if os(iOS)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        #endif
                        .disableAutocorrection(true)
                }
                
                Section {
                    Button(action: checkConnection) {
                        HStack {
                            if isChecking {
                                ProgressView()
                                    .scaleEffect(0.8)
                            } else {
                                Text("Check Connection")
                            }
                        }
                    }
                    .disabled(tempURL.isEmpty || isChecking)
                    
                    if let status = authStatus {
                        HStack {
                            Image(systemName: status.available ? "checkmark.circle.fill" : "xmark.circle.fill")
                                .foregroundColor(status.available ? .green : .red)
                            Text(status.message)
                        }
                        
                        if status.available, let realm = status.realm {
                            Text("Realm: \(realm)")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                
                Section {
                    Text("Enter the URL of your A2A server with Keycloak authentication enabled.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .navigationTitle("Server Settings")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        serverURL = tempURL
                        dismiss()
                    }
                    .disabled(tempURL.isEmpty)
                }
            }
            .onAppear {
                tempURL = serverURL
            }
        }
        #if os(macOS)
        .frame(minWidth: 400, minHeight: 300)
        #endif
    }
    
    private func checkConnection() {
        isChecking = true
        authStatus = nil
        
        Task {
            let service = AuthService(baseURL: tempURL)
            authStatus = await service.checkAuthStatus()
            isChecking = false
        }
    }
}

// MARK: - Sync Status View (for showing multi-device info)

struct SyncStatusView: View {
    @EnvironmentObject var authService: AuthService
    
    var body: some View {
        if let syncState = authService.syncState {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .foregroundColor(.blue)
                    Text("Synced Across Devices")
                        .font(.headline)
                    Spacer()
                    Text("\(syncState.activeDevices) device\(syncState.activeDevices == 1 ? "" : "s")")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                // Active sessions
                if !syncState.sessions.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Active Sessions")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        ForEach(syncState.sessions) { session in
                            HStack {
                                Image(systemName: deviceIcon(for: session.deviceInfo.deviceType))
                                    .foregroundColor(.secondary)
                                Text(session.deviceInfo.deviceName ?? "Unknown Device")
                                    .font(.caption)
                                Spacer()
                                if session.sessionId == authService.currentUser?.sessionId {
                                    Text("Current")
                                        .font(.caption2)
                                        .foregroundColor(.green)
                                }
                            }
                        }
                    }
                }
                
                // Codebases
                if !syncState.codebases.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Your Codebases")
                            .font(.caption)
                            .foregroundColor(.secondary)
                        
                        ForEach(syncState.codebases) { codebase in
                            HStack {
                                Image(systemName: "folder")
                                    .foregroundColor(.blue)
                                Text(codebase.codebaseName)
                                    .font(.caption)
                                Spacer()
                                Text(codebase.role)
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
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
                Image(systemName: "person.circle.fill")
                    .font(.title2)
                if let user = authService.currentUser {
                    Text(user.displayName)
                        .font(.caption)
                        .lineLimit(1)
                }
            }
            .foregroundColor(.primary)
        }
        .sheet(isPresented: $showingProfile) {
            UserProfileSheet()
        }
    }
}

// MARK: - User Profile Sheet

struct UserProfileSheet: View {
    @EnvironmentObject var authService: AuthService
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            List {
                if let user = authService.currentUser {
                    Section("Account") {
                        LabeledContent("Name", value: user.displayName)
                        LabeledContent("Email", value: user.email)
                        LabeledContent("Username", value: user.username)
                    }
                    
                    Section("Roles") {
                        ForEach(user.roles, id: \.self) { role in
                            HStack {
                                Image(systemName: role.contains("admin") ? "shield.fill" : "person.fill")
                                    .foregroundColor(role.contains("admin") ? .orange : .blue)
                                Text(role)
                            }
                        }
                    }
                }
                
                Section {
                    SyncStatusView()
                }
                
                Section {
                    Button(role: .destructive, action: logout) {
                        HStack {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                            Text("Sign Out")
                        }
                    }
                }
            }
            .navigationTitle("Profile")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
        #if os(macOS)
        .frame(minWidth: 400, minHeight: 500)
        #endif
    }
    
    private func logout() {
        Task {
            await authService.logout()
            dismiss()
        }
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthService())
}
