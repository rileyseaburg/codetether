# ruff: noqa: SLF001
import os

import pytest


os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')

from tests.agent_bridge_fixtures import bridge_with_save_result


@pytest.mark.asyncio
async def test_required_persistence_rolls_back_new_task():
    bridge = bridge_with_save_result(False)
    task = await bridge.create_task(
        codebase_id=None,
        title='author review',
        prompt='review',
        task_id='cttask_fixed',
        require_persistence=True,
    )
    assert task is None
    assert 'cttask_fixed' not in bridge._tasks
    assert bridge._codebase_tasks[None] == []


@pytest.mark.asyncio
async def test_required_persistence_rechecks_cached_task():
    bridge = bridge_with_save_result(False)
    cached = object()
    bridge._tasks['cttask_fixed'] = cached
    task = await bridge.create_task(
        codebase_id=None,
        title='author review',
        prompt='review',
        task_id='cttask_fixed',
        require_persistence=True,
    )
    assert task is None


@pytest.mark.asyncio
async def test_non_required_cache_remains_backward_compatible():
    bridge = bridge_with_save_result(False)
    cached = object()
    bridge._tasks['cttask_fixed'] = cached
    task = await bridge.create_task(
        codebase_id=None,
        title='legacy',
        prompt='legacy',
        task_id='cttask_fixed',
    )
    assert task is cached
