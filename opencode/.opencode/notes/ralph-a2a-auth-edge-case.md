
## Edge Case: Ralph Requires A2A Auth Token for Distributed Mode

**Issue:** When running `ralph({ action: "distributed" })` on the `spotless-dev-worker`, the tool fails with:
```
A2A server not configured. Set these environment variables:
- A2A_SERVER_URL: The A2A server URL (e.g., https://api.codetether.run)
- A2A_AUTH_TOKEN: Your auth token
```

**Root Cause:** The A2A worker configuration file at `/etc/a2a-worker/config.json` contains the `server_url` but the auth token is NOT stored there. Instead, it appears to be passed via environment variables (`A2A_AUTH_TOKEN`) when the worker process starts.

**Why This Happens:**
- A2A worker reads config from JSON file for: server_url, worker_name, codebases, capabilities
- But auth token comes from: `A2A_AUTH_TOKEN` environment variable (see worker.py line 4761)
- When running Ralph directly (not through the worker), this env var is not available

**Impact:**
- Cannot use `ralph({ action: "distributed" })` from opencode CLI
- Must either:
  1. Set `A2A_AUTH_TOKEN` environment variable manually
  2. Use `ralph({ action: "run" })` for local execution instead
  3. Implement changes manually

**Workaround for Family Budget Project:**
Added `family-budget` codebase to `/etc/a2a-worker/config.json` but proceeding with manual implementation since auth token is not accessible.

**Suggested Documentation:**
Add to A2A setup guide that workers need both:
1. Config file (`/etc/a2a-worker/config.json`) with server_url and codebases
2. Environment variable `A2A_AUTH_TOKEN` set when starting the worker

**Related Files:**
- `/etc/a2a-worker/config.json` - Worker configuration
- `/opt/a2a-worker/worker.py:4761` - Where A2A_AUTH_TOKEN is read
- `/home/riley/A2A-Server-MCP/opencode/packages/opencode/src/tool/ralph.ts` - Ralph tool implementation
