# Changelog

## [1.4.2] - 2026-02-10

### Added - Zapier Integration v1.2.0 (12 new components)

Expanded the Zapier integration from 6 to 18 components, covering agents, codebases, cron jobs, PRD generation, billing, and more.

#### New Actions
| Action | Description |
|--------|-------------|
| `send_message_async` | Fire-and-forget async messages with task tracking |
| `send_to_agent` | Target specific named agents with deadline support |
| `cancel_ralph_run` | Cancel autonomous Ralph development runs |
| `create_cronjob` | Schedule recurring tasks with cron expressions |
| `prd_chat` | AI-assisted PRD generation with user stories |

#### New Searches
| Search | Description |
|--------|-------------|
| `discover_agents` | Find registered worker agents in the network |
| `list_codebases` | Find codebases for targeting tasks and runs |
| `list_ralph_runs` | List/filter Ralph runs by status |
| `list_models` | Discover available AI models by provider |
| `get_usage_summary` | Token usage and billing summary |

#### New Triggers
| Trigger | Description |
|---------|-------------|
| `task_completed` | Fires when a task finishes successfully |
| `task_failed` | Fires when a task fails (for alerts/retry logic) |

#### Documentation Updates
- Comprehensive Zapier docs at `codetether-docs/features/zapier.md` (all 18 components)
- Updated marketing site getting-started page with new use cases
- Updated README.md and ALIGNMENT.md

## [1.4.1] - 2026-01-25

### Added - MCP-to-Ralph Integration (E2E Validated)

Complete end-to-end MCP integration enabling AI assistants to autonomously create and monitor Ralph runs.

#### New MCP Tools (6 tools added, 29 total)

| Tool | Description |
|------|-------------|
| `ralph_create_run` | Create and start autonomous development runs |
| `ralph_get_run` | Monitor run status and story results |
| `ralph_list_runs` | List runs filtered by codebase |
| `ralph_cancel_run` | Cancel running executions |
| `prd_chat` | AI-assisted PRD generation via chat |
| `prd_list_sessions` | List PRD chat sessions |

#### E2E Test Results

Successfully validated the complete pipeline:
1. **MCP Tool Call** → `ralph_create_run` with PRD and codebase_id
2. **Task Creation** → Ralph creates tasks for each user story
3. **Worker Execution** → Worker claims and executes tasks
4. **AI Implementation** → OpenCode implements acceptance criteria
5. **Completion** → Run marked complete with story results

#### Key Implementation Details

- PRD stored in PostgreSQL `ralph_runs` table as JSONB
- `codebase_id` is **required** for worker task pickup
- Worker must be registered and connected to claim tasks
- Story results include pass/fail status and implementation details

#### Example Usage

```bash
# Create Ralph run via MCP
curl -X POST http://localhost:9000/mcp/v1/rpc \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
       "params": {"name": "ralph_create_run", "arguments": {
         "project": "My Feature",
         "codebase_id": "ec77c942",
         "user_stories": [{"id": "US-001", "title": "...", ...}]
       }}}'

# Response: {"run_id": "uuid", "status": "pending", ...}
```

### Fixed

- Ralph API returns `id` not `run_id` - MCP handler now correctly parses response
- Tasks without `codebase_id` weren't being picked up by workers

### Documentation

- Updated `codetether-docs/features/mcp-tools.md` with complete Ralph MCP documentation
- Updated `codetether-docs/features/ralph.md` with MCP integration section
- Added E2E example workflow with code samples

---

## [1.4.0] - 2026-01-22

### Added - Ralph: Autonomous Development Loop

Ralph is a fully autonomous development agent that implements entire PRDs (Product Requirements Documents) with zero human intervention.

#### Ralph Architecture
- **PRD-Driven Development**: Define user stories with acceptance criteria, Ralph implements them all
- **Fresh Context Per Story**: Each user story spawns a new OpenCode instance for optimal context
- **Iterative Learning**: Failed stories trigger re-analysis using `progress.txt` context
- **Self-Healing**: Automatic retry with accumulated learnings when acceptance criteria fail
- **Git Integration**: Atomic commits per user story with meaningful commit messages

