"""Issue work continues an existing same-family PR, not a new one."""

from types import SimpleNamespace

import pytest

from a2a_server import forgejo_inbox_dispatch as effects
from a2a_server import forgejo_related_pr as related
from a2a_server import forgejo_webhooks as fw


OLD_PR = 6878
NEW_ISSUE = 7001
LISTING_PAGES = 2

AUDIT_ISSUE = (
    '[ERROR] spotlessbinco: [FullAudit] Combined result: FAILED - '
    'Brand: ✗ (50) | Marketing: ✗ (70) | Copy: 308 chars avg'
)
AUDIT_PR = (
    'Fix #6877: [ERROR] spotlessbinco: [FullAudit] Combined result: FAILED '
    '- Brand: ✓ (85) | Marketing: ✗ (70) | Copy: 228 chars avg'
)


def _pr(number, issue, title, sha='abc'):
    return {
        'number': number,
        'title': title,
        'html_url': f'https://forge/o/r/pulls/{number}',
        'head': {'ref': f'codetether/issue-{issue}', 'sha': sha},
    }


def _api(pages):
    calls = []

    async def api(method, base, path, payload=None):
        calls.append(path)
        page = int(path.rsplit('page=', 1)[1])
        return pages[page - 1] if page <= len(pages) else []

    return api, calls


def test_varying_scores_are_one_family():
    assert related.same_family(AUDIT_ISSUE, AUDIT_PR)


def test_distinct_defects_are_not_one_family():
    other = (
        'Fix #6935: [ERROR] spotlessbinco: GTM forward failed owner=frontend '
        'event=page_view'
    )
    assert not related.same_family(AUDIT_ISSUE, other)


def test_generic_structured_log_titles_never_match():
    generic = '[ERROR] spotlessbinco: {"severity":"error","timestamp":"<ti'
    assert related.family_tokens(generic) == []
    assert not related.same_family(generic, f'Fix #1: {generic}')


@pytest.mark.asyncio
async def test_finds_oldest_matching_automation_pr():
    api, _ = _api(
        [
            [
                _pr(6999, 6998, AUDIT_PR.replace('6877', '6998'), 'new'),
                _pr(6878, 6877, AUDIT_PR, 'old'),
                {
                    'number': 5000,
                    'title': AUDIT_PR,
                    'head': {'ref': 'riley/manual', 'sha': 'human'},
                },
            ]
        ]
    )
    found = await related.find_related_pr(
        api, 'base', '/repos/o/r', 7001, AUDIT_ISSUE
    )
    assert found == {
        'number': 6878,
        'branch': 'codetether/issue-6877',
        'head_sha': 'old',
        'issue_number': 6877,
        'html_url': 'https://forge/o/r/pulls/6878',
    }


@pytest.mark.asyncio
async def test_issue_with_its_own_pr_keeps_it():
    api, _ = _api(
        [[_pr(6878, 6877, AUDIT_PR), _pr(7002, 7001, AUDIT_PR, 'own')]]
    )
    assert (
        await related.find_related_pr(
            api, 'base', '/repos/o/r', 7001, AUDIT_ISSUE
        )
        is None
    )


@pytest.mark.asyncio
async def test_listing_pages_until_short_page():
    first = [_pr(n, n - 1, f'Fix #{n}: unrelated thing {n}') for n in range(50)]
    api, calls = _api([first, [_pr(6878, 6877, AUDIT_PR)]])
    found = await related.find_related_pr(
        api, 'base', '/repos/o/r', 7001, AUDIT_ISSUE
    )
    assert found['number'] == OLD_PR
    assert len(calls) == LISTING_PAGES


