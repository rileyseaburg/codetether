import SwiftUI

/// A2A Agent Monitor - Liquid Glass UI
/// A modern, fluid SwiftUI interface for monitoring A2A agent conversations
@main
struct A2AMonitorApp: App {
    @StateObject private var viewModel = MonitorViewModel()
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(viewModel)
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
        }
        #endif
    }
}

// MARK: - Content View
struct ContentView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
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
            #else
            NavigationSplitView {
                SidebarView(selectedTab: $selectedTab)
            } detail: {
                tabContent(for: selectedTab)
            }
            #endif
        }
        .onAppear {
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

// MARK: - Settings View
struct SettingsView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
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
        }
        .padding()
        .frame(width: 400, height: 200)
    }
}
