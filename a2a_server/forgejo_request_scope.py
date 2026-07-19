"""Authenticated idempotency scope for Forgejo task requests."""

from fastapi import Request

from a2a_server.task_auth_scope import legacy_scope


def resolve(request: Request) -> tuple[str, str | None]:
    """Return a verified server-controlled scope and optional tenant."""
    user = getattr(request.state, 'policy_user', None)
    tenant = _field(user, 'tenant_id')
    subject = (
        _field(user, 'user_id') or _field(user, 'id') or _field(user, 'sub')
    )
    if tenant:
        return f'tenant:{tenant}', tenant
    if subject:
        return f'subject:{subject}', None
    return legacy_scope(request), None


def _field(user: object, key: str) -> str:
    if not isinstance(user, dict):
        return ''
    return str(user.get(key) or '').strip()
