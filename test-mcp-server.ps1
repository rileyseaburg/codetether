# Test MCP HTTP Server - PowerShell Version

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "A2A Server MCP Quick Test" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check if kubectl is available
$k8sDeployed = $false
if (Get-Command kubectl -ErrorAction SilentlyContinue) {
    Write-Host "Checking for Kubernetes deployment..." -ForegroundColor Yellow
    try {
        kubectl get deployment a2a-server -n a2a-system 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Found A2A server deployment in Kubernetes" -ForegroundColor Green
            Write-Host "Starting port-forward..." -ForegroundColor Yellow
            Start-Process kubectl -ArgumentList "port-forward -n a2a-system svc/a2a-server 8000:8000 9000:9000" -NoNewWindow
            Start-Sleep -Seconds 3
            $k8sDeployed = $true
        }
    } catch {}
}

# Test endpoints
Write-Host ""
Write-Host "Testing A2A Server endpoints..." -ForegroundColor Cyan
Write-Host "-----------------------------------" -ForegroundColor Cyan

Write-Host ""
Write-Host "1. Health check:" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:9000/" -Method Get
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "MCP server not responding: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "2. List MCP tools:" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:9000/mcp/v1/tools" -Method Get
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Failed to list tools: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "3. Agent card (with MCP info):" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/.well-known/agent-card.json" -Method Get
    if ($response.additional_interfaces.mcp) {
        Write-Host "MCP Interface found:" -ForegroundColor Green
        $response.additional_interfaces.mcp | ConvertTo-Json -Depth 10
    } else {
        Write-Host "No MCP interface in agent card" -ForegroundColor Red
    }
} catch {
    Write-Host "Failed to get agent card: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "4. Call calculator tool:" -ForegroundColor Yellow
try {
    $body = @{
        jsonrpc = "2.0"
        id = 1
        method = "tools/call"
        params = @{
            name = "calculator"
            arguments = @{
                operation = "add"
                a = 10
                b = 5
            }
        }
    } | ConvertTo-Json -Depth 10

    $response = Invoke-RestMethod -Uri "http://localhost:9000/mcp/v1/rpc" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
    
    $response | ConvertTo-Json -Depth 10
} catch {
    Write-Host "Failed to call calculator: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Test complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan

if ($k8sDeployed) {
    Write-Host ""
    Write-Host "Note: Port-forward is still running. Press Ctrl+C to stop it." -ForegroundColor Yellow
}
