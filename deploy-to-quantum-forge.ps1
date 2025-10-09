# Deploy A2A Server to Quantum Forge Registry
# This script builds, tags, and pushes the Docker image and Helm chart

param(
    [Parameter(Mandatory=$false)]
    [string]$Version = "latest",
    
    [Parameter(Mandatory=$false)]
    [string]$Registry = "registry.quantum-forge.net",
    
    [Parameter(Mandatory=$false)]
    [string]$Project = "library",
    
    [Parameter(Mandatory=$false)]
    [string]$ImageName = "a2a-server",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipDocker,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipHelm,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Color functions
function Write-Info { param($msg) Write-Host $msg -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Error { param($msg) Write-Host "✗ $msg" -ForegroundColor Red }
function Write-Warning { param($msg) Write-Host "⚠ $msg" -ForegroundColor Yellow }

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "   A2A Server - Quantum Forge Deployment" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$FullImageName = "$Registry/$Project/${ImageName}:$Version"
$ChartPath = "chart/a2a-server"
$ChartVersion = "0.1.0"

Write-Info "Configuration:"
Write-Host "  Registry:     $Registry"
Write-Host "  Project:      $Project"
Write-Host "  Image:        $FullImageName"
Write-Host "  Chart Path:   $ChartPath"
Write-Host "  Chart Version: $ChartVersion"
Write-Host ""

if ($DryRun) {
    Write-Warning "DRY RUN MODE - No actual push operations will be performed"
    Write-Host ""
}

# Step 1: Build Docker Image
if (-not $SkipDocker) {
    if (-not $SkipBuild) {
        Write-Info "Step 1: Building Docker image..."
        try {
            docker build -t a2a-server:$Version .
            if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }
            Write-Success "Docker image built successfully"
        }
        catch {
            Write-Error "Failed to build Docker image: $_"
            exit 1
        }
        Write-Host ""
    }

    # Step 2: Tag Docker Image
    Write-Info "Step 2: Tagging Docker image for Quantum Forge..."
    try {
        docker tag a2a-server:$Version $FullImageName
        if ($LASTEXITCODE -ne 0) { throw "Docker tag failed" }
        Write-Success "Image tagged as $FullImageName"
    }
    catch {
        Write-Error "Failed to tag Docker image: $_"
        exit 1
    }
    Write-Host ""

    # Step 3: Push Docker Image
    Write-Info "Step 3: Pushing Docker image to Quantum Forge..."
    if ($DryRun) {
        Write-Warning "Would execute: docker push $FullImageName"
    }
    else {
        try {
            Write-Host "Pushing to: $FullImageName" -ForegroundColor Yellow
            docker push $FullImageName
            if ($LASTEXITCODE -ne 0) { throw "Docker push failed" }
            Write-Success "Docker image pushed successfully"
        }
        catch {
            Write-Error "Failed to push Docker image: $_"
            Write-Warning "Make sure you're logged in: docker login $Registry"
            exit 1
        }
    }
    Write-Host ""
}

# Step 4: Package Helm Chart
if (-not $SkipHelm) {
    Write-Info "Step 4: Packaging Helm chart..."
    try {
        # Update chart values with Quantum Forge image
        $ValuesPath = "$ChartPath/values.yaml"
        if (Test-Path $ValuesPath) {
            Write-Info "Updating chart values with Quantum Forge image reference..."
            $content = Get-Content $ValuesPath -Raw
            $content = $content -replace 'repository:\s*a2a-server', "repository: $Registry/$Project/$ImageName"
            $content = $content -replace 'tag:\s*"latest"', "tag: `"$Version`""
            Set-Content $ValuesPath $content
            Write-Success "Chart values updated"
        }
        
        # Build dependencies
        Write-Info "Building chart dependencies..."
        Push-Location $ChartPath
        helm dependency build
        if ($LASTEXITCODE -ne 0) { throw "Helm dependency build failed" }
        Pop-Location
        
        # Package the chart
        helm package $ChartPath
        if ($LASTEXITCODE -ne 0) { throw "Helm package failed" }
        
        $ChartPackage = "a2a-server-$ChartVersion.tgz"
        Write-Success "Helm chart packaged: $ChartPackage"
    }
    catch {
        Write-Error "Failed to package Helm chart: $_"
        Pop-Location -ErrorAction SilentlyContinue
        exit 1
    }
    Write-Host ""

    # Step 5: Push Helm Chart
    Write-Info "Step 5: Pushing Helm chart to Quantum Forge..."
    if ($DryRun) {
        Write-Warning "Would execute: helm push $ChartPackage oci://$Registry/$Project"
    }
    else {
        try {
            $ChartPackage = "a2a-server-$ChartVersion.tgz"
            Write-Host "Pushing chart: $ChartPackage" -ForegroundColor Yellow
            Write-Host "To registry: oci://$Registry/$Project" -ForegroundColor Yellow
            
            helm push $ChartPackage oci://$Registry/$Project
            if ($LASTEXITCODE -ne 0) { throw "Helm push failed" }
            Write-Success "Helm chart pushed successfully"
            
            # Cleanup package
            if (Test-Path $ChartPackage) {
                Remove-Item $ChartPackage
                Write-Info "Cleaned up local chart package"
            }
        }
        catch {
            Write-Error "Failed to push Helm chart: $_"
            Write-Warning "Make sure you're logged in: helm registry login $Registry"
            exit 1
        }
    }
    Write-Host ""
}

# Summary
Write-Host "===============================================" -ForegroundColor Green
Write-Host "   Deployment Summary" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""

if (-not $SkipDocker) {
    Write-Success "Docker Image: $FullImageName"
}

if (-not $SkipHelm) {
    Write-Success "Helm Chart: oci://$Registry/$Project/a2a-server:$ChartVersion"
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Verify image: docker pull $FullImageName"
Write-Host "  2. Install chart: helm install a2a-server oci://$Registry/$Project/a2a-server --version $ChartVersion --namespace a2a-system --create-namespace"
Write-Host "  3. Check status: kubectl get pods -n a2a-system"
Write-Host ""

if ($DryRun) {
    Write-Warning "This was a DRY RUN - no changes were made"
}
