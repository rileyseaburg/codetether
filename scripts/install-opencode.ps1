# OpenCode Installer Script for Windows (PowerShell)
# Downloads and installs the latest OpenCode binary from GitHub Releases
#
# Install with:
#   Invoke-Expression (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-opencode.ps1" -UseBasicParsing).Content
#
# Or download and run:
#   curl -o install-opencode.ps1 https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-opencode.ps1
#   .\install-opencode.ps1
#
# Options:
#   -Version <string>   Install a specific version (e.g. "1.1.25" or "opencode-v1.1.25")

[CmdletBinding()]
param(
    [string]$Version
)

$ErrorActionPreference = "Stop"

$Repo       = "rileyseaburg/A2A-Server-MCP"
$BinaryName = "opencode.exe"
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "OpenCode" "bin" }

# ── Helpers ────────────────────────────────────────────────────────────────────

function Get-Platform {
    $os = "windows"

    # Use RuntimeInformation for accurate architecture detection
    $archInfo = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture
    $arch = switch ($archInfo) {
        ([System.Runtime.InteropServices.Architecture]::X64)   { "x64" }
        ([System.Runtime.InteropServices.Architecture]::Arm64) { "arm64" }
        ([System.Runtime.InteropServices.Architecture]::X86)   { "x64" }  # 32-bit PS on 64-bit OS
        default {
            Write-Host "error: Unsupported architecture: $archInfo" -ForegroundColor Red
            exit 1
        }
    }

    return "$os-$arch"
}

function Test-AVX2 {
    try {
        # Use Get-CimInstance (modern) with fallback to Get-WmiObject (legacy)
        $cpu = $null
        try {
            $cpu = Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop | Select-Object -First 1
        }
        catch {
            $cpu = Get-WmiObject -Class Win32_Processor | Select-Object -First 1
        }
        $cpuInfo = "$($cpu.Caption) $($cpu.Name)"
        return $cpuInfo -match "AVX2|Advanced Vector Extensions 2"
    }
    catch {
        # If we can't detect, assume AVX2 is available (most modern CPUs have it)
        return $true
    }
}

function Get-LatestVersion {
    try {
        $response = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers @{
            "Accept"     = "application/vnd.github+json"
            "User-Agent" = "OpenCode-Installer"
        }
        $tag = $response.tag_name
        if ($tag -match '^opencode-v') {
            return $tag
        }
    }
    catch {
        Write-Host "error: Failed to fetch latest version: $_" -ForegroundColor Red
    }
    return $null
}

function Add-ToUserPath {
    param([string]$Directory)
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($currentPath -split ";" | Where-Object { $_.TrimEnd('\') -eq $Directory.TrimEnd('\') }) {
        return $false  # already present
    }
    [Environment]::SetEnvironmentVariable("PATH", "$Directory;$currentPath", "User")
    # Also update the current session
    $env:PATH = "$Directory;$env:PATH"
    return $true
}

# ── Install ────────────────────────────────────────────────────────────────────

function Install-OpenCode {
    param(
        [string]$Platform,
        [string]$ReleaseTag
    )

    # Use baseline build if no AVX2 support (only for x64)
    if ($Platform -like "*x64*" -and -not (Test-AVX2)) {
        Write-Host "  info: No AVX2 support detected, using baseline build" -ForegroundColor Yellow
        $Platform = "$Platform-baseline"
    }

    $VersionNum  = $ReleaseTag -replace '^opencode-v', ''
    $Filename    = "opencode-$VersionNum-$Platform.zip"
    $DownloadUrl = "https://github.com/$Repo/releases/download/$ReleaseTag/$Filename"

    $TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "opencode-install-$([System.Guid]::NewGuid().ToString('N').Substring(0,8))"
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

    try {
        # Download
        Write-Host "  Downloading OpenCode $ReleaseTag for $Platform..." -ForegroundColor Cyan
        Write-Host "  URL: $DownloadUrl"

        $ProgressPreference = 'SilentlyContinue'
        try {
            Invoke-WebRequest -Uri $DownloadUrl -OutFile (Join-Path $TempDir $Filename) -UseBasicParsing
        }
        catch {
            Write-Host "error: Failed to download $Filename" -ForegroundColor Red
            Write-Host "  Check that the release exists at https://github.com/$Repo/releases" -ForegroundColor Yellow
            return
        }
        finally {
            $ProgressPreference = 'Continue'
        }

        # Extract
        Write-Host "  Extracting..." -ForegroundColor Cyan
        try {
            Expand-Archive -Path (Join-Path $TempDir $Filename) -DestinationPath $TempDir -Force
        }
        catch {
            Write-Host "error: Failed to extract archive: $_" -ForegroundColor Red
            return
        }

        # Find the binary
        $sourcePath = Join-Path $TempDir "opencode.exe"
        if (-not (Test-Path $sourcePath)) {
            $sourcePath = Get-ChildItem -Path $TempDir -Recurse -Filter "opencode.exe" |
                          Select-Object -First 1 -ExpandProperty FullName
            if (-not $sourcePath) {
                Write-Host "error: Could not find opencode.exe in the extracted archive" -ForegroundColor Red
                return
            }
        }

        # Install
        Write-Host "  Installing to $InstallDir..." -ForegroundColor Cyan
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
        Copy-Item -Path $sourcePath -Destination (Join-Path $InstallDir $BinaryName) -Force

        Write-Host "  OpenCode $ReleaseTag installed successfully!" -ForegroundColor Green
    }
    finally {
        # Always clean up temp directory
        if (Test-Path $TempDir) {
            Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# ── Main ───────────────────────────────────────────────────────────────────────

function Main {
    Write-Host ""
    Write-Host "  OpenCode Installer" -ForegroundColor Cyan
    Write-Host ""

    # Detect platform
    $platform = Get-Platform
    Write-Host "  Detected platform: $platform"

    # Resolve version
    $releaseTag = $null
    if ($Version) {
        $releaseTag = "opencode-v" + ($Version -replace '^opencode-v', '')
        Write-Host "  Using specified version: $releaseTag"
    }
    else {
        Write-Host "  Fetching latest release..."
        $releaseTag = Get-LatestVersion
        if (-not $releaseTag) {
            Write-Host "error: Could not find latest OpenCode release" -ForegroundColor Red
            Write-Host "  Make sure a release with 'opencode-v' prefix exists"
            exit 1
        }
        Write-Host "  Latest version: $releaseTag"
    }
    Write-Host ""

    # Download and install
    Install-OpenCode -Platform $platform -ReleaseTag $releaseTag

    # Verify installation
    $opencodePath = Join-Path $InstallDir $BinaryName
    if (Test-Path $opencodePath) {
        Write-Host ""
        Write-Host "  Installed version:" -ForegroundColor Cyan
        & $opencodePath --version

        # Add to PATH
        $added = Add-ToUserPath -Directory $InstallDir
        if ($added) {
            Write-Host "  Added $InstallDir to your user PATH" -ForegroundColor Green
            Write-Host "  Restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
        }
        else {
            Write-Host "  $InstallDir is already in your PATH" -ForegroundColor Green
        }

        Write-Host ""
        Write-Host "  Get started:" -ForegroundColor White
        Write-Host "    opencode --version  " -ForegroundColor Cyan -NoNewline; Write-Host "— verify installation"
        Write-Host "    opencode --help     " -ForegroundColor Cyan -NoNewline; Write-Host "— see all commands"
        Write-Host ""
    }
    else {
        Write-Host ""
        Write-Host "  Installation verification failed" -ForegroundColor Yellow
    }
}

Main
