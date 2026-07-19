"""Compact request fixture for Forgejo author service tests."""

from types import SimpleNamespace

from a2a_server.forgejo_author_request import AuthorTaskRequest


def request(metadata=None, token='token') -> AuthorTaskRequest:
    """Build a minimal structurally typed author service request."""
    values = {
        'idempotency_scope': 'token:reviewer:fingerprint',
        'tenant_id': 'tenant',
    }
    values.update(metadata or {})
    return AuthorTaskRequest(
        task_data=SimpleNamespace(
            title='review', prompt='data', agent_type='build', priority=1
        ),
        metadata=values,
        routing=SimpleNamespace(model_ref=None),
        workspace_id='global',
        forgejo_token=token,
        idempotency_scope=str(values['idempotency_scope']),
        tenant_id=str(values['tenant_id']),
    )

class RecordingBridge:
    """Task bridge that records and returns creation arguments."""

    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def create_task(self, **kwargs: object) -> dict[str, object]:
        self.events.append('create')
        return kwargs


def provenance_key() -> SimpleNamespace:
    """Return one trusted author key binding."""
    return SimpleNamespace(
        key_id='author-key', tenant_id='tenant', agent_identity='target', task_auth_label='reviewer'
    )