#### Ralph Dashboard (`/dashboard/ralph`)
- Interactive PRD builder with YAML import/export
- Real-time execution monitoring with live logs
- Story status tracking (pending/running/passed/failed)
- Agent and task overview with progress metrics
- Branch management with auto-generated feature branches

#### RLM Integration
- Ralph leverages RLM for large codebase analysis when context exceeds threshold
- Subcalls automatically triggered when analyzing complex files
- Progress context preserved across iterations

### Added - Chat Widget

Interactive chat widget for the marketing site, enabling live conversations with the A2A platform.

- **ChatWidget Component**: Floating chat bubble with expand/collapse states
- **Marketing Site Integration**: Embedded on index page for visitor engagement
- **Real-time Messaging**: Direct connection to A2A messaging system

### Added - Zapier Integration

Full Zapier CLI integration for no-code automation workflows.

#### Authentication
- OAuth2 authentication with Keycloak
- Secure token refresh flow

#### Zapier Components
- **Trigger**: `new_task` - Fires when tasks are created
- **Actions**: `create_task`, `send_message`, `cancel_task`
- **Search**: `find_task` - Find tasks by ID or status

### Added - Getting Started / Onboarding

New onboarding experience with Zapier as first-class integration method.

- `/dashboard/getting-started` page with quick start guide (3 steps)
- Popular Zapier automation examples
- All integration methods documented (Zapier, REST API, Webhooks)
- Highlighted navigation item with "New" badge

### Added - Task Reaper

Automatic stuck task recovery system for improved reliability.

#### Task Reaper Features
- Background service running every 60 seconds
- Detects tasks stuck in 'running' state for >5 minutes
- Requeues stuck tasks for retry (up to 3 attempts)
- Marks tasks as failed after max retries exceeded
- Email notification on permanent failure

#### New API Endpoints
- `GET /v1/opencode/tasks/stuck` - List stuck tasks
- `POST /v1/opencode/tasks/stuck/recover` - Manual recovery trigger
- `POST /v1/opencode/tasks/{id}/requeue` - Requeue specific task
- `GET /v1/opencode/reaper/health` - Reaper health status

#### Configuration
- `TASK_STUCK_TIMEOUT_SECONDS` (default: 300)
- `TASK_REAPER_INTERVAL_SECONDS` (default: 60)
- `TASK_MAX_ATTEMPTS` (default: 3)

### Added - Email Improvements

- **Contact Forwarding**: Emails to info@, support@, hello@, contact@, help@, sales@ forwarded to admin
- **Session ID in Reply-To**: Task notification emails include session_id for proper threading
- **Email Logging**: Inbound/outbound email tracking in database

### Fixed
- Missing `provisioning_service` import for user registration
- FK constraints removed from email tables (tasks may be in-memory only)
- Zapier OAuth refresh token flow

---

## [1.3.0] - 2026-01-18

### Added - RLM (Recursive Language Models)

Revolutionary infinite context processing that breaks the context window barrier.

#### RLM Architecture
- **model_resolver.py**: Priority-based model resolution for RLM subcalls
- **Hosted Worker Integration**: RLM capability detection and execution
- **Database Fields**: `subcall_model_ref`, `resolved_subcall_*` for tracking

#### How RLM Works
1. When context exceeds threshold (default: 80K tokens), RLM triggers automatically
2. Context is chunked and processed by subcall agents
3. Results are synthesized back into the parent context
4. Enables processing of arbitrarily large codebases

#### Marketing Site Updates
- RLM feature section with interactive code demo
- Hero badge with infinity symbol
- Primary feature tab highlighting RLM
- Feature cards with RLM benefits

#### Documentation
- RLM architecture diagrams
- Configuration guide in opencode-integration.md
- Flow diagrams in agent-messaging-architecture.md

---

## [1.2.2] - 2026-01-15

### Added - Production-Grade Agent Discovery

Workers can now register as discoverable agents in the A2A network, enabling agent-to-agent communication.

#### Role:Instance Pattern
- **Discovery identity** (`name`): Unique per-instance (e.g., `code-reviewer:dev-vm:abc123`)
- **Routing identity** (`role`): Stable for `send_to_agent` (e.g., `code-reviewer`)
- Multiple workers with same role show as distinct agents in discovery

