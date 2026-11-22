# History cleanup — 2026-11-22

The parent repository and `codetether-agent` are independent repositories. Each main history was cleaned separately, preserving commit authors, messages, ordering, and merge topology. Parent submodule references were translated through the agent commit map. Commit IDs change, and old commit signatures are not retained.

## Parent artifacts

Generated blobs above 50 MiB were removed from main history, including all historical occurrences:

- `artifacts/harvester-vault-fix/runs.json`
- `artifacts/ui-production/build-context.tar.gz`
- `artifacts/agent-workflow-validation/worker-image/codetether`
- `artifacts/downloads/awscliv2.zip`

Existing local files are retained; `/artifacts/` is ignored for future untracked output. Existing tracked smaller artifacts and application source remain intact.

## Agent OAuth configuration

The four embedded Gemini CLI/Antigravity OAuth application values were redacted throughout agent main history. Runtime code now requires explicit configuration rather than compiled-in application credentials. See the agent's `docs/gemini-oauth-configuration.md` for environment variables and Vault/cache fields.

Focused provider validation passed: 15 unit tests, 11 doc tests, and Clippy. One live test remains ignored. Tests cover explicit credential precedence, missing configuration, application-ID/secret matching, the authorization URL, and a mocked refresh request.

## Recovery and synchronization

Complete pre-cleanup Git bundles and old-to-new commit maps are retained outside the repositories under the owner's private `~/.local/share/codetether/history-backups/20261122/` directory. They preserve the old history and must not be republished as clean history.

Force updates use exact expected old main tips. Forgejo remains authoritative, and GitHub receives the same cleaned main tips. Other branches, tags, and existing secondary worktrees are not rewritten or deleted; rebase/recreate stale branches before merging them to avoid reintroducing removed history. Concurrent local SPIFFE work is preserved.

The earlier consolidation report records pre-cleanup commit IDs and validation. Its mirror blockers are resolved by this cleanup; use the new main tips rather than those historical IDs when syncing.

Cleaned agent main: `e002522eaa8a0cabdf39d44c42070c12bf287b23`.
