from a2a_server.automation_api import CreateTaskRequest, DispatchTaskRequest
from a2a_server.monitor_api import (
    WorkspaceRegistration,
    _build_vm_spec_from_registration,
)
from a2a_server.vm_workspace_provisioner import VMWorkspaceSpec


def test_create_task_request_prefers_workspace_id():
    request = CreateTaskRequest(
        title='task',
        description='0123456789',
        workspace_id='ws-1',
    )
    assert request.resolved_workspace_id() == 'ws-1'


def test_dispatch_request_treats_global_as_none():
    request = DispatchTaskRequest(
        title='task',
        description='0123456789',
        codebase_id='global',
    )
    assert request.resolved_workspace_id() is None


def test_vm_spec_uses_current_defaults():
    spec = _build_vm_spec_from_registration(
        WorkspaceRegistration(name='vm', runtime='vm')
    )
    assert spec.memory == VMWorkspaceSpec().memory
