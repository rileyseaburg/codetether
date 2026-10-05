"""Strip control-plane trust claims from caller-supplied task metadata.

Zero trust: a task's ``metadata`` is stored as-is and later read by trusted
automation. GitHub App and Forgejo completion hooks act on tasks whose
``metadata.source`` names them, using installation tokens and merge rights.

Public entry points (``POST /v1/agent/tasks`` is unauthenticated for the
marketing chat widget, and MCP ``create_task``/``send_message`` tools) accept
free-form metadata. Without sanitizing, any caller could create a task that
claims ``source: github-app`` with an attacker-chosen repo, PR, and stage,
and the completion hook would run privileged GitHub actions for it.

Only server-side producers (webhook handlers, workflow code) may set these
keys; they call the task factories directly, never through these endpoints.
"""

from __future__ import annotations

import logging

from collections.abc import Mapping
from typing import Any


logger = logging.getLogger(__name__)

#: Values of ``metadata.source`` that grant trusted-automation handling.
TRUSTED_SOURCES = frozenset(
    {
        'github-app',
        'forgejo-webhook',
        'forgejo-review-owner',
        'forgejo-pr-review',
        'forgejo-agent',
        'github-webhook',
    }
)

#: Keys only trusted producers may set; they drive privileged follow-ups.
RESERVED_KEYS = frozenset(
    {
        'codetether_provenance',
        'policy_decision',
        'github_installation_id',
        'github_work_key',
        'forgejo_work_key',
        'workflow_stage',
        'post_clone_task',
        'post_review_task',
        'review_task_id',
        'fix_followup',
        'fix_attempt',
    }
)


def sanitize_external_metadata(
    metadata: Mapping[str, Any] | None, *, entry_point: str
) -> dict[str, Any]:
    """Return a copy of ``metadata`` without trust-bearing claims.

    Drops reserved keys and any ``source`` that names trusted automation.
    Logs what was removed so forgery attempts are auditable.
    """
    cleaned = dict(metadata or {})
    removed = sorted(key for key in RESERVED_KEYS if key in cleaned)
    for key in removed:
        cleaned.pop(key)
    if str(cleaned.get('source') or '') in TRUSTED_SOURCES:
        removed.append(f'source={cleaned.pop("source")}')
    if removed:
        logger.warning(
            'Stripped reserved task metadata at %s: %s',
            entry_point,
            removed,
        )
    return cleaned


def untrusted_mcp_metadata(
    args: Mapping[str, Any], base_metadata: Mapping[str, Any]
) -> dict[str, Any]:
    """Sanitize an MCP tool call's ``metadata`` argument.

    The entry point is named after the tool's own ``base_metadata['source']``
    (for example ``mcp:create_task``) so audit logs identify the tool.
    """
    return sanitize_external_metadata(
        args.get('metadata'),
        entry_point=f'mcp:{base_metadata.get("source", "unknown")}',
    )
