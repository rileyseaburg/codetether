-- Migration: CI Runner Heartbeat & Progress Tracking
--
-- Adds a task_progress JSONB column to task_runs so CI runners can
-- phone home with incremental checkpoints.  If the runner dies, the
-- server (or the next worker) can read the last checkpoint to resume
-- from where it left off.
--
-- Key design decisions:
--   * task_progress is a JSONB blob — flexible schema that can hold
--     arbitrary checkpoint data (completed steps, file offsets, etc.)
--   * Separate last_heartbeat_at column (distinct from
--     lease_expires_at) records when the CI runner last phoned home.
--   * checkpoint_seq is a monotonically increasing integer that the
--     CI runner increments with each heartbeat so the server can
--     detect stale/out-of-order updates.

ALTER TABLE task_runs
    ADD COLUMN IF NOT EXISTS task_progress JSONB DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS checkpoint_seq INTEGER DEFAULT 0;

-- Index for finding runs whose CI runner went silent
CREATE INDEX IF NOT EXISTS idx_task_runs_heartbeat_stale
    ON task_runs(last_heartbeat_at)
    WHERE status = 'running' AND last_heartbeat_at IS NOT NULL;

-- Index for retrieving latest progress of a task
CREATE INDEX IF NOT EXISTS idx_task_runs_task_progress
    ON task_runs(task_id)
    WHERE task_progress IS NOT NULL AND task_progress != '{}'::jsonb;

-- Function: upsert a progress checkpoint from a CI runner.
-- Atomically updates the row only if the incoming checkpoint_seq is
-- strictly greater than the stored one (prevents stale overwrites).
CREATE OR REPLACE FUNCTION upsert_task_progress(
    p_task_id TEXT,
    p_worker_id TEXT,
    p_progress JSONB,
    p_checkpoint_seq INTEGER,
    p_status TEXT DEFAULT NULL,
    p_log_tail TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_run_id TEXT;
BEGIN
    -- Find the active (non-terminal) task run for this task.
    SELECT id INTO v_run_id
    FROM task_runs
    WHERE task_id = p_task_id
      AND status NOT IN ('completed', 'failed', 'cancelled')
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_run_id IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Only update if the new checkpoint sequence is strictly greater.
    -- This prevents stale heartbeats from overwriting fresher data.
    UPDATE task_runs
    SET task_progress        = p_progress,
        checkpoint_seq       = p_checkpoint_seq,
        last_heartbeat_at    = NOW(),
        updated_at           = NOW(),
        status               = COALESCE(p_status, status),
        last_error           = COALESCE(p_log_tail, last_error)
    WHERE id = v_run_id
      AND (checkpoint_seq < p_checkpoint_seq OR checkpoint_seq = 0);

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Function: get the latest progress checkpoint for a task.
-- Returns the task_progress blob plus metadata.
CREATE OR REPLACE FUNCTION get_task_progress(
    p_task_id TEXT
)
RETURNS TABLE (
    run_id TEXT,
    task_progress JSONB,
    checkpoint_seq INTEGER,
    last_heartbeat_at TIMESTAMPTZ,
    status TEXT,
    worker_id TEXT
) AS $$
SELECT tr.id,
       tr.task_progress,
       tr.checkpoint_seq,
       tr.last_heartbeat_at,
       tr.status,
       tr.lease_owner
FROM task_runs tr
WHERE tr.task_id = p_task_id
ORDER BY tr.created_at DESC
LIMIT 1;
$$ LANGUAGE sql STABLE;

-- Function: find task runs whose CI runner has gone silent.
-- Used by task_reaper or an operator to detect dead runners.
-- Returns runs that are "running" but haven't heartbeated within
-- the specified interval.
CREATE OR REPLACE FUNCTION find_silent_task_runs(
    p_silence_threshold_seconds INTEGER DEFAULT 300
)
RETURNS TABLE (
    run_id TEXT,
    task_id TEXT,
    last_heartbeat_at TIMESTAMPTZ,
    task_progress JSONB,
    lease_owner TEXT
) AS $$
SELECT tr.id,
       tr.task_id,
       tr.last_heartbeat_at,
       tr.task_progress,
       tr.lease_owner
FROM task_runs tr
WHERE tr.status = 'running'
  AND tr.last_heartbeat_at IS NOT NULL
  AND tr.last_heartbeat_at < NOW() - (p_silence_threshold_seconds || ' seconds')::INTERVAL
ORDER BY tr.last_heartbeat_at ASC;
$$ LANGUAGE sql STABLE;
