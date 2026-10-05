-- Immutable review bytes stay out of task-list/SSE payloads and Temporal history.
CREATE TABLE IF NOT EXISTS forgejo_review_snapshots (
    owner_task_id TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    context JSONB NOT NULL,
    chunks JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);