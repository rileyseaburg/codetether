# A2A Monitor iOS installation — 2026-10-05

## Outcome

- **Static/local:** Xcode 16.4 built the native app, exit 0. See `same-session-build.xcresult`.
- **Static/local:** `codesign --verify --deep --strict --verbose=2` exited 0 and reported the app valid on disk.
- **Real platform upload (device installation):** `devicectl device install app` exited 0. See `install.json` and the subsequent independent listing in `installed-app.json`.
- **Real platform upload (launch check):** `devicectl device process launch` exited 0. `launch.json` records PID 27857 in the newly installed container.
- Login, backend connectivity, and voice functionality: **not-run**.

## Identities and artifacts

- Repository HEAD at staging: `336f5fd88707887c2747939438c48115350fa6cd`.
- Source: `ui/swift/A2AMonitor`; no application source edits.
- App: `com.a2a.monitor`, version `1.0.0`, build `1`.
- Device: `riley`, iPhone 13 Pro Max; CoreDevice ID `4745B27B-2B68-5164-A053-B869B07EE2CA`.
- Installed container: `7CA03B0A-76B4-4EBB-848B-483AF2A985CC`.
- Main executable SHA-256: `8ddd1cc9ccc2dd0d8baf540f65cff7d45b76b945945070cae5756f265bfcc535`.
- Signed Mac app: `/Users/rileyseaburg/a2amonitor-install-20261005-336f5fd/build/Build/Products/Debug-iphoneos/A2AMonitor.app`.
- Original Mac evidence: `/Users/rileyseaburg/a2amonitor-install-20261005-336f5fd/evidence/`.
- A post-build checksum-based `rsync -acin` comparison showed no input file differences between the repository app and staged Mac source (only root directory timestamp differed; generated project/build/evidence directories excluded).

## Recovery and scope

The first dependency download failed due to disk exhaustion. No caches or user files were deleted. A subsequent check found more free space; the successful build reused cached LiveKit 2.15.1 and its resolved dependencies, within the declared version range. The earlier generated lock is preserved in `resolved-before-cache-retry.json`.

Build-only overrides used automatic signing with the existing valid wildcard development profile instead of the expired source-configured `debug1`. Approved Vault credentials were piped directly into SSH without printing or saving them. Command-line signing access was configured only for the private key labeled `CodeTether iOS development`. The successful build unlocked the keychain and ran Xcode in the same SSH session.
