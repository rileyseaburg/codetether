# Audit of Record: Unrelated Working Tree Changes

## Scope

This AOR covers the non-Agent-Provenance working-tree changes that were present before the provenance implementation was started. These changes are intentionally separated from the Agent Provenance Framework work.

## Audited Changes

### 1. GitHub App non-actionable mention guidance

**File:** `a2a_server/github_app/router.py`

The existing behavior posted a terse response when `@codetether` was mentioned without an explicit fix/apply request. The change expands that response to clarify that CodeTether only starts repository-changing work when the comment asks to fix, apply, implement, handle, or otherwise change code. It also provides examples for issue and PR usage.

**Risk assessment:** Low. This is a response-copy change in the non-fix branch. It does not broaden the `is_fix_request()` predicate or cause additional repository mutation.

**Validation:** Added `tests/test_github_app_router.py::test_non_fix_mention_posts_actionable_guidance` to assert that non-fix mentions still return `{'accepted': False, 'reason': 'non-fix mention'}` and post actionable guidance.

### 2. Remove `models.dev` git submodule registration

**Files:** `.gitmodules`, `models.dev`

The staged change removes the `models.dev` submodule entry and gitlink. The codebase already consumes live pricing through `https://models.dev/api.json` in runtime paths, and `.dockerignore` already excludes `models.dev/` from build contexts. Make targets that assume a local checkout remain a follow-up concern if local model API rebuilds are still needed.

**Risk assessment:** Medium. Removing a submodule reduces checkout/submodule complexity but may break the optional `make models-build` and `make models-update` targets unless those targets are updated or the submodule is restored externally.

**Recommendation:** Accept only if local `models.dev` rebuild workflows are no longer required. Otherwise, split this deletion into its own PR with Makefile updates.

### 3. Update `codetether-agent` submodule pointer

**Path:** `codetether-agent`

Submodule moved from `62fc60d4ba7eb2d429ca257b7c6e7f8b18cc9ba1` to `b6bce15c503f23b2ada94c95ee68c96204b24557`.

Included upstream submodule commits:

- `8d129ea fix: retry TUI stream context errors with compaction`
- `53ccb66 test: address TUI context retry review feedback`
- `b6bce15 Merge pull request #100 from rileyseaburg/fix/tui-rlm-context-window`

Summary from submodule diff:

- Adds retry handling for TUI/context-window provider errors using forced compaction.
- Adds test provider support and regression coverage.
- Touches only `src/session/helper/*` files in the submodule.

**Risk assessment:** Medium. The update changes agent runtime retry behavior, but the new target commit is already present on `origin/fix/tui-rlm-context-window` in the submodule.

**Validation:** Ran targeted submodule test:

```bash
cd codetether-agent
cargo test -q streaming_context_errors_retry_with_forced_compaction
```

Result: passed.

## Validation Summary

From repository root:

```bash
PYTHONPATH=. pytest tests/test_github_app_mentions.py tests/test_github_app_router.py tests/test_github_app_task_completion.py -q
```

Result: `8 passed`.

From `codetether-agent/`:

```bash
cargo test -q streaming_context_errors_retry_with_forced_compaction
```

Result: `1 passed` for the targeted crate test; other test binaries had no matching tests.

## Decision

The GitHub App copy change and the codetether-agent submodule pointer update are suitable for a separate PR after review. The `models.dev` submodule removal should be explicitly called out in the PR because it may affect optional local pricing-data rebuild targets.
