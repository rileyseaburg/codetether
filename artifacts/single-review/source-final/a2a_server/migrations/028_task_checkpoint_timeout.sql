-- Migration: 7-Day Task Lifecycle — Checkpoint Storage & Timeout Decoupling
--
-- Supports execution windows up to 7 days (604800 seconds) by:
--   * Adding task_timeout_seconds to task_runs (decoupled from Knative timeout)
--   * Storing github_issue metadata for progress comments
--   * Adding checkpoint JSONB with completed_steps, files_modified, git_state
--   * Adding resume_attempt counter for tracking how many times a task was resumed
--   * Adding checkpoint_at timestamp separate from heartbeat

ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS task_timeout_seconds INTEGER DEFAULT 600;

ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS checkpoint JSONB DEFAULT NULL;

ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS checkpoint_at TIMESTAMPTZ;

ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS resume_attempt INTEGER DEFAULT 0;

ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS github_issue_url TEXT;

ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS github_last_comment_at TIMESTAMPTZ;

ALTER TABLE task_runs
    ADD CONSTRAINT chk_task_timeout_range
    CHECK (task_timeout_seconds IS NULL OR (task_timeout_seconds >= 60 AND task_timeout_seconds <= 604800));

CREATE INDEX IF NOT EXISTS idx_task_runs_checkpoint_stale
    ON task_runs(last_heartbeat_at, task_timeout_seconds)
    WHERE status = 'running' AND last_heartbeat_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_runs_has_checkpoint
    ON task_runs(task_id)
    WHERE checkpoint IS NOT NULL;

-- Save a checkpoint for a task run.
CREATE OR REPLACE FUNCTION save_task_checkpoint(
    p_task_id TEXT,
    p_worker_id TEXT,
    p_checkpoint JSONB,
    p_checkpoint_seq INTEGER DEFAULT NULL,
    p_progress_pct INTEGER DEFAULT NULL,
    p_status_message TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_run_id TEXT;
    v_current_seq INTEGER;
BEGIN
    SELECT id, COALESCE(checkpoint_seq, 0) INTO v_run_id, v_current_seq
    FROM task_runs
    WHERE task_id = p_task_id
      AND status NOT IN ('completed', 'failed', 'cancelled')
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_run_id IS NULL THEN
        RETURN FALSE;
    END IF;

    IF p_checkpoint_seq IS NOT NULL AND p_checkpoint_seq <= v_current_seq THEN
        RETURN FALSE;
    END IF;

    UPDATE task_runs
    SET checkpoint           = p_checkpoint,
        checkpoint_at        = NOW(),
        last_heartbeat_at    = NOW(),
        updated_at           = NOW(),
        checkpoint_seq       = COALESCE(p_checkpoint_seq, checkpoint_seq + 1),
        task_progress        = CASE
            WHEN p_progress_pct IS NOT NULL OR p_status_message IS NOT NULL THEN
                COALESCE(task_progress, '{}'::jsonb) ||
                jsonb_build_object(
                    'progress_pct', COALESCE(p_progress_pct, 0),
                    'status_message', COALESCE(p_status_message, ''),
                    'worker_id', p_worker_id,
                    'heartbeat_at', NOW()::text
                )
            ELSE task_progress
        END
    WHERE id = v_run_id
      AND (lease_owner IS NULL OR lease_owner = p_worker_id);

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;


-- Resume a task from checkpoint: increment resume_attempt, claim for new worker.
CREATE OR REPLACE FUNCTION resume_task_from_checkpoint(
    p_task_id TEXT,
    p_new_worker_id TEXT,
    p_lease_duration INTEGER DEFAULT 600
)
RETURNS TABLE (
    run_id TEXT,
    checkpoint JSONB,
    checkpoint_seq INTEGER,
    resume_attempt INTEGER,
    task_timeout_seconds INTEGER,
    github_issue_url TEXT,
    task_progress JSONB,
    elapsed_seconds INTEGER
) AS $$
DECLARE
    v_run_id TEXT;
    v_checkpoint JSONB;
    v_seq INTEGER;
    v_resume INTEGER;
    v_timeout INTEGER;
    v_issue_url TEXT;
    v_progress JSONB;
    v_started TIMESTAMPTZ;
    v_elapsed INTEGER;
BEGIN
    SELECT tr.id, tr.checkpoint, tr.checkpoint_seq, tr.resume_attempt,
           tr.task_timeout_seconds, tr.github_issue_url, tr.task_progress,
           tr.started_at
    INTO v_run_id, v_checkpoint, v_seq, v_resume,
         v_timeout, v_issue_url, v_progress, v_started
    FROM task_runs tr
    WHERE tr.task_id = p_task_id
      AND tr.status IN ('running', 'queued')
    ORDER BY tr.created_at DESC
    LIMIT 1;

    IF v_run_id IS NULL THEN
        RETURN;
    END IF;

    UPDATE task_runs
    SET lease_owner       = p_new_worker_id,
        lease_expires_at  = NOW() + (p_lease_duration || ' seconds')::INTERVAL,
        resume_attempt    = COALESCE(resume_attempt, 0) + 1,
        last_heartbeat_at = NOW(),
        updated_at        = NOW(),
        status            = 'running',
        started_at        = COALESCE(started_at, NOW())
    WHERE id = v_run_id;

    IF v_started IS NOT NULL THEN
        v_elapsed := EXTRACT(EPOCH FROM (NOW() - v_started))::INTEGER;
    ELSE
        v_elapsed := 0;
    END IF;

    RETURN QUERY SELECT
        v_run_id,
        v_checkpoint,
        v_seq,
        COALESCE(v_resume, 0) + 1,
        v_timeout,
        v_issue_url,
        v_progress,
        v_elapsed;
END;
$$ LANGUAGE plpgsql;


-- Check if a task is within its timeout budget.
CREATE OR REPLACE FUNCTION task_within_timeout(
    p_task_id TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_timeout INTEGER;
    v_started TIMESTAMPTZ;
BEGIN
    SELECT tr.task_timeout_seconds, tr.started_at
    INTO v_timeout, v_started
    FROM task_runs tr
    WHERE tr.task_id = p_task_id
    ORDER BY tr.created_at DESC
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    v_timeout := COALESCE(v_timeout, 600);

    IF v_started IS NULL THEN
        RETURN TRUE;
    END IF;

    RETURN EXTRACT(EPOCH FROM (NOW() - v_started))::INTEGER < v_timeout;
END;
$$ LANGUAGE plpgsql STABLE;


-- Update github_last_comment_at after posting a progress comment.
CREATE OR REPLACE FUNCTION record_github_comment(
    p_task_id TEXT
)
RETURNS VOID AS $$
BEGIN
    UPDATE task_runs
    SET github_last_comment_at = NOW(),
        updated_at = NOW()
    WHERE task_id = p_task_id
      AND status NOT IN ('completed', 'failed', 'cancelled');
END;
$$ LANGUAGE plpgsql;
