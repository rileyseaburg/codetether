"""
Ralph API - Server-side autonomous development loop.

Provides endpoints to run Ralph (PRD-driven development) as a background task,
enabling automation via Zapier, API calls, or scheduled jobs.

Data is persisted to PostgreSQL for durability across restarts.
"""

import asyncio
import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from enum import Enum
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import database as db
from .monitor_api import get_agent_bridge

logger = logging.getLogger(__name__)

# Router for Ralph endpoints
ralph_router = APIRouter(prefix='/v1/ralph', tags=['ralph'])


# ============================================================================
# Models
# ============================================================================


class StoryStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    PASSED = 'passed'
    FAILED = 'failed'
    SKIPPED = 'skipped'


class RunStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class UserStory(BaseModel):
    """A user story in a PRD."""

    id: str
    title: str
    description: str
    acceptance_criteria: List[str] = Field(
        alias='acceptanceCriteria', default_factory=list
    )
    priority: int = 1

    class Config:
        populate_by_name = True


class PRD(BaseModel):
    """Product Requirements Document."""

    project: str
    branch_name: str = Field(alias='branchName')
    description: str
    user_stories: List[UserStory] = Field(alias='userStories')

    class Config:
        populate_by_name = True


class RalphRunCreate(BaseModel):
    """Request to create a new Ralph run."""

    prd: PRD
    codebase_id: Optional[str] = None
    model: Optional[str] = None
    max_iterations: int = Field(default=10, ge=1, le=50)
    run_mode: str = Field(
        default='sequential', pattern='^(sequential|parallel)$'
    )
    max_parallel: int = Field(default=3, ge=1, le=10)


class StoryResult(BaseModel):
    """Result of a single story execution."""

    story_id: str
    status: StoryStatus
    task_id: Optional[str] = None
    iteration: int = 1
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class RalphRun(BaseModel):
    """A Ralph run instance."""

    id: str
    prd: PRD
    codebase_id: Optional[str]
    model: Optional[str]
    status: RunStatus
    max_iterations: int
    current_iteration: int = 0
    run_mode: str
    max_parallel: int
    story_results: List[StoryResult] = []
    logs: List[Dict[str, Any]] = []
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


# In-memory task handles for cancellation (run data is in database)
_ralph_tasks: Dict[str, asyncio.Task] = {}

# Flag to track if recovery has been run
_recovery_started = False


# ============================================================================
# Helper Functions
# ============================================================================


def generate_uuid() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def add_log_to_db(
    run_id: str, log_type: str, message: str, story_id: Optional[str] = None
):
    """Add a log entry to a run (persisted to database)."""
    await db.db_add_ralph_log(run_id, log_type, message, story_id)


def db_run_to_model(db_run: Dict[str, Any]) -> RalphRun:
    """Convert a database row to a RalphRun model."""
    # Parse story results from DB format
    story_results = []
    for sr in db_run.get('story_results') or []:
        story_results.append(
            StoryResult(
                story_id=sr.get('story_id', ''),
                status=StoryStatus(sr.get('status', 'pending')),
                task_id=sr.get('task_id'),
                iteration=sr.get('iteration', 1),
                result=sr.get('result'),
                error=sr.get('error'),
                started_at=sr.get('started_at'),
                completed_at=sr.get('completed_at'),
            )
        )

    # Parse PRD from DB
    prd_data = db_run.get('prd', {})
    user_stories = []
    for us in prd_data.get('userStories', prd_data.get('user_stories', [])):
        user_stories.append(
            UserStory(
                id=us.get('id', ''),
                title=us.get('title', ''),
                description=us.get('description', ''),
                acceptanceCriteria=us.get(
                    'acceptanceCriteria', us.get('acceptance_criteria', [])
                ),
                priority=us.get('priority', 1),
            )
        )

    prd = PRD(
        project=prd_data.get('project', ''),
        branchName=prd_data.get('branchName', prd_data.get('branch_name', '')),
        description=prd_data.get('description', ''),
        userStories=user_stories,
    )

    # Parse timestamps
    created_at = db_run.get('created_at')
    if created_at is not None and hasattr(created_at, 'isoformat'):
        created_at = created_at.isoformat()
    elif created_at is None:
        created_at = now_iso()
    else:
        created_at = str(created_at)

    started_at = db_run.get('started_at')
    if started_at is not None and hasattr(started_at, 'isoformat'):
        started_at = started_at.isoformat()
    elif started_at is not None:
        started_at = str(started_at)

    completed_at = db_run.get('completed_at')
    if completed_at is not None and hasattr(completed_at, 'isoformat'):
        completed_at = completed_at.isoformat()
    elif completed_at is not None:
        completed_at = str(completed_at)

    return RalphRun(
        id=db_run.get('id', ''),
        prd=prd,
        codebase_id=db_run.get('codebase_id'),
        model=db_run.get('model'),
        status=RunStatus(db_run.get('status', 'pending')),
        max_iterations=db_run.get('max_iterations', 10),
        current_iteration=db_run.get('current_iteration', 0),
        run_mode=db_run.get('run_mode', 'sequential'),
        max_parallel=db_run.get('max_parallel', 3),
        story_results=story_results,
        logs=db_run.get('logs') or [],
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        error=db_run.get('error'),
    )


