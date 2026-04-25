from a2a_server.github_app.mention import is_fix_request, mentions_bot


def test_mentions_bot_is_case_insensitive():
    assert mentions_bot('@CodeTether can you handle this bug?')


def test_handle_this_bug_is_actionable_issue_request():
    assert is_fix_request('@CodeTether can you handle this bug?')


def test_plain_mention_without_action_still_not_fix_request():
    assert not is_fix_request('@CodeTether thanks for the context')
