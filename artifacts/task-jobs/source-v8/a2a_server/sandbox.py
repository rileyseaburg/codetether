"""
Sandbox Execution for A2A Workers.

Provides container-based isolation for task execution. When SANDBOX_ENABLED=true,
agent tasks run inside ephemeral Docker containers with constrained resources.

Security Controls:
- Read-only root filesystem (work dir is tmpfs)
- No network access by default (opt-in per task)
- Resource limits (CPU, memory, disk)
- No privileged operations
- Dropped Linux capabilities
- PID namespace isolation
"""

import asyncio
import json
import logging
import os
import shutil
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Configuration
SANDBOX_ENABLED = os.environ.get('SANDBOX_ENABLED', 'false').lower() == 'true'
SANDBOX_IMAGE = os.environ.get(
    'SANDBOX_IMAGE', 'ghcr.io/rileyseaburg/codetether-worker:latest'
)
SANDBOX_MEMORY_LIMIT = os.environ.get('SANDBOX_MEMORY_LIMIT', '2g')
SANDBOX_CPU_LIMIT = os.environ.get('SANDBOX_CPU_LIMIT', '2.0')
SANDBOX_TIMEOUT = int(os.environ.get('SANDBOX_TIMEOUT', '600'))  # 10 min
SANDBOX_NETWORK = os.environ.get('SANDBOX_NETWORK', 'none')  # 'none' or 'bridge'


def is_sandbox_available() -> bool:
    """Check if Docker is available for sandboxed execution."""
    if not SANDBOX_ENABLED:
        return False
    return shutil.which('docker') is not None


async def execute_sandboxed(
    cmd: list[str],
    cwd: str,
    env: Dict[str, str],
    task_id: str,
    timeout: int = SANDBOX_TIMEOUT,
    allow_network: bool = False,
) -> Tuple[int, str, str]:
    """Execute a command inside a sandboxed Docker container.

    Args:
        cmd: Command and arguments to execute.
        cwd: Working directory (mounted read-write into container).
        env: Environment variables to pass.
        task_id: Task ID for container naming.
        timeout: Max execution time in seconds.
        allow_network: Whether to allow network access.

    Returns:
        Tuple of (return_code, stdout, stderr).
    """
    container_name = f'ct-task-{task_id[:12]}'
    network = 'bridge' if allow_network else 'none'

    docker_cmd = [
        'docker', 'run',
        '--rm',
        '--name', container_name,
        # Resource limits
        '--memory', SANDBOX_MEMORY_LIMIT,
        '--cpus', SANDBOX_CPU_LIMIT,
        '--pids-limit', '256',
        # Security: drop all caps, read-only root, no privilege escalation
        '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges',
        '--read-only',
        # Writable tmpfs for /tmp and agent workspace
        '--tmpfs', '/tmp:rw,noexec,nosuid,size=512m',
        # Network isolation
        '--network', network,
        # Mount working directory
        '-v', f'{cwd}:/workspace:rw',
        '-w', '/workspace',
    ]

    # Pass environment variables (filter sensitive ones)
    safe_env_prefixes = (
        'ANTHROPIC_', 'OPENAI_', 'GOOGLE_', 'CODETETHER_',
        'NO_COLOR', 'HOME', 'PATH', 'LANG',
    )
    for key, value in env.items():
        if any(key.startswith(p) for p in safe_env_prefixes):
            docker_cmd.extend(['-e', f'{key}={value}'])

    # Image and command
    docker_cmd.append(SANDBOX_IMAGE)
    docker_cmd.extend(cmd)

    logger.info(
        f'Sandboxed execution for task {task_id}: '
        f'image={SANDBOX_IMAGE}, network={network}, mem={SANDBOX_MEMORY_LIMIT}'
    )

    try:
        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )

        return (
            process.returncode or 0,
            stdout_bytes.decode('utf-8', errors='replace'),
            stderr_bytes.decode('utf-8', errors='replace'),
        )

    except asyncio.TimeoutError:
        # Kill the container on timeout
        logger.warning(f'Sandbox timeout for task {task_id}, killing container')
        kill_proc = await asyncio.create_subprocess_exec(
            'docker', 'kill', container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await kill_proc.wait()
        return (124, '', f'Task execution timed out after {timeout}s')

    except Exception as e:
        logger.error(f'Sandbox execution error for task {task_id}: {e}')
        return (1, '', str(e))