async def create_story_task(
    run: RalphRun,
    story: UserStory,
    iteration: int,
) -> Optional[str]:
    """Create an A2A task for a user story."""
    bridge = get_agent_bridge()
    if not bridge:
        raise HTTPException(
            status_code=503, detail='Agent bridge not available'
        )

    # Build the prompt
    criteria_list = '\n'.join(f'- {c}' for c in story.acceptance_criteria)
    prompt = f"""## Ralph Autonomous Development - {story.id}

**Project:** {run.prd.project}
**Branch:** {run.prd.branch_name}
**Iteration:** {iteration}/{run.max_iterations}

### User Story: {story.title}

{story.description}

### Acceptance Criteria
{criteria_list}

### Instructions
1. Implement this user story to satisfy ALL acceptance criteria
2. Run any necessary tests or type checks
3. If all criteria pass, respond with "STORY_COMPLETE"
4. If blocked, respond with "STORY_BLOCKED: <reason>"
5. Commit your changes with a meaningful message

Do NOT ask for clarification - make reasonable assumptions and proceed.
"""

    # Use the effective codebase_id
    effective_codebase_id = run.codebase_id or 'global'

    # Build metadata
    metadata = {
        'ralph': True,
        'ralph_run_id': run.id,
        'story_id': story.id,
        'iteration': iteration,
    }
    if run.model:
        metadata['model'] = run.model

    # Create the task
    task = await bridge.create_task(
        codebase_id=effective_codebase_id,
        title=f'Ralph: {story.id} - {story.title}',
        prompt=prompt,
        agent_type='build',
        priority=10 - story.priority,
        metadata=metadata,
    )

    if not task:
        return None

    # Handle both dict and object responses
    if isinstance(task, dict):
        return task.get('id')
    return getattr(task, 'id', None)


async def wait_for_task(
    task_id: str, timeout_seconds: int = 600
) -> Dict[str, Any]:
    """Wait for a task to complete."""
    bridge = get_agent_bridge()
    if not bridge:
        return {'success': False, 'result': 'Agent bridge not available'}

    start_time = asyncio.get_event_loop().time()
    consecutive_failures = 0
    max_consecutive_failures = 30  # Give up after 30 consecutive failures (60s)

    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout_seconds:
            return {'success': False, 'result': 'Task timed out'}

        task = await bridge.get_task(task_id)
        if not task:
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                logger.warning(
                    f'Task {task_id}: {consecutive_failures} consecutive failures fetching task, giving up'
                )
                return {
                    'success': False,
                    'result': f'Failed to fetch task status after {consecutive_failures} attempts',
                }
            await asyncio.sleep(2)
            continue

        # Reset failure counter on successful fetch
        consecutive_failures = 0

        # Handle both dict and object responses
        if isinstance(task, dict):
            status = task.get('status')
            result_val = task.get('result', '')
            error_val = task.get('error', 'Task failed')
        else:
            status = getattr(task, 'status', None)
            result_val = getattr(task, 'result', '') or ''
            error_val = getattr(task, 'error', 'Task failed') or 'Task failed'

        if status == 'completed':
            success = (
                'STORY_COMPLETE' in result_val
                or 'STORY_BLOCKED' not in result_val
            )
            return {'success': success, 'result': result_val}
        elif status == 'failed':
            return {'success': False, 'result': error_val}
        elif status == 'cancelled':
            return {'success': False, 'result': 'Task cancelled'}

        await asyncio.sleep(2)


