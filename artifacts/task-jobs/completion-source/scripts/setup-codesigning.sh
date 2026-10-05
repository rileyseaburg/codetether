#!/bin/bash
# Setup code signing for CI builds
# Required secrets:
#   APPLE_CERTIFICATE_BASE64 - Base64 encoded .p12 certificate
#   APPLE_CERTIFICATE_PASSWORD - Password for the .p12 certificate
#   APPLE_PROVISIONING_PROFILE_BASE64 - Base64 encoded .mobileprovision file
#   KEYCHAIN_PASSWORD - Password for the temporary keychain

set -euo pipefail

# Variables
KEYCHAIN_NAME="build.keychain"
KEYCHAIN_PASSWORD="${KEYCHAIN_PASSWORD:-build}"

echo "🔐 Setting up code signing..."

# Create a temporary keychain
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME" || true
security set-keychain-settings -lut 21600 "$KEYCHAIN_NAME"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"

# Add keychain to search list
security list-keychains -d user -s "$KEYCHAIN_NAME" $(security list-keychains -d user | tr -d '"')

# Import certificate
if [ -n "${APPLE_CERTIFICATE_BASE64:-}" ]; then
    echo "📜 Importing certificate..."
    CERTIFICATE_PATH="$RUNNER_TEMP/certificate.p12"
    echo "$APPLE_CERTIFICATE_BASE64" | base64 --decode > "$CERTIFICATE_PATH"
    
    security import "$CERTIFICATE_PATH" \
        -k "$KEYCHAIN_NAME" \
        -P "${APPLE_CERTIFICATE_PASSWORD:-}" \
        -T /usr/bin/codesign \
        -T /usr/bin/security
    
    rm -f "$CERTIFICATE_PATH"
fi

# Set key partition list (required for codesign to access the key)
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_NAME"

# Install provisioning profile
if [ -n "${APPLE_PROVISIONING_PROFILE_BASE64:-}" ]; then
    echo "📋 Installing provisioning profile..."
    PROFILE_PATH="$RUNNER_TEMP/profile.mobileprovision"
    echo "$APPLE_PROVISIONING_PROFILE_BASE64" | base64 --decode > "$PROFILE_PATH"
    
    # Create provisioning profiles directory
    mkdir -p ~/Library/MobileDevice/Provisioning\ Profiles
    
    # Get UUID from profile and copy with that name
    PROFILE_UUID=$(/usr/libexec/PlistBuddy -c "Print UUID" /dev/stdin <<< $(/usr/bin/security cms -D -i "$PROFILE_PATH"))
    cp "$PROFILE_PATH" ~/Library/MobileDevice/Provisioning\ Profiles/"$PROFILE_UUID".mobileprovision
    
    rm -f "$PROFILE_PATH"
fi

echo "✅ Code signing setup complete!"

# List available signing identities
echo "📝 Available signing identities:"
security find-identity -v -p codesigning "$KEYCHAIN_NAME"
