import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from a2a_server.github_app import rudder_incidents


HTTP_OK = 200
HTTP_UNPROCESSABLE_ENTITY = 422
INSTALLATION_ID = 123
CREATED_ISSUE_NUMBER = 42
EXISTING_ISSUE_NUMBER = 7
ISSUES_PATH = '/repos/spotlessbinco/spotlessbinco/issues'
LOG_INCIDENTS_PATH = '/v1/integrations/rudder/log-incidents'


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(rudder_incidents, 'verify_auth', lambda request: None)
    app = FastAPI()
    app.include_router(rudder_incidents.rudder_incident_router)
    return TestClient(app)


def incident_payload(**overrides):
    payload = {
        'repo': 'spotlessbinco/spotlessbinco',
        'fingerprint': 'abc123',
        'severity': 'error',
        'namespace': 'spotlessbinco',
        'release': 'spotlessbinco-deployment',
        'workload': 'api',
        'pod': 'api-123',
        'container': 'api',
        'reason': 'CrashLoopBackOff',
        'message': 'api is crashlooping',
        'log_excerpt': 'Traceback example',
        'labels': ['prod'],
        'policy': {'auto_create': True, 'update_existing': True},
    }
    payload.update(overrides)
    return payload


def test_forgejo_is_default_and_creates_issue(client, monkeypatch):
    calls = []

    async def fake_forgejo_json(method, path, payload=None):
        calls.append((method, path, payload))
        if method == 'GET':
            return []
        return {
            'number': CREATED_ISSUE_NUMBER,
            'html_url': (
                'https://forgejo.example/spotlessbinco/spotlessbinco/issues/42'
            ),
        }

    monkeypatch.setattr(rudder_incidents, 'forgejo_json', fake_forgejo_json)

    response = client.post(
        LOG_INCIDENTS_PATH,
        json=incident_payload(),
    )

    assert response.status_code == HTTP_OK
    assert response.json()['provider'] == 'forgejo'
    assert response.json()['action'] == 'created_issue'
    assert response.json()['issue_number'] == CREATED_ISSUE_NUMBER
    assert calls[-1][0] == 'POST'
    assert calls[-1][1] == ISSUES_PATH
    assert 'rudder-log-fingerprint: abc123' in calls[-1][2]['body']


def test_forgejo_updates_existing_issue(client, monkeypatch):
    calls = []

    async def fake_forgejo_json(method, path, payload=None):
        calls.append((method, path, payload))
        if method == 'GET':
            return [
                {
                    'number': EXISTING_ISSUE_NUMBER,
                    'body': '<!-- rudder-log-fingerprint: abc123 -->',
                    'html_url': 'https://forgejo.example/issue/7',
                },
            ]
        return {}

    monkeypatch.setattr(rudder_incidents, 'forgejo_json', fake_forgejo_json)

    response = client.post(
        LOG_INCIDENTS_PATH,
        json=incident_payload(),
    )

    assert response.status_code == HTTP_OK
    assert response.json()['action'] == 'updated_existing_issue'
    assert response.json()['issue_number'] == EXISTING_ISSUE_NUMBER
    assert calls[-1][0] == 'POST'
    assert calls[-1][1] == f'{ISSUES_PATH}/7/comments'


def test_github_provider_requires_installation_id(client):
    response = client.post(
        LOG_INCIDENTS_PATH,
        json=incident_payload(provider='github'),
    )

    assert response.status_code == HTTP_UNPROCESSABLE_ENTITY
    assert 'installation_id is required' in response.text


def test_github_legacy_path_still_supported(client, monkeypatch):
    async def fake_installation_token(installation_id):
        assert installation_id == INSTALLATION_ID
        return 'token', 'later'

    async def fake_find_existing_issue(repo, fingerprint, token):
        return None

    github_calls = []

    async def fake_github_json(method, path, token, payload=None):
        github_calls.append((method, path, token, payload))
        return {
            'number': 9,
            'html_url': 'https://github.example/issues/9',
        }

    monkeypatch.setattr(
        rudder_incidents,
        'installation_token',
        fake_installation_token,
    )
    monkeypatch.setattr(
        rudder_incidents,
        '_find_existing_issue',
        fake_find_existing_issue,
    )
    monkeypatch.setattr(rudder_incidents, 'github_json', fake_github_json)

    response = client.post(
        LOG_INCIDENTS_PATH,
        json=incident_payload(
            provider='github',
            installation_id=INSTALLATION_ID,
        ),
    )

    assert response.status_code == HTTP_OK
    assert response.json()['provider'] == 'github'
    assert response.json()['action'] == 'created_issue'
    assert github_calls[-1][1] == ISSUES_PATH