async def run_ralph_sequential(run_id: str, run_data: Dict[str, Any]):
    """Run Ralph loop sequentially with database persistence."""
    prd = run_data.get('prd', {})
    project = prd.get('project', 'Unknown')
    branch = prd.get('branchName', prd.get('branch_name', ''))
    user_stories = prd.get('userStories', prd.get('user_stories', []))
    max_iterations = run_data.get('max_iterations', 10)

    await add_log_to_db(run_id, 'info', f'Starting Ralph loop for {project}')
    await add_log_to_db(run_id, 'info', f'Branch: {branch}')
    await add_log_to_db(run_id, 'info', f'Stories: {len(user_stories)}')
    await add_log_to_db(run_id, 'info', 'Mode: sequential')

    # Get current story results from DB
    story_results = run_data.get('story_results') or []

    for iteration in range(1, max_iterations + 1):
        # Update current iteration in DB
        await db.db_update_ralph_run(run_id, current_iteration=iteration)

        # Find next incomplete story
        passed_story_ids = {
            r.get('story_id')
            for r in story_results
            if r.get('status') == 'passed'
        }
        pending_stories = [
            s for s in user_stories if s.get('id') not in passed_story_ids
        ]

        if not pending_stories:
            await add_log_to_db(run_id, 'complete', 'All stories complete!')
            break

        story = pending_stories[0]
        story_id = story.get('id', '')
        story_title = story.get('title', '')

        await add_log_to_db(
            run_id,
            'story_start',
            f'Starting {story_id}: {story_title}',
            story_id,
        )

        # Create story result
        story_result = {
            'story_id': story_id,
            'status': 'running',
            'iteration': iteration,
            'started_at': now_iso(),
        }
        story_results.append(story_result)
        await db.db_update_ralph_run(run_id, story_results=story_results)

        # Build a minimal run object for create_story_task
        run_obj = db_run_to_model(run_data)

        try:
            # Create task
            await add_log_to_db(
                run_id, 'info', f'Creating task for {story_id}...', story_id
            )

            # Build UserStory for create_story_task
            story_obj = UserStory(
                id=story_id,
                title=story_title,
                description=story.get('description', ''),
                acceptanceCriteria=story.get(
                    'acceptanceCriteria', story.get('acceptance_criteria', [])
                ),
                priority=story.get('priority', 1),
            )
            task_id = await create_story_task(run_obj, story_obj, iteration)

            if not task_id:
                story_result['status'] = 'failed'
                story_result['error'] = 'Failed to create task'
                story_result['completed_at'] = now_iso()
                await db.db_update_ralph_run(
                    run_id, story_results=story_results
                )
                await add_log_to_db(
                    run_id,
                    'error',
                    f'Failed to create task for {story_id}',
                    story_id,
                )
                continue

            story_result['task_id'] = task_id
            await db.db_update_ralph_run(run_id, story_results=story_results)
            await add_log_to_db(
                run_id, 'info', f'Task created: {task_id}', story_id
            )

            # Wait for completion
            result = await wait_for_task(task_id)
            story_result['result'] = result.get('result', '')
            story_result['completed_at'] = now_iso()

            if result['success']:
                story_result['status'] = 'passed'
                await add_log_to_db(
                    run_id, 'story_pass', f'{story_id} PASSED!', story_id
                )
            else:
                story_result['status'] = 'failed'
                story_result['error'] = result.get('result', 'Unknown error')
                await add_log_to_db(
                    run_id,
                    'story_fail',
                    f'{story_id} FAILED: {story_result["error"][:200]}',
                    story_id,
                )

            await db.db_update_ralph_run(run_id, story_results=story_results)

        except Exception as e:
            story_result['status'] = 'failed'
            story_result['error'] = str(e)
            story_result['completed_at'] = now_iso()
            await db.db_update_ralph_run(run_id, story_results=story_results)
            await add_log_to_db(
                run_id, 'error', f'Error on {story_id}: {e}', story_id
            )

    # Final status
    passed = sum(1 for r in story_results if r.get('status') == 'passed')
    total = len(user_stories)

    if passed == total:
        await add_log_to_db(
            run_id,
            'complete',
            f'Ralph completed: {passed}/{total} stories passed',
        )
    else:
        await add_log_to_db(
            run_id, 'info', f'Ralph finished: {passed}/{total} stories passed'
        )


