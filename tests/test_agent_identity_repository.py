import pytest

import a2a_server.agent_identity_repository as repository


class Connection:
    def __init__(self, row):
        self.row = row

    async def execute(self, *_):
        return 'INSERT 0 1'

    async def fetchrow(self, *_):
        return self.row


class Acquire:
    def __init__(self, row):
        self.connection = Connection(row)

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_):
        return None


class Pool:
    def __init__(self, row):
        self.row = row

    def acquire(self):
        return Acquire(self.row)


@pytest.mark.asyncio
async def test_binding_replay_is_exact(monkeypatch):
    receipt = {
        'provisioning_id': 'hire-1',
        'persona_id': 'manager',
        'spiffe_id': 'spiffe://td/ns/a/sa/b',
        'keycloak_subject': 'sub-1',
        'keycloak_realm': 'spotless',
        'realm_roles': ['line-manager'],
        'groups': ['engineering'],
        'opa_policy_binding_id': 'binding-1',
        'opa_policy_revision': 'sha256:1',
        'provenance_id': 'ctprov_1234567890123456',
    }
    row = dict(receipt)
    row['roles'] = row.pop('realm_roles')
    row['policy_binding_id'] = row.pop('opa_policy_binding_id')
    row['policy_revision'] = row.pop('opa_policy_revision')
    row['tenant_id'] = 'tenant-1'
    monkeypatch.setattr(repository, '_database_pool', lambda: _pool(Pool(row)))
    binding = await repository.save_binding(receipt)
    assert binding.policy_user()['roles'] == ['line-manager']


async def _pool(value):
    return value
