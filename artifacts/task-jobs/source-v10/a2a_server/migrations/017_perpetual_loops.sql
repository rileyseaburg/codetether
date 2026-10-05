-- Migration 017: Perpetual Cognition Loops + Billing Gap Fixes
--
-- 1. Perpetual loops table for persistent thought loops that survive restarts
-- 2. Extend check_user_task_limits() to enforce agent_minutes_limit
-- 3. Add cost tracking columns for per-loop budget control
--
-- Backs the marketing claims:
--   "Continuous thought loops that persist across restarts"
--   "Your agents reason, plan, and act autonomously"

BEGIN;

-- ============================================================================
-- perpetual_loops: persistent thought loops that survive restarts
-- ============================================================================
CREATE TABLE IF NOT EXISTS perpetual_loops (
    id                      TEXT PRIMARY KEY,
    tenant_id               TEXT REFERENCES tenants(id),
    user_id                 TEXT,

    -- What persona runs this loop
    persona_slug            TEXT NOT NULL,
    codebase_id             TEXT,

    -- State machine
    status                  TEXT NOT NULL DEFAULT 'running'
                            CHECK (status IN ('running', 'paused', 'stopped', 'budget_exhausted', 'failed')),
    -- Serialized reasoning context carried across iterations
    state                   JSONB DEFAULT '{}'::jsonb,

    -- Iteration tracking
    iteration_count         INTEGER DEFAULT 0,
    iteration_interval_seconds INTEGER DEFAULT 300,  -- 5 min default for monitoring
    max_iterations_per_day  INTEGER DEFAULT 100,
    iterations_today        INTEGER DEFAULT 0,
    iterations_today_reset_at TIMESTAMPTZ DEFAULT NOW(),

    -- Cost control (daily ceiling prevents runaway LLM spend)
    daily_cost_ceiling_cents INTEGER DEFAULT 500,   -- $5/day default
    cost_today_cents        INTEGER DEFAULT 0,
    cost_today_reset_at     TIMESTAMPTZ DEFAULT NOW(),
    cost_total_cents        INTEGER DEFAULT 0,

    -- Heartbeat for liveness detection
    last_heartbeat          TIMESTAMPTZ,
    last_iteration_at       TIMESTAMPTZ,

    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_perpetual_loops_tenant ON perpetual_loops(tenant_id);
CREATE INDEX IF NOT EXISTS idx_perpetual_loops_status ON perpetual_loops(status) WHERE status = 'running';

-- ============================================================================
-- perpetual_loop_iterations: per-iteration audit trail with cost tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS perpetual_loop_iterations (
    id                  TEXT PRIMARY KEY,
    loop_id             TEXT NOT NULL REFERENCES perpetual_loops(id) ON DELETE CASCADE,
    iteration_number    INTEGER NOT NULL,

    -- Task reference
    task_id             TEXT,

    -- State snapshots for debuggability
    input_state         JSONB DEFAULT '{}'::jsonb,
    output_state        JSONB DEFAULT '{}'::jsonb,

    -- Cost and duration per iteration
    cost_cents          INTEGER DEFAULT 0,
    duration_seconds    INTEGER DEFAULT 0,

    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_loop_iterations_loop ON perpetual_loop_iterations(loop_id);

-- ============================================================================
-- Fix billing gap: enforce agent_minutes_limit in check_user_task_limits()
-- The existing function checks tasks_used and concurrency but NOT agent_minutes.
-- ============================================================================
CREATE OR REPLACE FUNCTION check_user_task_limits(p_user_id TEXT)
RETURNS TABLE (
    allowed BOOLEAN,
    reason TEXT,
    tasks_used INTEGER,
    tasks_limit INTEGER,
    running_count INTEGER,
    concurrency_limit INTEGER
) AS $$
DECLARE
    v_user RECORD;
    v_running INTEGER;
BEGIN
    -- Get user's current state
    SELECT
        u.tasks_used_this_month,
        u.tasks_limit,
        u.concurrency_limit,
        u.tier_id,
        u.stripe_subscription_status,
        u.agent_minutes_used_this_month,
        u.agent_minutes_limit
    INTO v_user
    FROM users u WHERE u.id = p_user_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'User not found'::TEXT, 0, 0, 0, 0;
        RETURN;
    END IF;

    -- Count running tasks
    SELECT COUNT(*) INTO v_running
    FROM task_runs
    WHERE user_id = p_user_id AND status = 'running';

    -- Check monthly task limit
    IF v_user.tasks_used_this_month >= v_user.tasks_limit THEN
        RETURN QUERY SELECT
            FALSE,
            format('Monthly task limit reached (%s/%s). Upgrade to continue.',
                   v_user.tasks_used_this_month, v_user.tasks_limit),
            v_user.tasks_used_this_month,
            v_user.tasks_limit,
            v_running,
            v_user.concurrency_limit;
        RETURN;
    END IF;

    -- Check concurrency limit
    IF v_running >= v_user.concurrency_limit THEN
        RETURN QUERY SELECT
            FALSE,
            format('Concurrency limit reached (%s/%s running). Wait for tasks to complete or upgrade.',
                   v_running, v_user.concurrency_limit),
            v_user.tasks_used_this_month,
            v_user.tasks_limit,
            v_running,
            v_user.concurrency_limit;
        RETURN;
    END IF;

    -- Check agent minutes limit (NEW — fixes billing gap)
    IF v_user.agent_minutes_limit IS NOT NULL
       AND v_user.agent_minutes_used_this_month >= v_user.agent_minutes_limit THEN
        RETURN QUERY SELECT
            FALSE,
            format('Agent minutes limit reached (%s/%s minutes). Upgrade to continue.',
                   v_user.agent_minutes_used_this_month, v_user.agent_minutes_limit),
            v_user.tasks_used_this_month,
            v_user.tasks_limit,
            v_running,
            v_user.concurrency_limit;
        RETURN;
    END IF;

    -- All checks passed
    RETURN QUERY SELECT
        TRUE,
        'OK'::TEXT,
        v_user.tasks_used_this_month,
        v_user.tasks_limit,
        v_running,
        v_user.concurrency_limit;
END;
$$ LANGUAGE plpgsql;

COMMIT;
