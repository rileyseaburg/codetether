# SPIRE-native worker identity

Workers authenticate to the A2A server with short-lived SPIFFE JWT-SVIDs from
the cluster SPIRE deployment, not a shared `WORKER_AUTH_TOKEN`.

## Live SPIRE facts (verified against the cluster)

| Item | Value |
|---|---|
| Trust domain | `codetether.io` (spire-server `trust_domain`) |
| JWT issuer | `https://oidc-discovery.codetether.io` |
| Default JWT-SVID TTL | 1h |
| Workload registration | `spire-spire-default` ClusterSPIFFEID: `spiffe://codetether.io/ns/<ns>/sa/<sa>` for every pod outside `spire*` namespaces |
| Task Job worker identity | `spiffe://codetether.io/ns/a2a-system/sa/a2a-server-harvester` (10 live entries) |
| Workload API | SPIFFE CSI driver `csi.spiffe.io` on every node |
| JWKS | `spire-spiffe-oidc-discovery-provider.spire.svc.cluster.local/keys`, trust via `spire/spire-bundle` |

The server was configured with `SPIFFE_TRUST_DOMAIN=codetether.run`, so every
real SVID would have been rejected. `deploy/argocd/application.yaml` now uses
`codetether.io`.

## Flow

1. The task Job pod mounts the Workload API socket via the SPIFFE CSI driver.
2. A `spiffe-helper` native sidecar (init container, `restartPolicy: Always`)
   fetches a JWT-SVID with audience `a2a-server` and keeps
   `/svid/jwt_svid.token` (in-memory emptyDir) fresh before expiry.
3. `job_worker.py` sets `CODETETHER_SVID_PATH` instead of `CODETETHER_TOKEN`,
   waits for the first SVID, re-reads it on every request, and passes the
   current value to the worker process.
4. The server validates signature (SPIRE JWKS), `aud`, `iss`, `exp`, and trust
   domain, then requires the SPIFFE ID to be in `SPIFFE_WORKER_IDS`. Any other
   workload in the trust domain gets 403 on worker routes.

## Server settings

| Env | Meaning |
|---|---|
| `SPIFFE_TRUST_DOMAIN`, `SPIFFE_AUDIENCE` | Required; unset means SVIDs are rejected (503), never accepted |
| `SPIFFE_ISSUER` | Expected `iss` |
| `SPIFFE_WORKER_IDS` | Comma list of exact IDs or `prefix*` allowed on worker routes |
| `SPIFFE_ALLOW_TOKEN_LEGACY=false` | SPIRE-native: shared `WORKER_AUTH_TOKEN` and `A2A_AUTH_TOKENS` rejected |

## Rollout

1. Deploy with `allowTokenLegacy: true` (both paths accepted).
2. Confirm task Jobs authenticate with SVIDs (server logs show SPIFFE IDs).
3. Rust agent workers outside task Jobs must read the Workload API or an SVID
   file (codetether-agent owner; the server side is already in place).
4. Set `allowTokenLegacy: false` to remove shared secrets entirely.

## Verification

`scripts/spire_svid_check.py` validates a real SPIRE-minted SVID against the
live bundle using the server code. Result: `artifacts/ui-audit/spire-svid-check.txt`.
