import json

import pytest

from a2a_server.github_app import checks
from a2a_server.github_app.task_status_hook import handle_github_app_terminal_task


FIXED_TIME = '2026-01-02T03:04:05+00:00'


def _task(**overrides):
    metadata = {
        'source': 'github-app',
        'repo': 'owner/repo',
        'pr_number': 7,
        'workflow_stage': 'code',
        'github_installation_id': 123,
        'github_check_head_sha': 'abc123',
        'github_issue_url': 'https://github.com/owner/repo/pull/7?token=secret',
        'completed_at': FIXED_TIME,
        'started_at': FIXED_TIME,
        'steps': [{'name': '<build>', 'status': 'completed', 'password': 'hidden'}],
        'tool_calls': [{'name': 'bash', 'status': 'completed', 'args': {'command': 'pytest'}, 'result': 'secret'}],
        'codetether_provenance': {
            'origin': 'github-app',
            'intent': 'test',
            'token': 'must-redact',
            'ignored': 'not-allowed',
            'ap_origin': {'authorization': 'Bearer ghs_abcdefghijklmnopqrstuvwxyz123456'},
        },
        'evidence': [{
            'label': 'pytest',
            'path': '/tmp/report.txt',
            'url': 'https://user:pass@example.test/report?access_token=secret&ok=1',
            'password': 'hidden',
        }],
        'private_prompt': 'do not render',
    }
    base = {
        'id': 'task-1',
        'title': 'Apply PR fix #7',
        'status': 'completed',
        'result': 'done with token=ghs_abcdefghijklmnopqrstuvwxyz123456',
        'metadata': metadata,
    }
    base.update(overrides)
    return base


def test_render_check_output_redacts_escapes_and_normalizes_schema():
    output = checks.render_check_output(_task())

    rendered = output['summary'] + output['text']
    assert '&lt;build&gt;' in rendered
    assert 'ghs_abcdefghijklmnopqrstuvwxyz123456' not in rendered
    assert 'access_token=secret' not in rendered
    assert 'user:pass@' not in rendered
    assert '[REDACTED]' in rendered
    assert 'private_prompt' not in rendered
    assert '"args"' not in rendered
    assert '"result"' not in rendered
    assert 'must-redact' not in rendered
    assert 'not-allowed' not in rendered
    assert 'codetether.checks.v1' in rendered
    assert 'pytest' in rendered

    schema_json = output['text'].removeprefix('```json\n').removesuffix('\n```')
    schema = json.loads(schema_json)
    assert schema['tool_calls'] == [{'name': 'bash', 'status': 'completed', 'redacted': True}]
    assert 'tool_call_details' in schema['redactions']


def test_output_limits_include_explicit_truncation_marker():
    task = _task(title='x' * 200, result='y' * 9000)
    output = checks.render_check_output(task)
    assert len(output['title']) <= 80 + len('\n\n… truncated for GitHub Checks output')
    assert 'truncated for GitHub Checks output' in output['title']
    assert 'truncated for GitHub Checks output' in output['summary']


def test_completed_payload_exact_shape_and_conclusion():
    payload = checks.build_check_run_payload(_task(), status='completed', include_head_sha=True)

    assert payload['name'] == 'CodeTether / code'
    assert payload['status'] == 'completed'
    assert payload['head_sha'] == 'abc123'
    assert payload['conclusion'] == 'success'
    assert payload['completed_at'] == FIXED_TIME
    assert 'started_at' not in payload
    assert payload['details_url'] == 'https://github.com/owner/repo/pull/7?token=[REDACTED]'
    assert set(payload) == {'name', 'status', 'output', 'details_url', 'head_sha', 'conclusion', 'completed_at'}


@pytest.mark.parametrize(
    ('task_status', 'expected'),
    [
        ('completed', 'success'),
        ('cancelled', 'cancelled'),
        ('failed', 'failure'),
        ('timed_out', 'timed_out'),
        ('skipped', 'skipped'),
        ('unknown', 'neutral'),
    ],
)
def test_completed_conclusion_mapping(task_status, expected):
    payload = checks.build_check_run_payload(_task(status=task_status), status='completed')
    assert payload['conclusion'] == expected


