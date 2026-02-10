-- Migration 018: Autonomous Decision Audit Trail
--
-- Backs the marketing claim: "Every autonomous decision is audit-logged"
-- Central table that records all proactive/autonomous decisions made by
-- the rule engine, perpetual loops, and Ralph.

BEGIN;

CREATE TABLE IF NOT EXISTS autonomous_decisions (
    id                  TEXT PRIMARY KEY,
    tenant_id           TEXT REFERENCES tenants(id),
    user_id             TEXT,

    -- What system made the decision
    source              TEXT NOT NULL CHECK (source IN (
        'rule_engine', 'perpetual_loop', 'ralph', 'health_monitor', 'cron_scheduler'
    )),

    -- What decision was made
    decision_type       TEXT NOT NULL,   -- e.g. 'trigger_rule', 'dispatch_iteration', 'downgrade_model'
    description         TEXT NOT NULL DEFAULT '',

    -- Context and justification
    trigger_data        JSONB DEFAULT '{}'::jsonb,
    decision_data       JSONB DEFAULT '{}'::jsonb,

    -- Outcome tracking
    task_id             TEXT,            -- FK to the task created (if any)
    outcome             TEXT DEFAULT 'pending'
                        CHECK (outcome IN ('pending', 'success', 'failed', 'skipped')),

    -- Cost attribution
    cost_cents          INTEGER DEFAULT 0,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_autonomous_decisions_tenant ON autonomous_decisions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_autonomous_decisions_source ON autonomous_decisions(source);
CREATE INDEX IF NOT EXISTS idx_autonomous_decisions_created ON autonomous_decisions(created_at);

COMMIT;
