"""Regression tests for hosted worker task-run claim migration."""

from pathlib import Path


def test_latest_claim_next_task_run_migration_preserves_hosted_worker_signature():
    sql = Path('a2a_server/migrations/019_restore_task_run_routing_claim.sql').read_text()

    assert 'CREATE OR REPLACE FUNCTION claim_next_task_run' in sql
    assert 'p_worker_id TEXT' in sql
    assert 'p_lease_duration_seconds INTEGER DEFAULT 600' in sql
    assert 'p_worker_agent_name TEXT DEFAULT NULL' in sql
    assert "p_worker_capabilities JSONB DEFAULT '[]'::JSONB" in sql
    assert 'p_worker_models_supported TEXT[] DEFAULT NULL' in sql

    # hosted_worker.py indexes these columns from SELECT * FROM claim_next_task_run(...)
    assert 'target_agent_name TEXT' in sql
    assert 'required_capabilities JSONB' in sql
    assert 'model_ref TEXT' in sql

    # Preserve the routing filters that earlier migrations added.
    assert 'tr.target_agent_name = p_worker_agent_name' in sql
    assert 'p_worker_capabilities @> tr.required_capabilities' in sql
    assert 'tr.model_ref = ANY(p_worker_models_supported)' in sql
