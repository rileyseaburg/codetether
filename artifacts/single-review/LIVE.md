# Single-owner Forgejo review cutover

## Outcome (live deployment/Argo)

- Repository: `riley/spotlessbinco`.
- Retired the duplicate `codetether-pr-review.yml` Actions workflow through
  Forgejo's native disable-workflow operation; confirmed its enable control.
- Hook 2 is active only for PR lifecycle, synchronization and review-request
  events. API input uses `pull_request_only` to avoid the `pull_request`
  compatibility alias expanding into comment/issue intake.
- Native issue workflows attach to the same `(repo, PR, head)` review owner.
- Required review context: `CodeTether / Harvester Review`.
- Restored auto-merge with the five existing build/scan checks plus this review
  context and an APPROVED, published owner ledger for the exact PR/head.
- Retired CI results remain historical; they cannot override the new owner.
- The #5873 automation hold and unsolicited-remediation disable were preserved.
- Closed superseded capacity-only PR #5912; its branch/history were preserved.

## Runtime and storage evidence

- Argo app: `argocd/codetether-a2a-server`, source revision
  `d8227827b179687118271d6d46d120da3dc80f4e`.
- API/Temporal image: `single-review-d8227827b179`.
- API pod after gate restoration: `a2a-server-deployment-green-d7c69b447-nvpqn`.
- Dedicated deployment: `a2a-system/a2a-server-review-harvester`, safe tools,
  targeted-only, two task slots, non-root UID 1000, writable isolated scratch,
  no repository PVC. Codex backend opt-in matches existing harvesters.
- Readiness task `2e8177a4-24d5-4fa3-b05c-05e8c449419e` completed on
  `wrk_1788931322_825451fb5a26d852` with `SINGLE_REVIEW_WORKER_READY`.
- Migration `037_forgejo_review_snapshots` applied in the CodeTether production
  database; table presence and compatible task columns observed.
- Argo health was Healthy and rollout operations succeeded. App sync still
  reports OutOfSync for the existing coding-harvester StatefulSet. Compared
  desired/live spec values match; remaining differences are live-only defaults
  and a restart annotation. That unrelated resource was not rewritten.

## Real PR result

- PR #5909 head: `b93bc48cb0b60c4acf7a5ab63e206b9ac9837dc6`.
- Owner: `ce621100-7d32-5bd8-9739-8047e802f049` (exactly one database record).
- Workflow: `forgejo-review-3993d3fea3f4244d12b79edcdaa081bb1d3af3a0`.
- Chunk task: `8e48b723-450c-4e72-ab18-91b88a23270b`, completed on the safe worker.
- Repeated enrollment returned the same owner/workflow.
- Published result: BLOCKED / failure, because exact-head CI/typecheck/behavioral
  evidence was not supplied. No competing approval or forced green status.
- Live merge evaluation returned `checks-not-all-successful`; #5873 returned
  `disabled-or-paused`. #5907 and #5918 were already closed and were not reopened.

## Focused validation

- 87 checks passed in `release-tests.xml`: mocked Forgejo/Temporal execution and
  real PostgreSQL snapshot immutability/concurrent ownership checks.
- Scoped Ruff checks passed; Helm safe-worker rendering checks passed.
- No live APPROVED review or automatic merge is claimed for #5909; its missing
  validation remains a real blocker, not an infrastructure success override.