import pytest

from a2a_server import git_service
from a2a_server.github_app import pr_final_comment, task_completion


@pytest.mark.asyncio
async def test_pr_prepare_task_creates_pr_followup(monkeypatch):
    calls = []

    async def fake_handle(task, worker_id=None):
        calls.append((task, worker_id))

    monkeypatch.setattr(task_completion, 'handle_pr_prepare_completion', fake_handle)

    task = {
        'title': 'Prepare PR workspace #40',
        'metadata': {'source': 'github-app', 'pr_number': 40},
    }
    await task_completion.notify_issue_task_completion(task, 'wrk_123')

    assert calls == [(task, 'wrk_123')]


@pytest.mark.asyncio
async def test_pr_build_task_posts_pr_final_comment(monkeypatch):
    calls = []

    async def fake_notify(task):
        calls.append(task)

    monkeypatch.setattr(task_completion, 'notify_pr_final_comment', fake_notify)

    task = {
        'title': 'Apply PR fix #40',
        'metadata': {'source': 'github-app', 'pr_number': 40},
    }
    await task_completion.notify_issue_task_completion(task)

    assert calls == [task]


@pytest.mark.asyncio
async def test_issue_prepare_task_still_uses_issue_followup(monkeypatch):
    calls = []

    async def fake_handle(task, worker_id=None):
        calls.append((task, worker_id))

    monkeypatch.setattr(task_completion, 'handle_issue_prepare_completion', fake_handle)

    task = {
        'title': 'Prepare issue workspace #39',
        'metadata': {'source': 'github-app', 'issue_number': 39},
    }
    await task_completion.notify_issue_task_completion(task, 'wrk_456')

    assert calls == [(task, 'wrk_456')]


@pytest.mark.asyncio
async def test_git_credentials_fall_back_to_workspace_github_app(monkeypatch):
    async def fake_get_git_credentials(workspace_id):
        assert workspace_id == 'ws_private'
        return None

    async def fake_db_get_workspace(workspace_id):
        assert workspace_id == 'ws_private'
        return {
            'git_url': 'https://github.com/rileyseaburg/spotlessbinco.git',
            'agent_config': {},
            'git_auth': {
                'github_app': {
                    'installation_id': '12345',
                }
            },
        }

    async def fake_installation_token(installation_id):
        assert installation_id == 12345
        return 'ghs_test_token', '2026-04-24T22:00:00Z'

    from a2a_server import database as db
    from a2a_server.github_app import auth

    monkeypatch.setattr(git_service, 'get_git_credentials', fake_get_git_credentials)
    monkeypatch.setattr(db, 'db_get_workspace', fake_db_get_workspace)
    monkeypatch.setattr(auth, 'installation_token', fake_installation_token)

    credentials = await git_service.issue_git_credentials(
        'ws_private',
        requested_host='github.com',
        requested_path='rileyseaburg/spotlessbinco.git',
    )

    assert credentials == {
        'username': 'x-access-token',
        'password': 'ghs_test_token',
        'expires_at': '2026-04-24T22:00:00Z',
        'token_type': 'github_app',
        'host': 'github.com',
        'path': 'rileyseaburg/spotlessbinco.git',
    }


@pytest.mark.asyncio
async def test_pr_final_comment_queues_review_after_pr_fix(monkeypatch):
    comments = []
    created = []
    pr = {
        'number': 40,
        'html_url': 'https://github.com/acme/widgets/pull/40',
        'head': {'sha': 'abc123', 'ref': 'feature'},
        'base': {'sha': 'def456', 'ref': 'main'},
    }

    async def fake_context(task):
        return 'acme/widgets', 40, 'feature', 'token'

    async def fake_github_json(method, path, token):
        assert method == 'GET'
        assert path == '/repos/acme/widgets/pulls/40'
        return pr

    async def fake_create_review_task(**kwargs):
        created.append(kwargs)
        return 'task-review-40'

    async def fake_post(repo, issue_number, token, body):
        comments.append(body)

    monkeypatch.setattr(pr_final_comment, 'github_app_task_context', fake_context)
    monkeypatch.setattr('a2a_server.github_app.auth.github_json', fake_github_json)
    monkeypatch.setattr('a2a_server.github_app.issue_review_task.create_issue_review_task', fake_create_review_task)
    monkeypatch.setattr(pr_final_comment, 'post_issue_comment', fake_post)

    await pr_final_comment.notify_pr_final_comment({
        'id': 'task-pr-fix',
        'status': 'completed',
        'result': 'done',
        'metadata': {
            'workspace_id': 'ws1',
            'repo': 'acme/widgets',
            'pr_number': 40,
            'pr_head': 'feature',
            'github_issue_url': 'https://github.com/acme/widgets/pull/40',
            'github_installation_id': 123,
        },
    })

    assert created
    assert created[0]['repo'] == 'acme/widgets'
    assert created[0]['issue_number'] == 40
    assert created[0]['branch'] == 'feature'
    assert created[0]['parent_task_id'] == 'task-pr-fix'
    assert 'Queued CodeTether reviewer task `task-review-40`' in comments[0]
