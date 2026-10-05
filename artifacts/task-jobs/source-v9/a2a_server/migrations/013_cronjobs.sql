-- Migration: Create cronjobs table for scheduled task execution
-- Created: 2026-02-01

-- Main table for storing scheduled cronjobs
CREATE TABLE IF NOT EXISTS cronjobs (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    tenant_id TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    cron_expression VARCHAR(100) NOT NULL,
    task_template JSONB NOT NULL DEFAULT '{}',
    timezone VARCHAR(50) DEFAULT 'UTC',
    enabled BOOLEAN DEFAULT true,
    last_run_at TIMESTAMP WITH TIME ZONE,
    next_run_at TIMESTAMP WITH TIME ZONE,
    run_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_cronjobs_tenant ON cronjobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cronjobs_user ON cronjobs(user_id);
CREATE INDEX IF NOT EXISTS idx_cronjobs_next_run ON cronjobs(next_run_at) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_cronjobs_enabled ON cronjobs(enabled);

-- Execution history table
CREATE TABLE IF NOT EXISTS cronjob_runs (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    cronjob_id TEXT NOT NULL REFERENCES cronjobs(id) ON DELETE CASCADE,
    tenant_id TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    output TEXT,
    error_message TEXT,
    task_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for cronjob_runs
CREATE INDEX IF NOT EXISTS idx_cronjob_runs_cronjob ON cronjob_runs(cronjob_id);
CREATE INDEX IF NOT EXISTS idx_cronjob_runs_tenant ON cronjob_runs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cronjob_runs_started ON cronjob_runs(started_at DESC);

-- Enable RLS
ALTER TABLE cronjobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE cronjob_runs ENABLE ROW LEVEL SECURITY;

-- RLS policies for cronjobs
DROP POLICY IF EXISTS cronjobs_tenant_isolation ON cronjobs;
CREATE POLICY cronjobs_tenant_isolation ON cronjobs
    USING (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS cronjobs_admin_bypass ON cronjobs;
CREATE POLICY cronjobs_admin_bypass ON cronjobs
    USING (current_setting('app.current_tenant_id', true) = 'admin');

-- RLS policies for cronjob_runs
DROP POLICY IF EXISTS cronjob_runs_tenant_isolation ON cronjob_runs;
CREATE POLICY cronjob_runs_tenant_isolation ON cronjob_runs
    USING (tenant_id = current_setting('app.current_tenant_id', true));

DROP POLICY IF EXISTS cronjob_runs_admin_bypass ON cronjob_runs;
CREATE POLICY cronjob_runs_admin_bypass ON cronjob_runs
    USING (current_setting('app.current_tenant_id', true) = 'admin');

-- Auto-cleanup old runs (retention: 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_cronjob_runs()
RETURNS void AS $$
BEGIN
    DELETE FROM cronjob_runs
    WHERE created_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Migration tracking
INSERT INTO schema_migrations (migration_name, applied_at)
VALUES ('013_cronjobs', NOW())
ON CONFLICT (migration_name) DO NOTHING;
