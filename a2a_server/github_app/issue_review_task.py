"""Review and merge task creation for issue-driven GitHub App PRs."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)

from ..provenance import verify_provenance
from .settings import AUTO_MERGE_ENABLED, MERGE_METHOD, MODEL_REF

DEFAULT_TASK_TIMEOUT = 604800  # 7 days

CODETETHER_PERSONALITY = {
    'name': 'CodeTether',
    'avatar': 'codetether-avatar',
    'tone': 'concise, safety-first, provenance-aware',
}


def issue_pr_provenance(
    *,
    repo: str,
    issue_number: int,
    branch: str,
    pr: dict[str, Any],
    installation_id: int | str | None,
    action: str,
    parent_task_id: str | None = None,
) -> dict[str, Any]:
    """Build an APF-compatible provenance envelope for GitHub issue automation.

    The local provenance verifier is intentionally deterministic. We bind the
    delegated action to the exact repo, issue, PR, branch, and head SHA and carry
    that envelope through the reviewer/merger tasks.
    """
    pr_number = int(pr.get('number') or 0)
    head = pr.get('head') or {}
    base = pr.get('base') or {}
    head_sha = str(head.get('sha') or '')
    base_sha = str(base.get('sha') or '')
    intent_material = {
        'repo': repo,
        'issue_number': issue_number,
        'pr_number': pr_number,
        'branch': branch,
        'head_sha': head_sha,
        'action': action,
    }
    intent_hash = hashlib.sha256(
        json.dumps(intent_material, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()
    return {
        'ap_origin': {
            'system': 'codetether-github-app',
            'intent_hash': intent_hash,
            'intent': f'{action} issue #{issue_number} PR #{pr_number} in {repo}',
            'trigger': 'github-issue-automation',
        },
        'ap_inputs': [
            {
                'id': f'github:{repo}#issue-{issue_number}',
                'source': 'github-webhook',
                'sensitivity': 'repository-write',
                'applied_at_turn': 0,
            },
            {
                'id': f'github:{repo}#pr-{pr_number}@{head_sha}',
                'source': 'github-rest',
                'sensitivity': 'repository-write',
                'applied_at_turn': 1,
            },
        ],
        'ap_delegation': {
            'chain': [
                {
                    'actor': 'codetether-github-app',
                    'capability': {
                        'root': False,
                        'operations': ['github:review_pr', 'github:request_changes', 'github:merge_pr'],
                        'spawn': {'max_depth': 2, 'max_fanout': 2},
                        'budget': {'github_api_calls': 200},
                    },
                },
                {
                    'actor': 'codetether-merge-steward' if action == 'github:merge_pr' else 'codetether-reviewer',
                    'capability': {
                        'root': False,
                        'operations': [action],
                        'spawn': {'max_depth': 1, 'max_fanout': 1},
                        'budget': {'github_api_calls': 100},
                    },
                },
            ]
        },
        'ap_runtime': {
            'service': 'a2a-server',
            'workflow': 'github-issue-review-merge',
            'parent_task_id': parent_task_id,
        },
        'ap_output': {
            'repo': repo,
            'issue_number': issue_number,
            'pr_number': pr_number,
            'branch': branch,
            'head_sha': head_sha,
            'base_sha': base_sha,
            'installation_id': str(installation_id or ''),
            'action': action,
        },
    }


def provenance_footer(provenance: dict[str, Any], *, action: str) -> str:
    """Render a compact GitHub-visible provenance footer."""
    output = provenance.get('ap_output') or {}
    origin = provenance.get('ap_origin') or {}
    return (
        "\n\n---\n"
        "Automation provenance:\n"
        f"- CodeTether workflow: `github-issue-review-merge`\n"
        f"- Action: `{action}`\n"
        f"- Intent hash: `{origin.get('intent_hash', '')}`\n"
        f"- PR: `#{output.get('pr_number', '')}`\n"
        f"- Head SHA: `{output.get('head_sha', '')}`\n"
        f"- Personality/avatar: `{CODETETHER_PERSONALITY['name']}` / `{CODETETHER_PERSONALITY['avatar']}`"
    )


def policy_decision(provenance: dict[str, Any], action: str) -> dict[str, Any]:
    """Evaluate the local provenance gate for a GitHub automation action."""
    resource = {
        'session_origin_intent_hash': (provenance.get('ap_origin') or {}).get('intent_hash'),
        'session_taints': provenance.get('ap_inputs') or [],
    }
    decision = verify_provenance(provenance, action, resource)
    return {
        'allowed': decision.allowed_by_provenance and not decision.partial,
        'provenance': decision.as_dict(),
        'action': action,
    }


def _repo_parts(repo_full_name: str) -> tuple[str, str]:
    owner, _, repo = repo_full_name.partition('/')
    return owner, repo


def _failure_decision(action: str, failures: list[str]) -> dict[str, Any]:
    return {
        'allowed': False,
        'action': action,
        'provenance': {
            'complete': True,
            'dimensions': {},
            'missing_dimensions': [],
            'failures': failures,
            'partial': False,
        },
    }


def _format_blockers(blockers: list[str]) -> str:
    return '\n'.join(f'- {blocker}' for blocker in blockers[:12])


async def record_automation_decision(
    *,
    provenance: dict[str, Any],
    decision: dict[str, Any],
    task_id: str | None = None,
    github_request_id: str | None = None,
    github_status: int | None = None,
) -> None:
    """Persist a GitHub automation policy/provenance decision if the DB is available."""
    try:
        from .. import database as db

        pool = await db.get_pool()
        if not pool:
            return
        output = provenance.get('ap_output') or {}
        owner, repo_name = _repo_parts(str(output.get('repo') or ''))
        policy = decision.get('provenance') or {}
        personality = dict(CODETETHER_PERSONALITY)
        policy_decision_value = 'allow' if decision.get('allowed') else 'deny'
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO github_automation_decisions (
                    id, action, owner, repo, pull_number, issue_number,
                    branch_name, head_sha, base_sha, installation_id, actor,
                    personality, policy_decision, policy_reasons, provenance,
                    task_id, github_request_id, github_status
                ) VALUES (
                    $1, $2, $3, $4, $5, $6,
                    $7, $8, $9, NULLIF($10, '')::BIGINT, $11,
                    $12::jsonb, $13, $14::jsonb, $15::jsonb,
                    $16, $17, $18
                )
                """,
                str(uuid.uuid4()),
                str(decision.get('action') or output.get('action') or ''),
                owner,
                repo_name,
                int(output.get('pr_number') or 0) or None,
                int(output.get('issue_number') or 0) or None,
                str(output.get('branch') or ''),
                str(output.get('head_sha') or ''),
                str(output.get('base_sha') or ''),
                str(output.get('installation_id') or ''),
                str(((provenance.get('ap_delegation') or {}).get('chain') or [{}])[-1].get('actor') or 'codetether-github-app'),
                json.dumps(personality),
                policy_decision_value,
                json.dumps(policy.get('failures') or []),
                json.dumps(provenance),
                task_id,
                github_request_id,
                github_status,
            )
    except Exception as exc:
        logger.warning('Failed to record GitHub automation decision: %s', exc)


