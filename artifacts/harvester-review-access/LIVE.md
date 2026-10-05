# Harvester review access

## Provisioned capability

- Existing source Vault record contains a service-account password and a
  separate GitOps token. Neither was granted to the model or copied into the
  new record.
- Created Forgejo token ID 35 for the existing `spotless-agent` account, limited
  to repository `riley/spotlessbinco` and scopes `read:repository`, `read:issue`.
- Projected only that token and non-sensitive routing metadata at
  `kv/codetether/harvester/forgejo-review`.
- Added policy `codetether-harvester-forgejo-read` to Kubernetes auth role
  `codetether-harvester`, preserving existing role fields/policies.
- The new policy grants only `read` on the projected KV-v2 data path.
- The CLI obtains fresh Kubernetes/Vault authentication in-process and does
  not depend on an environment Vault token or a shared home token file.

## Live deployment/Argo evidence

- Worker image: `4.7.5-dev.49-forgejo-ro-599230d97ec3`.
- Digest: `sha256:8f12439cb6a295a9cee2310a3c7524328992d8924dcb1c991cc49e824e2a399d`.
- `a2a-system/a2a-server-harvester`: 2 ready, 2 updated;
  revision `a2a-server-harvester-7d4b7ccbdd`.
- `forgejo-cli get /repos/riley/spotlessbinco/pulls/5901` exited 0 on both pods
  without a token argument.
- Harvester-0 also read PR diff (2656 bytes), review discussion, and combined
  commit statuses successfully. The failed CI check was not hidden or changed.
- Existing Astra client and workspace tooling were retained.

## Validation / limits

- Mocked local: 13 CLI and review-context tests passed; `tests-combined.xml`.
- Boundaries checked: other origins/repos, traversal, and opaque-mode writes
  rejected; textual diffs supported; credential absent from CLI output.
- No Spotless code edits, PR merge, synthetic application writes, or CI rerun.
- This proves harvester review access, not that the separate trusted CI
  runner's previous Vault token failure has been repaired.