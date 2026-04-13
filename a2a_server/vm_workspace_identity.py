import re
from typing import Dict, Optional


def _slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[^a-z0-9._-]+', '-', value.lower()).strip('-.')
    return cleaned or fallback


def build_vm_git_identity(
    user_id: Optional[str], tenant_id: Optional[str], workspace_id: str
) -> Dict[str, str]:
    if user_id:
        identity = f'user:{user_id}'
        slug = _slug(f'user-{user_id}', f'workspace-{workspace_id}')
    elif tenant_id:
        identity = f'tenant:{tenant_id}'
        slug = _slug(f'tenant-{tenant_id}', f'workspace-{workspace_id}')
    else:
        identity = f'workspace:{workspace_id}'
        slug = _slug(f'workspace-{workspace_id}', f'workspace-{workspace_id}')
    return {
        'agent_identity_id': identity,
        'git_user_name': f'CodeTether Agent [{slug}]',
        'git_user_email': f'agent+{slug}@codetether.run',
    }
