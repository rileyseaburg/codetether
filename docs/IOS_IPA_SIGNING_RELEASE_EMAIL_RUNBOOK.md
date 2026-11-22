# iOS IPA signing, NAS/HTTPS release, and email runbook

This is the handoff for another agent releasing **another app** using the same pattern as A2A Monitor. iOS uses **`.ipa`**, not `.ipk`. This procedure produces a device-scoped **Ad Hoc** build, not an App Store/TestFlight release.

## 1. Define the release before doing anything

Read the target repository's applicable `AGENTS.md`/overrides. Preserve unrelated edits and all failed-run evidence. Confirm that the user authorized signing, publication, the destination device(s), and the exact email recipient. Use existing authenticated `git`, Vault, SSH, and Cloudflare tooling; do not search the filesystem for tokens or inspect old agent sessions/memory.

Prepare a nonsecret release configuration with these values:

| Setting | A2A Monitor example | Required change for another app |
|---|---|---|
| App/scheme/project | `A2AMonitor`, `A2AMonitor.xcodeproj` | Actual app target, scheme and project/workspace |
| Repository sources | `ui/swift/A2AMonitor/` | Target app source directory |
| Bundle ID | `com.a2a.monitor` | Registered bundle ID; keep stable for an in-place update |
| Version/build | `1.0.0`, `5` | Set `CFBundleShortVersionString` and a new `CFBundleVersion` |
| Signing team | `J9YRM3U37D` | Authorized Apple team |
| Distribution identity | Fingerprint pinned by the signing helper | Pin the intended certificate fingerprint; never pick the first identity blindly |
| Vault certificate path | `secret/codetether/ios-signing/distribution-6JF3S3B8MP` | Approved certificate/private-key secret |
| Certificate fields | `certificate_base64`, `private_key_pem`, `certificate_id`, `team_id` | Map actual fields without printing values |
| Apple API key path | `secret/codetether/ios-api-key` | Approved App Store Connect API key if profile management is required |
| Signing Mac | SSH alias `mac` | Authorized reachable macOS/Xcode host |
| Mac working directory | `~/a2amonitor-login-20261005` | Dedicated directory for this app/release |
| Package cache | `<Mac working directory>/SourcePackages` | Cache that actually contains required binary XCFramework artifacts |
| Profile | Device-scoped `IOS_APP_ADHOC` | Correct app/team/certificate/devices/entitlements; unexpired |
| Device | Explicit registered UDID/CoreDevice ID | Obtain and verify the intended physical device; do not select by an ambiguous name |
| NAS path on Linux | `/mnt/nas/A2AMonitor/20261005/download` | Dedicated app/release directory |
| NAS path on Mac | `~/NAS/A2AMonitor/20261005/download` | Verify it maps to the same storage |
| HTTPS base | `https://server.codetether.run/downloads/a2amonitor/20261005/` | App-specific HTTPS path; do not overwrite another app's route |
| Gateway | Loopback-only port `18772`, `codetether-a2amonitor-download` | Unique port/service/allowlist for the other app |
| Tunnel | Existing `codetether-public-tunnel` | Reuse approved tunnel without replacing unrelated ingress rules |
| Email sender | `noreply@codetether.run` | SendGrid-verified sender authorized for this release |
| Email recipient | `riley@spotlessbinco.com` | Exact recipient requested by the user |
| SendGrid Vault path | `kv/spotlessbinco-api/sendgrid` / `SENDGRID_API_KEY` | Approved secret and field |
| Evidence directory | `artifacts/agent-workflow-validation/delivery-v5/` | Dedicated immutable/reviewable evidence directory |

**Important:** the existing build/sign/publish/install helpers are A2A Monitor implementations, not universally parameterized tools. Before adapting them, inspect and replace app name, bundle ID, team/fingerprint, profile UUID/path, Mac root, NAS root, public URL, service/port, device ID, proof schema and test gates. Some support `IOS_BUILD_NUMBER` and `WORKBENCH_PROOF_DIR`; that alone does not adapt them to another app.

## 2. Discover hosts and verify prerequisites

Use first-party `agent list`, and message a relevant authenticated peer when one exists. Do not scan ports or browse generic mDNS services to find a collaborator. For an already user-designated signing Mac, use its provisioned SSH access.

Read-only checks on that Mac:

```bash
xcodebuild -version
xcrun simctl list devices available --json
xcrun devicectl list devices --json-output evidence/devices.json
security find-identity -v -p codesigning
df -h "$HOME"
```

