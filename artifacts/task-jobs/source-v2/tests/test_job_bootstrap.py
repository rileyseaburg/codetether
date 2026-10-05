"""Bootstrap boundary tests; mocked local, no repositories cloned."""

import importlib.util

from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    'job_bootstrap', Path('scripts/harvester/job_bootstrap.py')
)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


@pytest.mark.parametrize('workspace', ['../existing', '/outside', 'id;command'])
def test_workspace_cannot_escape_job_mount(workspace):
    with pytest.raises(ValueError, match='workspace_identifier_invalid'):
        bootstrap.prepare({'JOB_WORKSPACE_ID': workspace})


def test_url_credentials_are_not_accepted(monkeypatch):
    monkeypatch.setattr(bootstrap.Path, 'exists', lambda p: False)
    with pytest.raises(ValueError, match='git_url_invalid'):
        bootstrap.prepare(
            {
                'JOB_WORKSPACE_ID': 'ws',
                'JOB_GIT_URL': 'https://user:canary@forge.example/o/r',
            }
        )


def test_existing_workspace_is_preserved(monkeypatch):
    monkeypatch.setattr(bootstrap.Path, 'exists', lambda p: True)
    with pytest.raises(ValueError, match='workspace_not_empty'):
        bootstrap.prepare({'JOB_WORKSPACE_ID': 'ws'})
