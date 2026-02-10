-- Migration: Multi-Tenant Token Billing
-- Adds per-tenant token usage tracking, model pricing registry,
-- tenant credit balances, spending limits, and Stripe metered billing support.

-- ============================================================
-- 1. Model Pricing Registry
--    Stores cost-per-million-tokens for each model.
--    Updated without code deploys. Supports provider overrides.
-- ============================================================

CREATE TABLE IF NOT EXISTS model_pricing (
    id SERIAL PRIMARY KEY,
    provider TEXT NOT NULL,                -- e.g., 'anthropic', 'openai', 'azure-anthropic'
    model TEXT NOT NULL,                   -- e.g., 'claude-opus-4-5', 'gpt-4o'
    input_cost_per_m NUMERIC(12, 6) NOT NULL DEFAULT 0,   -- USD per 1M input tokens
    output_cost_per_m NUMERIC(12, 6) NOT NULL DEFAULT 0,  -- USD per 1M output tokens
    cache_read_cost_per_m NUMERIC(12, 6) DEFAULT 0,       -- USD per 1M cache-read tokens
    cache_write_cost_per_m NUMERIC(12, 6) DEFAULT 0,      -- USD per 1M cache-write tokens
    reasoning_cost_per_m NUMERIC(12, 6),                   -- USD per 1M reasoning tokens (NULL = same as output)
    is_active BOOLEAN DEFAULT TRUE,
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider, model)
);

CREATE INDEX IF NOT EXISTS idx_model_pricing_provider ON model_pricing(provider);
CREATE INDEX IF NOT EXISTS idx_model_pricing_active ON model_pricing(is_active);

-- Seed with common model pricing (USD per 1M tokens, as of 2025)
INSERT INTO model_pricing (provider, model, input_cost_per_m, output_cost_per_m, cache_read_cost_per_m, cache_write_cost_per_m, reasoning_cost_per_m) VALUES
    -- Anthropic
    ('anthropic', 'claude-opus-4-5',      5.00,  25.00,  0.50,  6.25,  NULL),
    ('anthropic', 'claude-sonnet-4',      3.00,  15.00,  0.30,  3.75,  NULL),
    ('anthropic', 'claude-haiku-3-5',     0.80,   4.00,  0.08,  1.00,  NULL),
    ('anthropic', 'claude-sonnet-3-5',    3.00,  15.00,  0.30,  3.75,  NULL),
    -- Azure-hosted Anthropic
    ('azure-anthropic', 'claude-opus-4-5',   5.00, 25.00, 0.50, 6.25, NULL),
    ('azure-anthropic', 'claude-sonnet-4',   3.00, 15.00, 0.30, 3.75, NULL),
    -- OpenAI
    ('openai', 'gpt-4o',                 2.50,  10.00,  NULL,  NULL,  NULL),
    ('openai', 'gpt-4o-mini',            0.15,   0.60,  NULL,  NULL,  NULL),
    ('openai', 'gpt-4.1',               2.00,   8.00,  NULL,  NULL,  NULL),
    ('openai', 'gpt-4.1-mini',          0.40,   1.60,  NULL,  NULL,  NULL),
    ('openai', 'o3',                    2.00,   8.00,  NULL,  NULL,  8.00),
    ('openai', 'o3-mini',              1.10,   4.40,  NULL,  NULL,  4.40),
    -- Google
    ('google', 'gemini-2.5-pro',        1.25,  10.00,  NULL,  NULL,  NULL),
    ('google', 'gemini-2.5-flash',      0.15,   0.60,  NULL,  NULL,  NULL)
ON CONFLICT (provider, model) DO UPDATE SET
    input_cost_per_m = EXCLUDED.input_cost_per_m,
    output_cost_per_m = EXCLUDED.output_cost_per_m,
    cache_read_cost_per_m = EXCLUDED.cache_read_cost_per_m,
    cache_write_cost_per_m = EXCLUDED.cache_write_cost_per_m,
    reasoning_cost_per_m = EXCLUDED.reasoning_cost_per_m,
    updated_at = NOW();

