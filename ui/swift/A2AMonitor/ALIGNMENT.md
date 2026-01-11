# A2AMonitor iOS App Alignment

## Overview

A2AMonitor is a SwiftUI iOS application for monitoring and managing A2A agent workflows. It provides real-time visibility into agent activities, task management, and the ability to intervene in agent operations.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      A2AMonitor App                         │
├─────────────────────────────────────────────────────────────┤
│  Views/                                                     │
│  ├── DashboardView.swift    - Main dashboard                │
│  ├── AgentsView.swift       - Agent status list             │
│  ├── TasksView.swift        - Task queue management         │
│  ├── SessionsView.swift     - Session history               │
│  ├── MessagesView.swift     - Monitor message feed          │
│  └── AgentOutputView.swift  - Live agent output streaming   │
├─────────────────────────────────────────────────────────────┤
│  Services/                                                  │
│  ├── A2AClient.swift        - REST/SSE API client           │
│  ├── AuthService.swift      - Keycloak OIDC authentication  │
│  ├── NotificationService.swift - Local notifications        │
│  └── MonitorViewModel.swift - State management              │
├─────────────────────────────────────────────────────────────┤
│  Voice/                                                     │
│  ├── VoiceChatView.swift    - Voice interaction UI          │
│  ├── VoiceSessionManager.swift - Audio session handling     │
│  └── VoiceButton.swift      - Push-to-talk control          │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### Real-time Monitoring

- SSE connection to `/v1/monitor/stream`
- Live agent status updates
- Message feed with filtering

### Notifications

- **Local notifications** triggered when SSE events arrive
- Shows agent messages, interventions, errors
- Badge count management
- Works in foreground and background (while connected)

### Task Management

- View pending/active/completed tasks
- Create new tasks for codebases
- Cancel running tasks

### Session Management

- Browse session history per codebase
- Resume sessions with new prompts
- View session messages and tool calls

### Agent Control

- Trigger agents on codebases
- Send interventions to running agents
- Stop/interrupt agent execution

## API Integration

### A2AClient.swift

```swift
// SSE Streaming
func connectToMonitorStream()
func connectToAgentEvents(codebaseId: String, onEvent: @escaping (AgentEvent) -> Void)

// Codebases
func fetchCodebases() async throws -> [Codebase]
func registerCodebase(name: String, path: String, description: String?) async throws -> Codebase

// Tasks
func fetchTasks() async throws -> [AgentTask]
func createTask(codebaseId: String, title: String, ...) async throws -> AgentTask
func cancelTask(taskId: String) async throws

// Sessions
func fetchSessions(codebaseId: String) async throws -> [SessionSummary]
func resumeSession(codebaseId: String, sessionId: String, prompt: String?, ...) async throws -> Bool

// Agent Control
func triggerAgent(codebaseId: String, prompt: String, agent: String, model: String?) async throws
func sendAgentMessage(codebaseId: String, message: String, agent: String?) async throws
func interruptAgent(codebaseId: String) async throws
func stopAgent(codebaseId: String) async throws
```

## Notification Flow

1. **OpenCode Worker** completes task
2. Worker calls `POST /v1/monitor/intervene` with message
3. **A2A Server** broadcasts via SSE to `/v1/monitor/stream`
4. **iOS App** receives SSE event in `A2AClient`
5. `NotificationService.notifyIfNeeded()` triggered
6. **Local notification** displayed to user

### NotificationService.swift

```swift
// Settings
var isEnabled: Bool       // Global enable/disable
var agentOnly: Bool       // Only notify for agent messages (recommended)

// Methods
func configure()          // Set up notification delegate
func requestAuthorizationIfNeeded() async
func notifyIfNeeded(for message: Message)
func sendTestNotification()
```

## Authentication

Uses Keycloak OIDC via `AuthService.swift`:

- Token refresh handling
- Secure credential storage
- Authorization header injection

## Data Models

### Message

```swift
struct Message: Codable, Identifiable {
    let id: String
    let timestamp: Date
    let type: MessageType  // .agent, .system, .human, .tool, .error
    let agentName: String
    let content: String
}
```

### AgentTask

```swift
struct AgentTask: Codable, Identifiable {
    let id: String
    let codebaseId: String
    let title: String
    let status: TaskStatus  // .pending, .running, .completed, .failed, .cancelled
    let priority: TaskPriority
    let createdAt: Date
    let result: String?
    let error: String?
}
```

### Codebase

```swift
struct Codebase: Codable, Identifiable {
    let id: String
    let name: String
    let path: String
    let description: String?
    let status: CodebaseStatus  // .idle, .running, .error
    let workerId: String?
}
```

## Building

```bash
cd ui/swift/A2AMonitor
swift build
# Or open in Xcode
open Package.swift
```

## Configuration

Set the API base URL in `A2AClient`:

```swift
init(baseURL: String = "https://api.codetether.run")
```

Or update dynamically:

```swift
client.updateBaseURL("https://your-a2a-server.com")
```

## TODO

- [ ] **APNs Push Notifications** - Currently uses local notifications which only work when app is running. Need to integrate Apple Push Notification service for true push when app is closed.
- [ ] Deep linking from notification tap to specific task/session
- [ ] Offline support with local caching
- [ ] Voice command integration improvements
- [ ] Widget for quick status overview
- [ ] Watch app companion
