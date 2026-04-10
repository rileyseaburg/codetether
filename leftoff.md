# CodeTether - Left Off

## Completed (Jan 21, 2026)

### Local Worker Setup (Easy Mode)

**One-liner to start everything:**
```bash
cd ~/A2A-Server-MCP && make dev
```

This starts:
- **A2A Server** on port 8001
- **MCP Server** on port 9000  
- **Next.js Marketing Site** on port 3001
- **Local Worker** (auto-connects via SSE)

**What the worker does:**
- Connects to the server via SSE stream (`/v1/worker/tasks/stream`)
- Discovers models from CodeTether auth (`~/.local/share/agent/auth.json`)
- Syncs local CodeTether sessions to the server
- Processes tasks from the queue

**Manual worker start (if needed):**
```bash
make worker
# or directly:
python agent_worker/worker.py \
  --server http://localhost:8001 \
  --mcp-url http://localhost:9000 \
  --name "local-worker" \
  --worker-id "local-worker-1" \
  --codebase A2A-Server-MCP:.
```

**Systemd service (production):**
```bash
# Install
sudo bash agent_worker/install.sh

# Restart
make local-worker-restart
```

### Resume Flow Fix

- Hide Resume button when message is being sent or awaiting response ✅
- Test task processing works with local worker ✅

---

## Completed (Jan 20, 2026)

### Email Reply System

1. **SendGrid Inbound Parse** - Working ✅
   - Configured at `POST /v1/email/inbound`
   - Parses reply-to address: `task+{session_id}@inbound.codetether.run`
   - Extracts reply content, strips quoted text
   - Creates continuation tasks with `resume_session_id`

2. **Model Selection via Email** - NEW ✅
   - Users can select models when replying via email
   - Subject line format: `[model:claude-sonnet]` or `[use:gpt-4o]` or `[with:gemini]`
   - Supports aliases: `claude`, `sonnet`, `opus`, `haiku`, `gpt-4o`, `gemini`, `minimax`, `grok`
   - Also supports direct provider/model: `[model:anthropic/claude-sonnet-4-20250514]`
   - Test endpoint: `GET /v1/email/test-model-parsing?subject=...`

3. **Contact Email Forwarding** - Working ✅
   - Emails to info@, support@, hello@, etc. are forwarded to admin

---

## Completed (Jan 19, 2026)

### Landing Page (https://codetether.run)

1. **RLM Explainer Section** - Explains the problem (context rot) and solution (RLM) ✅
2. **Interactive RLM Demo** - Click "Run Demo" to watch simulated RLM execution ✅
    - Shows 847K tokens being processed
    - Displays code execution, sub-calls, output stitching
    - Links to MIT paper

### Dashboard (https://codetether.run/dashboard/sessions)

1. **RLM Button** in chat header - toggles execution pane ✅
2. **RLM Execution Pane** - fully wired with live data ✅
    - Shows real-time RLM steps from SSE events
    - Displays stats (tokens, chunks, sub-calls)
    - Supports both live streaming and historical data

### SSE Wiring (COMPLETED)

1. **useSessionStream hook** (`hooks/useSessionStream.ts`) ✅
   - Parses `part.tool` events where `tool_name === 'rlm'`
   - Extracts RLM metadata (iterations, tokens, subcalls)
   - Handles `rlm.routing` events for routing decisions
   - Handles `rlm.step` and `rlm.stats` events

2. **useRlmFromHistory hook** (`hooks/useRlmFromHistory.ts`) ✅
   - Extracts RLM data from historical chat items
   - Shows RLM info even for past sessions

3. **RLMExecutionPane component** (`components/RLMExecutionPane.tsx`) ✅
   - Accepts `steps` and `stats` props from live/history hooks
   - Auto-scrolls to show latest activity
   - Shows idle/processing states

4. **page.tsx** ✅
   - Combines live RLM steps with historical data
   - Passes to both overlay (mobile) and docked (desktop) panes

5. **Backend events** (`a2a_server/monitor_api.py`) ✅
   - `part.tool` events include tool_name, status, metadata, output, error
   - `rlm.routing.decision` events transformed to `rlm.routing`
   - CodeTether emits these events when RLM tool executes

