-- Migration 032: Honor target_worker_id in claim_next_task_run_extended
--
-- Problem: The clone_repo → post_clone_task pipeline enqueues a build task
-- with target_worker_id set to the worker that cloned the repo (so the
-- workspace directory exists locally).  However, claim_next_task_run_extended
-- only filtered by target_agent_name — any worker could claim the task, and
-- if it landed on a different pod the workspace path wouldn't exist.
--
-- Fix: Add a target_worker_id filter so tasks pinned to a specific worker
-- are only claimed by that worker.  Tasks without a target_worker_id are
-- unaffected (the NULL check preserves the open-pool behaviour).

CREATE OR REPLACE FUNCTION claim_next_task_run_extended(
    p_worker_id TEXT,
    p_lease_duration INTEGER DEFAULT 600,
    p_agent_name TEXT DEFAULT NULL,
    p_capabilities JSONB DEFAULT '[]'::jsonb,
    p_models_supported TEXT[] DEFAULT NULL,
    p_max_task_timeout INTEGER DEFAULT 604800
)
RETURNS TABLE (
    run_id TEXT,
    task_id TEXT,
    priority INTEGER,
    target_agent_name TEXT,
    model_ref TEXT,
    dispatch_mode TEXT,
    task_timeout_seconds INTEGER,
    checkpoint JSONB,
    checkpoint_seq INTEGER,
    resume_attempt INTEGER,
    github_issue_url TEXT,
    tenant_id TEXT,
    provider_keys JSONB,
    provider_key_source TEXT
) AS $$
DECLARE
    v_run_id TEXT;
    v_task_id TEXT;
    v_priority INTEGER;
    v_target_agent TEXT;
    v_model_ref TEXT;
    v_dispatch_mode TEXT;
    v_timeout INTEGER;
    v_checkpoint JSONB;
    v_checkpoint_seq INTEGER;
    v_resume_attempt INTEGER;
    v_issue_url TEXT;
    v_tenant_id TEXT;
    v_provider_keys JSONB;
    v_provider_key_source TEXT;
BEGIN
    SELECT tr.id, tr.task_id, t.priority,
           t.metadata->>'target_agent_name',
           COALESCE(t.metadata->>'model_ref', t.model),
           COALESCE(tr.dispatch_mode, 'polling'),
           COALESCE(tr.task_timeout_seconds, 600),
           tr.checkpoint,
           COALESCE(tr.checkpoint_seq, 0),
           COALESCE(tr.resume_attempt, 0),
           tr.github_issue_url,
           COALESCE(tr.tenant_id, t.tenant_id),
           tr.provider_keys,
           COALESCE(tr.provider_key_source, 'platform')
    INTO v_run_id, v_task_id, v_priority, v_target_agent, v_model_ref,
         v_dispatch_mode, v_timeout, v_checkpoint, v_checkpoint_seq,
         v_resume_attempt, v_issue_url, v_tenant_id, v_provider_keys, v_provider_key_source
    FROM task_runs tr
    JOIN tasks t ON tr.task_id = t.id
    WHERE tr.status IN ('queued', 'running')
      AND (tr.lease_owner IS NULL OR tr.lease_expires_at < NOW())
      AND (tr.task_timeout_seconds IS NULL OR tr.task_timeout_seconds <= p_max_task_timeout)
      AND (
        t.metadata->>'target_agent_name' IS NULL
        OR t.metadata->>'target_agent_name' = p_agent_name
      )
      AND (
        t.metadata->>'target_worker_id' IS NULL
        OR t.metadata->>'target_worker_id' = p_worker_id
      )
    ORDER BY t.priority DESC NULLS LAST, tr.created_at ASC
    LIMIT 1
    FOR UPDATE OF tr SKIP LOCKED;

    IF v_run_id IS NULL THEN
        RETURN;
    END IF;

    DECLARE
        v_effective_lease INTEGER;
    BEGIN
        v_effective_lease := p_lease_duration;
        IF v_dispatch_mode = 'fire_and_forget' AND v_timeout > p_lease_duration THEN
            v_effective_lease := LEAST(v_timeout, 3600);
        END IF;

        UPDATE task_runs
        SET lease_owner = p_worker_id,
            lease_expires_at = NOW() + (v_effective_lease || ' seconds')::INTERVAL,
            status = 'running',
            started_at = COALESCE(started_at, NOW()),
            updated_at = NOW()
        WHERE id = v_run_id;
    END;

    RETURN QUERY SELECT
        v_run_id, v_task_id, v_priority, v_target_agent, v_model_ref,
        v_dispatch_mode, v_timeout, v_checkpoint, v_checkpoint_seq,
        v_resume_attempt, v_issue_url, v_tenant_id, v_provider_keys, v_provider_key_source;
END;
$$ LANGUAGE plpgsql;

INSERT INTO schema_migrations (migration_name, checksum)
VALUES ('032_target_worker_id_claim_filter', md5('032_target_worker_id_claim_filter'))
ON CONFLICT (migration_name) DO UPDATE SET applied_at = NOW();
