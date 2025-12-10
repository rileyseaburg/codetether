import SwiftUI

// MARK: - Liquid Glass Design System
// Apple-inspired frosted glass aesthetic with vibrant gradients and fluid animations

// MARK: - Color Theme

extension Color {
    static let liquidGlass = LiquidGlassColors()
    
    struct LiquidGlassColors {
        let primary = Color(red: 0.4, green: 0.5, blue: 0.92)       // #667eea
        let secondary = Color(red: 0.46, green: 0.29, blue: 0.64)   // #764ba2
        let accent = Color(red: 0.0, green: 0.78, blue: 0.78)       // cyan
        
        let success = Color(red: 0.16, green: 0.65, blue: 0.27)     // green
        let warning = Color(red: 1.0, green: 0.76, blue: 0.03)      // yellow
        let error = Color(red: 0.86, green: 0.21, blue: 0.27)       // red
        let info = Color(red: 0.13, green: 0.59, blue: 0.95)        // blue
        
        let background = Color(red: 0.06, green: 0.06, blue: 0.1)
        let surface = Color.white.opacity(0.08)
        let surfaceLight = Color.white.opacity(0.12)
        
        let textPrimary = Color.white
        let textSecondary = Color.white.opacity(0.7)
        let textMuted = Color.white.opacity(0.5)
    }
}

// MARK: - Liquid Gradient Background

struct LiquidGradientBackground: View {
    @State private var animateGradient = false
    
    var body: some View {
        ZStack {
            // Base gradient
            LinearGradient(
                colors: [
                    Color.liquidGlass.primary,
                    Color.liquidGlass.secondary,
                    Color.liquidGlass.primary.opacity(0.8)
                ],
                startPoint: animateGradient ? .topLeading : .bottomLeading,
                endPoint: animateGradient ? .bottomTrailing : .topTrailing
            )
            
            // Animated orbs
            GeometryReader { geometry in
                ForEach(0..<3) { index in
                    Circle()
                        .fill(
                            RadialGradient(
                                colors: [
                                    Color.liquidGlass.accent.opacity(0.3),
                                    Color.clear
                                ],
                                center: .center,
                                startRadius: 0,
                                endRadius: 200
                            )
                        )
                        .frame(width: 400, height: 400)
                        .offset(
                            x: animateGradient ? CGFloat(index * 100) : CGFloat(index * -100),
                            y: animateGradient ? CGFloat(index * 50) : CGFloat(index * -50)
                        )
                        .blur(radius: 60)
                }
            }
        }
        .ignoresSafeArea()
        .onAppear {
            withAnimation(.easeInOut(duration: 8).repeatForever(autoreverses: true)) {
                animateGradient.toggle()
            }
        }
    }
}

// MARK: - Glass Card

struct GlassCard<Content: View>: View {
    let content: Content
    var cornerRadius: CGFloat = 20
    var padding: CGFloat = 20
    
    init(cornerRadius: CGFloat = 20, padding: CGFloat = 20, @ViewBuilder content: () -> Content) {
        self.content = content()
        self.cornerRadius = cornerRadius
        self.padding = padding
    }
    
