"""Regression tests for worker codebase routing.

Workers should only receive tasks for codebases they've explicitly registered.
This prevents cross-server task leakage where a worker picks up tasks for
codebases it doesn't have access to.

Key requirements:
1) Workers with specific codebases only get tasks for those codebases.
2) Workers with NO codebases can still receive 'global' and '__pending__' tasks.
3) Workers with NO codebases do NOT receive codebase-specific tasks.
"""

import asyncio
import pytest

from a2a_server.worker_sse import WorkerRegistry


@pytest.fixture
def registry():
    """Create a fresh WorkerRegistry instance."""
    return WorkerRegistry()


@pytest.mark.asyncio
async def test_worker_only_receives_tasks_for_registered_codebases(registry):
    """Workers should only receive tasks for codebases they've registered."""
    queue_a = asyncio.Queue()
    queue_b = asyncio.Queue()

    # Register worker_a with codebase_1
    await registry.register_worker(
        worker_id='worker_a',
        agent_name='Agent A',
        queue=queue_a,
        codebases={'codebase_1'},
    )

    # Register worker_b with codebase_2
    await registry.register_worker(
        worker_id='worker_b',
        agent_name='Agent B',
        queue=queue_b,
        codebases={'codebase_2'},
    )

    # Get workers for codebase_1 - only worker_a should be returned
    workers_for_cb1 = await registry.get_available_workers(
        codebase_id='codebase_1'
    )
    worker_ids_cb1 = {w.worker_id for w in workers_for_cb1}
    assert worker_ids_cb1 == {'worker_a'}, (
        f'Expected only worker_a for codebase_1, got {worker_ids_cb1}'
    )

    # Get workers for codebase_2 - only worker_b should be returned
    workers_for_cb2 = await registry.get_available_workers(
        codebase_id='codebase_2'
    )
    worker_ids_cb2 = {w.worker_id for w in workers_for_cb2}
    assert worker_ids_cb2 == {'worker_b'}, (
        f'Expected only worker_b for codebase_2, got {worker_ids_cb2}'
    )


@pytest.mark.asyncio
async def test_all_workers_receive_global_tasks(registry):
    """All workers should receive 'global' tasks regardless of registered codebases."""
    queue_a = asyncio.Queue()
    queue_b = asyncio.Queue()

    await registry.register_worker(
        worker_id='worker_a',
        agent_name='Agent A',
        queue=queue_a,
        codebases={'codebase_1'},
    )

    await registry.register_worker(
        worker_id='worker_b',
        agent_name='Agent B',
        queue=queue_b,
        codebases={'codebase_2'},
    )

    # Get workers for global tasks - both workers should be returned
    workers_for_global = await registry.get_available_workers(
        codebase_id='global'
    )
    worker_ids_global = {w.worker_id for w in workers_for_global}
    assert worker_ids_global == {'worker_a', 'worker_b'}, (
        f'Expected both workers for global, got {worker_ids_global}'
    )

    # Same for __pending__ tasks
    workers_for_pending = await registry.get_available_workers(
        codebase_id='__pending__'
    )
    worker_ids_pending = {w.worker_id for w in workers_for_pending}
    assert worker_ids_pending == {'worker_a', 'worker_b'}, (
        f'Expected both workers for __pending__, got {worker_ids_pending}'
    )


