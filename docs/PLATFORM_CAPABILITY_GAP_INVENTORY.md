# Platform capability and audit gap inventory

## Scope and evidence boundary

This inventory supports real CodeTether capability and audit closure, not
reducing product claims or treating a subset as the full platform objective.
It is a review artifact, not implementation, deployment, or release evidence.

The child checkout is based on `336f5fd88707887c2747939438c48115350fa6cd`.
The pinned Rust submodule is `8d9bf0c49e2a842e457f147f80c8c6945069c7c9`.
Parent uncommitted edits are not copied here. A subsequent **static/local**
reconciliation inspected CURRENT UI sources and retained artifacts read-only
at `/home/riley/A2A-Server-MCP`; parent-only evidence paths below resolve against
that root, not this child checkout. UI dispositions include selectively
integrated parent changes. Retained **mocked local** UI, worker and voice results
are listed below; the child did not rerun application tests. The separately
named `ui-combined-jest.log` was absent during child inspection. Parent review
now directly observes **mocked local** 11-suite/194-test results in
`artifacts/ui-audit/parent-handoff/ui-tests.log` and `ui-results.json`, plus
15 passing auth tests in `auth-tests.log`. Parent source/evidence review does not establish
broader Python/Rust contract parity or runtime acceptance. Live/platform evidence
is **not-run**. Auth/checkout integration into this child is not implied by
inspection of CURRENT parent files.
The full platform implementation objective remains **pending**.

Parent Rust session recovery has since changed from the pinned child source:
`/home/riley/A2A-Server-MCP/codetether-agent/src/server/session_recovery.rs`
now calls `Session::resume(id).await?`, saves the same identity, and propagates
storage failures instead of creating a replacement session. Its `errors.rs`
maps typed `NotFound` errors to HTTP 404 and other recovery errors to HTTP 500.
This is **static/local** parent-source repair evidence only; its test files
were inspected, not executed here. The parent handler still ignores
`_codebase_id`. Tenant/codebase/session authorization, full CRUD, dashboard
contract compatibility and runtime recovery acceptance remain **pending/not-run**.

### Evidence labels and source boundaries

- **static/local** means inspected source or an observed document/source-link
  check. Route presence is not successful execution.
- **not-run** means tests or runtime behavior were not observed here. Test
  files are coverage candidates, not passing evidence.
- **pending** means implementation or stronger evidence remains required.
- **blocked** identifies an unavailable prerequisite for a specific slice.
  A blocked source review is not evidence that a capability is unavailable.

No child application-test execution, live Argo checks, provider calls, or
platform uploads are asserted by this document. Preserve incoming evidence
with its actual level: mocked local, focused CI-like, live deployment/Argo,
or real platform upload. Do not transfer one slice's proof to another runtime.

Authoritative sources inspected here:

- [Agent abilities audit](../web/docs/agent-abilities-gap-analysis.md)
- [Repository audit](REPOSITORY_AUDIT.md)
- [Marketing refactor plan](../web/marketing-site-refactor-plan.md)
- [Integration audit](../codetether-docs/integrations/gap-analysis.md)
- [Roadmap](../web/src/components/Roadmap.tsx)
- [Primary claims](../web/src/components/PrimaryFeatures.tsx)

The designated parent `artifacts/ui-audit/AUDIT.md` is now readable and was
inspected **static/local**, removing the unavailable-original-audit blocker.
Its eight numbered findings and additional shell observations are reconciled
below against CURRENT parent files. The audit covers marketing/auth, the
dashboard shell and selected Tasks/Sessions/Settings/Billing flows, not all
routes or WCAG conformance. Its fixture-backed probes are **mocked local**,
not live authentication, payments, native IME or real-media acceptance.

## Agent API and dashboard contracts

The historical agent audit must be read against both backends. The Python
control plane mounts monitoring, worker, billing, tenant, automation,
and dispatch routers in [server.py](../a2a_server/server.py). Dashboard API
origin/proxy selection is implemented by
[useTenantApi](../web/src/hooks/useTenantApi.ts),
[api-origin](../web/src/lib/api-origin.ts), and
[Next rewrites](../web/next.config.js). Python route presence and
Rust route presence are separate facts; neither certifies tenant discovery,
authorization, frontend response compatibility, or a connected executor.

| Finding | Current evidence (static/local) | Remaining capability/evidence |
| --- | --- | --- |
| Worker list/discovery routes | Rust now mounts both `/v1/agent/workers` and `/v1/worker/connected` through [worker_modules](../codetether-agent/src/server/worker_modules.rs). Python owners are [monitor_api](../a2a_server/monitor_api.py), [worker_sse](../a2a_server/worker_sse.py), and [worker_auth](../a2a_server/worker_auth.py). | Historical route-absence finding is stale. **Pending:** inspect integrated parent tenant discovery/auth repairs; exercise viewer isolation, worker credentials, liveness, and dashboard discovery. Not-run here. |
| Task list/create/output and dispatch | [Rust server](../codetether-agent/src/server/mod.rs) includes `/v1/agent/tasks`, task output/stream, and `/v1/tasks/dispatch`; task storage is `Arc<Mutex<Vec<KnativeTask>>>`. Dispatch pushes a pending item and publishes a bus event, then reports `dispatched_via_knative: true`. Python [automation_api](../a2a_server/automation_api.py) and [monitor_api](../a2a_server/monitor_api.py) provide control-plane task surfaces. | Historical blanket absence is stale. **Pending:** durable execution lifecycle, model/metadata propagation, cancellation/output semantics, worker claim/release compatibility, and truthful dispatch reporting. A bus event plus an in-memory entry is not proof that a Knative job ran. |
| Codebase/session control plane | Python [monitor_api](../a2a_server/monitor_api.py) supplies the dashboard's codebase/session family. Rust has a codebase-scoped resume route, but not the full `/v1/agent/codebases` CRUD/session family in its server router. | **Pending:** real standalone-Rust codebase/session contracts or a functional, explicitly supported control-plane integration. Do not silently narrow the platform to whichever routes happen to exist. |
| Session resume | The pinned child [resume handler](../codetether-agent/src/server/mod.rs) ignores `_codebase_id` and creates a session after any load error. Current parent `session_recovery.rs` instead preserves the requested identity and propagates failures, with typed 404/500 classification; its route still ignores `_codebase_id`. Both return terminal completion/error JSON when a prompt executes. The dashboard [resume hook](../web/src/app/(dashboard)/dashboard/sessions/hooks/useSessionResume.ts) consumes its task/session contract. | **Pending:** compare request/response and SSE/task-state behavior, bind sessions to authorized tenant/codebase, verify missing/forbidden/storage-error handling and identity preservation, and test terminal/error recovery. Parent source repair is not compatibility or runtime proof. |
| MCP tool catalog alias | Rust [server](../codetether-agent/src/server/mod.rs) mounts both `/v1/tools` and `/mcp/v1/tools` to `list_tools`; Python [mcp_http_server](../a2a_server/mcp_http_server.py) also exposes `/mcp/v1/tools`. | Alias-absence finding is stale. **Pending/not-run:** verify catalog payload shape, tool executability, registration heartbeat, and dashboard SDK behavior, not just the path. |
| A2A discovery aliases | Rust [A2A server](../codetether-agent/src/a2a/server.rs) has `/.well-known/agent.json` and `/.well-known/agent-card.json`. | Alias absence is stale at this pin. **Pending/not-run:** advertised endpoint/transport/auth correctness in the actual tenant environment and dashboard clients. |
| Voice REST/gRPC | Rust [REST bridge](../codetether-agent/src/server/mod.rs) and [gRPC voice service](../codetether-agent/src/a2a/voice_grpc.rs) expose voice entry points but return empty access tokens; REST lookup reports active without a session lookup. Python [monitor_api](../a2a_server/monitor_api.py) already owns `create_voice_session`, `get_voice_session`, `delete_voice_session` and `voice_router`; [server](../a2a_server/server.py) mounts it. Separate parent-reported `a2a_server/voice_api.py` is absent at this base and requires integration-time inspection; that absence does not imply missing Python voice support. | **Pending:** credential issuance, real room/session lifecycle, ownership, worker launch/auth, and real-time media integration. Parent voice local tests must be retained and inspected after integration; they do not imply a live LiveKit call or platform upload. |
| Task state and swarm visibility | Dashboard [task page](../web/src/app/(dashboard)/dashboard/tasks/page.tsx) and [resume hook](../web/src/app/(dashboard)/dashboard/sessions/hooks/useSessionResume.ts) translate executor responses and stream events; worker execution and server responses use different state vocabularies. | **Pending/not-run:** explicit accepted→pending→working/running→terminal mappings and structured swarm telemetry across direct agent, worker, server, and frontend. A displayed text line is not equivalent to correlated lifecycle telemetry. |

