-- Migration: Stripe Tier Wiring
-- Enables durable price-to-tier mapping, webhook idempotency, and billing period tracking
-- for the mid-market subscription model (Free $0, Pro $297, Agency $497)

-- ============================================================
-- 1. Stripe Price Map - durable mapping, no code deploy for new prices
-- ============================================================

CREATE TABLE IF NOT EXISTS stripe_price_map (
    price_id TEXT PRIMARY KEY,           -- Stripe Price ID (price_xxx)
    tier_id TEXT NOT NULL REFERENCES subscription_tiers(id),
    description TEXT,                     -- Human-readable (e.g., "Pro Monthly")
    is_active BOOLEAN DEFAULT TRUE,       -- Can disable without deleting
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for tier lookup
CREATE INDEX IF NOT EXISTS idx_stripe_price_map_tier ON stripe_price_map(tier_id);

-- Seed with initial prices (update these with your actual Stripe price IDs)
-- Free tier has no price_id (no subscription required)
INSERT INTO stripe_price_map (price_id, tier_id, description) VALUES
    ('price_pro_monthly', 'pro', 'Pro - $297/month'),
    ('price_agency_monthly', 'agency', 'Agency - $497/month')
ON CONFLICT (price_id) DO UPDATE SET
    tier_id = EXCLUDED.tier_id,
    description = EXCLUDED.description,
    updated_at = NOW();

-- ============================================================
-- 2. Stripe Events - webhook idempotency (persistent across restarts)
-- ============================================================

CREATE TABLE IF NOT EXISTS stripe_events (
    event_id TEXT PRIMARY KEY,            -- Stripe Event ID (evt_xxx)
    event_type TEXT NOT NULL,             -- e.g., 'customer.subscription.updated'
    processed_at TIMESTAMPTZ DEFAULT NOW(),
    -- Optional: store key data for debugging
    customer_id TEXT,
    subscription_id TEXT,
    user_id TEXT REFERENCES users(id)
);

-- Index for cleanup queries (delete events older than 90 days)
CREATE INDEX IF NOT EXISTS idx_stripe_events_processed_at ON stripe_events(processed_at);

-- Cleanup old events (call periodically or via pg_cron)
-- DELETE FROM stripe_events WHERE processed_at < NOW() - INTERVAL '90 days';

-- ============================================================
-- 3. Add billing period tracking to users table
-- ============================================================

-- Add Stripe subscription and billing period columns
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT,
    ADD COLUMN IF NOT EXISTS stripe_price_id TEXT,
    ADD COLUMN IF NOT EXISTS stripe_subscription_status TEXT DEFAULT 'none',  -- none, active, past_due, canceled, etc.
    ADD COLUMN IF NOT EXISTS stripe_current_period_start TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS stripe_current_period_end TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS usage_reset_at TIMESTAMPTZ;  -- Last time usage counters were reset

-- Index for finding users by subscription
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_stripe_subscription ON users(stripe_subscription_id) WHERE stripe_subscription_id IS NOT NULL;

-- ============================================================
-- 4. Update subscription_tiers with correct mid-market pricing
-- ============================================================

-- Update existing tiers to match mid-market pricing
UPDATE subscription_tiers SET
    price_monthly_cents = 0,
    tasks_per_month = 10,
    concurrency_limit = 1,
    max_runtime_seconds = 600,
    features = '["basic_templates", "email_results"]'::jsonb
WHERE id = 'free';

UPDATE subscription_tiers SET
    price_monthly_cents = 29700,  -- $297
    tasks_per_month = 300,
    concurrency_limit = 3,
    max_runtime_seconds = 1800,  -- 30 min
    features = '["all_templates", "email_results", "priority_queue", "api_access", "webhook_notifications"]'::jsonb
WHERE id = 'pro';

UPDATE subscription_tiers SET
    price_monthly_cents = 49700,  -- $497
    tasks_per_month = 2000,
    concurrency_limit = 10,
    max_runtime_seconds = 3600,  -- 60 min
    features = '["all_templates", "email_results", "priority_queue", "api_access", "webhook_notifications", "custom_templates", "dedicated_support", "white_label"]'::jsonb
WHERE id = 'agency';

-- ============================================================
-- 5. Function to sync user tier from Stripe subscription
-- ============================================================

CREATE OR REPLACE FUNCTION sync_user_tier_from_stripe(
    p_user_id TEXT,
    p_stripe_customer_id TEXT,
    p_stripe_subscription_id TEXT,
    p_stripe_price_id TEXT,
    p_subscription_status TEXT,
    p_current_period_start TIMESTAMPTZ,
    p_current_period_end TIMESTAMPTZ
)
RETURNS VOID AS $$
DECLARE
    v_tier_id TEXT;
    v_old_period_start TIMESTAMPTZ;
    v_tier_limits RECORD;
BEGIN
    -- Get tier from price map (default to 'free' if not found)
    SELECT tier_id INTO v_tier_id
    FROM stripe_price_map
    WHERE price_id = p_stripe_price_id AND is_active = TRUE;
    
    -- If no active price found or subscription canceled, default to free
    IF v_tier_id IS NULL OR p_subscription_status IN ('canceled', 'unpaid', 'incomplete_expired') THEN
        v_tier_id := 'free';
    END IF;
    
    -- Get the user's old period start to detect billing cycle change
    SELECT stripe_current_period_start INTO v_old_period_start
    FROM users WHERE id = p_user_id;
    
    -- Get tier limits
    SELECT tasks_per_month, concurrency_limit, max_runtime_seconds
    INTO v_tier_limits
    FROM subscription_tiers WHERE id = v_tier_id;
    
    -- Update user with Stripe data and tier limits
    UPDATE users SET
        stripe_customer_id = COALESCE(p_stripe_customer_id, stripe_customer_id),
        stripe_subscription_id = p_stripe_subscription_id,
        stripe_price_id = p_stripe_price_id,
        stripe_subscription_status = p_subscription_status,
        stripe_current_period_start = p_current_period_start,
        stripe_current_period_end = p_current_period_end,
        tier_id = v_tier_id,
        -- Copy limits from tier
        tasks_limit = v_tier_limits.tasks_per_month,
        concurrency_limit = v_tier_limits.concurrency_limit,
        max_runtime_seconds = v_tier_limits.max_runtime_seconds,
        updated_at = NOW()
    WHERE id = p_user_id;
    
    -- Reset usage counters if billing period changed
    -- (different period start than before, and it's a new period)
    IF v_old_period_start IS DISTINCT FROM p_current_period_start 
       AND p_current_period_start IS NOT NULL THEN
        UPDATE users SET
            tasks_used_this_month = 0,
            agent_minutes_used_this_month = 0,
            usage_reset_at = NOW()
        WHERE id = p_user_id;
        
        RAISE NOTICE 'Reset usage counters for user % (new billing period)', p_user_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 6. Function to check if event was already processed (idempotency)
-- ============================================================

CREATE OR REPLACE FUNCTION is_stripe_event_processed(p_event_id TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (SELECT 1 FROM stripe_events WHERE event_id = p_event_id);
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 7. Function to mark event as processed
-- ============================================================

CREATE OR REPLACE FUNCTION mark_stripe_event_processed(
    p_event_id TEXT,
    p_event_type TEXT,
    p_customer_id TEXT DEFAULT NULL,
    p_subscription_id TEXT DEFAULT NULL,
    p_user_id TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO stripe_events (event_id, event_type, customer_id, subscription_id, user_id)
    VALUES (p_event_id, p_event_type, p_customer_id, p_subscription_id, p_user_id)
    ON CONFLICT (event_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 8. Function to check user limits before task creation
-- ============================================================

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
        u.stripe_subscription_status
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

-- ============================================================
-- 9. View for user billing status (useful for dashboard)
-- ============================================================

CREATE OR REPLACE VIEW user_billing_status AS
SELECT 
    u.id as user_id,
    u.email,
    u.tier_id,
    st.name as tier_name,
    st.price_monthly_cents,
    u.stripe_subscription_status,
    u.stripe_current_period_end,
    u.tasks_used_this_month,
    u.tasks_limit,
    ROUND(100.0 * u.tasks_used_this_month / NULLIF(u.tasks_limit, 0), 1) as tasks_used_percent,
    (SELECT COUNT(*) FROM task_runs tr WHERE tr.user_id = u.id AND tr.status = 'running') as running_tasks,
    u.concurrency_limit,
    u.usage_reset_at,
    u.created_at
FROM users u
LEFT JOIN subscription_tiers st ON u.tier_id = st.id;

-- ============================================================
-- Comments for documentation
-- ============================================================

COMMENT ON TABLE stripe_price_map IS 'Maps Stripe price_ids to internal tier_ids. Add new prices without code deploy.';
COMMENT ON TABLE stripe_events IS 'Tracks processed Stripe webhook events for idempotency. Clean up events older than 90 days.';
COMMENT ON FUNCTION sync_user_tier_from_stripe IS 'Updates user tier and limits from Stripe subscription data. Resets usage on billing period change.';
COMMENT ON FUNCTION check_user_task_limits IS 'Checks if user can create a new task. Returns allowed=false with reason if limits exceeded.';