def reviewer_allows_merge(review_task: dict[str, Any]) -> bool:
    """Return True only when the reviewer explicitly approved the PR."""
    result = str(review_task.get('result') or '')
    upper_result = result.upper()

    verdict_matches = re.findall(
        r'(?:FINAL\s+(?:VERDICT|RESPONSE|STATUS)|VERDICT|STATUS)\s*:?\s*\**\s*'
        r'(APPROVED|CHANGES_REQUESTED|BLOCKED)\b',
        upper_result,
    )
    if verdict_matches:
        return verdict_matches[-1] == 'APPROVED'

    line_verdicts = [
        match.group(1)
        for match in re.finditer(
            r'^\s*\**\s*(APPROVED|CHANGES_REQUESTED|BLOCKED)\b',
            upper_result,
            flags=re.MULTILINE,
        )
    ]
    if line_verdicts:
        return line_verdicts[-1] == 'APPROVED'

    if 'CHANGES_REQUESTED' in upper_result or re.search(r'\bBLOCKED\s*:', upper_result):
        return False
    return 'APPROVED' in upper_result


def feedback_blockers_from_pull_request(pull_request: dict[str, Any] | None) -> list[str]:
    """Return review-feedback blockers from GitHub GraphQL pull request state."""
    if not pull_request:
        return ['Pull request was not found in GitHub GraphQL response']

    blockers: list[str] = []
    if pull_request.get('state') != 'OPEN':
        blockers.append(f"PR is not open: {pull_request.get('state') or 'unknown'}")
    if pull_request.get('isDraft'):
        blockers.append('PR is still marked as draft')

    review_decision = str(pull_request.get('reviewDecision') or '').upper()
    if review_decision == 'CHANGES_REQUESTED':
        blockers.append('Latest GitHub review decision is CHANGES_REQUESTED')

    threads = (pull_request.get('reviewThreads') or {}).get('nodes') or []
    for thread in threads:
        if thread.get('isResolved') or thread.get('isOutdated'):
            continue
        comments = (thread.get('comments') or {}).get('nodes') or []
        latest = comments[-1] if comments else {}
        author = ((latest.get('author') or {}).get('login') or 'unknown').strip()
        path = str(latest.get('path') or thread.get('path') or '').strip()
        line = latest.get('line') or thread.get('line')
        location = f'{path}:{line}' if path and line else path or 'unknown location'
        blockers.append(f'Unresolved review thread at {location} by {author}')

    page_info = (pull_request.get('reviewThreads') or {}).get('pageInfo') or {}
    if page_info.get('hasNextPage'):
        blockers.append('More than 100 review threads exist; refusing to merge without a complete review-thread scan')

    return blockers


