import os
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault(
    'DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/a2a_server',
)

from a2a_server.keycloak_auth import UserSession, require_admin
from a2a_server.tenant_deployments import router
from a2a_server.vm_workspace_provisioner import VMWorkspaceResult
import a2a_server.tenant_deployments.dedicated as dedicated_mod
import a2a_server.tenant_deployments.listing as listing_mod
import a2a_server.tenant_deployments.vm as vm_mod


def _admin_user(tenant_id: str = 'tenant-a') -> UserSession:
    return UserSession(
        user_id='user-1',
        email='admin@example.com',
        username='admin',
        name='Admin',
        session_id='session-1',
        access_token='token',
        refresh_token=None,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        roles=['admin'],
        tenant_id=tenant_id,
        realm_name=f'{tenant_id}.codetether.run',
    )


@pytest_asyncio.fixture
async def client():
    app = FastAPI()
    app.include_router(router)

    async def _override():
        return _admin_user()

    app.dependency_overrides[require_admin] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        yield ac


@pytest.mark.asyncio
async def test_dedicated_instance_deployment_api(client, monkeypatch):
    tenant = {'id': 'tenant-a', 'realm_name': 'tenant-a.codetether.run', 'plan': 'free'}
    captured = {}

    async def fake_get_tenant(tenant_id: str):
        assert tenant_id == 'tenant-a'
        return tenant

    async def fake_update_tenant(tenant_id: str, **kwargs):
        captured['tenant_id'] = tenant_id
        captured['update'] = kwargs
        return {**tenant, **kwargs, 'plan': kwargs.get('plan', tenant['plan'])}

    class FakeK8sService:
        async def provision_instance(self, **kwargs):
            captured['provision'] = kwargs
            return SimpleNamespace(
                success=True,
                namespace='tenant-tenant-a',
                external_url='https://tenant-a.codetether.run',
                internal_url='http://a2a.tenant-a.svc.cluster.local:8000',
                status=SimpleNamespace(value='completed'),
                error_message=None,
            )

    monkeypatch.setattr(dedicated_mod, 'get_tenant_by_id', fake_get_tenant)
    monkeypatch.setattr(dedicated_mod, 'update_tenant', fake_update_tenant)
    monkeypatch.setattr(dedicated_mod, 'k8s_provisioning_service', FakeK8sService())

    response = await client.post(
        '/v1/tenants/tenant-a/deployments/dedicated-instance',
        json={'tier': 'pro'},
    )

    assert response.status_code == 201
    body = response.json()
    assert body['deployment']['driver'] == 'kubernetes'
    assert body['deployment']['namespace'] == 'tenant-tenant-a'
    assert body['deployment']['plan'] == 'pro'
    assert captured['provision']['org_slug'] == 'tenant-a'
    assert captured['update']['k8s_external_url'] == 'https://tenant-a.codetether.run'


@pytest.mark.asyncio
async def test_workspace_vm_deployment_api(client, monkeypatch):
    tenant = {'id': 'tenant-a', 'realm_name': 'tenant-a.codetether.run', 'plan': 'free'}
    captured = {}

    async def fake_get_tenant(_tenant_id: str):
        return tenant

    async def fake_upsert_workspace(workspace, tenant_id=None):
        captured['workspace'] = workspace
        captured['tenant_id'] = tenant_id
        return True

    async def fake_hydrate(workspace):
        captured['hydrated'] = workspace['id']

    class FakeProvisioner:
        async def provision_workspace_vm(self, **kwargs):
            captured['provision'] = kwargs
            return VMWorkspaceResult(
                success=True,
                vm_name='codetether-vm-tenant-a',
                namespace='a2a-server',
                pvc_name='codetether-vm-workspace-tenant-a',
                ssh_service_name='codetether-vm-tenant-a-ssh',
                ssh_host='codetether-vm-tenant-a-ssh.a2a-server.svc.cluster.local',
                ssh_port=22,
                status='Running',
            )

    monkeypatch.setattr(vm_mod, 'get_tenant_by_id', fake_get_tenant)
    monkeypatch.setattr(vm_mod.db, 'db_upsert_workspace', fake_upsert_workspace)
    monkeypatch.setattr(vm_mod, '_hydrate_bridge', fake_hydrate)
    monkeypatch.setattr(vm_mod, 'vm_workspace_provisioner', FakeProvisioner())

    response = await client.post(
        '/v1/tenants/tenant-a/deployments/workspace-vm',
        json={'name': 'marketing-site', 'path': '/workspace/repos/marketing-site'},
    )

    assert response.status_code == 201
    body = response.json()
    assert body['deployment']['runtime'] == 'vm'
    assert body['deployment']['vm_status'] == 'Running'
    assert captured['tenant_id'] == 'tenant-a'
    assert captured['workspace']['agent_config']['workspace_runtime'] == 'vm'


