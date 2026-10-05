# Read only the projected review token. The source bundle includes an account
# password and a GitOps token and deliberately remains inaccessible.
path "kv/data/codetether/harvester/forgejo-review" {
  capabilities = ["read"]
}