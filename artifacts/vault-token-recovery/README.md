# Vault Kubernetes token recovery evidence

Scope: CodeTether VaultClient only; no deployment, cluster/Vault mutation, or Spotless changes in this assigned task.

## Mocked local

Command (using the existing shared Python virtualenv, importing source from this child worktree):

```
DATABASE_URL=postgresql://localhost:1/codetether_test /home/riley/A2A-Server-MCP/.venv/bin/python -m pytest tests/test_vault_token_refresh.py tests/test_git_service_vault_results.py --junitxml=artifacts/vault-token-recovery/pytest.xml -q
```

Observed: 33 tests passed, exit 0. All Vault sessions in the new tests are mocked; no real credentials or Vault calls are used.

Coverage: lease deadlines, cross-instance cache refresh, JWT rotation, auth-scope isolation, concurrent invalid-token rejection and failed refresh, static-token precedence, ordinary ACL denial without retry, twice-rejected token cooldown, bounded missing-lease caching, malformed login/lease data, transport-error redaction, redirect refusal, existing 204/404 semantics, and Git credential result propagation.

## Static/local

- Ruff formatting check: both scoped files formatted, exit 0.
- Ruff focused test lint: no findings, exit 0.
- git diff --check: exit 0.
- Existing production-file lint findings: 80 baseline, 67 current, no new diagnostics (lint-comparison.json).

## Not-run

Live deployment and live Vault verification were deliberately not run.

## Tool routing caveat

The apply_patch tool routed the initial relative-path edits to the parent checkout despite this being a child task. The two affected paths were a2a_server/vault_client.py and tests/test_vault_token_refresh.py, previously clean/absent there. Their initial contents were copied into this child, and subsequent changes used exec with explicit child workdir. Parent copies remain uncommitted and require parent review before cherry-picking; no unrelated parent edits should be discarded.
