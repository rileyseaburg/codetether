# Checks-gated Forgejo auto-merge

## Scope

- Explicitly enabled only for CodeTether-published PRs in `riley/spotlessbinco`.
- Requires all six configured check contexts on the current PR head, with every
  returned check successful. Missing, pending, failed, truncated, or stale
  evidence cannot authorize a merge.
- Respects draft/conflict/paused/cancelled states and change-request reviews.
- Calls Forgejo merge with exact `head_commit_id`, `force_merge=false`, and
  branch deletion disabled. Does not create a native queue that can follow an
  unchecked future head. Forgejo still enforces its server-side protections.
- An independent reconciler evaluates eligible publication checkpoints every
  roughly 60 seconds; no repository/model work is scheduled by this gate.

## Evidence

- Mocked local / focused checks: 41 passed; `tests-final-v2.xml`.
- Docker build, publication, and production-runtime imports exited 0.
- Live deployment/Argo: API and Temporal workers in `a2a-system` rolled onto
  `automerge-580ff64bd07d`.
- Digest: `sha256:947b15f8bf2176f5ba38dce85e35a9302093cef283f04e312e52c250ebfb1341`.
- API pod: `a2a-server-deployment-green-7b6755f596-kxb8q`.
- Live read-only evaluation for PR 5901 returned `checks-not-all-successful`
  for head `98e37a2747484ec83de0d3940d22861d1c7877f3`.
- Forgejo reported the PR open/unmerged and zero statuses for that head.
- PR 5873 evaluation returned `disabled-or-paused`; its hold was preserved.
- Repository protections were inspected, not modified. No force merge or
  branch deletion was performed.

## Not-run

- No successful production auto-merge is claimed: the inspected PR did not
  yet have the required passing checks. Positive merge behavior was tested
  with mocked Forgejo responses; the live negative gate was observed.