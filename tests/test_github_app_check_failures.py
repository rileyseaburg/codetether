from a2a_server.github_app.check_failures import (
    check_output_excerpt,
    context_from_failed_check,
    should_remediate_failed_check,
)
from a2a_server.github_app.settings import APP_SLUG


def _payload(
    conclusion='failure', app_slug='github-actions', prs=None, output=None
):
    return {
        'action': 'completed',
        'installation': {'id': 123},
        'repository': {'full_name': 'owner/repo'},
        'check_run': {
            'id': 777,
            'name': 'Lint Code Base',
            'conclusion': conclusion,
            'details_url': 'https://github.com/owner/repo/actions/runs/1/job/2',
            'head_sha': 'abc123',
            'app': {'slug': app_slug, 'name': app_slug},
            'output': output or {},
            'pull_requests': prs if prs is not None else [{'number': 87}],
        },
    }


def test_failed_check_run_is_remediable_context():
    payload = _payload()

    assert should_remediate_failed_check('check_run', payload)

    context = context_from_failed_check('check_run', payload)
    assert context.repo_full_name == 'owner/repo'
    assert context.installation_id == 123
    assert context.issue_number == 87
    assert context.pr_number == 87
    assert f'@{APP_SLUG} fix the failing PR check' in context.comment_body
    assert 'Check: Lint Code Base' in context.comment_body
    assert (
        'Details URL: https://github.com/owner/repo/actions/runs/1/job/2'
        in context.comment_body
    )


def test_failed_check_context_includes_output_excerpt():
    payload = _payload(
        output={
            'summary': '[WebServer] [listMedia] Error: column "url" does not exist'
        }
    )

    context = context_from_failed_check('check_run', payload)

    assert 'Check output excerpt:' in context.comment_body
    assert 'column "url" does not exist' in context.comment_body


def test_check_output_excerpt_truncates_large_logs():
    excerpt = check_output_excerpt({'output': {'text': 'x' * 5000}}, limit=20)

    assert excerpt == 'x' * 20 + '\n… [truncated]'


def test_success_check_is_not_remediable():
    assert not should_remediate_failed_check(
        'check_run', _payload(conclusion='success')
    )


def test_codetether_check_is_not_remediable():
    assert not should_remediate_failed_check(
        'check_run', _payload(app_slug=APP_SLUG)
    )


def test_failed_check_without_pr_is_not_remediable():
    assert not should_remediate_failed_check('check_run', _payload(prs=[]))
