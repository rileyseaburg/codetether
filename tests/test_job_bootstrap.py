"""Bootstrap boundary tests; mocked local, no repositories cloned."""

import importlib.util

from pathlib import Path
from types import SimpleNamespace

import pytest


SPEC = importlib.util.spec_from_file_location(
    'job_bootstrap', Path('scripts/harvester/job_bootstrap.py')
)
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)
CLONE_TIMEOUT = 2400
GIT_TIMEOUT = 600


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
    assert timeouts['clone'] == CLONE_TIMEOUT
    assert all(
        t == GIT_TIMEOUT for cmd, t in timeouts.items() if cmd != 'clone'
    )


class FakeGit:
    """Record git calls; fail the listed subcommands."""

    def __init__(self, behind='3', fail=()):
        self.calls, self.behind, self.fail = [], behind, set(fail)

    @staticmethod
    def _sub(args):
        # Skip `-C path` and `-c key=value` pairs, then any other flags.
        rest = list(args)
        while rest and rest[0] in ('-C', '-c'):
            rest = rest[2:]
        return next(a for a in rest if not a.startswith('-'))

    def __call__(self, *args, timeout=600):
        self.calls.append(args)
        sub = self._sub(args)
        if sub in self.fail:
            raise ValueError('git_bootstrap_failed')
        return self.behind if sub == 'rev-list' else ''

    def subcommands(self):
        return [self._sub(c) for c in self.calls]


def test_work_branch_merges_the_current_default_branch(tmp_path):
    git = FakeGit(behind='4')
    assert bootstrap.sync_base(git, tmp_path, 'main', 'feature') == 'merged'
    assert git.subcommands() == ['fetch', 'rev-list', 'merge']
    fetch = git.calls[0]
    assert '+refs/heads/main:refs/remotes/origin/main' in fetch
    merge = git.calls[-1]
    # The bootstrap merge is not agent work; hooks are installed afterwards.
    assert merge[-1] == 'refs/remotes/origin/main'


def test_current_branch_is_not_merged(tmp_path):
    git = FakeGit(behind='0')
    assert bootstrap.sync_base(git, tmp_path, 'main', 'feature') == 'current'
    assert 'merge' not in git.subcommands()


def test_merge_conflict_is_aborted_and_left_for_the_agent(tmp_path):
    git = FakeGit(fail={'merge'})
    assert bootstrap.sync_base(git, tmp_path, 'main', 'feature') == 'conflict'
    assert git.calls[-1][-2:] == ('merge', '--abort')


@pytest.mark.parametrize('base', ['', 'main'])
def test_default_branch_work_needs_no_sync(tmp_path, base):
    git = FakeGit()
    assert bootstrap.sync_base(git, tmp_path, base, 'main') == 'not_applicable'
    assert git.calls == []


def test_invalid_base_branch_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='branch_invalid'):
        bootstrap.sync_base(FakeGit(), tmp_path, '--upload-pack=x', 'feature')


def _hook_repo(tmp_path, *, precommit=True, prepush=True):
    if precommit:
        (tmp_path / '.pre-commit-config.yaml').write_text('repos: []\n')
    if prepush:
        (tmp_path / '.githooks').mkdir()
        (tmp_path / '.githooks/pre-push').write_text('#!/bin/sh\n')
        installer = tmp_path / 'scripts/dev/install-pre-push-cache-gate.sh'
        installer.parent.mkdir(parents=True)
        installer.write_text('#!/bin/sh\n')
    return tmp_path


def test_declared_hooks_are_installed(tmp_path, monkeypatch):
    repo = _hook_repo(tmp_path)
    ran = []
    monkeypatch.setattr(bootstrap.shutil, 'which', lambda name: '/bin/' + name)
    monkeypatch.setattr(
        bootstrap.subprocess,
        'run',
        lambda argv, **kw: ran.append(argv) or SimpleNamespace(returncode=0),
    )
    assert bootstrap.install_hooks(repo, {}) == ['pre-push', 'pre-commit']
    assert ran[0][-1].endswith('install-pre-push-cache-gate.sh')
    assert ran[1] == [
        'pre-commit',
        'install',
        '--install-hooks',
        '--hook-type',
        'pre-commit',
    ]


def test_stale_generated_post_commit_is_replaced(tmp_path, monkeypatch):
    repo = _hook_repo(tmp_path)
    (repo / '.pre-commit-config.yaml').write_text(
        'default_install_hook_types: [pre-commit, post-commit]\n'
    )
    (repo / '.githooks/post-commit').write_text('#!/bin/sh\nrepo hook\n')
    hooks = repo / '.git/hooks'
    hooks.mkdir(parents=True)
    stale = hooks / 'post-commit'
    stale.write_text('# File generated by pre-commit: https://pre-commit.com\n')
    custom = hooks / 'pre-push'
    custom.write_text('#!/bin/sh\ncustom\n')
    ran = []
    monkeypatch.setattr(bootstrap.shutil, 'which', lambda name: '/bin/' + name)
    monkeypatch.setattr(
        bootstrap.subprocess,
        'run',
        lambda argv, **kw: ran.append(argv) or SimpleNamespace(returncode=0),
    )
    bootstrap.install_hooks(repo, {})
    assert not stale.exists()
    assert custom.exists()
    # .githooks owns post-commit, so pre-commit must not install it.
    assert 'post-commit' not in ran[1]


def test_missing_hook_tooling_refuses_the_workspace(tmp_path, monkeypatch):
    repo = _hook_repo(tmp_path, prepush=False)
    monkeypatch.setattr(bootstrap.shutil, 'which', lambda name: None)
    with pytest.raises(ValueError, match='workspace_hooks_unavailable'):
        bootstrap.install_hooks(repo, {})


def test_failed_hook_install_refuses_the_workspace(tmp_path, monkeypatch):
    repo = _hook_repo(tmp_path)
    monkeypatch.setattr(bootstrap.shutil, 'which', lambda name: '/bin/' + name)
    monkeypatch.setattr(
        bootstrap.subprocess,
        'run',
        lambda argv, **kw: SimpleNamespace(returncode=1),
    )
    with pytest.raises(ValueError, match='workspace_hooks_unavailable'):
        bootstrap.install_hooks(repo, {})


def test_declared_pre_push_without_installer_is_refused(tmp_path, monkeypatch):
    repo = _hook_repo(tmp_path, precommit=False)
    (repo / 'scripts/dev/install-pre-push-cache-gate.sh').unlink()
    with pytest.raises(ValueError, match='workspace_hooks_unavailable'):
        bootstrap.install_hooks(repo, {})


def test_repository_without_hooks_installs_nothing(tmp_path):
    assert bootstrap.install_hooks(tmp_path, {}) == []
