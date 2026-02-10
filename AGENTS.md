
---

## OPA Policy Engine

The project uses **Open Policy Agent (OPA)** as a centralized authorization engine across both the Python A2A server and the Rust CodeTether agent.

### Key Files

| Layer | File | Purpose |
|-------|------|---------|
| Rego policies | `policies/authz.rego` | RBAC permission checks |
| Rego policies | `policies/api_keys.rego` | API key scope enforcement |
| Rego policies | `policies/tenants.rego` | Tenant isolation |
| Static data | `policies/data.json` | Role→permission mappings |
| Python client | `a2a_server/policy.py` | OPA HTTP client + `require_permission()` dependency |
| Python middleware | `a2a_server/policy_middleware.py` | Centralized auth middleware (~160 route rules) |
| Rust client | `codetether-agent/src/server/policy.rs` | OPA HTTP client + local eval fallback |
| Rust middleware | `codetether-agent/src/server/mod.rs` | `POLICY_ROUTES` + `policy_middleware()` |
| Helm | `chart/a2a-server/templates/opa-configmap.yaml` | OPA sidecar ConfigMap |

### Testing

```bash
# Run all policy tests (Rego + Python + Rust)
make policy-test

# Individual test suites
opa test policies/ -v                    # 41 Rego tests
python -m pytest tests/test_policy.py     # 23 Python tests
python -m pytest tests/test_policy_middleware.py  # 83 middleware tests
cargo test policy                         # 9 Rust tests
```

### RBAC Roles

`admin` > `a2a-admin` > `operator` > `editor` > `viewer`

Permissions follow `resource:action` format (e.g., `task:read`, `agent:admin`). See `policies/data.json` for the full mapping.

---

## OpenCode Releases

OpenCode binaries are automatically built and published to **GitHub Releases** when you create a tag matching `opencode-v*` or `v*`.

### Release Process

**Automatic (GitHub Actions):**
```bash
# Trigger a release from the current version in package.json
make release-opencode

# Or manually create and push a tag
git tag opencode-v1.1.25
git push origin opencode-v1.1.25
```

The GitHub Actions workflow (`.github/workflows/release-opencode.yml`) will:
1. Build binaries for all 11 platforms (Linux, macOS, Windows - x64/ARM64/baseline/musl)
2. Package them as `.tar.gz` (Unix) or `.zip` (Windows)
3. Create a GitHub Release with all binaries attached

**Manual (Local Build):**
```bash
# Build locally and upload to GitHub release (requires gh CLI)
make release-opencode-local
```

### Available Platforms

| Platform | File | Notes |
|----------|------|-------|
| Linux x64 | `opencode-vX.X.X-linux-x64.tar.gz` | Standard glibc build |
| Linux x64 (baseline) | `opencode-vX.X.X-linux-x64-baseline.tar.gz` | For older CPUs without AVX2 |
| Linux x64 (musl) | `opencode-vX.X.X-linux-x64-musl.tar.gz` | For Alpine Linux |
| Linux ARM64 | `opencode-vX.X.X-linux-arm64.tar.gz` | ARM64 glibc |
| Linux ARM64 (musl) | `opencode-vX.X.X-linux-arm64-musl.tar.gz` | ARM64 musl |
| macOS x64 | `opencode-vX.X.X-darwin-x64.tar.gz` | Intel Macs |
| macOS x64 (baseline) | `opencode-vX.X.X-darwin-x64-baseline.tar.gz` | Intel Macs without AVX2 |
| macOS ARM64 | `opencode-vX.X.X-darwin-arm64.tar.gz` | Apple Silicon |
| Windows x64 | `opencode-vX.X.X-windows-x64.zip` | Standard build |
| Windows x64 (baseline) | `opencode-vX.X.X-windows-x64-baseline.zip` | For older CPUs |

### Installation for End Users

**One-line install script:**
```bash
curl -fsSL https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-opencode.sh | bash
```

**Manual download:**
1. Go to [GitHub Releases](https://github.com/rileyseaburg/A2A-Server-MCP/releases)
2. Download the appropriate binary for your platform
3. Extract and place in your PATH

### Release File Locations

- **Workflow:** `.github/workflows/release-opencode.yml`
- **Install Script:** `scripts/install-opencode.sh`
- **Makefile Targets:**
  - `build-opencode` - Build local binaries
  - `release-opencode` - Trigger GitHub Actions release
  - `release-opencode-local` - Build and upload locally

