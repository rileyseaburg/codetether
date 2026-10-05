"""Worker routing must not pin tasks to one pod in an interchangeable pool.

Discovery previously copied the selected worker's name into
`target_agent_name`, so a task could only be claimed by that single pod. While
it ran a long build, identical idle siblings were ineligible and a freshly filed
issue waited behind unrelated work.
"""

from __future__ import annotations

import importlib

import pytest


def _routing(monkeypatch: pytest.MonkeyPatch, **env: str):
    for key in (
        'GITHUB_APP_TARGET_AGENT',
        'GITHUB_APP_TARGET_WORKER_ID',
        'GITHUB_APP_TARGET_CAPABILITIES',
        'GITHUB_APP_PREFERRED_AGENTS',
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    settings = importlib.reload(
        importlib.import_module('a2a_server.github_app.settings')
    )
    routing = importlib.reload(
        importlib.import_module('a2a_server.github_app.routing')
    )
    assert settings is not None
    return routing


def test_discovery_does_not_pin_to_a_single_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = _routing(monkeypatch)
    worker = {
        'name': 'harvester-a2a-server-harvester-0',
        'capabilities': ['persistent-workspace'],
        'is_busy': False,
    }

    metadata = routing._worker_routing_metadata(worker)

    assert 'target_agent_name' not in metadata, (
        'a busy pod must not block identical idle siblings'
    )
    assert metadata['required_capabilities'] == ['persistent-workspace']


def test_explicit_operator_target_still_pins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = _routing(
        monkeypatch, GITHUB_APP_TARGET_AGENT='harvester-a2a-server-harvester-1'
    )
    worker = {'name': 'harvester-a2a-server-harvester-0', 'is_busy': False}

    metadata = routing._worker_routing_metadata(worker)

    assert (
        metadata['target_agent_name'] == 'harvester-a2a-server-harvester-1'
    ), 'an explicit override is intentional and must be honored'


def test_capability_aliases_are_canonicalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = _routing(
        monkeypatch,
        GITHUB_APP_TARGET_CAPABILITIES='harvester,persistent,persistent_workspace',
    )

    metadata = routing.clone_task_routing_metadata()

    assert metadata['required_capabilities'] == ['persistent-workspace']


def test_worker_id_override_skips_capability_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = _routing(monkeypatch, GITHUB_APP_TARGET_WORKER_ID='wrk-fixed')

    metadata = routing.clone_task_routing_metadata()

    assert 'required_capabilities' not in metadata
