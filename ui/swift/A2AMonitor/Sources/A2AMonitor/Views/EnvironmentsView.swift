import SwiftUI

/// EnvironmentsView - Manage connected development environments and machines
/// Shows connection status, security info, and allows adding new environments
struct EnvironmentsView: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    @State private var showAddSheet = false
    @State private var environments: [DevEnvironment] = DevEnvironment.sampleData
    
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Connected environments
                connectedSection
                
                // Security overview
                securitySection
                
                // Add environment button
                addEnvironmentButton
                
                Spacer(minLength: 100)
            }
            .padding(.horizontal, 20)
            .padding(.top, 20)
        }
        .navigationTitle("Environments")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.large)
        #endif
        .sheet(isPresented: $showAddSheet) {
            AddEnvironmentSheet(isPresented: $showAddSheet)
        }
    }
    
    // MARK: - Connected Section
    
    private var connectedSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Connected")
                    .font(.headline)
                    .foregroundColor(.white.opacity(0.9))
                
                Spacer()
                
                Text("\(environments.filter { $0.isConnected }.count) active")
                    .font(.subheadline)
                    .foregroundColor(.cyan)
            }
            
            if environments.isEmpty {
                emptyStateView
            } else {
                VStack(spacing: 12) {
                    ForEach(environments) { env in
                        EnvironmentCard(environment: env)
                    }
                }
            }
        }
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "desktopcomputer")
                .font(.system(size: 48))
                .foregroundColor(.white.opacity(0.3))
            
            Text("No environments connected")
                .font(.headline)
                .foregroundColor(.white.opacity(0.7))
            
            Text("Add your development machine to start spawning agents")
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.5))
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 40)
        .background(Color.white.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
    
    // MARK: - Security Section
    
    private var securitySection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "lock.shield.fill")
                    .foregroundColor(.green)
                Text("Security")
                    .font(.headline)
                    .foregroundColor(.white.opacity(0.9))
            }
            
            VStack(spacing: 12) {
                SecurityRow(
                    icon: "lock.fill",
                    title: "End-to-End Encryption",
                    subtitle: "All connections use TLS 1.3",
                    isEnabled: true
                )
                
                SecurityRow(
                    icon: "key.fill",
                    title: "Device Authentication",
                    subtitle: "Verified via secure pairing",
                    isEnabled: true
                )
                
                SecurityRow(
                    icon: "checkmark.shield.fill",
                    title: "Code Signing",
                    subtitle: "Agent actions are signed",
                    isEnabled: true
                )
            }
            .padding(16)
            .background(Color.white.opacity(0.05))
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(Color.green.opacity(0.3), lineWidth: 1)
            )
        }
    }
    
    // MARK: - Add Environment Button
    
    private var addEnvironmentButton: some View {
        Button {
            showAddSheet = true
        } label: {
            HStack(spacing: 12) {
                Image(systemName: "plus.circle.fill")
                    .font(.system(size: 24))
                
                VStack(alignment: .leading, spacing: 2) {
                    Text("Add Environment")
                        .font(.headline)
                    Text("Scan QR code or enter connection details")
                        .font(.caption)
                        .opacity(0.7)
                }
                
                Spacer()
                
                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .opacity(0.5)
            }
            .foregroundColor(.cyan)
            .padding(20)
            .frame(maxWidth: .infinity)
            .background(Color.cyan.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(Color.cyan.opacity(0.3), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Environment Model

struct DevEnvironment: Identifiable {
    let id = UUID()
    let name: String
    let hostname: String
    let platform: Platform
    let isConnected: Bool
    let lastSeen: Date
    let agentCount: Int
    
    enum Platform: String {
        case macos = "macOS"
        case linux = "Linux"
        case windows = "Windows"
        
        var icon: String {
            switch self {
            case .macos: return "apple.logo"
            case .linux: return "server.rack"
            case .windows: return "desktopcomputer"
            }
        }
    }
    
    static let sampleData: [DevEnvironment] = [
        DevEnvironment(
            name: "MacBook Pro",
            hostname: "rileys-mbp.local",
            platform: .macos,
            isConnected: true,
            lastSeen: Date(),
            agentCount: 3
        ),
        DevEnvironment(
            name: "Dev Server",
            hostname: "dev.internal.corp",
            platform: .linux,
            isConnected: true,
            lastSeen: Date().addingTimeInterval(-300),
            agentCount: 1
        ),
        DevEnvironment(
            name: "Work Desktop",
            hostname: "desktop-001.local",
            platform: .macos,
            isConnected: false,
            lastSeen: Date().addingTimeInterval(-86400),
            agentCount: 0
        )
    ]
}

// MARK: - Environment Card

struct EnvironmentCard: View {
    let environment: DevEnvironment
    
    var body: some View {
        HStack(spacing: 16) {
            // Platform icon with connection indicator
            ZStack(alignment: .bottomTrailing) {
                Image(systemName: environment.platform.icon)
                    .font(.system(size: 28))
                    .foregroundColor(.white.opacity(0.8))
                    .frame(width: 50, height: 50)
                    .background(Color.white.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                
                // Connection status dot
                Circle()
                    .fill(environment.isConnected ? Color.green : Color.red)
                    .frame(width: 12, height: 12)
                    .overlay(
                        Circle()
                            .stroke(Color.black, lineWidth: 2)
                    )
                    .offset(x: 4, y: 4)
            }
            
            // Info
            VStack(alignment: .leading, spacing: 4) {
                Text(environment.name)
                    .font(.headline)
                    .foregroundColor(.white)
                
                Text(environment.hostname)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
                
                HStack(spacing: 8) {
                    // Platform badge
                    Text(environment.platform.rawValue)
                        .font(.caption2)
                        .fontWeight(.medium)
                        .foregroundColor(.white.opacity(0.7))
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.white.opacity(0.1))
                        .clipShape(Capsule())
                    
                    // Agent count
                    if environment.agentCount > 0 {
                        HStack(spacing: 4) {
                            Image(systemName: "cpu")
                                .font(.system(size: 10))
                            Text("\(environment.agentCount)")
                                .font(.caption2)
                                .fontWeight(.medium)
                        }
                        .foregroundColor(.cyan)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Color.cyan.opacity(0.2))
                        .clipShape(Capsule())
                    }
                }
            }
            
            Spacer()
            
            // Encryption badge
            Image(systemName: "lock.fill")
                .font(.system(size: 14))
                .foregroundColor(.green)
        }
        .padding(16)
        .background(Color.white.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(
                    environment.isConnected
                        ? Color.green.opacity(0.2)
                        : Color.white.opacity(0.1),
                    lineWidth: 1
                )
        )
    }
}

// MARK: - Security Row

struct SecurityRow: View {
    let icon: String
    let title: String
    let subtitle: String
    let isEnabled: Bool
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundColor(isEnabled ? .green : .white.opacity(0.4))
                .frame(width: 24)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.white)
                
                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
            }
            
            Spacer()
            
            Image(systemName: isEnabled ? "checkmark.circle.fill" : "circle")
                .foregroundColor(isEnabled ? .green : .white.opacity(0.3))
        }
    }
}

