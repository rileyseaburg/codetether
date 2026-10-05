## Production UI release

- Simplifies workspace, task, session, and navigation layouts.
- Production image: `registry.quantum-forge.net/cluster-ci-cache/codetether-marketing:ui-a1d68a889bd3`.
- Image source: `a1d68a889bd3e752e5a00b6cfba90a0e9888c0c0`; GitOps promotion: `767a70bee083399b78a355292837e3a915580869`.
- Argo app `argocd/codetether-marketing`: Synced / Healthy.
- Real sign-in and dashboard/mobile smoke checks succeeded on codetether.run and quantum-forge.codetether.run.
- Fixes auth callback origin after ingress TLS termination and removes cross-host browser redirects that lose host-only session cookies.
- Build uses the same Next/React versions as the previously deployed runtime, deterministic dependencies, and runtime-only auth secrets.

Existing unrelated work was excluded using a separate Git index. Production is pinned to the tested source commit. The legacy GCP publishing workflow was not used (project billing disabled); this release uses the on-cluster Harbor registry.
