# Completion recovery — 2026-09-14

## Observed blocker (live deployment/Argo)

In `a2a-system`, all workers were idle while 40 retained Job objects consumed
the coding admission cap. The queue included four coding tasks, 25 preparation
tasks, four remediation tasks, and 23 review chunks. Many older cancellations
were review chunks that had never received capacity.

The single-branch-clone Git regression reproduced a second retention defect:
a pushed topic branch need not create an `origin/topic` tracking ref. Comparing
local branches only against cached remote refs falsely reports unpushed work.
The controller also erased saved audit evidence after Pod GC and retained the
now-empty Job objects indefinitely. Stale PR-head bindings waited forever.

## Changes

- Each cleanup/review/coding lane gets a bounded rotating scan window.
- Read-only admission is independent of retained coding work.
- Finished Jobs with no Pods can be reclaimed without deleting a workspace;
  the last available audit is retained.
- Supervisor audits record every local branch head; live remote refs and
  ancestry decide whether each is published. Unknown/dirty work stays retained.
- Permanently stale/closed PR bindings fail explicitly, while transient
  admission failures remain retryable.

## Verification

- **Focused CI-like:** 71 tests and 32 subtests in
  `completion-release-tests.xml`, including real PostgreSQL scan fairness and
  a filesystem Git sparse-refspec regression alongside mocked lifecycle tests.
- **Focused CI-like:** 49 tests and 32 subtests after stale-binding handling,
  recorded in `completion-final-tests.xml`.
- **Static/local:** root `.ruff.toml` diagnostics resolved on the changed
  controller, supervisor, tests, and listed operational helpers.
- **Live deployment/Argo:** app `codetether-a2a-server`, namespace `a2a-system`,
  code revision `91c113bfa855bd3b15368df7fe21b506cffa5242`. Exact image digest and
  rollout evidence: `completion-binding-fix-deploy.json`.
- **Live deployment/Argo:** review #6046 returned success on head
  `e989f36958b52f22184f319a807b62945ffb0865` in
  `completion-watch-20260914T122619.json`; that branch subsequently advanced.
  The approval is not claimed for the later head. Coding jobs remained active.

## End-to-end publication observed (live deployment/Argo)

`completion-watch-20260914T124842.json` records real server publication:

- Issue #6032, task `e6a8b1fe-3777-4b13-adfb-886f3ad2d966`, completed at
  12:44:15 UTC, published PR
  https://forgejo.quantum-forge.io/riley/spotlessbinco/pulls/6072
- Issue #6030, task `420aa345-9af2-4fdb-8027-f95a79a3d0c3`, completed at
  12:46:38 UTC, published PR
  https://forgejo.quantum-forge.io/riley/spotlessbinco/pulls/6073

These are PR publications, not application deployment or merge claims. Review
and CI remain separate gates. The original issue #5853 has PR #6003.

## API memory recovery (live deployment/Argo)

During resumed worker activity the API pod
`a2a-server-deployment-green-54c78cf959-btt7w` was OOMKilled (exit 137) under a
2 GiB limit and 16 MiB request. The Job metadata scan was only ~100 KiB, so
metadata size was not established as the cause of the memory spike. Reserved
API memory was raised to 1 GiB with a 4 GiB ceiling through Argo. The replacement
`a2a-server-deployment-green-565547cdcf-kh7vt` was Ready with zero restarts after
6m22s, using 1543 MiB. This is bounded recovery evidence, not a leak-free claim.

Root Ruff diagnostics on changed code, supervisor copies, tests, and operational
helpers were rechecked. No retained workspace was forcibly deleted to free slots.