### Python versus Rust contract reconciliation

This matrix is **static/local** at the revisions above. An alias establishes
routing, not payload, authorization, persistence or executor parity. Python is
the dashboard control-plane reference for reconciliation, not a certified
implementation. Owners must deliver equivalent contracts or an explicit
supported topology and adapter without removing advertised capabilities.
Acceptance below is **pending/not-run** here; parent changes need separate review.

| ID / priority / owner | Dashboard contract | Current Python implementation (static/local) | Current Rust implementation and alias disposition (static/local) | Remaining acceptance / dependencies |
| --- | --- | --- | --- | --- |
| C01 / P0 / worker + security | `/v1/agent/workers`, `/v1/worker/connected`; [voice consumer](../web/src/app/(dashboard)/dashboard/components/voice/VoiceAgentButton.tsx). | [monitor_api: list_workers](../a2a_server/monitor_api.py) returns a worker list; [worker_sse: list_connected_workers](../a2a_server/worker_sse.py) authenticates worker/user requests and returns `{workers, count, timestamp}` from the SSE registry. Parent visibility repair is outside this snapshot. | Both URLs alias `list_connected_workers` via [worker_modules](../codetether-agent/src/server/worker_modules.rs). [Handler](../codetether-agent/src/server/mod.rs) returns `{workers}` from name-filtered Kubernetes pods; `Running` becomes `is_sse_connected`, and pod-list errors become an empty list. **Aliases present; shapes and liveness differ.** | Integrate parent repair; reconcile list/envelope, capability/model discovery, true connection liveness, stale workers and errors; exercise user/worker credentials and cross-tenant denial. Parent reports an existing **mocked local 24-test artifact**, not inspected here; rerun pending. |
| C02 / P0 / execution + control plane | Create/dispatch/poll tasks: `/v1/agent/tasks/*`, `/v1/tasks/dispatch`; [task dashboard](../web/src/app/(dashboard)/dashboard/tasks/page.tsx). | [monitor_api](../a2a_server/monitor_api.py) owns agent-task operations. [automation_api: dispatch_task](../a2a_server/automation_api.py) requires `UserSession`, persists a database task, attempts Knative publication and falls back to the task queue; returns `event_id`, `created_at`, `task_timeout_seconds` and a flag derived from publication. This is not observed execution. | [Server handlers](../codetether-agent/src/server/mod.rs) expose task/dispatch aliases but use in-memory `KnativeTaskQueue`. Dispatch returns `{task_id, status, dispatched_via_knative: true}` after bus publication and enqueue; model/metadata are not retained. **Routing exists; response, persistence and execution are not equivalent.** | First gate: durable tenant-owned run, preserve request fields, distinguish accepted/queued/executing/terminal, truthful dispatch mode, executor acknowledgement, cancel/retry/restart recovery. Depends on C01 and worker claim/release ownership; broker publication alone is not task success. |
| C03 / P0 / runtime + telemetry + security | Output GET/POST and `/v1/agent/tasks/{id}/output/stream`; [EventSource consumer](../web/src/app/(dashboard)/dashboard/tasks/page.tsx). | [monitor_api: get_task_output / stream_task_output_sse](../a2a_server/monitor_api.py) returns `{task_id, outputs, total}` with optional `since`, and emits `output`/terminal SSE using process-local `_task_output_streams`. History in source does not prove durable replay or authorization. | [get_agent_task_output / agent_task_output / stream_agent_task_output](../codetether-agent/src/server/mod.rs) returns `output: null`, ignores submitted worker ID, marks task `working` and broadcasts; SSE has no cursor replay and prefix-matches task topics. **Routes present; output/event contracts differ.** | Persist ordered tenant-owned chunks; authenticate assigned worker; preserve terminal state; exact task matching; cursor/reconnect, lag and restart recovery; test consumer event names/payloads/errors against both supported backends. Depends on C02; parent SSE repair does not close standalone Rust. |
| C04 / P1 / control plane + dashboard | Codebase/workspace/session CRUD and resume; [resume hook](../web/src/app/(dashboard)/dashboard/sessions/hooks/useSessionResume.ts). | [monitor_api](../a2a_server/monitor_api.py) owns workspace/session APIs, persistence helpers and `/workspaces/{workspace_id}/sessions/{session_id}/resume`; [server mount](../a2a_server/server.py) provides codebase compatibility routing. Workspace-to-codebase mapping needs contract tests. | The pinned child [resume_codebase_session](../codetether-agent/src/server/mod.rs) exposes `/v1/agent/codebases/{id}/sessions/{id}/resume` but ignores `_codebase_id`, creates a session after any load error, and lacks the corresponding full CRUD family. Current parent `session_recovery.rs` preserves identity and propagates failures with typed 404/500 classification (see source-drift note above); its route still ignores `_codebase_id`. **One resume alias is not the control plane.** | Bind tenant/workspace/codebase/session identity; distinguish missing, forbidden and load failure; reconcile resume body/return/stream and model selection, durable lifecycle and lineage. Depends on C02/C03 and explicit API topology; parent source repair is not runtime acceptance. |
| C05 / P1 / tools + MCP + security | Catalog `/mcp/v1/tools`, registration/heartbeat and tool invocation; [MCP consumer](../web/src/app/(dashboard)/dashboard/mcp/page.tsx). | [mcp_http_server](../a2a_server/mcp_http_server.py) owns MCP HTTP catalog/invocation; [monitor_api](../a2a_server/monitor_api.py) owns agent tool registration/heartbeat. Routes are not proof of executable tools. | [Server](../codetether-agent/src/server/mod.rs) mounts both `/v1/tools` and `/mcp/v1/tools` to `list_tools` (`Vec<RegisteredToolView>`), plus registration/heartbeat. **Historical missing catalog alias is stale.** | Reconcile schema/wrappers, stable tool IDs, expiry and heartbeat; execute a registered tool with tenant scopes, approvals, structured errors, cancellation, receipts and artifact access. Visibility must reflect authorization, not just registry contents. |
| C06 / P0 / voice + worker + security | `/v1/voice/sessions`, credential/room lookup/cleanup; [VoiceAgentButton](../web/src/app/(dashboard)/dashboard/components/voice/VoiceAgentButton.tsx) consumes `access_token`, `livekit_url`, `room_name`. | [monitor_api: create_voice_session / get_voice_session / delete_voice_session](../a2a_server/monitor_api.py) already creates bridge rooms, dispatches the named LiveKit voice agent, mints participant tokens, looks up room metadata and cleans up after dispatch failure. Separate parent `voice_api.py` is absent here, **not evidence that Python voice is absent**. | [REST handlers](../codetether-agent/src/server/mod.rs) and [VoiceServiceImpl](../codetether-agent/src/a2a/voice_grpc.rs) expose sessions but return empty tokens; REST lookup reports active without checking a room/session. **REST alias exists; usable credential/lifecycle parity missing.** | Integrate parent changes; authenticate owner/worker, mint nonempty room-scoped expiring tokens, align lookup/expiry/reconnect/delete and idempotent cleanup. Retain mocked failure-path evidence; real authorized media is **not-run**, with no platform/upload claim. Depends on C01/C02 and configured services. |
| C07 / P1 / protocol + security | `/.well-known/agent-card.json` and legacy `/.well-known/agent.json`. | [a2a_agent_card](../a2a_server/a2a_agent_card.py) and [server](../a2a_server/server.py) own card construction/mounting. | [a2a/server](../codetether-agent/src/a2a/server.rs) mounts both aliases at root and under `/a2a`. **Historical missing standardized alias is stale.** | Verify advertised URL/version/transports/authentication/skills against callable endpoints; test both aliases and deployment prefixes. Discovery success is not transport parity. |
| C08 / P1 / telemetry + dashboard | Task status, cognition and swarm data; [task UI](../web/src/app/(dashboard)/dashboard/tasks/page.tsx) and [swarm UI](../web/src/app/(dashboard)/dashboard/page.tsx). | [Models](../a2a_server/models.py) and [monitor_api](../a2a_server/monitor_api.py) provide task state/output surfaces. Cognition has a separately configured [Next proxy backend](../web/next.config.js); task APIs alone do not establish a Python cognition contract. Tenancy, backend identity and durable replay need acceptance. | [Server](../codetether-agent/src/server/mod.rs) provides task/cognition/swarm routes; internal A2A states and dashboard task states differ. The dashboard still parses `[swarm]` text. **Aligned routes are not typed telemetry or governance proof.** | Typed state/event mapping preserving blocked/cancelled/error/terminal semantics; correlation IDs, ordered replay, lineage, receipts and real completion aggregation. Depends on C02/C03; labels are not execution evidence. |
| C09 / P2 / transport + dashboard + infrastructure | Typed A2A/Voice consumers versus REST/SSE, origins and proxy routing. | [Server mounts](../a2a_server/server.py) remain the REST control plane; [tenant API](../web/src/hooks/useTenantApi.ts) and [Next rewrites](../web/next.config.js) determine dashboard routing. | [gRPC-Web registration](../codetether-agent/src/server/mod.rs), [browser client](../web/src/lib/grpc/client.ts) and [A2A hooks](../web/src/hooks/useA2AService.ts) exist, but inspected task/voice dashboard consumers use REST/SSE. **Typed clients do not equal adoption.** | Resolve Python/Rust topology, API/gRPC origins and TLS/proxy configuration; adopt typed consumers with documented compatibility exceptions; regenerate from authoritative proto/OpenAPI without hand edits. Cross-transport identity, lifecycle, ownership/reconnect checks remain **not-run**; see the gRPC gate below. |
| C10 / P0 / security + governance | Approval creation/decision, actor identity and scope; do not equate authorization middleware with an approval workflow. | [Policy middleware](../a2a_server/policy_middleware.py) resolves `request.state.policy_user`; [server](../a2a_server/server.py) mounts centralized authorization. These sources establish the authorization layer, **not Python/Rust approval-workflow parity**. | [Approval request](../codetether-agent/src/server/approval_routes/request.rs) opens the default store; [decision handler](../codetether-agent/src/server/approval_routes/decision.rs) accepts `body.actor` (defaults to `server`) and may grant session approval. [Server policy middleware](../codetether-agent/src/server/mod.rs) checks permission without a resource argument. **Approval routes exist; actor/resource binding requires review.** | Derive actor and tenant from authenticated identity, bind tenant/session/tool/arguments, enforce expiry/revocation and replay denial, and resume only the matching request. Exercise cross-tenant and forged-actor rejection and receipts. No exploit is claimed; acceptance **not-run**. Depends on C02/C04 and policy ownership. |

