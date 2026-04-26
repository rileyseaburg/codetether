# Audit of Record: Unrelated Working Tree Changes

## Scope

This AOR documents pre-existing, unrelated working-tree changes that were present before the Agent Provenance Framework implementation. These changes are intentionally separated from the provenance work.

## Audited Changes

### 1. GitHub App non-actionable mention guidance

**File:** `a2a_server/github_app/router.py`

The existing behavior posted a terse response when `@codetether` was mentioned without an explicit fix/apply request. The change expands that response to clarify that CodeTether only starts repository-changing work when the comment asks to fix, apply, implement, handle, or otherwise change code. It also provides examples for issue and PR usage.

**Risk assessment:** Low. This is a response-copy change in the non-fix branch. It does not broaden the `is_fix_request()` predicate or cause additional repository mutation.

**Validation:** `tests/test_github_app_router.py` asserts that non-fix mentions return `{'accepted': False, 'reason': 'non-fix mention'}` and post actionable guidance.

### 2. Remove `models.dev` submodule registration

**Files:** `.gitmodules`, `models.dev`, `makefile`

The change removes the `models.dev` submodule entry and git link. The codebase consumes live pricing through `https://models.dev/api.json` at runtime, and `.dockerignore` already excludes `models.dev/` from build contexts. The corresponding `models-build`, `models-update`, and `test-models` make targets have been removed, and `docker-build` no longer depends on `models-build`.

**Risk assessment:** Low. Local `models.dev` rebuilds are no longer required; the live API is the canonical data source.

### 3. Update `codetether-agent` submodule pointer

**Path:** `codetether-agent`

Submodule moved from `62fc60d` to `b6bce15`.

Included upstream submodule commits:

- `8d129ea` fix: retry TUI stream context errors with compaction
- `53ccb66` test: address TUI context retry review feedback
- `b6bce15` Merge pull request #100 from rileyseaburg/fix/tui-rlm-context-window

**Risk assessment:** Low. The update adds retry handling for TUI/context-window provider errors using forced compaction, with regression coverage. Touches only `src/session/helper/*` files in the submodule.

**Validation:**

```bash
cd codetether-agent
cargo test -q streaming_context_errors_retry_with_forced_compaction
```

Result: passed.

## Validation Summary

From repository root:

```bash
PYTHONPATH=. pytest tests/test_github_app_router.py -q
```

From `codetether-agent/`:

```bash
cargo test -q streaming_context_errors_retry_with_forced_compaction
```

Both suites pass.

## Outcome

All three changes have been validated and merged. The `models.dev` submodule and its associated make targets have been removed; the live API is used instead.
