# Signup and checkout regressions

Run from `marketing-site/`:

```sh
npm run test:auth
npx jest --runInBand --config jest.signup-checkout.config.cjs
npx jest --runInBand --config jest.dashboard-shell.config.cjs
```

`npm run test:ui` includes the signup/checkout and dashboard-shell projects.

- `src/lib/signup-pkce.test.ts` uses Node's test runner and Auth.js with a
  **mocked local** identity provider. It checks the cookie-backed S256 verifier,
  state binding, rejection of missing cookies and direct callbacks, and public
  tenant-client behavior. It must not be loaded as a Jest suite.
- `tests/signup-checkout.test.cjs` is **mocked local** rendered UI/server-action
  coverage for tenant signup and both Auth.js and password-token checkout.
- `tests/auth-readiness.test.cjs` is **mocked local** hydration and safe native
  POST coverage in the dashboard-shell project.

These commands contact neither a real identity provider nor Stripe. They do not
establish live account creation, a payment session, or deployment success.