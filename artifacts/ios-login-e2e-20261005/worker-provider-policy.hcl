# Provider discovery plus read-only access to the worker's default and rehearsal providers.
path "secret/metadata/codetether/providers" {
  capabilities = ["list"]
}
path "secret/data/codetether/providers/zai" {
  capabilities = ["read"]
}
path "secret/data/codetether/providers/github-copilot" {
  capabilities = ["read"]
}