def test_in_progress_payload_omits_conclusion_and_completed_at():
    payload = checks.build_check_run_payload(_task(status='in_progress'), status='in_progress', include_head_sha=False)

    assert payload['status'] == 'in_progress'
    assert payload['started_at'] == FIXED_TIME
    assert 'conclusion' not in payload
    assert 'completed_at' not in payload
    assert 'head_sha' not in payload
    assert set(payload) == {'name', 'status', 'output', 'details_url', 'started_at'}


def test_invalid_status_rejected():
    with pytest.raises(ValueError):
        checks.build_check_run_payload(_task(), status='bad')  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_ensure_task_check_run_creates_check_run_with_exact_payload(monkeypatch):
    calls = []

    async def fake_installation_token(installation_id):
        assert installation_id == 123
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, token, payload))
        return {'id': 456}

    async def fake_record(task_id, check_run_id):
        calls.append(('record', task_id, check_run_id, None))

    monkeypatch.setattr(checks, 'installation_token', fake_installation_token)
    monkeypatch.setattr(checks, 'github_json', fake_github_json)
    monkeypatch.setattr(checks, '_record_check_run_id', fake_record)

    check_run_id = await checks.ensure_task_check_run(_task())

    assert check_run_id == 456
    method, path, token, payload = calls[0]
    assert method == 'POST'
    assert path == '/repos/owner/repo/check-runs'
    assert token == 'ghs_test'
    assert payload['name'] == 'CodeTether / code'
    assert payload['head_sha'] == 'abc123'
    assert payload['status'] == 'completed'
    assert payload['conclusion'] == 'success'
    assert payload['completed_at'] == FIXED_TIME
    assert 'started_at' not in payload
    assert calls[1] == ('record', 'task-1', 456, None)


@pytest.mark.asyncio
async def test_ensure_task_check_run_updates_existing_in_progress_without_conclusion(monkeypatch):
    calls = []
    task = _task(status='in_progress', metadata={**_task()['metadata'], 'github_check_run_id': 456})

    async def fake_installation_token(installation_id):
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, payload))
        return {'id': 456}

    monkeypatch.setattr(checks, 'installation_token', fake_installation_token)
    monkeypatch.setattr(checks, 'github_json', fake_github_json)

    assert await checks.ensure_task_check_run(task, status='in_progress') == 456
    assert calls[0][0] == 'PATCH'
    assert calls[0][1] == '/repos/owner/repo/check-runs/456'
    assert calls[0][2]['status'] == 'in_progress'
    assert 'head_sha' not in calls[0][2]
    assert 'conclusion' not in calls[0][2]
    assert 'completed_at' not in calls[0][2]
    assert calls[0][2]['started_at'] == FIXED_TIME


@pytest.mark.asyncio
async def test_missing_context_safely_returns_none(monkeypatch):
    async def fail_installation_token(installation_id):
        raise AssertionError('should not mint token when context is missing')

    monkeypatch.setattr(checks, 'installation_token', fail_installation_token)
    task = _task(metadata={'source': 'github-app', 'repo': 'owner/repo'})
    assert await checks.ensure_task_check_run(task) is None


@pytest.mark.asyncio
async def test_api_failure_swallowed(monkeypatch):
    async def fake_installation_token(installation_id):
        return 'ghs_test', None

    async def failing_github_json(method, path, token, payload=None):
        raise RuntimeError('api down')

    monkeypatch.setattr(checks, 'installation_token', fake_installation_token)
    monkeypatch.setattr(checks, 'github_json', failing_github_json)

    assert await checks.ensure_task_check_run(_task()) is None


@pytest.mark.asyncio
async def test_terminal_hook_continues_when_check_update_fails(monkeypatch):
    from a2a_server import database as db

    calls = []

    async def fake_db_get_task(task_id):
        return _task(id=task_id)

    async def failing_check(task, status='completed'):
        raise RuntimeError('network down')

    async def fake_notify(task, worker_id=None):
        calls.append((task['id'], worker_id))

    monkeypatch.setattr(db, 'db_get_task', fake_db_get_task)

    from a2a_server.github_app import task_completion

    monkeypatch.setattr(checks, 'ensure_task_check_run', failing_check)
    monkeypatch.setattr(task_completion, 'notify_issue_task_completion', fake_notify)

    await handle_github_app_terminal_task('task-1', 'worker-1')

    assert calls == [('task-1', 'worker-1')]


