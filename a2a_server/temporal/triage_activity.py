"""Temporal activities that let the coding agent triage before review.

`triage_prompt` prefixes the code-stage prompt with the open pull requests and
issues most similar to the task's issue. `apply_triage` reads the verdict line
from the finished code task; a duplicate or not-needed verdict closes the
issue with the agent's reason and the workflow skips review.
"""

from __future__ import annotations

import logging
import os

from urllib.parse import quote

from temporalio import activity

from a2a_server.forgejo_triage import (
    parse_triage,
    similar_open_work,
    triage_instructions,
)


logger = logging.getLogger(__name__)


def _repo_path(repository: str) -> str:
    owner, name = repository.split('/', 1)
    return f'/repos/{quote(owner, safe="")}/{quote(name, safe="")}'


async def triage_prompt(repository: str, issue_number: int, prompt: str) -> str:
    """Return `prompt` prefixed with similar open work; unchanged on failure."""
    from a2a_server.forgejo_webhooks import forgejo_json  # noqa: PLC0415

    if not issue_number:
        return prompt
    base = os.environ.get('FORGEJO_API_URL', '').rstrip('/')
    path = _repo_path(repository)
    try:
        issue = await forgejo_json('GET', base, f'{path}/issues/{issue_number}')
        candidates = await similar_open_work(
            forgejo_json,
            base,
            path,
            issue_number,
            str((issue or {}).get('title') or ''),
        )
    except Exception:
        logger.warning('Triage context unavailable issue=%s', issue_number)
        return prompt
    return triage_instructions(issue_number, candidates) + prompt


@activity.defn(name='forgejo_apply_triage')
async def apply_triage(payload: dict) -> str:
    """Act on the code task's verdict and return it (`proceed` by default).

    Fails open: any error keeps the existing review path, and no exception
    text reaches Temporal history.
    """
    try:
        return await _apply_triage(payload)
    except Exception:
        logger.warning('Triage not applied task=%s', payload.get('task_id'))
        return 'proceed'


async def _apply_triage(payload: dict) -> str:
    from a2a_server import database as db  # noqa: PLC0415
    from a2a_server.forgejo_webhooks import (  # noqa: PLC0415
        _comment,
        forgejo_json,
    )

    task = await db.db_get_task(str(payload['task_id'])) or {}
    verdict, number, reason = parse_triage(str(task.get('result') or ''))
    issue = int(payload.get('issue_number') or 0)
    if verdict == 'proceed' or not issue:
        return 'proceed'
    repository = str(payload['repository'])
    base = os.environ.get('FORGEJO_API_URL', '').rstrip('/')
    path = _repo_path(repository)
    if verdict == 'duplicate':
        target = await forgejo_json(
            'GET', base, f'{path}/issues/{number}', allow_not_found=True
        )
        if not target or target.get('state') != 'open' or number == issue:
            return 'proceed'
        body = (
            '## CodeTether triage\n\nClosing as a duplicate of '
            f'#{number}, which already covers this defect. No code was changed.'
        )
    else:
        body = (
            '## CodeTether triage\n\nClosing: no change is needed. '
            f'{reason or "The evidence describes expected behaviour."} '
            'No code was changed. Reopen if this is a real defect.'
        )
    marker = f'<!-- codetether-triage:{payload["task_id"]} -->'
    await _comment(base, repository, issue, f'{body}\n\n{marker}')
    await forgejo_json(
        'PATCH', base, f'{path}/issues/{issue}', {'state': 'closed'}
    )
    return verdict
