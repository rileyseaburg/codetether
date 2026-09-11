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


def test_clone_gets_long_timeout_but_local_git_does_not(monkeypatch):
    """A multi-GiB clone over a shared link needs far more than 10 minutes."""
    from types import SimpleNamespace

    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs['timeout']))
        return SimpleNamespace(
            returncode=0, stdout=b'a' * 40 + b'\n', stderr=b''
        )

    monkeypatch.setattr(bootstrap.Path, 'exists', lambda p: False)
    monkeypatch.setattr(bootstrap.Path, 'mkdir', lambda *a, **k: None)
    monkeypatch.setattr(
        bootstrap.shutil,
        'disk_usage',
        lambda p: SimpleNamespace(free=64 * 1024**3),
    )
    monkeypatch.setattr(bootstrap.subprocess, 'run', run)
    bootstrap.prepare(
        {
            'JOB_WORKSPACE_ID': 'ws',
            'JOB_GIT_URL': 'https://forge.example/o/r.git',
            'JOB_GIT_BRANCH': 'main',
            'JOB_TARGET_BRANCH': 'main',
            'CODETETHER_SERVER': 'https://api.example',
            'JOB_CLONE_TIMEOUT_SECONDS': '2400',
        }
    )

    def subcommand(args):
        # git -c k=v -c k=v [-C path] <subcommand> ...
        rest = list(args[1:])
        while rest and rest[0] in ('-c', '-C'):
            rest = rest[2:]
        return rest[0]

    timeouts = {subcommand(args): t for args, t in calls}
    assert timeouts['clone'] == 2400
    assert all(t == 600 for cmd, t in timeouts.items() if cmd != 'clone')