async def run_ralph_parallel(run_id: str, run_data: Dict[str, Any]):
    """Run Ralph loop with parallel story execution and database persistence."""
    prd = run_data.get('prd', {})
    project = prd.get('project', 'Unknown')
    branch = prd.get('branchName', prd.get('branch_name', ''))
    user_stories = prd.get('userStories', prd.get('user_stories', []))
    max_parallel = run_data.get('max_parallel', 3)

    await add_log_to_db(run_id, 'info', f'Starting Ralph loop for {project}')
    await add_log_to_db(run_id, 'info', f'Branch: {branch}')
    await add_log_to_db(run_id, 'info', f'Stories: {len(user_stories)}')
    await add_log_to_db(run_id, 'info', f'Mode: parallel (max {max_parallel})')

    semaphore = asyncio.Semaphore(max_parallel)
    story_results = []
    results_lock = asyncio.Lock()

    # Build run object for create_story_task
    run_obj = db_run_to_model(run_data)

    async def run_story(story: Dict[str, Any], iteration: int):
        async with semaphore:
            story_id = story.get('id', '')
            story_title = story.get('title', '')

            story_result = {
                'story_id': story_id,
                'status': 'running',
                'iteration': iteration,
                'started_at': now_iso(),
            }

            async with results_lock:
                story_results.append(story_result)
                await db.db_update_ralph_run(
                    run_id, story_results=story_results
                )

            try:
                await add_log_to_db(
                    run_id,
                    'story_start',
                    f'Starting {story_id}: {story_title}',
                    story_id,
                )

                # Build UserStory object
                story_obj = UserStory(
                    id=story_id,
                    title=story_title,
                    description=story.get('description', ''),
                    acceptanceCriteria=story.get(
                        'acceptanceCriteria',
                        story.get('acceptance_criteria', []),
                    ),
                    priority=story.get('priority', 1),
                )
                task_id = await create_story_task(run_obj, story_obj, iteration)

                if not task_id:
                    story_result['status'] = 'failed'
                    story_result['error'] = 'Failed to create task'
                    story_result['completed_at'] = now_iso()
                    async with results_lock:
                        await db.db_update_ralph_run(
                            run_id, story_results=story_results
                        )
                    return

                story_result['task_id'] = task_id
                async with results_lock:
                    await db.db_update_ralph_run(
                        run_id, story_results=story_results
                    )

                result = await wait_for_task(task_id)
                story_result['result'] = result.get('result', '')
                story_result['completed_at'] = now_iso()

                if result['success']:
                    story_result['status'] = 'passed'
                    await add_log_to_db(
                        run_id, 'story_pass', f'{story_id} PASSED!', story_id
                    )
                else:
                    story_result['status'] = 'failed'
                    story_result['error'] = result.get(
                        'result', 'Unknown error'
                    )
                    await add_log_to_db(
                        run_id, 'story_fail', f'{story_id} FAILED', story_id
                    )

                async with results_lock:
                    await db.db_update_ralph_run(
                        run_id, story_results=story_results
                    )

            except Exception as e:
                story_result['status'] = 'failed'
                story_result['error'] = str(e)
                story_result['completed_at'] = now_iso()
                async with results_lock:
                    await db.db_update_ralph_run(
                        run_id, story_results=story_results
                    )
                await add_log_to_db(
                    run_id, 'error', f'Error on {story_id}: {e}', story_id
                )

    # Run all stories in parallel (with semaphore limiting concurrency)
    tasks = [run_story(s, 1) for s in user_stories]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Final status
    passed = sum(1 for r in story_results if r.get('status') == 'passed')
    total = len(user_stories)

    await add_log_to_db(
        run_id, 'complete', f'Ralph finished: {passed}/{total} stories passed'
    )


async def run_ralph(run_id: str):
    """Background task to run Ralph with database persistence."""
    # Load run from database
    run_data = await db.db_get_ralph_run(run_id)
    if not run_data:
        logger.error(f'Ralph run {run_id} not found in database')
        return

    # Update status to running
    await db.db_update_ralph_run(
        run_id,
        status='running',
        started_at=datetime.now(timezone.utc),
    )

    try:
        run_mode = run_data.get('run_mode', 'sequential')
        if run_mode == 'parallel':
            await run_ralph_parallel(run_id, run_data)
        else:
            await run_ralph_sequential(run_id, run_data)

        # Mark as completed
        await db.db_update_ralph_run(
            run_id,
            status='completed',
            completed_at=datetime.now(timezone.utc),
        )
    except asyncio.CancelledError:
        await db.db_update_ralph_run(
            run_id,
            status='cancelled',
            completed_at=datetime.now(timezone.utc),
        )
        await add_log_to_db(run_id, 'info', 'Ralph run cancelled')
    except Exception as e:
        await db.db_update_ralph_run(
            run_id,
            status='failed',
            error=str(e),
            completed_at=datetime.now(timezone.utc),
        )
        await add_log_to_db(run_id, 'error', f'Ralph run failed: {e}')
        logger.exception(f'Ralph run {run_id} failed')
    finally:
        # Clean up task reference
        _ralph_tasks.pop(run_id, None)


# ============================================================================
# Recovery Functions
# ============================================================================