    var body: some View {
        content
            .padding(padding)
            .background(
                ZStack {
                    // Frosted glass effect
                    RoundedRectangle(cornerRadius: cornerRadius)
                        .fill(.ultraThinMaterial)
                    
                    // Subtle gradient overlay
                    RoundedRectangle(cornerRadius: cornerRadius)
                        .fill(
                            LinearGradient(
                                colors: [
                                    Color.white.opacity(0.15),
                                    Color.white.opacity(0.05)
                                ],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                    
                    // Border
                    RoundedRectangle(cornerRadius: cornerRadius)
                        .stroke(
                            LinearGradient(
                                colors: [
                                    Color.white.opacity(0.3),
                                    Color.white.opacity(0.1)
                                ],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ),
                            lineWidth: 1
                        )
                }
            )
            .shadow(color: Color.black.opacity(0.2), radius: 20, x: 0, y: 10)
    }
}

// MARK: - Glass Button

struct GlassButton: View {
    let title: String
    let icon: String?
    let style: ButtonStyle
    let action: () -> Void
    
    enum ButtonStyle {
        case primary, secondary, danger, success
        
        var gradient: LinearGradient {
            switch self {
            case .primary:
                return LinearGradient(
                    colors: [Color.liquidGlass.primary, Color.liquidGlass.secondary],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            case .secondary:
                return LinearGradient(
                    colors: [Color.white.opacity(0.2), Color.white.opacity(0.1)],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            case .danger:
                return LinearGradient(
                    colors: [Color.liquidGlass.error, Color.liquidGlass.error.opacity(0.8)],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            case .success:
                return LinearGradient(
                    colors: [Color.liquidGlass.success, Color.liquidGlass.success.opacity(0.8)],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            }
        }
    }
    
    init(_ title: String, icon: String? = nil, style: ButtonStyle = .primary, action: @escaping () -> Void) {
        self.title = title
        self.icon = icon
        self.style = style
        self.action = action
    }
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if let icon = icon {
                    Image(systemName: icon)
                }
                Text(title)
                    .fontWeight(.semibold)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .background(style.gradient)
            .foregroundColor(.white)
            .clipShape(Capsule())
            .shadow(color: Color.black.opacity(0.2), radius: 8, x: 0, y: 4)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Status Indicator

struct StatusIndicator: View {
    let status: AgentStatus
    var showLabel: Bool = true
    var size: CGFloat = 12
    
    var color: Color {
        switch status {
        case .idle: return .gray
        case .running: return Color.liquidGlass.success
        case .busy: return Color.liquidGlass.warning
        case .watching: return Color.liquidGlass.accent
        case .error: return Color.liquidGlass.error
        case .disconnected: return .gray
        case .stopped: return .gray
        case .unknown: return .gray
        }
    }
    
    var body: some View {
        HStack(spacing: 8) {
            ZStack {
                // Glow effect
                Circle()
                    .fill(color.opacity(0.3))
                    .frame(width: size + 8, height: size + 8)
                    .blur(radius: 4)
                
                // Main dot
                Circle()
                    .fill(color)
                    .frame(width: size, height: size)
                
                // Pulse animation for active states
                if status == .running || status == .busy || status == .watching {
                    Circle()
                        .stroke(color.opacity(0.5), lineWidth: 2)
                        .frame(width: size + 4, height: size + 4)
                        .modifier(PulseAnimation())
                }
            }
            
            if showLabel {
                Text(status.rawValue.capitalized)
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundColor(Color.liquidGlass.textSecondary)
            }
        }
    }
}

// MARK: - Pulse Animation Modifier

struct PulseAnimation: ViewModifier {
    @State private var isPulsing = false
    
    func body(content: Content) -> some View {
        content
            .scaleEffect(isPulsing ? 1.5 : 1)
            .opacity(isPulsing ? 0 : 1)
            .onAppear {
                withAnimation(.easeOut(duration: 1.5).repeatForever(autoreverses: false)) {
                    isPulsing = true
                }
            }
    }
}

// MARK: - Stat Card

struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        GlassCard(cornerRadius: 16, padding: 16) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: icon)
                        .font(.title2)
                        .foregroundColor(color)
                    Spacer()
                }
                
                Text(value)
                    .font(.system(size: 32, weight: .bold, design: .rounded))
                    .foregroundColor(Color.liquidGlass.textPrimary)
                
                Text(title)
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.textMuted)
                    .textCase(.uppercase)
                    .tracking(1)
            }
        }
    }
}

// MARK: - Connection Status Badge

struct ConnectionStatusBadge: View {
    @EnvironmentObject var viewModel: MonitorViewModel
    
    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(viewModel.isConnected ? Color.liquidGlass.success : Color.liquidGlass.error)
                .frame(width: 8, height: 8)
            
