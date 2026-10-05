# Review feedback recovery and PR 5921 diagnosis

## Live deployment
- Code revision: `c9a83c9124357c8f88b8eb1ac01523d79256cafa`.
- Image: `registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:review-recovery-c9a83c912435`.
- Image digest: `sha256:94e3f027b6375c975e65f6fbd86c382c27d6052fe00bb4cc75e3786561bf6b71`.
- Namespace: `a2a-system`; API pod `a2a-server-deployment-green-7ff754c4fc-7v48x`.
- API and Temporal worker rollout commands reported success.
- Recovery is explicitly enabled for `riley/spotlessbinco`; existing single-owner
  review, merge checks, native-request cancellation, and #5873 hold remain.

## Behavior
- Valid BLOCKED feedback and CHANGES_REQUESTED attach to one idempotent coding
  recovery task on the existing authorized issue workspace and branch.
- The coding harvester may repair code/tests and produce authorized validation.
- Re-review requires a verified non-empty descendant commit or newly successful
  exact-head CI evidence. Worker self-reports and empty commits do not count.
- Three recovery attempts across the PR are permitted; genuine operator blockers,
  cancellation, stale branches, and missing authorization stop safely.
- Harness failures, invalid review acknowledgements and empty PR diffs are not
  instructions to edit application code.

## Actual handoff
- PR #5909 owner `d054b211-3278-5c67-be91-a6fe77012279`.
- Recovery task `7d986fda-4b77-4bdd-a0e1-f1b3080643c7`.
- Input head `dd66f93c4fd53eeefbc153e5d45e627ec021fb55`.
- Claimed by coding harvester 0 on `/var/lib/codetether/repos/19f101630ced7f58`.
- Run `run_73b02ad875cb491ba077039a36889345`; claim/workspace readiness observed.
- No resulting commit or APPROVED verdict was claimed at handoff observation.

## PR #5921 and credentials
- Head `79606f43c2114907d2d184d1fa4858bb102a8952`: zero changed files, zero diff bytes.
- The previous diagnostic conflated empty and oversized diffs.
- Owner `a5f3814e-deac-5377-aa88-6a1bb866c5de` was retried and now publishes
  `review_diff_empty`. No renderer edit or empty commit is warranted.
- Scoped Forgejo token 35 revoked; replacement 36 retains read:issue,
  read:repository and the same repository restriction. See `token-rotation.json`.
- Opaque `forgejo-cli get` from harvester 0 authenticated successfully after rotation.
- The standalone local CLI prints raw transport errors. A redaction patch is
  prepared and `git apply --check` succeeded, but installation is blocked by
  the external-workspace write/approval boundary. No CLI hardening deployment claimed.

## Local checks
- 84 focused tests passed, including mocked feedback/Temporal loops and real
  PostgreSQL single-writer checks. Evidence: `release-tests.xml`.
- Scoped Ruff checks passed; runtime container imports succeeded.