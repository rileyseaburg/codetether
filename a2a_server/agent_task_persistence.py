"""Fail-closed PostgreSQL persistence for agent tasks."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from a2a_server import database as db
from a2a_server.agent_task_record import build


if TYPE_CHECKING:
    from a2a_server.agent_bridge import AgentTask

logger = logging.getLogger(__name__)


async def save(task: AgentTask) -> bool:
    """Persist a task and propagate the database write result."""
    try:
        return await db.db_upsert_task(build(task))
    except Exception as error:
        logger.error('Failed to save task to PostgreSQL: %s', error)
        return False