## Current State Summary

- **Marketing landing page**: RLM demo works with simulated data ✅
- **Dashboard RLM pane**: Fully wired with live SSE events ✅
- **Backend RLM events**: Events are emitted and transformed ✅
- **Historical data**: RLM output visible in past sessions ✅

## Next Steps (Future Work)

- Add more granular RLM step events (if CodeTether emits them)
- Show estimated completion time based on chunk progress
- Add ability to cancel RLM execution in-progress
- Performance metrics visualization (tokens/second, cost breakdown)

---

## Completed (Jan 23, 2026)

### SDK Generation & Type-Safe API Calls

1. **SDK Generation Setup** ✅
   - Installed `@hey-api/openapi-ts` for auto-generating TypeScript SDK from OpenAPI spec
   - Configured `openapi-ts.config.ts` to fetch from `https://api.codetether.run/openapi.json`
   - Added `npm run generate:api` script to regenerate SDK
   - Generated SDK files in `src/lib/api/generated/`

2. **Environment-Aware Client** ✅
   - Created `src/lib/api/index.ts` with environment-aware base URL
   - Uses `NEXT_PUBLIC_API_URL` if set, else localhost:8000 in dev, else api.codetether.run

3. **Ralph Page Migration (Partial)** ✅
   - Migrated `RalphPageHooks.ts` to use SDK functions
   - Migrated `ServerRalphRuns.tsx` to use SDK
   - Migrated `page.tsx` task fetching to use SDK

4. **Updated AGENTS.md** ✅
   - Documented the SDK generation pattern and usage

### Ralph Page Refactoring (50-Line Rule) ✅

Refactored `ralph/page.tsx` from **2006 lines** to modular components:

| Component | Lines | Purpose |
|-----------|-------|---------|
| `RalphIcons.tsx` | 44 | Shared icon components |
| `RalphHeader.tsx` | 42 | Page header with controls |
| `RalphPRDConfigPanel.tsx` | 50 | PRD JSON input & builder |
| `RalphSettingsPanel.tsx` | 35 | Codebase, model, run settings |
| `RalphStoriesPanel.tsx` | 39 | Stories list container |
| `RalphStoryCard.tsx` | 39 | Individual story card |
| `RalphLogViewer.tsx` | 45 | Terminal-style log output |
| `ServerRalphRuns.tsx` | 39 | Run history |
| `RalphTasksTable.tsx` | 29 | Active tasks table |
| `RalphPageHooks.ts` | 36 | Business logic hooks |
| `page.tsx` | 42 | Main orchestration |

---

## SDK Migration - Remaining Work

### High Priority (Dashboard Core)
| File | Endpoints to Migrate |
|------|---------------------|
| `dashboard/page.tsx` | codebases/list, workers, models, trigger, codebases CRUD |
| `dashboard/tasks/page.tsx` | agent/tasks |
| `dashboard/settings/page.tsx` | providers, vault/status, api-keys, billing/status |
| `dashboard/billing/page.tsx` | billing/status, checkout, portal |

### Medium Priority (Features)
| File | Endpoints |
|------|-----------|
| `components/IntercomChat.tsx` | agent/tasks |
| `components/ChatWidget.tsx` | agent/tasks |
| `components/WorkerSelector/index.tsx` | agent/workers |
| `sessions/hooks/useSessions.ts` | codebases sessions |
| `sessions/hooks/useCodebases.ts` | codebases/list |
| `ralph/prd-api.ts` | agent/tasks |
| `ralph/useAIPRDChat.ts` | agent/tasks |

### Lower Priority
| File | Endpoints |
|------|-----------|
| `voice/*` | voice/voices, voice/sessions |
| `admin/page.tsx` | admin/dashboard, admin/alerts |
| `automations/*` | automation/tasks |

### Commands
```bash
# Regenerate SDK after API changes
cd marketing-site && npm run generate:api

# Find remaining fetch calls
grep -rn "fetch(" src --include="*.ts" --include="*.tsx" | grep -v generated

# Check SDK functions available
grep "export const" src/lib/api/generated/sdk.gen.ts | head -50
```
