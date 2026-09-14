# Finite Forgejo task Jobs

Enable `taskJobs.enabled` and `HARVESTER_JOB_REPOS` for opted-in repositories.
`create_and_dispatch_task` assigns a deterministic Job/worker name before queue
publication. Only a worker with the `task-job` capability and exact target name
can claim that task. The API controller retries admission, never task execution.

Each task is a Kubernetes `batch/v1 Job` with one container worker slot,
`restartPolicy: Never`, `backoffLimit: 0`, and an active deadline. The supervisor
polls only its task, stops its own process group on terminal state, and exits.
Job failure without a worker outcome is projected as a failed task, never success.

Cleanup, review, and coding each have a bounded, rotating reconciliation window.
Old retained work cannot monopolize the scan. A stale PR head or closed PR is a
terminal admission error, not an endlessly queued task. Transient capacity and
HTTP failures still defer without replaying a worker.

## Storage and handoff

There is no shared workspace PVC in a new Job. Workspace and home/build caches
use bounded `emptyDir` volumes with ephemeral-storage requests/limits. Known
full nodes can be excluded with `HARVESTER_JOB_EXCLUDED_NODES`; a disk-free
preflight prevents cloning into an already exhausted filesystem.

Concurrency is `HARVESTER_JOB_MAX_ACTIVE` globally for coding Jobs, and
`HARVESTER_JOB_MAX_ACTIVE_READONLY` for read-only review chunks. They are
separate pools (label `codetether.io/job-class`) so a queue of multi-GiB clones
cannot starve the PR review check. Each coding Job requests
6Gi ephemeral storage (a measured spotlessbinco clone is ~4.5Gi; the emptyDir
ceiling is 10Gi) so the scheduler, not a one-per-node rule, keeps Jobs from
overcommitting a node. Anti-affinity is only a spreading preference.

Preparation runs the existing clone task. Later coding/recovery tasks reconstruct
their workspace from the authenticated Git remote in an init container. PR tasks
must match their pinned head. No old pod filesystem is reset, copied or removed.
Legacy author-session preservation requires an explicit handoff and is rejected
rather than silently losing unpushed state.

Successful read-only/clone Jobs receive a TTL after termination evidence is saved
in task metadata; because they never hold user work, cancelled or failed
read-only Jobs are released the same way (their evidence is kept on the task).
Coding Jobs additionally require a clean local audit, no stash
or unpushed branches, and confirmation of the audited head on the remote branch.
The supervisor records every local branch head. The controller verifies those
commits against live remote refs, including ancestry after a branch advances.
The local `unpushed` flag alone is not remote proof: `--single-branch` clones
can push topic branches without adding their remote-tracking refs. Genuine
unpublished work is still retained.

If Kubernetes has already removed a finished Pod, its Job record holds no
workspace and can be reclaimed. Its last saved audit is preserved instead of
being overwritten by an empty observation. Retained coding Jobs cannot consume
the separately bounded read-only review pool.

A committed `.gitmodules` file is ordinary content; only an initialised
submodule store (`.git/modules`), shallow, grafted or alternate-object layouts
make the audit refuse to judge the workspace.
On ordinary task failure, unknown/dirty work is retained in a terminated pod for
recovery. `emptyDir` is not disaster-recovery storage: node loss or eviction may
remove it. Pushed Git commits and control-plane results are the durable handoff;
do not mistake a retained pod for a durable backup.
Retained Job count is capped: capacity exhaustion defers new admission instead of
allowing unlimited disk growth. Do not manually remove retained pods before
recovering their work. Their private startup log is `/work/worker.log`.

## Operations

```sh
kubectl -n a2a-system get jobs -l codetether.io/task-job=true
kubectl -n a2a-system get pods -l codetether.io/task-job=true
```

Keep legacy StatefulSet replicas only while their existing tasks drain, with
`OnDelete` strategy to prevent surprise restarts. Scale them to zero through
Argo after drain; retain their old PVCs for independent recovery/audit.
Never put credentials in command arguments or diagnostic output. Job CLI help
is wrapped to suppress environment-backed credential values.