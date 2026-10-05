-- The task row lock serializes cursor allocation with claim/release.
ALTER TABLE workers ADD COLUMN IF NOT EXISTS spiffe_id TEXT;

CREATE TABLE IF NOT EXISTS task_output_chunks (
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    cursor BIGINT NOT NULL CHECK (cursor > 0),
    worker_id TEXT NOT NULL,
    output TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event JSONB,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (task_id, cursor)
);

COMMENT ON COLUMN workers.spiffe_id IS
    'Provisioned verified workload identity; never set from output requests';
COMMENT ON TABLE task_output_chunks IS
    'Task-owned output; access is authorized against durable tasks before replay';
