"""FastAPI control plane for the Remote Employee MVP."""

from __future__ import annotations

import hmac
import ipaddress
import os
import re
import uuid

from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from apps.remote_employee.livekit_tokens import LiveKitTokens
from apps.remote_employee.mux import MuxError, MuxGateway
from apps.remote_employee.profiles import build_profile
from apps.remote_employee.storage import Store


APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path.home() / '.local/share/remote-employee'


class HireRequest(BaseModel):
    """CEO request to provision an employee runtime."""

    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=2000)
    workspace: str = Field(min_length=1, max_length=1000)

    @field_validator('name', 'role', 'goal', 'workspace')
    @classmethod
    def trim(cls, value: str) -> str:
        return value.strip()


class TaskRequest(BaseModel):
    """One bounded objective assigned to an employee."""

    objective: str = Field(min_length=1, max_length=8000)
    source: str = Field(default='ceo', max_length=80)

    @field_validator('objective')
    @classmethod
    def trim_objective(cls, value: str) -> str:
        return value.strip()


class MeetingRequest(BaseModel):
    """CEO identity used for a scoped LiveKit room token."""

    identity: str = Field(default_factory=lambda: f'ceo-{uuid.uuid4().hex[:8]}')
    name: str = Field(default='CEO', min_length=1, max_length=128)


class ProposalRequest(BaseModel):
    """Employee-authored organizational action awaiting CEO review."""

    employee_id: str
    kind: Literal['hire', 'delegate', 'meeting']
    title: str = Field(min_length=1, max_length=160)
    details: dict[str, Any]


class DecisionRequest(BaseModel):
    """CEO approval or rejection of an employee proposal."""

    approve: bool


