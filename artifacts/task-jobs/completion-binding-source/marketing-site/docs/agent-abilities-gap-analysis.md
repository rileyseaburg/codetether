# Agent Abilities Gap Analysis

## Scope
This assessment compares **what the marketing dashboard says/does for agent abilities** against what is currently exposed by the `codetether-agent` server runtime.

Reference surfaces reviewed:
- Marketing UI ability pages/hooks in `src/app/(dashboard)/dashboard/**`, `src/hooks/**`, and `src/lib/api/**`.
- Agent server routes and runtime behavior in `../codetether-agent/src/server/mod.rs`, `../codetether-agent/src/a2a/**`, and `../codetether-agent/src/k8s/mod.rs`.

## Executive Summary
The marketing site is operating as if a broader control-plane API exists (`/v1/agent/*`, `/v1/worker/*`, `/v1/tasks/dispatch`, `/mcp/v1/*`, `/v1/voice/*`). In the current `codetether-agent` server, only a subset is present directly (notably `/v1/cognition/*`, `/v1/swarm/*`, `/v1/k8s/*`, `/v1/tools`, `/v1/bus/stream`, and `/a2a`).

This means the site is taking real product leaps in orchestration UX, but several abilities are currently dependent on external backends or missing compatibility routes.

## Where Marketing Site Is Taking Leaps (Abilities First)
- **Multi-worker operations console**: The dashboard acts like a full worker fleet control plane (presence, dispatch, stream output, targeted worker metadata), not just a single-agent UI. (`src/app/(dashboard)/dashboard/workers/page.tsx:468`, `src/app/(dashboard)/dashboard/tasks/page.tsx:332`)
- **Distributed swarm observability UX**: It exposes swarm decomposition, progress stages, subtask-level statuses, and speedup summaries, effectively presenting a branch-level orchestration monitor. (`src/app/(dashboard)/dashboard/page.tsx:429`, `src/app/(dashboard)/dashboard/tasks/page.tsx:88`)
- **One-click voice + infra launch path**: Voice flow can deploy a worker pod and then bootstrap a voice session from UI, implying an autonomous infra+agent control plane. (`src/app/(dashboard)/dashboard/components/voice/VoiceAgentButton.tsx:109`)
- **Cognition operator cockpit**: The cognition page already models beliefs, attention, proposals, receipts, lineage, and approvals, which is beyond normal “chat with agent” UX and closer to governance-grade runtime operations. (`src/app/(dashboard)/dashboard/cognition/page.tsx:356`)

## Ability-First Gap Matrix

