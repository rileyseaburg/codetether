#!/bin/bash
# Run on the paired Mac. Installs the published IPA without uninstalling the app.
set -euo pipefail
device='00008110-001879C23E0A401E'
bundle='com.a2a.monitor'
build="${1:-4}"
expected_sha="${2:-94b7dbb8e62da9b252e51514748bf67dc1bb4284f16a2410921ba713abd13e72}"
[[ "$build" =~ ^[0-9]+$ && "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || exit 2
[[ "$build" == 4 || $# -ge 2 ]] || exit 2
filename="A2AMonitor-1.0.0-$build.ipa"
url="https://server.codetether.run/downloads/a2amonitor/20261005/$filename"
root="$HOME/a2amonitor-login-20261005/evidence/physical-install-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$root"
printf 'INSTALL_EVIDENCE=%s\n' "$root"
trap 'printf "Install step failed at line %s; retained evidence: %s\n" "$LINENO" "$root" >&2' ERR
xcrun devicectl device info details --device "$device" --quiet --timeout 30 --json-output "$root/device.json"
xcrun devicectl device info apps --device "$device" --bundle-id "$bundle" --include-default-apps \
  --timeout 30 --json-output "$root/before.json"
curl --proto '=https' --tlsv1.2 --fail --silent --show-error --max-time 120 \
  --dump-header "$root/download-headers.txt" --output "$root/$filename" \
  --write-out 'HTTPS download status=%{http_code} TLS verification=%{ssl_verify_result}\n' "$url"
actual_sha=$(shasum -a 256 "$root/$filename" | awk '{print $1}')
test "$actual_sha" = "$expected_sha"
printf '%s  %s\n' "$actual_sha" "$filename" > "$root/sha256.txt"
ditto -x -k "$root/$filename" "$root/extracted"
app="$root/extracted/Payload/A2AMonitor.app"
codesign --verify --deep --strict "$app"
test "$(plutil -extract CFBundleIdentifier raw "$app/Info.plist")" = "$bundle"
test "$(plutil -extract CFBundleVersion raw "$app/Info.plist")" = "$build"
security cms -D -i "$app/embedded.mobileprovision" -o "$root/profile.plist"
/usr/libexec/PlistBuddy -c 'Print :ProvisionedDevices' "$root/profile.plist" | grep -Fq "$device"
test "$(plutil -extract Entitlements.get-task-allow raw "$root/profile.plist")" = false
printf 'ARTIFACT_VERIFIED=build%s\n' "$build"
xcrun devicectl device install app --device "$device" "$app" --timeout 180 \
  --json-output "$root/install.json" --log-output "$root/install.log"
xcrun devicectl device info apps --device "$device" --bundle-id "$bundle" --include-default-apps \
  --timeout 30 --json-output "$root/after.json"
xcrun devicectl device process launch --device "$device" "$bundle" --timeout 30 \
  --json-output "$root/launch.json" --log-output "$root/launch.log"
printf 'INSTALL_AND_LAUNCH_COMMANDS_FINISHED=%s\n' "$root"