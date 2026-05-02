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