            Text(viewModel.isConnected ? "Connected" : "Disconnected")
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(.ultraThinMaterial)
        .clipShape(Capsule())
    }
}

// MARK: - Search Bar

struct GlassSearchBar: View {
    @Binding var text: String
    var placeholder: String = "Search..."
    var onSubmit: (() -> Void)?
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(Color.liquidGlass.textMuted)
            
            TextField(placeholder, text: $text)
                .textFieldStyle(.plain)
                .foregroundColor(Color.liquidGlass.textPrimary)
                .onSubmit {
                    onSubmit?()
                }
            
            if !text.isEmpty {
                Button {
                    text = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(Color.liquidGlass.textMuted)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(12)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.white.opacity(0.1), lineWidth: 1)
        )
    }
}

// MARK: - Badge

struct GlassBadge: View {
    let text: String
    let color: Color
    
    var body: some View {
        Text(text)
            .font(.caption2)
            .fontWeight(.bold)
            .foregroundColor(.white)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color)
            .clipShape(Capsule())
    }
}

// MARK: - Empty State

struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String
    var action: (() -> Void)?
    var actionTitle: String?
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: icon)
                .font(.system(size: 60))
                .foregroundColor(Color.liquidGlass.textMuted)
            
            Text(title)
                .font(.title2)
                .fontWeight(.semibold)
                .foregroundColor(Color.liquidGlass.textPrimary)
            
            Text(message)
                .font(.body)
                .foregroundColor(Color.liquidGlass.textSecondary)
                .multilineTextAlignment(.center)
            
            if let action = action, let actionTitle = actionTitle {
                GlassButton(actionTitle, icon: "plus", action: action)
            }
        }
        .padding(40)
    }
}

// MARK: - Loading Indicator

struct GlassLoadingIndicator: View {
    @State private var isAnimating = false
    
    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.white.opacity(0.2), lineWidth: 4)
                .frame(width: 40, height: 40)
            
            Circle()
                .trim(from: 0, to: 0.7)
                .stroke(
                    LinearGradient(
                        colors: [Color.liquidGlass.primary, Color.liquidGlass.accent],
                        startPoint: .leading,
                        endPoint: .trailing
                    ),
                    style: StrokeStyle(lineWidth: 4, lineCap: .round)
                )
                .frame(width: 40, height: 40)
                .rotationEffect(.degrees(isAnimating ? 360 : 0))
        }
        .onAppear {
            withAnimation(.linear(duration: 1).repeatForever(autoreverses: false)) {
                isAnimating = true
            }
        }
    }
}

// MARK: - Message Bubble

struct MessageBubble: View {
    let message: Message
    
    var bubbleColor: Color {
        switch message.type {
        case .agent: return Color.liquidGlass.info.opacity(0.3)
        case .human: return Color.orange.opacity(0.3)
        case .system: return Color.purple.opacity(0.3)
        case .tool: return Color.liquidGlass.success.opacity(0.3)
        }
    }
    
    var accentColor: Color {
        switch message.type {
        case .agent: return Color.liquidGlass.info
        case .human: return .orange
        case .system: return .purple
        case .tool: return Color.liquidGlass.success
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header
            HStack {
                Image(systemName: message.type.icon)
                    .foregroundColor(accentColor)
                
                Text(message.agentName)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(Color.liquidGlass.textPrimary)
                
                Spacer()
                
                Text(message.timestamp, style: .time)
                    .font(.caption)
                    .foregroundColor(Color.liquidGlass.textMuted)
                
                if message.isFlagged {
                    Image(systemName: "flag.fill")
                        .foregroundColor(Color.liquidGlass.warning)
                        .font(.caption)
                }
            }
            
            // Content
            Text(message.content)
                .font(.body)
                .foregroundColor(Color.liquidGlass.textPrimary)
                .lineLimit(nil)
            
            // Metadata
            if let metadata = message.metadata, !metadata.isEmpty {
                HStack {
                    ForEach(Array(metadata.keys.prefix(3)), id: \.self) { key in
                        Text("\(key): \(metadata[key] ?? "")")
                            .font(.caption2)
                            .foregroundColor(Color.liquidGlass.textMuted)
                    }
                }
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(bubbleColor)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(accentColor.opacity(0.3), lineWidth: 1)
                )
        )
        .overlay(
            Rectangle()
                .fill(accentColor)
                .frame(width: 4)
                .clipShape(RoundedRectangle(cornerRadius: 2)),
            alignment: .leading
        )
    }
}

