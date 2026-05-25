# GitHub App active work dedupe ledger

## 2026-05-25 incident

Live DB evidence in namespace `a2a-server` showed multiple active `github-app`
tasks for the same repo/PR/stage/head SHA, which caused multiple workers to pick
up the same PR commit. Examples:

- `rileyseaburg/codetether-agent` PR `272`, stage `code`, head
  `798c9dc6d0d2853a6c1ca52ebbf086ce91ec8cb2`: active task IDs
  `078cd303-29f8-4a60-9114-97a1db095f12`,
  `8fb96dd5-4af1-49be-8efe-c38bf9ef2980`,
  `562d056c-256f-4106-8aa2-46a9d67bab6a`.
- `rileyseaburg/codetether-agent` PR `272`, stage `code`, head
  `487ecddacf4a7c56ac13b46bdc62e988273fa3ee`: six active duplicate tasks.
- `CodeTether/TetherScript` PR `14`, stage `clone_repo`, head
  `cd4c8d17660ed51fdd2112525997dec12963af8a`: three active duplicate tasks.

## Durable prevention

The production fix must be persisted in source/storage, not just session memory:

1. `create_and_dispatch_task()` computes `metadata.github_work_key` for
   GitHub App tasks as `github-app:{repo}:{number}:{stage}:{head_sha}`.
2. API pods serialize create/dispatch with `pg_advisory_lock(hashtextextended(key, 0))`.
3. The create path reuses the oldest active task with the same key instead of
   creating another `tasks`/`task_runs` pair.
4. Migration `034_github_app_work_dedupe_key.sql` adds a partial unique index on
   active tasks where `metadata->>'github_work_key'` is present. This is the
   storage-level backstop against local/session drift or multi-pod races.

## Operational validation query

```sql
WITH keyed AS (
  SELECT id, title, status, created_at,
         metadata->>'repo' repo,
         COALESCE(metadata->>'pr_number', metadata->>'issue_number') num,
         COALESCE(metadata->>'workflow_stage', agent_type) stage,
         COALESCE(metadata->>'pr_head_sha', metadata->>'github_check_head_sha', metadata->>'head_sha', '') sha,
         metadata->>'github_work_key' github_work_key
  FROM tasks
  WHERE metadata->>'source' = 'github-app'
    AND status IN ('pending','queued','running','working')
), grp AS (
  SELECT repo, num, stage, sha, github_work_key, count(*) cnt,
         array_agg(id ORDER BY created_at) ids
  FROM keyed
  GROUP BY repo, num, stage, sha, github_work_key
  HAVING count(*) > 1
)
SELECT * FROM grp ORDER BY cnt DESC, repo, num;
```
