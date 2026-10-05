-- Migration: 014_worker_profiles
-- Creates worker_profiles table for framework-provided and custom worker personalities.

-- Worker profiles define reusable personality configurations that can be
-- assigned to tasks. Framework-provided (builtin) profiles cannot be
-- deleted and serve as sensible defaults.

CREATE TABLE IF NOT EXISTS worker_profiles (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    -- The system-prompt / behavioral instructions for this personality.
    system_prompt   TEXT DEFAULT '',
    -- Comma-separated or JSON array of default capabilities expected.
    default_capabilities JSONB DEFAULT '[]'::jsonb,
    -- Suggested model tier: fast, balanced, heavy
    default_model_tier  TEXT DEFAULT 'balanced',
    -- Specific default model ref (provider:model) when personality is selected.
    default_model_ref   TEXT,
    -- Suggested agent type: build, plan, coder, explore, swarm
    default_agent_type  TEXT DEFAULT 'build',
    -- Visual: icon emoji and accent color for the UI.
    icon            TEXT DEFAULT '🤖',
    color           TEXT DEFAULT '#6366f1',
    -- Framework-provided profiles are is_builtin=true, users cannot delete them.
    is_builtin      BOOLEAN DEFAULT FALSE,
    -- NULL user_id means framework-provided; non-null means user-created.
    user_id         TEXT,
    tenant_id       TEXT REFERENCES tenants(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups by slug and tenant.
CREATE INDEX IF NOT EXISTS idx_worker_profiles_slug ON worker_profiles(slug);
CREATE INDEX IF NOT EXISTS idx_worker_profiles_tenant ON worker_profiles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_worker_profiles_builtin ON worker_profiles(is_builtin);

-- Add profile_id column to workers table so workers can optionally advertise
-- the personality profile they are currently operating under.
ALTER TABLE workers ADD COLUMN IF NOT EXISTS profile_id TEXT REFERENCES worker_profiles(id) ON DELETE SET NULL;

-- Add profile_id column to task_runs so each task records which profile was used.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'task_runs') THEN
        EXECUTE 'ALTER TABLE task_runs ADD COLUMN IF NOT EXISTS profile_id TEXT REFERENCES worker_profiles(id) ON DELETE SET NULL';
    END IF;
END
$$;

-- Seed framework-provided (builtin) profiles.
INSERT INTO worker_profiles (id, slug, name, description, system_prompt, default_capabilities, default_model_tier, default_model_ref, default_agent_type, icon, color, is_builtin)
VALUES
    ('wp-deep-research', 'deep-research', 'Deep Research', 'Thorough analysis with extensive context gathering. Best for complex investigations, architecture reviews, and multi-file understanding.',
     'You are a meticulous researcher. Gather extensive context before answering. Read broadly, cross-reference findings, and produce comprehensive analysis. Prioritize accuracy over speed.',
     '["code_analysis","search","read"]'::jsonb, 'heavy', NULL, 'explore', '🔬', '#7c3aed', TRUE),

    ('wp-fast-fix', 'fast-fix', 'Fast Fix', 'Quick targeted fixes with minimal overhead. Best for typos, small bug patches, and straightforward changes.',
     'You are a fast, focused fixer. Make the minimal correct change. Do not refactor unrelated code. Keep changes small and targeted.',
     '["code_edit","quick_fix"]'::jsonb, 'fast', NULL, 'coder', '⚡', '#f59e0b', TRUE),

    ('wp-backend-specialist', 'backend-specialist', 'Backend Specialist', 'Server-side expertise: APIs, databases, authentication, infrastructure. Fluent in Python, Rust, Go, SQL.',
     'You are a backend engineering specialist. Focus on server-side code, API design, database queries, authentication, and infrastructure. Prefer robust, tested solutions.',
     '["backend","api","database","infrastructure"]'::jsonb, 'balanced', NULL, 'build', '🖧', '#059669', TRUE),

    ('wp-frontend-specialist', 'frontend-specialist', 'Frontend Specialist', 'UI/UX expertise: React, Next.js, CSS, accessibility, responsive design.',
     'You are a frontend specialist. Focus on UI components, styling, accessibility, responsive layouts, and client-side state management. Write clean, reusable components.',
     '["frontend","ui","css","react"]'::jsonb, 'balanced', NULL, 'build', '🎨', '#ec4899', TRUE),

    ('wp-devops', 'devops', 'DevOps Engineer', 'Infrastructure, CI/CD, Docker, Kubernetes, deployment pipelines, monitoring.',
     'You are a DevOps engineer. Focus on infrastructure as code, container orchestration, CI/CD pipelines, monitoring, and deployment automation. Prefer reproducible, declarative configurations.',
     '["devops","docker","kubernetes","ci_cd"]'::jsonb, 'balanced', NULL, 'build', '🚀', '#0891b2', TRUE),

    ('wp-security-auditor', 'security-auditor', 'Security Auditor', 'Security review: vulnerability scanning, dependency auditing, auth patterns, OWASP best practices.',
     'You are a security auditor. Identify vulnerabilities, insecure patterns, and potential attack vectors. Recommend fixes following OWASP guidelines and security best practices. Be thorough and cautious.',
     '["security","audit","code_analysis"]'::jsonb, 'heavy', NULL, 'explore', '🛡️', '#dc2626', TRUE),

    ('wp-code-reviewer', 'code-reviewer', 'Code Reviewer', 'Detailed code review: style, correctness, performance, maintainability. Provides actionable feedback.',
     'You are a senior code reviewer. Examine code for correctness, performance, maintainability, and style. Provide specific, actionable feedback with examples. Be constructive.',
     '["code_review","code_analysis","read"]'::jsonb, 'balanced', NULL, 'plan', '👀', '#8b5cf6', TRUE),

    ('wp-test-writer', 'test-writer', 'Test Writer', 'Test-first development: unit tests, integration tests, E2E tests. Ensures comprehensive coverage.',
     'You are a testing specialist. Write comprehensive tests covering edge cases, error paths, and happy paths. Prefer test-driven development. Ensure high coverage without brittle tests.',
     '["testing","code_edit","code_analysis"]'::jsonb, 'balanced', NULL, 'coder', '🧪', '#16a34a', TRUE),

    ('wp-documentation', 'documentation', 'Documentation Writer', 'Technical writing: READMEs, API docs, inline comments, architecture decision records.',
     'You are a technical writer. Produce clear, concise documentation. Use proper formatting, examples, and cross-references. Target the appropriate audience level.',
     '["documentation","read","code_analysis"]'::jsonb, 'fast', NULL, 'plan', '📝', '#2563eb', TRUE),

    ('wp-refactorer', 'refactorer', 'Refactoring Expert', 'Code restructuring: extract functions, simplify logic, improve naming, reduce duplication.',
     'You are a refactoring expert. Improve code structure without changing behavior. Focus on readability, DRY principles, proper abstractions, and clean architecture.',
     '["refactoring","code_edit","code_analysis"]'::jsonb, 'balanced', NULL, 'build', '♻️', '#ea580c', TRUE)
ON CONFLICT (slug) DO NOTHING;
