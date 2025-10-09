# A2A Server Monitoring UI

Real-time web interface for monitoring agent conversations, enabling human intervention, and maintaining audit logs.

## Features

- 🔴 **Real-time Monitoring**: Live stream of all agent conversations via Server-Sent Events (SSE)
- 👁️ **Full Auditability**: Complete conversation history with timestamps and metadata
- ✋ **Human Intervention**: Send messages or instructions to any active agent
- 📊 **Statistics Dashboard**: Response times, tool usage, error tracking, token counts
- 🔍 **Search & Filter**: Find specific messages, filter by type (agent/human/system/tool)
- 💾 **Export Logs**: Download conversation logs as JSON, CSV, or HTML reports
- 🎯 **Agent Tracking**: Monitor active agents and their status
- 🚩 **Message Flagging**: Flag important messages for review
- ⏸️ **Pause/Resume**: Control monitoring flow

## Quick Start

### Access the UI

**Production**:
```
https://acp.quantum-forge.net/v1/monitor/
```

**Local Development**:
```
http://localhost:8000/v1/monitor/
```

**Port-Forwarded Kubernetes**:
```bash
kubectl port-forward -n a2a-system svc/a2a-server 8000:8000
# Then open: http://localhost:8000/v1/monitor/
```

## UI Layout

```
┌──────────────────────────────────────────────────────────────────┐
│                   A2A Agent Monitor Header                        │
│  Connection Status │ Active Agents │ Messages │ Interventions    │
└──────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────┬────────────────────────────────┐
│                                 │                                │
│  💬 Live Conversation           │  📊 Statistics                 │
│                                 │     Avg Response, Tool Calls   │
│  [All] [Agents] [Human] [System]│                                │
│  🔍 Search messages...          │  🤖 Active Agents             │
│                                 │     • Agent 1 (active)         │
│  Agent 1: Message text...       │     • Agent 2 (idle)           │
│  [🚩 Flag] [✋ Intervene] [📋 Copy] │                              │
│                                 │  ✋ Human Intervention         │
│  Human: Intervention message... │     [Select Agent ▼]           │
│                                 │     [Message text...]          │
│  Agent 2: Response...           │     [Send Intervention]        │
│                                 │                                │
│  System: Task completed         │  💾 Export & Logs              │
│                                 │     [JSON] [CSV] [HTML]        │
│  (Auto-scrolling)               │     [Clear] [Pause]            │
│                                 │                                │
└─────────────────────────────────┴────────────────────────────────┘
```

## Using the Interface

### Viewing Conversations

1. **Real-time Updates**: Messages appear automatically as agents communicate
2. **Message Types**: Color-coded by type:
   - 🔵 Blue: Agent messages
   - 🟠 Orange: Human interventions
   - 🟣 Purple: System messages
   - 🟢 Green: Tool calls

3. **Message Actions**:
   - **Flag (🚩)**: Mark message for later review
   - **Intervene (✋)**: Respond to specific message
   - **Copy (📋)**: Copy message to clipboard

### Filtering & Search

- **Filter Buttons**: Click to show only specific message types
- **Search Box**: Type keywords to find specific messages
- **Clear Search**: Delete text to show all messages again

### Human Intervention

1. Select target agent from dropdown
2. Enter your message or instruction
3. Click "Send Intervention"
4. Message appears in conversation and is sent to agent

**Use Cases**:
- Correct agent behavior
- Provide additional context
- Override agent decisions
- Emergency stop
- Guide conversation direction

### Statistics

Monitor in real-time:
- **Avg Response**: Average agent response time (ms)
- **Tool Calls**: Number of MCP tool invocations
- **Errors**: Count of errors encountered
- **Tokens Used**: Total token consumption

### Exporting Logs

Click export buttons to download:
- **JSON**: Machine-readable format with full metadata
- **CSV**: Spreadsheet-compatible format
- **HTML**: Formatted report for human review

Exports include:
- All messages with timestamps
- Agent names and types
- Metadata and statistics
- Response times
- Error information

## API Endpoints

The monitoring UI uses these backend endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/monitor/` | GET | Serve monitoring UI (HTML) |
| `/v1/monitor/stream` | GET | SSE stream for real-time updates |
| `/v1/monitor/agents` | GET | List active agents |
| `/v1/monitor/messages` | GET | Get message history |
| `/v1/monitor/stats` | GET | Get statistics |
| `/v1/monitor/intervene` | POST | Send human intervention |
| `/v1/monitor/export/json` | GET | Export as JSON |
| `/v1/monitor/export/csv` | GET | Export as CSV |

### Example: Send Intervention

```bash
curl -X POST https://acp.quantum-forge.net/v1/monitor/intervene \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-123",
    "message": "Please provide more detail",
    "timestamp": "2025-10-09T12:00:00Z"
  }'
```

### Example: Get Messages

```bash
# Get last 50 messages
curl "https://acp.quantum-forge.net/v1/monitor/messages?limit=50"

