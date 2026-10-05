# ruff: noqa: PLR2004

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apps.remote_employee.server import create_app
from apps.remote_employee.storage import Store


class FakeMux:
    binary = 'codetether-test'

    def __init__(self):
        self.created: list[tuple[str, Path]] = []
        self.killed: list[str] = []
        self.started: list[dict] = []
        self.complete = True

    async def create(self, name: str, workspace: Path) -> None:
        self.created.append((name, workspace))

    async def kill(self, name: str) -> None:
        self.killed.append(name)

    async def start_task(self, **kwargs) -> None:
        self.started.append(kwargs)

    async def read_task(self, mux_name: str, offset: int) -> dict:
        task = self.started[-1]
        if self.complete:
            output = f'Agent report\n{task["completion_marker"]}:0\n'
        else:
            # A terminal echoes the submitted printf command before it executes.
            output = (
                f"printf '{task['completion_marker']}:%s'\nAgent is working"
            )
        return {'output': output, 'offset': offset + len(output.encode())}


class FakeLiveKit:
    configured = True
    url = 'wss://live.example.test'

    def __init__(self):
        self.issued: list[dict] = []

    def issue(self, **kwargs) -> dict[str, str]:
        self.issued.append(kwargs)
        return {'url': self.url, 'room': kwargs['room'], 'token': 'scoped-jwt'}


def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv('REMOTE_EMPLOYEE_ADMIN_TOKEN', 'ceo-secret')
    mux = FakeMux()
    livekit = FakeLiveKit()
    app = create_app(
        store=Store(tmp_path / 'company.sqlite3'), mux=mux, livekit=livekit
    )
    return TestClient(app), mux, livekit


def auth() -> dict[str, str]:
    return {'Authorization': 'Bearer ceo-secret'}


def hire(test_client: TestClient, workspace: Path, name: str = 'Maya') -> dict:
    response = test_client.post(
        '/api/employees',
        headers=auth(),
        json={
            'name': name,
            'role': 'Head of Sales',
            'goal': 'Build a qualified pipeline',
            'workspace': str(workspace),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_hiring_creates_one_real_runtime_record(tmp_path, monkeypatch):
    test_client, mux, _ = client(tmp_path, monkeypatch)

    employee = hire(test_client, tmp_path)

    assert employee['name'] == 'Maya'
    assert employee['mux_name'].startswith('re-maya-')
    assert employee['room_name'].startswith('remote-employee-')
    assert mux.created == [(employee['mux_name'], tmp_path.resolve())]
    company = test_client.get('/api/company', headers=auth()).json()
    assert [item['id'] for item in company['employees']] == [employee['id']]


def test_task_runs_in_employee_mux_and_completion_is_detected(
    tmp_path, monkeypatch
):
    test_client, mux, _ = client(tmp_path, monkeypatch)
    employee = hire(test_client, tmp_path)

    response = test_client.post(
        f'/api/employees/{employee["id"]}/tasks',
        headers=auth(),
        json={'objective': 'Prepare the launch plan'},
    )

    assert response.status_code == 202, response.text
    assert mux.started[0]['mux_name'] == employee['mux_name']
    assert mux.started[0]['objective'] == 'Prepare the launch plan'
    assert mux.started[0]['completion_marker'].startswith(
        '__REMOTE_EMPLOYEE_DONE_'
    )

    company = test_client.get('/api/company', headers=auth()).json()
    refreshed = company['employees'][0]
    assert refreshed['status'] == 'review'
    assert 'Agent report' in refreshed['output_tail']
    assert company['tasks'][0]['status'] == 'review'


def test_echoed_completion_command_does_not_finish_task(tmp_path, monkeypatch):
    test_client, mux, _ = client(tmp_path, monkeypatch)
    employee = hire(test_client, tmp_path)
    mux.complete = False
    response = test_client.post(
        f'/api/employees/{employee["id"]}/tasks',
        headers=auth(),
        json={'objective': 'Prepare the launch plan'},
    )
    assert response.status_code == 202

    company = test_client.get('/api/company', headers=auth()).json()

    assert company['employees'][0]['status'] == 'working'
    assert company['tasks'][0]['status'] == 'running'

    mux.complete = True
    company = test_client.get('/api/company', headers=auth()).json()

    assert company['employees'][0]['status'] == 'review'
    assert company['tasks'][0]['status'] == 'review'


def test_office_and_private_tokens_are_server_scoped(tmp_path, monkeypatch):
    test_client, _, livekit = client(tmp_path, monkeypatch)
    employee = hire(test_client, tmp_path)

    office = test_client.post(
        '/api/office-token', headers=auth(), json={'name': 'CEO'}
    )
    private = test_client.post(
        f'/api/employees/{employee["id"]}/meeting-token',
        headers=auth(),
        json={'name': 'CEO'},
    )

    assert office.status_code == 200
    assert office.json()['room'] == 'remote-employee-office'
    assert private.json()['room'] == employee['room_name']
    assert all(call['role'] == 'ceo' for call in livekit.issued)


def test_hire_proposal_requires_ceo_decision(tmp_path, monkeypatch):
    test_client, mux, _ = client(tmp_path, monkeypatch)
    proposer = hire(test_client, tmp_path, 'Maya')
    response = test_client.post(
        '/api/proposals',
        headers=auth(),
        json={
            'employee_id': proposer['id'],
            'kind': 'hire',
            'title': 'Add an SDR',
            'details': {
                'name': 'Ari',
                'role': 'SDR',
                'goal': 'Qualify inbound leads',
                'workspace': str(tmp_path),
            },
        },
    )
    assert response.status_code == 201
    proposal = response.json()
    assert len(mux.created) == 1

    decision = test_client.post(
        f'/api/proposals/{proposal["id"]}/decision',
        headers=auth(),
        json={'approve': True},
    )

    assert decision.status_code == 200, decision.text
    assert decision.json()['proposal']['status'] == 'approved'
    assert len(mux.created) == 2


def test_admin_token_is_required_for_company_operations(tmp_path, monkeypatch):
    test_client, _, _ = client(tmp_path, monkeypatch)

    assert test_client.get('/api/company').status_code == 401
    assert test_client.get('/api/health').status_code == 200


def test_missing_workspace_does_not_create_mux(tmp_path, monkeypatch):
    test_client, mux, _ = client(tmp_path, monkeypatch)
    response = test_client.post(
        '/api/employees',
        headers=auth(),
        json={
            'name': 'Maya',
            'role': 'Sales',
            'goal': 'Sell',
            'workspace': str(tmp_path / 'missing'),
        },
    )
    assert response.status_code == 400
    assert mux.created == []