@pytest.mark.asyncio
async def test_worker_with_no_codebases_does_not_get_specific_tasks(registry):
    """Workers with NO codebases should NOT receive codebase-specific tasks.

    This is the key regression test for the bug where empty codebases was
    incorrectly treated as "can handle anything".
    """
    queue_empty = asyncio.Queue()
    queue_specific = asyncio.Queue()

    # Register a worker with NO codebases
    await registry.register_worker(
        worker_id='worker_empty',
        agent_name='Agent Empty',
        queue=queue_empty,
        codebases=set(),  # Explicitly empty
    )

    # Register a worker WITH codebase_1
    await registry.register_worker(
        worker_id='worker_specific',
        agent_name='Agent Specific',
        queue=queue_specific,
        codebases={'codebase_1'},
    )

    # Get workers for codebase_1 - only worker_specific should be returned
    workers_for_cb1 = await registry.get_available_workers(
        codebase_id='codebase_1'
    )
    worker_ids_cb1 = {w.worker_id for w in workers_for_cb1}
    assert worker_ids_cb1 == {'worker_specific'}, (
        f'Expected only worker_specific for codebase_1, got {worker_ids_cb1}. '
        f'Workers with empty codebases should NOT receive codebase-specific tasks.'
    )

    # Worker with empty codebases should still get global tasks
    workers_for_global = await registry.get_available_workers(
        codebase_id='global'
    )
    worker_ids_global = {w.worker_id for w in workers_for_global}
    assert 'worker_empty' in worker_ids_global, (
        f'Expected worker_empty for global tasks, got {worker_ids_global}'
    )


@pytest.mark.asyncio
async def test_worker_with_multiple_codebases(registry):
    """Workers with multiple codebases should receive tasks for any of them."""
    queue = asyncio.Queue()

    await registry.register_worker(
        worker_id='worker_multi',
        agent_name='Agent Multi',
        queue=queue,
        codebases={'codebase_1', 'codebase_2', 'codebase_3'},
    )

    for codebase_id in ['codebase_1', 'codebase_2', 'codebase_3']:
        workers = await registry.get_available_workers(codebase_id=codebase_id)
        worker_ids = {w.worker_id for w in workers}
        assert 'worker_multi' in worker_ids, (
            f'Expected worker_multi for {codebase_id}, got {worker_ids}'
        )

    # Should NOT get tasks for unregistered codebases
    workers_for_cb4 = await registry.get_available_workers(
        codebase_id='codebase_4'
    )
    worker_ids_cb4 = {w.worker_id for w in workers_for_cb4}
    assert 'worker_multi' not in worker_ids_cb4, (
        f'worker_multi should NOT receive tasks for codebase_4'
    )


@pytest.mark.asyncio
async def test_busy_workers_excluded_from_available(registry):
    """Busy workers should not be returned by get_available_workers."""
    queue = asyncio.Queue()

    await registry.register_worker(
        worker_id='worker_busy',
        agent_name='Agent Busy',
        queue=queue,
        codebases={'codebase_1'},
    )

    # Initially available
    workers = await registry.get_available_workers(codebase_id='codebase_1')
    assert len(workers) == 1

    # Claim a task to make worker busy
    await registry.claim_task('task_1', 'worker_busy')

    # Now should not be available
    workers = await registry.get_available_workers(codebase_id='codebase_1')
    assert len(workers) == 0

    # Release task
    await registry.release_task('task_1', 'worker_busy')

    # Available again
    workers = await registry.get_available_workers(codebase_id='codebase_1')
    assert len(workers) == 1


@pytest.mark.asyncio
async def test_update_worker_codebases(registry):
    """Workers should be able to update their codebase list after registration."""
    queue = asyncio.Queue()

    await registry.register_worker(
        worker_id='worker_update',
        agent_name='Agent Update',
        queue=queue,
        codebases={'codebase_1'},
    )

    # Initially only handles codebase_1
    workers_cb1 = await registry.get_available_workers(codebase_id='codebase_1')
    workers_cb2 = await registry.get_available_workers(codebase_id='codebase_2')
    assert len(workers_cb1) == 1
    assert len(workers_cb2) == 0

    # Update to handle codebase_2 instead
    await registry.update_worker_codebases('worker_update', {'codebase_2'})

    workers_cb1 = await registry.get_available_workers(codebase_id='codebase_1')
    workers_cb2 = await registry.get_available_workers(codebase_id='codebase_2')
    assert len(workers_cb1) == 0
    assert len(workers_cb2) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