async def review_feedback_status(repo: str, pr_number: int, token: str) -> dict[str, Any]:
    """Fetch GitHub review-thread state and summarize whether feedback is addressed."""
    from .auth import github_graphql

    owner, repo_name = _repo_parts(repo)
    query = """
    query CodeTetherPullRequestFeedback($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        pullRequest(number: $number) {
          state
          isDraft
          reviewDecision
          mergeable
          reviewThreads(first: 100) {
            pageInfo { hasNextPage }
            nodes {
              isResolved
              isOutdated
              path
              line
              comments(first: 20) {
                nodes {
                  author { login }
                  body
                  path
                  line
                }
              }
            }
          }
        }
      }
    }
    """
    data = await github_graphql(
        query,
        {'owner': owner, 'name': repo_name, 'number': pr_number},
        token,
    )
    pull_request = ((data.get('repository') or {}).get('pullRequest') or None)
    blockers = feedback_blockers_from_pull_request(pull_request)
    return {
        'feedback_addressed': not blockers,
        'blockers': blockers,
        'pull_request': pull_request,
    }


def choose_merge_method(repo: dict[str, Any]) -> str | None:
    """Choose a merge method allowed by repository settings."""
    requested = MERGE_METHOD
    allowed_methods = {
        'merge': bool(repo.get('allow_merge_commit', True)),
        'squash': bool(repo.get('allow_squash_merge', True)),
        'rebase': bool(repo.get('allow_rebase_merge', True)),
    }
    if requested:
        return requested if allowed_methods.get(requested, False) else None
    for method in ('squash', 'rebase', 'merge'):
        if allowed_methods.get(method, False):
            return method
    return None


def review_prompt(repo: str, issue_number: int, branch: str, pr: dict[str, Any], provenance: dict[str, Any]) -> str:
    pr_number = pr.get('number')
    pr_url = pr.get('html_url') or f'https://github.com/{repo}/pull/{pr_number}'
    footer = provenance_footer(provenance, action='github:review_pr')
    return f"""You are the CodeTether reviewer agent for issue #{issue_number} in {repo}.

Review PR #{pr_number}: {pr_url}
Branch: {branch}
Head SHA: {(pr.get('head') or {}).get('sha', '')}

Personality/avatar: {CODETETHER_PERSONALITY['name']} using {CODETETHER_PERSONALITY['avatar']} — concise, safety-first, provenance-aware.

End-to-end responsibilities:
1. Fetch the PR branch and inspect the diff.
2. Run the smallest relevant validation for the changed files.
3. Do not approve your own unsafe work. If tests fail, scope drifts, secrets appear, or provenance does not match the current head SHA, request changes with clear remediation.
4. If the PR is safe, leave an approving review or success comment.
5. Include this exact provenance footer in any GitHub review/comment you create:{footer}

Final response must state one of: APPROVED, CHANGES_REQUESTED, or BLOCKED, plus the PR URL and validation summary."""


