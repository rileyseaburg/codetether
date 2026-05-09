-- Migration 031: GitHub App automation policy/provenance audit trail
-- Records issue -> code -> review -> merge decisions made by CodeTether agents.

BEGIN;

CREATE TABLE IF NOT EXISTS github_automation_decisions (
    id                  TEXT PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action              TEXT NOT NULL,
    owner               TEXT NOT NULL DEFAULT '',
    repo                TEXT NOT NULL DEFAULT '',
    pull_number         INTEGER,
    issue_number        INTEGER,
    branch_name         TEXT NOT NULL DEFAULT '',
    head_sha            TEXT NOT NULL DEFAULT '',
    base_sha            TEXT NOT NULL DEFAULT '',
    installation_id     BIGINT,
    actor               TEXT NOT NULL DEFAULT 'codetether-github-app',
    personality         JSONB NOT NULL DEFAULT '{}'::jsonb,
    policy_decision     TEXT NOT NULL CHECK (policy_decision IN ('allow', 'deny')),
    policy_reasons      JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance          JSONB NOT NULL DEFAULT '{}'::jsonb,
    task_id             TEXT,
    github_request_id   TEXT,
    github_status       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_github_automation_decisions_repo_pr
    ON github_automation_decisions(owner, repo, pull_number);
CREATE INDEX IF NOT EXISTS idx_github_automation_decisions_created
    ON github_automation_decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_github_automation_decisions_action
    ON github_automation_decisions(action);

COMMIT;
