-- Migration: 7-Day Persistent Worker Architecture
--
-- Adds support for tasks that run up to 7 days by introducing:
--   * dispatch_mode column: 'polling' (legacy) vs 'fire_and_forget' (new)
--   * Extended lease support with checkpoint-based resumption
--   * Enhanced heartbeat with configurable lease renewal

-- task_runs: dispatch mode for fire-and-forget vs polling
ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS dispatch_mode TEXT DEFAULT 'polling'
    CHECK (dispatch_mode IN ('polling', 'fire_and_forget'));

-- tasks: dispatch mode propagation
ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS dispatch_mode TEXT DEFAULT 'polling'
    CHECK (dispatch_mode IN ('polling', 'fire_and_forget'));

-- Index for finding fire-and-forget tasks needing progress comments
CREATE INDEX IF NOT EXISTS idx_task_runs_ff_progress
    ON task_runs(github_last_comment_at, status)
    WHERE dispatch_mode = 'fire_and_forget'
      AND status = 'running'
      AND github_issue_url IS NOT NULL;

-- Index for finding fire-and-forget tasks needing worker assignment
CREATE INDEX IF NOT EXISTS idx_task_runs_ff_pending
    ON task_runs(created_at, priority DESC)
    WHERE dispatch_mode = 'fire_and_forget'
      AND status IN ('queued', 'running')
      AND lease_owner IS NULL;

-- Create a persistent fire-and-forget task run for an existing task.
-- Used by the GitHub App harvester path after it creates the A2A task row.
CREATE OR REPLACE FUNCTION create_fire_and_forget_run(
    p_task_id TEXT,
    p_user_id TEXT DEFAULT NULL,
    p_tenant_id TEXT DEFAULT NULL,
    p_priority INTEGER DEFAULT 0,
    p_task_timeout_seconds INTEGER DEFAULT 604800,
    p_github_issue_url TEXT DEFAULT NULL
)
RETURNS TEXT AS $$
DECLARE
    v_run_id TEXT;
    v_timeout INTEGER;
BEGIN
    v_run_id := 'run_' || replace(gen_random_uuid()::TEXT, '-', '');
    v_timeout := LEAST(GREATEST(COALESCE(p_task_timeout_seconds, 604800), 60), 604800);

    INSERT INTO task_runs (
        id, task_id, user_id, tenant_id, status, priority,
        task_timeout_seconds, github_issue_url, dispatch_mode, created_at, updated_at
    ) VALUES (
        v_run_id, p_task_id, p_user_id, p_tenant_id, 'queued', COALESCE(p_priority, 0),
        v_timeout, p_github_issue_url, 'fire_and_forget', NOW(), NOW()
    );

    UPDATE tasks
    SET dispatch_mode = 'fire_and_forget',
        updated_at = NOW()
    WHERE id = p_task_id;

    RETURN v_run_id;
END;
$$ LANGUAGE plpgsql;

-- Extended claim wrapper for persistent workers. Reuses the restored routing claim
-- function, then returns the additional fire-and-forget/checkpoint metadata used
-- by persistent_worker_pool.py.
CREATE OR REPLACE FUNCTION claim_next_task_run_extended(
    p_worker_id TEXT,
    p_lease_duration_seconds INTEGER DEFAULT 600,
    p_worker_agent_name TEXT DEFAULT NULL,
    p_worker_capabilities JSONB DEFAULT '[]'::JSONB,
    p_worker_models_supported TEXT[] DEFAULT NULL,
    p_max_task_timeout_seconds INTEGER DEFAULT 604800
)
RETURNS TABLE (
    run_id TEXT,
    task_id TEXT,
    user_id TEXT,
    tenant_id TEXT,
    priority INTEGER,
    target_agent_name TEXT,
    required_capabilities JSONB,
    model_ref TEXT,
    dispatch_mode TEXT,
    task_timeout_seconds INTEGER,
    github_issue_url TEXT,
    checkpoint JSONB,
    checkpoint_seq INTEGER,
    resume_attempt INTEGER,
    task_progress JSONB,
    elapsed_seconds INTEGER
) AS $$
DECLARE
    v_claim RECORD;
    v_run task_runs%ROWTYPE;
