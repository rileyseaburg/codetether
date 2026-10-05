# Parent integration of reviewed Vault recovery

This record supersedes the historical parent-copy warning in the copied child
`README.md`. The user explicitly authorized integration of these two files only.

## Static/local file identity

Parent checkout: `/home/riley/A2A-Server-MCP`.
Reviewed child commit: `b31f5ed80a4560dea65c9ae2de5c520041b6c28c`.

Both parent files matched the reviewed commit before and after parent tests:

| File | Git blob |
| --- | --- |
| `a2a_server/vault_client.py` | `6f0c0984ff68a0da26e0270c1c38a760094e005f` |
| `tests/test_vault_token_refresh.py` | `c79537168c28d37777ce30deb655cb6166327de8` |

The older parent drafts, including the untracked test file, are preserved in
`parent-draft.patch`. Its reverse-application check against the drafts returned
exit 0 before replacement. An alternate `parent-draft.index` generated that
patch without changing the parent's actual Git index; the actual index SHA256
was identical before and after the copies. No parent commit was created.

## Mocked-local parent verification

Command, run from the parent checkout:

`DATABASE_URL=postgresql://localhost:1/codetether_test .venv/bin/python -m pytest tests/test_vault_token_refresh.py tests/test_git_service_vault_results.py --junitxml=artifacts/vault-token-recovery/parent-pytest.xml -q`

Observed: 33 tests passed, process exit 0. Parent evidence: `parent-pytest.xml`.
Original child evidence was copied byte-for-byte as `pytest.xml`,
`lint-comparison.json`, and `README.md`.

Static/local checks: focused test Ruff lint, two-file Ruff formatting check,
and scoped Git whitespace check each returned exit 0. No deployment was run.