@pytest.mark.asyncio
async def test_check_run_permission_block_uses_commit_status_fallback(monkeypatch, caplog):
    calls = []

    async def fake_installation_token(installation_id):
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, payload))
        if path.endswith('/check-runs'):
            raise RuntimeError('GitHub API POST failed: Resource not accessible by integration')
        return {'id': 789}

    monkeypatch.setattr(checks, 'installation_token', fake_installation_token)
    monkeypatch.setattr(checks, 'github_json', fake_github_json)

    check_id = await checks.ensure_task_check_run(_task())

    assert check_id == 789
    assert calls[0][0] == 'POST'
    assert calls[0][1] == '/repos/owner/repo/check-runs'
    assert calls[1][0] == 'POST'
    assert calls[1][1] == '/repos/owner/repo/statuses/abc123'
    assert calls[1][2]['state'] == 'success'
    assert calls[1][2]['context'] == 'CodeTether / code'
    assert 'task-1 is completed' in calls[1][2]['description']


@pytest.mark.asyncio
async def test_check_run_and_status_permission_block_is_logged(monkeypatch, caplog):
    async def fake_installation_token(installation_id):
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        raise RuntimeError('GitHub API failed: Resource not accessible by integration')

    monkeypatch.setattr(checks, 'installation_token', fake_installation_token)
    monkeypatch.setattr(checks, 'github_json', fake_github_json)

    with caplog.at_level('ERROR'):
        assert await checks.ensure_task_check_run(_task()) is None

    assert 'Grant the GitHub App Checks: write permission, or Statuses: write' in caplog.text


def test_commit_status_payload_maps_in_progress_to_pending():
    payload = checks.build_commit_status_payload(_task(status='in_progress'), status='in_progress')

    assert payload['state'] == 'pending'
    assert payload['context'] == 'CodeTether / code'
    assert payload['target_url'] == 'https://github.com/owner/repo/pull/7?token=[REDACTED]'


@pytest.mark.asyncio
async def test_statuses_mode_skips_checks_api(monkeypatch):
    calls = []

    async def fake_installation_token(installation_id):
        return 'ghs_test', None

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, token, payload))
        return {'id': 987}

    monkeypatch.setenv('GITHUB_APP_STATUS_PUBLISHER', 'statuses')
    monkeypatch.setattr(checks, 'installation_token', fake_installation_token)
    monkeypatch.setattr(checks, 'github_json', fake_github_json)

    assert await checks.ensure_task_check_run(_task()) == 987
    assert len(calls) == 1
    assert calls[0][0] == 'POST'
    assert calls[0][1] == '/repos/owner/repo/statuses/abc123'
    assert calls[0][3]['state'] == 'success'


@pytest.mark.asyncio
async def test_off_mode_skips_installation_token(monkeypatch):
    async def fail_installation_token(installation_id):
        raise AssertionError('off mode should not mint an installation token')

    monkeypatch.setenv('GITHUB_APP_STATUS_PUBLISHER', 'off')
    monkeypatch.setattr(checks, 'installation_token', fail_installation_token)

    assert await checks.ensure_task_check_run(_task()) is None


def test_invalid_publisher_mode_falls_back_to_checks(monkeypatch, caplog):
    monkeypatch.setenv('GITHUB_APP_STATUS_PUBLISHER', 'bogus')

    with caplog.at_level('WARNING'):
        assert checks._publisher_mode() == 'checks'

    assert 'Invalid GITHUB_APP_STATUS_PUBLISHER' in caplog.text


