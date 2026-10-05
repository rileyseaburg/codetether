# Finite harvester Job cutover

## Confirmed incident

Native task #506 / issue #5960 failed in clone preparation, before implementation.
CodeTether task `5fb84b85-16f9-4c8b-8357-3c3aedad8115` reported Git `No space left
on device`. Its node-local workspace disk was 295 GiB, 278 GiB used, 1.7 GiB
available. The local-path PVC's 50 Gi request was not an isolated capacity quota.

## Implemented model

- Each opted-in Forgejo task is a `batch/v1 Job`, one worker slot, no automatic
  Job retry, bounded deadline, process exit on task termination.
- Fresh bounded `emptyDir` workspace and home/cache; no shared workspace PVC.
- Coding stages reconstruct from Git in an init container. No old workspace is
  reset or removed. Claimed user work and author-session state are not silently copied.
- Success cleanup requires stored termination evidence. Coding cleanup also
  requires clean/no-stash/no-unpushed audit and a matching remote branch head.
- Failed/uncertain work is retained in terminated pods, with an admission cap.
  This is not durable disaster-recovery storage: node loss may remove emptyDir.
- Qualified nodes are k8s-worker-2 and k8s-worker-3; one Job per node prevents
  multiple task storage budgets from consuming the same free space concurrently.
- Legacy harvester StatefulSet scaled to zero after drain; review daemon removed.
  Existing local-path PVCs remain Bound and were not deleted.

## Live evidence

- Readiness task `7db2c1c2-11d1-4353-b5e3-6aa1c3d1722b` ran as
  `ct-task-f20e3247311c3969e963274b36f0f187`, completed, exited and was TTL-deleted.
- Task #506 retry preparation `3c36243a-06a2-414f-852f-c448f3b7ac3c` completed as
  Job `ct-task-0adaff175669eb78bfdb492ee062c44f`; exit 0, cleanup recorded, Job deleted.
- First coding Job was retained after init reported `workspace_storage_insufficient`
  on kube-worker-08 (26.3 GiB available). No application implementation ran there.
- Placement corrected using measured free space: 46.9 GiB on k8s-worker-2 and
  54.3 GiB on k8s-worker-3. Another canonical retry of the same native task was issued.
- Latest preparation `0b2ece2d-d7d4-4a7b-80ce-8e75f432fa58` was running in
  `ct-task-c7068a3d590c9cf141ceaf34e6538c8f` on k8s-worker-3 at observation time.
- Final observation: that preparation completed. Coding task
  `808c388e-7840-43bc-a745-66204a9e8490` is running in fresh Job
  `ct-task-d6b426a0b1de17c04da653da2129ea7b`; Git bootstrap succeeded.
- Final controller image is `task-jobs-27b021420425`, revision
  `27b021420425c474150900604a5284a1683e876f`. Argo app health is Healthy;
  its zero-replica legacy StatefulSet still reports manifest drift/OutOfSync.
- Follow-up: that preparation completed. Coding task
  `808c388e-7840-43bc-a745-66204a9e8490` is now running in separate Job
  `ct-task-d6b426a0b1de17c04da653da2129ea7b`; its fresh-clone init succeeded at
  head `0f381b62bb34ff2ce13228bb00574b22356920d5`.
- Final API/controller code revision `27b021420425c474150900604a5284a1683e876f`,
  image `task-jobs-27b021420425`, API pod
  `a2a-server-deployment-green-84d5fc5568-c58d6` in `a2a-system`.
- Legacy StatefulSet observed at zero replicas; no harvester daemon pods remain.
- Worker credential revocation verified on protected `/v1/worker/connected`:
  old credential HTTP 401; replacement HTTP 200.
- The production offer-creation request was not replayed. No application fix,
  commit, or approval is claimed from the infrastructure cutover alone.

## Credential containment

CLI help unexpectedly exposed an environment-backed worker credential. It was
rotated after legacy workers drained. Protected `/v1/worker/connected` returned
401 for the old credential and 200 for the replacement. Job CLI help is wrapped
to suppress credential-bearing environment values. No credential values are
stored in this evidence file; see `worker-token-rotation.json`.

## Local evidence

`final-tests.xml`: 51 focused tests and 19 subtests passed (mocked lifecycle/HTTP
and real PostgreSQL safety tests). Subsequent placement/race checks are recorded
separately. Helm Job JSON rendered with restartPolicy Never and no workspace PVC.

## Incident 2: "sessions start but PRs do not happen" (2026-09-11)

Observed facts (live, `a2a-system`, controller image `task-jobs-27b021420425`):

- 105 Job tasks completed 2026-09-10 13:38 → 2026-09-11 03:25, then nothing.
- Review owner cancelled 50 `review_chunk` tasks at its 3 h deadline
  (02:00–04:22). Each cancelled chunk left a **Failed** Job (worker exit 1).
- From 04:09 every new task (`prepare` for native #521–#526, later
  `review_chunk`) deferred with `job_wait_reason=job_retention_capacity_exhausted`
  because 20 retained Jobs hit `HARVESTER_JOB_MAX_RETAINED=20`.
- 9 **Complete** coding Jobs were never TTL-reclaimed: their audit reported
  `audit_git_layout_unsupported`. spotlessbinco has a committed `.gitmodules`
  (Forgejo contents API → 200), which the audit treated as unsupported.
- Nothing was wrong with the worker sessions themselves; the previous coding
  runs for #5960/#5962/#5964 pushed branches whose heads match the remote.

Confirmed root causes and fixes (commit `62af5c2315f9`, image
`task-jobs-62af5c2315f9`, Argo `codetether-a2a-server` patched, green pod
`a2a-server-deployment-green-5ff57b548-sr2pd`):

1. `observe_terminal` only reclaimed **completed** read-only Jobs. Read-only
   review chunks hold no user work, so any terminal state now releases the slot
   after evidence is stored. Cancelled coding Jobs are still retained.
2. `audit_workspace` no longer treats `path/.gitmodules` as unsupported; an
   initialised `.git/modules` store still is.
3. `HARVESTER_JOB_MAX_ACTIVE` 4→2 (equals qualified node count; anti-affinity
   made extra admissions unschedulable) and `HARVESTER_JOB_MAX_RETAINED` 20→40.

Backlog release: `release_empty_jobs.py` deleted 9 Failed Jobs whose task was
a cancelled read-only chunk or whose only terminated container was the
`workspace-prepare` init container (`release-log.jsonl`, `retained-before.jsonl`).
No Complete coding Job was deleted; the controller will reclaim those through
the corrected audit on their next run, or they stay retained.

Post-deploy observation: retained Jobs 20→11, zero
`job_retention_capacity_exhausted` deferrals in controller logs, prepare Jobs
for #5966 (`ct-task-517ff9f9…`, k8s-worker-3) and #5967 (`ct-task-49f03e97…`,
k8s-worker-2) running and Ready. PR creation for those tasks is pending, not
yet proven. Tests: `retention-fix-tests.xml` — 25 passed, 22 subtests (mocked local).