### C03 reconciliation: durable Python output and terminal replay

The C03 matrix above retains the earlier snapshot; it is not a description of all
current parent sources. **Static/local** inspection of
`a2a_server/monitor_api.py::{post_task_output,get_task_output,stream_task_output_sse}`
and `a2a_server/task_output.py` now shows durable append/read helpers, task-owned
read authorization, assigned-worker checks, exclusive replay cursors and
authorization before SSE success headers. SSE drains every page before emitting
`done` with `task_id`, terminal `status` and `next_cursor`; subsequent read failures
close the stream without reporting successful completion. Reconnects reauthorize.

**Static/local** inspection of
`web/src/lib/task-output-stream.ts::watchTaskOutput` shows authenticated
replay before reconnect and before the completion callback, including legacy
cursorless completion. Invalid task identities, backward/invalid terminal cursors
and incomplete terminal replay are errors, not completion.

Retained **mocked local** evidence:
`artifacts/task-output/terminal-cursor/producer-and-replay-verification.xml`
(51 tests, zero failures/errors/skips) and
`artifacts/task-output/terminal-cursor/dashboard-combined-regressions.json`
(7 suites, 91 tests). Producer tests are in `tests/test_task_output_sse.py`;
consumer tests are in `web/tests/task-output-completion.test.cjs`.
These artifacts do not demonstrate a live database, HTTP authentication, worker
execution, cross-replica deployment or Rust parity.

**Pending:** standalone Rust durable output and assigned-worker/tenant ownership,
cross-backend consumer contracts, and database-backed restart/replica tests. The
current Rust exact-topic adapter (`src/server/task_output_stream.rs`) must be
distinguished from the pinned prefix-match snapshot; exact matching alone does
not satisfy these remaining C03 gates. Live deployment proof is **not-run**.

### P2 — gRPC path not used for core dashboards

The eighth matrix finding in the [ability-first audit](../web/docs/agent-abilities-gap-analysis.md) remains **pending**, independently of the voice credential gap. **Static/local:** the [browser client](../web/src/lib/grpc/client.ts) creates typed A2A and Voice gRPC-Web clients from generated service descriptors; `NEXT_PUBLIC_GRPC_URL` defaults to `http://localhost:50051`. [A2A hooks](../web/src/hooks/useA2AService.ts) implement task lookup, agent-card lookup, message submission, subscription, and cancellation; [Voice hooks](../web/src/hooks/useVoiceService.ts) implement session creation/lookup/deletion, voice listing, and event subscriptions. The [Rust server](../codetether-agent/src/server/mod.rs) constructs `GrpcTaskStore` and `VoiceServiceImpl`, serves both services with HTTP/1 support, CORS and `GrpcWebLayer`, and defaults `CODETETHER_GRPC_PORT` to `50051`. [Buf generation configuration](../specification/grpc/buf.gen.yaml) produces browser descriptors from the agent's stripped protobuf source. These are available interfaces, not proof of dashboard adoption or transport equivalence.

