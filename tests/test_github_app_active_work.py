from datetime import UTC, datetime

import pytest

from a2a_server.github_app import active_work


INSTALLATION_ID = 123
PR_NUMBER = 2


@pytest.mark.asyncio
async def test_dispatch_active_work_for_repo_queues_open_issues_and_prs(
    monkeypatch,
):
    calls = []

    async def fake_installation_token(installation_id):
        assert installation_id == INSTALLATION_ID
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        assert method == 'GET'
        assert token == 'ghs_test'
        assert path == (
            '/repos/owner/repo/issues?state=open&per_page=100&page=1'
        )
        return [
            {
                'id': 11,
                'number': 1,
                'body': '@codetether implement this',
                'user': {'login': 'issue-author'},
            },
            {
                'id': 22,
                'number': PR_NUMBER,
                'body': '@codetether fix the failing PR',
                'pull_request': {},
                'user': {'login': 'pr-author'},
            },
        ]

    async def fake_handle_fix_request(context, token):
        calls.append((context, token))
        return {
            'accepted': True,
            'clone_task_id': f'task-{context.issue_number}',
        }

    async def fake_has_active_github_app_task(repo, number):
        return False

    monkeypatch.setattr(
        active_work,
        'installation_token',
        fake_installation_token,
    )
    monkeypatch.setattr(active_work, 'github_json', fake_github_json)
    monkeypatch.setattr(
        active_work,
        'handle_fix_request',
        fake_handle_fix_request,
    )
    monkeypatch.setattr(
        active_work,
        'has_active_github_app_task',
        fake_has_active_github_app_task,
    )

    results = await active_work.dispatch_active_work_for_repo(
        'owner/repo',
        INSTALLATION_ID,
    )

    assert [result.task_id for result in results] == ['task-1', 'task-2']
    assert calls[0][0].pr_number is None
    assert calls[0][0].comment_body == '@codetether implement this'
    assert calls[0][0].actor_login == 'issue-author'
    assert calls[1][0].pr_number == PR_NUMBER
    assert calls[1][0].comment_body == '@codetether fix the failing PR'
    assert calls[1][0].actor_login == 'pr-author'


@pytest.mark.asyncio
async def test_dispatch_active_work_for_repo_paginates_all_open_items(
    monkeypatch,
):
    paths = []

    async def fake_installation_token(installation_id):
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        paths.append(path)
        if path.endswith('page=1'):
            return [
                {'id': 11, 'number': 1, 'body': '@codetether implement one'},
            ]
        if path.endswith('page=2'):
            return [
                {'id': 22, 'number': 2, 'body': '@codetether implement two'},
            ]
        return []

    async def fake_handle_fix_request(context, token):
        return {
            'accepted': True,
            'clone_task_id': f'task-{context.issue_number}',
        }

    async def fake_has_active_github_app_task(repo, number):
        return False

    monkeypatch.setattr(
        active_work,
        'installation_token',
        fake_installation_token,
    )
    monkeypatch.setattr(active_work, 'github_json', fake_github_json)
    monkeypatch.setattr(
        active_work,
        'handle_fix_request',
        fake_handle_fix_request,
    )
    monkeypatch.setattr(
        active_work,
        'has_active_github_app_task',
        fake_has_active_github_app_task,
    )

    results = await active_work.dispatch_active_work_for_repo(
        'owner/repo',
        INSTALLATION_ID,
        limit=1,
    )

    assert paths == [
        '/repos/owner/repo/issues?state=open&per_page=1&page=1',
        '/repos/owner/repo/issues?state=open&per_page=1&page=2',
        '/repos/owner/repo/issues?state=open&per_page=1&page=3',
    ]
    assert [result.task_id for result in results] == ['task-1', 'task-2']


