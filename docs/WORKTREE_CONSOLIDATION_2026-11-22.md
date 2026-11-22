# Worktree consolidation — 2026-11-22

Forgejo is the authoritative upstream; GitHub is a mirror. The source checkpoint before consolidation is `d96640a2`; the pre-consolidation main tip is retained on `backup/20261122-worktree-consolidation`.

## Integration

- Merged Forgejo main at `c09c8d75`, preserving local source changes.
- Reconciled all 26 registered secondary worktree heads in this repository, including 8 stale registrations whose commits were already ancestors.
- Committed pending source in the LM Studio helper worktree and four older GitHub automation worktrees before merging.
- Kept the `web/` rename, README, workspace exclusions, newer authentication handling, worker identity support, and current Temporal/GitHub automation behavior.
- Corrected Git rename inference that targeted archived source copies instead of `web/`. Archived copies were not used as integration targets.
- Retained worktrees and local runtime/test artifacts. Build outputs and private local repair artifacts were not added as source.
- Reconciled all 38 secondary worktree heads in the Rust submodule. See [Rust reconciliation](../codetether-agent/docs/worktree-reconciliation-2026-11-22.md) for historical drafts and their current implementations.

## Validation

- Web UI: 19 suites, 319 tests passed.
- Authentication: 15 tests passed.
- Python focused regressions: 186 tests and 32 subtests passed. These use a fixture database URL and mocked backend boundaries, not a live database.
- Rust delegated goals: 37 unit tests, 1 integration test, and 20 doc tests passed.
- Focused Rust formatting and Clippy checks passed for the affected MCP, goal, and related integration crates; existing warnings remain. Repository-wide formatting also reports an unrelated existing formatting difference in `dispatch_gemini_cli.rs`.
- Temporal triage: 4 tests passed.
- Focused Rust package tests and doc tests: 260 passed, 0 failed, 8 ignored. Packages: codetether-config, codetether-mcp-core, codetether-native-mcp-client, codetether-session-title, codetether-gemini-web-protocol, codetether-rust-build, and codetether-rust-repair.

Rust reconciliation tip before final validation: `fd569990b44f1eac7f166c49faae40731cda1363`.

## Publication and retained local work

Publish the Rust main tip to Forgejo and GitHub before the parent repository pointer. GitHub main mirrors the final Forgejo source; the previous GitHub-only head is preserved on `backup/pre-forgejo-mirror-20261122`.

Concurrent SPIFFE launcher/docs changes in the Rust checkout remain uncommitted and outside this consolidation. Existing runtime artifacts and worktrees remain on disk.
