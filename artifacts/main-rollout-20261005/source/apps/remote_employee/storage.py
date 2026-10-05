"""SQLite persistence for the Remote Employee control plane."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """Return a timezone-aware timestamp suitable for persistence."""
    return datetime.now(UTC).isoformat()


class Store:
    """Small thread-safe repository with no process-global database handle."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('PRAGMA journal_mode = WAL')
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    mux_name TEXT NOT NULL UNIQUE,
                    room_name TEXT NOT NULL UNIQUE,
                    profile_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'idle',
                    current_task_id TEXT,
                    output_offset INTEGER NOT NULL DEFAULT 0,
                    output_tail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL REFERENCES employees(id),
                    objective TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    completion_marker TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL REFERENCES employees(id),
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                );
                """
            )
            columns = {
                row[1]
                for row in connection.execute(
                    'PRAGMA table_info(tasks)'
                ).fetchall()
            }
            if 'completion_marker' not in columns:
                connection.execute(
                    'ALTER TABLE tasks ADD COLUMN completion_marker '
                    "TEXT NOT NULL DEFAULT ''"
                )
            employee_columns = {
                row[1]
                for row in connection.execute(
                    'PRAGMA table_info(employees)'
                ).fetchall()
            }
            if 'profile_json' not in employee_columns:
                connection.execute(
                    'ALTER TABLE employees ADD COLUMN profile_json '
                    "TEXT NOT NULL DEFAULT '{}'"
                )

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    @staticmethod
    def _employee(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        value = dict(row)
        value['profile'] = json.loads(value.pop('profile_json'))
        return value

    def list_employees(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                'SELECT * FROM employees ORDER BY created_at ASC'
            ).fetchall()
        return [self._employee(row) or {} for row in rows]

    def get_employee(self, employee_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT * FROM employees WHERE id = ?', (employee_id,)
            ).fetchone()
        return self._employee(row)

    def create_employee(  # noqa: PLR0913
        self,
        *,
        name: str,
        role: str,
        goal: str,
        workspace: str,
        mux_name: str,
        room_name: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        employee_id = uuid.uuid4().hex
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO employees
                    (id, name, role, goal, workspace, mux_name, room_name,
                     profile_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    employee_id,
                    name,
                    role,
                    goal,
                    workspace,
                    mux_name,
                    room_name,
                    json.dumps(profile),
                    utc_now(),
                ),
            )
        return self.get_employee(employee_id) or {}

    def set_employee_profile(
        self, employee_id: str, profile: dict[str, Any]
    ) -> None:
        """Persist a generated personality profile for a legacy employee row."""
        with self._lock, self._connect() as connection:
            connection.execute(
                'UPDATE employees SET profile_json = ? WHERE id = ?',
                (json.dumps(profile), employee_id),
            )

    def delete_employee(self, employee_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                'DELETE FROM proposals WHERE employee_id = ?', (employee_id,)
            )
            connection.execute(
                'DELETE FROM tasks WHERE employee_id = ?', (employee_id,)
            )
            connection.execute(
                'DELETE FROM employees WHERE id = ?', (employee_id,)
            )

    def set_employee_runtime(
        self,
        employee_id: str,
        *,
        status: str,
        task_id: str | None,
        output_offset: int | None = None,
        output_tail: str | None = None,
    ) -> None:
        fields: list[str] = ['status = ?', 'current_task_id = ?']
        values: list[Any] = [status, task_id]
        if output_offset is not None:
            fields.append('output_offset = ?')
            values.append(output_offset)
        if output_tail is not None:
            fields.append('output_tail = ?')
            values.append(output_tail[-12000:])
        values.append(employee_id)
        with self._lock, self._connect() as connection:
            connection.execute(
                f'UPDATE employees SET {", ".join(fields)} WHERE id = ?', values
            )

    def create_task(
        self,
        *,
        employee_id: str,
        objective: str,
        source: str,
        completion_marker: str,
    ) -> dict[str, Any]:
        task_id = uuid.uuid4().hex
        now = utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks
                    (id, employee_id, objective, source, status,
                     completion_marker,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, 'running', ?, ?, ?)
                """,
                (
                    task_id,
                    employee_id,
                    objective,
                    source,
                    completion_marker,
                    now,
                    now,
                ),
            )
        return self.get_task(task_id) or {}

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT * FROM tasks WHERE id = ?', (task_id,)
            ).fetchone()
        return self._row(row)

    def update_task_status(self, task_id: str, status: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                'UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?',
                (status, utc_now(), task_id),
            )

    def list_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT tasks.*, employees.name AS employee_name
                FROM tasks JOIN employees ON employees.id = tasks.employee_id
                ORDER BY tasks.created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_proposal(
        self,
        *,
        employee_id: str,
        kind: str,
        title: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        proposal_id = uuid.uuid4().hex
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO proposals
                    (id, employee_id, kind, title, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    employee_id,
                    kind,
                    title,
                    json.dumps(details),
                    utc_now(),
                ),
            )
        return self.get_proposal(proposal_id) or {}

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT * FROM proposals WHERE id = ?', (proposal_id,)
            ).fetchone()
        return self._decode_proposal(row)

    @staticmethod
    def _decode_proposal(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        value = dict(row)
        value['details'] = json.loads(value.pop('details_json'))
        return value

    def list_proposals(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT proposals.*, employees.name AS employee_name
                FROM proposals
                JOIN employees ON employees.id = proposals.employee_id
                ORDER BY proposals.created_at DESC
                """
            ).fetchall()
        return [self._decode_proposal(row) or {} for row in rows]

    def decide_proposal(self, proposal_id: str, status: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                'UPDATE proposals SET status = ?, decided_at = ? WHERE id = ?',
                (status, utc_now(), proposal_id),
            )
