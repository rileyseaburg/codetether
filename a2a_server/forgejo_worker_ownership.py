"""Durable claim ownership policy for author-task mutations."""

from collections.abc import Mapping


def require(task: Mapping[str, object], worker_id: str, action: str) -> None:
    """Require the claiming worker and an active task for every mutation."""
    if action == 'claim':
        return
    if str(task.get('worker_id') or '') != worker_id:
        raise ValueError('worker does not own the author task claim')
    if str(task.get('status') or '') not in {'running', 'working'}:
        raise ValueError('author task is not active')