# Get only agent messages
curl "https://acp.quantum-forge.net/v1/monitor/messages?type=agent&limit=100"
```

## Integration with A2A Server

The monitoring service automatically logs:
- All incoming client messages
- All agent responses
- Tool calls (MCP)
- System events
- Errors and exceptions

### Programmatic Logging

In your agent code:

```python
from a2a_server.monitor_api import log_agent_message

# Log a message
await log_agent_message(
    agent_name="My Agent",
    content="Processing request...",
    message_type="agent",
    metadata={"task_id": "123"},
    response_time=150,  # milliseconds
    tokens=50
)

# Log tool call
await log_agent_message(
    agent_name="Calculator Agent",
    content="Called calculator tool: add(10, 5)",
    message_type="tool",
    metadata={"tool": "calculator", "operation": "add"}
)

# Log error
await log_agent_message(
    agent_name="Worker Agent",
    content="Failed to process task",
    message_type="error",
    error="Connection timeout",
    metadata={"task_id": "456"}
)
```

## Security Considerations

### Access Control

The monitoring UI should be protected in production:

1. **Add Authentication**:
   ```python
   # In a2a_server/monitor_api.py
   from fastapi.security import HTTPBasic, HTTPBasicCredentials

   security = HTTPBasic()

   @monitor_router.get("/")
   async def serve_monitor_ui(credentials: HTTPBasicCredentials = Depends(security)):
       # Verify credentials
       ...
   ```

2. **Use Ingress Auth**:
   ```yaml
   # In Helm values
   ingress:
     annotations:
       nginx.ingress.kubernetes.io/auth-type: basic
       nginx.ingress.kubernetes.io/auth-secret: monitor-auth
       nginx.ingress.kubernetes.io/auth-realm: 'A2A Monitor'
   ```

3. **Network Policies**:
   ```bash
   # Restrict access to monitoring endpoints
   kubectl apply -f network-policy-monitor.yaml
   ```

### Data Privacy

- Logs may contain sensitive information
- Consider data retention policies
- Implement automatic log rotation
- Use encryption for exported data

## Troubleshooting

### UI Not Loading

```bash
# Check if endpoint exists
curl https://acp.quantum-forge.net/v1/monitor/

# Verify ui directory in container
kubectl exec -n a2a-system <pod-name> -- ls -la /app/ui

# Check logs
kubectl logs -n a2a-system <pod-name> | grep monitor
```

### No Real-time Updates

- Check browser console for SSE errors
- Verify `/v1/monitor/stream` endpoint is accessible
- Check for proxy/firewall blocking SSE connections
- Ensure CORS is properly configured

### Messages Not Appearing

```bash
# Verify monitoring service is logging
kubectl logs -n a2a-system <pod-name> | grep "Logged message"

# Check if agents are registered
curl https://acp.quantum-forge.net/v1/monitor/agents

# Test manual logging
curl -X POST https://acp.quantum-forge.net/v1/monitor/intervene \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"test","message":"test"}'
```

### Interventions Not Working

- Verify agent ID is correct
- Check agent is still active
- Review agent logs for intervention handling
- Ensure agent subscribed to intervention events

## Customization

### Change UI Theme

Edit `ui/monitor.html`:

```css
/* Change color scheme */
body {
    background: linear-gradient(135deg, #your-color 0%, #your-color2 100%);
}

.message.agent {
    background: linear-gradient(135deg, #custom-blue 0%, #custom-blue2 100%);
}
```

### Add Custom Filters

Edit `ui/monitor.js`:

```javascript
// Add custom filter
window.filterByError = () => {
    document.querySelectorAll('.message').forEach(msg => {
        const hasError = msg.querySelector('.message-details').textContent.includes('error');
        msg.style.display = hasError ? 'block' : 'none';
    });
};
```

### Custom Export Formats

Extend `a2a_server/monitor_api.py`:

```python
@monitor_router.get("/export/xml")
async def export_xml(limit: int = 1000):
    messages = monitoring_service.get_messages(limit=limit)
    # Convert to XML
    return Response(content=xml_content, media_type="application/xml")
```

## Best Practices

1. **Regular Exports**: Download logs periodically for backup
2. **Monitor Statistics**: Watch for unusual patterns (high errors, slow responses)
3. **Use Interventions Sparingly**: Let agents work autonomously when possible
4. **Flag Important Messages**: Mark key decisions or errors for review
5. **Search Before Intervening**: Check conversation history first
6. **Clear Old Logs**: Prevent UI slowdown with too many messages
7. **Pause When Needed**: Stop monitoring during non-critical periods

## Files

- `ui/monitor.html` - Main HTML interface
- `ui/monitor.js` - JavaScript client code
- `a2a_server/monitor_api.py` - FastAPI backend endpoints
- `a2a_server/server.py` - Integration with A2A server

## Support

For issues or questions:
- GitHub Issues: https://github.com/rileyseaburg/A2A-Server-MCP/issues
- Documentation: [ACP_DEPLOYMENT.md](../ACP_DEPLOYMENT.md)
- Main README: [README.md](../README.md)
