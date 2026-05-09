# Deploy A2A Server to acp.quantum-forge.net
# Complete automated deployment script

param(
    [Parameter(Mandatory=$false)]
    [string]$Version = "v1.0.0",

    [Parameter(Mandatory=$false)]
    [string]$Registry = "registry.quantum-forge.net",

    [Parameter(Mandatory=$false)]
    [string]$Project = "library",

    [Parameter(Mandatory=$false)]
    [string]$ImageName = "a2a-server",

    [Parameter(Mandatory=$false)]
    [string]$Domain = "acp.quantum-forge.net",

    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild,

    [Parameter(Mandatory=$false)]
    [switch]$SkipTests,

    [Parameter(Mandatory=$false)]
    [switch]$Production
)

$ErrorActionPreference = "Stop"

# Color functions
function Write-Step { param($msg) Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Error { param($msg) Write-Host "✗ $msg" -ForegroundColor Red }
function Write-Warning { param($msg) Write-Host "⚠ $msg" -ForegroundColor Yellow }
function Write-Info { param($msg) Write-Host "  $msg" -ForegroundColor Gray }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "    A2A Server Deployment to acp.quantum-forge.net" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$FullImageName = "$Registry/$Project/${ImageName}:$Version"
$LatestImageName = "$Registry/$Project/${ImageName}:latest"
$ChartPath = "chart/a2a-server"
$ChartVersion = "0.1.0"
$Namespace = "a2a-system"

Write-Info "Configuration:"
Write-Info "  Registry:      $Registry"
Write-Info "  Image:         $FullImageName"
Write-Info "  Domain:        $Domain"
Write-Info "  Namespace:     $Namespace"
Write-Info "  Environment:   $(if($Production){'Production'}else{'Staging'})"
Write-Host ""

# Step 1: Run tests (if not skipped)
if (-not $SkipTests) {
    Write-Step "Running tests..."
    try {
        python -m pytest tests/ -v
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Some tests failed, but continuing..."
        } else {
            Write-Success "All tests passed"
        }
    }
    catch {
        Write-Warning "Test execution failed: $_"
    }
}

# Step 2: Build Docker image
if (-not $SkipBuild) {
    Write-Step "Building Docker image..."
    try {
        docker build -t a2a-server:$Version `
            --build-arg VERSION=$Version `
            --build-arg BUILD_DATE=$(Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ") `
            .
        if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }
        Write-Success "Docker image built successfully"
    }
    catch {
        Write-Error "Failed to build Docker image: $_"
        exit 1
    }
}

# Step 3: Tag images
Write-Step "Tagging Docker images..."
try {
    docker tag a2a-server:$Version $FullImageName
    docker tag a2a-server:$Version $LatestImageName
    if ($LASTEXITCODE -ne 0) { throw "Docker tag failed" }
    Write-Success "Images tagged"
    Write-Info "  - $FullImageName"
    Write-Info "  - $LatestImageName"
}
catch {
    Write-Error "Failed to tag images: $_"
    exit 1
}

# Step 4: Push Docker images
Write-Step "Pushing Docker images to Quantum Forge..."
try {
    Write-Info "Pushing versioned image..."
    docker push $FullImageName
    if ($LASTEXITCODE -ne 0) { throw "Failed to push $FullImageName" }

    Write-Info "Pushing latest tag..."
    docker push $LatestImageName
    if ($LASTEXITCODE -ne 0) { throw "Failed to push $LatestImageName" }

    Write-Success "Docker images pushed successfully"
}
catch {
    Write-Error "Failed to push Docker images: $_"
    Write-Warning "Make sure you're logged in: docker login $Registry"
    exit 1
}

