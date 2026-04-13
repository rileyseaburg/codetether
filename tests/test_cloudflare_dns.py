import importlib.util
import asyncio
import os
import sys
import types
from pathlib import Path

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://user:pass@localhost:5432/test'
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / 'a2a_server'

if 'a2a_server' not in sys.modules:
    package = types.ModuleType('a2a_server')
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules['a2a_server'] = package


def _load_module(module_name: str):
    spec = importlib.util.spec_from_file_location(
        f'a2a_server.{module_name}',
        PACKAGE_DIR / f'{module_name}.py',
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[f'a2a_server.{module_name}'] = module
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_load_module('vault_client')
cloudflare_dns = _load_module('cloudflare_dns')


class FakeVaultClient:
    def __init__(self, secrets):
        self.secrets = secrets
        self.reads = []

    async def read_secret(self, path: str):
        self.reads.append(path)
        return self.secrets.get(path)


def test_setup_tenant_subdomain_uses_vault_token(monkeypatch):
    service = cloudflare_dns.CloudflareDNSService(api_token=None)
    service.api_token = None

    fake_vault = FakeVaultClient(
        {
            'codetether/cloudflare': {
                'api_token': 'vault-token',
            }
        }
    )

    monkeypatch.setattr(
        cloudflare_dns,
        'CLOUDFLARE_VAULT_PATHS',
        ('codetether/cloudflare',),
    )
    monkeypatch.setattr(
        cloudflare_dns, 'get_vault_client', lambda: fake_vault
    )

    async def fake_create_cname_record(subdomain, target, comment=''):
        assert service.api_token == 'vault-token'
        assert subdomain == 'quantum-forge'
        assert target == 'codetether.run'
        assert comment == 'Tenant: tenant-123'
        return cloudflare_dns.CloudflareDNSResult(
            success=True, dns_record_id='dns-record-1'
        )

    async def fake_add_tunnel_ingress(hostname):
        assert hostname == 'quantum-forge.codetether.run'
        assert service.api_token == 'vault-token'
        return True

    monkeypatch.setattr(
        service, '_create_cname_record', fake_create_cname_record
    )
    monkeypatch.setattr(
        service, '_add_tunnel_ingress', fake_add_tunnel_ingress
    )

    result = asyncio.run(
        service.setup_tenant_subdomain(
            subdomain='quantum-forge',
            tenant_id='tenant-123',
        )
    )

    assert result.success is True
    assert result.dns_record_id == 'dns-record-1'
    assert fake_vault.reads == ['codetether/cloudflare']


def test_setup_tenant_subdomain_falls_back_to_legacy_vault_path(monkeypatch):
    service = cloudflare_dns.CloudflareDNSService(api_token=None)
    service.api_token = None

    fake_vault = FakeVaultClient(
        {
            'kv/codetether/cloudflare': {
                'token': 'legacy-token',
                'base_domain': 'tenant.codetether.run',
            }
        }
    )

    monkeypatch.setattr(
        cloudflare_dns,
        'CLOUDFLARE_VAULT_PATHS',
        ('codetether/cloudflare', 'kv/codetether/cloudflare'),
    )
    monkeypatch.setattr(
        cloudflare_dns, 'get_vault_client', lambda: fake_vault
    )

    async def fake_create_cname_record(subdomain, target, comment=''):
        assert service.api_token == 'legacy-token'
        assert target == 'tenant.codetether.run'
        return cloudflare_dns.CloudflareDNSResult(
            success=True, dns_record_id='dns-record-2'
        )

    async def fake_add_tunnel_ingress(hostname):
        assert hostname == 'quantum-forge.tenant.codetether.run'
        return True

    monkeypatch.setattr(
        service, '_create_cname_record', fake_create_cname_record
    )
    monkeypatch.setattr(
        service, '_add_tunnel_ingress', fake_add_tunnel_ingress
    )

    result = asyncio.run(
        service.setup_tenant_subdomain(
            subdomain='quantum-forge',
            tenant_id='tenant-123',
        )
    )

    assert result.success is True
    assert result.dns_record_id == 'dns-record-2'
    assert fake_vault.reads == [
        'codetether/cloudflare',
        'kv/codetether/cloudflare',
    ]


def test_setup_tenant_subdomain_returns_clear_error_without_token(monkeypatch):
    service = cloudflare_dns.CloudflareDNSService(api_token=None)
    service.api_token = None

    fake_vault = FakeVaultClient({})

    monkeypatch.setattr(
        cloudflare_dns,
        'CLOUDFLARE_VAULT_PATHS',
        ('codetether/cloudflare',),
    )
    monkeypatch.setattr(
        cloudflare_dns, 'get_vault_client', lambda: fake_vault
    )

    async def unexpected_create(*_args, **_kwargs):
        raise AssertionError('DNS creation should not run without credentials')

    monkeypatch.setattr(service, '_create_cname_record', unexpected_create)

    result = asyncio.run(
        service.setup_tenant_subdomain(
            subdomain='quantum-forge',
            tenant_id='tenant-123',
        )
    )

    assert result.success is False
    assert result.error_message == (
        'Cloudflare API token not configured in environment or Vault'
    )
    assert fake_vault.reads == ['codetether/cloudflare']