#### TTL-Based Liveness
- Agents must send heartbeats every 45s to stay visible
- `discover_agents` filters agents not seen within 120s (configurable via `A2A_AGENT_DISCOVERY_MAX_AGE`)
- Lazy cleanup removes stale agents from all indexes
- Clock skew tolerance: future timestamps treated as fresh

#### New MCP Tool
- `refresh_agent_heartbeat`: Keep agent visible in discovery

#### Worker CLI Options
```bash
--agent-name NAME        # Routing role for send_to_agent
--agent-description DESC # Description for discovery
--agent-url URL          # Direct URL (optional)
--no-agent-registration  # Disable auto-registration
```

#### Environment Variables
- `A2A_AGENT_NAME` - Agent routing role
- `A2A_AGENT_DESCRIPTION` - Agent description
- `A2A_AGENT_URL` - Agent URL
- `A2A_AGENT_DISCOVERY_MAX_AGE` - TTL filter in seconds (default: 120)

#### discover_agents Response
```json
{
  "agents": [{
    "name": "code-reviewer:dev-vm:abc123",
    "role": "code-reviewer",
    "instance_id": "dev-vm:abc123",
    "last_seen": "2026-01-15T12:00:00"
  }],
  "routing_note": "Use 'role' with send_to_agent for routing."
}
```

### Fixed
- JSON-RPC response format compliance (result OR error, not both)
- Cross-platform hostname detection (Windows compatibility)

### Tests
- 13 new tests for agent discovery (`tests/test_agent_discovery.py`)

## [1.2.0] - 2025-01-15

### Added - A2A Protocol v0.3 Compliance

CodeTether is now fully compliant with the official A2A Protocol v0.3 specification.

#### New Dependencies
- `a2a-sdk[http-server,postgresql]>=0.3.22` - Official Google A2A SDK

#### New Endpoints
- `GET /.well-known/agent-card.json` - Standard agent discovery
- `POST /a2a/jsonrpc` - JSON-RPC 2.0 binding
- `POST /a2a/rest/message:send` - REST binding for messages
- `POST /a2a/rest/message:stream` - SSE streaming
- `GET /a2a/rest/tasks/{id}` - Task status
- `POST /a2a/rest/tasks/{id}:cancel` - Task cancellation

#### New Modules
- `a2a_executor.py` - Bridges A2A SDK to our task queue system
- `a2a_agent_card.py` - Standard agent card generation
- `a2a_router.py` - FastAPI router for A2A protocol
- `a2a_types.py` - Task state mapping (internal ↔ A2A)
- `a2a_errors.py` - A2A-compliant error codes (-32001 to -32009)

#### Task State Alignment
- Added states: `submitted`, `rejected`, `auth-required`
- Mapped existing states to A2A spec equivalents

### Preserved
- MCP tools at `/mcp` - unchanged
- Worker SSE push system - unchanged
- Agent-targeted routing (`send_to_agent`) - unchanged
- Capability-based routing - unchanged
- Multi-tenant support - unchanged

### Interoperability
- Any A2A-compliant client can now connect to CodeTether
- Compatible with official A2A JS SDK and Python SDK clients

## [0.7.0] - 2026-01-14

### Features

* **Agent-Targeted Routing**: Route tasks to specific named agents instead of any available worker
  - `send_to_agent` MCP tool: Route tasks to specific agents by name with optional deadline
  - `send_message_async` MCP tool: Fire-and-forget async messaging for generic task distribution
  - Exact agent name matching (no wildcards) with queue-indefinitely-by-default behavior
  - Optional `deadline_seconds` parameter to fail tasks if no matching worker claims them

* **Capability-Based Routing**: Workers can declare capabilities, tasks can require them
  - Workers register with `--agent-name` and `--capabilities` CLI flags
  - Tasks can specify `required_capabilities` as a JSONB array
  - SQL containment check (`@>`) ensures workers have ALL required capabilities
  - Combined with agent targeting for precise task routing

* **Database Migration 007**: New schema for routing support
  - `target_agent_name`, `required_capabilities`, `deadline_at` columns on `task_runs`
  - Updated `claim_next_task_run()` function with agent/capability filtering
  - `fail_deadline_exceeded_tasks()` function for deadline enforcement
  - `targeted_task_queue` view for monitoring agent-specific queues

