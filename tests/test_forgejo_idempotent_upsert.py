from pathlib import Path


EXPECTED_CLAUSES = 2


def test_verified_author_task_conflicts_do_not_reopen_existing_work():
    source = Path('a2a_server/database.py').read_text()
    assert source.count("WHERE tasks.metadata->>'protocol'") == EXPECTED_CLAUSES
    assert (
        source.count("IS DISTINCT FROM 'codetether.forgejo-author.v1'")
        == EXPECTED_CLAUSES
    )