| Priority | Ability | Marketing Site Behavior | `codetether-agent` Reality | Gap | Recommended Closure |
|---|---|---|---|---|---|
| P0 | Worker/task control plane | Core dashboards use `/v1/agent/workers`, `/v1/agent/tasks`, `/v1/agent/codebases/*`, `/v1/worker/connected`, `/v1/tasks/dispatch` for live ops and dispatch. (`src/app/(dashboard)/dashboard/workers/page.tsx:468`, `src/app/(dashboard)/dashboard/tasks/page.tsx:306`, `src/app/(dashboard)/dashboard/tasks/page.tsx:332`, `src/app/(dashboard)/dashboard/page.tsx:462`) | Route list in server does **not** expose `/v1/agent/*`, `/v1/worker/*`, or `/v1/tasks/dispatch`; it exposes `/v1/cognition/*`, `/v1/swarm/*`, `/v1/k8s/*`, `/v1/tools`, `/v1/bus/stream`, `/a2a`. (`../codetether-agent/src/server/mod.rs:622`) | Main dashboard abilities are not served by standalone agent runtime. | Decide architecture explicitly: 1) keep separate A2A control-plane service and document dependency, or 2) add compatibility routes in `codetether-agent` for the endpoints used by UI. |
| P0 | MCP tool catalog | MCP page calls `listToolsMcpV1ToolsGet` => `/mcp/v1/tools`. (`src/app/(dashboard)/dashboard/mcp/page.tsx:53`, `src/lib/api/generated/sdk.gen.ts:6888`) | Server exposes `/v1/tools` (not `/mcp/v1/tools`). (`../codetether-agent/src/server/mod.rs:689`) | Namespace mismatch causes MCP catalog calls to fail against this server. | Add `/mcp/v1/tools` alias route or switch UI SDK call to `/v1/tools`. |
| P0 | Voice session launch | Voice button deploys pod via `/v1/k8s/subagent`, then creates voice room via REST `/v1/voice/sessions`. (`src/app/(dashboard)/dashboard/components/voice/VoiceAgentButton.tsx:109`, `src/app/(dashboard)/dashboard/components/voice/VoiceAgentButton.tsx:135`) | K8s subagent endpoint exists. (`../codetether-agent/src/server/mod.rs:681`) Voice is currently gRPC service only (no REST `/v1/voice/sessions` route). (`../codetether-agent/src/server/mod.rs:568`) gRPC voice session currently returns empty `access_token` stub. (`../codetether-agent/src/a2a/voice_grpc.rs:60`) | UI assumes Python REST voice backend semantics that agent server does not implement directly. | Add REST voice adapter (`/v1/voice/*`) in agent server or explicitly route voice to external service in tenant config; align response contract (token/livekit_url). |
| P1 | A2A discovery contract | Generated API expects `/.well-known/agent-card.json`. (`src/lib/api/generated/sdk.gen.ts:819`) | A2A HTTP router serves `/.well-known/agent.json`. (`../codetether-agent/src/a2a/server.rs:38`) | Discovery path mismatch for card endpoint clients. | Serve both paths (keep existing + add `agent-card.json` alias). |
| P1 | Session resume/status consistency | Session resume poll expects status enum with `working`. (`src/app/(dashboard)/dashboard/sessions/hooks/useSessionResume.ts:18`) Other UI flows key on `running`. (`src/app/(dashboard)/dashboard/tasks/page.tsx:429`) | Inconsistent status assumptions in UI; backend status vocabulary may differ per service. | Possible polling dead states or wrong UX transitions. | Normalize to one canonical status model (`pending/running/completed/failed/cancelled`) in shared type module and adapters. |
| P1 | Endpoint target topology clarity | UI defaults tenant API to `https://api.codetether.run`. (`src/hooks/useTenantApi.ts:26`) Next rewrites also point to hardcoded private IP defaults for cognition/A2A. (`next.config.js:22`) | Multiple implicit backends are assumed with different target paths. | Local/prod behavior can diverge silently; difficult debugging. | Require explicit env for each backend in non-prod and fail fast when unset. Remove hardcoded private IP defaults. |
| P1 | Swarm telemetry contract stability | Swarm monitor derives state by parsing free-text `[swarm] ...` output from task stream. (`src/app/(dashboard)/dashboard/tasks/page.tsx:88`, `src/app/(dashboard)/dashboard/page.tsx:429`) | Worker currently emits matching text lines (`[swarm] started/stage/subtask/complete`). (`../codetether-agent/src/a2a/worker.rs:673`) | Works today but brittle; log format changes break dashboard state machine. | Add structured swarm telemetry events/API (JSON schema) and deprecate text parsing path. |
| P2 | gRPC path not used for core dashboards | Typed gRPC clients/hooks exist for A2A + Voice. (`src/lib/grpc/client.ts:5`, `src/hooks/useA2AService.ts:28`, `src/hooks/useVoiceService.ts:26`) | Agent server does expose gRPC A2A + Voice. (`../codetether-agent/src/server/mod.rs:560`) | Core operator flows still rely mainly on REST/SSE legacy surface. | Migrate high-value flows (task status, subscription, voice state) to gRPC where possible; keep REST only for compatibility. |

## What Is Already Strongly Aligned
- Cognition control surface is well aligned: UI uses `/v1/cognition/*` and `/v1/swarm/*` (via `/api/*` rewrites), and server exposes these routes. (`src/app/(dashboard)/dashboard/cognition/page.tsx:356`, `../codetether-agent/src/server/mod.rs:647`)
- K8s subagent lifecycle has real implementation with pod spec, labels, retries on 409 conflict, and delete support. (`../codetether-agent/src/server/mod.rs:681`, `../codetether-agent/src/k8s/mod.rs:423`)
- Worker capability model includes `ralph`, `swarm`, `rlm`, `a2a`, `mcp`, which matches product direction. (`../codetether-agent/src/a2a/worker.rs:398`)

## Concrete API Gaps (Ability Surfaces)
- Missing in current server route table for standalone runtime: `/v1/agent/*`, `/v1/worker/*`, `/v1/tasks/dispatch`, `/mcp/v1/*`, `/v1/voice/*`.
- Present and stable: `/v1/cognition/*`, `/v1/swarm/*`, `/v1/k8s/*`, `/v1/tools`, `/v1/bus/stream`, `/a2a`.

## Suggested Execution Order
1. **P0 compatibility layer**: add aliases/adapters for `/mcp/v1/tools`, `/.well-known/agent-card.json`, and voice REST bridge if this runtime is meant to back the dashboard directly.
2. **P0 architecture decision**: codify whether marketing-site targets a dedicated control-plane API service or `codetether-agent` directly; enforce with env validation.
3. **P1 contract cleanup**: unify task status enums and replace swarm text parsing with structured telemetry.
4. **P2 transport convergence**: incrementally move dashboard critical paths to gRPC A2A where available.