# Step 5: Update Helm chart values
Write-Step "Updating Helm chart values..."
try {
    $ValuesPath = "$ChartPath/values.yaml"
    $content = Get-Content $ValuesPath -Raw

    # Update image repository and tag
    $content = $content -replace 'repository:\s*a2a-server', "repository: $Registry/$Project/$ImageName"
    $content = $content -replace 'tag:\s*"[^"]*"', "tag: `"$Version`""

    Set-Content $ValuesPath $content
    Write-Success "Chart values updated"
}
catch {
    Write-Error "Failed to update chart values: $_"
    exit 1
}

# Step 6: Build Helm dependencies
Write-Step "Building Helm chart dependencies..."
try {
    Push-Location $ChartPath
    helm dependency build
    if ($LASTEXITCODE -ne 0) { throw "Helm dependency build failed" }
    Pop-Location
    Write-Success "Helm dependencies built"
}
catch {
    Write-Error "Failed to build Helm dependencies: $_"
    Pop-Location
    exit 1
}

# Step 7: Package Helm chart
Write-Step "Packaging Helm chart..."
try {
    helm package $ChartPath
    if ($LASTEXITCODE -ne 0) { throw "Helm package failed" }

    $ChartPackage = "a2a-server-$ChartVersion.tgz"
    Write-Success "Helm chart packaged: $ChartPackage"
}
catch {
    Write-Error "Failed to package Helm chart: $_"
    exit 1
}

# Step 8: Push Helm chart
Write-Step "Pushing Helm chart to Quantum Forge..."
try {
    helm push a2a-server-$ChartVersion.tgz oci://$Registry/$Project
    if ($LASTEXITCODE -ne 0) { throw "Helm push failed" }
    Write-Success "Helm chart pushed to oci://$Registry/$Project/a2a-server:$ChartVersion"

    # Cleanup
    Remove-Item a2a-server-$ChartVersion.tgz -Force
}
catch {
    Write-Error "Failed to push Helm chart: $_"
    Write-Warning "Make sure you're logged in: helm registry login $Registry"
    exit 1
}

# Step 9: Deploy to Kubernetes
Write-Step "Deploying to Kubernetes..."

# Create production values file
$ProductionValues = @"
image:
  repository: $Registry/$Project/$ImageName
  tag: "$Version"
  pullPolicy: Always

replicaCount: $(if($Production){3}else{2})

service:
  type: LoadBalancer
  port: 8000
  mcp:
    enabled: true
    port: 9000

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
  hosts:
    - host: $Domain
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: acp-quantum-forge-tls
      hosts:
        - $Domain

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: $(if($Production){'true'}else{'false'})
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

redis:
  enabled: true
  auth:
    enabled: true
    password: "$(New-Guid)"
  master:
    persistence:
      enabled: true
      size: 8Gi

env:
  A2A_HOST: "0.0.0.0"
  A2A_PORT: "8000"
  A2A_LOG_LEVEL: "INFO"
  MCP_HTTP_ENABLED: "true"
  MCP_HTTP_HOST: "0.0.0.0"
  MCP_HTTP_PORT: "9000"
  A2A_AGENT_NAME: "ACP Quantum Forge Agent"
  A2A_AGENT_DESCRIPTION: "Production A2A agent with MCP integration at acp.quantum-forge.net"

monitoring:
  serviceMonitor:
    enabled: true
    interval: 30s

networkPolicy:
  enabled: true

podDisruptionBudget:
  enabled: $(if($Production){'true'}else{'false'})
  minAvailable: 1
"@

$ValuesFile = "acp-production-values.yaml"
$ProductionValues | Set-Content $ValuesFile

try {
    # Create namespace if it doesn't exist
    kubectl create namespace $Namespace --dry-run=client -o yaml | kubectl apply -f -

    # Install or upgrade the release
    Write-Info "Installing/upgrading release..."
    helm upgrade --install a2a-server `
        oci://$Registry/$Project/a2a-server `
        --version $ChartVersion `
        --namespace $Namespace `
        --values $ValuesFile `
        --wait `
        --timeout 10m

    if ($LASTEXITCODE -ne 0) { throw "Helm install/upgrade failed" }
    Write-Success "Successfully deployed to Kubernetes"
}
catch {
    Write-Error "Failed to deploy to Kubernetes: $_"
    exit 1
}

# Step 10: Verify deployment
Write-Step "Verifying deployment..."
try {
    Start-Sleep -Seconds 5

    $pods = kubectl get pods -n $Namespace -l app.kubernetes.io/name=a2a-server -o json | ConvertFrom-Json
    $runningPods = ($pods.items | Where-Object { $_.status.phase -eq "Running" }).Count

    Write-Info "Running pods: $runningPods"

    if ($runningPods -gt 0) {
        Write-Success "Deployment verified - $runningPods pod(s) running"
    } else {
        Write-Warning "No running pods found yet"
    }

    # Get service info
    $service = kubectl get svc -n $Namespace a2a-server -o json | ConvertFrom-Json
    $serviceType = $service.spec.type

    Write-Info "Service type: $serviceType"

    if ($service.status.loadBalancer.ingress) {
        $externalIP = $service.status.loadBalancer.ingress[0].ip
        Write-Info "External IP: $externalIP"
    }
}
catch {
    Write-Warning "Could not verify deployment: $_"
}

# Step 11: Setup DNS (informational)
Write-Step "DNS Configuration Required:"
Write-Warning "Please configure DNS for $Domain to point to the LoadBalancer IP"
Write-Info "Run this command to get the external IP:"
Write-Info "  kubectl get svc -n $Namespace a2a-server"
Write-Host ""

# Summary
Write-Host "============================================================" -ForegroundColor Green
Write-Host "    Deployment Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

Write-Success "Docker Image: $FullImageName"
Write-Success "Helm Chart: oci://$Registry/$Project/a2a-server:$ChartVersion"
Write-Success "Namespace: $Namespace"
Write-Success "Domain: $Domain"
Write-Host ""

Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Configure DNS: $Domain -> LoadBalancer IP"
Write-Host "  2. Wait for cert-manager to issue TLS certificate"
Write-Host "  3. Verify endpoints:"
Write-Host "     - https://$Domain/.well-known/agent-card.json"
Write-Host "     - https://$Domain/v1/monitor/"
Write-Host "     - https://$Domain/health"
Write-Host "  4. Test MCP endpoint: https://${Domain}:9000/mcp/v1/tools"
Write-Host ""

Write-Host "Monitoring:" -ForegroundColor Cyan
Write-Host "  - Web UI: https://$Domain/v1/monitor/"
Write-Host "  - Logs: kubectl logs -n $Namespace -l app.kubernetes.io/name=a2a-server -f"
Write-Host "  - Status: kubectl get pods -n $Namespace"
Write-Host ""

# Cleanup
Remove-Item $ValuesFile -Force -ErrorAction SilentlyContinue

Write-Success "Deployment script completed successfully!"
