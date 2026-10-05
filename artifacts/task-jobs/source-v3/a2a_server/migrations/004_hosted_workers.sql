-- Migration: Hosted Workers Infrastructure
-- Enables task queue with leasing for managed worker pools
-- Supports per-user concurrency limits and COGS tracking

-- Task runs table - the job queue for hosted workers
-- This is separate from the tasks table - tasks are the "what", task_runs are the "execution"
CREATE TABLE IF NOT EXISTS task_runs (
    id TEXT PRIMARY KEY,
    -- Links to existing task
    task_id TEXT NOT NULL,
    -- User who owns this run (for concurrency limiting)
    user_id TEXT REFERENCES users(id),
    -- Template that generated this (for analytics)
    template_id TEXT REFERENCES automation_templates(id),
    automation_id TEXT REFERENCES automations(id),
    
    -- Job queue status
    status TEXT DEFAULT 'queued',  -- queued, running, needs_input, completed, failed, cancelled
    priority INTEGER DEFAULT 0,    -- Higher = more urgent (0 is default)
    
    -- Lease management (prevents double-execution)
    lease_owner TEXT,              -- Worker ID that claimed this job
    lease_expires_at TIMESTAMPTZ,  -- Job returns to queue if lease expires
    
    -- Retry handling
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 2,
    last_error TEXT,
    
    -- Runtime tracking (for COGS/billing)
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    runtime_seconds INTEGER,       -- Computed on completion
    
    -- Result storage
    result_summary TEXT,           -- Brief result for listings
    result_full JSONB,             -- Full result data
    
    -- Notification settings (can override user defaults)
    notify_email TEXT,             -- Email to notify on completion
    notify_webhook_url TEXT,       -- Webhook to call on completion
    notification_sent BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient queue operations
CREATE INDEX IF NOT EXISTS idx_task_runs_queue 
    ON task_runs(status, priority DESC, created_at ASC) 
    WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS idx_task_runs_user ON task_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_task ON task_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_lease ON task_runs(lease_expires_at) 
    WHERE status = 'running';
CREATE INDEX IF NOT EXISTS idx_task_runs_user_running 
    ON task_runs(user_id, status) 
    WHERE status = 'running';

-- Add concurrency limits to users table
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS concurrency_limit INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS max_runtime_seconds INTEGER DEFAULT 600,  -- 10 min default
    ADD COLUMN IF NOT EXISTS agent_minutes_used_this_month INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS agent_minutes_limit INTEGER;  -- NULL = unlimited (within task limit)

-- Update existing users with tier-appropriate defaults
-- Free tier: 1 concurrent, 10 min max runtime
UPDATE users SET 
    concurrency_limit = 1,
    max_runtime_seconds = 600
WHERE concurrency_limit IS NULL;

-- Subscription tiers table (if we want to formalize tiers)
CREATE TABLE IF NOT EXISTS subscription_tiers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    -- Pricing
    price_monthly_cents INTEGER NOT NULL,
    stripe_price_id TEXT,
    -- Limits
    tasks_per_month INTEGER NOT NULL,
    concurrency_limit INTEGER NOT NULL,
    max_runtime_seconds INTEGER NOT NULL,
    agent_minutes_per_month INTEGER,  -- NULL = derived from tasks * max_runtime
    -- Features
    features JSONB DEFAULT '[]'::jsonb,
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default tiers
INSERT INTO subscription_tiers (id, name, price_monthly_cents, tasks_per_month, concurrency_limit, max_runtime_seconds, features)
VALUES 
    ('free', 'Free', 0, 10, 1, 600, '["basic_templates", "email_results"]'::jsonb),
    ('pro', 'Pro', 29700, 300, 3, 1800, '["all_templates", "email_results", "priority_queue", "api_access"]'::jsonb),
    ('agency', 'Agency', 49700, 2000, 10, 3600, '["all_templates", "email_results", "priority_queue", "api_access", "custom_templates", "webhook_notifications", "dedicated_support"]'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    price_monthly_cents = EXCLUDED.price_monthly_cents,
    tasks_per_month = EXCLUDED.tasks_per_month,
    concurrency_limit = EXCLUDED.concurrency_limit,
    max_runtime_seconds = EXCLUDED.max_runtime_seconds,
    features = EXCLUDED.features;

-- Add tier reference to users
ALTER TABLE users 
    ADD COLUMN IF NOT EXISTS tier_id TEXT REFERENCES subscription_tiers(id) DEFAULT 'free';

-- Worker pool tracking (for hosted workers)
CREATE TABLE IF NOT EXISTS hosted_workers (
    id TEXT PRIMARY KEY,
    -- Worker identification
    hostname TEXT,
    process_id INTEGER,
    -- Status
    status TEXT DEFAULT 'active',  -- active, draining, stopped
    -- Capacity
    max_concurrent_tasks INTEGER DEFAULT 1,
    current_tasks INTEGER DEFAULT 0,
    -- Stats
    tasks_completed INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    total_runtime_seconds INTEGER DEFAULT 0,
    -- Health
    last_heartbeat TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    stopped_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_hosted_workers_status ON hosted_workers(status);
CREATE INDEX IF NOT EXISTS idx_hosted_workers_heartbeat ON hosted_workers(last_heartbeat);

-- Function to claim next available job (atomic operation)
-- This prevents race conditions when multiple workers poll
CREATE OR REPLACE FUNCTION claim_next_task_run(
    p_worker_id TEXT,
    p_lease_duration_seconds INTEGER DEFAULT 600
)
RETURNS TABLE (
    run_id TEXT,
    task_id TEXT,
    user_id TEXT,
    priority INTEGER
) AS $$
DECLARE
    v_run task_runs%ROWTYPE;
    v_user_running_count INTEGER;
    v_user_concurrency_limit INTEGER;
BEGIN
    -- Find next queued job, respecting user concurrency limits
    -- Uses SKIP LOCKED to allow concurrent workers without blocking
    SELECT tr.* INTO v_run
    FROM task_runs tr
    JOIN users u ON tr.user_id = u.id
    WHERE tr.status = 'queued'
      AND (tr.lease_expires_at IS NULL OR tr.lease_expires_at < NOW())
      -- Check user hasn't hit concurrency limit
      AND (
          SELECT COUNT(*) 
          FROM task_runs tr2 
          WHERE tr2.user_id = tr.user_id 
            AND tr2.status = 'running'
      ) < u.concurrency_limit
    ORDER BY tr.priority DESC, tr.created_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;
    
    IF v_run.id IS NULL THEN
        RETURN;
    END IF;
    
    -- Claim the job
    UPDATE task_runs SET
        status = 'running',
        lease_owner = p_worker_id,
        lease_expires_at = NOW() + (p_lease_duration_seconds || ' seconds')::INTERVAL,
        started_at = COALESCE(started_at, NOW()),
        attempts = attempts + 1,
        updated_at = NOW()
    WHERE id = v_run.id;
    
    -- Return claimed job info
    run_id := v_run.id;
    task_id := v_run.task_id;
    user_id := v_run.user_id;
    priority := v_run.priority;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Function to renew lease (heartbeat)
CREATE OR REPLACE FUNCTION renew_task_run_lease(
    p_run_id TEXT,
    p_worker_id TEXT,
    p_lease_duration_seconds INTEGER DEFAULT 600
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE task_runs SET
        lease_expires_at = NOW() + (p_lease_duration_seconds || ' seconds')::INTERVAL,
        updated_at = NOW()
    WHERE id = p_run_id 
      AND lease_owner = p_worker_id
      AND status = 'running';
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Function to complete a task run
CREATE OR REPLACE FUNCTION complete_task_run(
    p_run_id TEXT,
    p_worker_id TEXT,
    p_status TEXT,  -- 'completed' or 'failed'
    p_result_summary TEXT DEFAULT NULL,
    p_result_full JSONB DEFAULT NULL,
    p_error TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_started_at TIMESTAMPTZ;
    v_runtime INTEGER;
    v_user_id TEXT;
BEGIN
    -- Get started_at for runtime calculation
    SELECT started_at, user_id INTO v_started_at, v_user_id
    FROM task_runs 
    WHERE id = p_run_id AND lease_owner = p_worker_id;
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Calculate runtime
    v_runtime := EXTRACT(EPOCH FROM (NOW() - v_started_at))::INTEGER;
    
    -- Update task run
    UPDATE task_runs SET
        status = p_status,
        completed_at = NOW(),
        runtime_seconds = v_runtime,
        result_summary = p_result_summary,
        result_full = p_result_full,
        last_error = CASE WHEN p_status = 'failed' THEN p_error ELSE last_error END,
        lease_owner = NULL,
        lease_expires_at = NULL,
        updated_at = NOW()
    WHERE id = p_run_id AND lease_owner = p_worker_id;
    
    -- Update user's agent minutes (rounded up to nearest minute)
    IF v_user_id IS NOT NULL AND v_runtime > 0 THEN
        UPDATE users SET
            agent_minutes_used_this_month = agent_minutes_used_this_month + GREATEST(1, (v_runtime + 59) / 60)
        WHERE id = v_user_id;
    END IF;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Function to reclaim expired leases (run periodically)
CREATE OR REPLACE FUNCTION reclaim_expired_task_runs()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE task_runs SET
        status = CASE 
            WHEN attempts >= max_attempts THEN 'failed'
            ELSE 'queued'
        END,
        lease_owner = NULL,
        lease_expires_at = NULL,
        last_error = CASE 
            WHEN attempts >= max_attempts THEN 'Max attempts exceeded (lease expired)'
            ELSE 'Lease expired, requeued'
        END,
        updated_at = NOW()
    WHERE status = 'running'
      AND lease_expires_at < NOW();
    
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- View for queue dashboard
-- Drop first to allow recreation with potentially different columns
DROP VIEW IF EXISTS task_queue_status CASCADE;
CREATE VIEW task_queue_status AS
SELECT 
    status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (NOW() - created_at)))::INTEGER as avg_wait_seconds,
    MAX(EXTRACT(EPOCH FROM (NOW() - created_at)))::INTEGER as max_wait_seconds
FROM task_runs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY status;

-- View for user queue status
-- Drop first to allow recreation with potentially different columns
DROP VIEW IF EXISTS user_queue_status CASCADE;
CREATE VIEW user_queue_status AS
SELECT 
    u.id as user_id,
    u.email,
    u.concurrency_limit,
    u.tasks_limit,
    u.tasks_used_this_month,
    COUNT(*) FILTER (WHERE tr.status = 'queued') as queued_tasks,
    COUNT(*) FILTER (WHERE tr.status = 'running') as running_tasks,
    COUNT(*) FILTER (WHERE tr.status = 'completed') as completed_tasks_24h,
    COUNT(*) FILTER (WHERE tr.status = 'failed') as failed_tasks_24h
FROM users u
LEFT JOIN task_runs tr ON u.id = tr.user_id 
    AND tr.created_at > NOW() - INTERVAL '24 hours'
GROUP BY u.id, u.email, u.concurrency_limit, u.tasks_limit, u.tasks_used_this_month;
