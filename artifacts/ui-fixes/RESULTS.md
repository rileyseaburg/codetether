# UI fixes — implementation evidence

## Deliverables

| Area | Implementation | Evidence level |
| --- | --- | --- |
| Signup | Server-initiated, tenant-aware Auth.js sign-in with PKCE/state; tenant-aware token refresh; correct public client selection | Mocked local: browser checks authorization URL and HttpOnly verifier/state cookies; live callback/token exchange not run |
| Checkout | Shared credential resolver supports password-token and SSO users; waiting/duplicate-submit protection | Mocked local: checkout request includes password-login bearer token and redirects to fixture destination |
| Navigation | Homepage-qualified anchors from secondary pages; keyboard dismissal of mobile menu | Mocked local: privacy-to-pricing navigation and Escape checks |
| Dashboard shell | Managed dialog/menu, focus restoration, named controls, settings link, matching sidebar/content widths | Mocked local: component/browser interaction checks and DOM geometry |
| Tasks | Native task-selection buttons with pressed state and visible keyboard focus | Mocked local: Enter selects a task and opens its details |
| Chat | Ignore composing Enter and Safari keyCode 229; preserve ordinary Enter and Shift+Enter | Mocked local: focused component events; real OS IME not run |
| Provider keys | Test entered keys before saving; explicit unsupported/failure feedback; preserve custom URL saving | Mocked local: component tests and intercepted browser request |
| Billing | Preserve known quotas, display Unavailable on failed/malformed usage, explicit retry, defensive numeric rendering | Mocked local: component tests and failed-then-restored usage API |
| Visual polish | Readable primary CTA colors, responsive shell alignment and homepage widths | Mocked local: CTA contrast >=4.5, widths 390/768/1440, retained screenshots; not exhaustive visual/WCAG review |

## Commands and outcomes

Run from `marketing-site/` unless noted otherwise.

- **Mocked local:** `./node_modules/.bin/tsx --test src/lib/auth-ui.test.ts`
  exited 0, 8 tests. `auth-unit-final.log`.
- **Mocked local:** `./node_modules/.bin/jest --config jest.dashboard-shell.config.cjs --runInBand --json --outputFile=../artifacts/ui-fixes/dashboard-shell-results.json`
  exited 0, 11 tests (including two source assertions). `dashboard-shell.log` and `dashboard-shell-results.json`.
- **Mocked local:** `./node_modules/.bin/jest --config jest.settings-billing.config.cjs --runInBand --json --outputFile=../artifacts/ui-fixes/settings-billing-results.json`
  exited 0, 22 tests. `settings-billing.log` and `settings-billing-results.json`.
- **Mocked local:** `BASE_URL=http://127.0.0.1:3107 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/home/riley/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell ./node_modules/.bin/playwright test e2e/ui-regressions.spec.ts --workers=1 --reporter=line --trace=on --output=../artifacts/ui-fixes/playwright-run5`
  exited 0, 12 tests. `playwright-run5.log` plus screenshots/traces in `playwright-run5/`.
- **Static/local:** `./node_modules/.bin/tsc --noEmit --incremental false -p tsconfig.json`
  exited 0. `typecheck-release-check.log` (empty because there were no diagnostics).
- **Static/local:** `node artifacts/ui-fixes/lint-changes.cjs` from repository root
  exited 0: 22 changed/new source and test files, zero introduced errors against the checked-out HEAD baseline.
  `lint-release-check.log` and `lint-comparison.json`. Two existing dashboard
  `react-hooks/set-state-in-effect` errors remain; this is not a clean full lint claim.
- **Static/local:** Scoped `git diff --check` exited 0. Python AST inspection of
  `a2a_server/tenant_service.py` confirmed the central callback and origin in
  the new-tenant allowlists.

## Retained failures and recovery

Earlier browser runs and their traces remain in this directory. They exposed
and led to fixes for the Auth.js beta lazy-wrapper middleware boundary and
the dialog root's zero-sized box. Fixture corrections include representing
unauthenticated Auth.js sessions as null, allowing both loopback hostnames
used by Next's development redirect, and matching the actual Unavailable label.
The original audit evidence under `artifacts/ui-audit/` is preserved unchanged.

## Rollout limits

**Not-run:** deployment, live signup/callback/token exchange, Stripe checkout,
real provider requests, real screen reader/IME testing, production build, and
full-repository test suites. Existing tenant clients require the exact shared
callback URI added to their Keycloak allowlist. The backend does not implement
custom-endpoint key testing, so the UI reports it unsupported rather than
claiming success. See `marketing-site/UI_VALIDATION.md` for the rollout contract.

The audit-started development server was stopped. Generated `next-env.d.ts`
changes were restored. Unrelated pre-existing work was preserved; no commit,
push, deployment, or live account mutation was performed.