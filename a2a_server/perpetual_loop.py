"""
Perpetual Cognition Loops — persistent thought loops that survive restarts.

Implements continuous reasoning cycles where an agent persona iterates on a
codebase (or system) with state carried between iterations.  Each iteration
dispatches a real A2A task through the standard bridge/worker pipeline.

Key design decisions:
- DB-backed state machine (same pattern as Ralph): status, state JSONB, counters
- Recover running loops on startup (like ralph_api.recover_stuck_runs)
- Per-loop daily cost ceiling that auto-pauses the loop at budget exhaustion
- Auto-downgrade model tier at 80% of daily budget to stretch spend
- Daily counters reset automatically when the day rolls over

Safety:
- check_user_task_limits() is called before every iteration dispatch
- agent_minutes_limit now enforced (migration 017)
- Each iteration is a standard audited task

Usage:
    from .perpetual_loop import start_perpetual_loop_manager, stop_perpetual_loop_manager
    await start_perpetual_loop_manager()
    ...
    await stop_perpetual_loop_manager()
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .cron_dispatch import dispatch_cron_task

logger = logging.getLogger(__name__)

# Configuration
LOOP_ENABLED = os.environ.get('PERPETUAL_LOOPS_ENABLED', 'true').lower() == 'true'
LOOP_POLL_INTERVAL = int(os.environ.get('PERPETUAL_LOOP_POLL_SECONDS', '15'))

# Budget threshold at which model downgrades to 'fast' tier
DOWNGRADE_THRESHOLD = float(os.environ.get('LOOP_DOWNGRADE_THRESHOLD', '0.8'))


class PerpetualCognitionManager:
    """
    Background service that drives perpetual thought loops.

    On each poll cycle:
      1. Reset daily counters for loops whose day has rolled over
      2. Find loops that are 'running' and due for next iteration
      3. Check budget and billing limits
      4. Dispatch an iteration task through the standard pipeline
      5. Record the iteration in perpetual_loop_iterations
    """

    def __init__(self, poll_interval: int = LOOP_POLL_INTERVAL):
        self.poll_interval = poll_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if not LOOP_ENABLED:
            logger.info('Perpetual loops disabled via PERPETUAL_LOOPS_ENABLED')
            return
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info('PerpetualCognitionManager started (poll=%ss)', self.poll_interval)

        # Recover iterations that were in-flight when the server stopped
        asyncio.create_task(self._recover_stuck_iterations())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info('PerpetualCognitionManager stopped')

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _main_loop(self) -> None:
        """Poll for due loops and drive iterations."""
        await asyncio.sleep(20)  # let server and DB settle

        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error('Perpetual loop tick error: %s', e, exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def _tick(self) -> None:
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            return

        async with pool.acquire() as conn:
            # 1. Reset daily counters for loops whose day has rolled over
            await conn.execute("""
                UPDATE perpetual_loops
                SET iterations_today = 0,
                    cost_today_cents = 0,
                    iterations_today_reset_at = NOW(),
                    cost_today_reset_at = NOW()
                WHERE status = 'running'
                  AND iterations_today_reset_at < DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')
            """)

            # 2. Find running loops that are due for iteration
            try:
                due_loops = await conn.fetch("""
                    SELECT id, tenant_id, user_id, persona_slug, workspace_id,
                           state, iteration_count, iteration_interval_seconds,
                           max_iterations_per_day, iterations_today,
                           daily_cost_ceiling_cents, cost_today_cents,
                           last_iteration_at
                    FROM perpetual_loops
                    WHERE status = 'running'
                      AND (
                        last_iteration_at IS NULL
                        OR last_iteration_at + (iteration_interval_seconds || ' seconds')::interval <= NOW()
                      )
                    ORDER BY last_iteration_at ASC NULLS FIRST
                """)
            except Exception as e:
                # Backward compatibility: older schemas may still use codebase_id.
                if (
                    'workspace_id' in str(e).lower()
                    and 'column' in str(e).lower()
                ):
                    due_loops = await conn.fetch("""
                        SELECT id, tenant_id, user_id, persona_slug, codebase_id AS workspace_id,
                               state, iteration_count, iteration_interval_seconds,
                               max_iterations_per_day, iterations_today,
                               daily_cost_ceiling_cents, cost_today_cents,
                               last_iteration_at
                        FROM perpetual_loops
                        WHERE status = 'running'
                          AND (
                            last_iteration_at IS NULL
                            OR last_iteration_at + (iteration_interval_seconds || ' seconds')::interval <= NOW()
                          )
                        ORDER BY last_iteration_at ASC NULLS FIRST
                    """)
                else:
                    raise

            for loop in due_loops:
                try:
                    await self._run_iteration(conn, loop)
                except Exception as e:
                    logger.error(
                        'Loop %s iteration failed: %s', loop['id'], e, exc_info=True
                    )

    # ------------------------------------------------------------------
    # Iteration logic
    # ------------------------------------------------------------------

    async def _run_iteration(self, conn, loop: dict) -> None:
        loop_id = loop['id']
        tenant_id = loop['tenant_id']
        user_id = loop['user_id']
        persona_slug = loop['persona_slug']

        # --- Gate 1: daily iteration cap ---
        if loop['iterations_today'] >= loop['max_iterations_per_day']:
            logger.info('Loop %s: daily iteration cap reached (%d)', loop_id, loop['max_iterations_per_day'])
            return

        # --- Gate 2: daily cost ceiling ---
        ceiling = loop['daily_cost_ceiling_cents'] or 0
        spent = loop['cost_today_cents'] or 0
        if ceiling > 0 and spent >= ceiling:
            await conn.execute(
                "UPDATE perpetual_loops SET status = 'budget_exhausted', updated_at = NOW() WHERE id = $1",
                loop_id,
            )
            logger.info('Loop %s: budget exhausted ($%.2f/$%.2f)', loop_id, spent / 100, ceiling / 100)
            try:
                from .audit_log import log_decision
                await log_decision(
                    source='perpetual_loop',
                    decision_type='budget_exhausted',
                    description=f'Loop {loop_id[:8]}… paused: ${spent/100:.2f}/${ceiling/100:.2f} daily budget',
                    trigger_data={'loop_id': loop_id, 'spent': spent, 'ceiling': ceiling},
                    decision_data={'action': 'status_change', 'new_status': 'budget_exhausted'},
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
            except Exception:
                pass
            return

        # --- Gate 3: user billing limits ---
        if user_id:
            limits_ok = await self._check_user_limits(conn, user_id)
            if not limits_ok:
                logger.info('Loop %s: user %s task limits reached, skipping', loop_id, user_id)
                return

        # --- Determine model tier (auto-downgrade at 80% budget) ---
        budget_hint = None
        if ceiling > 0 and spent >= ceiling * DOWNGRADE_THRESHOLD:
            budget_hint = 'fast'
            logger.debug('Loop %s: at %.0f%% budget, downgrading to fast tier', loop_id, (spent / ceiling) * 100)

        # --- Build iteration task ---
        iteration_number = loop['iteration_count'] + 1
        state = loop['state'] or {}

        # Resolve persona system prompt for context
        persona_system_prompt = await self._get_persona_prompt(conn, persona_slug)

        prompt = self._build_iteration_prompt(
            persona_slug=persona_slug,
            persona_system_prompt=persona_system_prompt,
            iteration_number=iteration_number,
            state=state,
        )

        task_template = {
            'prompt': prompt,
            'title': f'Loop {loop_id[:8]}… iter #{iteration_number}',
            'agent_type': 'explore',
            'codebase_id': loop['workspace_id'],
            'worker_personality': persona_slug,
            'metadata': {
                'perpetual_loop_id': loop_id,
                'iteration_number': iteration_number,
                'loop_state': state,
            },
        }
        if budget_hint:
            task_template['metadata']['budget_tier'] = budget_hint

        # Record iteration pre-dispatch
        iteration_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO perpetual_loop_iterations
                (id, loop_id, iteration_number, input_state, started_at)
            VALUES ($1, $2, $3, $4::jsonb, NOW())
        """, iteration_id, loop_id, iteration_number, json.dumps(state, default=str))

        # Dispatch task
        try:
            task_id, routing = await dispatch_cron_task(
                job_id=loop_id,
                run_id=iteration_id,
                job_name=f'loop:{persona_slug}:{loop_id[:8]}',
                task_template=task_template,
                tenant_id=tenant_id,
                user_id=user_id,
                trigger_mode='perpetual_loop',
            )
        except Exception as e:
            await conn.execute("""
                UPDATE perpetual_loop_iterations
                SET completed_at = NOW(), output_state = $2::jsonb
                WHERE id = $1
            """, iteration_id, json.dumps({'error': str(e)}, default=str))
            raise

        # Update loop counters (we don't wait for task completion to keep loop non-blocking)
        await conn.execute("""
            UPDATE perpetual_loops
            SET iteration_count = iteration_count + 1,
                iterations_today = iterations_today + 1,
                last_iteration_at = NOW(),
                last_heartbeat = NOW(),
                updated_at = NOW()
            WHERE id = $1
        """, loop_id)

        # Link task to iteration
        await conn.execute("""
            UPDATE perpetual_loop_iterations SET task_id = $2 WHERE id = $1
        """, iteration_id, task_id)

        # Audit log the iteration dispatch
        try:
            from .audit_log import log_decision
            await log_decision(
                source='perpetual_loop',
                decision_type='dispatch_iteration',
                description=f'Loop {loop_id[:8]}… iter #{iteration_number} dispatched',
                trigger_data={'loop_id': loop_id, 'iteration': iteration_number},
                decision_data={'task_id': task_id, 'persona': persona_slug, 'routing': routing},
                task_id=task_id,
                outcome='pending',
                tenant_id=tenant_id,
                user_id=user_id,
            )
        except Exception:
            pass

        logger.info(
            'Loop %s iter #%d dispatched → task %s (persona=%s, model_tier=%s)',
            loop_id, iteration_number, task_id, persona_slug,
            routing.get('model_tier'),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _check_user_limits(self, conn, user_id: str) -> bool:
        """Check user billing limits via the DB function."""
        try:
            row = await conn.fetchrow(
                "SELECT allowed FROM check_user_task_limits($1)", user_id
            )
            return bool(row and row['allowed'])
        except Exception:
            # If the function doesn't exist, allow (best-effort)
            return True

    async def _recover_stuck_iterations(self) -> None:
        """
        Recover iterations that were in-flight when the server stopped.

        Follows Ralph's recover_stuck_runs() pattern:
        1. Wait for DB to settle
        2. Find iterations with completed_at IS NULL and started_at > 10 min ago
        3. Check task status — if completed/failed, record the result
        4. If task is gone, mark iteration as failed and carry forward old state
        """
        await asyncio.sleep(10)  # let DB pool initialize

        try:
            from . import database as db

            pool = await db.get_pool()
            if not pool:
                return

            async with pool.acquire() as conn:
                stuck = await conn.fetch("""
                    SELECT pli.id AS iteration_id, pli.loop_id, pli.task_id,
                           pli.iteration_number, pli.input_state
                    FROM perpetual_loop_iterations pli
                    WHERE pli.completed_at IS NULL
                      AND pli.started_at < NOW() - interval '10 minutes'
                """)

                if not stuck:
                    logger.info('Perpetual loops: no stuck iterations to recover')
                    return

                logger.info('Perpetual loops: recovering %d stuck iterations', len(stuck))

                for row in stuck:
                    task_id = row['task_id']
                    iteration_id = row['iteration_id']
                    loop_id = row['loop_id']

                    if not task_id:
                        # No task was dispatched — mark failed
                        await conn.execute("""
                            UPDATE perpetual_loop_iterations
                            SET completed_at = NOW(),
                                output_state = '{"error": "No task dispatched before server restart"}'::jsonb
                            WHERE id = $1
                        """, iteration_id)
                        continue

                    # Check task status
                    task_row = await conn.fetchrow(
                        "SELECT status, metadata FROM tasks WHERE id = $1", task_id
                    )

                    if not task_row:
                        # Task gone — mark iteration failed
                        await conn.execute("""
                            UPDATE perpetual_loop_iterations
                            SET completed_at = NOW(),
                                output_state = '{"error": "Task not found after restart"}'::jsonb
                            WHERE id = $1
                        """, iteration_id)
                        logger.info(
                            'Loop %s iter #%d: task %s not found, marked failed',
                            loop_id, row['iteration_number'], task_id,
                        )
                        continue

                    task_status = task_row['status']
                    if task_status in ('completed', 'failed'):
                        # Task finished while we were down — record result
                        await handle_task_completion_for_loops(
                            task_id=task_id,
                            status=task_status,
                            result=None,
                        )
                        logger.info(
                            'Loop %s iter #%d: recovered task %s (status=%s)',
                            loop_id, row['iteration_number'], task_id, task_status,
                        )
                    elif task_status in ('pending', 'running', 'queued'):
                        # Task still in progress — it will be picked up by
                        # the normal completion hook when it finishes
                        logger.info(
                            'Loop %s iter #%d: task %s still %s, will complete normally',
                            loop_id, row['iteration_number'], task_id, task_status,
                        )
                    else:
                        # Cancelled or unknown — mark failed
                        await conn.execute("""
                            UPDATE perpetual_loop_iterations
                            SET completed_at = NOW(),
                                output_state = $2::jsonb
                            WHERE id = $1
                        """, iteration_id, json.dumps({'error': f'Task status: {task_status}'}, default=str))

                # Also recover 'budget_exhausted' loops whose day has rolled over
                await conn.execute("""
                    UPDATE perpetual_loops
                    SET status = 'running',
                        iterations_today = 0,
                        cost_today_cents = 0,
                        iterations_today_reset_at = NOW(),
                        cost_today_reset_at = NOW(),
                        updated_at = NOW()
                    WHERE status = 'budget_exhausted'
                      AND cost_today_reset_at < DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')
                """)

        except Exception as e:
            logger.error('Perpetual loop recovery failed: %s', e, exc_info=True)

    async def _get_persona_prompt(self, conn, persona_slug: str) -> str:
        """Fetch system_prompt from worker_profiles for this persona."""
        row = await conn.fetchrow(
            "SELECT system_prompt FROM worker_profiles WHERE slug = $1",
            persona_slug,
        )
        if row and row['system_prompt']:
            return row['system_prompt']
        return f'You are the {persona_slug} agent.'

    def _build_iteration_prompt(
        self,
        *,
        persona_slug: str,
        persona_system_prompt: str,
        iteration_number: int,
        state: Dict[str, Any],
    ) -> str:
        """Build the prompt for an iteration, injecting carried state."""
        state_summary = json.dumps(state, indent=2, default=str) if state else '{}'
        return f"""{persona_system_prompt}

---
## Perpetual Loop Iteration #{iteration_number}

You are in a persistent cognition loop. Between iterations your observations
and conclusions are carried forward in the state below. Use this context to
build on previous work rather than starting from scratch.

### Carried State
```json
{state_summary}
```

### Instructions
1. Review the carried state from your previous iteration.
2. Perform your persona's primary function (monitor, review, deploy, etc.).
3. Record your findings, decisions, and any actions taken.
4. Return a JSON object under a ```json block with the key "next_state" containing
   the updated state to carry into the next iteration, and "summary" with a brief
   human-readable summary of what you did.

Example response:
```json
{{
  "summary": "Checked health endpoints; all services healthy.",
  "next_state": {{
    "last_check": "2025-01-01T00:00:00Z",
    "issues_found": [],
    "consecutive_healthy": 5
  }}
}}
```
"""

    # ------------------------------------------------------------------
    # Completion callback (called when iteration task finishes)
    # ------------------------------------------------------------------

    async def record_iteration_result(
        self,
        loop_id: str,
        iteration_id: str,
        output_state: Dict[str, Any],
        cost_cents: int = 0,
        duration_seconds: int = 0,
    ) -> None:
        """
        Record the result of a completed iteration and update the loop state.

        This should be called when the task created by _run_iteration completes.
        It can be called from the task completion webhook or a polling checker.
        """
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            return

        async with pool.acquire() as conn:
            # Update iteration record
            await conn.execute("""
                UPDATE perpetual_loop_iterations
                SET output_state = $2::jsonb,
                    cost_cents = $3,
                    duration_seconds = $4,
                    completed_at = NOW()
                WHERE id = $1
            """, iteration_id, json.dumps(output_state, default=str), cost_cents, duration_seconds)

            # Update loop state and cost
            next_state = output_state.get('next_state', output_state)
            await conn.execute("""
                UPDATE perpetual_loops
                SET state = $2::jsonb,
                    cost_today_cents = cost_today_cents + $3,
                    cost_total_cents = cost_total_cents + $3,
                    updated_at = NOW()
                WHERE id = $1
            """, loop_id, json.dumps(next_state, default=str), cost_cents)

    def get_health(self) -> Dict[str, Any]:
        return {
            'running': self._running,
            'enabled': LOOP_ENABLED,
            'poll_interval_seconds': self.poll_interval,
        }


# ============================================================================
# Global instance management
# ============================================================================

_manager: Optional[PerpetualCognitionManager] = None


def get_loop_manager() -> Optional[PerpetualCognitionManager]:
    return _manager


# Alias used by proactive_api.py status endpoint
get_perpetual_manager = get_loop_manager


async def start_perpetual_loop_manager() -> PerpetualCognitionManager:
    global _manager
    if _manager is not None:
        return _manager
    _manager = PerpetualCognitionManager()
    await _manager.start()
    return _manager


async def stop_perpetual_loop_manager() -> None:
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None


# ============================================================================
# Task completion hook — call from worker_sse.py and hosted_worker.py
# ============================================================================


async def handle_task_completion_for_loops(
    task_id: str,
    status: str,
    result: Optional[str] = None,
) -> None:
    """
    Check if a completed task belongs to a perpetual loop iteration and,
    if so, record the result and carry state forward.

    This should be called from every task completion path (SSE release,
    hosted worker completion) to close the feedback loop.
    """
    if status not in ('completed', 'failed'):
        return

    try:
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            return

        async with pool.acquire() as conn:
            # Look up the task to check for perpetual_loop_id in metadata
            row = await conn.fetchrow(
                "SELECT metadata FROM tasks WHERE id = $1", task_id
            )
            if not row or not row['metadata']:
                return

            metadata = row['metadata']
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            loop_id = metadata.get('perpetual_loop_id')
            if not loop_id:
                return  # Not a loop iteration task

            # Find the iteration record linked to this task
            iteration = await conn.fetchrow(
                """SELECT id, iteration_number FROM perpetual_loop_iterations
                   WHERE loop_id = $1 AND task_id = $2 AND completed_at IS NULL""",
                loop_id, task_id,
            )
            if not iteration:
                return  # Already recorded or not found

            # Parse result for next_state
            output_state: Dict[str, Any] = {}
            if result and status == 'completed':
                output_state = _parse_loop_result(result)
            elif status == 'failed':
                output_state = {'error': result or 'Task failed', '_failed': True}

            # Record via the manager if available, otherwise direct DB update
            manager = get_loop_manager()
            if manager:
                await manager.record_iteration_result(
                    loop_id=loop_id,
                    iteration_id=iteration['id'],
                    output_state=output_state,
                    cost_cents=0,  # Cost tracking comes from billing layer
                    duration_seconds=0,
                )
            else:
                # Direct DB fallback
                next_state = output_state.get('next_state', output_state)
                await conn.execute("""
                    UPDATE perpetual_loop_iterations
                    SET output_state = $2::jsonb, completed_at = NOW()
                    WHERE id = $1
                """, iteration['id'], json.dumps(output_state, default=str))

                await conn.execute("""
                    UPDATE perpetual_loops
                    SET state = $2::jsonb, updated_at = NOW()
                    WHERE id = $1
                """, loop_id, json.dumps(next_state, default=str))

            logger.info(
                'Loop %s iter #%d result recorded (status=%s)',
                loop_id, iteration['iteration_number'], status,
            )

    except Exception as e:
        # Never break the completion flow
        logger.error('Failed to record loop iteration result: %s', e)


def _parse_loop_result(result: str) -> Dict[str, Any]:
    """
    Parse the agent's response for next_state JSON.

    Expects a ```json block with 'next_state' and 'summary' keys,
    but gracefully handles plain text responses.
    """
    import re

    # Try to find a JSON code block
    json_match = re.search(r'```json\s*\n(.*?)\n```', result, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try parsing entire result as JSON
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: wrap plain text as summary
    return {'summary': result[:500], 'next_state': {'last_result': result[:500]}}
