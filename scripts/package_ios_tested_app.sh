#!/bin/bash
set -euo pipefail
trap 'printf "Packaging failed at line %s\n" "$LINENO" >&2' ERR
# Use an unlocked signing keychain, or the isolated Vault signing runner.
build="${1:-2}"
[[ "$build" =~ ^[0-9]+$ ]] || exit 2
source_app="$HOME/a2amonitor-login-20261005/build/Build/Products/Debug-iphoneos/A2AMonitor.app"
profile="$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles/f1c447de-6f2f-4a45-aed1-7f72b474692e.mobileprovision"
output="$HOME/a2amonitor-login-20261005/adhoc-stage-$build"
download="$HOME/NAS/A2AMonitor/20261005/download"
identity="9113C278A8C8873BEBDB3BBFE807011FF1734C75"
test -d "$source_app"
test -f "$profile"
test ! -e "$output/Payload/A2AMonitor.app"
signing_keychain=()
if [[ "${IOS_VAULT_SIGNING:-0}" == 1 ]]; then
  test -f "${IOS_SIGNING_KEYCHAIN:?Isolated signing keychain required}"
  test "${IOS_SIGNING_IDENTITY:?Signing identity required}" = "$identity"
  signing_keychain=(--keychain "$IOS_SIGNING_KEYCHAIN")
else
  codesign --verify --deep --strict "$source_app"
fi
mkdir -p "$output/Payload" "$download"
cp -cR "$source_app" "$output/Payload/A2AMonitor.app"
app="$output/Payload/A2AMonitor.app"
plutil -replace CFBundleVersion -string "$build" "$app/Info.plist"
cp "$profile" "$app/embedded.mobileprovision"
xattr -cr "$app"
security cms -D -i "$profile" -o "$output/profile.plist"
plutil -extract Entitlements xml1 -o "$output/entitlements.plist" "$output/profile.plist"
test "$(plutil -extract Entitlements.get-task-allow raw "$output/profile.plist")" = false
# Sign inner code before its containing bundle. No private keys are exported.
while IFS= read -r -d '' item; do
  codesign --force --sign "$identity" "${signing_keychain[@]}" --timestamp=none "$item"
done < <(find "$app" -type f -name '*.dylib' -print0)
while IFS= read -r -d '' item; do
  codesign --force --sign "$identity" "${signing_keychain[@]}" --timestamp=none "$item"
done < <(find "$app" -depth -type d -name '*.framework' -print0)
codesign --force --sign "$identity" "${signing_keychain[@]}" --timestamp=none --entitlements "$output/entitlements.plist" "$app"
codesign --verify --deep --strict --verbose=2 "$app"
ditto -c -k --norsrc --noextattr --keepParent "$output/Payload" "$download/A2AMonitor-1.0.0-$build.ipa"
unzip -t "$download/A2AMonitor-1.0.0-$build.ipa" | tail -1
shasum -a 256 "$download/A2AMonitor-1.0.0-$build.ipa"
plutil -extract CFBundleIdentifier raw "$app/Info.plist"
plutil -extract CFBundleVersion raw "$app/Info.plist"