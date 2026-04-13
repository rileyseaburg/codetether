# Tenant Deployments

CodeTether supports two tenant-scoped deployment paths:

1. `dedicated-instance`
   Runs a dedicated A2A server for one tenant in its own Kubernetes namespace.
2. `workspace-vm`
   Provisions a tenant-owned VM-backed workspace on KubeVirt/Harvester for full repo execution.

Both paths are now exposed as tenant APIs instead of being split across signup and workspace registration internals.

## APIs

### Dedicated Tenant Instance

`POST /v1/tenants/{tenant_id}/deployments/dedicated-instance`

```json
{
  "tier": "enterprise"
}
```

Returns the namespace and URLs for the dedicated tenant deployment.

### VM Workspace Runtime

`POST /v1/tenants/{tenant_id}/deployments/workspace-vm`

```json
{
  "name": "marketing-site",
  "path": "/workspace/repos/marketing-site",
  "cpu_cores": 4,
  "memory": "16Gi",
  "disk_size": "80Gi"
}
```

Returns the workspace ID plus the VM identity, SSH host, and runtime status.

### Deployment Status

`GET /v1/tenants/{tenant_id}/deployments`

This returns both deployment surfaces for the tenant:

- `dedicated_instance`
- `workspace_vms`

## Auth and Isolation

- Caller must be a tenant admin or super-admin.
- Non-super-admin callers can only manage their own `tenant_id`.
- VM workspaces are persisted on the tenant’s workspace records.
- Dedicated instance metadata is persisted on the tenant record.

## Runtime Prerequisites

### Dedicated Instance

- `K8S_PROVISIONING_ENABLED=true`
- Helm or Kubernetes API access for tenant namespaces

### VM Workspace

- `VM_WORKSPACES_ENABLED=true`
- KubeVirt or Harvester-compatible CRDs installed
- VM workspace storage class configured

## Recommended Use

- Use `dedicated-instance` when a customer needs an isolated control plane.
- Use `workspace-vm` when a customer needs a full mutable runtime with repo-local tools, CI-like behavior, or long-lived filesystem state.
