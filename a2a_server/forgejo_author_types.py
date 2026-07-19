"""Structural types used by the Forgejo author task service."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Protocol


class TaskData(Protocol):
    """HTTP-independent fields required to construct an author task."""

    title: str
    prompt: str
    agent_type: str
    priority: int


class RoutingDecision(Protocol):
    """Resolved model route required by task persistence."""

    model_ref: str | None


class TaskBridge(Protocol):
    """Task persistence boundary used by the author service."""

    async def create_task(self, **kwargs: object) -> object | None: ...


class WorkerValidator(Protocol):
    """Strict worker-availability validation boundary."""

    async def __call__(
        self, metadata: MutableMapping[str, object], *, strict: bool
    ) -> None: ...
