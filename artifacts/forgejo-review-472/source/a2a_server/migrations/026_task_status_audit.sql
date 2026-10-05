-- Task status audit trail: records every status transition for any task run.
-- Enables operators to reconstruct the full lifecycle of any job.

CREATE TABLE IF NOT EXISTS task_status_audit (
    id BIGSERIAL PRIMARY KEY,
    task_run_id TEXT NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    actor TEXT,                           -- worker_id, user_id, or 'system'
    reason TEXT,                          -- human-readable explanation
    transition_metadata JSONB,            -- structured details (model_ref, branch, etc.)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_status_audit_run_id
    ON task_status_audit(task_run_id);
CREATE INDEX IF NOT EXISTS idx_task_status_audit_created_at
    ON task_status_audit(created_at);
CREATE INDEX IF NOT EXISTS idx_task_status_audit_new_status
    ON task_status_audit(new_status);
