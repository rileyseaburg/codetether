# Auth/signup and checkout evidence ledger

Objective: implement UI audit findings 1–2, with Auth.js PKCE signup and both
Auth.js/password-token checkout, mocked local regressions, focused checks,
and scoped commits. No live credentials, deployment, or checkout was attempted.

Source of truth: `/home/riley/A2A-Server-MCP/artifacts/ui-audit/AUDIT.md` (read-only).
A byte-identical, mode `0444` snapshot is available to workspace-confined readers
at `artifacts/ui-audit/AUDIT.md`. `cmp` exited 0; both files' SHA-256 is
`d2042fe88cee557e5b915af1fa3d6b1ad76f00bc0c5cbc4f425b0ab168c670a6`.
The parent document was not modified.

The first independent review reproduced the mocked local and static/local
checks but rejected the terminal transition solely because its confined tools
could not read the parent audit document. The snapshot above addresses that
specific evidence-access gap; no code/test changes were made after the checked
revision.

## Production

- Scoped commit: `5496c3f1` changes only `marketing-site/src/components/Pricing.tsx`.
- Static/local: registration uses `startWorkspaceSignIn`; the action validates
  tenant selectors before Auth.js sign-in. The tenant provider retains PKCE/state.
- Static/local: Pricing observes password-token changes and permits checkout
  during Auth.js discovery only when usable credentials exist. Click handling
  reads fresh credentials and still blocks duplicate upgrades.

## Observed checks

- `local-checks.log`: static/local auth helper tests 11/11, mocked local
  readiness tests 4/4, focused ESLint and no-emit TypeScript, each exit 0.
- `peer-pkce-rerun.log`: mocked local original Auth.js protocol tests 4/4, exit 0.
- Failed diagnostic logs are retained alongside the subsequent successful run.

## Committed-revision audit

Current tested revision: `b36548b223b45386a93308510c01222214b93499`.
Tests-only peer commit `dc20702d` was reviewed and explicitly cherry-picked as
`b36548b2`; production commit remains `5496c3f1e1effc441d505d6ce07b2e74d49bf7b3`.
The two scoped commits change exactly these files:

- `marketing-site/src/components/Pricing.tsx`
- `marketing-site/jest.signup-checkout.config.cjs`
- `marketing-site/src/lib/signup-pkce.test.ts`
- `marketing-site/tests/signup-checkout.test.cjs`

No voice files, package metadata, credentials, or unrelated production files
were changed. Signup's server-action PKCE path already existed at the supplied
base revision; it was inspected and covered with new regressions rather than
rewritten redundantly.

| Requirement | Evidence level and observed result |
| --- | --- |
| Inspect findings 1–2 | Static/local: read the designated `AUDIT.md` and current register/action/provider/Pricing/auth-token sources. No changes to the audit. |
| Signup initializes Auth.js PKCE | Mocked local: signup result renders a server-action form using only the realm; action selects the validated tenant before sign-in. Real Auth.js against a mocked IdP issues fresh PKCE/state cookies, exchanges the code with the matching verifier, and creates a session. Direct callback, missing PKCE, and mismatched state are rejected without token exchange/session creation. |
| Both checkout auth methods | Mocked local: rendered Pricing sends the session or password bearer token, tier, success and cancellation URLs. Both `a2a_token`/`access_token` work while Auth.js loads; same/cross-tab changes, fresh click-time tokens, loading with no token, duplicate clicks, successful navigation and missing-URL retry feedback are covered. |
| Run focused checks | See the two logs below; every command exited 0. |
| Scoped commits | Static/local: `git diff 336f5fd..HEAD --name-only` lists only the four files above. |

### Commands at the tested revision

Executed from this isolated worktree's `marketing-site/` directory:

- Static/local: `npm run test:auth` — **11/11**, exit 0.
- Mocked local: `./node_modules/.bin/tsx --test src/lib/signup-pkce.test.ts` — **4/4**, exit 0.
- Mocked local: `./node_modules/.bin/jest --config jest.signup-checkout.config.cjs --runInBand` — **23/23**, exit 0.
- Mocked local: `./node_modules/.bin/jest --config jest.dashboard-shell.config.cjs --runInBand --runTestsByPath tests/auth-readiness.test.cjs` — **4/4**, exit 0.
- Static/local: focused ESLint on Pricing, the three new regression/config files, and register/action/provider/auth-token sources — exit 0.
- Static/local: `./node_modules/.bin/tsc --noEmit --incremental false` — exit 0.
- Static/local: `git diff --check` — exit 0.

Full command/output artifacts, retained relative to this worktree:

- `artifacts/ui-audit/auth-checkout/committed-regressions.log`
- `artifacts/ui-audit/auth-checkout/committed-static-checks.log`

The nonfatal Node `module.register()` deprecation and outdated Browserslist
data warnings remain visible in the logs. Earlier failed fixture/invocation
and diagnostic artifacts are preserved; the original committed suites above
were rerun successfully, rather than substituting diagnostic copies as proof.

Live deployment/Argo: **not-run**. Real IdP/Stripe/platform upload: **not-run**.
This objective requires mocked local and static/local evidence only; fixture
callbacks and checkout URLs are not live authentication or payment evidence.