async def recover_stuck_runs():
    """Recover Ralph runs that were interrupted by server restart.

    This function:
    1. Finds runs with status='running' that have no in-memory task
    2. Checks if their underlying tasks are actually completed/failed
    3. Updates the run status accordingly or resumes the run
    """
    global _recovery_started
    if _recovery_started:
        return
    _recovery_started = True

    logger.info('Ralph: Starting recovery of stuck runs...')

    try:
        # Find all runs marked as 'running' in the database
        running_runs = await db.db_list_ralph_runs(status='running', limit=100)

        if not running_runs:
            logger.info('Ralph: No stuck runs to recover')
            return

        logger.info(f'Ralph: Found {len(running_runs)} potentially stuck runs')

        bridge = get_agent_bridge()

        for db_run in running_runs:
            run_id = db_run.get('id')
            if not run_id:
                continue

            # Skip if we already have an in-memory task for this run
            if run_id in _ralph_tasks:
                continue

            logger.info(f'Ralph: Checking stuck run {run_id}')

            # Check the status of any running story tasks
            story_results = db_run.get('story_results') or []
            needs_resume = False
            updated_results = False

            for story_result in story_results:
                if story_result.get('status') != 'running':
                    continue

                task_id = story_result.get('task_id')
                if not task_id:
                    continue

                # Check task status in the task queue
                if bridge:
                    task = await bridge.get_task(task_id)
                    if task:
                        task_status = (
                            task.get('status')
                            if isinstance(task, dict)
                            else getattr(task, 'status', None)
                        )
                        task_error = (
                            task.get('error')
                            if isinstance(task, dict)
                            else getattr(task, 'error', None)
                        )
                        task_result = (
                            task.get('result')
                            if isinstance(task, dict)
                            else getattr(task, 'result', None)
                        )

                        if task_status == 'completed':
                            # Task completed while we were down
                            success = task_result and (
                                'STORY_COMPLETE' in str(task_result)
                                or 'STORY_BLOCKED' not in str(task_result)
                            )
                            story_result['status'] = (
                                'passed' if success else 'failed'
                            )
                            story_result['result'] = task_result
                            story_result['completed_at'] = now_iso()
                            updated_results = True
                            logger.info(
                                f'Ralph: Story {story_result.get("story_id")} task completed -> {story_result["status"]}'
                            )
                        elif task_status == 'failed':
                            # Task failed while we were down
                            story_result['status'] = 'failed'
                            story_result['error'] = (
                                task_error
                                or 'Task failed during server restart'
                            )
                            story_result['completed_at'] = now_iso()
                            updated_results = True
                            logger.info(
                                f'Ralph: Story {story_result.get("story_id")} task failed'
                            )
                        elif task_status == 'cancelled':
                            story_result['status'] = 'failed'
                            story_result['error'] = 'Task cancelled'
                            story_result['completed_at'] = now_iso()
                            updated_results = True
                            logger.info(
                                f'Ralph: Story {story_result.get("story_id")} task cancelled'
                            )
                        elif task_status in ['pending', 'running', 'queued']:
                            # Task is still running/queued, need to resume monitoring
                            needs_resume = True
                            logger.info(
                                f'Ralph: Story {story_result.get("story_id")} task still {task_status}, will resume'
                            )
                    else:
                        # Task not found - mark as failed
                        story_result['status'] = 'failed'
                        story_result['error'] = (
                            'Task not found after server restart'
                        )
                        story_result['completed_at'] = now_iso()
                        updated_results = True
                        logger.info(
                            f'Ralph: Story {story_result.get("story_id")} task not found, marking failed'
                        )

            # Update story results in database
            if updated_results:
                await db.db_update_ralph_run(
                    run_id, story_results=story_results
                )
                await add_log_to_db(
                    run_id,
                    'info',
                    'Recovered story results after server restart',
                )

            # Check if we should resume or mark as failed
            if needs_resume:
                # Resume the run
                logger.info(f'Ralph: Resuming run {run_id}')
                await add_log_to_db(
                    run_id, 'info', 'Resuming run after server restart'
                )
                task = asyncio.create_task(run_ralph(run_id))
                _ralph_tasks[run_id] = task
            else:
                # Check final status
                passed = sum(
                    1 for r in story_results if r.get('status') == 'passed'
                )
                total = len(
                    db_run.get('prd', {}).get(
                        'userStories',
                        db_run.get('prd', {}).get('user_stories', []),
                    )
                )

                if passed == total:
                    await db.db_update_ralph_run(
                        run_id,
                        status='completed',
                        completed_at=datetime.now(timezone.utc),
                    )
                    await add_log_to_db(
                        run_id,
                        'complete',
                        f'Run completed after recovery: {passed}/{total} passed',
                    )
                    logger.info(f'Ralph: Run {run_id} completed after recovery')
                else:
                    await db.db_update_ralph_run(
                        run_id,
                        status='failed',
                        error='Run interrupted by server restart',
                        completed_at=datetime.now(timezone.utc),
                    )
                    await add_log_to_db(
                        run_id, 'error', 'Run failed after server restart'
                    )
                    logger.info(
                        f'Ralph: Run {run_id} marked as failed after recovery'
                    )

    except Exception as e:
        logger.exception(f'Ralph: Error during recovery: {e}')


# ============================================================================
# API Endpoints
# ============================================================================


