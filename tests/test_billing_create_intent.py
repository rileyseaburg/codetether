import sys
import types
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if 'aiohttp' not in sys.modules:
    aiohttp_stub = types.ModuleType('aiohttp')

    class ClientSession:
        pass

    aiohttp_stub.ClientSession = ClientSession
    sys.modules['aiohttp'] = aiohttp_stub


if 'jose' not in sys.modules:
    jose_stub = types.ModuleType('jose')
    jose_stub.jwt = types.SimpleNamespace()
    jose_stub.jwk = types.SimpleNamespace()

    class JWTError(Exception):
        pass

    jose_stub.JWTError = JWTError
    sys.modules['jose'] = jose_stub
    jose_utils_stub = types.ModuleType('jose.utils')
    jose_utils_stub.base64url_decode = lambda value: value
    sys.modules['jose.utils'] = jose_utils_stub

if 'stripe' not in sys.modules:
    stripe_stub = types.ModuleType('stripe')

    class StripeError(Exception):
        pass

    class InvalidRequestError(StripeError):
        pass

    stripe_stub.StripeError = StripeError
    stripe_stub.InvalidRequestError = InvalidRequestError
    stripe_stub.Customer = types.SimpleNamespace()
    stripe_stub.Subscription = types.SimpleNamespace()
    stripe_stub.SubscriptionItem = types.SimpleNamespace()
    stripe_stub.SetupIntent = types.SimpleNamespace()
    stripe_stub.checkout = types.SimpleNamespace(Session=types.SimpleNamespace())
    stripe_stub.billing_portal = types.SimpleNamespace(Session=types.SimpleNamespace())
    stripe_stub.api_key = None
    sys.modules['stripe'] = stripe_stub

from a2a_server import billing_api
from a2a_server.billing_api import router
from a2a_server.billing_service import BillingServiceError, CustomerNotFoundError
from a2a_server.keycloak_auth import UserSession


@dataclass
class FakeBilling:
    create_customer: AsyncMock
    create_setup_intent: AsyncMock


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    yield app
    app.dependency_overrides.clear()


def install_auth(app, tenant_id='tenant-1'):
    async def fake_auth():
        return UserSession(
            user_id='user-1',
            email='buyer@example.com',
            username='buyer',
            name='Buyer Example',
            session_id='session-1',
            access_token='token',
            refresh_token=None,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            roles=[],
            tenant_id=tenant_id,
        )

    app.dependency_overrides[billing_api.require_auth] = fake_auth


def install_billing(app, billing):
    async def fake_billing():
        return billing

    app.dependency_overrides[billing_api.get_billing_service] = fake_billing


@pytest.mark.asyncio
async def test_create_intent_creates_first_time_customer_and_setup_intent(app, monkeypatch):
    install_auth(app)
    billing = FakeBilling(
        create_customer=AsyncMock(return_value='cus_new'),
        create_setup_intent=AsyncMock(return_value='seti_secret_123'),
    )
    install_billing(app, billing)

    monkeypatch.setattr(
        billing_api,
        'get_tenant_by_id',
        AsyncMock(return_value={'id': 'tenant-1', 'display_name': 'Tenant One'}),
    )
    update_tenant = AsyncMock()
    monkeypatch.setattr(billing_api, 'update_tenant_stripe', update_tenant)

    response = TestClient(app).post(
        '/v1/billing/create-intent', headers={'authorization': 'Bearer test'}
    )

    assert response.status_code == 200
    assert response.json() == {'client_secret': 'seti_secret_123'}
    billing.create_customer.assert_awaited_once_with(
        tenant_id='tenant-1', email='buyer@example.com', name='Tenant One'
    )
    update_tenant.assert_awaited_once_with(
        tenant_id='tenant-1', customer_id='cus_new', subscription_id=''
    )
    billing.create_setup_intent.assert_awaited_once_with('cus_new')


@pytest.mark.asyncio
async def test_create_intent_uses_existing_customer(app, monkeypatch):
    install_auth(app)
    billing = FakeBilling(
        create_customer=AsyncMock(),
        create_setup_intent=AsyncMock(return_value='seti_existing_secret'),
    )
    install_billing(app, billing)
    monkeypatch.setattr(
        billing_api,
        'get_tenant_by_id',
        AsyncMock(return_value={'id': 'tenant-1', 'stripe_customer_id': 'cus_existing'}),
    )
    monkeypatch.setattr(billing_api, 'update_tenant_stripe', AsyncMock())

    response = TestClient(app).post(
        '/v1/billing/create-intent', headers={'authorization': 'Bearer test'}
    )

    assert response.status_code == 200
    assert response.json() == {'client_secret': 'seti_existing_secret'}
    billing.create_customer.assert_not_awaited()
    billing.create_setup_intent.assert_awaited_once_with('cus_existing')


@pytest.mark.asyncio
async def test_create_intent_customer_not_found_returns_400(app, monkeypatch):
    install_auth(app)
    billing = FakeBilling(
        create_customer=AsyncMock(),
        create_setup_intent=AsyncMock(side_effect=CustomerNotFoundError('missing')),
    )
    install_billing(app, billing)
    monkeypatch.setattr(
        billing_api,
        'get_tenant_by_id',
        AsyncMock(return_value={'id': 'tenant-1', 'stripe_customer_id': 'cus_missing'}),
    )

    response = TestClient(app).post(
        '/v1/billing/create-intent', headers={'authorization': 'Bearer test'}
    )

    assert response.status_code == 400
    assert response.json() == {'detail': 'Customer not found in Stripe'}


@pytest.mark.asyncio
async def test_create_intent_service_error_returns_500(app, monkeypatch):
    install_auth(app)
    billing = FakeBilling(
        create_customer=AsyncMock(),
        create_setup_intent=AsyncMock(side_effect=BillingServiceError('stripe down')),
    )
    install_billing(app, billing)
    monkeypatch.setattr(
        billing_api,
        'get_tenant_by_id',
        AsyncMock(return_value={'id': 'tenant-1', 'stripe_customer_id': 'cus_existing'}),
    )

    response = TestClient(app).post(
        '/v1/billing/create-intent', headers={'authorization': 'Bearer test'}
    )

    assert response.status_code == 500
    assert response.json() == {'detail': 'stripe down'}