def merge_prompt(repo: str, issue_number: int, branch: str, pr: dict[str, Any], provenance: dict[str, Any]) -> str:
    pr_number = pr.get('number')
    pr_url = pr.get('html_url') or f'https://github.com/{repo}/pull/{pr_number}'
    footer = provenance_footer(provenance, action='github:merge_pr')
    return f"""You are the CodeTether merge steward for issue #{issue_number} in {repo}.

Target PR #{pr_number}: {pr_url}
Branch: {branch}
Expected head SHA: {(pr.get('head') or {}).get('sha', '')}

Personality/avatar: {CODETETHER_PERSONALITY['name']} using {CODETETHER_PERSONALITY['avatar']} — concise, safety-first, provenance-aware.

Before merging, enforce these policy gates with fresh GitHub state:
- PR is open and current head SHA exactly matches the expected head SHA above.
- Required checks are green or branch protection reports mergeable.
- There are no unresolved requested-changes reviews.
- The diff remains scoped to issue #{issue_number}; no secrets or destructive changes.
- CodeTether provenance footer is present on the review/comment trail or you add a status comment with it.
- Never force-push or bypass branch protection.

If every gate passes, merge the PR using the repository's normal merge method. If any gate fails, do not merge; comment with the blocked reason and final response BLOCKED.{footer}

Final response must state MERGED or BLOCKED, plus the PR URL and policy-gate summary."""


async def create_issue_review_task(
    *,
    workspace_id: str,
    repo: str,
    issue_number: int,
    branch: str,
    pr: dict[str, Any],
    github_issue_url: str | None,
    github_installation_id: int | str | None,
    parent_task_id: str | None = None,
    target_worker_id: str | None = None,
) -> str | None:
    """Queue a reviewer task for an issue PR if provenance policy allows it."""
    from ..persistent_worker_pool import create_and_dispatch_task

    provenance = issue_pr_provenance(
        repo=repo,
        issue_number=issue_number,
        branch=branch,
        pr=pr,
        installation_id=github_installation_id,
        action='github:review_pr',
        parent_task_id=parent_task_id,
    )
    decision = policy_decision(provenance, 'github:review_pr')
    if not decision['allowed']:
        await record_automation_decision(provenance=provenance, decision=decision, task_id=parent_task_id)
        return None

    metadata = {
        'workspace_id': workspace_id,
        'source': 'github-app',
        'workflow_stage': 'review',
        'repo': repo,
        'issue_number': issue_number,
        'pr_number': pr.get('number'),
        'branch_name': branch,
        'pr_head_sha': (pr.get('head') or {}).get('sha'),
        'github_issue_url': github_issue_url,
        'github_installation_id': github_installation_id,
        'worker_personality': 'reviewer',
        'personality': CODETETHER_PERSONALITY,
        'codetether_provenance': provenance,
        'policy_decision': decision,
        'post_review_task': {
            'title': f'Merge issue PR #{pr.get("number")}',
            'agent_type': 'merge',
        },
    }
    task_id = await create_and_dispatch_task(
        workspace_id=workspace_id,
        title=f'Review issue PR #{pr.get("number")}',
        prompt=review_prompt(repo, issue_number, branch, pr, provenance),
        agent_type='review',
        model_ref=MODEL_REF,
        metadata=metadata,
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
        github_issue_url=github_issue_url,
    )
    await record_automation_decision(provenance=provenance, decision=decision, task_id=task_id)
    return task_id


