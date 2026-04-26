# Quick Reference: MCP Configuration for Cline/Claude Dev

## Where to Add Configuration

**File Location:**
- **Windows**: `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- **macOS**: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
- **Linux**: `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

## Configuration Templates

### 1. Local Development (Port-Forwarded Kubernetes)

```json
{
  "mcpServers": {
    "a2a-server-local": {
      "command": "python",
      "args": [
        "C:/Users/riley/programming/A2A-Server-MCP/examples/mcp_external_client.py",
        "--endpoint",
        "http://localhost:9000/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": [
        "calculator",
        "text_analyzer"
      ]
    }
  }
}
```

**Setup:**
```bash
# Start port-forward
kubectl port-forward -n a2a-system svc/a2a-server 9000:9000
```

---

### 2. Production Deployment (Public Endpoint)

```json
{
  "mcpServers": {
    "a2a-server-production": {
      "command": "python",
      "args": [
        "C:/Users/riley/programming/A2A-Server-MCP/examples/mcp_external_client.py",
        "--endpoint",
        "https://a2a.example.com/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": [
        "calculator",
        "text_analyzer",
        "weather_info"
      ]
    }
  }
}
```

**Requirements:**
- Ingress configured with TLS
- Public DNS pointing to LoadBalancer/Ingress
- Port 9000 exposed

---

### 3. Kubernetes Internal (In-Cluster Agents)

```json
{
  "mcpServers": {
    "a2a-server-k8s": {
      "command": "python",
      "args": [
        "/app/examples/mcp_external_client.py",
        "--endpoint",
        "http://a2a-server.a2a-system.svc.cluster.local:9000/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

**Use Case:** Agents running as pods in the same Kubernetes cluster

---

### 4. Multiple Environments

```json
{
  "mcpServers": {
    "a2a-production": {
      "command": "python",
      "args": [
        "examples/mcp_external_client.py",
        "--endpoint",
        "https://a2a.example.com/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": ["calculator"]
    },
    "a2a-staging": {
      "command": "python",
      "args": [
        "examples/mcp_external_client.py",
        "--endpoint",
        "https://a2a-staging.example.com/mcp/v1/rpc"
      ],
      "disabled": true,
      "autoApprove": []
    },
    "a2a-local": {
      "command": "python",
      "args": [
        "examples/mcp_external_client.py",
        "--endpoint",
        "http://localhost:9000/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": ["calculator", "text_analyzer", "memory_store"]
    }
  }
}
```

---

## Configuration Options Explained

| Option | Description | Example |
|--------|-------------|---------|
| `command` | Python executable | `"python"` or `"python3"` |
| `args` | Command arguments | Path to client script + `--endpoint` URL |
| `disabled` | Enable/disable server | `false` to enable, `true` to disable |
| `autoApprove` | Tools to auto-approve | `["calculator", "text_analyzer"]` |

---

## Available Tools to Auto-Approve

- `calculator` - Math operations (add, subtract, multiply, divide, square, sqrt)
- `text_analyzer` - Text statistics (word count, character count, etc.)
- `weather_info` - Mock weather data
- `memory_store` - Shared memory for agent coordination

---

## Testing Your Configuration

### 1. Verify Endpoint is Reachable

```bash
# Test MCP health
curl http://localhost:9000/

# List available tools
curl http://localhost:9000/mcp/v1/tools
```

### 2. Test with Python Client

```bash
# Run the example client
python examples/mcp_external_client.py
```

### 3. Reload Cline/Claude Dev

1. Open VS Code Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`)
2. Run: `Developer: Reload Window`
3. Cline should now show the MCP server connection

---

## Troubleshooting

### Issue: "Connection refused"

**Solution:**
```bash
# Check if service is running
kubectl get svc -n a2a-system

# Start port-forward
kubectl port-forward -n a2a-system svc/a2a-server 9000:9000
```

### Issue: "Module not found: mcp_external_client"

**Solution:**
- Use full absolute path to the script
- Ensure Python can import from the examples directory

```json
"args": [
  "C:/Users/riley/programming/A2A-Server-MCP/examples/mcp_external_client.py",
  "--endpoint",
  "http://localhost:9000/mcp/v1/rpc"
]
```

### Issue: "Tool not found"

**Solution:**
- Verify MCP server is running with enhanced mode:
  ```bash
  python run_server.py run --enhanced
  ```
- Check available tools:
  ```bash
  curl http://localhost:9000/mcp/v1/tools
  ```

### Issue: Auto-approve not working

**Solution:**
- Tool names are case-sensitive
- Use exact tool names from `/mcp/v1/tools`
- Reload VS Code after configuration changes

---

## Full Working Example

**File:** `cline_mcp_settings.json`

```json
{
  "mcpServers": {
    "a2a-server-mcp": {
      "command": "python",
      "args": [
        "C:/Users/riley/programming/A2A-Server-MCP/examples/mcp_external_client.py",
        "--endpoint",
        "http://localhost:9000/mcp/v1/rpc"
      ],
      "disabled": false,
      "autoApprove": [
        "calculator",
        "text_analyzer",
        "weather_info",
        "memory_store"
      ]
    }
  }
}
```

**Start Server:**
```bash
# In terminal 1
python run_server.py run --enhanced

# In terminal 2 (if using Kubernetes)
kubectl port-forward -n a2a-system svc/a2a-server 8000:8000 9000:9000
```

**Reload VS Code** and Cline will connect to the MCP server!

---

## Next Steps

1. ✅ Copy appropriate configuration template above
2. ✅ Update paths and endpoints for your environment
3. ✅ Save to `cline_mcp_settings.json`
4. ✅ Start A2A server with MCP enabled
5. ✅ Reload VS Code
6. ✅ Test in Cline chat: "Use the calculator tool to add 5 + 3"

For complete deployment guide: [HELM_OCI_DEPLOYMENT.md](HELM_OCI_DEPLOYMENT.md)
