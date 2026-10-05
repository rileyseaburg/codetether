-- Migration: restore full task_run claim routing after tenant isolation
--
-- Migration 010 redefined claim_next_task_run with a 3-argument signature,
-- unintentionally dropping the 5-argument worker claim function used by
-- hosted_worker.py. That makes hosted workers fail to claim GitHub Action
-- dispatch jobs with "function claim_next_task_run(...) does not exist". This
-- migration preserves tenant isolation while restoring agent/capability/model
-- routing and the expected return columns.

CREATE OR REPLACE FUNCTION claim_next_task_run(
    p_worker_id TEXT,
    p_lease_duration_seconds INTEGER DEFAULT 600,
    p_worker_agent_name TEXT DEFAULT NULL,
    p_worker_capabilities JSONB DEFAULT '[]'::JSONB,
    p_worker_models_supported TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    run_id TEXT,
    task_id TEXT,
    user_id TEXT,
    priority INTEGER,
    target_agent_name TEXT,
    required_capabilities JSONB,
    model_ref TEXT,
    tenant_id TEXT
) AS $$
DECLARE
    v_run task_runs%ROWTYPE;
BEGIN
    SELECT tr.* INTO v_run
    FROM task_runs tr
    LEFT JOIN users u ON tr.user_id = u.id
    WHERE tr.status = 'queued'
      AND (tr.lease_expires_at IS NULL OR tr.lease_expires_at < NOW())
      AND (tr.deadline_at IS NULL OR tr.deadline_at > NOW())
      -- Agent targeting: if task has target_agent_name, only that agent can claim it.
      AND (
          tr.target_agent_name IS NULL
          OR tr.target_agent_name = p_worker_agent_name
      )
      -- Capability check: worker must have all requested capabilities.
      AND (
          tr.required_capabilities IS NULL
          OR tr.required_capabilities = '[]'::JSONB
          OR p_worker_capabilities @> tr.required_capabilities
      )
      -- Model check: explicit model tasks require an advertising compatible worker.
      AND (
          tr.model_ref IS NULL
          OR (
              p_worker_models_supported IS NOT NULL
              AND array_length(p_worker_models_supported, 1) > 0
              AND tr.model_ref = ANY(p_worker_models_supported)
          )
      )
      -- User concurrency check; service/internal rows may have no user.
      AND (
          tr.user_id IS NULL
          OR u.id IS NULL
          OR (
              SELECT COUNT(*)
              FROM task_runs tr2
              WHERE tr2.user_id = tr.user_id
                AND tr2.status = 'running'
          ) < COALESCE(u.concurrency_limit, 999)
      )
    ORDER BY
        CASE WHEN tr.target_agent_name IS NOT NULL THEN 0 ELSE 1 END,
        CASE WHEN tr.model_ref IS NOT NULL THEN 0 ELSE 1 END,
        tr.priority DESC,
        tr.created_at ASC
    FOR UPDATE OF tr SKIP LOCKED
    LIMIT 1;

    IF v_run.id IS NULL THEN
        RETURN;
    END IF;

    UPDATE task_runs SET
        status = 'running',
        lease_owner = p_worker_id,
        lease_expires_at = NOW() + (p_lease_duration_seconds || ' seconds')::INTERVAL,
        started_at = COALESCE(task_runs.started_at, NOW()),
        attempts = task_runs.attempts + 1,
        updated_at = NOW()
    WHERE id = v_run.id;

    run_id := v_run.id;
    task_id := v_run.task_id;
    user_id := v_run.user_id;
    priority := v_run.priority;
    target_agent_name := v_run.target_agent_name;
    required_capabilities := v_run.required_capabilities;
    model_ref := v_run.model_ref;
    tenant_id := v_run.tenant_id;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

INSERT INTO schema_migrations (migration_name, checksum)
VALUES ('019_restore_task_run_routing_claim', md5('019_restore_task_run_routing_claim'))
ON CONFLICT (migration_name) DO UPDATE SET applied_at = NOW();