BEGIN
    SELECT * INTO v_claim
    FROM claim_next_task_run(
        p_worker_id,
        p_lease_duration_seconds,
        p_worker_agent_name,
        p_worker_capabilities,
        p_worker_models_supported
    )
    LIMIT 1;

    IF v_claim.run_id IS NULL THEN
        RETURN;
    END IF;

    SELECT tr.* INTO v_run
    FROM task_runs tr
    WHERE tr.id = v_claim.run_id
      AND COALESCE(tr.task_timeout_seconds, 600) <= COALESCE(p_max_task_timeout_seconds, 604800);

    IF v_run.id IS NULL THEN
        RETURN;
    END IF;

    UPDATE task_runs
    SET last_heartbeat_at = NOW(),
        updated_at = NOW()
    WHERE id = v_run.id;

    run_id := v_run.id;
    task_id := v_run.task_id;
    user_id := v_run.user_id;
    tenant_id := v_run.tenant_id;
    priority := v_run.priority;
    target_agent_name := v_run.target_agent_name;
    required_capabilities := v_run.required_capabilities;
    model_ref := v_run.model_ref;
    dispatch_mode := COALESCE(v_run.dispatch_mode, 'polling');
    task_timeout_seconds := COALESCE(v_run.task_timeout_seconds, 600);
    github_issue_url := v_run.github_issue_url;
    checkpoint := v_run.checkpoint;
    checkpoint_seq := COALESCE(v_run.checkpoint_seq, 0);
    resume_attempt := COALESCE(v_run.resume_attempt, 0);
    task_progress := COALESCE(v_run.task_progress, '{}'::JSONB);
    elapsed_seconds := CASE
        WHEN v_run.started_at IS NULL THEN 0
        ELSE EXTRACT(EPOCH FROM (NOW() - v_run.started_at))::INTEGER
    END;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Heartbeat endpoint for persistent workers. Updates checkpoint/progress and
-- renews the lease without changing terminal runs or stealing another worker's lease.
CREATE OR REPLACE FUNCTION extended_heartbeat(
    p_task_id TEXT,
    p_worker_id TEXT,
    p_progress JSONB DEFAULT NULL,
    p_checkpoint JSONB DEFAULT NULL,
    p_checkpoint_seq INTEGER DEFAULT NULL,
    p_lease_duration_seconds INTEGER DEFAULT 600,
    p_log_tail TEXT DEFAULT NULL
)
RETURNS TABLE (
    success BOOLEAN,
    lease_expires_at TIMESTAMPTZ,
    within_timeout BOOLEAN,
    elapsed_seconds INTEGER,
    resume_attempt INTEGER
) AS $$
DECLARE
    v_run task_runs%ROWTYPE;
BEGIN
    SELECT * INTO v_run
    FROM task_runs
    WHERE task_id = p_task_id
      AND status NOT IN ('completed', 'failed', 'cancelled')
    ORDER BY created_at DESC
    LIMIT 1
    FOR UPDATE;

    IF v_run.id IS NULL OR v_run.lease_owner IS DISTINCT FROM p_worker_id THEN
        success := FALSE;
        lease_expires_at := NULL;
        within_timeout := FALSE;
        elapsed_seconds := 0;
        resume_attempt := 0;
        RETURN NEXT;
        RETURN;
    END IF;

    UPDATE task_runs
    SET lease_expires_at = NOW() + (p_lease_duration_seconds || ' seconds')::INTERVAL,
        last_heartbeat_at = NOW(),
        updated_at = NOW(),
        task_progress = CASE
            WHEN p_progress IS NOT NULL THEN COALESCE(task_progress, '{}'::JSONB) || p_progress
            ELSE task_progress
        END,
        checkpoint = CASE
            WHEN p_checkpoint IS NOT NULL
             AND (p_checkpoint_seq IS NULL OR p_checkpoint_seq > COALESCE(checkpoint_seq, 0))
            THEN p_checkpoint
            ELSE checkpoint
        END,
        checkpoint_at = CASE
            WHEN p_checkpoint IS NOT NULL
             AND (p_checkpoint_seq IS NULL OR p_checkpoint_seq > COALESCE(checkpoint_seq, 0))
            THEN NOW()
            ELSE checkpoint_at
        END,
        checkpoint_seq = CASE
            WHEN p_checkpoint_seq IS NOT NULL AND p_checkpoint_seq > COALESCE(checkpoint_seq, 0)
            THEN p_checkpoint_seq
            ELSE checkpoint_seq
        END,
        last_error = COALESCE(p_log_tail, last_error)
    WHERE id = v_run.id
    RETURNING task_runs.lease_expires_at INTO lease_expires_at;

    success := TRUE;
    within_timeout := CASE
        WHEN v_run.started_at IS NULL THEN TRUE
        ELSE EXTRACT(EPOCH FROM (NOW() - v_run.started_at))::INTEGER < COALESCE(v_run.task_timeout_seconds, 600)
    END;
    elapsed_seconds := CASE
        WHEN v_run.started_at IS NULL THEN 0
        ELSE EXTRACT(EPOCH FROM (NOW() - v_run.started_at))::INTEGER
    END;
    resume_attempt := COALESCE(v_run.resume_attempt, 0);
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;
