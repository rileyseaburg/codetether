from a2a_server.github_app.mention import is_fix_request, mentions_bot
from a2a_server.github_app.payload import extract_context, is_supported_event_action
from a2a_server.github_app.settings import APP_SLUG


def test_mentions_bot_is_case_insensitive():
    assert mentions_bot(f'@{APP_SLUG.title()} can you handle this bug?')


def test_handle_this_bug_is_actionable_issue_request():
    assert is_fix_request(f'@{APP_SLUG} can you handle this bug?')


def test_plain_mention_without_action_still_not_fix_request():
    assert not is_fix_request(f'@{APP_SLUG} thanks for the context')


def test_issue_opened_body_mention_extracts_context():
    payload = {
        'action': 'opened',
        'installation': {'id': 123},
        'repository': {'full_name': 'owner/repo'},
        'issue': {
            'id': 456,
            'number': 7,
            'title': 'Bug',
            'body': f'@{APP_SLUG} handle this issue',
        },
    }

    assert is_supported_event_action('issues', payload)
    context = extract_context('issues', payload)

    assert context is not None
    assert context.repo_full_name == 'owner/repo'
    assert context.installation_id == 123
    assert context.issue_number == 7
    assert context.pr_number is None
    assert context.comment_id == 456
    assert context.comment_body == f'@{APP_SLUG} handle this issue'


def test_issue_edit_only_triggers_when_mention_is_new():
    payload = {
        'action': 'edited',
        'changes': {'body': {'from': 'plain issue body'}},
        'issue': {'body': f'@{APP_SLUG} handle this issue'},
    }

    assert is_supported_event_action('issues', payload)

    payload['changes']['body']['from'] = f'@{APP_SLUG} old instructions'
    assert not is_supported_event_action('issues', payload)
