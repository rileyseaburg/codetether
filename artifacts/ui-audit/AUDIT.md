# UI audit — marketing-site

Scope: Next.js marketing/auth UI, dashboard shell, and selected Tasks, Sessions, Settings, Billing flows. Read-only application audit; only evidence files retained. This is not an exhaustive route, visual-design, or WCAG conformance audit.

## Findings

### 1. P1 — Post-signup sign-in skips Auth.js PKCE initialization
Evidence: **static/local**. `src/app/(auth)/register/page.tsx:79–92` constructs a direct Keycloak authorization URL targeting the Auth.js callback. It does not create a PKCE challenge/verifier cookie; `src/auth.ts:62` enables PKCE outside development. For a fresh browser whose callback is handled by this application, the required verifier is absent. New users can encounter authentication failure immediately after registration. Start tenant-aware sign-in through the server auth flow rather than constructing the provider URL. Live tenant-instance configuration/authentication was not exercised.

### 2. P2 — Paid-plan upgrade sends password-authenticated users to registration
Evidence: **static/local**. `src/components/Pricing.tsx:212–220` recognizes only NextAuth authentication. Password login stores a custom token/cookie (`src/app/(auth)/login/login-form.tsx:92–100`) instead. A user signed in with that supported method clicks a paid-plan CTA and is redirected to `/register`. Share a dual-method authentication/token abstraction with checkout.

### 3. P2 — Closed mobile navigation captures invisible keyboard focus
Evidence: **mocked local**. At 390×844 on `/dashboard/settings`, the first six Tab stops were in the closed drawer, with every bounding box entirely left of the viewport (e.g. logo right edge −88px). `src/app/(dashboard)/layout.tsx:553–559` hides it only with translation. Remove the closed drawer from the focus/accessibility tree; use a managed dialog with focus restoration when open. Opening/closing controls also need accessible names.

### 4. P2 — Task details cannot be selected by keyboard
Evidence: **static/local**. `src/app/(dashboard)/dashboard/tasks/page.tsx:606–610` uses a clickable div without keyboard handlers, tabIndex, or button semantics. Keyboard-only users cannot activate a task row to open its details. Use a native button/link or an appropriate keyboard-operable selection pattern.

### 5. P2 — Test Key silently ignores a newly entered provider key
Evidence: **mocked local**. The enabled form button (`src/app/(dashboard)/dashboard/settings/page.tsx:550–553`) calls a handler that returns unless the provider already exists in saved keys (`:204–206`). Executing the actual extracted handler with an empty saved-key list produced zero requests and zero feedback calls. Test the entered key directly, or clearly require saving first and disable the action accordingly.

### 6. P2 — IME confirmation can submit an unfinished message
Evidence: **mocked local**. `src/app/(dashboard)/dashboard/sessions/components/ChatInput.tsx:19–23` submits on Enter without checking composition. An Enter event with `nativeEvent.isComposing: true` invoked sending and prevented default. The parent clears the draft (`sessions/page.tsx:229`). Respect composition state before treating Enter as send; retain Shift+Enter behavior. Real operating-system IME testing was not run.

### 7. P2 — Usage API failure becomes misleading zero quota
Evidence: **static/local**. `src/app/(dashboard)/dashboard/billing/page.tsx:308–317` ignores `usageRes.error` and defaults both usage and quota to zero, overwriting subscription data. When subscription succeeds but usage returns an SDK error result, the page represents unavailable data as `0 / 0`. Preserve the subscription quota and show usage unavailable/retry feedback rather than inventing zero usage.

### 8. P2 — Marketing header links break on secondary pages
Evidence: **mocked local**. Clicking Pricing from `/privacy` produced `/privacy#pricing`, where the target count was zero. Shared header links use fragments (`src/components/Header.tsx:70–88`, mobile `:158–179`) instead of homepage-qualified URLs. Use `/#pricing`, `/#features`, and the other corresponding homepage anchors.

## Additional shell observations

- **Mocked local:** Escape left the account menu open. The custom menu lacks keyboard dismissal (`src/app/(dashboard)/layout.tsx:719–775`).
- **Mocked local:** Four dashboard buttons had no text, aria-label, aria-labelledby, or title; this includes the mobile open/close and theme controls. The probe reports DOM attributes, not a full accessibility-tree audit.
- **Mocked local:** At desktop width 1440, sidebar width was 224px but content began at 208px. The 16px shell overlap comes from `lg:w-56` versus `lg:left-52` (`layout.tsx:612,675`). Match the layout dimensions; no assertion of obscured form content is made.
- **Static/local:** The settings gear in the shell is a button with no handler or link (`layout.tsx:712–714`).

## Verification and retained evidence

- **Mocked local:** `node artifacts/ui-audit/browser-check.cjs > artifacts/ui-audit/run-3.log 2>&1` exited 0. Browser requests used fixture authentication and intentionally returned 503 for external/API requests. No live account mutations were performed. The script collects observations; exit 0 does not mean the UI is free of defects.
- **Mocked local:** `node artifacts/ui-audit/interaction-probes.cjs` exited 0. Two assertions reproduced the API-key no-op and composition-triggered send using extracted source handlers.
- **Mocked local:** No page JavaScript exceptions were captured in the final browser run. Homepage document width equaled viewport width at 1440, 768, and 390px; this does not establish every component is usable or unclipped.
- **Not-run:** Full Jest/E2E suites, production build, live authentication/checkout, real backend integration, screen-reader/OS IME testing, and exhaustive visual/contrast checks. The existing Playwright config defaults to a production base URL, so it was not run blindly.
- `results.json`: browser observations and element bounds.
- `interaction-results.json`: handler-probe observations.
- `desktop.png`, `desktop-user-menu.png`, `mobile.png`: dashboard captures.
- `home-1440.png`, `home-768.png`, `home-390.png`: homepage captures.
- `browser-check.cjs`, `interaction-probes.cjs`: reproducible probes. Run from repository root with a local Next dev server at 127.0.0.1:3107; browser executable path is environment-specific.
- `run.log`: initial probe locator timeout; corrected from exact text to substring matching. Preserved, not an application failure.
- `run-2.log`: dashboard-only browser run, exit 0.
- `run-3.log`: final expanded browser run, exit 0.

The audit-started dev server was stopped. Its generated `next-env.d.ts` edit was restored; existing user changes were preserved. No product fixes were made.