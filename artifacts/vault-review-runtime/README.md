# Forgejo review Vault access

## Actions and evidence

Evidence level: **live deployment/Argo** (direct Kubernetes/Vault observations;
no Argo reconciliation or Forgejo rerun claim).

- Namespace: `forgejo-actions`.
- Deployment: `forgejo-act-runner-dind`.
- Pods: `forgejo-act-runner-dind-7784886b55-ggvk4` and
  `forgejo-act-runner-dind-7784886b55-qp6nb`.
- Existing Kubernetes auth role: `forgejo-ci-runtime`, bound to service account
  `forgejo-vault-sync` in namespace `forgejo-actions`.
- Existing policies: `default`, `forgejo-ci-runtime`; not an admin/root token.
- Both existing tokens were explicitly renewed, returning a lease of 86400
  seconds and `renewable: true`. No additional static bearer token was issued.
- Both tokens could read nonempty reviewer credentials from
  `kv/forgejo/spotlessbinco-agent` and `kv/forgejo/codetether-bot`.
- Both tokens reported `deny` for `auth/token/create`.
- Both runner `/data/job-env` tokens matched their Vault Agent token sinks.
- Vault Agent logs on `ggvk4` showed Kubernetes authentication and renewal.

Command: `python3 artifacts/vault-review-runtime/verify-renewal.py`, exit 0.
Sanitized results: `renewal-evidence.json`. Neither tokens nor secret values
are written to these artifacts.

## Limits

Forgejo API reads timed out; the failed run's runner identity and a successful
PR review rerun are not established. No runners were restarted or jobs retried.
Automatic renewal extends the same token. Source inspection shows startup-only
copying into the job environment; propagation of a replacement token after
reauthentication remains a separate gap, not repaired or exercised here.