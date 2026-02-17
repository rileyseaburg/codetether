# CodeTether Domain Unification Plan

## Overview
This plan outlines the strategy to unify three separate sites under the root domain `codetether.run` while maintaining their individual functionality and improving user experience.

## Current State
- **Marketing Site**: `marketing-site/` (Next.js) - Primary marketing and landing pages
- **Documentation Site**: `docs/` (MkDocs) - Technical documentation
- **API Site**: `agent/` (Next.js) - API reference and SDK documentation

## Unification Strategy
### Domain Structure
```
codetether.run          → Marketing site (primary landing)
docs.codetether.run     → Documentation site
api.codetether.run      → API reference site
```

### Redirect Strategy
- All sites redirect to their subdomain counterparts
- Clean URL structure maintained
- Permanent (301) redirects for SEO preservation

## Configuration Updates Completed

### 1. Marketing Site (Next.js)
- **File**: `marketing-site/next.config.js`
- **Changes**: Added redirect rules for `/docs` and `/api` paths
- **Redirects**:
  - `/docs` → `https://docs.codetether.run`
  - `/api` → `https://api.codetether.run`

### 2. Documentation Site (MkDocs)
- **File**: `docs/codetether-mkdocs.yml`
- **Changes**: Fixed YAML syntax and added redirect rules
- **Redirects**:
  - `/docs` → `https://docs.codetether.run`
  - `/api` → `https://api.codetether.run`

### 3. API Site (Next.js)
- **File**: `agent/packages/agent/next.config.js`
- **Changes**: Added redirect rules for root and `/docs` paths
- **Redirects**:
  - `/docs` → `https://docs.codetether.run`
  - `/` → `https://codetether.run`

## DNS Configuration (COMPLETED)

### Cloudflare DNS Records Created
| Record | Type | Content | Proxied |
|--------|------|---------|---------|
| `codetether.run` | A | 216.171.12.196 | Yes |
| `www.codetether.run` | CNAME | codetether.run | Yes |
| `docs.codetether.run` | CNAME | codetether.run | Yes |
| `api.codetether.run` | CNAME | codetether.run | Yes |

### Cloudflare Zone Info
- **Zone ID**: `5059c11395b9eb527438be98150fc321`
- **Nameservers**: `deb.ns.cloudflare.com`, `garret.ns.cloudflare.com`
- **SSL**: Automatic via Cloudflare (proxied traffic)

## Remaining Steps

### 1. Server Configuration
- Configure your server at `216.171.12.196` to handle traffic for `codetether.run` subdomains
- Set up virtual hosts or reverse proxy for each subdomain

### 2. Deployment
- Deploy updated Next.js configurations
- Deploy MkDocs documentation site
- Update any external links or references

### 3. Testing
- Test redirects from all sites
- Verify URL structure and SEO optimization
- Check cross-site navigation

## Benefits
- Unified brand identity under single domain
- Improved user experience with consistent navigation
- Better SEO through consolidated domain authority
- Easier maintenance and updates

## Timeline
1. DNS Configuration: Immediate
2. SSL Setup: 1-2 days
3. Testing: 1 day
4. Deployment: 1 day
5. Monitoring: Ongoing

## Risks & Mitigation
- **DNS Propagation Delay**: Plan for 24-48 hour propagation
- **Redirect Loops**: Thorough testing before deployment
- **SSL Issues**: Use Let's Encrypt or similar for automated renewal

## Success Criteria
- All redirects working correctly
- All sites accessible via their subdomains
- No broken links or navigation issues
- Improved user experience metrics

## Contact
- For DNS configuration: Infrastructure team
- For SSL setup: DevOps team
- For testing: QA team

---

*Last updated: December 10, 2025*
