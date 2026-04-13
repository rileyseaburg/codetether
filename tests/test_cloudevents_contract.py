from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'a2a_server' / 'cloudevents_contract.py'
SPEC = spec_from_file_location('cloudevents_contract', MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
build_event = MODULE.build_event
build_task_created_data = MODULE.build_task_created_data


def test_task_created_data_normalizes_fields():
    data = build_task_created_data(
        'task-1',
        prompt='Fix the bug',
        session_id='sess-1',
        agent_type='build',
        metadata={'workspace_id': 'ws-1'},
    )
    assert data['task_id'] == 'task-1'
    assert data['title'] == 'Fix the bug'
    assert data['description'] == 'Fix the bug'
    assert data['prompt'] == 'Fix the bug'
    assert data['agent_type'] == 'build'
    assert data['agent'] == 'build'


def test_build_event_includes_extensions():
    event = build_event(
        'codetether.task.created',
        {'task_id': 'task-1'},
        event_id='evt-1',
        extensions={'session': 'sess-1', 'tenant': 'tenant-1'},
    )
    assert event['id'] == 'evt-1'
    assert event['type'] == 'codetether.task.created'
    assert event['specversion'] == '1.0'
    assert event['session'] == 'sess-1'
    assert event['tenant'] == 'tenant-1'
