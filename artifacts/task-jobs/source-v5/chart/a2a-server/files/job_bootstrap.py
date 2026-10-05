#!/usr/bin/env python3
"""Reconstruct an isolated coding workspace from Git, never from an old pod disk."""

import json
import os
import re
import shutil
import subprocess

from pathlib import Path
from urllib.parse import urlsplit


def prepare(env):
    """Clone an authenticated remote into an empty destination; preserve existing data."""
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
    helper = f'!codetether git-credential-helper --workspace-id {workspace} --server {server}'
    child = {**env, 'GIT_TERMINAL_PROMPT': '0'}

    def git(*args):
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
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
    )
    current = git('-C', str(path), 'rev-parse', 'HEAD')
    if sha and current != sha:
        # Do not silently build another head after a remote branch move.
        raise ValueError('remote_head_advanced')
    if branch != target:
        git('-C', str(path), 'checkout', '-b', target)
    git('-C', str(path), 'config', 'credential.helper', helper)
    git('-C', str(path), 'config', 'credential.useHttpPath', 'true')
    return {
        'diagnostic': 'workspace_bootstrapped',
        'head': current,
        'workspace': workspace,
    }


def main():
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
