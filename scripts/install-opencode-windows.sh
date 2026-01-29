#!/bin/bash
# OpenCode Installer Script for Windows
# Downloads and installs the latest OpenCode binary from GitHub Releases

set -e

REPO="rileyseaburg/codetether"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
BINARY_NAME="opencode.exe"

# Detect OS and architecture
detect_platform() {
    local os arch
    
    case "$(uname -s)" in
        CYGWIN*|MINGW*|MSYS*) os=windows;;
        *)          echo "❌ Unsupported OS: $(uname -s)" && exit 1;;
    esac
    
    case "$(uname -m)" in
        x86_64|amd64)   arch=x64;;
        arm64|aarch64)  arch=arm64;;
        *)              echo "❌ Unsupported architecture: $(uname -m)" && exit 1;;
    esac
    
    echo "${os}-${arch}"
}

# Check for AVX2 support (for baseline builds)
has_avx2() {
    if command -v wmic &> /dev/null; then
        wmic cpu get Caption | grep -q "AVX2" && return 0 || return 1
    fi
    return 1
}

# Get the latest release version
get_latest_version() {
    curl -s "https://api.github.com/repos/${REPO}/releases/latest" | grep -o '"tag_name": "[^"]*' | grep -o '[^"]*$' | grep '^opencode-v' | head -1
}

# Download and install
download_and_install() {
    local platform="$1"
    local version="$2"
    
    # Use baseline build if no AVX2 support
    if [[ "$platform" == *"x64"* ]] && ! has_avx2; then
        echo "ℹ️  No AVX2 support detected, using baseline build"
        platform="${platform}-baseline"
    fi
    
    local version_num="${version#opencode-v}"
    local filename="opencode-${version_num}-${platform}.zip"
    
    local download_url="https://github.com/${REPO}/releases/download/${version}/${filename}"
    local tmp_dir=$(mktemp -d)
    
    echo "📥 Downloading OpenCode ${version} for ${platform}..."
    echo "   URL: ${download_url}"
    
    if ! curl -fsL -o "${tmp_dir}/${filename}" "$download_url"; then
        echo "❌ Failed to download ${filename}"
        echo "   Check that the release exists at https://github.com/${REPO}/releases"
        rm -rf "$tmp_dir"
        exit 1
    fi
    
    echo "📦 Extracting..."
    cd "$tmp_dir"
    unzip -q "$filename"
    
    echo "🔧 Installing to ${INSTALL_DIR}..."
    mkdir -p "$INSTALL_DIR"
    mv "opencode.exe" "${INSTALL_DIR}/"
    
    cd - > /dev/null
    rm -rf "$tmp_dir"
    
    echo "✅ OpenCode ${version} installed successfully!"
    echo ""
    echo "Run 'opencode --version' to verify installation"
}

# Main
main() {
    echo "🚀 OpenCode Installer for Windows"
    echo "=================================="
    echo ""
    
    # Check for required tools
    if ! command -v curl &> /dev/null; then
        echo "❌ curl is required but not installed"
        exit 1
    fi
    
    if ! command -v unzip &> /dev/null; then
        echo "❌ unzip is required but not installed"
        exit 1
    fi
    
    # Detect platform
    platform=$(detect_platform)
    echo "🔍 Detected platform: ${platform}"
    
    # Get latest version
    version=$(get_latest_version)
    if [[ -z "$version" ]]; then
        echo "❌ Could not find latest OpenCode release"
        echo "   Make sure a release with 'opencode-v' prefix exists"
        exit 1
    fi
    echo "📋 Latest version: ${version}"
    echo ""
    
    # Download and install
    download_and_install "$platform" "$version"
    
    # Verify installation
    if command -v opencode &> /dev/null; then
        echo ""
        echo "📊 Installed version:"
        opencode --version
    else
        echo ""
        echo "⚠️  Note: ${INSTALL_DIR} may not be in your PATH"
        echo "   Add it to your PATH or run: ${INSTALL_DIR}/opencode.exe"
    fi
}

# Allow version override
if [[ -n "$1" ]]; then
    version="opencode-v${1#opencode-v}"
    echo "📋 Using specified version: ${version}"
fi

main