async def create_issue_merge_task(
    *,
    review_task: dict[str, Any],
    token: str,
) -> str | None:
    """Merge an approved issue/PR branch after GitHub feedback gates pass."""
    from ..persistent_worker_pool import create_and_dispatch_task
    from .auth import github_json
    from .watch import post_issue_comment

    if not reviewer_allows_merge(review_task):
        return None

    metadata = review_task.get('metadata') or {}
    repo = str(metadata.get('repo') or '')
    issue_number = int(metadata.get('issue_number') or 0)
    pr_number = int(metadata.get('pr_number') or 0)
    branch = str(metadata.get('branch_name') or '')
    workspace_id = str(metadata.get('workspace_id') or '')
    if not (repo and issue_number and pr_number and branch and workspace_id):
        return None

    pr = await github_json('GET', f'/repos/{repo}/pulls/{pr_number}', token)
    expected_sha = str(metadata.get('pr_head_sha') or '')
    current_sha = str((pr.get('head') or {}).get('sha') or '')
    parent_task_id = str(review_task.get('id') or '')
    if expected_sha and current_sha != expected_sha:
        stale_provenance = issue_pr_provenance(
            repo=repo,
            issue_number=issue_number,
            branch=branch,
            pr=pr,
            installation_id=metadata.get('github_installation_id'),
            action='github:merge_pr',
            parent_task_id=parent_task_id,
        )
        failures = [f'PR head SHA changed: expected {expected_sha}, got {current_sha}']
        await record_automation_decision(
            provenance=stale_provenance,
            decision=_failure_decision('github:merge_pr', failures),
            task_id=parent_task_id,
        )
        await post_issue_comment(
            repo,
            pr_number,
            token,
            "## 🛠️ CodeTether Auto-Merge\n\n"
            "Blocked because the PR changed after the approved review.\n\n"
            f"{_format_blockers(failures)}",
        )
        return None

    provenance = issue_pr_provenance(
        repo=repo,
        issue_number=issue_number,
        branch=branch,
        pr=pr,
        installation_id=metadata.get('github_installation_id'),
        action='github:merge_pr',
        parent_task_id=parent_task_id,
    )
    decision = policy_decision(provenance, 'github:merge_pr')
    if not decision['allowed']:
        await record_automation_decision(
            provenance=provenance,
            decision=decision,
            task_id=parent_task_id,
        )
        return None

    feedback_status = await review_feedback_status(repo, pr_number, token)
    if not feedback_status['feedback_addressed']:
        failures = list(feedback_status.get('blockers') or ['GitHub review feedback is not fully addressed'])
        await record_automation_decision(
            provenance=provenance,
            decision=_failure_decision('github:merge_pr', failures),
            task_id=parent_task_id,
        )
        await post_issue_comment(
            repo,
            pr_number,
            token,
            "## 🛠️ CodeTether Auto-Merge\n\n"
            "Blocked because review feedback is not fully addressed.\n\n"
            f"{_format_blockers(failures)}",
        )
        return None

    merge_metadata = dict(metadata)
    merge_metadata.update({
        'workflow_stage': 'merge',
        'worker_personality': 'merge-steward',
        'codetether_provenance': provenance,
        'policy_decision': decision,
        'pr_head_sha': current_sha,
    })

    if AUTO_MERGE_ENABLED:
        repo_info = await github_json('GET', f'/repos/{repo}', token)
        merge_method = choose_merge_method(repo_info)
        if not merge_method:
            failures = ['Repository does not allow merge, squash, or rebase merging for this GitHub App flow']
            await record_automation_decision(
                provenance=provenance,
                decision=_failure_decision('github:merge_pr', failures),
                task_id=parent_task_id,
            )
            await post_issue_comment(
                repo,
                pr_number,
                token,
                "## 🛠️ CodeTether Auto-Merge\n\n"
                "Blocked because no allowed repository merge method is available.\n\n"
                f"{_format_blockers(failures)}",
            )
            return None

        try:
            merge_result = await github_json(
                'PUT',
                f'/repos/{repo}/pulls/{pr_number}/merge',
                token,
                {
                    'commit_title': f'Merge PR #{pr_number}: CodeTether automated fix',
                    'commit_message': f'Approved by CodeTether reviewer task {parent_task_id}.',
                    'sha': current_sha,
                    'merge_method': merge_method,
                },
            )
        except Exception as exc:
            failures = [f'GitHub merge API rejected the merge: {exc}']
            await record_automation_decision(
                provenance=provenance,
                decision=_failure_decision('github:merge_pr', failures),
                task_id=parent_task_id,
            )
            await post_issue_comment(
                repo,
                pr_number,
                token,
                "## 🛠️ CodeTether Auto-Merge\n\n"
                "Blocked by GitHub while attempting to merge.\n\n"
                f"{_format_blockers(failures)}",
            )
            return None

        merged_sha = str(merge_result.get('sha') or '').strip()
        await record_automation_decision(provenance=provenance, decision=decision, task_id=parent_task_id)
        message = (
            "## 🛠️ CodeTether Auto-Merge\n\n"
            f"Merged PR #{pr_number} using `{merge_method}` after reviewer approval and resolved-feedback checks."
        )
        if merged_sha:
            message += f"\n\nMerge SHA: `{merged_sha}`"
        message += provenance_footer(provenance, action='github:merge_pr')
        await post_issue_comment(repo, pr_number, token, message)
        return merged_sha or 'merged'

    task_id = await create_and_dispatch_task(
        workspace_id=workspace_id,
        title=f'Merge issue PR #{pr_number}',
        prompt=merge_prompt(repo, issue_number, branch, pr, provenance),
        agent_type='merge',
        model_ref=MODEL_REF,
        metadata=merge_metadata,
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
        github_issue_url=metadata.get('github_issue_url'),
    )
    await record_automation_decision(provenance=provenance, decision=decision, task_id=task_id)
    return task_id
