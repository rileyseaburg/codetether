import pytest

from a2a_server.github_app import active_work


@pytest.mark.asyncio
async def test_dispatch_active_work_for_repo_queues_open_issues_and_prs(monkeypatch):
    calls = []

    async def fake_installation_token(installation_id):
        assert installation_id == 123
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        assert method == 'GET'
        assert token == 'ghs_test'
        assert path == '/repos/owner/repo/issues?state=open&per_page=100&page=1'
        return [
            {'id': 11, 'number': 1, 'body': '@codetether implement this'},
            {'id': 22, 'number': 2, 'body': 'failing', 'pull_request': {}},
        ]

    async def fake_handle_fix_request(context, token):
        calls.append((context, token))
        return {'accepted': True, 'clone_task_id': f'task-{context.issue_number}'}

    async def fake_has_active_github_app_task(repo, number):
        return False

    monkeypatch.setattr(active_work, 'installation_token', fake_installation_token)
    monkeypatch.setattr(active_work, 'github_json', fake_github_json)
    monkeypatch.setattr(active_work, 'handle_fix_request', fake_handle_fix_request)
    monkeypatch.setattr(active_work, 'has_active_github_app_task', fake_has_active_github_app_task)

    results = await active_work.dispatch_active_work_for_repo('owner/repo', 123)

    assert [result.task_id for result in results] == ['task-1', 'task-2']
    assert calls[0][0].pr_number is None
    assert calls[0][0].comment_body == '@codetether implement this'
    assert calls[1][0].pr_number == 2
    assert calls[1][0].comment_body.startswith('@codetether handle this active work item.')


@pytest.mark.asyncio
async def test_dispatch_active_work_for_repo_paginates_all_open_items(monkeypatch):
    paths = []

    async def fake_installation_token(installation_id):
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        paths.append(path)
        if path.endswith('page=1'):
            return [{'id': 11, 'number': 1, 'body': 'one'}]
        if path.endswith('page=2'):
            return [{'id': 22, 'number': 2, 'body': 'two'}]
        return []

    async def fake_handle_fix_request(context, token):
        return {'accepted': True, 'clone_task_id': f'task-{context.issue_number}'}

    async def fake_has_active_github_app_task(repo, number):
        return False

    monkeypatch.setattr(active_work, 'installation_token', fake_installation_token)
    monkeypatch.setattr(active_work, 'github_json', fake_github_json)
    monkeypatch.setattr(active_work, 'handle_fix_request', fake_handle_fix_request)
    monkeypatch.setattr(active_work, 'has_active_github_app_task', fake_has_active_github_app_task)

    results = await active_work.dispatch_active_work_for_repo('owner/repo', 123, limit=1)

    assert paths == [
        '/repos/owner/repo/issues?state=open&per_page=1&page=1',
        '/repos/owner/repo/issues?state=open&per_page=1&page=2',
        '/repos/owner/repo/issues?state=open&per_page=1&page=3',
    ]
    assert [result.task_id for result in results] == ['task-1', 'task-2']


@pytest.mark.asyncio
async def test_dispatch_active_work_for_installation_walks_installed_repos(monkeypatch):
    dispatched = []

    async def fake_list_installation_repositories(installation_id):
        assert installation_id == 123
        return [{'full_name': 'owner/one'}, {'full_name': 'owner/two'}]

    async def fake_dispatch_active_work_for_repo(repo, installation_id, limit=100):
        dispatched.append((repo, installation_id, limit))
        return [
            active_work.ActiveWorkDispatch(
                repo=repo,
                number=1,
                kind='issue',
                accepted=True,
            )
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

    results = await active_work.dispatch_active_work_for_installation(123, limit_per_repo=50)

    assert dispatched == [('owner/one', 123, 50), ('owner/two', 123, 50)]
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
        return {'accepted': True, 'clone_task_id': f'task-{context.issue_number}'}

    monkeypatch.setattr(active_work, 'installation_token', fake_installation_token)
    monkeypatch.setattr(active_work, 'github_json', fake_github_json)
    monkeypatch.setattr(
        active_work,
        'has_active_github_app_task',
        fake_has_active_github_app_task,
    )
    monkeypatch.setattr(active_work, 'handle_fix_request', fake_handle_fix_request)

    results = await active_work.dispatch_active_work_for_repo('owner/repo', 123)

    assert calls == [2]
    assert [(result.number, result.accepted, result.reason, result.task_id) for result in results] == [
        (1, False, 'active-task-exists', ''),
        (2, True, '', 'task-2'),
    ]