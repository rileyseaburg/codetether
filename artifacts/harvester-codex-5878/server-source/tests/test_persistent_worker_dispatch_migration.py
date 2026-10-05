"""Regression tests for persistent fire-and-forget worker migration."""

from pathlib import Path


SQL = Path('a2a_server/migrations/029_persistent_worker_dispatch.sql').read_text()


def test_fire_and_forget_run_function_exists_with_harvester_signature():
    assert 'CREATE OR REPLACE FUNCTION create_fire_and_forget_run' in SQL
    assert 'p_task_id TEXT' in SQL
    assert 'p_user_id TEXT DEFAULT NULL' in SQL
    assert 'p_tenant_id TEXT DEFAULT NULL' in SQL
    assert 'p_priority INTEGER DEFAULT 0' in SQL
    assert 'p_task_timeout_seconds INTEGER DEFAULT 604800' in SQL
    assert 'p_github_issue_url TEXT DEFAULT NULL' in SQL
    assert "'fire_and_forget'" in SQL
    assert 'INSERT INTO task_runs' in SQL
    assert 'UPDATE tasks' in SQL


def test_extended_claim_and_heartbeat_functions_exist():
    assert 'CREATE OR REPLACE FUNCTION claim_next_task_run_extended' in SQL
    assert 'p_worker_models_supported TEXT[] DEFAULT NULL' in SQL
    assert 'dispatch_mode TEXT' in SQL
    assert 'github_issue_url TEXT' in SQL
    assert 'checkpoint JSONB' in SQL
    assert 'FROM claim_next_task_run' in SQL

    assert 'CREATE OR REPLACE FUNCTION extended_heartbeat' in SQL
    assert 'p_checkpoint_seq INTEGER DEFAULT NULL' in SQL
    assert 'lease_owner IS DISTINCT FROM p_worker_id' in SQL
