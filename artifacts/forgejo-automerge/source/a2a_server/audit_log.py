"""
Autonomous Decision Audit Logger.

Central utility for recording all autonomous decisions made by the proactive
agent layer: rule engine triggers, perpetual loop iterations, Ralph actions,
health monitor alerts, and cron scheduler dispatches.

Backs the marketing claim: "Every autonomous decision is audit-logged."

Usage:
    from .audit_log import log_decision

    await log_decision(
        source='rule_engine',
        decision_type='trigger_rule',
        description='Rule "deploy-on-push" triggered by event git.push',
        trigger_data={'event': 'git.push', 'branch': 'main'},
        decision_data={'rule_id': '...', 'action': 'deploy'},
        task_id='task-123',
        tenant_id='tenant-1',
    )
"""

import json
import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def log_decision(
    *,
    source: str,
    decision_type: str,
    description: str = '',
    trigger_data: Optional[Dict[str, Any]] = None,
    decision_data: Optional[Dict[str, Any]] = None,
    task_id: Optional[str] = None,
    outcome: str = 'pending',
    cost_cents: int = 0,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """
    Record an autonomous decision in the audit trail.

    Returns the decision ID on success, None on failure.
    """
    try:
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            logger.debug('Audit log skipped: no DB pool')
            return None

        decision_id = str(uuid.uuid4())

        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO autonomous_decisions
                    (id, tenant_id, user_id, source, decision_type, description,
                     trigger_data, decision_data, task_id, outcome, cost_cents, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10, $11, NOW())
            """,
                decision_id, tenant_id, user_id, source, decision_type, description,
                json.dumps(trigger_data or {}, default=str),
                json.dumps(decision_data or {}, default=str),
                task_id, outcome, cost_cents,
            )

        return decision_id

    except Exception as e:
        # Never break the caller — audit logging is best-effort
        logger.error('Failed to log autonomous decision: %s', e)
        return None


async def update_decision_outcome(
    decision_id: str,
    outcome: str,
    cost_cents: int = 0,
) -> None:
    """Update the outcome of a previously logged decision."""
    try:
        from . import database as db

        pool = await db.get_pool()
        if not pool:
            return

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE autonomous_decisions
                SET outcome = $2, cost_cents = cost_cents + $3
                WHERE id = $1
            """, decision_id, outcome, cost_cents)

    except Exception as e:
        logger.error('Failed to update decision outcome: %s', e)
