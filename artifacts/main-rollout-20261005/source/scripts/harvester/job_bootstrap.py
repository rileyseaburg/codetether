#!/usr/bin/env python3
"""Reconstruct an isolated coding workspace from Git, not an old pod disk."""

import json
import os
import re
import shutil
import subprocess

from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit


def prepare(env):
    """Clone into an empty destination, preserving any existing data."""
    root = Path('/var/lib/codetether/repos')
    workspace = env['JOB_WORKSPACE_ID']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', workspace):
        raise ValueError('workspace_identifier_invalid')
    path = root / workspace
    if path.exists():
        raise ValueError('workspace_not_empty')
    url = env['JOB_GIT_URL']
    parsed = urlsplit(url)
    if (
        parsed.scheme != 'https'
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError('git_url_invalid')
    branch = env['JOB_GIT_BRANCH']
    target = env['JOB_TARGET_BRANCH']
    sha = env.get('JOB_EXPECTED_HEAD', '')
    for ref in (branch, target):
        if not ref or ref.startswith('-') or any(c.isspace() for c in ref):
            raise ValueError('branch_invalid')
    if sha and not re.fullmatch(r'[0-9a-fA-F]{40}', sha):
        raise ValueError('head_invalid')
    server = env['CODETETHER_SERVER']
    if not re.fullmatch(r'https?://[A-Za-z0-9._:/-]+', server):
        raise ValueError('server_invalid')
    helper = (
        f'!codetether git-credential-helper --workspace-id {workspace} '
        f'--server {server}'
    )
    child = {**env, 'GIT_TERMINAL_PROMPT': '0'}
    # Measured: forgejo.quantum-forge.io serves a ~3.3 GiB repository at
    # roughly 100 MiB/min per concurrent clone, so a full clone needs ~35 min.
    # The 10-minute default only ever succeeded for a single clone at a time.
    clone_timeout = int(env.get('JOB_CLONE_TIMEOUT_SECONDS', '3000'))

    def git(*args: str, timeout: int = 600) -> str:
        result = subprocess.run(
            [
                'git',
                '-c',
                'credential.helper=' + helper,
                '-c',
                'credential.useHttpPath=true',
                *args,
            ],
            env=child,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            if b'No space left on device' in result.stderr:
                raise ValueError('workspace_storage_exhausted')
            if b'Authentication failed' in result.stderr:
                raise ValueError('workspace_git_auth_failed')
            raise ValueError('git_bootstrap_failed')
        return result.stdout.decode().strip()

    root.mkdir(parents=True, exist_ok=True)
    # Measured: a spotlessbinco clone is ~4.5 GiB; require ~2x headroom.
    if shutil.disk_usage(root).free < 10 * 1024**3:
        raise ValueError('workspace_storage_insufficient')
    git(
        'clone',
        '--no-tags',
        '--single-branch',
        '--branch',
        branch,
        '--',
        url,
        str(path),
        timeout=clone_timeout,
    )
    current = git('-C', str(path), 'rev-parse', 'HEAD')
    if sha and current != sha:
        # Do not silently build another head after a remote branch move.
        raise ValueError('remote_head_advanced')
    if branch != target:
        git('-C', str(path), 'checkout', '-b', target)
    git('-C', str(path), 'config', 'credential.helper', helper)
    git('-C', str(path), 'config', 'credential.useHttpPath', 'true')
    synced = sync_base(git, path, env.get('JOB_BASE_BRANCH', ''), branch)
    hooks = install_hooks(path, child)
    return {
        'diagnostic': 'workspace_bootstrapped',
        'head': current,
        'workspace': workspace,
        'base_sync': synced,
        'hooks': hooks,
    }


def sync_base(git, path, base, branch):
    """Bring the work branch up to date with the default branch before work.

    Fetch the base into a tracking ref, then merge it. A conflict aborts the
    merge and is left for the agent to resolve with full context; the branch
    is never rewritten, and the pre-push gate still refuses stale pushes.
    """
    if not base or base == branch:
        return 'not_applicable'
    if base.startswith('-') or any(c.isspace() for c in base):
        raise ValueError('branch_invalid')
    git(
        '-C',
        str(path),
        'fetch',
        '--no-tags',
        'origin',
        f'+refs/heads/{base}:refs/remotes/origin/{base}',
    )
    tip = f'refs/remotes/origin/{base}'
    behind = git('-C', str(path), 'rev-list', '--count', f'HEAD..{tip}')
    if behind == '0':
        return 'current'
    try:
        git(
            '-C',
            str(path),
            '-c',
            'user.name=CodeTether Agent',
            '-c',
            'user.email=agent@codetether.run',
            'merge',
            '--no-edit',
            '--no-verify',
            tip,
        )
    except ValueError:
        # Abort is a no-op failure when the merge never started; the tree is
        # then unchanged, and the agent still resolves the sync explicitly.
        with suppress(ValueError):
            git('-C', str(path), 'merge', '--abort')
        return 'conflict'
    return 'merged'


def install_hooks(path, child):
    """Install the repository's declared hooks, or refuse the workspace.

    Pushes are only allowed through the repository's own pre-commit,
    post-commit and pre-push hooks. A repository that declares hooks the
    image cannot install fails the bootstrap instead of silently skipping.
    """
    installed = []
    config = path / '.pre-commit-config.yaml'
    if config.exists():
        if shutil.which('pre-commit') is None:
            raise ValueError('workspace_hooks_unavailable')
        run_hook_tool(['pre-commit', 'install', '--install-hooks'], path, child)
        installed.append('pre-commit')
    installer = path / 'scripts/dev/install-pre-push-cache-gate.sh'
    if (path / '.githooks/pre-push').exists():
        if not installer.exists():
            raise ValueError('workspace_hooks_unavailable')
        run_hook_tool(['bash', str(installer)], path, child)
        installed.append('pre-push')
    return installed


def run_hook_tool(argv, path, child):
    """Run one hook installer in the repository, with a bounded timeout."""
    result = subprocess.run(
        argv,
        cwd=path,
        env=child,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=int(child.get('JOB_HOOK_INSTALL_TIMEOUT_SECONDS', '900')),
        check=False,
    )
    if result.returncode:
        raise ValueError('workspace_hooks_unavailable')


def main():
    """Bootstrap once and record a fixed diagnostic for the controller."""
    result = {'diagnostic': 'workspace_bootstrap_failed'}
    code = 1
    try:
        result = prepare(dict(os.environ))
        code = 0
    except ValueError as error:
        if str(error) in {
            'remote_head_advanced',
            'workspace_storage_insufficient',
            'workspace_storage_exhausted',
            'workspace_git_auth_failed',
            'workspace_hooks_unavailable',
            'workspace_not_empty',
        }:
            result['diagnostic'] = str(error)
    except subprocess.TimeoutExpired:
        result['diagnostic'] = 'workspace_bootstrap_timeout'
    except KeyError:
        pass
    Path('/tmp/job-result.json').write_text(json.dumps(result) + '\n')
    print(json.dumps(result))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