### Architecture

* **Dual-Layer Routing Enforcement**: Both SSE notify-time AND SQL claim-time filtering
  - SSE layer: Workers only notified of tasks they can claim (reduces noise)
  - SQL layer: Atomic claim ensures no race conditions (authoritative filter)
  - No silent fallback: Tasks for agent X never run on agent Y

* **TaskRun Dataclass Extensions**: New routing fields for task inspection
  - `target_agent_name`, `required_capabilities`, `deadline_at`
  - `routing_failed_at`, `routing_failure_reason` for debugging failures

### API

* **New MCP Tools**:
  - `send_message_async(message, conversation_id?, codebase_id?, priority?, notify_email?)` - Generic async task
  - `send_to_agent(agent_name, message, conversation_id?, codebase_id?, priority?, deadline_seconds?, notify_email?)` - Targeted routing

* **Worker CLI Extensions**:
  - `--agent-name NAME` - Register worker with a specific agent name
  - `--capabilities cap1,cap2` - Declare worker capabilities

### Tests

* **Agent Routing Test Suite**: 10 passing tests in `tests/test_agent_routing.py`
  - Worker registry targeting and capability filtering
  - Broadcast task with targeting
  - TaskRun dataclass with routing fields
  - Combined targeting + capabilities (AND logic)

## [0.6.0] - 2026-01-04

### Features

* **Voice Agent with Gemini Live API**: Production-ready voice assistant using Google Gemini Live 2.5 Flash
  - Real-time voice conversations with LiveKit integration
  - 5 MCP tools accessible via voice: `list_tasks`, `create_task`, `get_task`, `cancel_task`, `discover_agents`
  - Vertex AI authentication with service account credentials
  - LiveKit Agents SDK 1.3.10 compatibility with `@llm.function_tool` decorator

* **Voice Agent Test Suite**: Comprehensive integration tests with audio recording
  - `test_voice_tools.py` - Full test suite for all voice tools
  - `test_create_task_recording.py` - Task creation with audio capture
  - Sample recordings: `agent_create_task_response.wav`, `agent_architecture_review.wav`

* **Agent Worker God Object Refactor**: Major architectural improvement to `agent_worker/worker.py`
  - **`WorkerClient`** - HTTP/SSE communication with A2A server
  - **`ConfigManager`** - OpenCode binary, storage paths, API keys, models
  - **`SessionSyncService`** - Session reading and syncing from OpenCode storage
  - **`TaskExecutor`** - Task execution, OpenCode subprocess, concurrency control
  - **`AgentWorker`** - Thin orchestrator composing all services

### Marketing Site Voice Improvements

* **Authentication Headers**: All voice API calls now include Bearer token when available
* **Session Reconnection**: Auto-reconnects to existing sessions after disconnection using persistent user ID
* **Agent State Polling**: Real-time agent state updates (idle/listening/thinking/speaking/error) with color-coded UI
* **Mode/Playback Parameters**: Session creation now sends `mode` and `playback_style` parameters

### Swift iOS Voice Improvements

* **Working Mute Toggle**: Mute button now actually controls microphone via LiveKit SDK
* **Optional Voice Fields**: `provider`, `model`, `language` fields now optional with safe defaults

### Bug Fixes

* **MCP Client Null Error Handling**: Fixed `if 'error' in result` to check for non-null values
* **Voice Agent Import Paths**: Fixed container import paths with try/except fallback
* **Worker Task Claiming**: Added `_claim_task()` and `_release_task()` for distributed task safety
* **Worker Memory Leak**: Changed `_known_task_ids` from unbounded Set to LRU OrderedDict (10k max)
* **Worker Silent Exceptions**: Fixed 17 silent `except: pass` handlers with proper logging
* **Worker Status Retry**: Added exponential backoff (5 attempts) for task status updates

### Architecture

* **Single Responsibility Principle**: Worker code split from 2872-line god object to 5 focused classes
* **Dependency Injection**: Services receive dependencies via constructors
* **Backward Compatibility**: Original AgentWorker methods preserved as delegates

## [0.5.0] - 2024-12-29

### Features

