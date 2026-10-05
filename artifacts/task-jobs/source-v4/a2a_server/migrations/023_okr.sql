-- Migration: OKR (Objectives and Key Results)
-- Adds server-side OKR storage for the dashboard UI.
-- Mirrors the Rust agent's file-based OKR model but persists to PostgreSQL.

CREATE TABLE IF NOT EXISTS okrs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    user_id TEXT,
    objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',  -- draft, approved, running, completed, denied
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_okrs_tenant ON okrs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_okrs_status ON okrs(status);

CREATE TABLE IF NOT EXISTS okr_key_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    okr_id UUID NOT NULL REFERENCES okrs(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'not-started',  -- not-started, in-progress, completed, blocked
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_okr_kr_okr ON okr_key_results(okr_id);

CREATE TABLE IF NOT EXISTS okr_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    okr_id UUID NOT NULL REFERENCES okrs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_okr_runs_okr ON okr_runs(okr_id);
