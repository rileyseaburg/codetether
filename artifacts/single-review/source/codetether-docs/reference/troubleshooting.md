---
title: Troubleshooting
description: Common issues and solutions for CodeTether Server
---

# Troubleshooting

This guide covers common issues you may encounter when running CodeTether Server and how to resolve them.

## SSL/TLS Certificate Errors

### "Unable to verify the first certificate"

This error occurs when connecting to the A2A server via SSE (Server-Sent Events) and the server uses a self-signed certificate or a certificate from an untrusted Certificate Authority.

**Error message:**

```
a2a-server SSE error: unable to verify the first certificate
```

**Causes:**

- Self-signed certificate on the server
- Certificate signed by an internal/private CA
- Missing intermediate certificates in the certificate chain
- Expired or invalid certificate

### Solutions

#### Option 1: Development/Testing Only - Disable Certificate Verification

!!! warning "Security Risk"
    This disables all certificate verification and should **never** be used in production environments.

Set the environment variable before starting your MCP client:

```bash
export NODE_TLS_REJECT_UNAUTHORIZED=0
```

For MCP configuration files (e.g., VS Code, Cline, Claude Desktop):

```json
{
  "mcpServers": {
    "a2a-server": {
      "command": "npx",
      "args": ["-y", "@anthropic/a2a-mcp-client"],
      "env": {
        "NODE_TLS_REJECT_UNAUTHORIZED": "0",
        "A2A_SERVER_URL": "https://your-server:8080"
      }
    }
  }
}
```

#### Option 2: Trust the Server Certificate (Recommended for Internal CAs)

If your server uses a self-signed certificate or internal CA, add it to your system's trusted certificates.

**Step 1: Export the certificate**

```bash
openssl s_client -connect your-server:443 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM > server.crt
```

**Step 2: Add to trusted certificates**

=== "Linux (Debian/Ubuntu)"

    ```bash
    sudo cp server.crt /usr/local/share/ca-certificates/
    sudo update-ca-certificates
    ```

=== "Linux (RHEL/CentOS)"

    ```bash
    sudo cp server.crt /etc/pki/ca-trust/source/anchors/
    sudo update-ca-trust
    ```

=== "macOS"

    ```bash
    sudo security add-trusted-cert -d -r trustRoot \
      -k /Library/Keychains/System.keychain server.crt
    ```

=== "Windows"

    ```powershell
    Import-Certificate -FilePath server.crt -CertStoreLocation Cert:\LocalMachine\Root
    ```

**Step 3: For Node.js applications**

You can also specify the certificate directly:

```bash
export NODE_EXTRA_CA_CERTS=/path/to/server.crt
```

Or in MCP configuration:

```json
{
  "mcpServers": {
    "a2a-server": {
      "command": "npx",
      "args": ["-y", "@anthropic/a2a-mcp-client"],
      "env": {
        "NODE_EXTRA_CA_CERTS": "/path/to/server.crt",
        "A2A_SERVER_URL": "https://your-server:8080"
      }
    }
  }
}
```

#### Option 3: Use a Valid Certificate (Recommended for Production)

For production deployments, use a certificate from a trusted Certificate Authority:

- **Let's Encrypt**: Free, automated certificates via [certbot](https://certbot.eff.org/)
- **Commercial CAs**: DigiCert, Comodo, GlobalSign, etc.

See the [Production Checklist](../deployment/production.md) for TLS configuration guidance.

#### Option 4: Fix Certificate Chain Issues

If you have a valid certificate but are missing intermediate certificates:

```bash
# Check the certificate chain
openssl s_client -connect your-server:443 -showcerts

# Combine certificates in correct order
cat your-cert.crt intermediate.crt root.crt > fullchain.crt
```

Ensure your server is configured to serve the full certificate chain.

---

## Connection Errors

### "Connection refused"

**Causes:**

- Server is not running
- Wrong port number
- Firewall blocking the connection

**Solutions:**

1. Verify the server is running:
   ```bash
   curl -v http://localhost:8080/health
   ```

2. Check the correct port in your configuration:
   ```bash
   grep -i port .env
   ```