COMMENT ON TABLE model_pricing IS 'Model-level pricing in USD per 1M tokens. Add new models/providers without code deploy.';

-- ============================================================
-- 2. Tenant Token Usage Ledger
--    Immutable append-only ledger of every AI operation.
--    One row per LLM call, scoped to tenant + user.
-- ============================================================

CREATE TABLE IF NOT EXISTS token_usage (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    user_id TEXT REFERENCES users(id),
    -- What was used
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    -- Token counts
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    -- Cost in micro-cents (1 cent = 10,000 micro-cents, for precision)
    cost_micro_cents BIGINT NOT NULL DEFAULT 0,
    -- Context
    session_id TEXT,                       -- opencode session reference
    task_id TEXT,                          -- task reference if from a task
    message_id TEXT,                       -- message reference
    -- Markup applied (tenant-specific)
    markup_percent NUMERIC(5, 2) DEFAULT 0,  -- e.g., 20.00 = 20% markup
    base_cost_micro_cents BIGINT NOT NULL DEFAULT 0,  -- cost before markup
    -- Billing state
    stripe_reported BOOLEAN DEFAULT FALSE, -- whether reported to Stripe metered billing
    stripe_reported_at TIMESTAMPTZ,
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_token_usage_tenant ON token_usage(tenant_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_tenant_created ON token_usage(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_token_usage_user ON token_usage(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_token_usage_session ON token_usage(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_token_usage_unreported ON token_usage(stripe_reported) WHERE stripe_reported = FALSE;

-- Partition-friendly: monthly aggregation is the main query pattern
CREATE INDEX IF NOT EXISTS idx_token_usage_monthly ON token_usage(tenant_id, date_trunc('month', created_at));

COMMENT ON TABLE token_usage IS 'Immutable ledger of per-request AI token consumption, scoped per tenant.';

-- ============================================================
-- 3. Tenant Billing Balances & Configuration
--    Pre-paid credit balance, spending limits, markup config.
-- ============================================================

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS token_balance_micro_cents BIGINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS monthly_spend_limit_cents INTEGER,          -- NULL = unlimited
    ADD COLUMN IF NOT EXISTS monthly_spend_alert_cents INTEGER,          -- NULL = no alert
    ADD COLUMN IF NOT EXISTS token_markup_percent NUMERIC(5, 2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS billing_model TEXT DEFAULT 'subscription',   -- 'subscription', 'prepaid', 'metered'
    ADD COLUMN IF NOT EXISTS stripe_metered_item_id TEXT,                 -- Stripe subscription item for metered billing
    ADD COLUMN IF NOT EXISTS tokens_as_of TIMESTAMPTZ;                   -- Last time balance was reconciled

-- Also add to users table for user-level tracking
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS token_balance_micro_cents BIGINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS monthly_token_spend_micro_cents BIGINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS monthly_token_spend_reset_at TIMESTAMPTZ;

-- ============================================================
-- 4. Monthly Aggregation View (materialized for performance)
-- ============================================================

CREATE OR REPLACE VIEW tenant_token_usage_monthly AS
SELECT
    tenant_id,
    date_trunc('month', created_at) AS month,
    provider,
    model,
    COUNT(*) AS request_count,
    SUM(input_tokens) AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    SUM(reasoning_tokens) AS total_reasoning_tokens,
    SUM(cache_read_tokens) AS total_cache_read_tokens,
    SUM(cache_write_tokens) AS total_cache_write_tokens,
    SUM(input_tokens + output_tokens + COALESCE(reasoning_tokens, 0)) AS total_tokens,
    SUM(cost_micro_cents) AS total_cost_micro_cents,
    SUM(base_cost_micro_cents) AS total_base_cost_micro_cents,
    ROUND(SUM(cost_micro_cents)::NUMERIC / 10000, 2) AS total_cost_dollars
FROM token_usage
GROUP BY tenant_id, date_trunc('month', created_at), provider, model;

COMMENT ON VIEW tenant_token_usage_monthly IS 'Monthly token usage aggregation per tenant, provider, model.';

-- ============================================================
-- 5. Per-user usage view (for user dashboards)
-- ============================================================

CREATE OR REPLACE VIEW user_token_usage_monthly AS
SELECT
    user_id,
    tenant_id,
    date_trunc('month', created_at) AS month,
    provider,
    model,
    COUNT(*) AS request_count,
    SUM(input_tokens + output_tokens + COALESCE(reasoning_tokens, 0)) AS total_tokens,
    SUM(cost_micro_cents) AS total_cost_micro_cents,
    ROUND(SUM(cost_micro_cents)::NUMERIC / 10000, 2) AS total_cost_dollars
FROM token_usage
WHERE user_id IS NOT NULL
GROUP BY user_id, tenant_id, date_trunc('month', created_at), provider, model;

-- ============================================================
-- 6. Function: Calculate cost for a given model + token counts
--    Returns cost in micro-cents (10,000 micro-cents = 1 cent)
-- ============================================================

CREATE OR REPLACE FUNCTION calculate_token_cost(
    p_provider TEXT,
    p_model TEXT,
    p_input_tokens INTEGER,
    p_output_tokens INTEGER,
    p_reasoning_tokens INTEGER DEFAULT 0,
    p_cache_read_tokens INTEGER DEFAULT 0,
    p_cache_write_tokens INTEGER DEFAULT 0,
    p_markup_percent NUMERIC DEFAULT 0
)
RETURNS TABLE (
    base_cost_micro_cents BIGINT,
    markup_micro_cents BIGINT,
    total_cost_micro_cents BIGINT
) AS $$
DECLARE
    v_pricing RECORD;
    v_base BIGINT;
    v_markup BIGINT;
    v_reasoning_rate NUMERIC;
BEGIN
    -- Look up pricing (try exact match first, then prefix match)
    SELECT * INTO v_pricing
    FROM model_pricing
    WHERE provider = p_provider AND model = p_model AND is_active = TRUE
    LIMIT 1;

    -- Fallback: try matching model name without provider prefix
    IF NOT FOUND THEN
        SELECT * INTO v_pricing
        FROM model_pricing
        WHERE model = p_model AND is_active = TRUE
        LIMIT 1;
    END IF;

    -- If still not found, use zero cost (unknown model)
    IF NOT FOUND THEN
        RETURN QUERY SELECT 0::BIGINT, 0::BIGINT, 0::BIGINT;
        RETURN;
    END IF;

    -- Reasoning tokens: use dedicated rate or fall back to output rate
    v_reasoning_rate := COALESCE(v_pricing.reasoning_cost_per_m, v_pricing.output_cost_per_m);

    -- Calculate base cost in micro-cents
    -- Formula: (tokens / 1,000,000) * cost_per_m * 100 (to cents) * 10,000 (to micro-cents)
    -- Simplified: tokens * cost_per_m / 1,000,000 * 1,000,000 = tokens * cost_per_m (in micro-dollars)
    -- Then * 100 for micro-cents ... actually let me be precise:
    -- cost_dollars = tokens * cost_per_m_dollars / 1,000,000
    -- cost_micro_cents = cost_dollars * 100 * 10,000 = cost_dollars * 1,000,000
    -- So: cost_micro_cents = tokens * cost_per_m_dollars  (conveniently!)
    v_base := (
        p_input_tokens::BIGINT * v_pricing.input_cost_per_m +
        p_output_tokens::BIGINT * v_pricing.output_cost_per_m +
        COALESCE(p_reasoning_tokens, 0)::BIGINT * v_reasoning_rate +
        COALESCE(p_cache_read_tokens, 0)::BIGINT * COALESCE(v_pricing.cache_read_cost_per_m, 0) +
        COALESCE(p_cache_write_tokens, 0)::BIGINT * COALESCE(v_pricing.cache_write_cost_per_m, 0)
    )::BIGINT;

    -- Apply markup
    v_markup := (v_base * p_markup_percent / 100)::BIGINT;

    RETURN QUERY SELECT v_base, v_markup, (v_base + v_markup)::BIGINT;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION calculate_token_cost IS 'Calculates token cost in micro-cents using model_pricing registry. 10,000 micro-cents = 1 cent.';

-- ============================================================
-- 7. Function: Record token usage and deduct from balance
--    Atomic: records usage + deducts balance in one transaction
-- ============================================================

CREATE OR REPLACE FUNCTION record_token_usage(
    p_tenant_id TEXT,
    p_user_id TEXT,
    p_provider TEXT,
    p_model TEXT,
    p_input_tokens INTEGER,
    p_output_tokens INTEGER,
    p_reasoning_tokens INTEGER DEFAULT 0,
    p_cache_read_tokens INTEGER DEFAULT 0,
    p_cache_write_tokens INTEGER DEFAULT 0,
    p_session_id TEXT DEFAULT NULL,
    p_task_id TEXT DEFAULT NULL,
    p_message_id TEXT DEFAULT NULL
)
RETURNS TABLE (
    usage_id BIGINT,
    cost_micro_cents BIGINT,
    remaining_balance_micro_cents BIGINT,
    over_limit BOOLEAN
) AS $$
DECLARE
    v_markup NUMERIC;
    v_billing_model TEXT;
    v_monthly_limit INTEGER;
    v_cost_info RECORD;
    v_usage_id BIGINT;
    v_new_balance BIGINT;
    v_monthly_spend BIGINT;
    v_over_limit BOOLEAN := FALSE;
BEGIN
    -- Get tenant config
    SELECT
        COALESCE(t.token_markup_percent, 0),
        COALESCE(t.billing_model, 'subscription'),
        t.monthly_spend_limit_cents
    INTO v_markup, v_billing_model, v_monthly_limit
    FROM tenants t WHERE t.id = p_tenant_id;

    -- Calculate cost
    SELECT * INTO v_cost_info
    FROM calculate_token_cost(
        p_provider, p_model,
        p_input_tokens, p_output_tokens,
        p_reasoning_tokens, p_cache_read_tokens, p_cache_write_tokens,
        v_markup
    );

    -- Insert usage record
    INSERT INTO token_usage (
        tenant_id, user_id, provider, model,
        input_tokens, output_tokens, reasoning_tokens,
        cache_read_tokens, cache_write_tokens,
        cost_micro_cents, base_cost_micro_cents,
        markup_percent, session_id, task_id, message_id
    ) VALUES (
        p_tenant_id, p_user_id, p_provider, p_model,
        p_input_tokens, p_output_tokens, p_reasoning_tokens,
        p_cache_read_tokens, p_cache_write_tokens,
        v_cost_info.total_cost_micro_cents, v_cost_info.base_cost_micro_cents,
        v_markup, p_session_id, p_task_id, p_message_id
    ) RETURNING id INTO v_usage_id;

    -- Deduct from tenant balance (for prepaid model)
    IF v_billing_model = 'prepaid' THEN
        UPDATE tenants
        SET token_balance_micro_cents = token_balance_micro_cents - v_cost_info.total_cost_micro_cents,
            tokens_as_of = NOW()
        WHERE id = p_tenant_id
        RETURNING token_balance_micro_cents INTO v_new_balance;
    ELSE
        SELECT token_balance_micro_cents INTO v_new_balance FROM tenants WHERE id = p_tenant_id;
    END IF;

    -- Deduct from user balance too (if user-level tracking)
    IF p_user_id IS NOT NULL THEN
        UPDATE users
        SET monthly_token_spend_micro_cents = monthly_token_spend_micro_cents + v_cost_info.total_cost_micro_cents
        WHERE id = p_user_id;
    END IF;

    -- Check monthly spend limit
    IF v_monthly_limit IS NOT NULL THEN
        SELECT COALESCE(SUM(tu.cost_micro_cents), 0) INTO v_monthly_spend
        FROM token_usage tu
        WHERE tu.tenant_id = p_tenant_id
          AND tu.created_at >= date_trunc('month', NOW());

        -- Convert limit from cents to micro-cents for comparison
        v_over_limit := v_monthly_spend > (v_monthly_limit::BIGINT * 10000);
    END IF;

    RETURN QUERY SELECT v_usage_id, v_cost_info.total_cost_micro_cents, COALESCE(v_new_balance, 0::BIGINT), v_over_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION record_token_usage IS 'Atomically records token usage and deducts from tenant balance. Returns cost and remaining balance.';

-- ============================================================
-- 8. Function: Check if tenant can afford a request (pre-check)
-- ============================================================

CREATE OR REPLACE FUNCTION check_token_budget(
    p_tenant_id TEXT,
    p_estimated_tokens INTEGER DEFAULT 10000  -- rough estimate for pre-check
)
RETURNS TABLE (
    allowed BOOLEAN,
    reason TEXT,
    balance_micro_cents BIGINT,
    monthly_spend_micro_cents BIGINT,
    monthly_limit_cents INTEGER,
    billing_model TEXT
) AS $$
DECLARE
    v_tenant RECORD;
    v_monthly_spend BIGINT;
BEGIN
    SELECT
        t.token_balance_micro_cents,
        t.monthly_spend_limit_cents,
        COALESCE(t.billing_model, 'subscription') as billing_model
    INTO v_tenant
    FROM tenants t WHERE t.id = p_tenant_id;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Tenant not found'::TEXT, 0::BIGINT, 0::BIGINT, 0, 'unknown'::TEXT;
        RETURN;
    END IF;

    -- Get current month spend
    SELECT COALESCE(SUM(tu.cost_micro_cents), 0) INTO v_monthly_spend
    FROM token_usage tu
    WHERE tu.tenant_id = p_tenant_id
      AND tu.created_at >= date_trunc('month', NOW());

    -- Check prepaid balance
    IF v_tenant.billing_model = 'prepaid' AND v_tenant.token_balance_micro_cents <= 0 THEN
        RETURN QUERY SELECT
            FALSE,
            'Prepaid balance exhausted. Add credits to continue.'::TEXT,
            v_tenant.token_balance_micro_cents,
            v_monthly_spend,
            v_tenant.monthly_spend_limit_cents,
            v_tenant.billing_model;
        RETURN;
    END IF;

    -- Check monthly limit
    IF v_tenant.monthly_spend_limit_cents IS NOT NULL
       AND v_monthly_spend > (v_tenant.monthly_spend_limit_cents::BIGINT * 10000) THEN
        RETURN QUERY SELECT
            FALSE,
            format('Monthly spending limit of $%s reached.', v_tenant.monthly_spend_limit_cents::NUMERIC / 100),
            v_tenant.token_balance_micro_cents,
            v_monthly_spend,
            v_tenant.monthly_spend_limit_cents,
            v_tenant.billing_model;
        RETURN;
    END IF;

    -- All good
    RETURN QUERY SELECT
        TRUE,
        'OK'::TEXT,
        v_tenant.token_balance_micro_cents,
        v_monthly_spend,
        v_tenant.monthly_spend_limit_cents,
        v_tenant.billing_model;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 9. Tenant credit top-up function
-- ============================================================

CREATE OR REPLACE FUNCTION add_tenant_credits(
    p_tenant_id TEXT,
    p_amount_cents INTEGER,   -- amount in cents (e.g., 2000 = $20)
    p_reason TEXT DEFAULT 'manual'
)
RETURNS BIGINT AS $$
DECLARE
    v_micro_cents BIGINT;
    v_new_balance BIGINT;
BEGIN
    v_micro_cents := p_amount_cents::BIGINT * 10000;

    UPDATE tenants
    SET token_balance_micro_cents = token_balance_micro_cents + v_micro_cents,
        tokens_as_of = NOW()
    WHERE id = p_tenant_id
    RETURNING token_balance_micro_cents INTO v_new_balance;

    RETURN v_new_balance;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION add_tenant_credits IS 'Adds credits to tenant balance. Amount in cents (2000 = $20).';