* **Marketing Coordinator Agent**: New strategic marketing orchestration agent that plans and coordinates marketing initiatives via the task queue.
  - Creates tasks for workers to execute marketing operations (creative generation, campaign launches, audience building)
  - Uses AI (Claude Opus 4.5 via Azure AI Foundry) for initiative planning and strategy
  - Initiative lifecycle management: draft → planning → executing → monitoring
  - Database-backed initiative persistence with PostgreSQL
  - Task-based architecture: Coordinator creates tasks → Workers execute via OpenCode → MCP tools call spotlessbinco APIs

* **Spotless Bin Co MCP Tools**: 27 new MCP tools exposing marketing services:
  - **Creative**: `spotless_generate_creative`, `spotless_batch_generate_creatives`, `spotless_get_top_creatives`, `spotless_analyze_creative_performance`
  - **Campaigns**: `spotless_create_campaign`, `spotless_update_campaign_status`, `spotless_update_campaign_budget`, `spotless_get_campaign_metrics`, `spotless_list_campaigns`
  - **Automations**: `spotless_create_automation`, `spotless_trigger_automation`, `spotless_list_automations`, `spotless_update_automation_status`
  - **Audiences**: `spotless_create_geo_audience`, `spotless_create_lookalike_audience`, `spotless_create_custom_audience`, `spotless_get_trash_zone_zips`
  - **Analytics**: `spotless_get_unified_metrics`, `spotless_get_roi_metrics`, `spotless_get_channel_performance`, `spotless_thompson_sample_budget`, `spotless_get_conversion_attribution`
  - **Platform Sync**: `spotless_sync_facebook_metrics`, `spotless_sync_tiktok_metrics`, `spotless_sync_google_metrics`, `spotless_send_facebook_conversion`, `spotless_send_tiktok_event`

* **Enhanced Tool Discovery**: Added new search categories for marketing tools: `creative`, `campaigns`, `automations`, `audiences`, `analytics`, `platform_sync`, `marketing`, `spotless`

### Architecture

* **Task-Based Orchestration**: Marketing Coordinator now creates tasks for workers instead of making direct API calls:
  ```
  Coordinator → Creates Task → A2A Queue → Worker picks up → OpenCode executes → MCP tool calls API
  ```
  This enables distributed execution, better monitoring, and resilience.

* **MCP Tool Integration**: All spotlessbinco marketing services are now accessible via MCP tools, allowing any agent to orchestrate marketing operations through the standard MCP protocol.

## [0.4.0] - 2024-12-24

### Features

* **PostgreSQL Task Persistence**: Tasks now persist to PostgreSQL via `PersistentTaskManager` with asyncpg. Tasks are stored in the `a2a_tasks` table with full status history and message tracking.
* **PostgreSQL Monitor Messages**: Monitor messages now persist to PostgreSQL in the `monitor_messages` table. Includes message types, response times, token counts, and agent tracking.
* **Redis Reactive Task Execution**: Workers can now subscribe to Redis MessageBroker events for near-instant task execution. Tasks start within milliseconds instead of waiting for poll cycles.
* **Worker Redis Integration**: Added Redis pub/sub support to agent workers with automatic reconnection, event subscriptions, and graceful shutdown handling.
* **Model Filtering by Authentication**: Workers now automatically filter available models based on configured authentication. Only models from providers with valid API keys or OAuth tokens in `auth.json` are registered with the server.
* **Runtime Sessions API**: Direct access to local OpenCode sessions without requiring codebase registration
  - `GET /v1/opencode/runtime/status` - Check if OpenCode runtime is available locally
  - `GET /v1/opencode/runtime/projects` - List all local projects with session counts
  - `GET /v1/opencode/runtime/sessions` - List all sessions with pagination
  - `GET /v1/opencode/runtime/sessions/{id}` - Get session details
  - `GET /v1/opencode/runtime/sessions/{id}/messages` - Get conversation history
  - `GET /v1/opencode/runtime/sessions/{id}/parts` - Get message content parts
* **Enhanced OpenCode Status**: The `/v1/opencode/status` endpoint now includes runtime session information when OpenCode is detected locally
* **Blue-Green Deployments**: Added `make bluegreen-deploy` target with zero-downtime deployment support
* **Kubernetes Targets**: New makefile targets for dev/staging/prod deployments (`make k8s-dev`, `make k8s-staging`, `make k8s-prod`)