// MARK: - Task Card

struct TaskCard: View {
    let task: AgentTask
    var onStart: (() -> Void)?
    var onCancel: (() -> Void)?
    
    var statusColor: Color {
        switch task.status {
        case .pending: return Color.liquidGlass.warning
        case .working: return Color.liquidGlass.info
        case .completed: return Color.liquidGlass.success
        case .failed: return Color.liquidGlass.error
        case .cancelled: return .gray
        }
    }
    
    var priorityColor: Color {
        switch task.priority {
        case .low: return Color.liquidGlass.success
        case .normal: return Color.liquidGlass.warning
        case .high: return .orange
        case .urgent: return Color.liquidGlass.error
        }
    }
    
    var body: some View {
        GlassCard(cornerRadius: 16, padding: 16) {
            VStack(alignment: .leading, spacing: 12) {
                // Header
                HStack {
                    Image(systemName: task.status.icon)
                        .foregroundColor(statusColor)
                    
                    Text(task.title)
                        .font(.headline)
                        .foregroundColor(Color.liquidGlass.textPrimary)
                        .lineLimit(1)
                    
                    Spacer()
                    
                    GlassBadge(text: task.priority.label, color: priorityColor)
                }
                
                // Description
                if !task.description.isEmpty {
                    Text(task.description)
                        .font(.subheadline)
                        .foregroundColor(Color.liquidGlass.textSecondary)
                        .lineLimit(2)
                }
                
                // Footer
                HStack {
                    Text(task.createdAt, style: .relative)
                        .font(.caption)
                        .foregroundColor(Color.liquidGlass.textMuted)
                    
                    Spacer()
                    
                    GlassBadge(text: task.status.rawValue.capitalized, color: statusColor)
                }
                
                // Actions
                if task.status == .pending {
                    HStack(spacing: 12) {
                        if let onStart = onStart {
                            GlassButton("Start", icon: "play.fill", style: .primary, action: onStart)
                        }
                        if let onCancel = onCancel {
                            GlassButton("Cancel", icon: "xmark", style: .secondary, action: onCancel)
                        }
                    }
                }
            }
        }
    }
}

// MARK: - Codebase Card

struct CodebaseCard: View {
    let codebase: Codebase
    var onTrigger: (() -> Void)?
    var onWatch: (() -> Void)?
    var onDelete: (() -> Void)?
    
