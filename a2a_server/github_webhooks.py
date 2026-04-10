"""GitHub App webhook ingress for @codetether comment handling."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .github_app_auth import github_installation_request, verify_github_webhook_signature
from .github_comment_tasks import bot_login, has_bot_mention, queue_github_comment_task

router = APIRouter(prefix='/v1/webhooks', tags=['github'])


async def _post_ack(payload: dict, task_id: str, branch: str) -> None:
    repo = payload['repository']
    installation_id = str(payload['installation']['id'])
    if 'issue' not in payload:
        issue_number = payload['pull_request']['number']
    else:
        issue_number = payload['issue']['number']
    body = (
        f"@{payload['sender']['login']} CodeTether accepted this request.\n\n"
        f"- task: `{task_id}`\n- branch: `{branch}`\n- agent: `@{bot_login()}`\n\n"
        "I queued repository preparation and the follow-up implementation task."
    )
    await github_installation_request(
        installation_id=installation_id,
        owner=repo['owner']['login'],
        repo=repo['name'],
        method='POST',
        url=f"https://api.github.com/repos/{repo['full_name']}/issues/{issue_number}/comments",
        json_body={'body': body},
    )


@router.post('/github')
async def github_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_github_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail='Invalid GitHub webhook signature')
    event_name = request.headers.get('X-GitHub-Event', '')
    data = await request.json()
    if event_name == 'ping':
        return {'ok': True, 'event': 'ping'}
    if event_name not in {'issue_comment', 'pull_request_review_comment'}:
        return {'ok': True, 'ignored': event_name}
    if not has_bot_mention((data.get('comment') or {}).get('body') or ''):
        return {'ok': True, 'ignored': 'no-mention'}
    queued = await queue_github_comment_task(event_name, data)
    try:
        await _post_ack(data, queued['task_id'], queued['branch'])
    except Exception:
        pass
    return {'ok': True, **queued}
