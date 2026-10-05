"""Single-owner review identity, exact coverage and fail-closed publication."""

import hashlib
import json

from unittest.mock import AsyncMock

import pytest

from a2a_server.forgejo_review_owner import (
    activities,
    evidence,
    identities,
    state,
)


def test_identity_is_shared_by_issue_and_pr_deliveries():
    assert identities('owner/repo', 7, 'a') == identities('owner/repo', 7, 'a')
    assert identities('owner/repo', 7, 'a') != identities('owner/repo', 7, 'b')
    assert identities('owner/repo', 7, 'a') != identities('owner/other', 7, 'a')


def test_utf8_chunks_cover_every_byte(monkeypatch):
    monkeypatch.setattr(evidence, 'CHUNK_BYTES', 83)
    data = ('diff --git a/one b/one\n+安全 café\n' * 70).encode()
    chunks = evidence.split_diff(data)
    assert b''.join(c['text'].encode() for c in chunks) == data
    assert all(c['bytes'] <= 83 for c in chunks)
    assert all(
        hashlib.sha256(c['text'].encode()).hexdigest() == c['sha256']
        for c in chunks
    )


def test_oversized_diff_cannot_be_partially_reviewed(monkeypatch):
    monkeypatch.setattr(evidence, 'MAX_DIFF', 10)
    with pytest.raises(ValueError, match='size_out_of_bounds'):
        evidence.split_diff(b'x' * 11)


@pytest.mark.parametrize(
    'output',
    [
        {
            'reviewed_chunk_sha256': 'wrong',
            'verdict': 'APPROVED',
            'findings': [],
        },
        {
            'reviewed_chunk_sha256': 'hash',
            'verdict': 'APPROVED',
            'findings': [{'severity': 'blocking'}],
        },
        {
            'reviewed_chunk_sha256': 'hash',
            'verdict': 'CHANGES_REQUESTED',
            'findings': [],
        },
    ],
)
def test_invalid_ack_or_verdict_never_approves(output):
    with pytest.raises(ValueError):
        evidence.parse_result(json.dumps(output), 'hash')


@pytest.mark.asyncio
async def test_cancelled_owner_cannot_publish_success(monkeypatch):
    monkeypatch.setattr(
        state.db, 'db_get_task', AsyncMock(return_value={'status': 'cancelled'})
    )
    api = AsyncMock()
    monkeypatch.setattr(state, 'forgejo_json', api)
    assert (
        await state.finish({'task_id': 'owner'}, 'APPROVED', 'text')
        == 'CANCELLED'
    )
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_head_cannot_publish_any_green_status(monkeypatch):
    monkeypatch.setattr(
        state.db,
        'db_get_task',
        AsyncMock(return_value={'status': 'working', 'metadata': {}}),
    )
    monkeypatch.setattr(state.db, 'db_update_task_status', AsyncMock())
    monkeypatch.setattr(
        state,
        'bound_pr',
        AsyncMock(side_effect=RuntimeError('review_head_advanced')),
    )
    api = AsyncMock()
    monkeypatch.setattr(state, 'forgejo_json', api)
    assert (
        await state.finish({'task_id': 'owner'}, 'APPROVED', 'text')
        == 'CANCELLED'
    )
    api.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_chunk_fails_closed(monkeypatch):
    owner = {
        'metadata': {'review_manifest': [{'sha256': 'a'}, {'sha256': 'b'}]}
    }
    monkeypatch.setattr(
        activities.db, 'db_get_task', AsyncMock(return_value=owner)
    )
    end = AsyncMock(return_value='BLOCKED')
    monkeypatch.setattr(activities, 'checkpoint', AsyncMock())
    monkeypatch.setattr(activities, 'finish', end)
    assert (
        await activities.complete({'task_id': 'owner', 'chunks': ['only-one']})
        == 'BLOCKED'
    )
    assert end.await_args.args[1] == 'BLOCKED'


