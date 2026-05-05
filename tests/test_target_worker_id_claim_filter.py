"""Regression test for target_worker_id claim filter (migration 032)."""

from pathlib import Path


SQL = Path('a2a_server/migrations/032_target_worker_id_claim_filter.sql').read_text()


def test_claim_function_includes_target_worker_id_filter():
    """The claim function must filter by target_worker_id so post-clone tasks
    are only picked up by the worker that has the cloned workspace on disk."""
    assert 'CREATE OR REPLACE FUNCTION claim_next_task_run_extended' in SQL
    assert "t.metadata->>'target_worker_id' IS NULL" in SQL
    assert "t.metadata->>'target_worker_id' = p_worker_id" in SQL


def test_claim_function_preserves_target_agent_name_filter():
    """Existing target_agent_name filter must still be present."""
    assert "t.metadata->>'target_agent_name' IS NULL" in SQL
    assert "t.metadata->>'target_agent_name' = p_agent_name" in SQL


def test_claim_function_preserves_skip_locked():
    """Concurrent-worker safety: SKIP LOCKED must still be present."""
    assert 'FOR UPDATE OF tr SKIP LOCKED' in SQL


def test_claim_function_still_returns_provider_keys():
    """The provider_keys and provider_key_source columns must still be returned."""
    assert 'provider_keys JSONB' in SQL
    assert 'provider_key_source TEXT' in SQL
