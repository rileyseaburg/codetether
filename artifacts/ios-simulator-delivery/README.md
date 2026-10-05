# A2A Monitor simulator proof, signed IPA, and email delivery

- **Focused CI-like / live backend:** the real native client running in iOS
  Simulator submitted task `b009806e-6184-4d5f-a5cb-2ca7ccf93214` to the local
  worker, polled its result, and checked the actual hosted HTML and process.
  Xcode reports 1 test passed, 0 failures, 0 skips in `xcode-summary.json` and
  `live-simulator-task-20261005.xcresult`.
- This was not a URLProtocol fixture. A temporary, allowlisted loopback bridge
  supplied existing service authentication outside the iOS process. No user
  credentials were entered and none were embedded in the app. The bridge and
  SSH forwarding were stopped when the test ended.
- **Static/local signing:** an Ad Hoc Apple Distribution profile for
  `com.a2a.monitor` includes Riley's registered iPhone. The tested device app
  was re-signed on the Mac; `codesign --verify --deep --strict` exited 0.
  Embedded `get-task-allow` is false. Version is 1.0.0, build 2.
- **Real platform upload/publication:** NAS artifact:
  `/mnt/nas/A2AMonitor/20261005/download/A2AMonitor-1.0.0-2.ipa`.
  HTTPS page: https://server.codetether.run/downloads/a2amonitor/20261005/
  `delivery-proof.json` records HTTP 200, range 206, rejected path 404, and
  IPA SHA-256 `4679f356dde97dbbfd82c5b64c68cd3911ad4431e497d7e2253767d449319109`.
- **Real platform upload/email submission:** SendGrid accepted the notification
  to the repository-configured `riley@spotlessbinco.com` with HTTP 202 and message
  ID `bzYP-ipSR9iNPCe_zBkLSw`. See `email-receipt.json`; the message text is in
  `email-draft.json`. It was sent only after both proof gates were satisfied.
- **Not-run:** mailbox delivery, user-password/Keycloak UI sign-in, and physical
  iPhone installation of this Ad Hoc package. No claim is made for those steps.
- Archive attempts that failed due to Mac disk exhaustion remain in the Mac/NAS
  evidence; no unrelated caches or user files were deleted to make the package.