from a2a_server.github_app.mention import is_fix_request, mentions_bot
from a2a_server.github_app.settings import APP_SLUG


def test_mentions_bot_is_case_insensitive():
    assert mentions_bot(f'@{APP_SLUG.title()} can you handle this bug?')


def test_handle_this_bug_is_actionable_issue_request():
    assert is_fix_request(f'@{APP_SLUG} can you handle this bug?')


def test_plain_mention_without_action_still_not_fix_request():
    assert not is_fix_request(f'@{APP_SLUG} thanks for the context')
