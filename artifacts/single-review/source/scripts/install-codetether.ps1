# CodeTether Installer Script for Windows (PowerShell)
# - Creates a venv under ~\.codetether\venv
# - Installs CodeTether (from PyPI if available, else from GitHub)
# - Adds codetether to PATH
#
# Install with:
#   Invoke-Expression (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-codetether.ps1" -UseBasicParsing).Content
#
# Or download and run:
#   curl -o install-codetether.ps1 https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-codetether.ps1
#   .\install-codetether.ps1
#
# For Linux/macOS, use install-codetether.sh instead:
#   curl -fsSL https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-codetether.sh | bash

param(
    [string]$Prefix,
    [string]$GitUrl,
    [string]$GitRef
)

$ErrorActionPreference = "Stop"

$App = "codetether"
$DefaultPrefix = Join-Path $env:USERPROFILE ".codetether"
$PrefixDir = if ($Prefix) { $Prefix } elseif ($env:CODETETHER_PREFIX) { $env:CODETETHER_PREFIX } else { $DefaultPrefix }
$VenvDir = Join-Path $PrefixDir "venv"
$BinDir = Join-Path $env:USERPROFILE ".local\bin"

function Log {
    param([string]$Message)
    Write-Host "[$App] $Message"
}

function Log-Error {
    param([string]$Message)
    Write-Host "[$App] $Message" -ForegroundColor Red
}

function Log-Warn {
    param([string]$Message)
    Write-Host "[$App] $Message" -ForegroundColor Yellow
}

function Log-Success {
    param([string]$Message)
    Write-Host "[$App] $Message" -ForegroundColor Green
}

# Check for Python 3
function Find-Python {
    # Try common Python 3 command names
    foreach ($cmd in @("python3", "python", "py")) {
        try {
            $output = & $cmd --version 2>&1
            if ($output -match "Python 3\.") {
                return $cmd
            }
        } catch {
            continue
        }
    }
    return $null
}

# Main installation logic
function Install-CodeTether {
    Write-Host ""
    Write-Host "🚀 CodeTether Installer (Windows)" -ForegroundColor Cyan
    Write-Host "===================================" -ForegroundColor Cyan
    Write-Host ""

    # Find Python 3
    $python = Find-Python
    if (-not $python) {
        Log-Error "Python 3 is required but not found."
        Log-Error "Install Python 3 from https://www.python.org/downloads/"
        Log-Error "Make sure to check 'Add Python to PATH' during installation."
        exit 1
    }
    Log "Found Python: $(& $python --version 2>&1)"

    # Create directories
    if (-not (Test-Path $PrefixDir)) {
        New-Item -ItemType Directory -Path $PrefixDir -Force | Out-Null
    }
    if (-not (Test-Path $BinDir)) {
        New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    }

    # Create virtual environment
    Log "Creating virtual environment at: $VenvDir"
    if (Test-Path $VenvDir) {
        Log "Removing existing venv..."
        Remove-Item -Recurse -Force $VenvDir
    }
    & $python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Log-Error "Failed to create virtual environment"
        exit 1
    }

    # Activate venv
    $venvPython = Join-Path $VenvDir "Scripts\python.exe"
    $venvPip = Join-Path $VenvDir "Scripts\pip.exe"

    if (-not (Test-Path $venvPython)) {
        Log-Error "Virtual environment creation failed — python.exe not found in $VenvDir\Scripts"
        exit 1
    }

    # Upgrade pip
    Log "Upgrading pip..."
    & $venvPython -m pip install --upgrade pip 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Log-Warn "pip upgrade failed, continuing with existing version..."
    }

    # Try PyPI first; fall back to GitHub source install
    Log "Installing CodeTether..."
    $pypiSuccess = $false
    try {
        & $venvPip install --upgrade codetether 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $pypiSuccess = $true
            Log "Installed CodeTether from PyPI"
        }
    } catch {
        # PyPI install failed, will try GitHub
    }

    if (-not $pypiSuccess) {
        $gitUrl = if ($GitUrl) { $GitUrl } elseif ($env:CODETETHER_GIT_URL) { $env:CODETETHER_GIT_URL } else { "https://github.com/rileyseaburg/codetether.git" }
        $gitRef = if ($GitRef) { $GitRef } elseif ($env:CODETETHER_GIT_REF) { $env:CODETETHER_GIT_REF } else { "main" }

        Log "PyPI install failed; installing from source: $gitUrl@$gitRef"

        # Check for git
        try {
            $null = & git --version 2>&1
        } catch {
            Log-Error "git is required for source installation but not found."
            Log-Error "Install git from https://git-scm.com/download/win"
            exit 1
        }

        & $venvPip install --upgrade "git+$gitUrl@$gitRef" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Log-Error "Failed to install CodeTether from source"
            exit 1
        }
        Log "Installed CodeTether from source"
    }

    # Create wrapper scripts in BinDir
    Log "Creating CLI wrappers in: $BinDir"

    $codetether_exe = Join-Path $VenvDir "Scripts\codetether.exe"
    $worker_exe = Join-Path $VenvDir "Scripts\codetether-worker.exe"

    # Create batch wrapper for codetether
    if (Test-Path $codetether_exe) {
        $wrapperBat = Join-Path $BinDir "codetether.bat"
        $wrapperPs1 = Join-Path $BinDir "codetether.ps1"

        # .bat wrapper (for cmd.exe)
        Set-Content -Path $wrapperBat -Value "@echo off`r`n`"$codetether_exe`" %*"

        # .ps1 wrapper (for PowerShell)
        Set-Content -Path $wrapperPs1 -Value "& `"$codetether_exe`" @args"

        Log "Created codetether wrappers"
    } else {
        Log-Warn "codetether.exe not found in venv — the package may not provide a CLI entry point"
    }

    # Create wrapper for codetether-worker (optional)
    if (Test-Path $worker_exe) {
        $workerBat = Join-Path $BinDir "codetether-worker.bat"
        $workerPs1 = Join-Path $BinDir "codetether-worker.ps1"

        Set-Content -Path $workerBat -Value "@echo off`r`n`"$worker_exe`" %*"
        Set-Content -Path $workerPs1 -Value "& `"$worker_exe`" @args"

        Log "Created codetether-worker wrappers"
    }

    # Success
    Write-Host ""
    Log-Success "Done! CodeTether installed successfully."
    Write-Host ""
    Log "Verify with:"
    Log "  codetether --version"
    Log "  codetether --help"

    # Check if BinDir is in PATH
    $pathDirs = $env:Path -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $inPath = $false
    foreach ($dir in $pathDirs) {
        if ($dir -eq $BinDir -or $dir.TrimEnd('\') -eq $BinDir.TrimEnd('\')) {
            $inPath = $true
            break
        }
    }

    if (-not $inPath) {
        Write-Host ""
        Log-Warn "NOTE: $BinDir is not on your PATH."
        Log-Warn "Add it by running:"
        Write-Host ""
        Write-Host "  [Environment]::SetEnvironmentVariable('Path', `$env:Path + ';$BinDir', 'User')" -ForegroundColor Cyan
        Write-Host ""
        Log-Warn "Then restart your PowerShell session."
    }
}

Install-CodeTether
