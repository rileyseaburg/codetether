import SwiftUI

/// A2A Agent Monitor - Liquid Glass UI
/// A modern, fluid SwiftUI interface for monitoring A2A agent conversations
@main
struct A2AMonitorApp: App {
    @StateObject private var viewModel = MonitorViewModel()
    @StateObject private var authService = AuthService()
    
    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(viewModel)
                .environmentObject(authService)
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
            SettingsView()
                .environmentObject(viewModel)
                .environmentObject(authService)
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
    @State private var selectedTab: Tab = .dashboard
    
    enum Tab: String, CaseIterable {
        case dashboard = "Dashboard"
        case agents = "Agents"
        case messages = "Messages"
        case tasks = "Tasks"
        case output = "Output"
        
        var icon: String {
            switch self {
            case .dashboard: return "square.grid.2x2"
            case .agents: return "cpu"
            case .messages: return "bubble.left.and.bubble.right"
            case .tasks: return "checklist"
            case .output: return "terminal"
            }
        }
    }
    
    var body: some View {
        ZStack {
            // Background gradient
            LiquidGradientBackground()
            
            #if os(iOS)
            TabView(selection: $selectedTab) {
                ForEach(Tab.allCases, id: \.self) { tab in
                    tabContent(for: tab)
                        .tabItem {
                            Label(tab.rawValue, systemImage: tab.icon)
                        }
                        .tag(tab)
                }
            }
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    UserProfileButton()
                }
            }
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
        }
    }
    
    @ViewBuilder
    func tabContent(for tab: Tab) -> some View {
        switch tab {
        case .dashboard:
            DashboardView()
        case .agents:
            AgentsView()
        case .messages:
            MessagesView()
        case .tasks:
            TasksView()
        case .output:
            AgentOutputView()
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

// MARK: - Settings View
struct SettingsView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @EnvironmentObject var authService: AuthService
    @AppStorage("serverURL") private var serverURL = "http://localhost:8000"
    @AppStorage("autoReconnect") private var autoReconnect = true
    @AppStorage("refreshInterval") private var refreshInterval = 5.0
    
    var body: some View {
        Form {
            Section("Server") {
                TextField("Server URL", text: $serverURL)
                Toggle("Auto Reconnect", isOn: $autoReconnect)
            }
            
            Section("Refresh") {
                Slider(value: $refreshInterval, in: 1...30, step: 1) {
                    Text("Refresh Interval: \(Int(refreshInterval))s")
                }
            }
            
            Section("Account") {
                if let user = authService.currentUser {
                    LabeledContent("Signed in as", value: user.displayName)
                    LabeledContent("Email", value: user.email)
                    
                    Button("Sign Out", role: .destructive) {
                        Task {
                            await authService.logout()
                        }
                    }
                } else {
                    Text("Not signed in")
                        .foregroundColor(.secondary)
                }
            }
            
            if let syncState = authService.syncState {
                Section("Sync Status") {
                    LabeledContent("Active Devices", value: "\(syncState.activeDevices)")
                    LabeledContent("Codebases", value: "\(syncState.codebases.count)")
                    LabeledContent("Agent Sessions", value: "\(syncState.agentSessions.count)")
                }
            }
        }
        .padding()
        .frame(width: 400, height: 400)
    }
}