    var body: some View {
        GlassCard(cornerRadius: 16, padding: 16) {
            VStack(alignment: .leading, spacing: 12) {
                // Header
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(codebase.name)
                            .font(.headline)
                            .foregroundColor(Color.liquidGlass.textPrimary)
                        
                        Text(codebase.path)
                            .font(.caption)
                            .foregroundColor(Color.liquidGlass.textMuted)
                            .lineLimit(1)
                    }
                    
                    Spacer()
                    
                    StatusIndicator(status: codebase.status)
                }
                
                // Description
                if let description = codebase.description {
                    Text(description)
                        .font(.subheadline)
                        .foregroundColor(Color.liquidGlass.textSecondary)
                        .lineLimit(2)
                }
                
                // Task badges
                if codebase.pendingTasks > 0 || codebase.workingTasks > 0 {
                    HStack(spacing: 8) {
                        if codebase.pendingTasks > 0 {
                            GlassBadge(text: "\(codebase.pendingTasks) pending", color: Color.liquidGlass.warning)
                        }
                        if codebase.workingTasks > 0 {
                            GlassBadge(text: "\(codebase.workingTasks) working", color: Color.liquidGlass.info)
                        }
                    }
                }
                
                // Actions
                HStack(spacing: 12) {
                    if let onTrigger = onTrigger {
                        GlassButton("Trigger", icon: "bolt.fill", style: .primary, action: onTrigger)
                    }
                    
                    if let onWatch = onWatch {
                        GlassButton(
                            codebase.status == .watching ? "Stop" : "Watch",
                            icon: codebase.status == .watching ? "eye.slash" : "eye",
                            style: .secondary,
                            action: onWatch
                        )
                    }
                    
                    Spacer()
                    
                    if let onDelete = onDelete {
                        Button(action: onDelete) {
                            Image(systemName: "trash")
                                .foregroundColor(Color.liquidGlass.error)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }
}

// MARK: - Output Entry View

struct OutputEntryView: View {
    let entry: OutputEntry
    
    var typeColor: Color {
        switch entry.type {
        case .text: return Color.liquidGlass.accent
        case .reasoning: return Color.liquidGlass.warning
        case .toolPending: return Color.liquidGlass.info
        case .toolRunning: return .orange
        case .toolCompleted: return Color.liquidGlass.success
        case .toolError: return Color.liquidGlass.error
        case .stepStart, .stepFinish: return .purple
        case .fileEdit: return Color.liquidGlass.success
        case .command: return Color.liquidGlass.warning
        case .status: return Color.liquidGlass.info
        case .diagnostics: return Color.liquidGlass.accent
        case .error: return Color.liquidGlass.error
        }
    }
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Type indicator
            RoundedRectangle(cornerRadius: 2)
                .fill(typeColor)
                .frame(width: 4)
            
            VStack(alignment: .leading, spacing: 8) {
                // Header
                HStack {
                    Image(systemName: entry.type.icon)
                        .foregroundColor(typeColor)
                    
                    Text(entry.type.label)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(Color.liquidGlass.textSecondary)
                    
                    Spacer()
                    
                    Text(entry.timestamp, style: .time)
                        .font(.caption2)
                        .foregroundColor(Color.liquidGlass.textMuted)
                }
                
                // Content
                Text(entry.content)
                    .font(.system(.body, design: .monospaced))
                    .foregroundColor(Color.liquidGlass.textPrimary)
                    .lineLimit(nil)
                
                // Tool info
                if let toolName = entry.toolName {
                    HStack {
                        Image(systemName: "wrench.fill")
                            .font(.caption)
                        Text(toolName)
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                    .foregroundColor(typeColor)
                }
                
                // Tool output
                if let output = entry.toolOutput {
                    Text(output)
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(Color.liquidGlass.textMuted)
                        .padding(8)
                        .background(Color.black.opacity(0.3))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .lineLimit(10)
                }
                
                // Error
                if let error = entry.error {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(Color.liquidGlass.error)
                }
                
                // Tokens
                if let tokens = entry.tokens {
                    HStack {
                        Text("Tokens: \(tokens.input) in / \(tokens.output) out")
                            .font(.caption2)
                            .foregroundColor(Color.liquidGlass.textMuted)
                        
                        if let cost = entry.cost {
                            Text("Cost: $\(String(format: "%.4f", cost))")
                                .font(.caption2)
                                .foregroundColor(Color.liquidGlass.success)
                        }
                    }
                }
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.black.opacity(0.2))
        )
    }
}

// MARK: - Filter Chip

struct FilterChip: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline)
                .fontWeight(isSelected ? .semibold : .regular)
                .foregroundColor(isSelected ? .white : Color.liquidGlass.textSecondary)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(
                    Capsule()
                        .fill(isSelected ? Color.liquidGlass.primary : Color.white.opacity(0.1))
                )
                .overlay(
                    Capsule()
                        .stroke(Color.white.opacity(0.2), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
    }
}
