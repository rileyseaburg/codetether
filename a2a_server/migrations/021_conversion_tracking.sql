-- Migration 021: Conversion tracking, funnel persistence, orchestration
--
-- Adds tables for:
-- 1. conversion_events — tracking user signups/subscriptions forwarded to marketing systems
-- 2. funnel_state_snapshots — periodic FunnelBrain Thompson Sampling state backups
-- 3. Seed rules for conversion-triggered orchestration

-- ============================================================================
-- 1. Conversion Events
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversion_events (
    id              TEXT PRIMARY KEY,
    event_type      TEXT NOT NULL,           -- signup | trial_start | subscription | subscription_upgrade
    email           TEXT,                     -- user email (stored for attribution)
    user_id         TEXT,                     -- internal user ID
    session_id      TEXT,                     -- browser session for FunnelBrain attribution
    gclid           TEXT,                     -- Google Click ID
    variant_ids     JSONB DEFAULT '{}'::jsonb, -- FunnelBrain variant selections
    value_dollars   NUMERIC(10,2) DEFAULT 0,
    order_id        TEXT,                     -- Stripe subscription/order ID for dedup
    metadata        JSONB DEFAULT '{}'::jsonb,
    funnel_forwarded BOOLEAN DEFAULT FALSE,   -- successfully forwarded to FunnelBrain?
    google_forwarded BOOLEAN DEFAULT FALSE,   -- successfully forwarded to Google Ads?
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversion_events_type ON conversion_events(event_type);
CREATE INDEX IF NOT EXISTS idx_conversion_events_user ON conversion_events(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_conversion_events_created ON conversion_events(created_at);
CREATE INDEX IF NOT EXISTS idx_conversion_events_unfwd
    ON conversion_events(created_at)
    WHERE NOT funnel_forwarded OR NOT google_forwarded;

-- ============================================================================
-- 2. Funnel State Snapshots
-- ============================================================================

CREATE TABLE IF NOT EXISTS funnel_state_snapshots (
    id                TEXT PRIMARY KEY,
    funnel_brain_state JSONB DEFAULT '{}'::jsonb,
    ad_brain_state     JSONB DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_funnel_snapshots_created ON funnel_state_snapshots(created_at);

-- ============================================================================
-- 3. Seed Rules for Conversion-Triggered Orchestration
-- ============================================================================

-- Rule: When a subscription conversion fires, run conversion_spike playbook
INSERT INTO agent_rules (id, name, description, trigger_type, trigger_config, action, enabled, cooldown_seconds, created_at, updated_at)
VALUES (
    'rule-conversion-spike',
    'Conversion Spike Orchestrator',
    'When a subscription conversion is tracked, evaluate whether to scale winning campaigns',
    'event',
    '{"event_name": "conversion.subscription"}'::jsonb,
    '{"type": "orchestrate", "playbook": "conversion_spike"}'::jsonb,
    true,
    3600,
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Rule: When ROAS drops, trigger recovery playbook via orchestrator
INSERT INTO agent_rules (id, name, description, trigger_type, trigger_config, action, enabled, cooldown_seconds, created_at, updated_at)
VALUES (
    'rule-roas-recovery',
    'ROAS Recovery Orchestrator',
    'When ROAS drops below threshold, run multi-step recovery: pause weak campaigns, generate fresh creative',
    'event',
    '{"event_name": "marketing.roas_low"}'::jsonb,
    '{"type": "orchestrate", "playbook": "roas_recovery"}'::jsonb,
    true,
    7200,
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Rule: Weekly creative refresh
INSERT INTO agent_rules (id, name, description, trigger_type, trigger_config, action, enabled, cooldown_seconds, created_at, updated_at)
VALUES (
    'rule-creative-refresh',
    'Weekly Creative Refresh',
    'Every Wednesday, generate fresh video creatives to combat ad fatigue',
    'cron',
    '{"cron_expression": "0 14 * * 3", "timezone": "UTC"}'::jsonb,
    '{"type": "orchestrate", "playbook": "creative_refresh"}'::jsonb,
    true,
    86400,
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Rule: Retry failed conversion forwards daily
INSERT INTO agent_rules (id, name, description, trigger_type, trigger_config, action, enabled, cooldown_seconds, created_at, updated_at)
VALUES (
    'rule-conversion-retry',
    'Retry Failed Conversion Forwards',
    'Daily retry of conversions that failed to forward to FunnelBrain or Google Ads',
    'cron',
    '{"cron_expression": "30 5 * * *", "timezone": "UTC"}'::jsonb,
    '{"type": "conversion_retry"}'::jsonb,
    true,
    86400,
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;
