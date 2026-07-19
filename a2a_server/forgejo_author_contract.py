"""Fail-closed metadata contract for Forgejo author tasks."""

import re

from collections.abc import Mapping

from a2a_server.forgejo_author_identity import canonical_identity
from a2a_server.forgejo_conversation_identity import validate_binding


PROTOCOL = 'codetether.forgejo-author.v1'
_HEAD = re.compile(r'^[0-9a-f]{40}$')
_SESSION = re.compile(r'^[A-Za-z0-9_-]{1,128}$')
_PROVENANCE = re.compile(r'^ctprov_[A-Za-z0-9_-]{16,80}$')


def validate(metadata: Mapping[str, object]) -> str:
    """Validate and return the canonical target identity."""
    if metadata.get('protocol') != PROTOCOL:
        raise ValueError('unsupported author-conversation protocol')
    if metadata.get('source') != 'forgejo-pr-review':
        raise ValueError('invalid author-conversation source')
    if metadata.get('workflow_stage') != 'forgejo-author-review':
        raise ValueError('invalid author-conversation stage')
    host = str(metadata.get('forgejo_host') or '').lower()
    login = str(metadata.get('forgejo_author_login') or '').lower()
    slot = str(metadata.get('agent_slot') or '').lower()
    target = canonical_identity(host, login, slot)
    if metadata.get('target_agent_name') != target:
        raise ValueError('target does not match the signed Forgejo principal')
    if not _HEAD.fullmatch(str(metadata.get('pr_head_sha') or '').lower()):
        raise ValueError('invalid immutable head SHA')
    if not _SESSION.fullmatch(str(metadata.get('resume_session_id') or '')):
        raise ValueError('invalid reusable session identity')
    if not _PROVENANCE.fullmatch(
        str(metadata.get('author_provenance_id') or '')
    ):
        raise ValueError('invalid signed provenance identity')
    if metadata.get('provenance_verified') is not True:
        raise ValueError('verified provenance is required')
    if metadata.get('preserve_session_workspace') is not True:
        raise ValueError('verified workspace preservation is required')
    validate_binding(metadata, target)
    return target
