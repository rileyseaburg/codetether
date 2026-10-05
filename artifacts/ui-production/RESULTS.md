# Production UI deployment

## Outcome

**Live deployment/Argo:** the redesigned UI is deployed on
`https://codetether.run/dashboard` and `https://quantum-forge.codetether.run/dashboard`.
Real browser sign-in, Workspaces, Tasks, Sessions, and mobile navigation checks
succeeded on both hosts without a canary header or mocked responses.

- Source commit: `a1d68a889bd3e752e5a00b6cfba90a0e9888c0c0`.
- GitOps promotion commit: `767a70bee083399b78a355292837e3a915580869`.
- Image: `registry.quantum-forge.net/cluster-ci-cache/codetether-marketing:ui-a1d68a889bd3`.
- Digest: `sha256:96c02d1812ae83977361370ef9acdd57ed02497001694e2bc42deb3dc9f5dbab`.
- Argo Application: `argocd/codetether-marketing`, **Synced / Healthy**, operation **Succeeded**.
- Production pod: `a2a-server/codetether-marketing-65f976658f-56hz6`, ready, zero restarts.
- Public build check: `https://codetether.run/api/ui-version` returned the source commit.
- PR: https://github.com/rileyseaburg/codetether/pull/133

## Evidence

- `release.json`: source/image/promotion identity.
- `argo-final.json`, `production-pod.json`: live controller and pod evidence.
- `production-browser.json`, `smoke-final.log`: normal production browser checks,
  including matching-host OAuth callbacks, authenticated screens, collapsed
  advanced navigation, and mobile viewport bounds.
- `codetether.run-*.png`, `quantum-forge.codetether.run-*.png`: production screenshots.
- `canary-browser.json`, `canary-smoke-retry.log`, `canary-a1d68a889bd3/`: the
  successful production-host canary before global promotion.
- `build-a1d68a889bd3.log`: **focused CI-like** image build with 146 UI tests,
  11 auth-helper tests, TypeScript checking, and optimized production build.

## Deployment corrections

The earlier candidate was rolled back after the production smoke caught an
OAuth redirect URI mismatch. The final candidate normalizes trusted public
request origins behind TLS termination and keeps the browser on the origin
where authentication completed. Tenant API routing remains intact; it no longer
silently moves the browser to another host and loses the login cookie.

The image uses deterministic installs and the same Next.js/React versions as the
previous production runtime. Legacy embedded Dockerfile credentials were removed;
real secrets are supplied only at runtime. Build-only Node heap was increased
after the default heap failed TypeScript checking; production limits were unchanged.

The deployment reader credential could not publish to Harbor, and the legacy
Google registry required billing. The configured Harbor publishing credential
was used instead; no billing or repository-permission changes were made.

## Preservation and scope

Release commits were created using a separate Git index. The user's branch,
index, and unrelated unfinished work were not switched, committed, or discarded.
Argo remains the deployment authority, pinned to the tested immutable source.
Protected main was not bypassed; the production release is also submitted as PR #133.

Temporary test users were disabled and logged out. The canary Deployment,
Service, and Ingress were removed after successful global verification. The
owned Keycloak port-forward was stopped. Failed builds and smoke results remain
available in this directory.

This is production UI deployment proof, not a claim that the previously observed
signup, provider-key, or task-dispatch backend defects have been repaired.