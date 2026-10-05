# Forgejo main publication and production rollout

## Source publication — static/local and live remote Git

- Workspace branch: `main`; no tracked modifications remain.
- Source commit: `eb2051a212a2c729a7963da8e1dda39a4e958513`.
- GitOps rollout commit: `336f5fd88707887c2747939438c48115350fa6cd`.
- `git ls-remote forgejo refs/heads/main` matched the rollout commit.
- Remote: `https://forgejo.quantum-forge.io/riley/codetether.git`.
- Requested changes were committed; unrelated local evidence/runtime files and submodule-only untracked work were retained rather than deleted or committed.
- Original tracked changes are also preserved in `pre-commit.patch`.

## Checks — focused CI-like / static/local

- Focused server regressions: 271 tests and 32 subtests; `server-tests-rerun.log`.
- Isolated policy suite: 26 tests; `policy-isolated.log` / `policy-isolated.xml`.
- Dashboard: 146 tests in 10 suites; `ui-tests.log`.
- Authentication/origin tests: 11 tests; `auth-tests.log`.
- `marketing-site/node_modules/.bin/tsc --noEmit`: observed exit 0; `typescript-final.log`.
- Helm lint: one chart, zero failures; `helm-lint.log`.
- Configured production-image imports succeeded; `server-image-smoke-configured.log`.
- Limitation: the original combined server/policy run had 19 failures, retained in `server-tests.log`. Separate suites succeeded, but the combined-run interaction is not established as fixed. This is not a claim that the full CI pipeline is green.

## Production — live deployment/Argo

- Image source revision: `eb2051a212a2c729a7963da8e1dda39a4e958513`; the next commit changes only deployment manifests.
- API and Temporal worker: `a2a-system`, `a2a-server-mcp:main-eb2051a212a2`, digest `sha256:f98bd714789f0b7a8693ec47a3abe87a0d87f34984e3c7719cfeb0f334b9b8a0`; API 2/2 Ready, Temporal worker 1/1 Ready, zero restarts.
- Dashboard: `a2a-server`, `codetether-marketing:ui-eb2051a212a2`, digest `sha256:fbd3f4c362329c3972dd297cb2de028a29e9da3a7ed748a2af89c7cc45401c87`; 1/1 Ready, zero restarts.
- Argo applications: `argocd/codetether-a2a-server` Healthy/OutOfSync and `argocd/codetether-marketing` Healthy/Synced; both successful sync operations reference the source revision above.
- Residual server drift is confined to the zero-replica `a2a-server-harvester` StatefulSet. Desired/live spec artifacts and normalized diff are retained; no destructive replacement was attempted.
- Public smoke checks: API `/health`, dashboard `/`, and dashboard `/login` return 200; anonymous `/v1/worker/connected` returns 401.
- `node artifacts/main-rollout-20261005/verify-live.mjs` exited 0, comparing live pod digests/readiness and Argo snapshots to publication records and checking public endpoints.