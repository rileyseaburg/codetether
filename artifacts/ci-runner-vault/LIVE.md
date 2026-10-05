# PR 5907 CI reviewer recovery

## Confirmed runtime attribution

- Original UI run 9261 / API run 10176 / job 20207 ran on runner 174,
  `proxmox-node-ephemeral-lxc`, and failed loading
  `kv/forgejo/codetether-bot` with Vault HTTP 403 / invalid token.
- Current-head UI run 9264 / API run 10179 / job 20213 had the same runner.
- User-provided SSH host `192.168.50.133` contains the runner source directory
  `/root/forgejo-lxc-runner-pool`; its topology documentation identifies pool
  host `192.168.50.134` and quarantined CT 300.
- CT 300 was still running `forgejo-runner.service`, advertising trusted labels,
  and using an invalid static Vault token in `/etc/forgejo-runner/job.env`.
- The live trusted Kubernetes runner IDs were 376, 377, 380, 382, 383, 384;
  the failing Proxmox runner was not one of those pods.

## Recovery action

- Verified no active Docker jobs, no unexpected nested job containers, and a
  three-hour graceful runner shutdown configuration.
- Disabled and stopped only `forgejo-runner.service` in CT 300. Observed
  `inactive` and `disabled`. Did not stop/restart CT 300, touch its quarantined
  disk, or stop the separate `codetether-worker-01` container.
- Healthy trusted Kubernetes runner credentials were verified renewable and
  authorized to read the required `codetether-bot` credential. No token values
  were printed or copied into the quarantined runner.
- Re-ran only the current-head review using Forgejo's authenticated rerun route.
  The obsolete original SHA was rejected by the recovery script's guard.
- Recovery run: https://forgejo.quantum-forge.io/riley/spotlessbinco/actions/runs/9264/jobs/0/attempt/2
- Head: `7ba48ee2c92ba7ce0cb313de36759ede4eb91ba0`.
- Selected runner 383: `forgejo-act-runner-dind-59d7674f4c-fdj99`.

## Live evidence and remaining blocker

- Checkout, tool setup, and helper validation succeeded on attempt 2.
- The review advanced beyond Vault credential loading and author validation.
- It then refused an oversized complete diff: 15,002,798 bytes with 80 lines
  of context; 13,866,128 bytes with standard context; limit 10,000,000 bytes.
- This is not a passing review. No diff truncation, author-verification bypass,
  forced merge, or green status override was performed.
- The current check remains failed pending a smaller PR scope or an explicitly
  approved bounded-review capacity change.

## Separate task 476 / issue 5908

- Its worker completed a read-only review at
  `6b5eb936c76152ff1b2978107fe81e25de1765f6` without identifying an actionable
  code defect. It reported missing exact-head build/runtime evidence, not a
  Vault access failure. It was not retried or rewritten by this recovery.