def create_app(  # noqa: PLR0915
    *,
    store: Store | None = None,
    mux: MuxGateway | None = None,
    livekit: LiveKitTokens | None = None,
) -> FastAPI:
    """Build an injectable Remote Employee API application."""
    data_dir = Path(os.getenv('REMOTE_EMPLOYEE_DATA_DIR', DEFAULT_DATA_DIR))
    store = store or Store(data_dir / 'remote-employee.sqlite3')
    mux = mux or MuxGateway()
    livekit = livekit or LiveKitTokens()
    admin_token = os.getenv('REMOTE_EMPLOYEE_ADMIN_TOKEN', '').strip()
    office_room = os.getenv(
        'REMOTE_EMPLOYEE_OFFICE_ROOM', 'remote-employee-office'
    ).strip()
    trusted_lan = os.getenv('REMOTE_EMPLOYEE_TRUSTED_LAN', '').lower() in {
        '1',
        'true',
        'yes',
    }
    trusted_networks = tuple(
        ipaddress.ip_network(item.strip(), strict=False)
        for item in os.getenv('REMOTE_EMPLOYEE_TRUSTED_IPS', '').split(',')
        if item.strip()
    )
    app = FastAPI(title='Remote Employee', version='0.1.0')
    app.state.store = store
    app.state.mux = mux
    app.state.livekit = livekit

    async def require_admin(
        request: Request, authorization: str | None = Header(default=None)
    ) -> None:
        if admin_token:
            supplied = ''
            if authorization and authorization.startswith('Bearer '):
                supplied = authorization[7:]
            if not hmac.compare_digest(supplied, admin_token):
                raise HTTPException(
                    status_code=401, detail='CEO token required'
                )
            return
        client_host = request.client.host if request.client else ''
        cloudflare_client = request.headers.get('cf-connecting-ip', '').strip()
        forwarded_client = request.headers.get('x-forwarded-for', '')
        if cloudflare_client:
            client_host = cloudflare_client
        elif forwarded_client:
            client_host = forwarded_client.split(',', maxsplit=1)[0].strip()
        try:
            client_address = ipaddress.ip_address(client_host)
            private_client = client_address.is_private
            trusted_client = any(
                client_address in network for network in trusted_networks
            )
        except ValueError:
            private_client = client_host in {'localhost', 'testclient'}
            trusted_client = False
        local_clients = {'127.0.0.1', '::1', 'localhost', 'testclient'}
        allowed = (
            client_host in local_clients
            or (trusted_lan and private_client)
            or trusted_client
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=('Set REMOTE_EMPLOYEE_ADMIN_TOKEN before remote access'),
            )

    def employee_or_404(employee_id: str) -> dict[str, Any]:
        employee = store.get_employee(employee_id)
        if not employee:
            raise HTTPException(status_code=404, detail='Employee not found')
        return employee

    async def launch_task(
        employee: dict[str, Any], objective: str, source: str
    ) -> dict[str, Any]:
        if employee['current_task_id'] and employee['status'] == 'working':
            raise HTTPException(
                status_code=409, detail='Employee is already working'
            )
        completion_marker = f'__REMOTE_EMPLOYEE_DONE_{uuid.uuid4().hex}__'
        task = store.create_task(
            employee_id=employee['id'],
            objective=objective,
            source=source,
            completion_marker=completion_marker,
        )
        try:
            await mux.start_task(
                mux_name=employee['mux_name'],
                employee_name=employee['name'],
                role=employee['role'],
                company_goal=employee['goal'],
                objective=objective,
                completion_marker=completion_marker,
            )
        except (MuxError, OSError) as error:
            store.update_task_status(task['id'], 'failed')
            raise HTTPException(status_code=502, detail=str(error)) from error
        store.set_employee_runtime(
            employee['id'],
            status='working',
            task_id=task['id'],
            output_offset=0,
            output_tail='',
        )
        return store.get_task(task['id']) or task

    @app.get('/api/health')
    async def health() -> dict[str, Any]:
        return {
            'status': 'ok',
            'livekit_configured': livekit.configured,
            'codetether_binary': mux.binary,
        }

    @app.get('/api/config')
    async def config() -> dict[str, Any]:
        return {
            'auth_required': bool(admin_token),
            'livekit_configured': livekit.configured,
            'livekit_url': livekit.url,
        }

    @app.get('/api/company', dependencies=[Depends(require_admin)])
    async def company() -> dict[str, Any]:
        employees = store.list_employees()
        used_voices = {
            employee['profile'].get('voice')
            for employee in employees
            if employee['profile'].get('voice')
        }
        refreshed: list[dict[str, Any]] = []
        for employee in employees:
            if not employee['profile']:
                profile = build_profile(
                    name=employee['name'],
                    role=employee['role'],
                    seed=employee['id'],
                    unavailable_voices=used_voices,
                )
                store.set_employee_profile(employee['id'], profile)
                used_voices.add(profile['voice'])
                employee['profile'] = profile
            if employee['status'] == 'working':
                try:
                    result = await mux.read_task(
                        employee['mux_name'], int(employee['output_offset'])
                    )
                    output = (employee['output_tail'] + result['output'])[
                        -12000:
                    ]
                    task_id = employee['current_task_id']
                    task = store.get_task(task_id) if task_id else None
                    marker = task['completion_marker'] if task else ''
                    match = (
                        re.search(re.escape(marker) + r':(\d+)', output)
                        if marker
                        else None
                    )
                    finished = match is not None
                    exit_code = int(match.group(1)) if match else None
                    status = (
                        'review'
                        if finished and exit_code == 0
                        else 'blocked'
                        if finished
                        else 'working'
                    )
                    store.set_employee_runtime(
                        employee['id'],
                        status=status,
                        task_id=task_id,
                        output_offset=result['offset'],
                        output_tail=output,
                    )
                    if task_id and finished:
                        store.update_task_status(task_id, status)
                except (MuxError, OSError):
                    store.set_employee_runtime(
                        employee['id'],
                        status='offline',
                        task_id=employee['current_task_id'],
                    )
            refreshed.append(store.get_employee(employee['id']) or employee)
        return {
            'employees': refreshed,
            'tasks': store.list_tasks(),
            'proposals': store.list_proposals(),
        }

    @app.post(
        '/api/employees', status_code=201, dependencies=[Depends(require_admin)]
    )
    async def hire(payload: HireRequest) -> dict[str, Any]:
        workspace = Path(payload.workspace).expanduser().resolve()
        if not workspace.is_dir():
            raise HTTPException(
                status_code=400,
                detail='Workspace must be an existing directory',
            )
        slug = re.sub(r'[^a-z0-9]+', '-', payload.name.lower()).strip('-')[:30]
        slug = slug or 'employee'
        suffix = uuid.uuid4().hex[:8]
        mux_name = f're-{slug}-{suffix}'
        room_name = f'remote-employee-{suffix}'
        unavailable_voices = {
            employee['profile'].get('voice')
            for employee in store.list_employees()
            if employee['profile'].get('voice')
        }
        profile = build_profile(
            name=payload.name,
            role=payload.role,
            seed=suffix,
            unavailable_voices=unavailable_voices,
        )
        try:
            await mux.create(mux_name, workspace)
        except (MuxError, OSError) as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        try:
            return store.create_employee(
                name=payload.name,
                role=payload.role,
                goal=payload.goal,
                workspace=str(workspace),
                mux_name=mux_name,
                room_name=room_name,
                profile=profile,
            )
        except Exception:
            await mux.kill(mux_name)
            raise

    @app.delete(
        '/api/employees/{employee_id}', dependencies=[Depends(require_admin)]
    )
    async def fire(employee_id: str) -> dict[str, bool]:
        employee = employee_or_404(employee_id)
        try:
            await mux.kill(employee['mux_name'])
        except MuxError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        store.delete_employee(employee_id)
        return {'deleted': True}

    @app.post(
        '/api/employees/{employee_id}/tasks',
        status_code=202,
        dependencies=[Depends(require_admin)],
    )
    async def assign(employee_id: str, payload: TaskRequest) -> dict[str, Any]:
        return await launch_task(
            employee_or_404(employee_id), payload.objective, payload.source
        )

    @app.post('/api/office-token', dependencies=[Depends(require_admin)])
    async def office_token(payload: MeetingRequest) -> dict[str, str]:
        """Join the shared office with camera, mic, and subscriptions."""
        try:
            return livekit.issue(
                identity=payload.identity,
                room=office_room,
                name=payload.name,
                role='ceo',
            )
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post(
        '/api/employees/{employee_id}/meeting-token',
        dependencies=[Depends(require_admin)],
    )
    async def meeting_token(
        employee_id: str, payload: MeetingRequest
    ) -> dict[str, str]:
        employee = employee_or_404(employee_id)
        try:
            return livekit.issue(
                identity=payload.identity,
                room=employee['room_name'],
                name=payload.name,
                role='ceo',
            )
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.post(
        '/api/proposals', status_code=201, dependencies=[Depends(require_admin)]
    )
    async def propose(payload: ProposalRequest) -> dict[str, Any]:
        employee_or_404(payload.employee_id)
        return store.create_proposal(
            employee_id=payload.employee_id,
            kind=payload.kind,
            title=payload.title,
            details=payload.details,
        )

    @app.post(
        '/api/proposals/{proposal_id}/decision',
        dependencies=[Depends(require_admin)],
    )
    async def decide(
        proposal_id: str, payload: DecisionRequest
    ) -> dict[str, Any]:
        proposal = store.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail='Proposal not found')
        if proposal['status'] != 'pending':
            raise HTTPException(
                status_code=409, detail='Proposal is already decided'
            )
        if not payload.approve:
            store.decide_proposal(proposal_id, 'rejected')
            return store.get_proposal(proposal_id) or proposal

        details = proposal['details']
        if proposal['kind'] == 'delegate':
            target_id = str(details.get('target_employee_id', ''))
            objective = str(details.get('objective', '')).strip()
            if not objective:
                raise HTTPException(
                    status_code=400, detail='Delegation needs an objective'
                )
            result = await launch_task(
                employee_or_404(target_id),
                objective,
                f'employee:{proposal["employee_id"]}',
            )
        elif proposal['kind'] == 'hire':
            required = ('name', 'role', 'goal', 'workspace')
            if not all(str(details.get(key, '')).strip() for key in required):
                raise HTTPException(
                    status_code=400, detail='Hire proposal is incomplete'
                )
            result = await hire(HireRequest(**details))
        else:
            employee = employee_or_404(proposal['employee_id'])
            result = {'room_name': employee['room_name'], 'ready': True}
        store.decide_proposal(proposal_id, 'approved')
        return {'proposal': store.get_proposal(proposal_id), 'result': result}

    app.mount(
        '/static', StaticFiles(directory=APP_DIR / 'static'), name='static'
    )

    @app.get('/')
    async def index() -> FileResponse:
        return FileResponse(APP_DIR / 'static/index.html')

    return app


app = create_app()


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=8090)
