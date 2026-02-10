-- Migration: FinOps (Financial Operations) Infrastructure
-- Adds cost alerts, anomaly detection, budget policies, cost allocation tags,
-- and optimization recommendations for multi-tenant token billing.

-- ============================================================
-- 1. Cost Alerts / Spending Notifications
--    Tracks threshold-based alerts per tenant.
-- ============================================================

CREATE TABLE IF NOT EXISTS cost_alerts (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    alert_type TEXT NOT NULL,                     -- 'budget_threshold', 'anomaly', 'balance_low', 'rate_spike'
    severity TEXT NOT NULL DEFAULT 'warning',     -- 'info', 'warning', 'critical'
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    threshold_value NUMERIC,                      -- The threshold that was breached
    actual_value NUMERIC,                         -- The actual value that triggered the alert
    metadata JSONB DEFAULT '{}',                  -- Additional context (model, period, etc.)
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    notified BOOLEAN DEFAULT FALSE,               -- Whether email/webhook was sent
    notified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cost_alerts_tenant ON cost_alerts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_unacked ON cost_alerts(tenant_id, acknowledged) WHERE acknowledged = FALSE;
CREATE INDEX IF NOT EXISTS idx_cost_alerts_type ON cost_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_created ON cost_alerts(created_at DESC);

COMMENT ON TABLE cost_alerts IS 'FinOps cost alerts for threshold breaches, anomalies, and budget warnings.';

-- ============================================================
-- 2. Budget Policies
--    Configurable per-tenant budget rules that trigger alerts or
--    enforcement actions at various thresholds.
-- ============================================================

CREATE TABLE IF NOT EXISTS budget_policies (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    -- What to monitor
    scope TEXT NOT NULL DEFAULT 'tenant',         -- 'tenant', 'user', 'model', 'project'
    scope_filter TEXT,                            -- e.g., user_id or model name (NULL = all)
    period TEXT NOT NULL DEFAULT 'monthly',       -- 'daily', 'weekly', 'monthly'
    -- Thresholds (in cents)
    soft_limit_cents INTEGER,                     -- Warning threshold
    hard_limit_cents INTEGER,                     -- Block threshold
    -- Actions
    action_on_soft TEXT DEFAULT 'alert',          -- 'alert', 'alert+webhook'
    action_on_hard TEXT DEFAULT 'alert',          -- 'alert', 'block', 'alert+block', 'throttle'
    webhook_url TEXT,                             -- Optional webhook for notifications
    -- State
    is_active BOOLEAN DEFAULT TRUE,
    last_evaluated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_budget_policies_tenant ON budget_policies(tenant_id);
CREATE INDEX IF NOT EXISTS idx_budget_policies_active ON budget_policies(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE budget_policies IS 'Configurable budget rules with soft/hard limits and enforcement actions.';

-- ============================================================
-- 3. Cost Allocation Tags
--    Arbitrary key-value tags on token_usage rows for chargeback,
--    project/team attribution, and filtering.
-- ============================================================

ALTER TABLE token_usage
    ADD COLUMN IF NOT EXISTS cost_tags JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS project_id TEXT,
    ADD COLUMN IF NOT EXISTS environment TEXT DEFAULT 'production';  -- 'production', 'staging', 'development'

CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_id) WHERE project_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_token_usage_tags ON token_usage USING GIN (cost_tags);
CREATE INDEX IF NOT EXISTS idx_token_usage_env ON token_usage(environment);

-- ============================================================
-- 4. Daily Cost Snapshots (for trend analysis & forecasting)
--    Pre-aggregated daily roll-ups for fast querying.
-- ============================================================

CREATE TABLE IF NOT EXISTS daily_cost_snapshots (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    snapshot_date DATE NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    -- Aggregated metrics
    request_count INTEGER NOT NULL DEFAULT 0,
    total_input_tokens BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    total_reasoning_tokens BIGINT NOT NULL DEFAULT 0,
    total_cache_read_tokens BIGINT NOT NULL DEFAULT 0,
    total_cache_write_tokens BIGINT NOT NULL DEFAULT 0,
    total_cost_micro_cents BIGINT NOT NULL DEFAULT 0,
    total_base_cost_micro_cents BIGINT NOT NULL DEFAULT 0,
    -- Averages for anomaly detection
    avg_cost_per_request NUMERIC(12, 4),
    avg_tokens_per_request NUMERIC(12, 2),
    max_single_request_cost BIGINT DEFAULT 0,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, snapshot_date, provider, model)
);

CREATE INDEX IF NOT EXISTS idx_daily_snapshots_tenant_date ON daily_cost_snapshots(tenant_id, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_snapshots_date ON daily_cost_snapshots(snapshot_date DESC);

COMMENT ON TABLE daily_cost_snapshots IS 'Daily pre-aggregated cost snapshots for trend analysis and forecasting.';

-- ============================================================
-- 5. Cost Optimization Recommendations
--    Auto-generated suggestions to reduce token spend.
-- ============================================================

CREATE TABLE IF NOT EXISTS cost_recommendations (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    recommendation_type TEXT NOT NULL,    -- 'model_downgrade', 'cache_optimization', 'prompt_reduction', 'batch_consolidation'
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    estimated_savings_percent NUMERIC(5, 2),
    estimated_savings_cents INTEGER,       -- Monthly estimated savings
    current_model TEXT,
    suggested_model TEXT,
    evidence JSONB DEFAULT '{}',          -- Supporting data (usage patterns, cost comparisons)
    status TEXT DEFAULT 'open',           -- 'open', 'accepted', 'dismissed', 'implemented'
    dismissed_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cost_recommendations_tenant ON cost_recommendations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cost_recommendations_open ON cost_recommendations(tenant_id, status) WHERE status = 'open';

COMMENT ON TABLE cost_recommendations IS 'Auto-generated cost optimization recommendations per tenant.';

-- ============================================================
-- 6. Tenant FinOps Configuration (extend tenants table)
-- ============================================================

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS finops_enabled BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS anomaly_sensitivity NUMERIC(3, 1) DEFAULT 2.0,  -- std deviations threshold
    ADD COLUMN IF NOT EXISTS cost_alert_email TEXT,
    ADD COLUMN IF NOT EXISTS cost_alert_webhook TEXT,
    ADD COLUMN IF NOT EXISTS auto_topup_enabled BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS auto_topup_amount_cents INTEGER DEFAULT 2000,     -- $20 default
    ADD COLUMN IF NOT EXISTS auto_topup_threshold_cents INTEGER DEFAULT 500,   -- Trigger when below $5
    ADD COLUMN IF NOT EXISTS daily_snapshot_at TIMESTAMPTZ;                    -- Last snapshot run

-- ============================================================
-- 7. Function: Build daily cost snapshot
-- ============================================================

CREATE OR REPLACE FUNCTION build_daily_snapshot(
    p_tenant_id TEXT,
    p_date DATE DEFAULT CURRENT_DATE - 1
)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    INSERT INTO daily_cost_snapshots (
        tenant_id, snapshot_date, provider, model,
        request_count, total_input_tokens, total_output_tokens,
        total_reasoning_tokens, total_cache_read_tokens, total_cache_write_tokens,
        total_cost_micro_cents, total_base_cost_micro_cents,
        avg_cost_per_request, avg_tokens_per_request, max_single_request_cost
    )
    SELECT
        tenant_id,
        p_date,
        provider,
        model,
        COUNT(*)::INTEGER,
        COALESCE(SUM(input_tokens), 0),
        COALESCE(SUM(output_tokens), 0),
        COALESCE(SUM(reasoning_tokens), 0),
        COALESCE(SUM(cache_read_tokens), 0),
        COALESCE(SUM(cache_write_tokens), 0),
        COALESCE(SUM(cost_micro_cents), 0),
        COALESCE(SUM(base_cost_micro_cents), 0),
        ROUND(AVG(cost_micro_cents)::NUMERIC, 4),
        ROUND(AVG(input_tokens + output_tokens + COALESCE(reasoning_tokens, 0))::NUMERIC, 2),
        MAX(cost_micro_cents)
    FROM token_usage
    WHERE tenant_id = p_tenant_id
      AND created_at >= p_date::TIMESTAMPTZ
      AND created_at < (p_date + 1)::TIMESTAMPTZ
    GROUP BY tenant_id, provider, model
    ON CONFLICT (tenant_id, snapshot_date, provider, model) DO UPDATE SET
        request_count = EXCLUDED.request_count,
        total_input_tokens = EXCLUDED.total_input_tokens,
        total_output_tokens = EXCLUDED.total_output_tokens,
        total_reasoning_tokens = EXCLUDED.total_reasoning_tokens,
        total_cache_read_tokens = EXCLUDED.total_cache_read_tokens,
        total_cache_write_tokens = EXCLUDED.total_cache_write_tokens,
        total_cost_micro_cents = EXCLUDED.total_cost_micro_cents,
        total_base_cost_micro_cents = EXCLUDED.total_base_cost_micro_cents,
        avg_cost_per_request = EXCLUDED.avg_cost_per_request,
        avg_tokens_per_request = EXCLUDED.avg_tokens_per_request,
        max_single_request_cost = EXCLUDED.max_single_request_cost;

    GET DIAGNOSTICS v_count = ROW_COUNT;

    -- Mark tenant snapshot time
    UPDATE tenants SET daily_snapshot_at = NOW() WHERE id = p_tenant_id;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION build_daily_snapshot IS 'Aggregates token_usage into daily_cost_snapshots for fast trend queries.';

-- ============================================================
-- 8. Function: Evaluate budget policies
-- ============================================================

CREATE OR REPLACE FUNCTION evaluate_budget_policies(p_tenant_id TEXT)
RETURNS TABLE (
    policy_id INTEGER,
    policy_name TEXT,
    breached_level TEXT,   -- 'soft' or 'hard'
    current_spend_cents NUMERIC,
    limit_cents INTEGER,
    action TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        bp.id AS policy_id,
        bp.name AS policy_name,
        CASE
            WHEN bp.hard_limit_cents IS NOT NULL AND period_spend >= bp.hard_limit_cents * 10000 THEN 'hard'
            WHEN bp.soft_limit_cents IS NOT NULL AND period_spend >= bp.soft_limit_cents * 10000 THEN 'soft'
        END AS breached_level,
        ROUND(period_spend::NUMERIC / 10000, 2) AS current_spend_cents,
        CASE
            WHEN bp.hard_limit_cents IS NOT NULL AND period_spend >= bp.hard_limit_cents * 10000 THEN bp.hard_limit_cents
            ELSE bp.soft_limit_cents
        END AS limit_cents,
        CASE
            WHEN bp.hard_limit_cents IS NOT NULL AND period_spend >= bp.hard_limit_cents * 10000 THEN bp.action_on_hard
            ELSE bp.action_on_soft
        END AS action
    FROM budget_policies bp
    CROSS JOIN LATERAL (
        SELECT COALESCE(SUM(tu.cost_micro_cents), 0) AS period_spend
        FROM token_usage tu
        WHERE tu.tenant_id = bp.tenant_id
          AND tu.created_at >= CASE bp.period
              WHEN 'daily' THEN date_trunc('day', NOW())
              WHEN 'weekly' THEN date_trunc('week', NOW())
              WHEN 'monthly' THEN date_trunc('month', NOW())
          END
          AND (bp.scope_filter IS NULL OR
               (bp.scope = 'user' AND tu.user_id = bp.scope_filter) OR
               (bp.scope = 'model' AND tu.model = bp.scope_filter) OR
               (bp.scope = 'project' AND tu.project_id = bp.scope_filter))
    ) usage
    WHERE bp.tenant_id = p_tenant_id
      AND bp.is_active = TRUE
      AND (
          (bp.hard_limit_cents IS NOT NULL AND period_spend >= bp.hard_limit_cents * 10000) OR
          (bp.soft_limit_cents IS NOT NULL AND period_spend >= bp.soft_limit_cents * 10000)
      );

    -- Update last evaluated timestamp
    UPDATE budget_policies SET last_evaluated_at = NOW()
    WHERE tenant_id = p_tenant_id AND is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION evaluate_budget_policies IS 'Evaluates all active budget policies for a tenant and returns breached ones.';
