import SwiftUI

/// SettingsView - iOS-focused settings screen with server config, notifications, and account management
struct SettingsView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @EnvironmentObject var authService: AuthService
    @AppStorage("serverURL") private var serverURL = "https://api.codetether.run"
    @AppStorage("autoReconnect") private var autoReconnect = true
    @AppStorage("refreshInterval") private var refreshInterval = 5.0
    @AppStorage("notificationsEnabled") private var notificationsEnabled = true
    @AppStorage("notifyOnNewTask") private var notifyOnNewTask = true
    @AppStorage("notifyOnTaskComplete") private var notifyOnTaskComplete = true
    @AppStorage("notifyOnAgentMessage") private var notifyOnAgentMessage = false
    
    @State private var showingLogoutConfirmation = false
    @State private var showingResetConfirmation = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Server Configuration
                serverSection
                
                // Notification Preferences
                notificationSection
                
                // About Section
                aboutSection
                
                // Account Section
                accountSection
            }
            .padding(16)
        }
        .background(Color.clear)
        .navigationTitle("Settings")
        #if os(iOS)
        .navigationBarTitleDisplayModeLarge()
        #endif
        .alert("Sign Out", isPresented: $showingLogoutConfirmation) {
            Button("Cancel", role: .cancel) { }
            Button("Sign Out", role: .destructive) {
                Task { await authService.logout() }
            }
        } message: {
            Text("Are you sure you want to sign out?")
        }
        .alert("Reset Settings", isPresented: $showingResetConfirmation) {
            Button("Cancel", role: .cancel) { }
            Button("Reset", role: .destructive) {
                resetToDefaults()
            }
        } message: {
            Text("This will reset all settings to their default values.")
        }
    }
    
    // MARK: - Server Section
    
    private var serverSection: some View {
        SettingsSectionCard(title: "Server", icon: "server.rack") {
            VStack(spacing: 16) {
                // Server URL
                VStack(alignment: .leading, spacing: 6) {
                    Text("Server URL")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                    TextField("https://api.codetether.run", text: $serverURL)
                        .textFieldStyle(.plain)
                        .foregroundColor(.white)
                        .padding(12)
                        .background(Color.white.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        #if os(iOS)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        .textContentType(.URL)
                        #endif
                }
                
                // Auto Reconnect Toggle
                Toggle(isOn: $autoReconnect) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Auto Reconnect")
                            .foregroundColor(.white)
                        Text("Automatically reconnect when connection is lost")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .toggleStyle(SwitchToggleStyle(tint: .cyan))
                
                // Refresh Interval
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("Refresh Interval")
                            .foregroundColor(.white)
                        Spacer()
                        Text("\(Int(refreshInterval))s")
                            .foregroundColor(.cyan)
                            .fontWeight(.medium)
                    }
                    Slider(value: $refreshInterval, in: 1...30, step: 1)
                        .tint(.cyan)
                }
                
                // Connection Status
                HStack {
                    Text("Status")
                        .foregroundColor(.white.opacity(0.7))
                    Spacer()
                    ConnectionStatusBadge()
                }
            }
        }
    }
    
    // MARK: - Notification Section
    
    private var notificationSection: some View {
        SettingsSectionCard(title: "Notifications", icon: "bell.fill") {
            VStack(spacing: 16) {
                // Master Toggle
                Toggle(isOn: $notificationsEnabled) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Enable Notifications")
                            .foregroundColor(.white)
                        Text("Receive alerts for important events")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .toggleStyle(SwitchToggleStyle(tint: .cyan))
                
                if notificationsEnabled {
                    Divider()
                        .background(Color.white.opacity(0.2))
                    
                    // Individual notification toggles
                    Toggle(isOn: $notifyOnNewTask) {
                        Text("New Tasks")
                            .foregroundColor(.white)
                    }
                    .toggleStyle(SwitchToggleStyle(tint: .cyan))
                    
                    Toggle(isOn: $notifyOnTaskComplete) {
                        Text("Task Completed")
                            .foregroundColor(.white)
                    }
                    .toggleStyle(SwitchToggleStyle(tint: .cyan))
                    
                    Toggle(isOn: $notifyOnAgentMessage) {
                        Text("Agent Messages")
                            .foregroundColor(.white)
                    }
                    .toggleStyle(SwitchToggleStyle(tint: .cyan))
                }
            }
        }
    }
    
    // MARK: - About Section
    
    private var aboutSection: some View {
        SettingsSectionCard(title: "About", icon: "info.circle.fill") {
            VStack(spacing: 12) {
                aboutRow(label: "App Name", value: "A2A Monitor")
                aboutRow(label: "Version", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0.0")
                aboutRow(label: "Build", value: Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1")
                
                Divider()
                    .background(Color.white.opacity(0.2))
                
                // Links
                #if os(iOS)
                Link(destination: URL(string: "https://github.com/sst/opencode")!) {
                    HStack {
                        Image(systemName: "link")
                        Text("GitHub Repository")
                        Spacer()
                        Image(systemName: "arrow.up.right")
                            .font(.caption)
                    }
                    .foregroundColor(.cyan)
                }
                
                Link(destination: URL(string: "https://opencode.ai/docs")!) {
                    HStack {
                        Image(systemName: "book")
                        Text("Documentation")
                        Spacer()
                        Image(systemName: "arrow.up.right")
                            .font(.caption)
                    }
                    .foregroundColor(.cyan)
                }
                #endif
            }
        }
    }
    
    private func aboutRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .foregroundColor(.white.opacity(0.7))
            Spacer()
            Text(value)
                .foregroundColor(.white)
                .fontWeight(.medium)
        }
    }
    
    // MARK: - Account Section
    
    private var accountSection: some View {
        SettingsSectionCard(title: "Account", icon: "person.circle.fill") {
            VStack(spacing: 16) {
                if let user = authService.currentUser {
                    // User info
                    HStack(spacing: 12) {
                        // Avatar
                        ZStack {
                            Circle()
                                .fill(Color.cyan.opacity(0.3))
                            Text(user.displayName.prefix(1).uppercased())
                                .font(.title2)
                                .fontWeight(.bold)
                                .foregroundColor(.cyan)
                        }
                        .frame(width: 50, height: 50)
                        
                        VStack(alignment: .leading, spacing: 2) {
                            Text(user.displayName)
                                .font(.headline)
                                .foregroundColor(.white)
                            Text(user.email)
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.7))
                        }
                        Spacer()
                    }
                    
                    Divider()
                        .background(Color.white.opacity(0.2))
                    
                    // Sync Status
                    if let syncState = authService.syncState {
                        VStack(spacing: 8) {
                            aboutRow(label: "Active Devices", value: "\(syncState.activeDevices)")
                            aboutRow(label: "Codebases", value: "\(syncState.codebases.count)")
                        }
                        
                        Divider()
                            .background(Color.white.opacity(0.2))
                    }
                } else if authService.isGuestMode {
                    HStack {
                        Image(systemName: "person.fill.questionmark")
                            .foregroundColor(.orange)
                        Text("Guest Mode")
                            .foregroundColor(.white)
                        Spacer()
                    }
                }
                
                // Action Buttons
                VStack(spacing: 12) {
                    // Reset Settings
                    Button {
                        showingResetConfirmation = true
                    } label: {
                        HStack {
                            Image(systemName: "arrow.counterclockwise")
                            Text("Reset Settings")
                        }
                        .foregroundColor(.orange)
                        .frame(maxWidth: .infinity)
                        .padding(12)
                        .background(Color.orange.opacity(0.15))
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                    
                    // Logout
                    if authService.isAuthenticated {
                        Button {
                            showingLogoutConfirmation = true
                        } label: {
                            HStack {
                                Image(systemName: "rectangle.portrait.and.arrow.right")
                                Text("Sign Out")
                            }
                            .foregroundColor(.red)
                            .frame(maxWidth: .infinity)
                            .padding(12)
                            .background(Color.red.opacity(0.15))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                    }
                }
            }
        }
    }
    
    // MARK: - Helpers
    
    private func resetToDefaults() {
        serverURL = "https://api.codetether.run"
        autoReconnect = true
        refreshInterval = 5.0
        notificationsEnabled = true
        notifyOnNewTask = true
        notifyOnTaskComplete = true
        notifyOnAgentMessage = false
    }
}

// MARK: - Settings Section Card (iOS-optimized)

struct SettingsSectionCard<Content: View>: View {
    let title: String
    let icon: String
    let content: Content
    
    init(title: String, icon: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.icon = icon
        self.content = content()
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .foregroundColor(.cyan)
                    .font(.system(size: 16, weight: .semibold))
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
            }
            
            content
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.white.opacity(0.15), lineWidth: 1)
        )
    }
}

#Preview {
    NavigationStack {
        ZStack {
            LiquidGradientBackground()
            SettingsView()
        }
    }
    .environmentObject(MonitorViewModel())
    .environmentObject(AuthService())
    .preferredColorScheme(.dark)
}
