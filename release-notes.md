## Quick Install

**Windows (PowerShell):**

```powershell
Invoke-Expression (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-agent.ps1" -UseBasicParsing).Content
```

**Windows (Git Bash):**

```bash
curl -fsSL https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-agent-windows.sh | bash
```

## What's Changed

- Fixed Windows build version issue (now correctly shows 1.1.27)
- Added kimik provider custom loader for Chat Completions API support
- Fixed image support for Kimi K2.5 model
- Added Windows install scripts (PowerShell & Git Bash)

**Full Changelog**: https://github.com/rileyseaburg/codetether/compare/agent-v1.1.26...codetether-v1.1.27
