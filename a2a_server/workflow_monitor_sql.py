GITHUB_TASK_PREDICATE = """
(metadata->>'source' = 'github-app'
 OR metadata ? 'github_installation_id'
 OR metadata ? 'github_issue_url')
"""

TASK_REPO_EXPR = "COALESCE(t.metadata->>'repo', t.metadata->>'github_repo')"
REPO_EXPR = "COALESCE(metadata->>'repo', metadata->>'github_repo')"

COUNTS_SQL = f"""
SELECT {REPO_EXPR} AS repo, status, COUNT(*) AS count
FROM tasks
WHERE {GITHUB_TASK_PREDICATE}
  AND {REPO_EXPR} = ANY($1::text[])
  AND ($2::text IS NULL OR tenant_id = $2::text)
GROUP BY 1, 2
ORDER BY 1, 2
"""

WORKFLOWS_SQL = f"""
WITH gh AS (
  SELECT t.*, {TASK_REPO_EXPR} AS repo,
    COALESCE(t.metadata->>'issue_number', t.metadata->>'pr_number') AS issue_pr,
    t.metadata->>'github_issue_url' AS url,
    t.metadata->>'target_worker_id' AS target_worker_id,
    t.metadata->>'target_agent_name' AS target_agent_name,
    w.name AS worker_name, w.status AS worker_status, w.last_seen AS worker_last_seen
  FROM tasks t LEFT JOIN workers w ON w.worker_id = t.metadata->>'target_worker_id'
  WHERE {GITHUB_TASK_PREDICATE.replace('metadata', 't.metadata')}
    AND {TASK_REPO_EXPR} = ANY($1::text[])
    AND ($2::text IS NULL OR t.tenant_id = $2::text)
)
SELECT repo, issue_pr, url,
  COUNT(*) FILTER (WHERE status IN ('pending','running','failed')) AS incomplete_count,
  COUNT(*) FILTER (WHERE status = 'pending') AS pending_count,
  COUNT(*) FILTER (WHERE status = 'running') AS running_count,
  COUNT(*) FILTER (WHERE status = 'failed') AS failed_count,
  COUNT(*) FILTER (WHERE status = 'pending' AND
    (target_worker_id IS NULL OR target_worker_id = '' OR worker_name IS NULL)) AS unscoped_pending_count,
  COUNT(*) FILTER (WHERE status = 'pending' AND target_worker_id IS NOT NULL
    AND target_worker_id != '' AND worker_name IS NOT NULL
    AND (worker_last_seen IS NULL OR worker_last_seen < NOW() - INTERVAL '15 minutes')) AS stale_pending_count,
  jsonb_object_agg(status, status_count ORDER BY status) AS status_counts,
  jsonb_object_agg(agent_type, agent_count ORDER BY agent_type) AS agent_counts,
  MAX(updated_at) AS last_update,
  LEFT(STRING_AGG(DISTINCT COALESCE(error, ''), ' | '), 600) AS errors
FROM (SELECT gh.*, COUNT(*) OVER (PARTITION BY repo, issue_pr, url, status) AS status_count,
  COUNT(*) OVER (PARTITION BY repo, issue_pr, url, agent_type) AS agent_count
  FROM gh WHERE status IN ('pending', 'running', 'failed')) grouped
GROUP BY repo, issue_pr, url ORDER BY MAX(updated_at) DESC NULLS LAST LIMIT $3
"""
TASK_ROWS_SQL = f"""
SELECT t.id, t.status, t.title, t.agent_type, t.priority, t.created_at,
  t.updated_at, t.started_at, t.completed_at, t.worker_id,
  t.workspace_id, t.dispatch_mode, t.metadata, t.error,
  {TASK_REPO_EXPR} AS repo,
  COALESCE(t.metadata->>'issue_number', t.metadata->>'pr_number') AS issue_pr,
  t.metadata->>'github_issue_url' AS url,
  t.metadata->>'target_worker_id' AS target_worker_id,
  t.metadata->>'target_agent_name' AS target_agent_name,
  w.name AS worker_name, w.status AS worker_status, w.last_seen AS worker_last_seen
FROM tasks t LEFT JOIN workers w ON w.worker_id = t.metadata->>'target_worker_id'
WHERE {GITHUB_TASK_PREDICATE.replace('metadata', 't.metadata')}
  AND {TASK_REPO_EXPR} = ANY($1::text[])
  AND ($2::text IS NULL OR t.tenant_id = $2::text)
  AND t.status IN ('pending', 'running', 'failed')
ORDER BY t.updated_at DESC NULLS LAST LIMIT $3
"""

RUN_ROWS_SQL = f"""
SELECT tr.id AS run_id, tr.task_id, tr.status, tr.dispatch_mode,
  tr.lease_owner, tr.created_at, tr.updated_at, tr.started_at,
  tr.completed_at, tr.lease_expires_at, tr.last_error,
  t.title, t.status AS task_status, {TASK_REPO_EXPR} AS repo,
  COALESCE(t.metadata->>'issue_number', t.metadata->>'pr_number') AS issue_pr,
  t.metadata->>'github_issue_url' AS url
FROM task_runs tr JOIN tasks t ON t.id = tr.task_id
WHERE {GITHUB_TASK_PREDICATE.replace('metadata', 't.metadata')}
  AND {TASK_REPO_EXPR} = ANY($1::text[])
  AND ($2::text IS NULL OR t.tenant_id = $2::text)
  AND tr.status NOT IN ('completed', 'cancelled')
ORDER BY tr.updated_at DESC NULLS LAST LIMIT $3
"""
