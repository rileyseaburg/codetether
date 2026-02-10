-- Migration 016: Proactive Persona Swarm Definitions + Permission Scoping
--
-- 1. Adds three builtin proactive personas (monitor, deployer, reviewer)
--    to back the marketing claims about "persona swarms"
-- 2. Adds permission scoping columns to worker_profiles for least-privilege access
--    to back the claim "each agent only has the permissions it needs"

BEGIN;

-- ============================================================================
-- Permission scoping columns on worker_profiles
-- These enforce the marketing claim about scoped permissions per persona.
-- NULL = unrestricted (backward compatible with existing profiles).
-- ============================================================================

ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS allowed_tools JSONB DEFAULT NULL;
-- JSON array of MCP tool names this persona can use, e.g. ["read_file", "grep_search"]
-- NULL means all tools allowed (unrestricted)

ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS allowed_paths JSONB DEFAULT NULL;
-- JSON array of filesystem path prefixes this persona can access, e.g. ["/home/user/project/src"]
-- NULL means all paths allowed (unrestricted)

ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS allowed_namespaces JSONB DEFAULT NULL;
-- JSON array of Kubernetes namespaces this persona can operate in, e.g. ["staging", "monitoring"]
-- NULL means all namespaces allowed (unrestricted)

-- ============================================================================
-- Proactive persona seeds
-- These are the personas referenced on the marketing page:
--   "A monitoring persona that watches your systems."
--   "A deployment persona that manages your staging environment."
--   "A review persona that reads pull requests."
-- ============================================================================

INSERT INTO worker_profiles
    (id, slug, name, description, system_prompt,
     default_capabilities, default_model_tier, default_model_ref,
     default_agent_type, icon, color, is_builtin,
     allowed_tools, allowed_paths, allowed_namespaces)
VALUES
    -- Monitoring Persona
    ('wp-monitor', 'monitor', 'Monitoring Persona',
     'Proactive system health watcher. Analyzes health check results, triages alerts, investigates failures, and recommends or takes corrective action. Runs as a perpetual thought loop.',
     'You are a monitoring agent operating as part of a persona swarm. Your job is to watch system health, analyze anomalies, and take corrective action within your scoped permissions.

Rules:
1. When a health check fails, investigate the root cause before suggesting fixes.
2. Check related systems and logs for cascading failures.
3. If the fix is within your allowed_tools and allowed_paths, apply it directly.
4. If the fix requires elevated permissions, create a detailed incident report and escalate.
5. Always log your reasoning. Every autonomous decision must be traceable.
6. Minimize false positives — do not alert on transient issues unless they persist.
7. You cannot deploy code or modify production infrastructure. You observe and report.',
     '["read_file","grep_search","list_dir","semantic_search"]'::jsonb,
     'fast', NULL, 'explore',
     '👁️', '#0ea5e9', TRUE,
     '["read_file","grep_search","list_dir","semantic_search","run_in_terminal"]'::jsonb,
     NULL,
     '["monitoring","default"]'::jsonb),

    -- Deployment Persona
    ('wp-deployer', 'deployer', 'Deployment Persona',
     'Manages staging environment, validates deployments, runs smoke tests. Scoped to staging namespace only — cannot touch production.',
     'You are a deployment agent operating as part of a persona swarm. Your job is to manage the staging environment: deploy code, run smoke tests, validate health, and report results.

Rules:
1. You are scoped to the staging namespace ONLY. Never attempt production operations.
2. Before deploying, verify the build artifact exists and tests have passed.
3. After deploying, run smoke tests and health checks before reporting success.
4. If deployment fails, roll back automatically and report the failure with logs.
5. Always log your reasoning. Every deployment decision must be auditable.
6. You cannot approve PRs, merge code, or modify CI/CD pipelines.',
     '["deployment","kubernetes","docker","ci_cd","smoke_test"]'::jsonb,
     'balanced', NULL, 'build',
     '🚀', '#f97316', TRUE,
     '["read_file","grep_search","run_in_terminal","list_dir"]'::jsonb,
     NULL,
     '["staging"]'::jsonb),

    -- Code Review Persona (proactive, distinct from the reactive wp-code-reviewer)
    ('wp-reviewer', 'reviewer', 'Review Persona',
     'Proactive pull request reviewer. Reads new PRs, analyzes code changes, provides automated feedback. Runs as a perpetual thought loop watching for new PRs.',
     'You are a code review agent operating as part of a persona swarm. Your job is to proactively review pull requests, analyze code changes, and provide constructive feedback.

Rules:
1. Focus on correctness, security, performance, and maintainability — in that order.
2. Provide specific, actionable feedback with code examples when possible.
3. Flag security vulnerabilities (OWASP Top 10) as high priority.
4. Do not approve PRs — only provide review comments. Humans approve.
5. Be constructive, not pedantic. Ignore style issues that linters should catch.
6. Always log your reasoning. Every review decision must be traceable.
7. You are read-only. You cannot modify code, merge PRs, or push commits.',
     '["code_review","code_analysis","read","search"]'::jsonb,
     'balanced', NULL, 'plan',
     '🔍', '#a855f7', TRUE,
     '["read_file","grep_search","list_dir","semantic_search"]'::jsonb,
     NULL,
     NULL)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    system_prompt = EXCLUDED.system_prompt,
    default_capabilities = EXCLUDED.default_capabilities,
    default_model_tier = EXCLUDED.default_model_tier,
    default_agent_type = EXCLUDED.default_agent_type,
    icon = EXCLUDED.icon,
    color = EXCLUDED.color,
    allowed_tools = EXCLUDED.allowed_tools,
    allowed_paths = EXCLUDED.allowed_paths,
    allowed_namespaces = EXCLUDED.allowed_namespaces,
    updated_at = NOW();

COMMIT;