### Bug Fixes

* **React UI Normalization**: Fixed "Minified React error #31" (Objects are not valid as React child) by normalizing model objects to string format in the backend.
* **Worker Production Connection**: Updated default worker configuration to use `https://api.codetether.run` for production environments.

### Documentation

* **Agent Worker Guide**: Comprehensive documentation for the Agent Worker daemon
  - Installation guide with quick install script and manual steps
  - Complete configuration reference (config file and environment variables)
  - Systemd service setup with security hardening
  - Task workflow explanation (polling, execution, streaming)
  - Session sync functionality
  - Troubleshooting guide
* **Worker API Documentation**: Added Worker endpoints to OpenCode API reference
  - `POST /v1/opencode/workers/register` - Register a worker
  - `POST /v1/opencode/workers/{id}/unregister` - Unregister a worker
  - `PUT /v1/opencode/tasks/{id}/status` - Update task status
  - `POST /v1/opencode/tasks/{id}/output` - Stream task output
  - `POST /v1/opencode/codebases/{id}/sessions/sync` - Sync sessions
* Updated Distributed Workers guide with accurate Agent Worker integration
* Updated REST API reference with Worker and Task endpoints
* Added Runtime Sessions API examples to README

## [0.3.0](https://github.com/a2aproject/A2A/compare/v0.2.6...v0.3.0) (2025-07-30)


### ⚠ BREAKING CHANGES

