# Task-output PostgreSQL storage contracts

These Node/native `psql` tests extract literal SQL from
`a2a_server/task_output.py` without executing Python and apply
`a2a_server/migrations/038_task_output_replay.sql` to isolated fixture tables.
Use a dedicated local or CI test database, never a production database.

Prerequisites: Node 22+, native `psql`, and PostgreSQL 16+. Set connection
variables explicitly; provide credentials through libpq (`.pgpass` or the CI
environment), not command arguments or checked-in files.

```sh
export PGHOST=127.0.0.1 PGPORT=5432 PGDATABASE=task_output_contract PGUSER=postgres
export TASK_OUTPUT_TEST_DATABASE=1
node scripts/check_task_output_postgres.cjs
```

The runner refuses to start without the explicit test-database acknowledgement.
Each test creates a randomly named `output_contract_*` schema and preserves it,
including on failure. The TAP report records schema names, source SHA-256 hashes,
and PostgreSQL version. Reports are retained beneath
`artifacts/task-output/postgres-contract/`; `TASK_OUTPUT_REPORT_DIR` can select
another evidence directory. Failed tests return a nonzero runner exit status.

Coverage: migration reapplication and constraints, concurrent cursor allocation,
rollback, exclusive pagination and task separation across fresh connections,
terminal-transition lock ordering, and repeatable-read output/status consistency.
Terminal rejection with HTTP 409 is Python behavior, not a SQL constraint; the
lock test checks what a waiting writer observes, not execution of that handler.

**Evidence level: static/local** for direct local runs; **focused CI-like** for
the dedicated CI job. These tests do not execute Python helpers, HTTP/SSE, OPA,
tenant authentication, SPIFFE authorization, full schema migrations or RLS.
They do not prove database-restart recovery, deployed replica behavior, worker
execution, Rust parity, or live deployment.