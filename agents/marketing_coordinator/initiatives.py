"""
Marketing Initiative Management

Handles the lifecycle of marketing initiatives from planning to completion.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class InitiativeStatus(Enum):
    """Status of a marketing initiative."""

    DRAFT = 'draft'
    PLANNING = 'planning'
    EXECUTING = 'executing'
    MONITORING = 'monitoring'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


@dataclass
class Initiative:
    """A marketing initiative."""

    id: uuid.UUID
    name: str
    goal: str
    status: InitiativeStatus = InitiativeStatus.DRAFT
    budget: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    strategy: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    completed_phases: Optional[List[str]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': str(self.id),
            'name': self.name,
            'goal': self.goal,
            'status': self.status.value,
            'budget': self.budget,
            'start_date': self.start_date.isoformat()
            if self.start_date
            else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'strategy': self.strategy,
            'context': self.context,
            'completed_phases': self.completed_phases,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Initiative':
        """Create from dictionary."""
        return cls(
            id=uuid.UUID(data['id'])
            if isinstance(data['id'], str)
            else data['id'],
            name=data['name'],
            goal=data['goal'],
            status=InitiativeStatus(data.get('status', 'draft')),
            budget=data.get('budget'),
            start_date=date.fromisoformat(data['start_date'])
            if data.get('start_date')
            else None,
            end_date=date.fromisoformat(data['end_date'])
            if data.get('end_date')
            else None,
            strategy=data.get('strategy'),
            context=data.get('context'),
            completed_phases=data.get('completed_phases'),
            created_at=datetime.fromisoformat(data['created_at'])
            if data.get('created_at')
            else datetime.now(),
            updated_at=datetime.fromisoformat(data['updated_at'])
            if data.get('updated_at')
            else datetime.now(),
        )


class InitiativeManager:
    """
    Manages marketing initiatives.

    Handles persistence, lifecycle transitions, and queries.
    Supports both in-memory and database-backed storage.
    """

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url
        self._pool = None

        # In-memory fallback
        self._initiatives: Dict[uuid.UUID, Initiative] = {}
        self._use_db = bool(database_url)

    async def initialize(self):
        """Initialize the manager, setting up database if configured."""
        if self._use_db:
            try:
                import asyncpg

                self._pool = await asyncpg.create_pool(self.database_url)
                await self._ensure_tables()
                logger.info('Initiative manager initialized with PostgreSQL')
            except Exception as e:
                logger.warning(
                    f'Failed to connect to database, using in-memory: {e}'
                )
                self._use_db = False
        else:
            logger.info('Initiative manager initialized with in-memory storage')

    async def _ensure_tables(self):
        """Ensure the database tables exist."""
        if not self._pool:
            return

        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS marketing_initiatives (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft',
                    budget DECIMAL,
                    start_date DATE,
                    end_date DATE,
                    strategy JSONB,
                    context JSONB,
                    completed_phases JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS initiative_tasks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    initiative_id UUID NOT NULL REFERENCES marketing_initiatives(id) ON DELETE CASCADE,
                    task_type TEXT NOT NULL,
                    a2a_task_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_initiatives_status 
                ON marketing_initiatives(status)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_initiative_tasks_initiative 
                ON initiative_tasks(initiative_id)
            """)

    async def create_initiative(
        self,
        name: str,
        goal: str,
        budget: Optional[float] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Initiative:
        """Create a new initiative."""
        initiative = Initiative(
            id=uuid.uuid4(),
            name=name,
            goal=goal,
            status=InitiativeStatus.PLANNING,
            budget=budget,
            start_date=start_date,
            end_date=end_date,
            context=context,
        )

        if self._use_db and self._pool:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO marketing_initiatives 
                    (id, name, goal, status, budget, start_date, end_date, context)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                    initiative.id,
                    initiative.name,
                    initiative.goal,
                    initiative.status.value,
                    initiative.budget,
                    initiative.start_date,
                    initiative.end_date,
                    initiative.context,
                )
        else:
            self._initiatives[initiative.id] = initiative

        logger.info(f'Created initiative: {initiative.id} - {name}')
        return initiative

    async def update_initiative(self, initiative: Initiative):
        """Update an existing initiative."""
        initiative.updated_at = datetime.now()

        if self._use_db and self._pool:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE marketing_initiatives SET
                        name = $2,
                        goal = $3,
                        status = $4,
                        budget = $5,
                        start_date = $6,
                        end_date = $7,
                        strategy = $8,
                        context = $9,
                        completed_phases = $10,
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    initiative.id,
                    initiative.name,
                    initiative.goal,
                    initiative.status.value,
                    initiative.budget,
                    initiative.start_date,
                    initiative.end_date,
                    initiative.strategy,
                    initiative.context,
                    initiative.completed_phases,
                )
        else:
            self._initiatives[initiative.id] = initiative

        logger.info(f'Updated initiative: {initiative.id}')

    async def get_initiative(
        self, initiative_id: uuid.UUID
    ) -> Optional[Initiative]:
        """Get an initiative by ID."""
        if self._use_db and self._pool:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM marketing_initiatives WHERE id = $1
                """,
                    initiative_id,
                )

                if row:
                    return Initiative(
                        id=row['id'],
                        name=row['name'],
                        goal=row['goal'],
                        status=InitiativeStatus(row['status']),
                        budget=float(row['budget']) if row['budget'] else None,
                        start_date=row['start_date'],
                        end_date=row['end_date'],
                        strategy=row['strategy'],
                        context=row['context'],
                        completed_phases=row['completed_phases'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                    )
                return None
        else:
            return self._initiatives.get(initiative_id)

    async def get_active_initiatives(self) -> List[Initiative]:
        """Get all active initiatives (planning, executing, monitoring)."""
        active_statuses = [
            InitiativeStatus.PLANNING.value,
            InitiativeStatus.EXECUTING.value,
            InitiativeStatus.MONITORING.value,
        ]

        if self._use_db and self._pool:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM marketing_initiatives 
                    WHERE status = ANY($1)
                    ORDER BY updated_at DESC
                """,
                    active_statuses,
                )

                return [
                    Initiative(
                        id=row['id'],
                        name=row['name'],
                        goal=row['goal'],
                        status=InitiativeStatus(row['status']),
                        budget=float(row['budget']) if row['budget'] else None,
                        start_date=row['start_date'],
                        end_date=row['end_date'],
                        strategy=row['strategy'],
                        context=row['context'],
                        completed_phases=row['completed_phases'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                    )
                    for row in rows
                ]
        else:
            return [
                init
                for init in self._initiatives.values()
                if init.status.value in active_statuses
            ]

    async def list_initiatives(
        self,
        status: Optional[InitiativeStatus] = None,
        limit: int = 50,
    ) -> List[Initiative]:
        """List initiatives, optionally filtered by status."""
        if self._use_db and self._pool:
            async with self._pool.acquire() as conn:
                if status:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM marketing_initiatives 
                        WHERE status = $1
                        ORDER BY updated_at DESC
                        LIMIT $2
                    """,
                        status.value,
                        limit,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM marketing_initiatives 
                        ORDER BY updated_at DESC
                        LIMIT $1
                    """,
                        limit,
                    )

                return [
                    Initiative(
                        id=row['id'],
                        name=row['name'],
                        goal=row['goal'],
                        status=InitiativeStatus(row['status']),
                        budget=float(row['budget']) if row['budget'] else None,
                        start_date=row['start_date'],
                        end_date=row['end_date'],
                        strategy=row['strategy'],
                        context=row['context'],
                        completed_phases=row['completed_phases'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                    )
                    for row in rows
                ]
        else:
            initiatives = list(self._initiatives.values())
            if status:
                initiatives = [i for i in initiatives if i.status == status]
            return sorted(
                initiatives, key=lambda x: x.updated_at, reverse=True
            )[:limit]

    async def record_task(
        self,
        initiative_id: uuid.UUID,
        task_type: str,
        a2a_task_id: Optional[str] = None,
        status: str = 'pending',
        result: Optional[Dict[str, Any]] = None,
    ) -> uuid.UUID:
        """Record a task associated with an initiative."""
        task_id = uuid.uuid4()

        if self._use_db and self._pool:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO initiative_tasks 
                    (id, initiative_id, task_type, a2a_task_id, status, result)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    task_id,
                    initiative_id,
                    task_type,
                    a2a_task_id,
                    status,
                    result,
                )

        logger.info(f'Recorded task {task_id} for initiative {initiative_id}')
        return task_id

    async def update_task_status(
        self,
        task_id: uuid.UUID,
        status: str,
        result: Optional[Dict[str, Any]] = None,
    ):
        """Update a task's status and result."""
        if self._use_db and self._pool:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE initiative_tasks SET
                        status = $2,
                        result = $3,
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    task_id,
                    status,
                    result,
                )

    async def get_initiative_tasks(
        self,
        initiative_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Get all tasks for an initiative."""
        if self._use_db and self._pool:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM initiative_tasks 
                    WHERE initiative_id = $1
                    ORDER BY created_at ASC
                """,
                    initiative_id,
                )

                return [dict(row) for row in rows]
        return []
