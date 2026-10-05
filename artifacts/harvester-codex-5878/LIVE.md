# Issue 5878 / native task 457: CodeTether runtime recovery

## Confirmed original failure

- Task `c9daad6f-48d2-4c60-bf9d-6a9ffa8f2cd1`, harvester-0, worker 4.7.5-dev.47.
- Requested reference: `openai-codex/gpt-6-astra-fast:high`.
- Backend identified wire model `gpt-6-astra` and returned HTTP 400 requiring
  a newer Codex client. First request recorded zero input/output tokens.
- The task description and workspace were present. This was not model
  unavailability or a missing-prompt failure.

## Live deployment/Argo: compatible client

- Prebuilt worker client 4.7.5-dev.49, source identifier `f65279c7`, includes
  the Codex `version: 0.153.3` request header absent from the deployed client.
- `Dockerfile` preserves the tool-equipped runtime at digest
  `sha256:53d24a55940738441f6ba070d2021863e7caa4d8c11a942440143b231edd2622`.
- Published worker image:
  `registry.quantum-forge.net/cluster-ci-cache/codetether-worker:4.7.5-dev.49-astra-client-f65279c7-devtools2`.
- Published digest:
  `sha256:c7997d52c0dfc994a25f7019df9e067fadbde3531fac33416480fdb64ae80dc2`.
- Isolated job `a2a-system/codetether-astra-client-5878`, pod
  `codetether-astra-client-5878-sgshf`, completed successfully. The exact
  requested model returned `CODEX_COMPAT_OK`. No repository volume was mounted.
- Both `a2a-server-harvester-0` and `a2a-server-harvester-1` were verified at
  version 4.7.5-dev.49 with the exact model and Forgejo CLI, RustyRoad, Python.
- No Rust compilation was run; the existing binary was reused.

## Baseline timing and task outcome

- Attempt 2 preparation completed at 17:54:28 UTC on `d6f7cd1`.
- PR https://forgejo.quantum-forge.io/riley/spotlessbinco/pulls/5879 merged the
  partial work at 17:54:37 UTC, producing main `68aa0c4`.
- Static/local source inspection: current main already contains the seven
  requested snake_case update mappings; no schema edits were made by this repair.
- A baseline retry confirmed the mappings and reported additional acceptance
  gaps, missing local dependencies/CLI, and a Vault authorization failure.
- Redundant work was cancelled through the native control. Final verified
  native task state: cancelled; active CodeTether tasks for #5878: zero.
- Issue diagnosis:
  https://forgejo.quantum-forge.io/riley/spotlessbinco/issues/5878#issuecomment-16064

## Terminal-status race repair

- Late stage updates previously forced native status back to running.
- Stage transcript/link updates no longer own native lifecycle status.
- Mocked local: 24 focused tests succeeded (`terminal-status.xml`).
- API/Temporal image: `terminal-970864939256`, digest
  `sha256:c29c5ccb87589bd49d7f1e6bf05b87e352e1eb6bc764088b7a822e0b8f3ce78c`.
- Live replay of the completed stage update preserved task 457 as cancelled.
- Changes are on https://forgejo.quantum-forge.io/riley/codetether/pulls/46.

## Remaining blockers / not-run

- Live Vault capability check: role `codetether-harvester` has `deny` on
  `kv/data/forgejo/spotlessbinco-agent`. No policy expansion or credential swap.
- Fastify startup, application typecheck, Spotless CLI/live-route verification,
  and cache publication were not run by this repair. Issue #5878 remains open.
- PR #5873 remains paused; unsolicited status remediation remains disabled.