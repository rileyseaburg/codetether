"""
Git Repository Service for A2A Server.

Allows tenants to register Git repositories (GitHub, GitLab, etc.)
and auto-clone them on workers. Credentials are stored in Vault.
"""

import asyncio
import logging
import os
import re
import shutil
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .github_app_auth import mint_github_app_installation_token

logger = logging.getLogger(__name__)

# Base directory where repos are cloned on workers
GIT_CLONE_BASE = os.environ.get('GIT_CLONE_BASE', '/var/lib/codetether/repos')

# Maximum repo size (in bytes) — default 2GB
MAX_REPO_SIZE = int(os.environ.get('GIT_MAX_REPO_SIZE', str(2 * 1024 * 1024 * 1024)))

# Allowed Git URL patterns (HTTPS only — no arbitrary protocols)
_ALLOWED_URL_PATTERN = re.compile(
    r'^https://(github\.com|gitlab\.com|bitbucket\.org|dev\.azure\.com)/[^\s]+\.git$'
)


def validate_git_url(url: str) -> bool:
    """Validate that a Git URL is an allowed HTTPS repo URL."""
    return bool(_ALLOWED_URL_PATTERN.match(url))


async def store_git_credentials(
    codebase_id: str,
    token: str,
    token_type: str = 'pat',
) -> bool:
    """Store Git credentials in Vault.

    Args:
        codebase_id: The codebase ID to associate credentials with.
        token: The access token (PAT, deploy key, etc.)
        token_type: Type of token ('pat', 'deploy_key', 'oauth')

    Returns:
        True if stored successfully.
    """
    try:
        from .vault_client import get_vault_client
        client = get_vault_client()
        await client.write_secret(
            f'codetether/git/{codebase_id}',
            {'token': token, 'token_type': token_type},
        )
        logger.info(f'Stored Git credentials for codebase {codebase_id}')
        return True
    except Exception as e:
        logger.error(f'Failed to store Git credentials: {e}')
        return False


async def store_git_credential_record(
    codebase_id: str, record: Dict[str, Any]
) -> bool:
    """Store arbitrary git credential metadata in Vault."""
    try:
        from .vault_client import get_vault_client
        client = get_vault_client()
        await client.write_secret(f'codetether/git/{codebase_id}', record)
        logger.info(f'Stored Git credential record for codebase {codebase_id}')
        return True
    except Exception as e:
        logger.error(f'Failed to store Git credential record: {e}')
        return False


async def get_git_credentials(codebase_id: str) -> Optional[Dict[str, str]]:
    """Retrieve Git credentials from Vault."""
    try:
        from .vault_client import get_vault_client
        client = get_vault_client()
        secret = await client.read_secret(f'codetether/git/{codebase_id}')
        return secret
    except Exception as e:
        logger.debug(f'No Git credentials found for {codebase_id}: {e}')
        return None


async def delete_git_credentials(codebase_id: str) -> bool:
    """Remove Git credentials from Vault."""
    try:
        from .vault_client import get_vault_client
        client = get_vault_client()
        await client.delete_secret(f'codetether/git/{codebase_id}')
        logger.info(f'Deleted Git credentials for codebase {codebase_id}')
        return True
    except Exception as e:
        logger.warning(f'Failed to delete Git credentials: {e}')
        return False


async def clone_repo(
    git_url: str,
    codebase_id: str,
    branch: str = 'main',
    depth: int = 1,
) -> str:
    """Clone a Git repository to the worker's local filesystem.

    Args:
        git_url: HTTPS Git URL to clone.
        codebase_id: Codebase ID (used for directory naming and credential lookup).
        branch: Branch to clone.
        depth: Clone depth (1 = shallow clone, 0 = full).

    Returns:
        Path to the cloned repository.

    Raises:
        ValueError: If URL is invalid or clone fails.
    """
    if not validate_git_url(git_url):
        raise ValueError(
            f'Invalid Git URL: {git_url}. '
            'Only HTTPS URLs from GitHub, GitLab, Bitbucket, and Azure DevOps are allowed.'
        )

    clone_dir = os.path.join(GIT_CLONE_BASE, codebase_id)

    # If already cloned, pull instead
    if os.path.isdir(os.path.join(clone_dir, '.git')):
        return await pull_repo(clone_dir, branch)

    os.makedirs(GIT_CLONE_BASE, exist_ok=True)

    # Build authenticated URL if credentials exist
    auth_url = await _build_auth_url(git_url, codebase_id)

    cmd = ['git', 'clone', '--single-branch', '--branch', branch]
    if depth > 0:
        cmd.extend(['--depth', str(depth)])
    cmd.extend([auth_url, clone_dir])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

    if proc.returncode != 0:
        # Clean up partial clone
        if os.path.exists(clone_dir):
            shutil.rmtree(clone_dir, ignore_errors=True)
        err_msg = stderr.decode(errors='replace')
        # Sanitize error message to avoid leaking credentials
        err_msg = _sanitize_output(err_msg)
        raise ValueError(f'Git clone failed: {err_msg}')

    logger.info(f'Cloned {git_url} → {clone_dir} (branch={branch}, depth={depth})')
    return clone_dir


