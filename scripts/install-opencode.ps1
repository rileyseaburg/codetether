# OpenCode Installer Script for Windows (PowerShell)
# Downloads and installs the latest OpenCode binary from GitHub Releases
# 
# Install with:
#   Invoke-Expression (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-opencode.ps1" -UseBasicParsing).Content
#
# Or download and run:
#   curl -o install-opencode.ps1 https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-opencode.ps1
#   .\install-opencode.ps1

$ErrorActionPreference = "Stop"

$Repo = "rileyseaburg/A2A-Server-MCP"
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { "$env:USERPROFILE\.local\bin" }
$BinaryName = "opencode.exe"

# Detect OS and architecture
function Get-Platform {
    $os = "windows"
    
    # Use RuntimeInformation for accurate architecture detection
    $archInfo = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture
    $arch = switch ($archInfo) {
        ([System.Runtime.InteropServices.Architecture]::X64) { "x64" }
        ([System.Runtime.InteropServices.Architecture]::Arm64) { "arm64" }
        ([System.Runtime.InteropServices.Architecture]::X86) { "x86" }
        default { 
            Write-Host "❌ Unsupported architecture: $archInfo" -ForegroundColor Red
            exit 1
        }
    }
    
    return "$os-$arch"
}

# Check for AVX2 support (for baseline builds)
function Test-AVX2 {
    try {
        $cpu = Get-WmiObject -Class Win32_Processor | Select-Object -First 1
        # Check CPU features - AVX2 is indicated in various ways depending on Windows version
        $cpuInfo = $cpu.Caption + " " + $cpu.Name
        return $cpuInfo -match "AVX2|Advanced Vector Extensions 2"
    } catch {
        # If we can't detect, assume AVX2 is available (most modern CPUs have it)
        return $true
    }
}

# Get the latest release version
function Get-LatestVersion {
    try {
        $response = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers @{
            "Accept" = "application/vnd.github.v3+json"
            "User-Agent" = "OpenCode-Installer"
        }
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
    
    # Use baseline build if no AVX2 support (only for x64)
    if ($Platform -like "*x64*" -and -not (Test-AVX2)) {
        Write-Host "ℹ️  No AVX2 support detected, using baseline build" -ForegroundColor Yellow
        $Platform = "$Platform-baseline"
    }
    
    $VersionNum = $Version -replace '^opencode-v', ''
    $Filename = "opencode-$VersionNum-$Platform.zip"
    $DownloadUrl = "https://github.com/$Repo/releases/download/$Version/$Filename"
    $TempDir = Join-Path $env:TEMP ([System.Guid]::NewGuid().ToString())
    
    Write-Host "📥 Downloading OpenCode $Version for $Platform..." -ForegroundColor Cyan
    Write-Host "   URL: $DownloadUrl"
    
    try {
        New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
        
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $DownloadUrl -OutFile "$TempDir\$Filename" -UseBasicParsing
        $ProgressPreference = 'Continue'
    } catch {
        Write-Host "❌ Failed to download $Filename" -ForegroundColor Red
        Write-Host "   Check that the release exists at https://github.com/$Repo/releases" -ForegroundColor Yellow
        Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
        exit 1
    }
    
    Write-Host "📦 Extracting..." -ForegroundColor Cyan
    try {
        Expand-Archive -Path "$TempDir\$Filename" -DestinationPath $TempDir -Force
    } catch {
        Write-Host "❌ Failed to extract archive: $_" -ForegroundColor Red
        Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
        exit 1
    }
    
    Write-Host "🔧 Installing to $InstallDir..." -ForegroundColor Cyan
    try {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
        
        $sourcePath = Join-Path $TempDir "opencode.exe"
        if (-not (Test-Path $sourcePath)) {
            # Try to find opencode.exe in subdirectories
            $sourcePath = Get-ChildItem -Path $TempDir -Recurse -Filter "opencode.exe" | Select-Object -First 1 -ExpandProperty FullName
            if (-not $sourcePath) {
                throw "Could not find opencode.exe in the extracted archive"
            }
        }
        
        Move-Item -Path $sourcePath -Destination "$InstallDir\$BinaryName" -Force
    } catch {
        Write-Host "❌ Failed to install: $_" -ForegroundColor Red
        Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
        exit 1
    }
    
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
    
    Write-Host "✅ OpenCode $Version installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Run 'opencode --version' to verify installation"
}

# Main
function Main {
    Write-Host "🚀 OpenCode Installer" -ForegroundColor Cyan
    Write-Host "====================="
    Write-Host ""
    
    # Check for required tools
    try {
        $null = Invoke-RestMethod -Uri "https://github.com" -Method Head -TimeoutSec 5
    } catch {
        Write-Host "❌ Internet connection is required but not available" -ForegroundColor Red
        exit 1
    }
    
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
    $opencodePath = Join-Path $InstallDir $BinaryName
    if (Test-Path $opencodePath) {
        Write-Host ""
        Write-Host "📊 Installed version:"
        & $opencodePath --version
        
        # Check if install dir is in PATH
        $pathDirs = $env:Path -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        $inPath = $pathDirs -contains $InstallDir
        
        if (-not $inPath) {
            Write-Host ""
            Write-Host "⚠️  Note: $InstallDir is not in your PATH" -ForegroundColor Yellow
            Write-Host "   Add it to your PATH or use the full path: $opencodePath"
            Write-Host ""
            Write-Host "To add to your user PATH, run:" -ForegroundColor Cyan
            Write-Host "   [Environment]::SetEnvironmentVariable('Path', `$env:Path + ';$InstallDir', 'User')"
            Write-Host ""
            Write-Host "Then restart your PowerShell session."
        }
    } else {
        Write-Host ""
        Write-Host "⚠️  Installation verification failed" -ForegroundColor Yellow
    }
}

# Allow version override via parameter or argument
param(
    [string]$Version
)

if ($Version) {
    $script:version = "opencode-v" + ($Version -replace '^opencode-v', '')
    Write-Host "📋 Using specified version: $script:version"
} elseif ($args[0]) {
    $script:version = "opencode-v" + ($args[0] -replace '^opencode-v', '')
    Write-Host "📋 Using specified version: $script:version"
}

Main