@pytest.mark.asyncio
async def test_list_tenant_deployments_reports_both_runtime_paths(client, monkeypatch):
    tenant = {
        'id': 'tenant-a',
        'realm_name': 'tenant-a.codetether.run',
        'plan': 'enterprise',
        'k8s_namespace': 'tenant-tenant-a',
        'k8s_external_url': 'https://tenant-a.codetether.run',
        'k8s_internal_url': 'http://a2a.tenant-a.svc.cluster.local:8000',
    }

    async def fake_get_tenant(_tenant_id: str):
        return tenant

    async def fake_list_workspaces(tenant_id=None):
        assert tenant_id == 'tenant-a'
        return [
            {
                'id': 'ws-vm-1',
                'name': 'marketing-site',
                'path': '/workspace/repos/marketing-site',
                'status': 'active',
                'agent_config': {
                    'workspace_runtime': 'vm',
                    'vm_provider': 'kubevirt',
                    'vm_name': 'codetether-vm-ws-vm-1',
                    'vm_namespace': 'a2a-server',
                    'vm_status': 'Provisioning',
                    'vm_ssh_host': 'ssh.a2a-server.svc.cluster.local',
                    'vm_ssh_port': 22,
                },
            }
        ]

    class FakeProvisioner:
        async def get_vm_status(self, vm_name: str):
            assert vm_name == 'codetether-vm-ws-vm-1'
            return 'Running'

    monkeypatch.setattr(listing_mod, 'get_tenant_by_id', fake_get_tenant)
    monkeypatch.setattr(listing_mod.db, 'db_list_workspaces', fake_list_workspaces)
    monkeypatch.setattr(listing_mod, 'vm_workspace_provisioner', FakeProvisioner())

    response = await client.get('/v1/tenants/tenant-a/deployments')

    assert response.status_code == 200
    body = response.json()
    assert body['dedicated_instance']['namespace'] == 'tenant-tenant-a'
    assert body['workspace_vms'][0]['workspace_id'] == 'ws-vm-1'
    assert body['workspace_vms'][0]['vm_status'] == 'Running'


@pytest.mark.asyncio
async def test_list_tenant_deployments_uses_deployment_metadata_for_slug(client, monkeypatch):
    tenant = {
        'id': 'tenant-a',
        'realm_name': 'quantum-forge',
        'plan': 'enterprise',
        'k8s_namespace': 'tenant-quantum-forge',
        'k8s_external_url': 'https://quantum-forge.codetether.run',
    }

    async def fake_get_tenant(_tenant_id: str):
        return tenant

    async def fake_list_workspaces(tenant_id=None):
        assert tenant_id == 'tenant-a'
        return []

    monkeypatch.setattr(listing_mod, 'get_tenant_by_id', fake_get_tenant)
    monkeypatch.setattr(listing_mod.db, 'db_list_workspaces', fake_list_workspaces)

    response = await client.get('/v1/tenants/tenant-a/deployments')

    assert response.status_code == 200
    assert response.json()['dedicated_instance']['org_slug'] == 'quantum-forge'
