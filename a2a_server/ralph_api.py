"""
Ralph API - Server-side autonomous development loop.

Provides endpoints to run Ralph (PRD-driven development) as a background task,
enabling automation via Zapier, API calls, or scheduled jobs.
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
from pydantic import BaseModel, Field

from . import database as db
from .opencode_bridge import get_opencode_bridge

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


# In-memory storage for runs (can be moved to database later)
_ralph_runs: Dict[str, RalphRun] = {}
_ralph_tasks: Dict[str, asyncio.Task] = {}


# ============================================================================
# Helper Functions
# ============================================================================


def generate_uuid() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_log(
    run: RalphRun, log_type: str, message: str, story_id: Optional[str] = None
):
    """Add a log entry to a run."""
    run.logs.append(
        {
            'id': generate_uuid(),
            'timestamp': now_iso(),
            'type': log_type,
            'message': message,
            'story_id': story_id,
        }
    )


async def create_story_task(
    run: RalphRun,
    story: UserStory,
    iteration: int,
) -> Optional[str]:
    """Create an A2A task for a user story."""
    bridge = get_opencode_bridge()
    if not bridge:
        raise HTTPException(
            status_code=503, detail='OpenCode bridge not available'
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

    return task.get('id')


async def wait_for_task(
    task_id: str, timeout_seconds: int = 600
) -> Dict[str, Any]:
    """Wait for a task to complete."""
    bridge = get_opencode_bridge()
    if not bridge:
        return {'success': False, 'result': 'OpenCode bridge not available'}

    start_time = asyncio.get_event_loop().time()

    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout_seconds:
            return {'success': False, 'result': 'Task timed out'}

        task = await bridge.get_task(task_id)
        if not task:
            await asyncio.sleep(2)
            continue

        status = task.get('status')
        if status == 'completed':
            result = task.get('result', '')
            success = (
                'STORY_COMPLETE' in result or 'STORY_BLOCKED' not in result
            )
            return {'success': success, 'result': result}
        elif status == 'failed':
            return {
                'success': False,
                'result': task.get('error', 'Task failed'),
            }
        elif status == 'cancelled':
            return {'success': False, 'result': 'Task cancelled'}

        await asyncio.sleep(2)


async def run_ralph_sequential(run: RalphRun):
    """Run Ralph loop sequentially."""
    add_log(run, 'info', f'Starting Ralph loop for {run.prd.project}')
    add_log(run, 'info', f'Branch: {run.prd.branch_name}')
    add_log(run, 'info', f'Stories: {len(run.prd.user_stories)}')
    add_log(run, 'info', f'Mode: sequential')

    for iteration in range(1, run.max_iterations + 1):
        run.current_iteration = iteration

        # Find next incomplete story
        pending_stories = [
            s
            for s in run.prd.user_stories
            if not any(
                r.story_id == s.id and r.status == StoryStatus.PASSED
                for r in run.story_results
            )
        ]

        if not pending_stories:
            add_log(run, 'complete', 'All stories complete!')
            run.status = RunStatus.COMPLETED
            break

        story = pending_stories[0]
        add_log(
            run, 'story_start', f'Starting {story.id}: {story.title}', story.id
        )

        # Create story result
        story_result = StoryResult(
            story_id=story.id,
            status=StoryStatus.RUNNING,
            iteration=iteration,
            started_at=now_iso(),
        )
        run.story_results.append(story_result)

        try:
            # Create task
            add_log(run, 'info', f'Creating task for {story.id}...', story.id)
            task_id = await create_story_task(run, story, iteration)

            if not task_id:
                story_result.status = StoryStatus.FAILED
                story_result.error = 'Failed to create task'
                story_result.completed_at = now_iso()
                add_log(
                    run,
                    'error',
                    f'Failed to create task for {story.id}',
                    story.id,
                )
                continue

            story_result.task_id = task_id
            add_log(run, 'info', f'Task created: {task_id}', story.id)

            # Wait for completion
            result = await wait_for_task(task_id)
            story_result.result = result.get('result', '')
            story_result.completed_at = now_iso()

            if result['success']:
                story_result.status = StoryStatus.PASSED
                add_log(run, 'story_pass', f'{story.id} PASSED!', story.id)
            else:
                story_result.status = StoryStatus.FAILED
                story_result.error = result.get('result', 'Unknown error')
                add_log(
                    run,
                    'story_fail',
                    f'{story.id} FAILED: {story_result.error[:200]}',
                    story.id,
                )

        except Exception as e:
            story_result.status = StoryStatus.FAILED
            story_result.error = str(e)
            story_result.completed_at = now_iso()
            add_log(run, 'error', f'Error on {story.id}: {e}', story.id)

    # Final status
    passed = sum(1 for r in run.story_results if r.status == StoryStatus.PASSED)
    total = len(run.prd.user_stories)

    if passed == total:
        run.status = RunStatus.COMPLETED
        add_log(
            run, 'complete', f'Ralph completed: {passed}/{total} stories passed'
        )
    else:
        run.status = RunStatus.COMPLETED  # Completed but with failures
        add_log(run, 'info', f'Ralph finished: {passed}/{total} stories passed')

    run.completed_at = now_iso()


async def run_ralph_parallel(run: RalphRun):
    """Run Ralph loop with parallel story execution."""
    add_log(run, 'info', f'Starting Ralph loop for {run.prd.project}')
    add_log(run, 'info', f'Branch: {run.prd.branch_name}')
    add_log(run, 'info', f'Stories: {len(run.prd.user_stories)}')
    add_log(run, 'info', f'Mode: parallel (max {run.max_parallel})')

    semaphore = asyncio.Semaphore(run.max_parallel)

    async def run_story(story: UserStory, iteration: int):
        async with semaphore:
            story_result = StoryResult(
                story_id=story.id,
                status=StoryStatus.RUNNING,
                iteration=iteration,
                started_at=now_iso(),
            )
            run.story_results.append(story_result)

            try:
                add_log(
                    run,
                    'story_start',
                    f'Starting {story.id}: {story.title}',
                    story.id,
                )
                task_id = await create_story_task(run, story, iteration)

                if not task_id:
                    story_result.status = StoryStatus.FAILED
                    story_result.error = 'Failed to create task'
                    story_result.completed_at = now_iso()
                    return

                story_result.task_id = task_id
                result = await wait_for_task(task_id)
                story_result.result = result.get('result', '')
                story_result.completed_at = now_iso()

                if result['success']:
                    story_result.status = StoryStatus.PASSED
                    add_log(run, 'story_pass', f'{story.id} PASSED!', story.id)
                else:
                    story_result.status = StoryStatus.FAILED
                    story_result.error = result.get('result', 'Unknown error')
                    add_log(run, 'story_fail', f'{story.id} FAILED', story.id)

            except Exception as e:
                story_result.status = StoryStatus.FAILED
                story_result.error = str(e)
                story_result.completed_at = now_iso()
                add_log(run, 'error', f'Error on {story.id}: {e}', story.id)

    # Run all stories in parallel (with semaphore limiting concurrency)
    tasks = [run_story(s, 1) for s in run.prd.user_stories]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Final status
    passed = sum(1 for r in run.story_results if r.status == StoryStatus.PASSED)
    total = len(run.prd.user_stories)

    run.status = RunStatus.COMPLETED
    run.completed_at = now_iso()
    add_log(run, 'complete', f'Ralph finished: {passed}/{total} stories passed')


async def run_ralph(run_id: str):
    """Background task to run Ralph."""
    run = _ralph_runs.get(run_id)
    if not run:
        logger.error(f'Ralph run {run_id} not found')
        return

    run.status = RunStatus.RUNNING
    run.started_at = now_iso()

    try:
        if run.run_mode == 'parallel':
            await run_ralph_parallel(run)
        else:
            await run_ralph_sequential(run)
    except asyncio.CancelledError:
        run.status = RunStatus.CANCELLED
        run.completed_at = now_iso()
        add_log(run, 'info', 'Ralph run cancelled')
    except Exception as e:
        run.status = RunStatus.FAILED
        run.error = str(e)
        run.completed_at = now_iso()
        add_log(run, 'error', f'Ralph run failed: {e}')
        logger.exception(f'Ralph run {run_id} failed')
    finally:
        # Clean up task reference
        _ralph_tasks.pop(run_id, None)


# ============================================================================
# API Endpoints
# ============================================================================


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

    # Initialize story results
    story_results = [
        StoryResult(story_id=s.id, status=StoryStatus.PENDING)
        for s in request.prd.user_stories
    ]

    run = RalphRun(
        id=run_id,
        prd=request.prd,
        codebase_id=request.codebase_id,
        model=request.model,
        status=RunStatus.PENDING,
        max_iterations=request.max_iterations,
        run_mode=request.run_mode,
        max_parallel=request.max_parallel,
        story_results=story_results,
        created_at=now_iso(),
    )

    _ralph_runs[run_id] = run

    # Start background task
    task = asyncio.create_task(run_ralph(run_id))
    _ralph_tasks[run_id] = task

    return run


@ralph_router.get('/runs', response_model=List[RalphRun])
async def list_ralph_runs(
    status: Optional[str] = None,
    limit: int = 50,
):
    """List Ralph runs, optionally filtered by status."""
    runs = list(_ralph_runs.values())

    if status:
        runs = [r for r in runs if r.status == status]

    # Sort by created_at descending
    runs.sort(key=lambda r: r.created_at, reverse=True)

    return runs[:limit]


@ralph_router.get('/runs/{run_id}', response_model=RalphRun)
async def get_ralph_run(run_id: str):
    """Get a specific Ralph run by ID."""
    run = _ralph_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Ralph run not found')
    return run


@ralph_router.post('/runs/{run_id}/cancel')
async def cancel_ralph_run(run_id: str):
    """Cancel a running Ralph run."""
    run = _ralph_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Ralph run not found')

    if run.status not in [RunStatus.PENDING, RunStatus.RUNNING]:
        raise HTTPException(
            status_code=400,
            detail=f'Cannot cancel run with status {run.status}',
        )

    # Cancel the background task
    task = _ralph_tasks.get(run_id)
    if task and not task.done():
        task.cancel()

    run.status = RunStatus.CANCELLED
    run.completed_at = now_iso()
    add_log(run, 'info', 'Run cancelled by user')

    return {'status': 'cancelled', 'run_id': run_id}


@ralph_router.delete('/runs/{run_id}')
async def delete_ralph_run(run_id: str):
    """Delete a Ralph run from history."""
    if run_id not in _ralph_runs:
        raise HTTPException(status_code=404, detail='Ralph run not found')

    run = _ralph_runs[run_id]

    # Cancel if still running
    if run.status in [RunStatus.PENDING, RunStatus.RUNNING]:
        task = _ralph_tasks.get(run_id)
        if task and not task.done():
            task.cancel()

    del _ralph_runs[run_id]
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
    run = _ralph_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail='Ralph run not found')

    logs = run.logs

    if since:
        logs = [l for l in logs if l['timestamp'] > since]

    return logs[-limit:]
