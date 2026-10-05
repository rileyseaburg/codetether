# UI regression checks and rollout notes

## Scope

The UI fixes cover tenant signup/SSO, password-token checkout, shared navigation,
dashboard keyboard access, IME-safe chat input, unsaved provider-key testing,
billing failure/retry states, and primary CTA contrast. The second pass adds
persistent themes, cross-tab auth synchronization, task/session request recovery,
history pagination without duplicates, and the shared model picker’s keyboard
and screen-reader semantics. These are not a claim of
full WCAG conformance or an exhaustive redesign of every dashboard route.

## Authentication rollout

Registration now starts Auth.js through a server action on the marketing app.
Only a validated workspace realm is accepted; the issuer is derived from the
server's Keycloak configuration and the public client name from the provisioned
realm convention. Auth.js creates PKCE and state cookies. The selected realm is
retained in the encrypted session JWT so refresh uses the original realm even
after the short-lived sign-in selector cookie expires. Ordinary SSO explicitly
clears a previous workspace selector.

Deploy the frontend and the tenant provisioner's redirect-list change together.
New tenant clients allow the exact central callback:
`https://codetether.run/api/auth/callback/keycloak`.
Existing tenant clients need that callback added to their Keycloak redirect
allowlist before this shared-origin sign-in path can work. This code change does
not mutate existing realms or deploy anything.

The installed Auth.js beta returns an asynchronous middleware wrapper when lazy
configuration is used. `src/middleware.ts` keeps a callable export and awaits
that wrapper; regression coverage includes a redirect without the test bypass.

## Focused component and helper checks

Run from `marketing-site/`:

```sh
npm run test:auth
npm run test:ui
./node_modules/.bin/tsc --noEmit --incremental false
```

`test:ui` runs five focused Jest projects: shell/preferences, settings/billing,
task resilience, session resilience, and model selection. Their requests use
fixtures; no real tasks, chat messages, payments, or provider-key tests are sent.

The dashboard theme is stored under `codetether-theme` and synchronized through
browser storage events. Restricted storage falls back to an in-page preference.
Password-login/logout changes notify the shared API client as well as the UI,
so another tab’s logout does not leave the SDK using its cached bearer token.
The shell no longer displays hardcoded connectivity or zero-count metrics.

## Fixture-backed browser checks

Run a local Next dev server on `127.0.0.1:3107`. Set both `AUTH_URL` and
`NEXTAUTH_URL` to `http://127.0.0.1:3107`, use a nonproduction fixture auth secret,
set `KEYCLOAK_ISSUER=http://127.0.0.1:3108/realms/shared`,
`KEYCLOAK_CLIENT_ID=ui-fixture`, and use a nonproduction fixture client secret.
Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:3108`.

```sh
BASE_URL=http://127.0.0.1:3107 ./node_modules/.bin/playwright test \
  e2e/ui-regressions.spec.ts --workers=1 --trace=on
```

The suite starts its own loopback OIDC discovery fixture on port 3108 and
intercepts account/API requests. It skips other base URLs. An optional
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` selects an existing browser installation.
These are **mocked local** checks, not live signup, checkout, provider-key, or
platform evidence. Custom-endpoint API-key testing remains unsupported by the
backend handler; the UI now reports that limitation rather than testing the
wrong endpoint. Saving a custom endpoint remains available.