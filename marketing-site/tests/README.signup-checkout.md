# Signup PKCE and dual-auth checkout regressions

This suite covers UI audit findings 1–2. All runtime evidence is **mocked local**;
configuration, lint, types, and Git checks are **static/local**. These checks do not
contact Keycloak, provision a tenant, enter user credentials, or create a Stripe
checkout session. Live Keycloak/Stripe checks are **not-run**.

## Authoritative audit inspected

The designated `artifacts/ui-audit/AUDIT.md` was inspected read-only in the primary
checkout at `/home/riley/A2A-Server-MCP/artifacts/ui-audit/AUDIT.md`. It is absent
from the managed child's tracked files; no primary-checkout files were changed.
The inspected full document has SHA-256
`d2042fe88cee557e5b915af1fa3d6b1ad76f00bc0c5cbc4f425b0ab168c670a6`.
An exact excerpt of its findings 1–2 is retained at
`artifacts/auth-checkout/audit-findings-1-2.md` in the managed child.

- **Finding 1, P1 — Post-signup sign-in skips Auth.js PKCE initialization:** the
  audit identifies a hand-built Keycloak URL without a verifier cookie and asks
  for tenant-aware server sign-in. The current registration/action/provider flow
  initializes Auth.js with PKCE/state; rendered signup/action tests and actual
  Auth.js callback tests against mocked OIDC cover that remedy.
- **Finding 2, P2 — Paid-plan upgrade sends password-authenticated users to
  registration:** the audit asks for a shared dual-method token abstraction.
  Current checkout uses the shared SSO/password-token resolver. The production
  readiness fix and rendered regressions also cover password tokens during SSO
  discovery, so those users can reach bearer-authenticated checkout.

The audit's line references describe earlier code, not current line locations.
The mapping below documents the current sources and evidence for both findings.

## Source-to-requirement map

| Requirement | Current implementation | Regression evidence |
| --- | --- | --- |
| Post-signup login initializes Auth.js rather than constructing a direct callback URL | `src/app/(auth)/register/page.tsx` submits `realm_name` to `startWorkspaceSignIn`; it ignores the response's `login_url` | Rendered signup success/failure and real server-action tests in `tests/signup-checkout.test.cjs` |
| Select the tenant before creating PKCE/state | `src/app/(auth)/actions.ts` validates the realm before setting `TENANT_AUTH_COOKIE` and calling `signIn('keycloak')`; `src/auth.ts` selects the tenant provider for sign-in and callback requests | Server-action ordering, invalid selectors, shared-realm clearing, redirect/error behavior; helper trust checks in `src/lib/auth-ui.test.ts` |
| Derive tenant issuer/client from trusted configuration, without the shared secret | `src/lib/tenant-auth.ts` restricts realm names and creates the public `<slug>-spa` provider with `checks: ['pkce', 'state']`; `src/auth.ts` uses this provider | Helper tests and actual Auth.js authorization/callback with a mocked OIDC provider in `src/lib/signup-pkce.test.ts` |
| A fresh callback creates a session only with matching PKCE/state | Auth.js manages the challenge, verifier, state, and session cookies | The mock IdP verifies S256 against the verifier sent by actual Auth.js. Missing initiation, missing PKCE cookie, and wrong state exchange no code and create no session |
| Checkout accepts Auth.js and supported password-token login | `src/lib/auth-token.ts` resolves session token first, then `a2a_token` / `access_token`; `src/components/Pricing.tsx` reads the token at click and sends a bearer-authenticated checkout request | Both password aliases, SSO precedence, fresh click-time token, billing URLs, and returned checkout URL |
| Password checkout is usable while Auth.js discovers its session | `Pricing.tsx` subscribes to stored-token changes with `useSyncExternalStore` and only waits when no usable token exists | Both aliases during Auth.js loading, SSR readiness, no-token loading, same-tab login, and cross-tab logout |
| Checkout remains safe and retryable during requests | `Pricing.tsx` disables paid checkout buttons in flight, reports errors, and resets the upgrade state | Duplicate-request prevention and missing-checkout-URL feedback in the rendered suite; existing `tests/auth-readiness.test.cjs` |

Registration's server action, trusted tenant provider, and shared token resolver
were already present in the assigned base; the tests protect those implementations
rather than replacing them. Production commit
`cdfd85c514320ee160cfbaae29b055ab4def328f` adds the missing password-checkout
readiness during SSO discovery. Regression commit
`dc20702d248475f0d28ab90b4e2c66d499f31192` adds the rendered/protocol suites.

## Test boundaries

- Jest renders the real signup and Pricing components and executes the real server
  action. It mocks Next headers/navigation, Auth.js sign-in/session lookup, and the
  signup/billing API boundary. Checkout redirect behavior uses a same-document URL.
- The protocol test runs actual `@auth/core` with the real tenant-provider helper,
  cookie jar, PKCE/state callbacks, and a mock OIDC discovery/token endpoint.
  Fixture session callbacks do not replace coverage of the production server
  action and provider selection. This is not a production Keycloak integration.
- Auth.js masks these negative callbacks behind a `Configuration` public redirect.
  The protocol tests assert captured `InvalidCheck` / `CallbackRouteError` causes
  as well as zero exchanges and absent sessions, not merely redirect labels.
- Test issuer/user/token/secret values are invented fixtures, not credentials.

## Reproduce

From `marketing-site/`, using the existing installed dependencies:

```sh
./node_modules/.bin/tsx --test src/lib/auth-ui.test.ts src/lib/signup-pkce.test.ts
./node_modules/.bin/jest --config jest.signup-checkout.config.cjs --runInBand --no-cache
./node_modules/.bin/jest --config jest.dashboard-shell.config.cjs --runInBand --runTestsByPath tests/auth-readiness.test.cjs
./node_modules/.bin/eslint src/components/Pricing.tsx 'src/app/(auth)/actions.ts' 'src/app/(auth)/register/page.tsx' src/lib/auth-token.ts src/lib/tenant-auth.ts src/lib/signup-pkce.test.ts tests/signup-checkout.test.cjs jest.signup-checkout.config.cjs
./node_modules/.bin/tsc --noEmit
```

The signup/checkout Jest config anchors both `dir` and `rootDir` to `__dirname`,
so it can also be invoked from the worktree root without mixing source trees:

```sh
./marketing-site/node_modules/.bin/jest --config marketing-site/jest.signup-checkout.config.cjs --runInBand --no-cache
git diff --check
```

The child worktree retains repeatable runner
`artifacts/auth-checkout/continuation-checks.cjs` and full logs
`artifacts/auth-checkout/combined-checks.log`,
`artifacts/auth-checkout/continuation-checks.log`,
`artifacts/auth-checkout/continuation-final-checks.log`, and
`artifacts/auth-checkout/continuation-rechecked.log`.
The two earlier continuation logs preserve command-only lint failures (unsupported
`next lint` invocation, then a nonexistent input path); do not treat their aggregate
exit status as successful. Inspect each logged command and exit status. The final
runner uses direct ESLint on existing scoped paths. Logs/runners are evidence
artifacts, not application code, and remain untracked in this managed worktree.