Use unique evidence names, not an existing result bundle. Check device identity against provisioning before an install. Never unlock a phone or enter the user's password, passcode or OAuth code.

## 3. Build a meaningful test gate

Run the target app's relevant unit/contract/UI tests, then any user-requested live integration test. Keep evidence levels distinct:

- **Static/local:** source/schema checks and signature/plist inspection.
- **Mocked local:** fixture-backed tests or rendered UI snapshots.
- **Focused CI-like:** actual test/build/signing commands and exit states.
- **Live deployment/Argo:** real services, task IDs, returned results and HTTP artifact availability.
- **Real platform upload:** actual physical-device install receipts (or a platform upload ID for an App Store upload). Installation alone is not proof of a signed-in workflow.

For A2A Monitor, the live test must select a model through the UI, submit real work, receive two successful replies, and verify worker-side model, workspace and conversation IDs. A different app needs its own acceptance criteria. Do not copy A2A test IDs or mark fixtures as live evidence.

The source used for tests and device build must match. Preserve source revision/dirty-state information or an input manifest, command line, `.xcresult`, logs, screenshots and task IDs. Re-run affected checks after app changes. Review screenshots: a green test can still miss a visible error.

## 4. Configure Xcode and build for the device

Update the app's Info.plist version/build. Resolve dependencies using the app's locked versions and a valid package cache. For an XcodeGen project, regenerate with the actual installed executable (on this Mac `/opt/homebrew/bin/xcodegen`).

Example structure, replacing all placeholders:

```bash
xcodebuild -project <App>.xcodeproj -scheme <App> \
  -destination 'platform=iOS Simulator,id=<actual-booted-UUID>' \
  -derivedDataPath build -clonedSourcePackagesDirPath <valid-cache> \
  -disableAutomaticPackageResolution -skipPackageUpdates \
  CODE_SIGNING_ALLOWED=NO PROVISIONING_PROFILE_SPECIFIER= \
  -resultBundlePath evidence/<unique-test-run>.xcresult test

xcodebuild -project <App>.xcodeproj -scheme <App> \
  -configuration <tested-configuration> -destination 'generic/platform=iOS' \
  -derivedDataPath build -clonedSourcePackagesDirPath <valid-cache> \
  -disableAutomaticPackageResolution -skipPackageUpdates \
  CODE_SIGNING_ALLOWED=NO PROVISIONING_PROFILE_SPECIFIER= \
  -resultBundlePath evidence/<unique-device-build>.xcresult build
```

For workspace-based projects use `-workspace` instead. An unsigned device build is only an intermediate artifact, **not an installable release**. The A2A test distribution uses Debug; another app may require Release/archive. Do not switch configuration after testing without appropriate checks.

## 5. Obtain the correct profile and Vault signing material

Inspect `scripts/ios_ad_hoc_profile.cjs` for the reference App Store Connect flow. It signs an API JWT in memory, verifies the registered bundle and device, checks certificate expiry, and creates/reuses an `IOS_APP_ADHOC` profile. For another app:

1. Resolve its exact bundle identifier and authorized team.
2. Verify the intended device UDIDs are registered/enabled.
3. Select an unexpired distribution certificate whose private key is available.
4. Create or reuse a profile for **that bundle, certificate and devices**.
5. Check required entitlements (push, associated domains, keychain groups, extensions, etc.). Existing A2A entitlements must not be copied into another app.
6. Retain the public profile metadata; never put private signing keys in the NAS download directory.

Retrieve Vault material through a subprocess with captured output, e.g. the pattern in `scripts/release_ios_from_vault.cjs`. Parse it in memory and pass JSON to the signing helper over **SSH stdin**. Do not print Vault output, embed it in command arguments, commit it, or attach it to email. An App Store Connect `.p8` API key is **not** the app's distribution signing private key.

## 6. Use an isolated temporary signing keychain

Reference: `scripts/sign_ios_vault_on_mac.cjs`.

1. Validate expected team/fingerprint/expiry and that the certificate matches the private key.
2. Create a private per-invocation directory under the dedicated Mac working directory, mode `0700`; key/P12 files must be `0600`.
3. Generate a random temporary keychain/P12 password. This is an automation secret, not the user's login password.
4. Convert the certificate and matching private key to PKCS#12. Supply the export password through stdin, not a literal command argument.
5. Create/unlock only the temporary keychain. `security -i` accepts commands on stdin: finish with EOF, **not `quit`** (macOS reports `quit` as unknown).
6. Add that keychain to the search list while preserving the existing entries.
7. Import the matching public Apple WWDR intermediate, verify it matches the certificate issuer/signature, then import the P12.
8. Set the key partition list for `apple-tool:`, `apple:` and `codesign:`. Send the generated password through the helper's private stdin; never log the command text.
9. Confirm the expected identity exists **in this temporary keychain**.
10. Sign with an explicit identity and `--keychain <temporary-keychain>`.
11. In `finally`, remove only this keychain from the current search list, delete it, and remove only this invocation's temporary private-key files. Preserve public logs/artifacts and failed packages.

