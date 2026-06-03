"""Tests for the failed-check remediation loop (issue #88).

Covers:
- Payload parsing for check_run, check_suite, workflow_run
- Recursion prevention (CodeTether-authored checks ignored)
- Idempotency / duplicate suppression
- Missing PR data handling
- Ineligible events (success, non-completed, etc.)
- Remediation prompt content
- Router-level integration
"""

import json

import pytest

from a2a_server.github_app import remediation, router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_run_payload(**overrides) -> dict:
    """Build a realistic check_run.completed webhook payload."""
    base = {
        'action': 'completed',
        'check_run': {
            'id': 42,
            'name': 'CI / tests',
            'head_sha': 'abc123def456',
            'head_branch': 'feature-branch',
            'status': 'completed',
            'conclusion': 'failure',
            'details_url': 'https://github.com/owner/repo/runs/42',
            'html_url': 'https://github.com/owner/repo/runs/42',
            'pull_requests': [{'number': 7, 'head': {'ref': 'feature-branch'}}],
            'app': {'slug': 'github-actions', 'id': 15368},
        },
        'repository': {'full_name': 'owner/repo'},
        'installation': {'id': 999},
        'sender': {'login': 'developer', 'type': 'User'},
    }
    base.update(overrides)
    return base


def _check_suite_payload(**overrides) -> dict:
    base = {
        'action': 'completed',
        'check_suite': {
            'id': 100,
            'head_sha': 'abc123def456',
            'head_branch': 'feature-branch',
            'conclusion': 'failure',
            'url': 'https://github.com/owner/repo/runs/suite/100',
            'pull_requests': [{'number': 7, 'head': {'ref': 'feature-branch'}}],
            'app': {'slug': 'github-actions', 'id': 15368},
        },
        'repository': {'full_name': 'owner/repo'},
        'installation': {'id': 999},
        'sender': {'login': 'developer', 'type': 'User'},
    }
    base.update(overrides)
    return base