**Static/local actual consumers:** the [task dashboard](../web/src/app/(dashboard)/dashboard/tasks/page.tsx) dispatches with `fetch` to `/v1/tasks/dispatch` and subscribes to task output with `EventSource`; the [session resume hook](../web/src/app/(dashboard)/dashboard/sessions/hooks/useSessionResume.ts) uses the REST control-plane task/session contract. The [voice launch button](../web/src/app/(dashboard)/dashboard/components/voice/VoiceAgentButton.tsx) uses tenant REST worker discovery and `/v1/voice/sessions`. Existing typed hooks do not close the historical core-dashboard adoption finding, and repairing REST voice tokens would not close it either.

**Owner:** dashboard, Rust A2A/Voice, control-plane and security maintainers jointly. **Dependencies:** explicit endpoint/tenant/auth topology below and in the backend ownership section; durable dispatch/output and canonical task states (N01/N02); subscription recovery and correlated telemetry (N03); authenticated ownership and credentials for voice (S13/F07). Establish the shared run/session lifecycle before moving consumers between stores or transports. Keep necessary REST/SSE compatibility with explicit ownership and regression coverage; do not remove capabilities merely to make the transport uniform.

**Closure recommendation and acceptance — pending/not-run:**

1. Identify the supported operator consumers and migrate high-value task status/subscription and voice-state flows to the typed A2A/Voice services where appropriate. Record intentional REST/SSE exceptions, their backend owners and compatibility contracts; unused clients are not adoption evidence.
2. Verify protobuf/service and generated-client agreement through the documented generation workflow; do not hand-edit generated clients. Exercise real consumers against supported endpoints, checking task/run identity, canonical state mapping, dispatch acceptance, output ordering and terminal behavior against the retained REST/SSE contracts.
3. Test tenant-scoped authentication/authorization, configured URLs, CORS/browser reachability, cancellation, disconnect/reconnect, subscription recovery, failure propagation and voice session ownership/deletion. A shared bus alone does not prove that REST and gRPC expose the same durable task state.
4. Attach focused commands, results and browser/contract artifacts. Label fixture-based transport probes **mocked local**; application/browser acceptance here is **not-run**. Live-deployment or real-media proof is required only when requested, and must name concrete identities/artifacts rather than infer operation from service registration.

### P1 — Endpoint target topology clarity

The transport-adoption discussion does not replace the separate endpoint-topology finding in the [ability-first audit](../web/docs/agent-abilities-gap-analysis.md). **Static/local mixed disposition:** the [Next proxy configuration](../web/next.config.js) now reads `COGNITION_API_BACKEND` and `A2A_API_BACKEND`; when unset, it warns and disables the corresponding rewrites. The audit's hardcoded private-IP-default claim is stale for this file. This is not fail-fast environment validation. The [tenant API hook](../web/src/hooks/useTenantApi.ts) still defaults `NEXT_PUBLIC_API_URL` to `https://api.codetether.run`, while the [gRPC client](../web/src/lib/grpc/client.ts) defaults to localhost separately. **Owner:** dashboard, platform and control-plane maintainers. **Dependencies:** explicit Python/Rust/voice backend ownership and tenant identity mapping. **Pending/not-run:** environment/tenant endpoint selection and validation, correct proxy/direct routing, browser authentication and CORS, and clear failure states when a required backend is unset or unavailable. Cover local and production topology without silently falling back to a different service; do not present a localhost gRPC default or existing REST rewrite as deployment proof.

## UI findings retained from the active assignment

The original [UI audit](../artifacts/ui-audit/AUDIT.md) is available and remains
the source for all eight findings and four shell observations. Current repair
dispositions below must distinguish static source review, retained mocked-local
test artifacts, and pending runtime acceptance; neither source presence nor a

| Finding | Current source and status | Required remaining proof/action |
| --- | --- | --- |
| Signup must enter Auth.js/PKCE flow | [Register](../web/src/app/(auth)/register/page.tsx) submits the realm to [startWorkspaceSignIn](../web/src/app/(auth)/actions.ts), which validates the realm, sets an HTTP-only selector and calls Auth.js `signIn`; it does not redirect to signup-response `login_url`. [Auth configuration](../web/src/auth.ts) and [tenant selector](../web/src/lib/tenant-auth.ts) own issuer/PKCE setup. **Static/local repair present; behavioral acceptance not-run.** Parallel auth/checkout integration still needs inspection. | Inspect integrated register handler and exercise PKCE/state/callback, expired/error states, and real identity-provider behavior when live evidence is requested. |
| Password-authenticated paid checkout misidentified as unauthenticated | [Pricing](../web/src/components/Pricing.tsx) uses [getApiAuth](../web/src/lib/auth-token.ts) and sends its bearer token to checkout, covering stored password credentials and Auth.js sessions rather than checking Auth.js alone. [Billing](../web/src/app/(dashboard)/dashboard/billing/page.tsx) remains a second consumer. **Static/local repair present; behavioral acceptance not-run.** Parallel auth/checkout ownership and integration remain separate. | Cover credentials and OIDC sessions, token refresh, server-authoritative checkout identity, subscription selection, failures, and return/cancel flows. Local fixtures are not Stripe payment proof. |
| Closed mobile navigation remains keyboard-focusable | [Dashboard layout](../web/src/app/(dashboard)/layout.tsx) now uses Headless UI `Dialog` with an unmounted closed drawer and focus restoration. **Static/local repair present.** | Not-run here: keyboard/focus restoration, Escape, responsive transitions, screen-reader semantics, and regressions against the original audit. |
| Task row not keyboard-operable | [Task page](../web/src/app/(dashboard)/dashboard/tasks/page.tsx) now renders selectable task cards as buttons with `aria-pressed`, `aria-controls`, and visible focus styles. **Static/local repair present.** | Not-run here: Enter/Space selection, details focus, mobile/back navigation, and stream update stability. |
| Test Key ignores a newly entered key | [Settings](../web/src/app/(dashboard)/dashboard/settings/page.tsx) sends `api_key: apiKey.trim()` and distinguishes unsupported custom-endpoint/untested outcomes. **Static/local repair present.** | Not-run here: server uses the candidate key without saving/logging it, invalid and unsupported providers fail honestly, and custom-endpoint testing is implemented. Unsupported endpoint testing remains a real capability gap, not a successful key verification. |
| IME Enter prematurely submits | [Session ChatInput](../web/src/app/(dashboard)/dashboard/sessions/components/ChatInput.tsx) ignores Enter while native `isComposing` or key code 229 is set. [AIPRDBuilder](../web/src/app/(dashboard)/dashboard/ralph/AIPRDBuilder.tsx) still sends on Enter without those guards, through a [shared ChatInput](../web/src/components/ui/ChatInput.tsx) that delegates key handling. **Static/local mixed disposition; behavioral acceptance not-run.** All message surfaces and the original audit need reconciliation. | Native OS IME evidence is separate from synthetic composition/key events. Cover composition start/end, native `isComposing`/229, newline/send, and streaming-state interactions without claiming mocked tests reproduce native IME. |
| Usage failures appear as `0 / 0` | [Billing](../web/src/app/(dashboard)/dashboard/billing/page.tsx) separates `usageError`; [settings](../web/src/app/(dashboard)/dashboard/settings/page.tsx) preserves nullable usage/quota values through shared helpers. **Static/local repair present.** | Not-run here: distinguish unknown, unavailable, zero, unlimited, and partial failures across both pages; do not substitute zero for missing data. |
| Marketing links broken on secondary pages | [Header](../web/src/components/Header.tsx) uses `/#features`, `/#use-cases`, `/#roadmap` and `/#pricing` for both desktop and mobile links; matching sections exist in [PrimaryFeatures](../web/src/components/PrimaryFeatures.tsx), [UseCases](../web/src/components/UseCases.tsx), [Roadmap](../web/src/components/Roadmap.tsx) and [Pricing](../web/src/components/Pricing.tsx). However, [Footer](../web/src/components/Footer.tsx) still consumes [NavLinks](../web/src/components/NavLinks.tsx), whose section hrefs remain page-relative `#...`. **Static/local mixed disposition; browser acceptance not-run.** | Check secondary-page→home section links, actual section IDs, browser history, focus, and reduced motion; preserve external documentation targets. |

