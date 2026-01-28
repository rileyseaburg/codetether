#!/bin/bash
# OpenCode Installer Script
# Downloads and installs the latest OpenCode binary from GitHub Releases

set -e

REPO="rileyseaburg/A2A-Server-MCP"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
BINARY_NAME="opencode"

# Detect OS and architecture
detect_platform() {
    local os arch
    
    case "$(uname -s)" in
        Linux*)     os=linux;;
        Darwin*)    os=darwin;;
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
    if [[ "$(uname -s)" == "Linux" ]]; then
        grep -q 'avx2' /proc/cpuinfo 2>/dev/null && return 0 || return 1
    elif [[ "$(uname -s)" == "Darwin" ]]; then
        sysctl -a 2>/dev/null | grep -q 'AVX2' && return 0 || return 1
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
    local filename
    
    if [[ "$platform" == *"windows"* ]]; then
        filename="opencode-${version_num}-${platform}.zip"
    else
        filename="opencode-${version_num}-${platform}.tar.gz"
    fi
    
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
    if [[ "$filename" == *.zip ]]; then
        unzip -q "$filename"
        mv opencode.exe "${BINARY_NAME}"
    else
        tar -xzf "$filename"
    fi
    
    echo "🔧 Installing to ${INSTALL_DIR}..."
    if [[ -w "$INSTALL_DIR" ]]; then
        mv "${BINARY_NAME}" "${INSTALL_DIR}/"
        chmod +x "${INSTALL_DIR}/${BINARY_NAME}"
    else
        echo "   (requires sudo)"
        sudo mv "${BINARY_NAME}" "${INSTALL_DIR}/"
        sudo chmod +x "${INSTALL_DIR}/${BINARY_NAME}"
    fi
    
    cd - > /dev/null
    rm -rf "$tmp_dir"
    
    echo "✅ OpenCode ${version} installed successfully!"
    echo ""
    echo "Run 'opencode --version' to verify installation"
}

# Main
main() {
    echo "🚀 OpenCode Installer"
    echo "====================="
    echo ""
    
    # Check for required tools
    if ! command -v curl &> /dev/null; then
        echo "❌ curl is required but not installed"
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
    fi
}

# Allow version override
if [[ -n "$1" ]]; then
    version="opencode-v${1#opencode-v}"
    echo "📋 Using specified version: ${version}"
fi

main