@pytest.mark.asyncio
async def test_dispatch_active_work_for_installation_walks_installed_repos(
    monkeypatch,
):
    dispatched = []

    async def fake_list_installation_repositories(installation_id):
        assert installation_id == INSTALLATION_ID
        return [{'full_name': 'owner/one'}, {'full_name': 'owner/two'}]

    async def fake_dispatch_active_work_for_repo(
        repo,
        installation_id,
        limit=100,
    ):
        dispatched.append((repo, installation_id, limit))
        return [
            active_work.ActiveWorkDispatch(
                repo=repo,
                number=1,
                kind='issue',
                accepted=True,
            ),
        ]

    monkeypatch.setattr(
        active_work,
        'list_installation_repositories',
        fake_list_installation_repositories,
    )
    monkeypatch.setattr(
        active_work,
        'dispatch_active_work_for_repo',
        fake_dispatch_active_work_for_repo,
    )

    results = await active_work.dispatch_active_work_for_installation(
        INSTALLATION_ID,
        limit_per_repo=50,
    )

    assert dispatched == [
        ('owner/one', INSTALLATION_ID, 50),
        ('owner/two', INSTALLATION_ID, 50),
    ]
    assert [result.repo for result in results] == ['owner/one', 'owner/two']


@pytest.mark.asyncio
async def test_dispatch_active_work_skips_items_with_active_tasks(monkeypatch):
    calls = []

    async def fake_installation_token(installation_id):
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        return [
            {'id': 11, 'number': 1, 'body': '@codetether implement this'},
            {'id': 22, 'number': 2, 'body': '@codetether implement this'},
        ]

    async def fake_has_active_github_app_task(repo, number):
        return number == 1

    async def fake_handle_fix_request(context, token):
        calls.append(context.issue_number)
        return {
            'accepted': True,
            'clone_task_id': f'task-{context.issue_number}',
        }

    monkeypatch.setattr(
        active_work,
        'installation_token',
        fake_installation_token,
    )
    monkeypatch.setattr(active_work, 'github_json', fake_github_json)
    monkeypatch.setattr(
        active_work,
        'has_active_github_app_task',
        fake_has_active_github_app_task,
    )
    monkeypatch.setattr(
        active_work,
        'handle_fix_request',
        fake_handle_fix_request,
    )

    results = await active_work.dispatch_active_work_for_repo(
        'owner/repo',
        INSTALLATION_ID,
    )

    assert calls == [2]
    assert [
        (result.number, result.accepted, result.reason, result.task_id)
        for result in results
    ] == [
        (1, False, 'active-task-exists', ''),
        (2, True, '', 'task-2'),
    ]


@pytest.mark.asyncio
async def test_dispatch_active_work_skips_stale_and_non_explicit_items(
    monkeypatch,
):
    calls = []

    async def fake_installation_token(installation_id):
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        fresh = datetime.now(UTC).isoformat()
        return [
            {
                'id': 11,
                'number': 1,
                'body': '@codetether implement this',
                'updated_at': '2000-01-01T00:00:00Z',
            },
            {
                'id': 22,
                'number': 2,
                'body': 'old open issue without an explicit bot request',
                'updated_at': fresh,
            },
            {
                'id': 33,
                'number': 3,
                'body': '@codetether handle this issue',
                'updated_at': fresh,
            },
        ]

    async def fake_has_active_github_app_task(repo, number):
        return False

    async def fake_handle_fix_request(context, token):
        calls.append(context.issue_number)
        return {
            'accepted': True,
            'clone_task_id': f'task-{context.issue_number}',
        }

    monkeypatch.setattr(
        active_work,
        'installation_token',
        fake_installation_token,
    )
    monkeypatch.setattr(active_work, 'github_json', fake_github_json)
    monkeypatch.setattr(
        active_work,
        'has_active_github_app_task',
        fake_has_active_github_app_task,
    )
    monkeypatch.setattr(
        active_work,
        'handle_fix_request',
        fake_handle_fix_request,
    )
    monkeypatch.setattr(
        active_work,
        '_active_work_max_age',
        lambda: active_work.timedelta(days=7),
    )
    results = await active_work.dispatch_active_work_for_repo(
        'owner/repo',
        INSTALLATION_ID,
    )

    assert calls == [3]
    assert [
        (result.number, result.reason, result.task_id) for result in results
    ] == [
        (1, 'stale-active-item', ''),
        (2, 'no-explicit-fix-request', ''),
        (3, '', 'task-3'),
    ]
