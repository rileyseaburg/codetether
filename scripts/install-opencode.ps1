# OpenCode Installer Script for Windows (PowerShell)
# Downloads and installs the latest OpenCode binary from GitHub Releases

$ErrorActionPreference = "Stop"

$Repo = "rileyseaburg/codetether"
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { "$env:USERPROFILE\.local\bin" }
$BinaryName = "opencode.exe"

# Detect platform
function Get-Platform {
    $os = "windows"
    $arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }
    return "$os-$arch"
}

# Check for AVX2 support
function Test-AVX2 {
    try {
        $cpu = Get-WmiObject -Class Win32_Processor | Select-Object -First 1
        return $cpu.Caption -match "AVX2"
    } catch {
        return $false
    }
}

# Get latest release version
function Get-LatestVersion {
    try {
        $response = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
        $tag = $response.tag_name
        if ($tag -match '^opencode-v') {
            return $tag
        }
    } catch {
        Write-Host "❌ Failed to fetch latest version: $_" -ForegroundColor Red
    }
    return $null
}

# Download and install
function Install-OpenCode {
    param(
        [string]$Platform,
        [string]$Version
    )
    
    # Use baseline build if no AVX2 support
    if ($Platform -like "*x64*" -and -not (Test-AVX2)) {
        Write-Host "ℹ️  No AVX2 support detected, using baseline build" -ForegroundColor Yellow
        $Platform = "$Platform-baseline"
    }
    
    $VersionNum = $Version -replace '^opencode-v', ''
    $Filename = "opencode-$VersionNum-$Platform.zip"
    $DownloadUrl = "https://github.com/$Repo/releases/download/$Version/$Filename"
    $TempDir = [System.IO.Path]::GetTempPath() + [System.Guid]::NewGuid().ToString()
    
    Write-Host "📥 Downloading OpenCode $Version for $Platform..." -ForegroundColor Cyan
    Write-Host "   URL: $DownloadUrl"
    
    try {
        New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
        Invoke-WebRequest -Uri $DownloadUrl -OutFile "$TempDir\$Filename" -UseBasicParsing
    } catch {
        Write-Host "❌ Failed to download $Filename" -ForegroundColor Red
        Write-Host "   Check that the release exists at https://github.com/$Repo/releases"
        Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
        exit 1
    }
    
    Write-Host "📦 Extracting..." -ForegroundColor Cyan
    Expand-Archive -Path "$TempDir\$Filename" -DestinationPath $TempDir -Force
    
    Write-Host "🔧 Installing to $InstallDir..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Move-Item -Path "$TempDir\opencode.exe" -Destination "$InstallDir\$BinaryName" -Force
    
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
    
    Write-Host "✅ OpenCode $Version installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Run 'opencode --version' to verify installation"
}

# Main
function Main {
    Write-Host "🚀 OpenCode Installer for Windows" -ForegroundColor Cyan
    Write-Host "=================================="
    Write-Host ""
    
    # Detect platform
    $platform = Get-Platform
    Write-Host "🔍 Detected platform: $platform"
    
    # Get latest version
    $version = Get-LatestVersion
    if (-not $version) {
        Write-Host "❌ Could not find latest OpenCode release" -ForegroundColor Red
        Write-Host "   Make sure a release with 'opencode-v' prefix exists"
        exit 1
    }
    Write-Host "📋 Latest version: $version"
    Write-Host ""
    
    # Download and install
    Install-OpenCode -Platform $platform -Version $version
    
    # Verify installation
    if (Get-Command opencode -ErrorAction SilentlyContinue) {
        Write-Host ""
        Write-Host "📊 Installed version:"
        opencode --version
    } else {
        Write-Host ""
        Write-Host "⚠️  Note: $InstallDir may not be in your PATH" -ForegroundColor Yellow
        Write-Host "   Add it to your PATH or run: $InstallDir\opencode.exe"
        Write-Host ""
        Write-Host "To add to PATH, run:" -ForegroundColor Cyan
        Write-Host "[Environment]::SetEnvironmentVariable('Path', `$env:Path + ';$InstallDir', 'User')"
    }
}

# Allow version override
if ($args[0]) {
    $version = "opencode-v" + ($args[0] -replace '^opencode-v', '')
    Write-Host "📋 Using specified version: $version"
}

Main