@pytest.mark.asyncio
async def test_plan_freezes_related_pr(monkeypatch):
    async def api(method, base, path, payload=None):
        if path == '/repos/o/r':
            return {'default_branch': 'main', 'clone_url': 'u'}
        if path == '/repos/o/r/issues/7001':
            return {'title': AUDIT_ISSUE, 'body': 'b'}
        return [_pr(6878, 6877, AUDIT_PR, 'old')]

    monkeypatch.setattr(fw, 'forgejo_json', api)
    plan = await effects.prepare_plan(
        {'repo': 'o/r', 'number': 7001, 'is_pr': False}, 'base'
    )
    assert plan['related_pr']['number'] == OLD_PR
    assert plan['branch'] == 'main'


@pytest.mark.asyncio
async def test_plan_reuse_can_be_disabled(monkeypatch):
    monkeypatch.setenv('FORGEJO_RELATED_PR_REUSE', '0')

    async def api(method, base, path, payload=None):
        assert '/pulls' not in path
        if path == '/repos/o/r':
            return {'default_branch': 'main', 'clone_url': 'u'}
        return {'title': AUDIT_ISSUE, 'body': 'b'}

    monkeypatch.setattr(fw, 'forgejo_json', api)
    plan = await effects.prepare_plan(
        {'repo': 'o/r', 'number': 7001, 'is_pr': False}, 'base'
    )
    assert plan['related_pr'] is None


@pytest.mark.asyncio
async def test_dispatch_continues_related_pr_branch(monkeypatch):
    monkeypatch.setenv('FORGEJO_API_URL', 'https://forge/api/v1')
    monkeypatch.setenv('FORGEJO_TOKEN', 'token')
    ensured, created, workflows = [], [], []

    async def fake_ensure(ctx, clone_url, branch, token, **kwargs):
        ensured.append((branch, kwargs))
        return 'ws'

    async def fake_create(**kwargs):
        created.append(kwargs)
        return {'id': 9, 'html_url': 'https://forge/o/r/agent/tasks/9'}

    async def fake_start(workflow):
        workflows.append(workflow)
        return 'wf'

    async def fake_update(**kwargs):
        return {}

    async def no_routing():
        return {}

    monkeypatch.setattr(fw, '_ensure_workspace', fake_ensure)
    monkeypatch.setattr(fw, 'resolve_task_target', no_routing)
    monkeypatch.setattr(
        'a2a_server.forgejo_agent_client.create_task', fake_create
    )
    monkeypatch.setattr(
        'a2a_server.forgejo_agent_client.update_task', fake_update
    )
    monkeypatch.setattr(
        'a2a_server.temporal.config.temporal_settings',
        lambda: SimpleNamespace(enabled=True),
    )
    monkeypatch.setattr(
        'a2a_server.temporal.client.start_forgejo_workflow', fake_start
    )
    plan = {
        'repo_data': {'clone_url': 'https://forge/o/r.git'},
        'default_branch': 'main',
        'branch': 'main',
        'head_sha': '',
        'issue': {'title': AUDIT_ISSUE, 'body': 'b'},
        'related_pr': {
            'number': 6878,
            'branch': 'codetether/issue-6877',
            'head_sha': 'old',
            'issue_number': 6877,
            'html_url': '',
        },
    }
    await fw._dispatch(  # noqa: SLF001 - dispatch is the unit under test
        {
            'repo': 'o/r',
            'number': 7001,
            'is_pr': False,
            'body': '@codetether handle this issue',
            'repo_data': {},
            'comment_id': 0,
            'html_url': 'https://forge/o/r/issues/7001',
            '_dispatch_plan': plan,
        },
        'https://forge/api/v1',
    )
    assert workflows[0].branch == 'codetether/issue-6877'
    assert workflows[0].pull_request_number == OLD_PR
    assert workflows[0].issue_number == NEW_ISSUE
    assert created[0]['pull_request_index'] == OLD_PR
    assert 'open PR #6878' in created[0]['prompt']
    assert 'Do not create a new branch' in created[0]['prompt']
    assert ensured[0][1]['workspace_branch'] == 'codetether/issue-6877'
