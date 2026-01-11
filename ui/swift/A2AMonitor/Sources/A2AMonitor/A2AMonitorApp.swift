import SwiftUI

/// A2A Agent Monitor - Liquid Glass UI
/// A modern, fluid SwiftUI interface for monitoring A2A agent conversations
@main
struct A2AMonitorApp: App {
    @StateObject private var viewModel = MonitorViewModel()
    @StateObject private var authService = AuthService()
    @AppStorage("hasSeenOnboarding") private var hasSeenOnboarding = false

    var body: some Scene {
        WindowGroup {
            Group {
                if hasSeenOnboarding {
                    RootView()
                } else {
                    OnboardingView(hasSeenOnboarding: $hasSeenOnboarding)
                }
            }
            .environmentObject(viewModel)
            .environmentObject(authService)
            .preferredColorScheme(.dark) // Force dark mode for liquid glass UI
            .animation(.easeInOut(duration: 0.4), value: hasSeenOnboarding)
            .task {
                // Configure notification handling (iOS local alerts).
                NotificationService.shared.configure()
                await NotificationService.shared.requestAuthorizationIfNeeded()
            }
            #if os(macOS)
            .frame(minWidth: 1200, minHeight: 800)
            #endif
        }
        #if os(macOS)
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1400, height: 900)
        #endif

        #if os(macOS)
        Settings {
            MacSettingsView()
                .environmentObject(viewModel)
                .environmentObject(authService)
                .preferredColorScheme(.dark)
        }
        #endif
    }
}

// MARK: - Root View (handles auth state)
struct RootView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var viewModel: MonitorViewModel

    var body: some View {
        Group {
            if authService.isAuthenticated {
                ContentView()
            } else {
                LoginView()
            }
        }
        .animation(.easeInOut, value: authService.isAuthenticated)
    }
}

// MARK: - Content View
struct ContentView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @EnvironmentObject var authService: AuthService
    @State private var selectedTab: Tab = .command

    enum Tab: String, CaseIterable {
        case command = "Command"
        case activity = "Activity"
        case environments = "Environments"

        var icon: String {
            switch self {
            case .command: return "mic.fill"
            case .activity: return "list.bullet.rectangle.fill"
            case .environments: return "lock.shield.fill"
            }
        }
    }

    var body: some View {
        ZStack {
            // Background gradient
            LiquidGradientBackground()

            #if os(iOS)
            NavigationStack {
                TabView(selection: $selectedTab) {
                    ForEach(Tab.allCases, id: \.self) { tab in
                        tabContent(for: tab)
                            .tabItem {
                                Label(tab.rawValue, systemImage: tab.icon)
                            }
                            .tag(tab)
                    }
                }
                .tint(.cyan) // Tab bar tint color
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        UserProfileButton()
                    }
                }
                .toolbarBackground(.ultraThinMaterial, for: .navigationBar)
                .toolbarBackground(.visible, for: .navigationBar)
            }
            .tint(.cyan)
            #else
            NavigationSplitView {
                SidebarView(selectedTab: $selectedTab)
            } detail: {
                tabContent(for: selectedTab)
            }
            .toolbar {
                ToolbarItem(placement: .automatic) {
                    UserProfileButton()
                }
            }
            #endif
        }
        .onAppear {
            // Connect auth service to viewModel's client
            viewModel.setAuthService(authService)
            viewModel.connect()

            #if os(iOS)
            // Configure tab bar appearance for iOS
            let tabBarAppearance = UITabBarAppearance()
            tabBarAppearance.configureWithTransparentBackground()
            tabBarAppearance.backgroundColor = UIColor.black.withAlphaComponent(0.3)
            tabBarAppearance.backgroundEffect = UIBlurEffect(style: .systemUltraThinMaterialDark)

            // Normal state
            tabBarAppearance.stackedLayoutAppearance.normal.iconColor = UIColor.white.withAlphaComponent(0.5)
            tabBarAppearance.stackedLayoutAppearance.normal.titleTextAttributes = [.foregroundColor: UIColor.white.withAlphaComponent(0.5)]

            // Selected state
            tabBarAppearance.stackedLayoutAppearance.selected.iconColor = UIColor.cyan
            tabBarAppearance.stackedLayoutAppearance.selected.titleTextAttributes = [.foregroundColor: UIColor.cyan]

            UITabBar.appearance().standardAppearance = tabBarAppearance
            UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance

            // Configure navigation bar appearance
            let navBarAppearance = UINavigationBarAppearance()
            navBarAppearance.configureWithTransparentBackground()
            navBarAppearance.backgroundColor = UIColor.black.withAlphaComponent(0.2)
            navBarAppearance.backgroundEffect = UIBlurEffect(style: .systemUltraThinMaterialDark)
            navBarAppearance.titleTextAttributes = [.foregroundColor: UIColor.white]
            navBarAppearance.largeTitleTextAttributes = [.foregroundColor: UIColor.white]

            UINavigationBar.appearance().standardAppearance = navBarAppearance
            UINavigationBar.appearance().scrollEdgeAppearance = navBarAppearance
            UINavigationBar.appearance().compactAppearance = navBarAppearance
            UINavigationBar.appearance().tintColor = .cyan
            #endif
        }
    }

    @ViewBuilder
    func tabContent(for tab: Tab) -> some View {
        switch tab {
        case .command:
            CommandView()
        case .activity:
            ActivityView()
        case .environments:
            EnvironmentsView()
        }
    }
}

