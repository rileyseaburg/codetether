# A2A Monitor - Swift Liquid Glass UI

A modern, fluid SwiftUI interface for monitoring A2A agent conversations with Apple's signature "Liquid Glass" aesthetic.

## Features

- **Real-time Monitoring**: Watch agent conversations as they happen via Server-Sent Events (SSE)
- **CodeTether Integration**: Register codebases, trigger AI agents, and manage watch mode
- **Task Queue**: Create and manage tasks that agents can pick up automatically
- **Agent Output**: Stream real-time output including tool calls, reasoning, and responses
- **Human Intervention**: Send messages directly to active agents
- **Liquid Glass Design**: Beautiful frosted glass UI with vibrant gradients and fluid animations

## Screenshots

The UI features a modern glassmorphism design with:
- Animated gradient backgrounds
- Frosted glass cards with subtle borders
- Pulsing status indicators
- Smooth transitions and animations

## Requirements

- iOS 17.0+ / macOS 14.0+
- Xcode 15.0+
- Swift 5.9+

## Building

### As a Swift Package

The project is structured as a Swift Package for easy integration:

```bash
cd ui/swift/A2AMonitor
swift build
```

### As an Xcode Project

1. Open the `A2AMonitor` folder in Xcode
2. Select your target device (iOS or macOS)
3. Build and run (Cmd+R)

### Creating an Xcode Project

To create a standalone Xcode project:

```bash
# Create a new iOS/macOS app in Xcode
# Add the A2AMonitor package as a local package dependency
# Point to: ui/swift/A2AMonitor
```

## Project Structure

```
A2AMonitor/
├── Package.swift                 # Swift Package manifest
├── Sources/
│   └── A2AMonitor/
│       ├── A2AMonitorApp.swift   # App entry point
│       ├── Models/
│       │   └── Models.swift      # Data models (Agent, Message, Task, etc.)
│       ├── Services/
│       │   ├── A2AClient.swift   # API client with SSE support
│       │   └── MonitorViewModel.swift  # Main view model
│       ├── Components/
│       │   └── LiquidGlassComponents.swift  # Reusable UI components
│       ├── Views/
│       │   ├── DashboardView.swift    # Main overview
│       │   ├── AgentsView.swift       # Agent management
│       │   ├── MessagesView.swift     # Conversation view
│       │   ├── TasksView.swift        # Task queue
│       │   └── AgentOutputView.swift  # Real-time output
│       └── Extensions/
│           └── Extensions.swift       # Swift extensions
```

## Configuration

The app connects to the A2A server at `http://localhost:8000` by default. You can change this in Settings (macOS) or in the app's configuration.

### Environment Variables

- `A2A_SERVER_URL`: Override the default server URL

## UI Components

### Liquid Glass Components

The UI includes custom SwiftUI components following the Liquid Glass design system:

- `GlassCard`: Frosted glass container with gradient overlay
- `GlassButton`: Stylized buttons with gradient backgrounds
- `StatusIndicator`: Animated status dots with pulse effects
- `StatCard`: Statistics display cards
- `GlassSearchBar`: Search input with glass styling
- `MessageBubble`: Conversation message display
- `TaskCard`: Task queue item display
- `CodebaseCard`: Agent/codebase display
- `OutputEntryView`: Agent output stream entry

### Color Theme

```swift
Color.liquidGlass.primary      // #667eea (purple-blue)
Color.liquidGlass.secondary    // #764ba2 (purple)
Color.liquidGlass.accent       // cyan
Color.liquidGlass.success      // green
Color.liquidGlass.warning      // yellow
Color.liquidGlass.error        // red
Color.liquidGlass.info         // blue
```

## API Endpoints

The app communicates with the following A2A server endpoints:

### Monitor API
- `GET /v1/monitor/stream` - SSE stream for real-time updates
- `GET /v1/monitor/agents` - List all agents
- `GET /v1/monitor/messages` - Get message history
- `POST /v1/monitor/intervene` - Send human intervention

### CodeTether API
- `GET /v1/agent/status` - CodeTether integration status
- `GET /v1/agent/codebases` - List registered codebases
- `POST /v1/agent/codebases` - Register new codebase
- `POST /v1/agent/codebases/{id}/trigger` - Trigger agent
- `POST /v1/agent/codebases/{id}/watch/start` - Start watch mode
- `GET /v1/agent/tasks` - List tasks

## Keyboard Shortcuts (macOS)

- `Cmd+N`: Create new task
- `Cmd+R`: Refresh data
- `Escape`: Close modals

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is part of the A2A-Server-MCP project. See the main LICENSE file for details.
