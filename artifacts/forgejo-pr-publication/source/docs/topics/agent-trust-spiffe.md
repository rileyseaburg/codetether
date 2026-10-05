# Agent Trust with SPIFFE / SPIRE

CodeTether Server can establish **cryptographic, short-lived, auto-rotating
identity** for agents and workers using
[SPIFFE](https://spiffe.io) (the standard) and
[SPIRE](https://spiffe.io/docs/latest/spire-about/) (the reference
implementation). This replaces long-lived shared bearer tokens with verifiable
**workload identity**, and feeds that identity directly into the existing
[OPA](https://www.openpolicyagent.org/) authorization layer.

!!! abstract "TL;DR"
    **SPIFFE = authentication** (who is calling), **OPA = authorization**
    (what they may do). A SPIFFE ID such as
    `spiffe://codetether.run/tenant/acme/agent/orchestrator` is validated from a
    JWT-SVID, then its path is mapped to a tenant and an RBAC role for policy
    evaluation.

## Why SPIFFE?

The default worker authentication uses static bearer tokens
(`A2A_AUTH_TOKENS`). Any holder of a token is trusted, tokens don't rotate, and
a leak grants full impersonation until the token is manually revoked.

SPIFFE/SPIRE addresses this directly:

- **No long-lived secrets** — SVIDs are short-lived (minutes) and rotated
    automatically by the SPIRE agent. A leaked credential is useless almost
    immediately.
- **Workload attestation** — SPIRE proves a caller's identity from its
    Kubernetes ServiceAccount, pod labels, or node, so a stolen credential
    can't be replayed from another pod.
- **Tenant isolation by construction** — the tenant is encoded in the SPIFFE
    path and enforced by OPA.
- **Federation** — trust domains can federate, so agents in separate clusters
    can trust each other without sharing secrets.

## SPIFFE IDs

A SPIFFE ID is a URI of the form `spiffe://<trust-domain>/<path>`. CodeTether
uses the path to encode tenant and role:

```
spiffe://codetether.run/tenant/acme/agent/marketing-orchestrator
spiffe://codetether.run/worker/persistent-pool
spiffe://codetether.run/server/a2a-mcp
```

| Path segment pattern | Extracted as |
|----------------------|--------------|
| `/tenant/<id>/...`   | `tenant` |
| `.../agent/<role>`, `.../worker/<role>`, `.../server/<role>` | `role` |

## How identity flows through the server

A worker presents a **JWT-SVID** as a standard bearer credential:

```http
Authorization: Bearer <jwt-svid>
```

The server then:

1. **Validates** the JWT-SVID against the SPIRE trust-domain JWKS (signature,
   expiry, audience, and trust domain).
2. **Parses** the SPIFFE ID from the `sub` claim into a tenant and a role.
3. **Maps** the SPIFFE identity into the `user` document consumed by OPA, with
   `auth_source` set to `spiffe`.
4. **Authorizes** the request through the same `authz` and `tenants` Rego
   policies used for all other callers.

```
SVID Bearer → verify_auth() → SpiffeIdentity (signature/aud/trust-domain verified)
            → to_policy_user() → enforce_policy() → authz.rego + tenants.rego
```

## Enabling SPIFFE

SPIFFE validation is **off by default**. Enable it with environment variables
(or the Helm `spiffe.*` values below).

| Variable | Default | Purpose |
|----------|---------|---------|
| `SPIFFE_ENABLED` | `false` | Turn on JWT-SVID validation |
| `SPIFFE_TRUST_DOMAIN` | _(empty)_ | Expected trust domain, e.g. `codetether.run` |
| `SPIFFE_AUDIENCE` | _(empty)_ | Expected SVID audience(s), comma-separated |
| `SPIFFE_JWKS_URL` | _(empty)_ | SPIRE OIDC discovery JWKS endpoint |
| `SPIFFE_JWKS_TTL` | `300` | JWKS cache TTL (seconds) |
| `SPIFFE_ALLOW_TOKEN_LEGACY` | `true` | Also accept `A2A_AUTH_TOKENS` during migration |
| `SPIFFE_ROLE_MAP` | _(empty)_ | `svid-role:rbac-role,...` mapping |
| `SPIFFE_DEFAULT_ROLE` | `a2a-agent` | RBAC role for unmapped SVID callers |

### Role mapping

The SPIFFE path role is mapped to an application RBAC role. By default every
SVID caller receives the `a2a-agent` service-account role. To grant specific
roles per agent:

```bash
# orchestrator SVIDs become "operator", reader SVIDs become "viewer"
SPIFFE_ROLE_MAP="orchestrator:operator,reader:viewer"
```

See the [OPA / Keycloak one-sheet](../OPA_KEYCLOAK_ONE_SHEET.md) for the full
role → permission mapping.

## Deploying with Helm

The chart ships a `spiffe` values block. Enabling it injects the `SPIFFE_*`
environment variables into the server deployments:

```yaml
spiffe:
  enabled: true
  trustDomain: "codetether.run"
  audience: "a2a-server"
  jwksUrl: "http://spire-oidc.spire.svc.cluster.local/keys"
  allowTokenLegacy: true        # keep legacy tokens working during cutover
  roleMap: "orchestrator:operator"
  defaultRole: "a2a-agent"
```

!!! warning "Running SPIRE"
    For **production**, install the upstream
    [`spiffe/spire-server`](https://artifacthub.io/packages/helm/spiffe/spire-server)
    and `spiffe/spire-agent` charts — these provide node attestation,
    persistent storage, the OIDC Discovery Provider, and registration tooling.

    The chart's optional `spiffe.server.enabled` flag renders a **minimal,
    single-replica SPIRE server for dev/test clusters only**. It is gated
    behind both `spiffe.enabled` and `spiffe.server.enabled` so it never ships
    by default.

## Registering workloads

With a SPIRE server running, register each agent/worker so SPIRE will issue it
an SVID. Registration ties a SPIFFE ID to an attestation selector (here, a
Kubernetes ServiceAccount):

```bash
# Register the persistent worker pool
spire-server entry create \
  -spiffeID spiffe://codetether.run/worker/persistent-pool \
  -parentID spiffe://codetether.run/spire/agent/k8s_psat/dev-cluster \
  -selector k8s:ns:default \
  -selector k8s:sa:a2a-worker

# Register a tenant-scoped agent
spire-server entry create \
  -spiffeID spiffe://codetether.run/tenant/acme/agent/orchestrator \
  -parentID spiffe://codetether.run/spire/agent/k8s_psat/dev-cluster \
  -selector k8s:ns:acme \
  -selector k8s:sa:orchestrator
```

A workload then fetches a JWT-SVID from its local SPIRE agent (for the server's
audience) and sends it as the `Authorization: Bearer` credential.

## Migrating off shared tokens

The migration is designed to be zero-downtime:

1. **Deploy SPIRE** and register workloads.
2. **Enable validation** with `SPIFFE_ENABLED=true` and
   `SPIFFE_ALLOW_TOKEN_LEGACY=true`. Both SVIDs and existing
   `A2A_AUTH_TOKENS` are accepted, so nothing breaks.
3. **Roll out SVID clients** — switch each worker to present a JWT-SVID.
4. **Retire shared tokens** by setting `SPIFFE_ALLOW_TOKEN_LEGACY=false` and
   removing `A2A_AUTH_TOKENS`. Only cryptographically verified SVIDs are now
   accepted.

## Related

- [Enterprise Features](enterprise-ready.md) — TLS, authentication, and
    authorization model.
- [OPA / Keycloak one-sheet](../OPA_KEYCLOAK_ONE_SHEET.md) — RBAC roles and
    permissions.