### Additional UI shell findings retained

The active assignment names four additional shell findings. Original audit
wording/artifacts are **blocked**; acceptance remains **pending/not-run**.

| Finding | Source and concrete pending gate |
| --- | --- |
| Shell content/header alignment | [Dashboard layout](../web/src/app/(dashboard)/layout.tsx); compare offsets/container widths at desktop/mobile widths and route transitions. |
| Escape dismissal | [Layout](../web/src/app/(dashboard)/layout.tsx)/[dashboard](../web/src/app/(dashboard)/dashboard/); every drawer/dialog/popover needs keyboard dismissal and focus return without leaking focus when hidden. |
| Unlabeled controls | [Dashboard](../web/src/app/(dashboard)/dashboard/); icon-only inputs/actions need accessible names, semantic controls, focus states and keyboard/screen-reader coverage. |
| Settings navigation/current location | [Settings](../web/src/app/(dashboard)/dashboard/settings/page.tsx)/[layout](../web/src/app/(dashboard)/layout.tsx); reliable active route/section, mobile access and history/deep-link behavior. |

## Open P0/P1 backend/runtime gates

**Static/local observations** apply to this checkout and Rust pin, not the
parent's uncommitted work. Parent owns Python voice ownership, telemetry,
reconnection/UI and worker tenant visibility. Parent reports **mocked local:
44 UI / 199 Python** voice tests from prior runs; child did not run them.
Worker results are pending. No live or platform evidence is claimed here.

| Gate / owner | Finding and concrete pending acceptance |
| --- | --- |
| P0 dispatch — runtime/control-plane | Rust [dispatch_task/KnativeTaskQueue](../codetether-agent/src/server/mod.rs) uses process-local queue and bus publication while responding `dispatched_via_knative: true`; selected model/metadata are not retained. Require durable tenant-owned runs, actual executor acceptance/job identity, model propagation, leases/retry/cancel/terminal transitions and restart recovery. Enqueue is not execution proof. |
| P0 output — runtime/control-plane | Rust [get_agent_task_output/agent_task_output/stream_agent_task_output](../codetether-agent/src/server/mod.rs): GET returns null output; POST ignores worker ID, sets working unconditionally and broadcasts only; SSE skips lag and uses topic prefix matching without replay. Require assigned-worker authorization, persisted ordered output/cursors, exact isolation, terminal-state preservation, reconnect/lag/restart recovery and tenant retrieval. Parent Python SSE/DB changes do not close Rust gaps. |
| P0 approvals — security/runtime | [Request](../codetether-agent/src/server/approval_routes/request.rs) uses default approval store; [decision](../codetether-agent/src/server/approval_routes/decision.rs) trusts JSON actor and permits session grants. [Middleware](../codetether-agent/src/server/mod.rs) permission evaluation has no resource argument. Require authenticated actor/tenant/session/tool-argument binding, expiry/revocation, cross-tenant/tamper/replay denial and execution resuming only the matching approved tool. [Tests](../codetether-agent/src/server/approval_routes/tests.rs) and [session tests](../codetether-agent/src/server/approval_routes/session_decision_tests.rs) are candidates, not observed proof; no exploit asserted without reproduction. |
| P0 worker/voice — parent + runtime | Python [worker auth](../a2a_server/worker_auth.py), [SSE](../a2a_server/worker_sse.py), [monitoring](../a2a_server/monitor_api.py), and parent-reported `a2a_server/voice_api.py` (absent at this base): integrate parent's changes and attach focused commands/results/artifacts, wrong-tenant/stale-worker/session ownership/cleanup/rejoin tests. Rust [worker modules](../codetether-agent/src/server/worker_modules.rs), [voice REST](../codetether-agent/src/server/mod.rs), [voice gRPC](../codetether-agent/src/a2a/voice_grpc.rs) have separate contracts; empty credentials and fabricated session lookup remain open. Real media proof not-run. |
| P1 topology/sessions — control-plane/frontend/runtime | [Server](../a2a_server/server.py), [API origin](../web/src/lib/api-origin.ts), [tenant hook](../web/src/hooks/useTenantApi.ts), [rewrites](../web/next.config.js): explicit supported endpoints and validated environment routing needed. Rust resume ignores codebase ID and falls back to creating a session on load error. Require complete codebase/session contracts, codebase binding, typed load errors and stream/terminal consistency; preserve standalone capability requirements. |
| P1 MCP — runtime/control-plane | HTTP aliases exist, but [MCP](../codetether-agent/src/mcp/)/[registry](../codetether-agent/src/tool/) execution are separate. Require schema/SDK parity, registration/removal/heartbeat, tenant/policy-filtered discovery, remote execution/error/cancel and approval tests. Alias presence closes historical path mismatch only. |
| P1 cognition — runtime/frontend/security | [Handlers](../codetether-agent/src/server/mod.rs), [runtime](../codetether-agent/src/cognition/), [UI](../web/src/app/(dashboard)/dashboard/cognition/page.tsx) exist; handler emits lag without cursor replay. Require idempotent start/stop, proposal→authorized approval→receipt, belief/attention/snapshot consistency, tenant scope, reconnect/lag/error behavior and durable audit replay. Aligned routes are not governance proof. |
| P1 swarm — runtime/frontend | [Runtime](../codetether-agent/src/swarm/) and [lineage handlers](../codetether-agent/src/server/mod.rs) exist; [task](../web/src/app/(dashboard)/dashboard/tasks/page.tsx)/[home](../web/src/app/(dashboard)/dashboard/page.tsx) UI parses `[swarm]` text. Require typed correlated run/subtask/dependency/model/worker telemetry, terminal errors/results, cancellation/dependency propagation, durable replay/lineage and measured speedup. Preserve requested/resolved model IDs and harness failure category; direct-agent/swarm failures are not interchangeable proof. |
| P1 enforcement/metering — security/billing | [Python middleware](../a2a_server/policy_middleware.py), [Rust middleware](../codetether-agent/src/server/mod.rs), [policies](../policies/) and [billing](../a2a_server/billing_api.py): require both runtime resource/tenant/role/worker-token matrices, fail-closed paths, authoritative concurrent quotas/cost accounting and durable receipts. UI numbers/maps do not prove enforcement. |

## Integration audit: all twelve findings retained

Source: [integration gap analysis](../codetether-docs/integrations/gap-analysis.md).
**Static/local** reconciles historical absence assertions with current source;
remaining behavior is **pending/not-run**. Owner integration/control-plane;
dependencies are the dispatch, output, security and lifecycle gates above.

