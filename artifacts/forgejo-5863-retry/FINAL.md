# Repair evidence ledger

Historical pre-rollout checkpoint. Subsequent deployment and recovered native
task evidence are recorded in `artifacts/forgejo-5870-rollout/LIVE.md`.

## Scope and source state

- Target: CodeTether's handling of Forgejo mentions, not Spotless application
  code or billing state. No Spotless source changes, billing updates, or replay.
- Local repair tip: `e3b523e` (`fix: persist Forgejo intake and recover failed handoffs`).
- Reviewed Temporal integration commits: `19dc206`, `f38c851`.
- Reviewed partial-run repair: `e7e2f30`.
- Existing unrelated worktree edits were left unstaged/uncommitted. Only the
  two-line retry-language hunk was staged from the already-edited mention file.

## Focused CI-like and mocked-local evidence

- `integrated-regressions.xml`: 183 tests, zero failures/errors, command exit 0.
- `final-handoff-check.xml`: 34 tests, zero failures/errors, command exit 0.
- PostgreSQL persistence, advisory locking, concurrent admission, checkpoint
  recovery, legacy lookup and connection-death tests use real PostgreSQL 16.
- External Forgejo/Vault/provider effects are mocked local, not platform proof.
- Additional Vault evidence and preserved early drafts:
  `artifacts/vault-token-recovery/`.

Commands used the repository `.venv/bin/python -m pytest`, with an isolated
test PostgreSQL DSN, across the Forgejo inbox/webhook/Temporal, Vault token,
partial-dispatch and mention suites. The final narrow rerun selected
`tests/test_forgejo_inbox.py`, `tests/test_forgejo_temporal_integration.py`, and
`tests/test_forgejo_temporal_workflow.py`.

## Static/local checks

- New inbox modules and tests: Ruff check succeeded.
- Changed existing runtime files: no new Ruff findings against `4e0fe718d799`;
  pre-existing findings were not disguised as a clean full-project lint run.
- Whitespace check succeeded. Earlier failed evidence is retained.

## Not-run / pending

- No image build/push, GitOps promotion, or production rollout.
- No live Vault renewal proof with the changed client.
- No live dispatch or legacy recovery enqueue of #5863.
- Controlled recovery command and safety gates: `docs/operations/forgejo-inbox.md`.