Do not unlock or modify the user's login keychain as the default workaround. Do not use broad key access (`-A`) or trust overrides to conceal a signing error. `errSecInternalComponent` alone does not prove a bad password; examine identity, chain, search list and partition access. Capture only safe, stage-specific diagnostics.

## 7. Stage, sign and package the app

Reference: `scripts/package_ios_tested_app.sh`.

1. Use a fresh staging directory. Preserve any prior candidate rather than overwriting/deleting it.
2. Copy the correct device `.app` into `Payload/<App>.app` and verify its bundle ID/build.
3. Embed the matching `embedded.mobileprovision` and extract its entitlements.
4. Check Ad Hoc `get-task-allow=false`, team/application identifier, expiry, authorized devices and allowed entitlements.
5. Remove extended attributes from the **staged copy only** if needed.
6. Sign nested dylibs/frameworks inside-out, then the containing app with correct entitlements. Apps with extensions/watch apps need separate matching profiles/entitlements and signatures; the simple A2A packager does not handle these automatically.
7. Run `codesign --verify --deep --strict` and inspect signing identity/entitlements. Do not treat packaging success alone as signature proof.
8. Create the IPA with `Payload/` at the archive root, e.g. `ditto -c -k --norsrc --noextattr --keepParent <stage>/Payload <App-version-build>.ipa`.
9. Run `unzip -t`, compute SHA-256 and record byte size. Check the profile includes the intended phone.
10. Copy to the NAS release directory and compare the NAS hash with the signing Mac's hash.

Use immutable app/version/build filenames. An Ad Hoc IPA installs only on provisioned devices. NAS hosting does not remove Apple's signing requirements.

## 8. Publish a narrow HTTPS download route

Reference: `scripts/ios_download_server.cjs`, `scripts/publish_workbench_ios.cjs`, and the existing route-management pattern in `scripts/publish_ios_download.cjs`.

- Run a dedicated **loopback-bound**, GET/HEAD-only download server with an explicit file allowlist. Serve IPA as `application/octet-stream`, manifest as XML, HTML as UTF-8, and support HTTP byte ranges.
- Do not expose the NAS root, `.signing`, keychains, private keys, credentials, directory listings or arbitrary paths.
- Route only the app-specific path through the authorized Cloudflare Tunnel. Read current ingress config, preserve unrelated routes and final catch-all, and insert a narrow hostname/path rule before the catch-all.
- Use the repository-approved Cloudflare Vault credential only if a route change is necessary. Do not recreate the shared tunnel or replace its whole ingress configuration.
- Keep trusted HTTPS certificate verification enabled. Never use `curl -k` or disable Node TLS verification.
- Back up the existing landing page, manifest and public proof into evidence before updating them. Stage new files and rename them into place. Keep old versioned IPAs available if required for rollback.

Minimal OTA manifest structure (substitute the actual values):

```xml
<plist version="1.0"><dict><key>items</key><array><dict>
  <key>assets</key><array><dict>
    <key>kind</key><string>software-package</string>
    <key>url</key><string>https://host/downloads/app/App-version-build.ipa</string>
  </dict></array>
  <key>metadata</key><dict>
    <key>bundle-identifier</key><string>com.example.app</string>
    <key>bundle-version</key><string>BUILD</string>
    <key>kind</key><string>software</string>
    <key>title</key><string>App Name</string>
  </dict>
</dict></array></dict></plist>
```

The landing page's Install button uses `itms-services://?action=download-manifest&url=<URL-encoded HTTPS manifest URL>`. Include a direct IPA link, version/build, signing/install restrictions, hash and honest validation limits. Ask the user to open the page in Safari on the registered iPhone.

## 9. Verify the release from its public URL

Before email or any successful-release claim:

1. Fetch the landing page, manifest and public proof over trusted HTTPS; require HTTP 200 and correct app/build/URLs.
2. Download the **entire public IPA** and compare SHA-256 with the signed artifact and NAS copy.
3. Request `Range: bytes=0-3`; require 206 and matching bytes.
4. Request a non-allowlisted path such as `private-key.pem`; require 404.
5. Record gateway/tunnel identity, artifact URL/hash/size, signature result, test summary and timestamp. Do not label HTTP availability as physical-device installation.

The email helper below consumes `delivery-proof.json` fields: `url`, `ipaUrl`, `ipaSha256`, `build`, `signatureVerified`, `publicStatus:200`, and `tlsVerificationEnabled:true`. It also expects an Xcode-style test summary with `result:"Passed"`, a positive `passedTests`, and zero `failedTests`/`skippedTests`. Adapt these gates explicitly for another test system; do not invent successful results.

## 10. Install on the intended phone when reachable

Use CoreDevice JSON output, not table-text parsing, for automation. Inspect the exact paired device and existing bundle version. Download the verified IPA, extract it, re-check signature/bundle/build/profile, then install **without uninstalling**:

```bash
xcrun devicectl device install app --device <exact-device-id> <Payload/App.app> \
  --json-output evidence/install.json
xcrun devicectl device info apps --device <exact-device-id> --bundle-id <bundle-id> \
  --include-default-apps --json-output evidence/after.json
xcrun devicectl device process launch --device <exact-device-id> <bundle-id> \
  --json-output evidence/launch.json
```

Verify receipt outcomes, device/bundle/build and the running process. Do not assume data preservation merely from a successful install; state that no uninstall/reset was performed. If unavailable, retain the failure and deliver the HTTPS install link. A physical install/launch is not a signed-in, end-to-end functional test. Never enter device passcodes or user login credentials.

## 11. Email the verified release through SendGrid

Use `scripts/send_ipa_release_email.cjs` for another app as well. This helper is configuration-driven, unlike the older build-2-only `send_ios_build_email.cjs`.

1. Write a reviewed plaintext notes file with the install page, direct IPA URL, app/build, changes, evidence levels and remaining limitations.
2. Provide the current release proof and test-summary paths. Confirm the recipient and verified sender.
3. Optionally attach this `.md` runbook. Attach no IPA/private key/profile secrets or raw logs.
4. Preview first. The helper re-fetches the public manifest/page/proof and full IPA hash before reading the SendGrid key.
5. Inspect `email-draft.json`, then invoke once with `--send`. The credential is read from Vault in memory and used only in the HTTPS Authorization header.

```bash
node scripts/send_ipa_release_email.cjs \
  --proof artifacts/<release>/delivery-proof.json \
  --tests artifacts/<release>/test-summary.json \
  --notes artifacts/<release>/release-email.txt \
  --recipient recipient@example.com --app 'Another App' \
  --sender noreply@codetether.run \
  --vault-path kv/spotlessbinco-api/sendgrid \
  --attachment docs/IOS_IPA_SIGNING_RELEASE_EMAIL_RUNBOOK.md
# Inspect the draft, then repeat the same command with --send.
```

The recipient above is a placeholder; use only the user-authorized address. The sender must be verified in the chosen SendGrid account. Use the target organization's approved Vault path rather than assuming cross-project authority.

The helper writes an exclusive `email-attempt.json` before sending and records `email-receipt.json` with HTTP status and `x-message-id`. **202 means SendGrid accepted the message, not that it reached the inbox.** A timeout is ambiguous: preserve the attempt and investigate provider activity before retrying. Do not delete the guard files or automatically re-send; duplicate-send protection is deliberate.

## 12. Handoff and completion checklist

- [ ] App/build/profile/team/device and signing certificate agree.
- [ ] Current source and applicable tests/build have concrete results.
- [ ] Temporary signing secrets were removed; no secrets in source, logs, URLs or email.
- [ ] Signed IPA and immutable SHA-256 are retained on NAS.
- [ ] Public HTTPS manifest points to that exact IPA; full hash/range/allowlist checks recorded.
- [ ] Physical install and end-to-end login/task status are separately labeled, not inferred.
- [ ] SendGrid receipt records accepted/rejected/unknown; mailbox delivery is not fabricated.
- [ ] Failed candidates and diagnostics remain available; unrelated work is preserved.
- [ ] Release notes give the install URL, version/build, evidence path and concrete blockers.

For A2A Monitor build 5, the reference evidence is `artifacts/agent-workflow-validation/delivery-v5/`; the original stricter live simulator evidence is under `app-api-repair/live-ui-v11/`. Its last direct phone-install attempt found the phone unavailable. Do not reuse that old result as evidence for another app or a new build.