| ID / finding | Current source; outstanding implementation/evidence |
| --- | --- |
| I01 simple REST | [Automation](../a2a_server/automation_api.py) has create/get/list/cancel. Require supported create→dispatch→poll→terminal/output contract, tenant/auth/errors and connector examples; blanket absence is stale. |
| I02 OpenAPI/Swagger | [FastAPI server](../a2a_server/server.py) exposes API schema surfaces. Require published accurate automation schema, generated-client parity, automation-platform import and version/deprecation policy. |
| I03 webhook events/subscriptions | [Automation](../a2a_server/automation_api.py) accepts webhook URL. Require tenant-owned subscription CRUD/filters, correlation/receipts, retries/backoff, dead-letter/redelivery and lifecycle/approval/error event coverage. Callback alone is not the full subscription contract. |
| I04 webhook signature verification | [Security helpers](../a2a_server/webhook_security.py) and [automation](../a2a_server/automation_api.py) contain signing/verification. Require signed exact delivery bytes, rotation, timestamp/replay rejection, outbound URL/SSRF controls and documented partner verification. Helpers are not end-to-end proof. |
| I05 idempotency | [Automation IdempotencyStore](../a2a_server/automation_api.py) is process-local/key-based. Require durable tenant+operation scope, request-fingerprint conflicts, atomic concurrent claim, TTL and restart/multiple-replica tests. |
| I06 rate-limit headers | [Automation](../a2a_server/automation_api.py) emits X-RateLimit headers. Require shared tenant/key limits across replicas, consistent reset/retry semantics and authoritative quota accounting. |
| I07 integration documentation | [Public docs](../codetether-docs/integrations/) and [implementations](../integrations/) exist. Require verified setup/polling/errors/retry/auth/webhook examples and connector/version ownership; not blanket absence. |
| I08 scoped keys/OAuth | [OAuth provider](../a2a_server/oauth_provider.py) exists. Require explicit supported automation grants (client credentials if promised), scoped service/API-key identities, revocation/rotation and tenant/tool enforcement. Existence does not prove every grant. |
| I09 polling | [Automation task GET/list](../a2a_server/automation_api.py) exists. Require authorized stable status/output/error, pagination, lifecycle mapping and restart retry; historical blanket absence is stale. |
| I10 partner/embed | [Audit partner requirement](../codetether-docs/integrations/gap-analysis.md) remains pending: partner-scoped auth/branding/embed/configuration contract and acceptance; not a normal dashboard link. |
| I11 Zapier directory | [Zapier app](../integrations/zapier/app/) exists. Require maintained triggers/actions/auth/schema tests and package/publication/directory identity with real platform proof; source is not publication. |
| I12 async action run | [Automation](../a2a_server/automation_api.py) has async create/poll/callback. Require connector create→stable ID→poll/callback→terminal semantics, timeout/cancellation/idempotency and bounded retries. |

## Roadmap coverage

All 24 Shipped claims, 11 Next items and 10 Future items in
[Roadmap](../web/src/components/Roadmap.tsx) remain in scope.
Mapping below is **static/local**; runtime acceptance is **pending/not-run**.
`done: true` is a product claim, not proof. No item is narrowed to current code.

### Shipped: exact claims and pending gates

