# Quick Deploy to acp.quantum-forge.net
# Run this after logging in to Docker and Helm registries

Write-Host "🚀 Quick Deploy to acp.quantum-forge.net" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "✗ Docker not found. Please install Docker." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker found" -ForegroundColor Green

# Check Helm
if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
    Write-Host "✗ Helm not found. Please install Helm 3.8+." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Helm found" -ForegroundColor Green

# Check kubectl
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host "✗ kubectl not found. Please install kubectl." -ForegroundColor Red
    exit 1
}
Write-Host "✓ kubectl found" -ForegroundColor Green

Write-Host ""
Write-Host "Login to registries:" -ForegroundColor Yellow
Write-Host "  docker login registry.quantum-forge.net"
Write-Host "  helm registry login registry.quantum-forge.net"
Write-Host ""

$continue = Read-Host "Have you logged in to both registries? (y/N)"
if ($continue -ne "y") {
    Write-Host "Please login first, then run this script again." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Starting deployment..." -ForegroundColor Cyan
Write-Host ""

# Run deployment
.\deploy-acp.ps1 -Version "v1.0.0" -Production

Write-Host ""
Write-Host "✅ Deployment initiated!" -ForegroundColor Green
Write-Host ""
Write-Host "Monitor deployment:" -ForegroundColor Cyan
Write-Host "  kubectl get pods -n a2a-system -w"
Write-Host ""