#if os(macOS)
// MARK: - Sidebar (macOS)
struct SidebarView: View {
    @Binding var selectedTab: ContentView.Tab
    @EnvironmentObject var viewModel: MonitorViewModel

    var body: some View {
        List(ContentView.Tab.allCases, id: \.self, selection: $selectedTab) { tab in
            Label(tab.rawValue, systemImage: tab.icon)
                .foregroundColor(.white)
                .tag(tab)
        }
        .listStyle(.sidebar)
        .navigationTitle("A2A Monitor")
        .safeAreaInset(edge: .bottom) {
            ConnectionStatusBadge()
                .padding()
        }
    }
}

#endif

// MARK: - macOS Settings View (for Settings menu)
#if os(macOS)
struct MacSettingsView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @EnvironmentObject var authService: AuthService
    @AppStorage("serverURL") private var serverURL = "https://api.codetether.run"
    @AppStorage("autoReconnect") private var autoReconnect = true
    @AppStorage("refreshInterval") private var refreshInterval = 5.0

    var body: some View {
        ZStack {
            LiquidGradientBackground()

            ScrollView {
                VStack(spacing: 24) {
                    // Server Section
                    SettingsSection(title: "Server", icon: "server.rack") {
                        VStack(spacing: 16) {
                            SettingsTextField(title: "Server URL", text: $serverURL)
                            SettingsToggle(title: "Auto Reconnect", isOn: $autoReconnect)
                        }
                    }

                    // Refresh Section
                    SettingsSection(title: "Refresh", icon: "arrow.clockwise") {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Refresh Interval: \(Int(refreshInterval))s")
                                .font(.subheadline)
                                .foregroundColor(.white)
                            Slider(value: $refreshInterval, in: 1...30, step: 1)
                                .tint(.cyan)
                        }
                    }

                    // Account Section
                    SettingsSection(title: "Account", icon: "person.circle") {
                        if let user = authService.currentUser {
                            VStack(spacing: 12) {
                                SettingsRow(label: "Signed in as", value: user.displayName)
                                SettingsRow(label: "Email", value: user.email)

                                Button {
                                    Task { await authService.logout() }
                                } label: {
                                    HStack {
                                        Image(systemName: "rectangle.portrait.and.arrow.right")
                                        Text("Sign Out")
                                    }
                                    .foregroundColor(.red)
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(Color.red.opacity(0.15))
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                                }
                            }
                        } else if authService.isGuestMode {
                            Text("Guest Mode")
                                .foregroundColor(.white.opacity(0.7))
                        } else {
                            Text("Not signed in")
                                .foregroundColor(.white.opacity(0.5))
                        }
                    }

                    // Sync Status
                    if let syncState = authService.syncState {
                        SettingsSection(title: "Sync Status", icon: "arrow.triangle.2.circlepath") {
                            VStack(spacing: 12) {
                                SettingsRow(label: "Active Devices", value: "\(syncState.activeDevices)")
                                SettingsRow(label: "Codebases", value: "\(syncState.codebases.count)")
                                SettingsRow(label: "Agent Sessions", value: "\(syncState.agentSessions.count)")
                            }
                        }
                    }
                }
                .padding(24)
            }
        }
        .frame(width: 450, height: 550)
    }
}
#endif

// MARK: - Settings Components

struct SettingsSection<Content: View>: View {
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
            HStack {
                Image(systemName: icon)
                    .foregroundColor(.cyan)
                Text(title)
                    .font(.headline)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
            }

            content
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.white.opacity(0.2), lineWidth: 1)
        )
    }
}

struct SettingsTextField: View {
    let title: String
    @Binding var text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
            TextField("", text: $text)
                .textFieldStyle(.plain)
                .foregroundColor(.white)
                .padding(12)
                .background(Color.white.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }
}

struct SettingsToggle: View {
    let title: String
    @Binding var isOn: Bool

    var body: some View {
        Toggle(isOn: $isOn) {
            Text(title)
                .foregroundColor(.white)
        }
        .toggleStyle(SwitchToggleStyle(tint: .cyan))
    }
}

struct SettingsRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.white.opacity(0.7))
            Spacer()
            Text(value)
                .foregroundColor(.white)
                .fontWeight(.medium)
        }
    }
}
