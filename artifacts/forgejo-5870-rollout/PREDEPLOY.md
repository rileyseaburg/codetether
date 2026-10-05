# CodeTether rollout evidence for issue 5870

## Live deployment/Argo: before promotion

- API pod: `a2a-system/a2a-server-deployment-green-c49c45b56-gnxn9`.
- Image: `registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:main-4e0fe718d799`.
- Delivery: `riley/spotlessbinco#5870:issues:body`, claimed at
  `2026-09-07 09:50:46.283208+00:00`.
- Read-only task query returned no rows; `forgejo_webhook_inbox` did not exist.
- Same API pod logged Vault HTTP 403 / invalid-token Git credential failures
  at `2026-09-07 13:04:33Z`.
- Argo application `argocd/codetether-a2a-server`: Healthy, OutOfSync,
  source revision `4e0fe718d79953fd39a6105a32e0ace92a9e73ca`.

## CI gate

- PR: https://forgejo.quantum-forge.io/riley/codetether/pulls/45
- Initial PR run: https://forgejo.quantum-forge.io/riley/codetether/actions/runs/123
  (`run_id=10028`, `job_id=19777`): failed with three stale test contracts.
- The corrections target imported completion callables, the existing isolated
  issue-workspace keyword argument, and capability-only worker discovery.
- Mocked-local rerun of the full PR compatibility command: 270 passed,
  20 PostgreSQL-dependent tests skipped, exit 0. Artifact: `pr-compatibility.xml`.
- Real PostgreSQL intake evidence from the earlier implementation is retained
  separately in `artifacts/forgejo-5863-retry/integrated-regressions.xml`.

No mux use is permitted. See `SCOPE.md` for the current user restriction.