@pytest.mark.asyncio
async def test_fix_task_without_result_or_branch_delta_fails_before_green_check(monkeypatch):
    from a2a_server import database as db
    from a2a_server.github_app import task_completion
    from a2a_server.github_app import pr_final_comment

    calls = []
    failed = []

    task = _task(
        result=None,
        metadata={
            **_task()['metadata'],
            'workflow_stage': 'fix',
            'pr_head_sha': 'same-sha',
            'github_check_head_sha': 'same-sha',
        },
    )

    async def fake_db_get_task(task_id):
        if failed:
            return {**task, 'status': 'failed', 'error': failed[-1][2]}
        return task

    async def fake_update(task_id, status, worker_id=None, result=None, error=None):
        failed.append((task_id, status, error))
        return True

    async def fake_context(_task):
        return ('owner/repo', 7, None, 'token')

    async def fake_github_json(method, path, token, payload=None):
        assert (method, path, token) == ('GET', '/repos/owner/repo/pulls/7', 'token')
        return {'head': {'sha': 'same-sha'}}

    async def fake_check(task, status='completed'):
        calls.append(('check', task['status'], task.get('error')))

    async def fake_notify(task, worker_id=None):
        calls.append(('notify', task['status'], worker_id, task.get('error')))

    monkeypatch.setattr(db, 'db_get_task', fake_db_get_task)
    monkeypatch.setattr(db, 'db_update_task_status', fake_update)
    monkeypatch.setattr(pr_final_comment, 'github_app_task_context', fake_context)
    monkeypatch.setattr(task_completion, 'notify_issue_task_completion', fake_notify)
    monkeypatch.setattr(checks, 'ensure_task_check_run', fake_check)
    monkeypatch.setattr('a2a_server.github_app.auth.github_json', fake_github_json)

    await handle_github_app_terminal_task('task-1', 'worker-1')

    assert failed == [('task-1', 'failed', 'GitHub fix task completed without moving PR #7 from head `same-sha`.')]
    assert calls == [
        ('check', 'failed', failed[0][2]),
        ('notify', 'failed', 'worker-1', failed[0][2]),
    ]


@pytest.mark.asyncio
async def test_fix_task_with_result_but_without_branch_delta_fails_before_green_check(monkeypatch):
    from a2a_server import database as db
    from a2a_server.github_app import task_completion
    from a2a_server.github_app import pr_final_comment

    calls = []
    failed = []

    task = _task(
        result='I reviewed the PR and found remaining problems, but did not push a commit.',
        metadata={
            **_task()['metadata'],
            'workflow_stage': 'fix',
            'pr_head_sha': 'same-sha',
            'github_check_head_sha': 'same-sha',
        },
    )

    async def fake_db_get_task(task_id):
        if failed:
            return {**task, 'status': 'failed', 'error': failed[-1][2]}
        return task

    async def fake_update(task_id, status, worker_id=None, result=None, error=None):
        failed.append((task_id, status, error))
        return True

    async def fake_context(_task):
        return ('owner/repo', 7, None, 'token')

    async def fake_github_json(method, path, token, payload=None):
        assert (method, path, token) == ('GET', '/repos/owner/repo/pulls/7', 'token')
        return {'head': {'sha': 'same-sha'}}

    async def fake_check(task, status='completed'):
        calls.append(('check', task['status'], task.get('error')))

    async def fake_notify(task, worker_id=None):
        calls.append(('notify', task['status'], worker_id, task.get('error')))

    monkeypatch.setattr(db, 'db_get_task', fake_db_get_task)
    monkeypatch.setattr(db, 'db_update_task_status', fake_update)
    monkeypatch.setattr(pr_final_comment, 'github_app_task_context', fake_context)
    monkeypatch.setattr(task_completion, 'notify_issue_task_completion', fake_notify)
    monkeypatch.setattr(checks, 'ensure_task_check_run', fake_check)
    monkeypatch.setattr('a2a_server.github_app.auth.github_json', fake_github_json)

    await handle_github_app_terminal_task('task-1', 'worker-1')

    assert failed == [('task-1', 'failed', 'GitHub fix task completed without moving PR #7 from head `same-sha`.')]
    assert calls == [
        ('check', 'failed', failed[0][2]),
        ('notify', 'failed', 'worker-1', failed[0][2]),
    ]