@ralph_router.on_event('startup')
async def ralph_startup():
    """Run recovery on server startup."""
    # Schedule recovery to run after a short delay to let the server fully start
    asyncio.create_task(_delayed_recovery())


async def _delayed_recovery():
    """Run recovery after a short delay."""
    await asyncio.sleep(5)  # Wait for database connection to be ready
    await recover_stuck_runs()


@ralph_router.post('/runs', response_model=RalphRun)
async def create_ralph_run(
    request: RalphRunCreate,
    background_tasks: BackgroundTasks,
):
    """Create and start a new Ralph run.

    This starts a background task that will:
    1. Parse the PRD and extract user stories
    2. Create A2A tasks for each story
    3. Monitor task completion
    4. Retry failed stories up to max_iterations

    Returns immediately with the run ID. Poll GET /v1/ralph/runs/{run_id}
    for status updates.
    """
    run_id = generate_uuid()

    # Convert PRD to dict for database storage
    prd_dict = {
        'project': request.prd.project,
        'branchName': request.prd.branch_name,
        'description': request.prd.description,
        'userStories': [
            {
                'id': s.id,
                'title': s.title,
                'description': s.description,
                'acceptanceCriteria': s.acceptance_criteria,
                'priority': s.priority,
            }
            for s in request.prd.user_stories
        ],
    }

    # Create run in database
    db_run = await db.db_create_ralph_run(
        run_id=run_id,
        prd=prd_dict,
        codebase_id=request.codebase_id,
        model=request.model,
        max_iterations=request.max_iterations,
        run_mode=request.run_mode,
        max_parallel=request.max_parallel,
    )

    if not db_run:
        raise HTTPException(
            status_code=500, detail='Failed to create Ralph run in database'
        )

    # Start background task
    task = asyncio.create_task(run_ralph(run_id))
    _ralph_tasks[run_id] = task

    # Convert to response model
    return db_run_to_model(db_run)


@ralph_router.post('/recover')
async def trigger_recovery():
    """Manually trigger recovery of stuck Ralph runs.

    Use this endpoint if runs are stuck after a server restart.
    """
    global _recovery_started
    _recovery_started = False  # Reset so recovery runs again
    await recover_stuck_runs()
    return {'status': 'recovery_complete'}


@ralph_router.get('/runs', response_model=List[RalphRun])
async def list_ralph_runs(
    status: Optional[str] = None,
    limit: int = 50,
):
    """List Ralph runs, optionally filtered by status."""
    db_runs = await db.db_list_ralph_runs(status=status, limit=limit)
    return [db_run_to_model(r) for r in db_runs]


@ralph_router.get('/runs/{run_id}', response_model=RalphRun)
async def get_ralph_run(run_id: str):
    """Get a specific Ralph run by ID."""
    db_run = await db.db_get_ralph_run(run_id)
    if not db_run:
        raise HTTPException(status_code=404, detail='Ralph run not found')
    return db_run_to_model(db_run)


@ralph_router.post('/runs/{run_id}/cancel')
async def cancel_ralph_run(run_id: str):
    """Cancel a running Ralph run."""
    db_run = await db.db_get_ralph_run(run_id)
    if not db_run:
        raise HTTPException(status_code=404, detail='Ralph run not found')

    status = db_run.get('status')
    if status not in ['pending', 'running']:
        raise HTTPException(
            status_code=400,
            detail=f'Cannot cancel run with status {status}',
        )

    # Cancel the background task
    task = _ralph_tasks.get(run_id)
    if task and not task.done():
        task.cancel()

    # Update in database
    await db.db_update_ralph_run(
        run_id,
        status='cancelled',
        completed_at=datetime.now(timezone.utc),
    )
    await add_log_to_db(run_id, 'info', 'Run cancelled by user')

    return {'status': 'cancelled', 'run_id': run_id}


@ralph_router.delete('/runs/{run_id}')
async def delete_ralph_run(run_id: str):
    """Delete a Ralph run from history."""
    db_run = await db.db_get_ralph_run(run_id)
    if not db_run:
        raise HTTPException(status_code=404, detail='Ralph run not found')

    # Cancel if still running
    status = db_run.get('status')
    if status in ['pending', 'running']:
        task = _ralph_tasks.get(run_id)
        if task and not task.done():
            task.cancel()

    # Delete from database
    await db.db_delete_ralph_run(run_id)
    _ralph_tasks.pop(run_id, None)

    return {'status': 'deleted', 'run_id': run_id}


