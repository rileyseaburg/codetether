from typing import Optional


def resolve_workspace_target(
    workspace_id: Optional[str],
    codebase_id: Optional[str],
) -> Optional[str]:
    candidate = (workspace_id or codebase_id or 'global').strip()
    if not candidate or candidate == 'global':
        return None
    return candidate
