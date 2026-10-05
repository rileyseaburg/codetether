# UI second pass — implementation and evidence

## Additional improvements

- **Dashboard preferences:** saved dark/light choice, cross-tab synchronization,
  and usable in-page fallback for blocked storage or failed writes. Refactored
  theme/auth subscriptions instead of suppressing state-in-effect diagnostics.
- **Identity synchronization:** password-login, rotation, and logout changes
  update both dashboard identity and the shared API client's cached credential.
  Storage failures and malformed profiles no longer crash the shell.
- **Navigation:** keyboard skip link, focusable main region, active-section
  announcements for nested paths, and breadcrumbs. Removed fabricated Connected
  status and hardcoded zero workspace/task counts.
- **Route recovery:** accessible loading skeleton and dashboard error fallback
  with retry/back navigation; raw exception details are not rendered.
- **Tasks:** distinct loading/error/empty/filtered states, stale-row preservation,
  retry, bounded requests, non-overlapping polling, and a managed creation form
  with validation, focus restoration, duplicate-submit protection, and explicit
  confirmed/unknown dispatch feedback.
- **Sessions:** list/message states are independent; stale requests cannot
  overwrite newer selections/searches. History expands the requested window
  instead of duplicating the same messages. Retry/load-more controls, native
  selection buttons, password-token auth, and malformed-response handling.
- **Model picker:** combobox/listbox semantics, active-descendant navigation,
  synchronous filtering, no Tab trap or accidental form submission, focus-aware
  dismissal, loading/no-results feedback, and corrected viewport positioning.
  All four outer variants now forward real disabled semantics.

## Verification

- **Mocked local:** `npm run test:ui -- --json --outputFile=../artifacts/ui-pass2/ui-unit-verified-results.json`
  exited 0: **120 tests across six suites/five Jest projects**.
  `ui-unit-verified-results.json`, `ui-unit-verified.log`.
- **Mocked local:** `npm run test:auth` exited 0: **8 helper tests**.
  `auth-unit.log`.
- **Mocked local:** `BASE_URL=http://127.0.0.1:3107 PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/home/riley/.cache/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-linux64/chrome-headless-shell ./node_modules/.bin/playwright test e2e/ui-regressions.spec.ts --workers=1 --reporter=line --trace=on --output=../artifacts/ui-pass2/playwright-retry`
  exited 0: **17 browser tests**. `playwright-retry.log` and
  `playwright-retry/` retain screenshots and traces. The suite includes the
  previous auth/checkout/navigation cases as regression coverage.
- **Static/local:** `tsc --noEmit --incremental false -p marketing-site/tsconfig.json`
  from repository root exited 0. `typecheck-verified.log` has no diagnostics.
- **Static/local:** `node artifacts/ui-pass2/lint-changes.cjs` exited 0.
  Across 50 changed/new source/test files, the current HEAD baseline has 12
  errors; current code has 6, with **zero introduced errors**. Existing Sessions
  errors remain; this is not a clean full-lint claim. `lint-comparison.json`,
  `lint-verified.log`.
- **Static/local:** Scoped `git diff --check` exited 0.

## Retained exploratory evidence

Earlier runs remain available. Initial browser failures were test assertions
that matched `dark:` utility classes instead of the standalone theme class,
matched session action buttons as well as the session row, or expected slash
model IDs where Workers normalizes them to colon IDs. Corrected assertions
retain the substantive focus, selection, persistence, and no-mutation checks.
A brittle source-shape test was relaxed after task activation moved into a
focus-aware handler; browser and component tests verify actual selection.

## Limits and cleanup

**Not-run:** deployment, production build, live task/chat submission, live
provider/auth/checkout operations, real assistive-technology testing, and an
exhaustive audit of all routes. This remains a targeted UI improvement pass.
The local dev server was stopped and generated `next-env.d.ts` changes restored.
Unrelated work and all earlier audit/first-pass evidence were preserved.
No commit, push, release, or live account mutation was performed.