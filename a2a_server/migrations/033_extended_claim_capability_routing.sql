-- Migration 033: Preserve capability/model routing in extended persistent claims
--
-- Migration 032 added target_worker_id filtering for GitHub App clone/fix
-- locality, but replaced the extended claim body with a simplified query that
-- no longer honored required_capabilities or model_ref routing.  That meant a
-- task queued with required_capabilities = ["persistent-workspace"] could still
-- be claimed by an arbitrary worker through the 7-day fire-and-forget path.
--
-- This version keeps explicit target_worker_id pinning for live workers while
-- restoring the same routing predicates used by hosted workers: agent name,
-- required capabilities, model support, and max timeout.
--
-- If the pinned worker is missing or has a stale heartbeat, the worker id is
-- treated as stale routing metadata and capability/agent routing is allowed to
-- recover the task. Worker ids are process-scoped, so treating them as
-- permanent queue ownership strands work after pod restarts.

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
    v_required_capabilities JSONB;
    v_model_ref TEXT;
    v_dispatch_mode TEXT;
    v_timeout INTEGER;
    v_checkpoint JSONB;
    v_checkpoint_seq INTEGER;
    v_resume_attempt INTEGER;
    v_issue_url TEXT;
    v_tenant_id TEXT;
BEGIN
    SELECT tr.id, tr.task_id, t.priority,
           COALESCE(tr.target_agent_name, t.metadata->>'target_agent_name'),
           COALESCE(tr.required_capabilities, t.metadata->'required_capabilities'),
           COALESCE(tr.model_ref, t.metadata->>'model_ref', t.model),
           COALESCE(tr.dispatch_mode, 'polling'),
           COALESCE(tr.task_timeout_seconds, 600),
           tr.checkpoint,
           COALESCE(tr.checkpoint_seq, 0),
           COALESCE(tr.resume_attempt, 0),
           tr.github_issue_url,
           COALESCE(tr.tenant_id, t.tenant_id)
    INTO v_run_id, v_task_id, v_priority, v_target_agent,
         v_required_capabilities, v_model_ref, v_dispatch_mode, v_timeout,
         v_checkpoint, v_checkpoint_seq, v_resume_attempt, v_issue_url,
         v_tenant_id
    FROM task_runs tr
    JOIN tasks t ON tr.task_id = t.id
    WHERE tr.status IN ('queued', 'running')
      AND (tr.lease_owner IS NULL OR tr.lease_expires_at < NOW())
      AND (tr.task_timeout_seconds IS NULL OR tr.task_timeout_seconds <= p_max_task_timeout)
      AND (
        COALESCE(tr.target_agent_name, t.metadata->>'target_agent_name') IS NULL
        OR COALESCE(tr.target_agent_name, t.metadata->>'target_agent_name') = ''
        OR COALESCE(tr.target_agent_name, t.metadata->>'target_agent_name') = p_agent_name
      )
      AND (
        t.metadata->>'target_worker_id' IS NULL
        OR t.metadata->>'target_worker_id' = ''
        OR t.metadata->>'target_worker_id' = p_worker_id
        OR (
          p_capabilities @> '["persistent-workspace"]'::jsonb
          AND NOT EXISTS (
            SELECT 1
            FROM workers target_worker
            WHERE target_worker.worker_id = t.metadata->>'target_worker_id'
              AND target_worker.status = 'active'
              AND target_worker.last_seen > NOW() - INTERVAL '2 minutes'
          )
        )
      )
      AND (
        COALESCE(tr.required_capabilities, t.metadata->'required_capabilities') IS NULL
        OR COALESCE(tr.required_capabilities, t.metadata->'required_capabilities') = '[]'::jsonb
        OR p_capabilities @> COALESCE(tr.required_capabilities, t.metadata->'required_capabilities')
      )
      AND (
        COALESCE(tr.model_ref, t.metadata->>'model_ref', t.model) IS NULL
        OR COALESCE(tr.model_ref, t.metadata->>'model_ref', t.model) = ''
        OR (
          p_models_supported IS NOT NULL
          AND COALESCE(tr.model_ref, t.metadata->>'model_ref', t.model) = ANY(p_models_supported)
        )
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
            last_heartbeat_at = NOW(),
            updated_at = NOW()
        WHERE id = v_run_id;
    END;

    RETURN QUERY SELECT
        v_run_id, v_task_id, v_priority, v_target_agent, v_model_ref,
        v_dispatch_mode, v_timeout, v_checkpoint, v_checkpoint_seq,
        v_resume_attempt, v_issue_url, v_tenant_id, NULL::jsonb,
        'platform'::text;
END;
$$ LANGUAGE plpgsql;

INSERT INTO schema_migrations (migration_name, checksum)
VALUES ('033_extended_claim_capability_routing', md5('033_extended_claim_capability_routing'))
ON CONFLICT (migration_name) DO UPDATE SET applied_at = NOW();
