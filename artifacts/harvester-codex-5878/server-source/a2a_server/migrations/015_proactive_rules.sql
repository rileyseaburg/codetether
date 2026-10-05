-- Migration 015: Proactive Rule Engine
-- Adds tables for event-driven rules, rule execution audit trail, and health checks.
-- These back the marketing claims about proactive agent behavior:
--   "monitoring persona that watches your systems"
--   "every autonomous decision audit-logged"

BEGIN;

-- ============================================================================
-- agent_rules: event-driven / cron / threshold triggers → agent actions
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_rules (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT REFERENCES tenants(id),
    user_id         TEXT,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',

    -- Trigger definition
    trigger_type    TEXT NOT NULL CHECK (trigger_type IN ('event', 'cron', 'threshold')),
    trigger_config  JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- event:     { "event_type": "task.updated", "filter": { "status": "failed" } }
    -- cron:      { "cron_expression": "*/5 * * * *", "timezone": "UTC" }
    -- threshold: { "health_check_id": "...", "condition": "status == 'failed'", "consecutive": 3 }

    -- Action definition (task template, same schema as cronjobs.task_template)
    action          JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- { "prompt": "Investigate...", "worker_personality": "monitor",
    --   "model_ref": "anthropic:claude-sonnet", "priority": 5,
    --   "codebase_id": "...", "agent_type": "explore" }

    -- Safety controls
    enabled         BOOLEAN DEFAULT TRUE,
    cooldown_seconds INTEGER DEFAULT 300,
    last_triggered_at TIMESTAMPTZ,
    trigger_count   INTEGER DEFAULT 0,

    -- Cron-specific (populated by rule engine for cron-type rules)
    next_run_at     TIMESTAMPTZ,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_rules_tenant ON agent_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_rules_trigger_type ON agent_rules(trigger_type) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_agent_rules_next_run ON agent_rules(next_run_at) WHERE enabled = true AND trigger_type = 'cron';

-- ============================================================================
-- agent_rule_runs: audit trail for every autonomous rule trigger
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_rule_runs (
    id              TEXT PRIMARY KEY,
    rule_id         TEXT NOT NULL REFERENCES agent_rules(id) ON DELETE CASCADE,
    tenant_id       TEXT REFERENCES tenants(id),

    -- What triggered it
    trigger_payload JSONB DEFAULT '{}'::jsonb,

    -- What it created
    task_id         TEXT,

    -- Outcome
    status          TEXT NOT NULL DEFAULT 'triggered'
                    CHECK (status IN ('triggered', 'task_created', 'failed', 'cooldown_skipped')),
    error_message   TEXT,

    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_rule_runs_rule ON agent_rule_runs(rule_id);
CREATE INDEX IF NOT EXISTS idx_agent_rule_runs_tenant ON agent_rule_runs(tenant_id);

-- ============================================================================
-- health_checks: configurable system health probes
-- ============================================================================
CREATE TABLE IF NOT EXISTS health_checks (
    id              TEXT PRIMARY KEY,
    tenant_id       TEXT REFERENCES tenants(id),
    user_id         TEXT,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',

    -- Check definition
    check_type      TEXT NOT NULL CHECK (check_type IN ('http', 'db_query', 'metric', 'task_queue')),
    check_config    JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- http:       { "url": "https://...", "method": "GET", "expected_status": 200, "timeout_ms": 5000 }
    -- db_query:   { "query": "SELECT count(*) FROM ...", "threshold_max": 100 }
    -- metric:     { "metric_name": "error_rate", "threshold_max": 0.05 }
    -- task_queue: { "max_pending": 50, "max_stuck": 5 }

    -- Schedule
    interval_seconds INTEGER DEFAULT 300,
    last_checked_at  TIMESTAMPTZ,
    next_check_at    TIMESTAMPTZ,

    -- Current state
    last_status     TEXT DEFAULT 'unknown'
                    CHECK (last_status IN ('unknown', 'healthy', 'degraded', 'failed')),
    last_result     JSONB DEFAULT '{}'::jsonb,
    consecutive_failures INTEGER DEFAULT 0,

    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_checks_tenant ON health_checks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_health_checks_next ON health_checks(next_check_at) WHERE enabled = true;

COMMIT;
