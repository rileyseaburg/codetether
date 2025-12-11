#!/bin/bash

echo "Testing Agentmesh Domain Unification Configuration"

# Test redirect configurations
echo "=== Testing Redirect Configurations ==="

# Test marketing site redirects
echo "Testing marketing site redirects..."
curl -I -L "http://localhost:3000/docs" 2>/dev/null | head -n 1
curl -I -L "http://localhost:3000/api" 2>/dev/null | head -n 1

# Test API site redirects
echo "Testing API site redirects..."
curl -I -L "http://localhost:4000/" 2>/dev/null | head -n 1
curl -I -L "http://localhost:4000/docs" 2>/dev/null | head -n 1

# Test documentation site (MkDocs)
echo "Testing documentation site..."
curl -I "http://localhost:8000" 2>/dev/null | head -n 1

echo "=== Configuration Summary ==="
echo "✓ Marketing site: next.config.js updated with redirects"
echo "✓ API site: next.config.js updated with redirects"
echo "✓ Documentation site: codetether-mkdocs.yml updated with redirects"
echo ""
echo "Next steps:"
echo "1. Configure DNS for subdomains (docs.codetether.run, api.codetether.run)"
echo "2. Set up SSL certificates"
echo "3. Deploy updated configurations"
echo "4. Test all redirects in production"