* Add mTLS to SecuritySchemes, add oauth2 metadata url field, allow Skills to specify Security ([#901](https://github.com/a2aproject/A2A/issues/901))
* Change Well-Known URI for Agent Card hosting from `agent.json` to `agent-card.json` ([#841](https://github.com/a2aproject/A2A/issues/841))
* Add method for fetching extended card ([#929](https://github.com/a2aproject/A2A/issues/929))

### Features

* Add `signatures` to the `AgentCard` ([#917](https://github.com/a2aproject/A2A/issues/917)) ([ef4a305](https://github.com/a2aproject/A2A/commit/ef4a30505381e99b20103724cabef024389bacef))
* Add method for fetching extended card ([#929](https://github.com/a2aproject/A2A/issues/929)) ([2cd7d98](https://github.com/a2aproject/A2A/commit/2cd7d98bc8566601b9a18ca8afe92a0b4d203248))
* Add mTLS to SecuritySchemes, add oauth2 metadata url field, allow Skills to specify Security ([#901](https://github.com/a2aproject/A2A/issues/901)) ([e162c0c](https://github.com/a2aproject/A2A/commit/e162c0c6c4f609d2f4eef9042466d176ec75ebda))


### Bug Fixes

* **spec:** Add `SendMessageRequest.request` `json_name` mapping to `message` ([#904](https://github.com/a2aproject/A2A/issues/904)) ([2eef3f6](https://github.com/a2aproject/A2A/commit/2eef3f6113851e690cee70a1b1643e1ffd6d2a60))
* **spec:** Add Transport enum to specification ([#909](https://github.com/a2aproject/A2A/issues/909)) ([e834347](https://github.com/a2aproject/A2A/commit/e834347c279186d9d7873b352298e8b19737dd5a))


### Code Refactoring

* Change Well-Known URI for Agent Card hosting from `agent.json` to `agent-card.json` ([#841](https://github.com/a2aproject/A2A/issues/841)) ([0858ddb](https://github.com/a2aproject/A2A/commit/0858ddb884dc4671681fd819648dfd697176abb3))

## [0.2.6](https://github.com/a2aproject/A2A/compare/v0.2.5...v0.2.6) (2025-07-17)


### Bug Fixes

* Type fix and doc clarification ([#877](https://github.com/a2aproject/A2A/issues/877)) ([6f1d17b](https://github.com/a2aproject/A2A/commit/6f1d17ba806c32f2b6fbe465be93ec13bfe7d83c))
* Update json names of gRPC objects for proper transcoding  ([#847](https://github.com/a2aproject/A2A/issues/847)) ([6ba72f0](https://github.com/a2aproject/A2A/commit/6ba72f0d51c2e3d0728f84e9743b6d0e88730b51))

## [0.2.5](https://github.com/a2aproject/A2A/compare/v0.2.4...v0.2.5) (2025-06-30)


### ⚠ BREAKING CHANGES

* **spec:** Add a required protocol version to the agent card. ([#802](https://github.com/a2aproject/A2A/issues/802))
* Support for multiple pushNotification config per task ([#738](https://github.com/a2aproject/A2A/issues/738)) ([f355d3e](https://github.com/a2aproject/A2A/commit/f355d3e922de61ba97873fe2989a8987fc89eec2))


### Features

* **spec:** Add a required protocol version to the agent card. ([#802](https://github.com/a2aproject/A2A/issues/802)) ([90fa642](https://github.com/a2aproject/A2A/commit/90fa64209498948b329a7b2ac6ec38942369157a))
* **spec:** Support for multiple pushNotification config per task ([#738](https://github.com/a2aproject/A2A/issues/738)) ([f355d3e](https://github.com/a2aproject/A2A/commit/f355d3e922de61ba97873fe2989a8987fc89eec2))


### Documentation

* update spec & doc topic with non-restartable tasks ([#770](https://github.com/a2aproject/A2A/issues/770)) ([ebc4157](https://github.com/a2aproject/A2A/commit/ebc4157ca87ae08d1c55e38e522a1a17201f2854))

## [0.2.4](https://github.com/a2aproject/A2A/compare/v0.2.3...v0.2.4) (2025-06-30)


### Features

* feat: Add support for multiple transport announcement in AgentCard ([#749](https://github.com/a2aproject/A2A/issues/749)) ([b35485e](https://github.com/a2aproject/A2A/commit/b35485e02e796d15232dec01acfab93fc858c3ec))

## [0.2.3](https://github.com/a2aproject/A2A/compare/v0.2.2...v0.2.3) (2025-06-12)


### Bug Fixes

* Address some typos in gRPC annotations ([#747](https://github.com/a2aproject/A2A/issues/747)) ([f506881](https://github.com/a2aproject/A2A/commit/f506881c9b8ff0632d7c7107d5c426646ae31592))

## [0.2.2](https://github.com/a2aproject/A2A/compare/v0.2.1...v0.2.2) (2025-06-09)


### ⚠ BREAKING CHANGES

* Resolve spec inconsistencies with JSON-RPC 2.0

### Features

* Add gRPC and REST definitions to A2A protocol specifications ([#695](https://github.com/a2aproject/A2A/issues/695)) ([89bb5b8](https://github.com/a2aproject/A2A/commit/89bb5b82438b74ff7bb0fafbe335db7100a0ac57))
* Add protocol support for extensions ([#716](https://github.com/a2aproject/A2A/issues/716)) ([70f1e2b](https://github.com/a2aproject/A2A/commit/70f1e2b0c68a3631888091ce9460a9f7fbfbdff2))
* **spec:** Add an optional iconUrl field to the AgentCard ([#687](https://github.com/a2aproject/A2A/issues/687)) ([9f3bb51](https://github.com/a2aproject/A2A/commit/9f3bb51257f008bd878d85e00ec5e88357016039))


### Bug Fixes

* Protocol should released as 0.2.2 ([22e7541](https://github.com/a2aproject/A2A/commit/22e7541be082c4f0845ff7fa044992cda05b437e))
* Resolve spec inconsistencies with JSON-RPC 2.0 ([628380e](https://github.com/a2aproject/A2A/commit/628380e7e392bc8f1778ae991d4719bd787c17a9))

## [0.2.1](https://github.com/a2aproject/A2A/compare/v0.2.0...v0.2.1) (2025-05-27)

### Features

* Add a new boolean for supporting authenticated extended cards ([#618](https://github.com/a2aproject/A2A/issues/618)) ([e0a3070](https://github.com/a2aproject/A2A/commit/e0a3070fc289110d43faf2e91b4ffe3c29ef81da))
* Add optional referenceTaskIds for task followups ([#608](https://github.com/a2aproject/A2A/issues/608)) ([5368e77](https://github.com/a2aproject/A2A/commit/5368e7728cb523caf1a9218fda0b1646325f524b))