| ID / claim | Source; acceptance |
| --- | --- |
| S01 OKR tracking and execution runs | [OKR types](../codetether-agent/src/okr/mod.rs) model objectives, results, runs and progress; [persistence](../codetether-agent/src/okr/persistence.rs) has CRUD and tenant-filtered queries. Pending: authorized durable tenant-owned objectives, rollups and correlated outcomes, including restart/recovery. |
| S02 OKR → PRD → Ralph autonomous pipeline | [OKR/run models](../codetether-agent/src/okr/mod.rs), [PRD model](../codetether-agent/src/ralph/types.rs) and [Ralph loop](../codetether-agent/src/ralph/ralph_loop.rs) exist as component surfaces. Their presence does not prove the complete objective→validated PRD→verified execution/artifacts chain; orchestration and failure recovery remain pending. |
| S03 Structured PRD generation and validation | [PRD types](../codetether-agent/src/ralph/types.rs) deserialize JSON and expose ready-story/stage helpers; deserialization alone is not semantic validation or generated-PRD acceptance. Pending: generation, schema/version/dependency checks and malformed PRD rejection. |
| S04 Ralph iterative implementation loop | [Ralph loop](../codetether-agent/src/ralph/ralph_loop.rs) runs stories and invokes [story verification](../codetether-agent/src/ralph/verification.rs). Pending: bounded retries, actual tool/test receipts, cancellation and real repository output. |
| S05 RLM infinite context processing | [Host RLM adapter](../codetether-agent/src/rlm/mod.rs) re-exports the [workspace crate](../codetether-agent/crates/codetether-rlm/); [configuration](../codetether-agent/crates/codetether-rlm/src/config.rs) explicitly bounds iterations/subcalls. Pending: defined practical limits, recursive context preservation and measured large-context correctness; retain the full advertised capability without treating the label as unlimited proof. |
| S06 RLM answer verification | [Oracle module](../codetether-agent/crates/codetether-rlm/src/oracle/mod.rs) provides grep/AST trace-validation surfaces, not proof of independent verification for arbitrary runtime answers. Pending: independent verifiers, contradiction handling and concrete evidence retention in actual RLM runs. |
| S07 Session recall and context browsing | [Recall source](../codetether-agent/src/tool/session_recall/execute.rs) searches workspace/session evidence; [registration](../codetether-agent/src/tool/mod.rs) includes context-browse and context-budget tools. Pending: authorized scoped browsing/recall, provenance and opt-out. Only implementation source was inspected, not prior-context data. |
| S08 Persistent memory across sessions | [Project memory source](../codetether-agent/src/memory/palace.rs) loads persisted codebase beliefs; [memory module](../codetether-agent/src/memory/mod.rs) exposes it. Pending: tenant isolation, provenance, deletion/retention and explicit opt-in. Only implementation source was inspected, not memory data. |
| S09 Real file output (CSV, PDF, code) | [File tools](../codetether-agent/src/tool/file.rs) implement writes; this does not demonstrate usable CSV/PDF generation. Actual persisted artifact formats, tenant access and ingestion/retrieval gates remain pending. |
| S10 Plan mode, safe edit previews, and undo | [Plan](../codetether-agent/src/tool/plan.rs), [read-only guard](../codetether-agent/src/tool/readonly.rs), [edit](../codetether-agent/src/tool/edit.rs), [undo](../codetether-agent/src/tool/undo.rs) and [registration](../codetether-agent/src/tool/mod.rs) are present. Permission-safe preview/write, exact diff and undo preserving unrelated edits require behavioral acceptance. |
| S11 Browser control with network replay | [Tools](../codetether-agent/src/tool/); lifecycle/auth-bound interaction and safe replay with observed network evidence. |
| S12 Web search, web fetch, and code search | [Tools](../codetether-agent/src/tool/); real responses, bounded errors/cancellation and source-linked results. |
| S13 Voice TTS and transcription | [Voice tool](../codetether-agent/src/tool/voice.rs) exposes `speak`, `transcribe`, voice listing and health via the Qwen TTS API; [voice_stream](../codetether-agent/src/tool/voice_stream.rs) provides browser TTS streaming/play actions; both have [registration](../codetether-agent/src/tool/mod.rs). Real authorized audio/transcription and parent-reported `a2a_server/voice_api.py` (absent at this base) integration gates remain pending; service/media acceptance not-run. |
| S14 Podcast generation & RSS | [Podcast](../codetether-agent/src/tool/podcast.rs); usable media, valid feed/storage/ownership and retry handling. |
| S15 YouTube upload | [Upload](../web/src/lib/youtube/upload.ts); authorized actual upload with artifact path and platform video ID, not a fixture. |
| S16 AI avatar video generation | [Avatar tool](../codetether-agent/src/tool/avatar.rs), [media registration](../codetether-agent/src/tool/register_media.rs) and [pipeline instructions](../AGENTS.md#codetether-avatar-pipeline) expose generation/service surfaces; audio→motion-safe lip sync→reenact/composite→usable video requires acceptance. Live media/upload proof not-run. |
| S17 Image input for vision-capable models | [Tools](../codetether-agent/src/tool/)/[providers](../codetether-agent/src/provider/); real image handoff, provider compatibility/errors and provenance. |
| S18 MCP bridge (Model Context Protocol) | [MCP](../codetether-agent/src/mcp/); registered remote execution, approval/policy/auth and lifecycle gates, not aliases alone. |
| S19 Kubernetes pod management | [Tools](../codetether-agent/src/tool/)/[server](../a2a_server/server.py); bounded namespace-scoped lifecycle, ownership and cleanup; concrete pod/job identity if live proof requested. |
| S20 Sub-agent relay autochat | [Runtime](../codetether-agent/src/lib.rs)/[swarm](../codetether-agent/src/swarm/); message ownership/order, cancellation and actual child execution/receipts. |
| S21 Swarm parallel execution | [Swarm](../codetether-agent/src/swarm/); structured lineage, partial failure/recovery and runtime gate above. |
| S22 Multi-model orchestration | [Providers](../codetether-agent/src/provider/)/[swarm](../codetether-agent/src/swarm/); requested/resolved model identity, routing/costs and typed failure diagnostics. |
| S23 OPA Rego RBAC and tenant isolation | [Policies](../policies/)/[Python](../a2a_server/policy_middleware.py)/[Rust](../codetether-agent/src/server/mod.rs); both resource/worker/approval/stream isolation matrices. |
| S24 Self-hosted (Docker / K8s / bare metal) | [Docker](../Dockerfile)/[Helm](../chart/)/[development](../DEVELOPMENT.md); reproducible setup/configuration and each supported topology smoke test. |

### Next: priority, owner/dependency and concrete pending acceptance

| ID / exact item | Priority / owner; acceptance |
| --- | --- |
| N01 Unified control plane API for OKRs, PRDs, runs, tools, and sessions | P0/P1 control-plane/runtime; supported tenant-scoped contracts and durable lifecycle; [server](../a2a_server/server.py), [Rust](../codetether-agent/src/server/mod.rs). |
| N02 Run lifecycle events and streaming progress | P0/P1 runtime; dispatch/output gates, typed events/cursors/terminal consistency; parent telemetry requires integration. |
| N03 Dashboard for OKR/run monitoring and replayable audit trails | P1 frontend/runtime; durable queries/replay/receipts, correlation/authorization; [dashboard](../web/src/app/(dashboard)/dashboard/). |
| N04 Team workspaces with role-scoped agent permissions | P1 security/control-plane; tenant/team/worker/tool role matrix across APIs/streams/artifacts; [policies](../policies/). |
| N05 Scheduled and webhook-triggered autonomous runs | P1 control-plane; durable scheduling/auth triggers/retry-safe dispatch/cancellation; [automation](../a2a_server/automation_api.py). |
| N06 Worker pools for local, cloud, and Kubernetes executors | P1 runtime/control-plane; capability matching, leases, stale/disconnect/restart recovery/namespace ownership; [workers](../a2a_server/worker_sse.py). |
| N07 Tool catalog, policy gates, and per-tenant capability controls | P0/P1 security/runtime; MCP/approval gates and tenant-visible authorized execution; [MCP](../codetether-agent/src/mcp/). |
| N08 Pre-built workflow templates for engineering, ops, and media | P1 product/runtime; versioned executable schemas, bounded costs, meaningful results/errors and reproducible examples; [examples](../examples/). |
| N09 Bulk task API and batched background execution | P1 control-plane/runtime; bounded concurrency, durable item status, partial retry/cancel/idempotency; [automation](../a2a_server/automation_api.py). |
| N10 Zapier, n8n, Make, and GitHub app integrations | P1 integration; connector auth/create/poll/webhook/terminal flows and publication; [integrations](../integrations/), [GitHub app](../a2a_server/github_app/). |
| N11 Usage metering, quotas, and cost controls | P1 billing/security; authoritative usage, concurrent limits, scoped reports/unavailable UI; [billing](../a2a_server/billing_api.py). |

### Future: retained without hiding unfinished Next work

| ID / exact item | Owner/dependency; pending acceptance |
| --- | --- |
| F01 Policy-aware autonomous delegation across teams and tenants | Security/runtime, N01/N04/N07; explicit grants, least privilege, actor/tenant provenance/revocation; [policy](../policies/), [swarm](../codetether-agent/src/swarm/). |
| F02 Learning workflow library from successful runs | Runtime/product, N03/N08; evidence-backed reusable templates, provenance, reversible feedback/access control; [Ralph](../codetether-agent/src/ralph/). |
| F03 Organization-level OKR decomposition into agent run plans | Planning/control-plane, S01/S02/N01; confidence/branching plans, dependencies/feedback tied to verified outcomes; [OKR](../codetether-agent/src/okr/). |
| F04 Cross-repository dependency reasoning and migration planning | Planning/runtime, N01/N03; scoped dependency graph, blocked-run propagation, safe migration receipts; [Ralph](../codetether-agent/src/ralph/). |
| F05 RLM deeper recursion and domain-trained retrieval models | Retrieval/evaluation; limits, benchmarked retrieval/provenance/error handling; [RLM](../codetether-agent/src/rlm/). |
| F06 Custom fine-tuned coding and operations models | Provider/evaluation; licensed train/eval pipeline, quality/cost/drift gates, rollback/routing; [providers](../codetether-agent/src/provider/). |
| F07 Real-time collaborative voice agent | Voice/runtime/frontend, parent voice/N01; multi-participant authorization, interruption/rejoin/cleanup and actual media proof; parent-reported `a2a_server/voice_api.py` (absent at this base), [Rust voice](../codetether-agent/src/a2a/voice_grpc.rs). |
| F08 Video understanding, generation, and review loops | Media/runtime; ingest/generate/review, provenance, quality gates/durable outputs; [tools](../codetether-agent/src/tool/). |
| F09 Marketplace for signed agent skills and MCP tool packs | Security/product, N07; signed packs/trust/revocation/compatibility/scoped install/rollback; [MCP](../codetether-agent/src/mcp/). |
| F10 White-label and private-cloud deployments for agencies and enterprises | Deployment/product/security, N04/N11; branding, isolated upgrades/backups/retention/observability; [Helm](../chart/). |

### Homepage claims

[PrimaryFeatures](../web/src/components/PrimaryFeatures.tsx),
[Hero](../web/src/components/Hero.tsx) and
[Pricing](../web/src/components/Pricing.tsx) remain in scope.
Demos/static JSX do not constitute runtime integration.

| Claim group | Pending mapping/evidence |
| --- | --- |
| Objective → PRD → Code | S01–S04/N01/N03: real artifacts/receipts, not a canned demo. |
| Swarm & Relay | S20–S22/dispatch/output/structured telemetry: speedup claims need comparable measured runs. |
| Multi-Modal Tools | S09/S11–S19/F07–F08: actual media/provider/upload evidence per capability. |
| Production Infrastructure | S23–S24/N04/N06/N11/F10: isolation, deployment and authoritative usage. Hero/pricing integration/support/benefit promises need the same acceptance; changing copy is not closure. |

Pricing renders [shared pricing content](../web/src/content/pricing.ts),
not backend entitlement data. The current marketed limits and benefits below
remain full acceptance requirements; their presence in content is **static/local**
evidence of claims only. **Owner: billing/platform/security**, with dashboard
integration; enforcement, purchase/credit accounting and service delivery are
**pending/not-run** here.

| Current pricing claim | Required acceptance / retained dependency |
| --- | --- |
| Free: 100 tasks/month, 1 agent, 3 workspaces, $5 prepaid credit | N04/N05/N10: authoritative task/concurrency/workspace limits, credit issuance and tenant-scoped token accounting, including concurrent requests and retries. |
| Pro: 5,000 tasks/month, 5 concurrent agents, 20 workspaces, $50/month credit | N05/N06/N10: paid entitlement activation, renewal and downgrades; durable quota/budget enforcement; real per-model costs and monthly spending limits. |
| Enterprise: unlimited tasks/agents/workspaces, $150/month credit, tenant token isolation, custom limits/alerts | N04/N05/N10/F10: explicit unlimited-plan semantics without accidental sentinel-limit denial, tenant isolation, authoritative renewal credits, alerts and private deployment behavior. |
| Free HMAC-SHA256 authentication/full audit trail; Pro OPA RBAC, plugin integrity, RLM unlimited context, swarm and MCP | Approval/security gates and S05–S09/S20–S24: authenticated operations with durable receipts, tamper denial and actual authorized execution; context and throughput promises need measured evidence, not content labels. |
| Enterprise team RBAC, relay, voice/media, self-deployment, custom OPA policies and dedicated support; at-cost per-token/model/cache/reasoning billing and prepaid top-ups | N04/N06/N10/F07/F08/F10 plus relay/voice/media gates: end-to-end delivery, policy enforcement, receipt-to-bill reconciliation, purchased-credit accounting and explicit support ownership. The displayed model-price table is not proof of current provider costs or available models. |

## Frontend maintainability: all phases retained

Source: [refactor plan](../web/marketing-site-refactor-plan.md).
Owner frontend; historical observations require remeasurement after integration.
**Static/local plan; behavior/performance acceptance not-run.**

| Finding / phase | Concrete pending acceptance/dependencies |
| --- | --- |
| Phase 0 correctness | [Root layout](../web/src/app/layout.tsx) is the single ChatWidget render owner in the inspected app/components sources; historical duplication is stale. Header anchors are rooted, but footer NavLinks remain page-relative (UI row above). Scrolling, generated/backup separation and behavior/performance acceptance remain pending. Preserve features and audit evidence. |
| Phase 1 primitives | Shared button/card/badge/section/tabs/empty/loading/shell primitives and typography/spacing/color/motion tokens with accessibility parity. |
| Phase 2 marketing | Centralized marketing/pricing configuration, decomposed sections, server-rendered static content/small interactive islands; compare JS/hydration and navigation regressions. |
| Phase 3 dashboard | Domain modules/hooks for dashboard/cognition/tasks/billing/settings/ads; consistent shell/navigation/errors without losing runtime ownership/stream semantics. |
| Phase 4 polish | Keyboard/focus/IME/Escape tests, responsive/metadata/loading/error consistency, lint/type/regressions and measured before/after bundle/performance artifacts. Historical client/line counts are not fresh measurements. |

## Repository maintainability: concrete dispositions and pending gates

Source: [repository audit](REPOSITORY_AUDIT.md). Owner maintainability/build/docs;
**static/local inventory**, packaging/build/deployment acceptance **not-run**.
Preserve compatibility until active references are checked. No binary/vendor
removal, migration rewrite, directory rename or secret exposure in this change.

| Finding | Current reconciliation / concrete edit or remaining gate |
| --- | --- |
| Split docs sources | Keep two existing published surfaces: A2A protocol docs/review notes in `docs/` via [root MkDocs](../mkdocs.yml), CodeTether product docs in `codetether-docs/` via [product config](../config/codetether-mkdocs.yml). [docs index](README.md) records boundaries/commands and this inventory; generated `site/` and `codetether-site/` are not authored sources. Publishing/navigation consolidation remains a separate tested decision. |
| Flat app boundaries/optional renames | Keep `web/`, `chart/`, `ui/`, `types/`, voice/services/agents, lowercase makefile and root Dockerfile compatible. Optional `apps/dashboard`, `deployment/helm`, SDK/client/script subdivisions require owner decision and reference/build/CI changes, not automatic moves. |
| Legacy worker/vendor | [Legacy status](../legacy/agent_worker/README.md) already says deprecated/compatibility and Rust primary. Root installer references still exist. Check active users and `_vendor/opencode*` before migration/removal; no duplicate classification/removal needed merely to satisfy historical wording. |
| Generated/binary outputs | Inventory generated clients/site, chart/release bundles/audio/assets, screenshots/test-results and caches. Prefer release/object storage/LFS where appropriate. Ignore rules alone do not untrack artifacts; preserve audit evidence or name durable equivalents before any relocation. |
| Archive indexes | [Root archive](archive/root/README.md), [deployment archive](../deployment/archive/README.md), [artifacts](../artifacts/README.md) already tracked: historical index-absence recommendation is satisfied at source level. Ownership/retention/active-use and redacted security review still pending; indexes are not archive safety proof. |
| Credential-shaped files | Inventory paths safely with approved redacted checks, owner-driven rotation for confirmed exposure; never print secrets. Pending review is not proof of exposure. |
| Integrations/SDK/client topology | Keep Zapier/n8n/VS Code/Swift/pocket/types consumers intact. Optional consolidation needs package/import/build checks; integrations are required capabilities, not disposable code. |
| Experiments/benchmarks/coordinators | Explicit experimental-versus-supported-service labels and consumer/owner review before moving quantumhead, benchmarks or agent coordinators. |
| Migration/packaging/entrypoint ambiguity | Reconcile root migration and `a2a_server/migrations/` ownership without rewriting applied identities. Preserve run_server.py, Docker/Helm, CLI/package metadata until install/migration/build checks establish safe simplification. |
| Submodules/protocols/tooling | Document initialization/pins and authoritative protobuf/OpenAPI regeneration; shared editor/MkDocs configuration intentional. Generated clients are not hand-edited. |

## Handoff and evidence gate

- Integrate parent worker/voice/telemetry/reconnection/UI and parallel
  auth/checkout changes before claiming acceptance. This child edits docs only.
- Parent-current audit and retained UI/worker/voice evidence were inspected
  read-only as recorded above. Preserve the distinct passing and failed attempts;
  the parent-reviewed 11-suite/194-test run is retained in
  `artifacts/ui-audit/parent-handoff/ui-tests.log` and `ui-results.json`.
  No retained count establishes standalone Rust or real-media parity.
- The original UI audit is available in the parent; recovery is no longer a
  prerequisite. Remaining UI acceptance and broader runtime contracts stay open.
- Prioritize durable dispatch/output/approvals and remaining standalone runtime
  gates, then MCP/cognition/swarm/control-plane/metering acceptance.
- Each finding needs change→focused command→exit/result→artifact traceability.
  Source/tests existing is not execution proof; mocked results cannot stand in
  for live Argo or platform IDs. Live proof is required only when requested,
  not as a precondition for ordinary review.
- Full capability, roadmap and audit implementation remains pending. This
  inventory retains every deliverable; documenting a gap does not close it.