@ralph_router.get('/runs/{run_id}/logs')
async def get_ralph_run_logs(
    run_id: str,
    since: Optional[str] = None,
    limit: int = 100,
):
    """Get logs for a Ralph run.

    Use 'since' timestamp to get only new logs (for polling).
    """
    db_run = await db.db_get_ralph_run(run_id)
    if not db_run:
        raise HTTPException(status_code=404, detail='Ralph run not found')

    logs = db_run.get('logs') or []

    if since:
        logs = [log for log in logs if log.get('timestamp', '') > since]

    return logs[-limit:]


@ralph_router.get('/runs/{run_id}/stream')
async def stream_ralph_run(run_id: str):
    """Stream real-time updates for a Ralph run via Server-Sent Events.

    Events:
    - log: New log entry added
    - status: Run status changed
    - story: Story status updated
    - output: Real-time agent output from running task
    - done: Run completed/failed/cancelled
    """
    # Import task output streams from monitor_api
    from .monitor_api import _task_output_streams

    # Verify run exists
    db_run = await db.db_get_ralph_run(run_id)
    if not db_run:
        raise HTTPException(status_code=404, detail='Ralph run not found')

    async def event_generator():
        last_log_count = 0
        last_status = db_run.get('status')
        last_story_results = json.dumps(db_run.get('story_results') or [])

        # Track output streams for running tasks
        task_output_indices: dict = {}  # {task_id: last_output_index}

        # Send initial state
        yield f'event: status\ndata: {json.dumps({"status": last_status, "run_id": run_id})}\n\n'

        # Send existing logs
        for log in db_run.get('logs') or []:
            yield f'event: log\ndata: {json.dumps(log)}\n\n'
            last_log_count += 1

        # Poll for updates until run completes
        while True:
            await asyncio.sleep(0.5)  # Faster polling for real-time output

            try:
                current_run = await db.db_get_ralph_run(run_id)
                if not current_run:
                    yield f'event: error\ndata: {json.dumps({"error": "Run not found"})}\n\n'
                    break

                current_status = current_run.get('status')
                current_logs = current_run.get('logs') or []
                current_story_results = current_run.get('story_results') or []
                current_story_results_json = json.dumps(current_story_results)

                # Send new logs
                if len(current_logs) > last_log_count:
                    for log in current_logs[last_log_count:]:
                        yield f'event: log\ndata: {json.dumps(log)}\n\n'
                    last_log_count = len(current_logs)

                # Send status change
                if current_status != last_status:
                    yield f'event: status\ndata: {json.dumps({"status": current_status, "run_id": run_id})}\n\n'
                    last_status = current_status

                # Send story updates
                if current_story_results_json != last_story_results:
                    yield f'event: story\ndata: {current_story_results_json}\n\n'
                    last_story_results = current_story_results_json

                # Stream real-time output from running tasks
                for story_result in current_story_results:
                    task_id = story_result.get('task_id')
                    if not task_id:
                        continue

                    # Only stream for running tasks
                    if story_result.get('status') != 'running':
                        # Clean up index when task completes
                        task_output_indices.pop(task_id, None)
                        continue

                    # Initialize index for new tasks
                    if task_id not in task_output_indices:
                        task_output_indices[task_id] = 0

                    # Get new output chunks
                    outputs = _task_output_streams.get(task_id, [])
                    last_idx = task_output_indices[task_id]

                    if len(outputs) > last_idx:
                        for output in outputs[last_idx:]:
                            yield f'event: output\ndata: {json.dumps({"task_id": task_id, "story_id": story_result.get("story_id"), "output": output.get("output", ""), "timestamp": output.get("timestamp", "")})}\n\n'
                        task_output_indices[task_id] = len(outputs)

                # Check if done
                if current_status in ['completed', 'failed', 'cancelled']:
                    yield f'event: done\ndata: {json.dumps({"status": current_status, "run_id": run_id})}\n\n'
                    break

            except Exception as e:
                logger.error(f'Error streaming Ralph run {run_id}: {e}')
                yield f'event: error\ndata: {json.dumps({"error": str(e)})}\n\n'
                break

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


# ============================================================================
# AI PRD Chat Endpoint
# ============================================================================


class PRDChatRequest(BaseModel):
    """Request for PRD chat."""

    message: str
    conversation_id: Optional[str] = 'prd-builder'
    history: Optional[List[Dict[str, str]]] = None
    model: Optional[str] = None
    worker_id: Optional[str] = None  # Route to specific worker
    codebase_id: Optional[str] = None  # Target codebase


class PRDChatResponse(BaseModel):
    """Response from PRD chat."""

    task_id: str
    status: str


