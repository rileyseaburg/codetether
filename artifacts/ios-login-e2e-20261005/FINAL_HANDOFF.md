# Current outcome and physical-phone handoff

The full phone-originated demonstration is **not complete**. The backend-only
rehearsal is successful and explicitly marked as such in its HTML and records.

## Achieved with concrete evidence

- **Live deployment/Argo:** Keycloak logs match the phone-displayed account's
  `invalid_user_credentials` errors. A separate enabled, verified synthetic user
  with editor permissions was created: `codetether-ios-e2e@example.invalid`.
  Its password remains only in Vault: `secret/codetether/ios-e2e-user`.
- **Static/local:** native login diagnostics, current workspace/task endpoints,
  task response decoding, explicit worker/model routing, and a Tasks & Responses
  screen were implemented. The response screen polls the exact created task ID.
- **Mocked local:** `final-task-model-tests.xcresult` records 6 tests, 0 failures,
  0 skips, including the real view-model/client with URLProtocol fixtures.
- **Static/local:** `final-task-model-device-build.xcresult` records the latest
  signed iOS build. Deep/strict codesign verification exited 0. Main executable
  SHA-256: `0b5e8ca16f3119eee4b518c4bc0d582795a58533d20f18932dd62f80fc6a1fe0`.
  The latest build is on the Mac, not yet installed on the unavailable phone.
- **Live deployment/Argo:** the real local worker ran the backend rehearsal and
  returned task `3df87692-22b0-4a17-8efe-18b37033fb75`. Its file, returned path/URL/
  hash, HTTP bytes, and running service all agree. See `backend-rehearsal/http-proof.json`.
  LAN URL: `http://192.168.50.101:8768/`; service:
  `codetether-ios-backend-rehearsal.service`; PID at verification: `893866`.
  Failed and unverified earlier attempts were retained, not counted as success.

## Remaining gate

`final-phone-readiness.json` records Riley's iPhone unavailable. The explicit
hardware-UDID lock query in `final-phone-lock.json` failed with CoreDevice error
1000, device not found. Manual credential entry is prohibited for this agent.

Reconnect/unlock the iPhone on the Mac's LAN or USB. Install the prepared app at
`~/a2amonitor-login-20261005/build/Build/Products/Debug-iphoneos/A2AMonitor.app`,
then have the user sign in. Follow `pending-phone-task.md` to submit a distinct
phone-originated task and verify its own file/URL/response; do not reuse the
backend rehearsal as phone proof.

The repaired worker's provider-read Vault token has a renewable 24-hour lease