@pytest.mark.asyncio
async def test_all_exact_chunks_required_for_approval(monkeypatch):
    records = {
        'owner': {
            'metadata': {
                'review_manifest': [{'sha256': 'a'}, {'sha256': 'b'}],
                'review_context': {'complete_diff_sha256': 'whole'},
            }
        }
    }
    for name, sha in (('one', 'a'), ('two', 'b')):
        records[name] = {
            'status': 'completed',
            'metadata': {
                'review_validated_output': {
                    'reviewed_chunk_sha256': sha,
                    'verdict': 'APPROVED',
                    'findings': [],
                }
            },
        }

    async def get(name):
        record = records[name]
        if name != 'owner':
            record['result'] = json.dumps(
                {
                    **record['metadata']['review_validated_output'],
                    'summary': 'Reviewed exact chunk',
                }
            )
        return record

    monkeypatch.setattr(activities.db, 'db_get_task', get)
    monkeypatch.setattr(activities, 'checkpoint', AsyncMock())
    end = AsyncMock(return_value='APPROVED')
    monkeypatch.setattr(activities, 'finish', end)
    assert (
        await activities.complete(
            {'task_id': 'owner', 'chunks': ['one', 'two']}
        )
        == 'APPROVED'
    )
    assert '2/2' in end.await_args.args[2]
    records['two']['metadata']['review_validated_output'][
        'reviewed_chunk_sha256'
    ] = 'old'
    await activities.complete({'task_id': 'owner', 'chunks': ['one', 'two']})
    assert end.await_args.args[1] == 'BLOCKED'


@pytest.mark.asyncio
async def test_pending_does_not_overwrite_terminal_on_duplicate_delivery(
    monkeypatch,
):
    from a2a_server.forgejo_review_owner import ensure_review, hooks
    from a2a_server.temporal import config

    monkeypatch.setenv('FORGEJO_SINGLE_REVIEW_REPOS', 'owner/repo')
    monkeypatch.setattr(
        state,
        'current_pr',
        AsyncMock(return_value={'number': 7, 'head': {'sha': 'head'}}),
    )
    monkeypatch.setattr(state, 'ensure_record', AsyncMock())
    monkeypatch.setattr(hooks, 'cancel_old_reviews', AsyncMock())
    client = AsyncMock()
    monkeypatch.setattr(
        config, 'get_temporal_client', AsyncMock(return_value=client)
    )
    first = await ensure_review('owner/repo', 7)
    second = await ensure_review('owner/repo', 7)
    assert first == second
    assert (
        client.start_workflow.await_args_list[0].kwargs['id']
        == client.start_workflow.await_args_list[1].kwargs['id']
    )


@pytest.mark.asyncio
async def test_native_workflow_attaches_to_owner_without_spawning_legacy_review(
    monkeypatch,
):
    from a2a_server import forgejo_automation as automation
    from a2a_server import forgejo_review_owner

    monkeypatch.setenv('FORGEJO_SINGLE_REVIEW_REPOS', 'owner/repo')
    monkeypatch.setattr(
        automation,
        'forgejo_json',
        AsyncMock(
            return_value={
                'number': 7,
                'state': 'open',
                'head': {'sha': 'head', 'ref': 'branch'},
            }
        ),
    )
    owner = AsyncMock(return_value='owner-id')
    monkeypatch.setattr(forgejo_review_owner, 'ensure_review', owner)
    legacy = AsyncMock()
    monkeypatch.setattr(automation, '_task_exists', legacy)
    result = await automation.create_forgejo_review_task(
        {
            'status': 'completed',
            'metadata': {
                'repo': 'owner/repo',
                'pr_number': 7,
                'forgejo_api_url': 'https://forge.example/api/v1',
                'workspace_id': 'workspace',
                'branch_name': 'branch',
                'workflow_stage': 'code',
            },
        }
    )
    assert result == 'owner-id'
    legacy.assert_not_awaited()
