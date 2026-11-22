"""The coding agent triages issues against open work before review."""

import pytest

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from a2a_server import forgejo_triage as triage
from a2a_server.temporal.models import ForgejoAgentWorkflowInput
from a2a_server.temporal.workflows import ForgejoAgentWorkflow
from tests.test_forgejo_temporal_workflow import (
    FakeActivities,
    complete,
    wait_for_stage,
)


DUPLICATE_PR = 6878
ISSUE = 7063

ISSUE_INPUT = ForgejoAgentWorkflowInput(
    forgejo_task_id=43,
    repository='acme/widgets',
    issue_number=ISSUE,
    pull_request_number=0,
    workspace_id='workspace-1',
    branch='codetether/issue-7063',
    head_sha='',
    operation='fix',
)


def test_parse_triage_verdicts():
    assert triage.parse_triage('no verdict') == ('proceed', 0, '')
    assert triage.parse_triage('work\nCODETETHER_TRIAGE: duplicate #6878') == (
        'duplicate',
        DUPLICATE_PR,
        '#6878',
    )
    verdict, number, reason = triage.parse_triage(
        'CODETETHER_TRIAGE: not_needed zero-failure report logged as error'
    )
    assert (verdict, number) == ('not_needed', 0)
    assert 'zero-failure' in reason
    # A duplicate without a target is not trusted.
    assert triage.parse_triage('CODETETHER_TRIAGE: duplicate')[0] == 'proceed'
    # The last verdict line wins.
    assert (
        triage.parse_triage(
            'CODETETHER_TRIAGE: duplicate #1\nCODETETHER_TRIAGE: proceed'
        )[0]
        == 'proceed'
    )


@pytest.mark.asyncio
async def test_similar_open_work_ranks_matching_titles():
    pulls = [
        {
            'number': 6878,
            'title': 'Fix #6877: transport retrying privately attempt',
            'head': {'ref': 'codetether/issue-6877'},
        },
        {'number': 5, 'title': 'Unrelated geocoding change'},
    ]
    issues = [
        {'number': ISSUE, 'title': 'transport retrying privately attempt 1'},
        {'number': 7064, 'title': 'transport retrying privately attempt 2'},
    ]

    async def api(method, base, path, payload=None):
        return pulls if '/pulls?' in path else issues

    found = await triage.similar_open_work(
        api, 'base', '/repos/o/r', ISSUE, issues[0]['title']
    )
    numbers = [item['number'] for item in found]
    assert ISSUE not in numbers
    assert set(numbers) == {6878, 7064}
    text = triage.triage_instructions(ISSUE, found)
    assert 'PR #6878 (branch `codetether/issue-6877`)' in text
    assert 'CODETETHER_TRIAGE: duplicate #<number>' in text


class TriageActivities(FakeActivities):
    def __init__(self, verdict: str):
        super().__init__(['APPROVED'])
        self.verdict = verdict
        self.triaged: list[dict] = []

    @activity.defn(name='forgejo_apply_triage')
    async def apply_triage(self, payload: dict) -> str:
        self.triaged.append(payload)
        return self.verdict

    @property
    def registered(self):
        return [*super().registered, self.apply_triage]


async def _run_issue(verdict: str) -> tuple:
    activities = TriageActivities(verdict)
    async with (
        await WorkflowEnvironment.start_time_skipping() as env,
        Worker(
            env.client,
            task_queue='forgejo-triage',
            workflows=[ForgejoAgentWorkflow],
            activities=activities.registered,
        ),
    ):
        handle = await env.client.start_workflow(
            ForgejoAgentWorkflow.run,
            ISSUE_INPUT,
            id=f'forgejo-triage-{verdict}',
            task_queue='forgejo-triage',
        )
        prepare = await wait_for_stage(handle, 'prepare')
        await complete(handle, prepare, 'prepare')
        code = await wait_for_stage(handle, 'code')
        await complete(handle, code, 'code')
        if verdict == 'proceed':
            review = await wait_for_stage(handle, 'review')
            await complete(handle, review, 'review')
        return activities, await handle.result()


@pytest.mark.asyncio
async def test_duplicate_verdict_skips_review():
    activities, result = await _run_issue('duplicate')
    assert result.status == 'completed'
    assert [r.stage for r in activities.dispatched] == ['prepare', 'code']
    assert activities.triaged[0]['issue_number'] == ISSUE
    assert activities.finalized[-1]['error_type'] == 'triage_duplicate'


@pytest.mark.asyncio
async def test_proceed_verdict_continues_to_review():
    activities, result = await _run_issue('proceed')
    assert result.status == 'completed'
    assert [r.stage for r in activities.dispatched] == [
        'prepare',
        'code',
        'review',
    ]