PRD_SYSTEM_PROMPT = """You are a helpful assistant that helps users create Product Requirements Documents (PRDs) for software development.

Your role is to:
1. Ask clarifying questions about the feature/project
2. Understand the user's requirements
3. Generate a structured PRD with user stories

When you have enough information, generate a PRD in this JSON format:
```json
{
  "project": "Project Name",
  "branchName": "feature/branch-name",
  "description": "Brief description of the feature",
  "userStories": [
    {
      "id": "US-001",
      "title": "Story title",
      "description": "As a [user], I want [feature] so that [benefit]",
      "acceptanceCriteria": ["Criteria 1", "Criteria 2"],
      "priority": 1
    }
  ]
}
```

Keep responses concise. Ask one or two questions at a time. When ready to generate the PRD, include the JSON block in your response."""


@ralph_router.post('/chat')
async def prd_chat(request: PRDChatRequest):
    """Chat endpoint for AI-assisted PRD generation - creates a task for workers."""
    from .monitor_api import get_agent_bridge

    bridge = get_agent_bridge()
    if not bridge:
        raise HTTPException(
            status_code=500, detail='Agent bridge not available'
        )

    # Build conversation context
    conversation_history = ''
    if request.history:
        for msg in request.history:
            role = 'User' if msg.get('role') == 'user' else 'Assistant'
            conversation_history += f'{role}: {msg.get("content", "")}\n\n'

    prompt = f'{PRD_SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}\nUser: {request.message}'

    # Use provided codebase_id, or None for global tasks
    codebase_id = (
        request.codebase_id
        if request.codebase_id and request.codebase_id != 'global'
        else None
    )

    # Create a session to track PRD chat history
    # Use conversation_id as the session identifier to group related messages
    session_id = request.conversation_id or 'prd-builder'

    # Generate a unique session UUID if codebase_id is provided
    if codebase_id:
        # Check if session exists for this conversation_id + codebase_id
        existing_sessions = await db.db_list_sessions(codebase_id)
        existing_prd_session = None
        for s in existing_sessions:
            if (
                s.get('metadata', {}).get('conversation_id')
                == request.conversation_id
            ):
                existing_prd_session = s
                break

        if existing_prd_session:
            session_id = existing_prd_session.get('id')
        else:
            # Create new session
            session_id = str(uuid.uuid4())
            await db.db_upsert_session(
                {
                    'id': session_id,
                    'codebase_id': codebase_id,
                    'title': f'PRD Chat: {request.message[:50]}',
                    'metadata': {
                        'prd_chat': True,
                        'conversation_id': request.conversation_id
                        or 'prd-builder',
                    },
                }
            )

        # Track this as a PRD chat session (upsert to prd_chat_sessions table)
        if session_id:
            await db.db_upsert_prd_chat_session(
                codebase_id=codebase_id,
                session_id=session_id,
                title=f'PRD Chat: {request.message[:50]}',
            )

        # Store user message in session
        await db.db_upsert_message(
            {
                'id': str(uuid.uuid4()),
                'session_id': session_id,
                'role': 'user',
                'content': request.message,
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
        )

    # Create task for workers to pick up
    metadata = {
        'prd_chat': True,
        'conversation_id': request.conversation_id,
    }
    if codebase_id:
        metadata['session_id'] = session_id
    # If worker_id specified, add to metadata for routing
    if request.worker_id:
        metadata['target_worker_id'] = request.worker_id

    task = await bridge.create_task(
        codebase_id=codebase_id,
        title=f'PRD Chat: {request.message[:50]}',
        prompt=prompt,
        agent_type='general',
        priority=5,
        model=request.model,
        metadata=metadata,
    )

    if not task:
        raise HTTPException(status_code=500, detail='Failed to create task')

    return PRDChatResponse(task_id=task.id, status=task.status.value)


# ============================================================================
# PRD Chat Sessions Endpoint
# ============================================================================


class PRDChatSession(BaseModel):
    """A PRD chat session."""

    id: str
    codebase_id: str
    session_id: str
    title: Optional[str] = None
    message_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PRDChatSessionsResponse(BaseModel):
    """Response for listing PRD chat sessions."""

    sessions: List[PRDChatSession]


@ralph_router.get('/chat/sessions/{codebase_id}')
async def list_prd_chat_sessions(
    codebase_id: str, limit: int = 50
) -> PRDChatSessionsResponse:
    """List PRD chat sessions for a codebase."""
    rows = await db.db_list_prd_chat_sessions(codebase_id, limit)

    sessions = []
    for row in rows:
        created = row.get('created_at')
        updated = row.get('updated_at')
        sessions.append(
            PRDChatSession(
                id=str(row.get('id', '')),
                codebase_id=row.get('codebase_id', ''),
                session_id=row.get('session_id', ''),
                title=row.get('title'),
                message_count=row.get('message_count', 0),
                created_at=created.isoformat() if created else None,
                updated_at=updated.isoformat() if updated else None,
            )
        )

    return PRDChatSessionsResponse(sessions=sessions)
