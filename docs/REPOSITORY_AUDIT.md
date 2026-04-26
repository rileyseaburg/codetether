# Repository Structure Audit

This audit describes the story the repository currently tells, what each top-level area appears to own, and which areas are not critical to the core CodeTether platform story.

## Big-picture story

The repository is a monorepo for a production AI-agent operations platform. The strongest story is:

1. **Control plane / API** — `a2a_server/`, `policies/`, `run_server.py`, `codetether/`.
2. **Execution plane** — `codetether-agent/` Rust worker submodule plus `agent_worker/` legacy/Python worker support.
3. **Product/UI plane** — `marketing-site/`, `ui/`, and docs sites.
4. **Deployment plane** — `chart/`, `docker/`, `Dockerfile`, `scripts/`, `.github/`.
5. **Protocol/integration plane** — `specification/`, `examples/`, `integrations/`, `zapier-app/`, `vscode-codetether-chat/`, `types/`.
6. **Governance/security plane** — `policies/`, `rfc/`, `SECURITY.md`, `GOVERNANCE.md`, APF provenance implementation.

That story is coherent, but the repository still mixes product code, generated outputs, experiments, built documentation, local caches, and historical artifacts in one checkout. A newcomer can tell CodeTether is broad, but not immediately what is essential vs. legacy/experimental/generated.

## Current top-level roles

| Path | Role it communicates | Criticality | Notes / recommendation |
| --- | --- | --- | --- |
| `a2a_server/` | Python FastAPI server/control plane | Critical | Core backend. Keep prominent. |
| `codetether-agent/` | Rust worker/agent runtime submodule | Critical | Core execution plane. README should call out it is a submodule. |
| `policies/` | OPA authorization + provenance policy | Critical | Strong enterprise/security story. Keep prominent. |
| `chart/` | Helm deployment assets | Critical for production | Contains a release package too; consider moving packaged chart under `artifacts/releases/` unless intentionally published from here. |
| `docker/` + root `Dockerfile` | Container build definitions | Critical | Cleaner after consolidation. Consider moving root `Dockerfile` to `docker/Dockerfile.api` later only if all build systems are updated. |
| `scripts/` | Operational/dev/test scripts | Important | Good home for scripts. Could split `scripts/deploy/`, `scripts/dev/`, `scripts/test/` over time. |
| `.github/` | CI/CD and repo automation | Critical | Keep. |
| `tests/` | Python/integration tests | Critical | Good. New `tests/integration/` helps. |
| `marketing-site/` | Next.js dashboard/marketing app | Product-critical but large | Name suggests marketing only, but README says dashboard lives here. Consider renaming long-term to `web/` or `dashboard/` if feasible. |
| `codetether/` | Python package/CLI wrapper | Critical packaging | Small but important. Keep root-visible. |
| `run_server.py` | Server entrypoint | Critical compatibility | Root is okay because Docker/Helm reference it. |
| `makefile` | Main developer command surface | Critical | Lowercase `makefile` is unusual; consider `Makefile` eventually. |
| `pyproject.toml`, `setup.py`, `requirements*.txt` | Python packaging/deps | Critical | Both `pyproject` and `setup.py` can be okay; eventually simplify to one packaging source if possible. |
| `README.md`, `DEVELOPMENT.md`, governance docs | Human onboarding | Critical | Keep root docs limited to canonical docs only. |
| `specification/` | Protocol definitions | Important | Strong protocol story. Keep. |
| `rfc/` | Agent Provenance Framework RFC | Important | Good location. Could expand to multiple RFCs. |
| `docs/` | General docs + archive | Important | Now includes archive; consider `docs/archive/root/README.md` index. |
| `codetether-docs/` | MkDocs source for public docs | Important, but overlaps `docs/` | Having both `docs/` and `codetether-docs/` is confusing. Decide which is canonical. |
| `codetether-site/` | Built static docs site | Generated, not critical source | Usually should not be tracked unless GitHub Pages requires it. Candidate for removal or separate deploy artifact. |
| `ui/` | Additional UI clients/templates | Secondary | Contains Swift app, monitor HTML, pocket template. Consider splitting to `clients/` or `apps/`. |
| `examples/` | Example clients/agents | Important for adoption | Keep. |
| `integrations/` | n8n integration | Important | Keep. |
| `zapier-app/` | Zapier integration | Important, but independent app | Consider under `integrations/zapier/` eventually. |
| `vscode-codetether-chat/` | VS Code extension | Secondary/experimental | Consider under `integrations/vscode/` or `apps/vscode-extension/`. |
| `types/` | TypeScript type package | Secondary/SDK | Consider `sdk/typescript/` if building an SDK story. |
| `agent_worker/` | Legacy/Python worker and systemd installer | Secondary/legacy | README says Rust worker is primary. Mark as legacy or move under `legacy/agent_worker/` if not active. |
| `codetether_voice_agent/` | Voice agent service | Secondary product module | Could live under `apps/voice-agent/` or `services/voice-agent/`. |
| `agents/` | Marketing coordinator agent | Secondary | Could be `examples/agents/` or `services/agents/` depending on production status. |
| `benchmarks/` | Benchmark task definitions | Secondary | Keep if active; otherwise `experiments/benchmarks/`. |
| `quantumhead/` | Experimental notebook/server | Non-critical/experimental | Candidate for `experiments/quantumhead/` or separate repo. |
| `artifacts/` | Archived releases/audio/misc/generated outputs | Non-critical source | Useful cleanup target, but should not grow indefinitely. Consider Git LFS or external storage for binaries/audio. |
| `deployment/archive/` | Historical manifests/scripts/kubeconfigs | Non-critical/archive | Kubeconfig files should be audited for secrets; archive is better than root but still sensitive if real. |
| `migrations/` | One SQL migration | Ambiguous | Most migrations are in `a2a_server/migrations/`; consolidate this into the canonical migrations folder if active. |
| `data/` | `.gitkeep` only | Placeholder | Fine, but runtime DBs/logs should remain ignored. |
| `assets/` | Mostly untracked media/assets | Ambiguous | Audit tracked need; likely product assets or generated video artifacts should be separated. |
| `.vscode/`, `.gemini/`, `.mkdocs/` | Tooling/editor config | Optional | Fine if intentionally shared. |
| `models.dev` | Submodule | Important for model catalog | Keep if active; document in README/DEVELOPMENT. |

