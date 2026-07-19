from a2a_server.forgejo_task_response import public


def test_public_author_task_hides_reusable_session_capabilities():
    task = {
        'id': 'cttask_public',
        'session_id': 'runtime-session',
        'metadata': {
            'protocol': 'codetether.forgejo-author.v1',
            'resume_session_id': 'author-session',
            'author_provenance_id': 'ctprov_secret',
            'tenant_id': 'tenant-secret',
            'context_id': 'conversation-secret',
            'blocking_findings': 1,
        },
    }
    response = public(task)
    assert response['session_id'] is None
    assert response['metadata'] == {
        'protocol': 'codetether.forgejo-author.v1',
        'blocking_findings': 1,
    }


def test_non_protocol_task_response_is_unchanged():
    task = {'id': 'legacy', 'metadata': {'resume_session_id': 'internal'}}
    assert public(task) == task
