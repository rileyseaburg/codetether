"""Zero-trust: later GitHub App stages verify against the recorded session.

Before, ``policy_decision`` derived its "expected" origin hash and taints from
the provenance it was verifying, so origin tampering and taint stripping could
never be detected. Now the expectation comes from the prior stage's task.
"""

import os


os.environ.setdefault(
    'DATABASE_URL', 'postgresql://test:test@localhost:5432/test'
)

from a2a_server.github_app import issue_review_task


PR = {'number': 77, 'head': {'sha': 'abc123'}, 'base': {'sha': 'def456'}}


def _provenance(action, *, pr=PR, repo='acme/widgets'):
    return issue_review_task.issue_pr_provenance(
        repo=repo,
        issue_number=12,
        branch='codetether/issue-12',
        pr=pr,
        installation_id=123,
        action=action,
    )


def _review_task(provenance):
    return {'metadata': {'codetether_provenance': provenance}}


def _session():
    review = _review_task(_provenance('github:review_pr'))
    return issue_review_task.session_state_from_task(review)


def test_merge_matching_session_allowed():
    decision = issue_review_task.policy_decision(
        _provenance('github:merge_pr'),
        'github:merge_pr',
        _session(),
        require_session=True,
    )
    assert decision['allowed'] is True


def test_merge_for_different_pr_denied():
    other = _provenance('github:merge_pr', repo='attacker/repo')
    decision = issue_review_task.policy_decision(
        other, 'github:merge_pr', _session(), require_session=True
    )
    assert decision['allowed'] is False
    assert 'origin intent hash mismatch' in decision['provenance']['failures']


def test_taint_stripping_detected():
    provenance = _provenance('github:merge_pr')
    provenance['ap_inputs'] = provenance['ap_inputs'][:1]
    decision = issue_review_task.policy_decision(
        provenance, 'github:merge_pr', _session(), require_session=True
    )
    assert decision['allowed'] is False
    assert 'taint stripping detected' in decision['provenance']['failures']


def test_missing_session_denied_when_required():
    decision = issue_review_task.policy_decision(
        _provenance('github:merge_pr'),
        'github:merge_pr',
        None,
        require_session=True,
    )
    assert decision['allowed'] is False


def test_first_stage_without_session_allowed():
    decision = issue_review_task.policy_decision(
        _provenance('github:review_pr'), 'github:review_pr'
    )
    assert decision['allowed'] is True


def test_session_state_absent_without_recorded_provenance():
    assert issue_review_task.session_state_from_task({'metadata': {}}) is None


def test_origin_is_stable_across_stages():
    review = _provenance('github:review_pr')['ap_origin']['intent_hash']
    merge = _provenance('github:merge_pr')['ap_origin']['intent_hash']
    assert review == merge