def _workflow_run_payload(**overrides) -> dict:
    base = {
        'action': 'completed',
        'workflow_run': {
            'id': 200,
            'name': 'CI Pipeline',
            'head_sha': 'abc123def456',
            'head_branch': 'feature-branch',
            'conclusion': 'failure',
            'html_url': 'https://github.com/owner/repo/actions/runs/200',
            'pull_requests': [{'number': 7, 'head': {'ref': 'feature-branch'}}],
        },
        'repository': {'full_name': 'owner/repo'},
        'installation': {'id': 999},
        'sender': {'login': 'developer', 'type': 'User'},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Parsing tests — check_run
# ---------------------------------------------------------------------------

class TestParseCheckRun:
    def test_completed_failure_with_pr(self):
        ctx = remediation.parse_check_run(_check_run_payload())
        assert ctx is not None
        assert ctx.repo_full_name == 'owner/repo'
        assert ctx.installation_id == 999
        assert ctx.head_sha == 'abc123def456'
        assert ctx.check_name == 'CI / tests'
        assert ctx.conclusion == 'failure'
        assert ctx.details_url == 'https://github.com/owner/repo/runs/42'
        assert ctx.event_type == 'check_run'
        assert ctx.pr_number == 7
        assert ctx.branch == 'feature-branch'
        assert ctx.app_slug == 'github-actions'

    def test_non_completed_action_returns_none(self):
        assert remediation.parse_check_run(_check_run_payload(action='created')) is None
        assert remediation.parse_check_run(_check_run_payload(action='rerequested')) is None

    def test_success_conclusion_returns_none(self):
        payload = _check_run_payload()
        payload['check_run']['conclusion'] = 'success'
        assert remediation.parse_check_run(payload) is None

    def test_timed_out_conclusion_is_captured(self):
        payload = _check_run_payload()
        payload['check_run']['conclusion'] = 'timed_out'
        ctx = remediation.parse_check_run(payload)
        assert ctx is not None
        assert ctx.conclusion == 'timed_out'

    def test_no_pull_requests_returns_context_without_pr(self):
        payload = _check_run_payload()
        payload['check_run']['pull_requests'] = []
        ctx = remediation.parse_check_run(payload)
        assert ctx is not None
        assert ctx.pr_number is None

    def test_missing_repo_returns_none(self):
        payload = _check_run_payload()
        del payload['repository']
        assert remediation.parse_check_run(payload) is None

    def test_missing_installation_returns_none(self):
        payload = _check_run_payload()
        del payload['installation']
        assert remediation.parse_check_run(payload) is None


# ---------------------------------------------------------------------------
# Parsing tests — check_suite
# ---------------------------------------------------------------------------

class TestParseCheckSuite:
    def test_completed_failure(self):
        ctx = remediation.parse_check_suite(_check_suite_payload())
        assert ctx is not None
        assert ctx.event_type == 'check_suite'
        assert ctx.conclusion == 'failure'
        assert ctx.pr_number == 7
        assert ctx.check_name.startswith('check-suite:')

    def test_non_completed_action_returns_none(self):
        assert remediation.parse_check_suite(_check_suite_payload(action='requested')) is None

    def test_success_returns_none(self):
        payload = _check_suite_payload()
        payload['check_suite']['conclusion'] = 'success'
        assert remediation.parse_check_suite(payload) is None


# ---------------------------------------------------------------------------
# Parsing tests — workflow_run
# ---------------------------------------------------------------------------

class TestParseWorkflowRun:
    def test_completed_failure(self):
        ctx = remediation.parse_workflow_run(_workflow_run_payload())
        assert ctx is not None
        assert ctx.event_type == 'workflow_run'
        assert ctx.check_name == 'CI Pipeline'
        assert ctx.head_sha == 'abc123def456'
        assert ctx.pr_number == 7
        assert ctx.branch == 'feature-branch'

    def test_non_completed_returns_none(self):
        assert remediation.parse_workflow_run(_workflow_run_payload(action='requested')) is None

    def test_success_returns_none(self):
        payload = _workflow_run_payload()
        payload['workflow_run']['conclusion'] = 'success'
        assert remediation.parse_workflow_run(payload) is None

    def test_no_pull_requests(self):
        payload = _workflow_run_payload()
        del payload['workflow_run']['pull_requests']
        ctx = remediation.parse_workflow_run(payload)
        assert ctx is not None
        assert ctx.pr_number is None


# ---------------------------------------------------------------------------
# normalize_check_event dispatcher
# ---------------------------------------------------------------------------

class TestNormalizeCheckEvent:
    def test_dispatches_check_run(self):
        ctx = remediation.normalize_check_event('check_run', _check_run_payload())
        assert ctx is not None
        assert ctx.event_type == 'check_run'

    def test_dispatches_check_suite(self):
        ctx = remediation.normalize_check_event('check_suite', _check_suite_payload())
        assert ctx is not None
        assert ctx.event_type == 'check_suite'

    def test_dispatches_workflow_run(self):
        ctx = remediation.normalize_check_event('workflow_run', _workflow_run_payload())
        assert ctx is not None
        assert ctx.event_type == 'workflow_run'

    def test_unknown_event_returns_none(self):
        assert remediation.normalize_check_event('push', {}) is None
        assert remediation.normalize_check_event('pull_request', {}) is None


# ---------------------------------------------------------------------------
# Recursion prevention
# ---------------------------------------------------------------------------

class TestRecursionPrevention:
    def setup_method(self):
        remediation.reset_seen_keys()

    def test_codetether_slug_check_is_ignored(self):
        payload = _check_run_payload()
        payload['check_run']['name'] = 'CodeTether / code'
        payload['check_run']['app'] = {'slug': 'codetether', 'id': 99999}
        ctx = remediation.parse_check_run(payload)
        assert ctx is not None
        assert remediation._is_codetether_authored(ctx) is True

    def test_codetether_name_prefix_is_ignored(self):
        payload = _check_run_payload()
        payload['check_run']['name'] = 'CodeTether / review'
        # No app slug set — name prefix match
        payload['check_run']['app'] = {}
        ctx = remediation.parse_check_run(payload)
        assert ctx is not None
        assert remediation._is_codetether_authored(ctx) is True

    def test_app_slug_prefix_match(self):
        payload = _check_run_payload()
        payload['check_run']['name'] = 'Some random check'
        payload['check_run']['app'] = {'slug': 'codetether', 'id': 1}
        ctx = remediation.parse_check_run(payload)
        assert ctx is not None
        assert remediation._is_codetether_authored(ctx) is True

    def test_third_party_check_is_not_ignored(self):
        payload = _check_run_payload()
        # Default payload uses 'github-actions' slug and 'CI / tests' name
        ctx = remediation.parse_check_run(payload)
        assert ctx is not None
        assert remediation._is_codetether_authored(ctx) is False


# ---------------------------------------------------------------------------
# Idempotency / duplicate suppression
# ---------------------------------------------------------------------------

class TestIdempotency:
    def setup_method(self):
        remediation.reset_seen_keys()

    def test_first_delivery_is_not_duplicate(self):
        ctx = remediation.parse_check_run(_check_run_payload())
        assert remediation.is_duplicate(ctx) is False

    def test_second_delivery_is_duplicate(self):
        ctx = remediation.parse_check_run(_check_run_payload())
        remediation.mark_seen(ctx)
        assert remediation.is_duplicate(ctx) is True

    def test_different_sha_is_not_duplicate(self):
        ctx1 = remediation.parse_check_run(_check_run_payload())
        remediation.mark_seen(ctx1)
        ctx2 = remediation.parse_check_run(_check_run_payload(
            check_run={
                **_check_run_payload()['check_run'],
                'head_sha': 'different-sha-999',
            },
        ))
        assert remediation.is_duplicate(ctx2) is False

    def test_different_check_name_is_not_duplicate(self):
        ctx1 = remediation.parse_check_run(_check_run_payload())
        remediation.mark_seen(ctx1)
        payload2 = _check_run_payload()
        payload2['check_run']['name'] = 'CI / lint'
        ctx2 = remediation.parse_check_run(payload2)
        assert remediation.is_duplicate(ctx2) is False

    def test_dedup_key_is_stable(self):
        ctx = remediation.parse_check_run(_check_run_payload())
        assert ctx.dedup_key == ctx.dedup_key  # idempotent
        assert len(ctx.dedup_key) == 40


# ---------------------------------------------------------------------------
# Worker prompt
# ---------------------------------------------------------------------------

class TestRemediationPrompt:
    def test_prompt_contains_check_details(self):
        ctx = remediation.parse_check_run(_check_run_payload())
        prompt = remediation.remediation_prompt(ctx)
        assert 'CI / tests' in prompt
        assert 'owner/repo' in prompt
        assert 'abc123def456' in prompt
        assert 'failure' in prompt
        assert '#7' in prompt
        assert 'feature-branch' in prompt

    def test_prompt_contains_actionable_instructions(self):
        ctx = remediation.parse_check_run(_check_run_payload())
        prompt = remediation.remediation_prompt(ctx)
        assert 'Fetch the logs' in prompt
        assert 'Patch the code' in prompt
        assert 'Commit and push' in prompt
        assert 'Do NOT merge' in prompt
        assert 'Do NOT force-push' in prompt

    def test_prompt_without_pr(self):
        payload = _check_run_payload()
        payload['check_run']['pull_requests'] = []
        ctx = remediation.parse_check_run(payload)
        prompt = remediation.remediation_prompt(ctx)
        assert 'Pull request' not in prompt


# ---------------------------------------------------------------------------
# Router-level integration
# ---------------------------------------------------------------------------

class TestRouterIntegration:
    def setup_method(self):
        remediation.reset_seen_keys()

    @pytest.mark.asyncio
    async def test_check_run_failure_queues_task(self, monkeypatch):
        queued = []

        async def fake_queue(ctx):
            queued.append(ctx)
            return 'rem-task-1'

        async def fake_resolve():
            return {}

        async def fake_verify(signature, body):
            pass

        monkeypatch.setattr(router, 'verify_signature', fake_verify)
        monkeypatch.setattr(router, '_queue_remediation_task', fake_queue)

        class FakeRequest:
            headers = {
                'X-Hub-Signature-256': 'sha256=test',
                'X-GitHub-Event': 'check_run',
            }
            async def body(self):
                return json.dumps(_check_run_payload()).encode()

        result = await router.handle_github_webhook(FakeRequest())

        assert result['accepted'] is True
        assert result['remediation_task_id'] == 'rem-task-1'
        assert result['check_name'] == 'CI / tests'
        assert result['pr_number'] == 7
        assert len(queued) == 1

    @pytest.mark.asyncio
    async def test_codetether_check_is_ignored(self, monkeypatch):
        async def fail_queue(ctx):
            raise AssertionError('should not queue self-authored check')

        async def fake_verify(signature, body):
            pass

        monkeypatch.setattr(router, 'verify_signature', fake_verify)
        monkeypatch.setattr(router, '_queue_remediation_task', fail_queue)

        payload = _check_run_payload()
        payload['check_run']['name'] = 'CodeTether / code'
        payload['check_run']['app'] = {'slug': 'codetether', 'id': 99999}

        class FakeRequest:
            headers = {
                'X-Hub-Signature-256': 'sha256=test',
                'X-GitHub-Event': 'check_run',
            }
            async def body(self):
                return json.dumps(payload).encode()

        result = await router.handle_github_webhook(FakeRequest())
        assert result['ignored'] is True
        assert result['reason'] == 'self-authored-check'

    @pytest.mark.asyncio
    async def test_duplicate_delivery_suppressed(self, monkeypatch):
        queue_count = 0

        async def fake_queue(ctx):
            nonlocal queue_count
            queue_count += 1
            return f'rem-task-{queue_count}'

        async def fake_verify(signature, body):
            pass

        monkeypatch.setattr(router, 'verify_signature', fake_verify)
        monkeypatch.setattr(router, '_queue_remediation_task', fake_queue)

        payload = _check_run_payload()

        class FakeRequest:
            headers = {
                'X-Hub-Signature-256': 'sha256=test',
                'X-GitHub-Event': 'check_run',
            }
            async def body(self):
                return json.dumps(payload).encode()

        result1 = await router.handle_github_webhook(FakeRequest())
        assert result1['accepted'] is True

        result2 = await router.handle_github_webhook(FakeRequest())
        assert result2['ignored'] is True
        assert result2['reason'] == 'duplicate-suppressed'
        assert queue_count == 1

    @pytest.mark.asyncio
    async def test_no_pr_returns_ignored(self, monkeypatch):
        async def fail_queue(ctx):
            raise AssertionError('should not queue without PR')

        async def fake_verify(signature, body):
            pass

        monkeypatch.setattr(router, 'verify_signature', fake_verify)
        monkeypatch.setattr(router, '_queue_remediation_task', fail_queue)

        payload = _check_run_payload()
        payload['check_run']['pull_requests'] = []

        class FakeRequest:
            headers = {
                'X-Hub-Signature-256': 'sha256=test',
                'X-GitHub-Event': 'check_run',
            }
            async def body(self):
                return json.dumps(payload).encode()

        result = await router.handle_github_webhook(FakeRequest())
        assert result['ignored'] is True
        assert result['reason'] == 'no-associated-pr'

    @pytest.mark.asyncio
    async def test_successful_check_run_not_queued(self, monkeypatch):
        async def fail_queue(ctx):
            raise AssertionError('should not queue successful checks')

        async def fake_verify(signature, body):
            pass

        monkeypatch.setattr(router, 'verify_signature', fake_verify)
        monkeypatch.setattr(router, '_queue_remediation_task', fail_queue)

        payload = _check_run_payload()
        payload['check_run']['conclusion'] = 'success'

        class FakeRequest:
            headers = {
                'X-Hub-Signature-256': 'sha256=test',
                'X-GitHub-Event': 'check_run',
            }
            async def body(self):
                return json.dumps(payload).encode()

        result = await router.handle_github_webhook(FakeRequest())
        assert result['ignored'] is True
        assert result['reason'] == 'ineligible-check-event'

    @pytest.mark.asyncio
    async def test_check_suite_failure_queues_task(self, monkeypatch):
        queued = []

        async def fake_queue(ctx):
            queued.append(ctx)
            return 'rem-suite-1'

        async def fake_verify(signature, body):
            pass

        monkeypatch.setattr(router, 'verify_signature', fake_verify)
        monkeypatch.setattr(router, '_queue_remediation_task', fake_queue)

        class FakeRequest:
            headers = {
                'X-Hub-Signature-256': 'sha256=test',
                'X-GitHub-Event': 'check_suite',
            }
            async def body(self):
                return json.dumps(_check_suite_payload()).encode()

        result = await router.handle_github_webhook(FakeRequest())
        assert result['accepted'] is True
        assert result['pr_number'] == 7
        assert len(queued) == 1

    @pytest.mark.asyncio
    async def test_workflow_run_failure_queues_task(self, monkeypatch):
        queued = []

        async def fake_queue(ctx):
            queued.append(ctx)
            return 'rem-wf-1'

        async def fake_verify(signature, body):
            pass

        monkeypatch.setattr(router, 'verify_signature', fake_verify)
        monkeypatch.setattr(router, '_queue_remediation_task', fake_queue)

        class FakeRequest:
            headers = {
                'X-Hub-Signature-256': 'sha256=test',
                'X-GitHub-Event': 'workflow_run',
            }
            async def body(self):
                return json.dumps(_workflow_run_payload()).encode()

        result = await router.handle_github_webhook(FakeRequest())
        assert result['accepted'] is True
        assert result['check_name'] == 'CI Pipeline'
        assert len(queued) == 1

    @pytest.mark.asyncio
    async def test_non_check_event_goes_to_mention_flow(self, monkeypatch):
        """Non-remediation events should still be handled by the existing mention flow."""
        app_slug = router.APP_SLUG

        async def fake_verify(signature, body):
            pass

        async def fail_handle_remediation(event_name, payload):
            raise AssertionError('remediation should not be called for issue_comment')

        monkeypatch.setattr(router, 'verify_signature', fake_verify)

        class FakeRequest:
            headers = {
                'X-Hub-Signature-256': 'sha256=test',
                'X-GitHub-Event': 'issue_comment',
            }
            async def body(self):
                return json.dumps({
                    'action': 'created',
                    'installation': {'id': 123},
                    'repository': {'full_name': 'owner/repo'},
                    'sender': {'login': 'user', 'type': 'User'},
                    'issue': {'number': 7},
                    'comment': {
                        'id': 99,
                        'user': {'login': 'user', 'type': 'User'},
                        'body': f'@{app_slug} fix this please',
                    },
                }).encode()

        # This should reach the mention flow, not the remediation flow
        result = await router.handle_github_webhook(FakeRequest())
        # It won't be accepted because is_fix_request and handle_fix_request are not patched,
        # but it definitely should not hit the remediation path
        assert 'remediation' not in str(result).lower() or result.get('ignored') is True
