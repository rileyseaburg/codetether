# CodeTether Tenant Helm Chart

This Helm chart provisions a dedicated A2A server instance for a CodeTether tenant.

## Overview

Each tenant gets:
- A dedicated Kubernetes namespace (`tenant-{orgSlug}`)
- A Deployment running their A2A server instance
- A Service for internal routing
- An Ingress for external access via subdomain (`{orgSlug}.codetether.run`)
- Automatic TLS certificate provisioning via cert-manager
- Image pull secrets copied from the main namespace

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- cert-manager installed with a `cloudflare-issuer` ClusterIssuer
- nginx-ingress controller
- `gcr-pull-secret` in the `a2a-server` namespace

## Installation

### Quick Install

```bash
helm install riley-tenant ./chart/codetether-tenant \
  --set tenant.id=4f5d33d4-9ce1-4deb-8087-95546c6d91f7 \
  --set tenant.orgSlug=riley-041b27 \
  --set tenant.userId=user-123
```

### Install with Custom Values

```bash
helm install my-tenant ./chart/codetether-tenant \
  -f my-values.yaml
```

Example `my-values.yaml`:

```yaml
tenant:
  id: "4f5d33d4-9ce1-4deb-8087-95546c6d91f7"
  orgSlug: "riley-041b27"
  userId: "user-123"

tier: pro  # free, pro, agency, enterprise

image:
  tag: "v1.2.0"
```

## Configuration

### Required Values

| Parameter | Description | Example |
|-----------|-------------|---------|
| `tenant.id` | Tenant UUID | `4f5d33d4-9ce1-4deb-8087-95546c6d91f7` |
| `tenant.orgSlug` | Organization slug (used in namespace and hostname) | `riley-041b27` |

### Optional Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `tenant.userId` | User ID who owns this tenant | `""` |
| `tier` | Subscription tier (affects resources) | `free` |
| `image.repository` | Docker image repository | `us-central1-docker.pkg.dev/spotlessbinco/codetether/a2a-server-mcp` |
| `image.tag` | Docker image tag | `latest` |
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.baseDomain` | Base domain for tenant subdomains | `codetether.run` |

### Tier-Based Resources

Resources are automatically configured based on the `tier` value:

| Tier | CPU Request | CPU Limit | Memory Request | Memory Limit | Replicas |
|------|-------------|-----------|----------------|--------------|----------|
| `free` | 50m | 200m | 64Mi | 256Mi | 1 |
| `pro` | 100m | 500m | 128Mi | 512Mi | 1 |
| `agency` | 250m | 1000m | 256Mi | 1Gi | 2 |
| `enterprise` | 500m | 2000m | 512Mi | 2Gi | 3 |

## Automatic Provisioning

This chart is designed to be deployed automatically by the CodeTether provisioning service when a new user signs up. The provisioning flow:

1. **User signs up** → Creates Keycloak realm
2. **Database tenant created** → Stores tenant metadata
3. **Cloudflare DNS** → Creates CNAME record and tunnel ingress
4. **Helm install** → Deploys this chart

### Programmatic Installation

```python
from a2a_server.k8s_provisioning import k8s_provisioning_service

result = await k8s_provisioning_service.provision_instance(
    user_id="user-123",
    tenant_id="4f5d33d4-...",
    org_slug="riley-041b27",
    tier="free",
)
```

## Upgrading

### Change Tier (Scale Up/Down)

```bash
helm upgrade riley-tenant ./chart/codetether-tenant \
  --set tenant.id=4f5d33d4-9ce1-4deb-8087-95546c6d91f7 \
  --set tenant.orgSlug=riley-041b27 \
  --set tier=pro
```

### Update Image

```bash
helm upgrade riley-tenant ./chart/codetether-tenant \
  --reuse-values \
  --set image.tag=v1.3.0
```

## Uninstalling

```bash
helm uninstall riley-tenant

# The namespace persists after uninstall, delete manually if needed:
kubectl delete namespace tenant-riley-041b27
```

## Troubleshooting

### Pod not starting

Check if image pull secret exists:

```bash
kubectl get secret gcr-pull-secret -n tenant-riley-041b27
```

If missing, copy from main namespace:

```bash
kubectl get secret gcr-pull-secret -n a2a-server -o yaml | \
  sed 's/namespace: a2a-server/namespace: tenant-riley-041b27/' | \
  kubectl apply -f -
```

### Ingress not working

1. Check certificate status:
   ```bash
   kubectl get certificate -n tenant-riley-041b27
   ```

2. Check ingress:
   ```bash
   kubectl describe ingress -n tenant-riley-041b27
   ```

3. Verify DNS record exists in Cloudflare for `{orgSlug}.codetether.run`

4. Verify Cloudflare Tunnel has an ingress rule for the hostname

### View Logs

```bash
kubectl logs -n tenant-riley-041b27 -l app=a2a-riley-041b27 -f
```

## Architecture

```
                                    ┌─────────────────────────────────────┐
                                    │         Cloudflare Tunnel           │
                                    │   dc7f7221-95ad-4cfb-b679-...       │
                                    └─────────────────┬───────────────────┘
                                                      │
                                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                            Kubernetes Cluster                               │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    Namespace: tenant-riley-041b27                    │  │
│  │                                                                      │  │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │  │
│  │  │   Ingress    │───▶│   Service    │───▶│     Deployment       │  │  │
│  │  │              │    │              │    │   a2a-riley-041b27   │  │  │
│  │  │ riley-041b27 │    │ :8000        │    │   replicas: 1        │  │  │
│  │  │ .codetether  │    │              │    │                      │  │  │
│  │  │ .run         │    │              │    │  ┌────────────────┐  │  │  │
│  │  │              │    │              │    │  │   Pod          │  │  │  │
│  │  │ TLS: ✓       │    │              │    │  │ a2a-server-mcp │  │  │  │
│  │  └──────────────┘    └──────────────┘    │  │ TENANT_ID=...  │  │  │  │
│  │                                          │  └────────────────┘  │  │  │
│  │                                          └──────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    Namespace: a2a-server (shared)                    │  │
│  │                                                                      │  │
│  │  ┌──────────────────┐    ┌──────────────────┐                       │  │
│  │  │  gcr-pull-secret │    │ codetether-db-   │                       │  │
│  │  │  (copied to      │    │ credentials      │                       │  │
│  │  │   tenant ns)     │    │ (shared DB)      │                       │  │
│  │  └──────────────────┘    └──────────────────┘                       │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

## Environment Variables

The following environment variables are set in the pod:

| Variable | Description | Source |
|----------|-------------|--------|
| `TENANT_ID` | Tenant UUID | `values.tenant.id` |
| `USER_ID` | User ID (optional) | `values.tenant.userId` |
| `A2A_HOST` | Bind host | `0.0.0.0` |
| `A2A_PORT` | Bind port | `8000` |
| `DATABASE_URL` | PostgreSQL connection string | Secret: `codetether-db-credentials` |

## Security

- Pods run as non-root user (UID 1000)
- TLS termination at ingress with auto-provisioned certificates
- Row-Level Security (RLS) enabled on database tables
- Each tenant isolated in its own namespace