async def pull_repo(clone_dir: str, branch: str = 'main') -> str:
    """Pull latest changes in an already-cloned repo."""
    proc = await asyncio.create_subprocess_exec(
        'git', '-C', clone_dir, 'pull', 'origin', branch,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

    if proc.returncode != 0:
        err_msg = _sanitize_output(stderr.decode(errors='replace'))
        logger.warning(f'Git pull failed in {clone_dir}: {err_msg}')
        # Fall through — stale repo is better than no repo

    logger.info(f'Pulled latest for {clone_dir} (branch={branch})')
    return clone_dir


def default_clone_dir(codebase_id: str) -> str:
    """Return the default clone location for a workspace."""
    base = os.environ.get('KNATIVE_WORKSPACE_BASE_PATH') or GIT_CLONE_BASE
    return os.path.join(base, codebase_id)


async def issue_git_credentials(
    codebase_id: str,
    requested_host: Optional[str] = None,
    requested_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve workspace git credentials for helper/API use."""
    creds = await get_git_credentials(codebase_id)
    if not creds:
        creds = await _workspace_github_app_credentials(codebase_id)
    if not creds:
        return None

    git_url = creds.get('git_url') or ''
    parsed = urlparse(git_url)
    stored_host = (parsed.hostname or '').strip()
    stored_path = parsed.path.lstrip('/')
    if requested_host and stored_host and requested_host != stored_host:
        raise ValueError('Requested Git host does not match stored remote')
    if requested_path and stored_path and requested_path != stored_path:
        raise ValueError('Requested Git path does not match stored remote')

    token_type = creds.get('token_type', 'pat')
    if token_type == 'github_app':
        if creds.get('token'):
            return {
                'username': 'x-access-token',
                'password': creds['token'],
                'expires_at': creds.get('expires_at'),
                'token_type': 'github_app',
                'host': requested_host or stored_host,
                'path': requested_path or stored_path,
            }
        token = await mint_github_app_installation_token(
            installation_id=str(creds.get('github_installation_id') or ''),
            owner=creds.get('github_owner'),
            repo=creds.get('github_repo'),
        )
        return {
            'username': 'x-access-token',
            'password': token['token'],
            'expires_at': token.get('expires_at'),
            'token_type': 'github_app',
            'host': requested_host or stored_host,
            'path': requested_path or stored_path,
        }

    return {
        'username': 'x-access-token',
        'password': creds.get('token', ''),
        'token_type': token_type,
        'host': requested_host or stored_host,
        'path': requested_path or stored_path,
    }


async def _workspace_github_app_credentials(
    workspace_id: str,
) -> Optional[Dict[str, Any]]:
    """Mint GitHub App credentials from workspace metadata when Vault has none."""
    try:
        from . import database as db

        workspace = await db.db_get_workspace(workspace_id)
    except Exception as exc:
        logger.debug(
            'No workspace-backed GitHub App credentials for %s: %s',
            workspace_id,
            exc,
        )
        return None

    if not workspace:
        return None

    github_app = _workspace_github_app_config(workspace)
    installation_id = str(github_app.get('installation_id') or '').strip()
    if not installation_id:
        return None

    from .github_app.auth import installation_token

    token, expires_at = await installation_token(int(installation_id))
    git_url = str(workspace.get('git_url') or '')
    owner, repo = _github_owner_repo_from_url(git_url)
    return {
        'git_url': git_url,
        'github_owner': owner,
        'github_repo': repo,
        'token': token,
        'token_type': 'github_app',
        'expires_at': expires_at,
    }


def _workspace_github_app_config(workspace: Dict[str, Any]) -> Dict[str, Any]:
    agent_config = workspace.get('agent_config') or {}
    return (
        ((agent_config.get('git_auth') or {}).get('github_app'))
        or ((workspace.get('git_auth') or {}).get('github_app'))
        or {}
    )


def _github_owner_repo_from_url(git_url: str) -> tuple[Optional[str], Optional[str]]:
    parsed = urlparse(git_url)
    parts = parsed.path.strip('/').removesuffix('.git').split('/')
    if len(parts) >= 2 and parsed.hostname == 'github.com':
        return parts[0], parts[1]
    return None, None


async def _build_auth_url(git_url: str, codebase_id: str) -> str:
    """Inject credentials into HTTPS Git URL."""
    creds = await issue_git_credentials(codebase_id)
    if not creds:
        return git_url

    token = creds.get('password', '')
    token_type = creds.get('token_type', 'pat')
    if token_type in ('pat', 'oauth', 'github_app'):
        return git_url.replace('https://', f'https://x-access-token:{token}@', 1)

    return git_url


def _sanitize_output(text: str) -> str:
    """Remove credentials from Git command output."""
    return re.sub(r'https://[^@]+@', 'https://***@', text)
