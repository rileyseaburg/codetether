"""Read-only: check a harvester workspace's Git hook setup inside a live Job.

Reports hook paths and installed hooks for one running coding-Job pod. Nothing
is changed and no file contents beyond hook names are printed.
"""

import json
import subprocess
import sys


def sh(pod: str, command: str) -> str:
    """Run a fixed read-only shell command in the pod's worker container."""
    run = subprocess.run(
        [
            'kubectl',
            '-n',
            'a2a-system',
            'exec',
            pod,
            '-c',
            'worker',
            '--',
            'sh',
            '-c',
            command,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    return (run.stdout or run.stderr).strip()[:1500]


def main() -> None:
    """Inspect the first running coding Job, or the one named on argv."""
    pods = json.loads(
        subprocess.check_output(
            [
                'kubectl',
                '-n',
                'a2a-system',
                'get',
                'pods',
                '-l',
                'codetether.io/job-class=coding',
                '--field-selector=status.phase=Running',
                '-o',
                'json',
            ]
        )
    )['items']
    names = [p['metadata']['name'] for p in pods]
    pod = sys.argv[1] if len(sys.argv) > 1 else (names[0] if names else '')
    if not pod:
        raise SystemExit('no running coding Job pod')
    repo = sh(pod, 'ls -d /var/lib/codetether/repos/*/ 2>/dev/null | head -1')
    repo = repo.splitlines()[0].rstrip('/') if repo else ''
    checks = {
        'pod': pod,
        'repo': repo,
        'tools': sh(
            pod,
            'for t in git pre-commit pnpm node gitleaks rustyroad python3 '
            'pip3 pipx cargo rustc flock setsid tar sha256sum realpath gpg '
            'docker; do printf "%s=" $t; command -v $t || echo missing; done',
        ),
        'runtime': sh(
            pod,
            'rustc --version 2>&1; nproc; '
            'cat /sys/fs/cgroup/memory.max 2>/dev/null; '
            'echo HOME=$HOME XDG=$XDG_CACHE_HOME; id',
        ),
        'hooks_path_config': sh(
            pod,
            f'git -C {repo} config --show-origin --get core.hooksPath'
            ' || echo unset',
        ),
        'installed_hooks': sh(
            pod, f'ls {repo}/.git/hooks | grep -v sample || echo none'
        ),
        'repo_githooks': sh(pod, f'ls {repo}/.githooks 2>&1'),
        'upstream': sh(
            pod,
            f'git -C {repo} rev-parse --abbrev-ref HEAD; '
            f'git -C {repo} config --get-regexp "^remote\\.origin\\.fetch"',
        ),
    }
    print(json.dumps(checks, indent=1))


if __name__ == '__main__':
    main()
