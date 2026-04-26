#!/bin/bash
# Quick test script for MCP HTTP server

echo "====================================="
echo "A2A Server MCP Quick Test"
echo "====================================="
echo ""

# Start port-forwarding if in Kubernetes
if command -v kubectl &> /dev/null; then
    echo "Checking for Kubernetes deployment..."
    if kubectl get deployment a2a-server -n a2a-system &> /dev/null; then
        echo "✓ Found A2A server deployment in Kubernetes"
        echo "Starting port-forward..."
        kubectl port-forward -n a2a-system svc/a2a-server 8000:8000 9000:9000 &
        PF_PID=$!
        sleep 3
    fi
fi

# Test endpoints
echo ""
echo "Testing A2A Server endpoints..."
echo "-----------------------------------"

echo ""
echo "1. Health check:"
curl -s http://localhost:9000/ | python -m json.tool 2>/dev/null || echo "MCP server not responding"

echo ""
echo "2. List MCP tools:"
curl -s http://localhost:9000/mcp/v1/tools | python -m json.tool 2>/dev/null || echo "Failed to list tools"

echo ""
echo "3. Agent card (with MCP info):"
curl -s http://localhost:8000/.well-known/agent-card.json | python -m json.tool | grep -A5 '"mcp"' 2>/dev/null || echo "No MCP info in agent card"

echo ""
echo "4. Call calculator tool:"
curl -s -X POST http://localhost:9000/mcp/v1/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "calculator",
      "arguments": {
        "operation": "add",
        "a": 10,
        "b": 5
      }
    }
  }' | python -m json.tool 2>/dev/null || echo "Failed to call calculator"

echo ""
echo "====================================="
echo "Test complete!"
echo "====================================="

# Cleanup port-forward
if [ ! -z "$PF_PID" ]; then
    echo "Stopping port-forward..."
    kill $PF_PID 2>/dev/null
fi