// MARK: - Add Environment Sheet

struct AddEnvironmentSheet: View {
    @Binding var isPresented: Bool
    @State private var connectionMethod: ConnectionMethod = .qrCode
    @State private var manualHost = ""
    @State private var manualPort = "8443"
    
    enum ConnectionMethod {
        case qrCode
        case manual
    }
    
    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.opacity(0.9)
                    .ignoresSafeArea()
                
                VStack(spacing: 24) {
                    // Method picker
                    Picker("Method", selection: $connectionMethod) {
                        Text("QR Code").tag(ConnectionMethod.qrCode)
                        Text("Manual").tag(ConnectionMethod.manual)
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal)
                    
                    if connectionMethod == .qrCode {
                        qrCodeView
                    } else {
                        manualEntryView
                    }
                    
                    Spacer()
                }
                .padding(.top, 20)
            }
            .navigationTitle("Add Environment")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        isPresented = false
                    }
                    .foregroundColor(.cyan)
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
    
    private var qrCodeView: some View {
        VStack(spacing: 20) {
            // Placeholder for camera view
            RoundedRectangle(cornerRadius: 20)
                .fill(Color.white.opacity(0.1))
                .frame(height: 250)
                .overlay(
                    VStack(spacing: 12) {
                        Image(systemName: "qrcode.viewfinder")
                            .font(.system(size: 60))
                            .foregroundColor(.white.opacity(0.5))
                        
                        Text("Point at QR code on your machine")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.7))
                    }
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 20)
                        .stroke(Color.cyan.opacity(0.5), lineWidth: 2)
                )
                .padding(.horizontal)
            
            Text("Run `a2a-monitor pair` on your machine to show the QR code")
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
                .multilineTextAlignment(.center)
                .padding(.horizontal)
        }
    }
    
    private var manualEntryView: some View {
        VStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Hostname or IP")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
                
                TextField("e.g., 192.168.1.100", text: $manualHost)
                    .textFieldStyle(.plain)
                    .foregroundColor(.white)
                    .padding(14)
                    .background(Color.white.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            
            VStack(alignment: .leading, spacing: 8) {
                Text("Port")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
                
                TextField("8443", text: $manualPort)
                    .textFieldStyle(.plain)
                    .foregroundColor(.white)
                    .padding(14)
                    .background(Color.white.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    #if os(iOS)
                    .keyboardType(.numberPad)
                    #endif
            }
            
            Button {
                // TODO: Connect to environment
                isPresented = false
            } label: {
                Text("Connect")
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Color.cyan)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .buttonStyle(.plain)
            .disabled(manualHost.isEmpty)
            .opacity(manualHost.isEmpty ? 0.5 : 1)
        }
        .padding(.horizontal)
    }
}

#Preview {
    ZStack {
        LiquidGradientBackground()
        EnvironmentsView()
            .environmentObject(MonitorViewModel())
    }
    .preferredColorScheme(.dark)
}
