# Backend preflight and remaining physical-phone gate

## Read-only diagnosis

- **Live deployment/Argo:** `kubectl auth can-i get pods/log -n keycloak`
  returned `yes`. The sanitized log check matched four `LOGIN_ERROR` events for
  the username displayed in the phone form and client `a2a-monitor`; all were
  `invalid_user_credentials`. These are recorded events, not new login attempts.
- No password was entered, printed, reset, or guessed. The dedicated synthetic
  test account remains in Vault at `secret/codetether/ios-e2e-user`.

## Worker repair and workspace mapping

- **Live deployment/Argo:** the API's worker middleware secret was not wired.
  Existing local and Vault worker credentials received HTTP 401. Added the
  dedicated `a2a-system/a2a-server-ios-worker-auth` Secret reference through the
  existing `workerAuth.existingSecret` chart setting, without disabling auth.
- Argo app `argocd/codetether-a2a-server`, pinned revision
  `eb2051a212a2c729a7963da8e1dda39a4e958513`, rolled the API deployment to
  generation 204 with 2 updated/ready replicas. App health is Healthy; its
  unrelated harvester StatefulSet remains OutOfSync and was not modified.
- The worker registry probe returned HTTP 200 after rollout. Refreshed the
  local service credential securely and restarted the previously failing worker.
- Actual worker: `wrk_1791203157_35195f4f7b97da0a`, name `ubuntu-dev`, active.
- Registered workspace: `ios-e2e-ubuntu-dev`, name `iOS E2E - ubuntu-dev`, path
  `/home/riley/A2A-Server-MCP/artifacts/ios-e2e-web`, attached to that worker.
- The optional legacy user/workspace-association endpoint returned HTTP 500.
  The native main workspace listing does not use it; the isolated workspace is
  present in that listing. This legacy endpoint issue remains unresolved.

## Hosting and remaining work

- Planned site root: `artifacts/ios-e2e-web/site`; unused LAN port: 8766.
- Planned URL: `http://192.168.50.101:8766/`; **no page is hosted yet**.
- Existing ports 80/443 serve cameras; the public tunnel serves agent/audio