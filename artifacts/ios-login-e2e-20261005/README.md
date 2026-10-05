# Native iOS login and task-path work — 2026-10-05

## Deliverables and remaining gate

- **Live deployment/Argo (Keycloak administration):** created dedicated user
  `codetether-ios-e2e@example.invalid` in realm `quantum-forge`, ID
  `0f3ebd9f-c68a-4b86-97a5-442d4fc62880`. Administration used the scoped
  `codetether-identity-provisioner` service identity via the `keycloak` namespace
  service. The test user is enabled, has no required actions, and has `editor`
  plus the realm default role; no administrator role was granted.
- Only this explicitly marked synthetic identity was email-preverified. The
  realm's email verification requirement was not changed. The password was
  generated and saved only in Vault at `secret/codetether/ios-e2e-user`.
- **Static/local:** native login used to discard all 401 error details. It now
  distinguishes account setup, disabled accounts, configuration failures, and
  bad credentials without echoing arbitrary upstream diagnostics.
- **Static/local:** legacy `/v1/opencode` routes were absent from the live schema.
  Updated paths, task request/response contracts, and server task-ID decoding.
  `node scripts/check_ios_api_routes.cjs artifacts/ios-login-e2e-20261005/openapi.json`
  exited 0: 50 literal routes checked, none absent. This checks path existence,
  not authenticated HTTP behavior. The command view no longer pins an old model.
- **Mocked local:** account-error and task-model fixture tests succeeded on the
  physical test runner. Fixtures are not evidence of login or agent execution.
- **Real platform upload/device check:** the updated app was installed and
  launched on Riley's iPhone 13 Pro Max. `current-app.json` and
  `current-launch.json` identify the same `com.a2a.monitor` container.
- `api-login-ui-tests-v2.xcresult` reports 3 tests, 0 failures, 0 skips: two
  fixture tests and one real native-screen inspection with no credential entry.
  `screenshots-final/7F420E8D-5F1C-4BE2-B8F3-54478774A56B.png` is the phone screen.
- Earlier result bundles, including the test-target compile failure, are retained.

## Not yet demonstrated

No end-user login was attempted because this session prohibits entering passwords
or OAuth codes. The user's original rejection cause is therefore not confirmed.
User sign-in, phone-submitted task, execution by a local agent, HTML creation and
hosting on this server, and the response returned to the phone remain **not-run**.

## Latest handoff checks

- **Live deployment/Argo (read-only Keycloak check):** the account visible in the
  native form exists, is enabled, has verified email and a password credential,
  and has no required actions. The provisioner cannot read its login-error events.
  This does not establish that the password entered by the user was correct.
- **Real platform upload/device check:** the latest Xcode screen recheck exited
  70 during device preparation, before tests ran. Xcode requested an unlocked
  phone on the Mac's LAN or connected by cable. See `sign-in-state.xcresult`.
- Next: unlock/reconnect the phone, sign in manually using the test account's
  Vault-stored password, then resume authenticated phone-to-agent verification.

## Follow-up response-contract correction

- The audit found create-task and fetch-task decoders reversed. The client now
  reads `task` from the create response and decodes a bare task for retrieval.
- **Mocked local:** `TaskHTTPContractTests` runs the real client methods against
  `URLProtocol` fixtures for both endpoints and their HTTP 403 responses.
  `task-http-contract-tests.xcresult` reports 5 tests, 0 failures, 0 skips,
  on iOS Simulator 18.6 (four HTTP tests plus the original model test).
- **Static/local:** a signed iOS build with this final correction succeeded and
  `codesign --verify --deep --strict` exited 0. See `prepared-task-api-build.xcresult`.
  This correction is prepared on the Mac but is **not yet installed on the phone**.
- `device-readiness-after-fix.json` still records the phone unavailable; a direct
  lock-state query returned CoreDevice error 1000, device not found. Authentication,
  actual phone task submission, HTML hosting, and the phone response remain pending.