## Things that are not critical to the core story

These do not appear essential to understanding or operating CodeTether's core platform:

- `quantumhead/` — experimental research/prototype area.
- `artifacts/audio/`, `artifacts/downloads/`, `artifacts/misc/` — generated/local artifacts, not source.
- `artifacts/releases/` — packaged outputs; useful for history but not source.
- `deployment/archive/` — historical deployment assets; not main deployment path.
- `codetether-site/` — built docs output; source seems to be `codetether-docs/` and/or `docs/`.
- `docs/archive/root/` — historical docs/reports; useful context, not onboarding path.
- `vscode-codetether-chat/`, `zapier-app/`, `integrations/n8n-*`, `types/` — integrations/SDKs that are valuable but peripheral to the core server/worker/policy story.
- `agent_worker/` — likely legacy now that Rust worker is primary.
- `benchmarks/` — useful validation material but not core runtime.
- `ui/pocket_template/`, standalone monitor HTML — secondary UI artifacts compared with `marketing-site/`.

## Main sources of confusion

1. **Docs split across three places**
   - `docs/` general docs and archive
   - `codetether-docs/` MkDocs source
   - `codetether-site/` built static site

   Recommendation: designate `codetether-docs/` as source and remove or externalize `codetether-site/` generated output, or merge `codetether-docs/` into `docs/`.

2. **App/service boundaries are flat**
   - `marketing-site/`, `codetether_voice_agent/`, `zapier-app/`, `vscode-codetether-chat/`, `quantumhead/`, `ui/` all sit at root.

   Recommendation: introduce `apps/` or `services/` over time:
   - `apps/web/` or `apps/dashboard/`
   - `apps/voice-agent/`
   - `apps/vscode-extension/`
   - `integrations/zapier/`
   - `experiments/quantumhead/`

3. **Legacy vs active worker story**
   - `codetether-agent/` is core Rust worker.
   - `agent_worker/` still exists and appears partly legacy.

   Recommendation: mark `agent_worker/README.md` with status or move to `legacy/` if it is no longer a first-class worker.

4. **Generated/binary outputs are tracked**
   - Release tarballs, audio, built site, screenshots/test-results.

   Recommendation: keep only reproducible source in git where possible. Store release/audio artifacts in GitHub Releases, object storage, or Git LFS.

5. **Root still has many operational entrypoints**
   - This is acceptable for monorepos, but root should only expose canonical entrypoints. Current remaining root files are mostly reasonable.

## Recommended target structure

A clearer long-term structure would be:

```text
.
├── README.md / DEVELOPMENT.md / SECURITY.md / GOVERNANCE.md
├── a2a_server/                 # Python API/control plane
├── codetether/                 # Python CLI/package
├── codetether-agent/           # Rust worker submodule
├── policies/                   # OPA/Rego policy engine
├── rfc/                        # Design/RFC documents
├── specification/              # Protocol definitions
├── tests/                      # Python/integration tests
├── apps/
│   ├── dashboard/              # current marketing-site if dashboard is primary
│   ├── voice-agent/            # current codetether_voice_agent
│   └── vscode-extension/       # current vscode-codetether-chat
├── integrations/
│   ├── n8n/
│   └── zapier/                 # current zapier-app
├── docs/                       # canonical docs source
├── examples/
├── deployment/
│   ├── helm/                   # current chart, if renamed later
│   └── archive/
├── docker/
├── scripts/
├── benchmarks/ or experiments/benchmarks/
├── experiments/quantumhead/
└── artifacts/                  # ideally ignored or Git LFS only
```

## Suggested next cleanup steps

Prioritized by value/risk:

1. **Add archive indexes**: create `docs/archive/root/README.md`, `deployment/archive/README.md`, and `artifacts/README.md` so archived files do not look like active source.
2. **Decide docs canonical source**: choose between `docs/` and `codetether-docs/`; document the decision in `README.md` and `DEVELOPMENT.md`.
3. **Move built docs output**: remove `codetether-site/` from source control if deployment no longer requires it, or document why it is tracked.
4. **Classify legacy worker**: add a status note to `agent_worker/` or move it under `legacy/`.
5. **Consolidate integrations**: move `zapier-app/` and `vscode-codetether-chat/` under `integrations/` or `apps/`.
6. **Move experiments**: move `quantumhead/` under `experiments/`.
7. **Consolidate migrations**: determine whether root `migrations/V007__tenant_email_settings.sql` belongs under `a2a_server/migrations/`.
8. **Audit tracked binaries/secrets**: especially archived kubeconfigs and release/audio artifacts.

## Current root after cleanup

The root now mostly contains acceptable canonical files: project README/governance, package configs, primary Dockerfile, Makefile, server entrypoint, and deployment worker entrypoint. The remaining clutter is less about individual root files and more about too many top-level product/experiment/generated directories.
