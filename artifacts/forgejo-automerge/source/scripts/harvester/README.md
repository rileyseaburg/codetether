# Harvester Forgejo review access

`forgejo-cli get /repos/riley/spotlessbinco/pulls/5901` authenticates internally.
No `--token`, copied Vault token, or token printed into a model transcript is
required. JSON and textual diff responses are supported.

The wrapper uses `VAULT_ADDR`, `VAULT_ROLE`, `VAULT_AUTH_MOUNT`, and
`VAULT_K8S_SA_JWT_PATH` from the harvester pod. Each invocation obtains fresh
Kubernetes authentication rather than using an expired shared CLI token.

The dedicated Vault record is `kv/codetether/harvester/forgejo-review` and contains
only `api_base`, `repo`, `username`, a repository-restricted token, its name,
and scopes. Scopes are `read:repository` and `read:issue`. Do not copy the source
account password or its separate GitOps token into this record.

The policy in `deploy/vault/codetether-harvester-forgejo-read.hcl` grants only
read access to that projected record. Append that policy to the existing
`codetether-harvester` Kubernetes role without replacing its other bindings.

Opaque mode rejects writes, other API origins, redirects, and paths outside
the configured repository. PR/review publication remains server-owned. Legacy
explicit-token mode remains available for existing callers.

Build using `docker/Dockerfile.harvester-forgejo-cli`; its private dockerignore
limits the build context to the wrapper files. No credentials enter the image.