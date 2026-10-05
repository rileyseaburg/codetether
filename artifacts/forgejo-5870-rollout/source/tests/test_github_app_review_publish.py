import pytest

from a2a_server.github_app import review_publish


def _review_task(result: str = 'APPROVED: looks safe') -> dict:
    return {
        'id': 'task-review-1',
        'result': result,
        'metadata': {
            'source': 'github-app',
            'workflow_stage': 'review',
            'repo': 'acme/widgets',
            'pr_number': 77,
            'pr_head_sha': 'abc123',
        },
    }


@pytest.mark.parametrize(
    ('result', 'event'),
    [
        ('APPROVED: looks safe', 'APPROVE'),
        ('CHANGES_REQUESTED: fix the tests', 'REQUEST_CHANGES'),
        ('BLOCKED: provenance mismatch', 'REQUEST_CHANGES'),
        ('Review completed without a terminal verdict', 'COMMENT'),
    ],
)
def test_review_event_maps_reviewer_verdict(result, event):
    assert review_publish.review_event(_review_task(result)) == event


@pytest.mark.asyncio
async def test_publish_github_review_posts_semantic_review(monkeypatch):
    calls = []

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, token, payload))
        if method == 'GET':
            return []
        return {'id': 991}

    monkeypatch.setattr(review_publish, 'github_json', fake_github_json)

    result = await review_publish.publish_github_review(
        _review_task(), 'ghs_token'
    )

    assert result == {
        'published': True,
        'duplicate': False,
        'event': 'APPROVE',
        'review_id': 991,
    }
    assert calls[0] == (
        'GET',
        '/repos/acme/widgets/pulls/77/reviews?per_page=100',
        'ghs_token',
        None,
    )
    assert calls[1][0:3] == (
        'POST',
        '/repos/acme/widgets/pulls/77/reviews',
        'ghs_token',
    )
    assert calls[1][3]['event'] == 'APPROVE'
    assert calls[1][3]['commit_id'] == 'abc123'
    assert 'APPROVED: looks safe' in calls[1][3]['body']
    assert review_publish.review_marker('task-review-1') in calls[1][3]['body']


@pytest.mark.asyncio
async def test_publish_github_review_suppresses_duplicate_marker(monkeypatch):
    calls = []
    marker = review_publish.review_marker('task-review-1')

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, token, payload))
        return [{'id': 440, 'state': 'COMMENTED', 'body': f'done\n{marker}'}]

    monkeypatch.setattr(review_publish, 'github_json', fake_github_json)

    result = await review_publish.publish_github_review(
        _review_task(), 'ghs_token'
    )

    assert result == {
        'published': True,
        'duplicate': True,
        'event': 'COMMENTED',
        'review_id': 440,
    }
    assert len(calls) == 1
    assert calls[0][0] == 'GET'


@pytest.mark.asyncio
async def test_publish_github_review_retries_self_review_as_comment(
    monkeypatch,
):
    calls = []

    async def fake_github_json(method, path, token, payload=None):
        calls.append((method, path, token, payload))
        if method == 'GET':
            return []
        if payload['event'] == 'REQUEST_CHANGES':
            raise RuntimeError(
                'Can not request changes on your own pull request'
            )
        return {'id': 992}

    monkeypatch.setattr(review_publish, 'github_json', fake_github_json)
    task = _review_task('CHANGES_REQUESTED: fix the tests')

    result = await review_publish.publish_github_review(task, 'ghs_token')

    assert result == {
        'published': True,
        'duplicate': False,
        'event': 'COMMENT',
        'requested_event': 'REQUEST_CHANGES',
        'review_id': 992,
    }
    assert [call[3]['event'] for call in calls if call[0] == 'POST'] == [
        'REQUEST_CHANGES',
        'COMMENT',
    ]
    assert calls[-1][3]['commit_id'] == 'abc123'
    assert 'CHANGES_REQUESTED' in calls[-1][3]['body']


@pytest.mark.asyncio
async def test_publish_github_review_requires_complete_context():
    with pytest.raises(ValueError, match='missing GitHub publication context'):
        await review_publish.publish_github_review(
            {'id': 'task-review-1', 'metadata': {}}, 'ghs_token'
        )