3. Check firewall rules:
   ```bash
   sudo ufw status  # Ubuntu
   sudo firewall-cmd --list-all  # RHEL/CentOS
   ```

### "Connection timeout"

**Causes:**

- Network connectivity issues
- Server overloaded
- DNS resolution problems

**Solutions:**

1. Test basic connectivity:
   ```bash
   ping your-server
   telnet your-server 8080
   ```

2. Check DNS resolution:
   ```bash
   nslookup your-server
   ```

3. Check server health and load

---

## Authentication Errors

### "401 Unauthorized"

**Causes:**

- Missing or invalid API token
- Expired token
- Incorrect authentication configuration

**Solutions:**

1. Verify your API token is set:
   ```bash
   echo $A2A_API_KEY
   ```

2. Check token validity in the server logs

3. Generate a new token if needed (see [API Tokens](../auth/tokens.md))

### "403 Forbidden"

**Causes:**

- Token lacks required permissions
- Resource access denied by policy

**Solutions:**

1. Check the required permissions for the endpoint
2. Verify your token's scope and permissions
3. Contact your administrator for access

---

## SSE Streaming Issues

### Events not received

**Causes:**

- Proxy/load balancer buffering responses
- Connection timeout settings too low
- Network interruptions

**Solutions:**

1. Disable proxy buffering:
   ```nginx
   # Nginx configuration
   proxy_buffering off;
   proxy_cache off;
   proxy_set_header Connection '';
   proxy_http_version 1.1;
   chunked_transfer_encoding off;
   ```

2. Increase timeout settings:
   ```nginx
   proxy_read_timeout 86400s;
   proxy_send_timeout 86400s;
   ```

3. For AWS ALB, enable streaming:
   ```
   idle_timeout: 4000
   ```

---

## Worker SSE Task Distribution Issues

### Workers not receiving tasks via SSE

**Causes:**

- Missing or incorrect `X-Codebases` header
- Missing or incorrect `X-Capabilities` header
- Worker not listening for `task_available` event type
- Codebase ID mismatch

**Solutions:**

1. Verify headers are sent correctly when connecting to SSE:
   ```bash
   curl -N "http://localhost:8000/v1/worker/tasks/stream" \
     -H "X-Codebases: my-project,api" \
     -H "X-Capabilities: agent,build,deploy,test" \
     -H "Accept: text/event-stream"
   ```

2. Ensure worker listens for the correct event type (`task_available`):
   ```python
   # Correct event types to handle
   if event_type in ('task', 'task_available', 'task_assigned'):
       process_task(data)
   ```

3. Check worker registration and codebase IDs match:
   ```bash
   curl http://localhost:8000/v1/agent/workers
   curl http://localhost:8000/v1/agent/codebases
   ```

### Global tasks not being received

**Causes:**

- Worker doesn't have a global codebase registered
- Task filtering logic not handling `codebase_id: "global"`

**Solutions:**

1. Ensure worker has a global codebase registered
2. Update filtering to accept global tasks:
   ```python
   # Accept tasks with codebase_id == 'global'
   if codebase_id in registered_codebases or codebase_id == 'global':
       process_task(task)
   ```

### SSE connection drops frequently

**Causes:**

- Server heartbeat timeout
- Network instability
- Load balancer idle timeout

**Solutions:**

1. Check heartbeat is being received (every 30s by default)
2. Implement exponential backoff reconnection:
   ```python
   reconnect_delay = min(2 ** retry_count, 60)  # Max 60s
   ```
3. Increase load balancer idle timeout

### Worker logs show "Unknown SSE event type"

This is usually informational. The worker should handle these event types:

| Event Type | Description |
|------------|-------------|
| `task_available` | New task available |
| `task` | Full task object |
| `task_assigned` | Task assigned to worker |
| `connected` | Connection confirmed |
| `keepalive` | Heartbeat signal |

---

## Getting Help

If you're still experiencing issues:

1. Check the [server logs](../features/monitor-ui.md) for detailed error messages
2. Search [existing issues](https://github.com/rileyseaburg/codetether/issues) on GitHub
3. Open a new issue with:
   - Error message and stack trace
   - Server version (`codetether --version`)
   - Environment details (OS, Node.js version)
   - Steps to reproduce
