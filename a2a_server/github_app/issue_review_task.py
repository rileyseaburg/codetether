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

CHANGE_REQUEST_MENTION = '@codetether'

MAX_FIX_ATTEMPTS_PER_SHA = 5


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


def _truncate_for_comment(value: str, *, limit: int = 4000) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 20].rstrip() + '\n\n...[truncated]'


def change_request_action_line(verdict: str, *, task_id: str | None = None) -> str:
    """Render the actionable change-request line with the worker mention.

    Any CodeTether GitHub-facing review/follow-up that asks for code changes
    must tag the app handle in the action sentence so mention-based workers can
    pick it up. Approval and informational comments should not use this helper.
    """
    normalized_verdict = str(verdict or 'CHANGES_REQUESTED').strip() or 'CHANGES_REQUESTED'
    if task_id:
        return (
            f"{CHANGE_REQUEST_MENTION} follow-up required: protocol-native fix task "
            f"`{task_id}` is queued for `{normalized_verdict}`."
        )
    return f"{CHANGE_REQUEST_MENTION} please address the requested PR changes."


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


def reviewer_verdict(review_task: dict[str, Any]) -> str | None:
    """Return the reviewer's terminal verdict when it can be parsed."""
    result = str(review_task.get('result') or '')
    upper_result = result.upper()

    verdict_matches = re.findall(
        r'(?:FINAL\s+(?:VERDICT|RESPONSE|STATUS)|VERDICT|STATUS)\s*:?\s*\**\s*'
        r'(APPROVED|CHANGES_REQUESTED|BLOCKED)\b',
        upper_result,
    )
    if verdict_matches:
        return verdict_matches[-1]

    line_verdicts = [
        match.group(1)
        for match in re.finditer(
            r'^\s*\**\s*(APPROVED|CHANGES_REQUESTED|BLOCKED)\b',
            upper_result,
            flags=re.MULTILINE,
        )
    ]
    if line_verdicts:
        return line_verdicts[-1]

    if 'CHANGES_REQUESTED' in upper_result:
        return 'CHANGES_REQUESTED'
    if re.search(r'\bBLOCKED\s*:', upper_result):
        return 'BLOCKED'
    if 'APPROVED' in upper_result:
        return 'APPROVED'
    return None


def reviewer_allows_merge(review_task: dict[str, Any]) -> bool:
    """Return True only when the reviewer explicitly approved the PR."""
    return reviewer_verdict(review_task) == 'APPROVED'


def reviewer_needs_work(review_task: dict[str, Any]) -> bool:
    """Return True when the reviewer explicitly requested work before merge."""
    return reviewer_verdict(review_task) in {'CHANGES_REQUESTED', 'BLOCKED'}


def fix_followup_prompt(
    *,
    repo: str,
    issue_number: int,
    pr_number: int,
    branch: str,
    head_sha: str,
    pr_url: str,
    verdict: str,
    review_summary: str,
    changed_files: list[str] | None = None,
    blockers: list[str] | None = None,
    last_validation_errors: str | None = None,
    provenance: dict[str, Any] | None = None,
    attempt: int = 1,
) -> str:
    """Build the worker prompt for a protocol-native PR fix follow-up task."""
    footer = (
        provenance_footer(provenance, action='github:fix_pr')
        if provenance
        else ''
    )
    files_section = ''
    if changed_files:
        files_section = '\n\nFiles changed in this PR:\n' + '\n'.join(f'- `{f}`' for f in changed_files[:30])
    blockers_section = ''
    if blockers:
        blockers_section = '\n\nSpecific blockers to address:\n' + _format_blockers(blockers)
    validation_section = ''
    if last_validation_errors:
        validation_section = f'\n\nLast validation errors:\n```\n{_truncate_for_comment(last_validation_errors, limit=2000)}\n```'
    attempt_line = f'\n\nFix attempt {attempt} of {MAX_FIX_ATTEMPTS_PER_SHA}.' if attempt > 1 else ''
    return f"""You are editing the existing PR branch for PR #{pr_number}: {pr_url}
Branch: {branch}
Head SHA: {head_sha}

Personality/avatar: {CODETETHER_PERSONALITY['name']} using {CODETETHER_PERSONALITY['avatar']} — concise, safety-first, provenance-aware.

A CodeTether reviewer returned verdict `{verdict}` for PR #{pr_number} in {repo} (issue #{issue_number}).
Apply the requested changes directly in the checked-out repository. Do not just describe the fix.

Do not stay in analysis mode. Use at most 5 discovery reads or searches before your first code edit. Prefer the files closest to the requested area, and keep moving toward an actual patch instead of repeating repo exploration.

Reviewer summary:
{_truncate_for_comment(review_summary)}{files_section}{blockers_section}{validation_section}{attempt_line}

After editing files, run the smallest relevant validation needed, commit the changes, and push them back to the existing PR branch `{branch}`. Do not open a new PR. In the final response, include the commit SHA if you created one.{footer}"""


def _fix_attempt_key(repo: str, pr_number: int, head_sha: str) -> str:
    """Return a deterministic key for tracking fix attempts per PR/head SHA."""
    return f'codetether:fix_followup:{repo}#{pr_number}@{head_sha}'


async def _count_fix_attempts(repo: str, pr_number: int, head_sha: str) -> int:
    """Count existing fix follow-up tasks for this repo/PR/head SHA combination."""
    try:
        from .. import database as db
        pool = await db.get_pool()
        if not pool:
            return 0
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS cnt
                FROM (SELECT jsonb_array_elements(metadata->'fix_followup_history') AS entry
                      FROM tasks
                      WHERE metadata->>'repo' = $1
                        AND metadata->>'pr_number' = $2
                        AND metadata->>'pr_head_sha' = $3
                        AND metadata->>'source' = 'github-app'
                        AND metadata->>'fix_followup' IS NOT NULL
                     ) sub
                """,
                repo, str(pr_number), head_sha,
            )
            return int((row or {}).get('cnt') or 0)
    except Exception:
        return 0


async def create_fix_followup_task(
    *,
    review_task: dict[str, Any],
    token: str,
) -> str | None:
    """Create a protocol-native A2A fix task when a reviewer requests changes.

    This is the primary handoff path: when a review task completes with
    CHANGES_REQUESTED or BLOCKED, we enqueue a follow-up fix task directly
    instead of relying on a GitHub @mention webhook round-trip.

    Includes idempotency (duplicate suppression) and loop guards:
    - PR must be open
    - Head SHA must match the reviewed commit
    - Branch must not have changed since review
    - Fix attempts are capped per PR/head SHA
    - Provenance/policy gates are enforced
    """
    verdict = reviewer_verdict(review_task)
    if verdict not in {'CHANGES_REQUESTED', 'BLOCKED'}:
        return None

    metadata = review_task.get('metadata') or {}
    repo = str(metadata.get('repo') or '')
    issue_number = int(metadata.get('issue_number') or 0)
    pr_number = int(metadata.get('pr_number') or 0)
    branch = str(metadata.get('branch_name') or '')
    workspace_id = str(metadata.get('workspace_id') or '')
    expected_sha = str(metadata.get('pr_head_sha') or '')
    installation_id = metadata.get('github_installation_id')
    github_issue_url = str(metadata.get('github_issue_url') or '')
    review_task_id = str(review_task.get('id') or '')
    review_summary = str(review_task.get('result') or '').strip()

    if not (repo and issue_number and pr_number and branch and workspace_id and expected_sha):
        logger.warning(
            'fix_followup: skipping due to missing metadata for review task %s',
            review_task_id,
        )
        return None

    from ..persistent_worker_pool import create_and_dispatch_task
    from .auth import github_json
    from .watch import post_issue_comment

    # Guard: verify PR is still open and head SHA matches
    try:
        pr = await github_json('GET', f'/repos/{repo}/pulls/{pr_number}', token)
    except Exception as exc:
        logger.warning('fix_followup: could not fetch PR %s/%s: %s', repo, pr_number, exc)
        return None

    if str(pr.get('state') or '').upper() != 'OPEN':
        logger.info('fix_followup: PR %s/%s is not open, skipping', repo, pr_number)
        return None

    current_sha = str((pr.get('head') or {}).get('sha') or '')
    if current_sha != expected_sha:
        logger.info(
            'fix_followup: PR %s/%s head SHA changed (%s -> %s), skipping',
            repo, pr_number, expected_sha, current_sha,
        )
        return None

    # Guard: check for forked PRs
    head_repo = ((pr.get('head') or {}).get('repo') or {}).get('full_name') or ''
    if head_repo and head_repo != repo:
        logger.info('fix_followup: PR %s/%s is forked (%s), skipping', repo, pr_number, head_repo)
        return None

    # Loop guard: cap attempts per PR/head SHA
    attempt_count = await _count_fix_attempts(repo, pr_number, expected_sha)
    attempt = attempt_count + 1
    if attempt > MAX_FIX_ATTEMPTS_PER_SHA:
        logger.warning(
            'fix_followup: max attempts (%d) reached for %s/%s @ %s, skipping',
            MAX_FIX_ATTEMPTS_PER_SHA, repo, pr_number, expected_sha,
        )
        await post_issue_comment(
            repo, pr_number, token,
            "## 🛠️ CodeTether Fix Follow-up\n\n"
            f"Maximum fix attempts ({MAX_FIX_ATTEMPTS_PER_SHA}) reached for this PR head SHA. "
            "Manual intervention may be required.",
        )
        return None

    # Build provenance for the fix action
    provenance = issue_pr_provenance(
        repo=repo,
        issue_number=issue_number,
        branch=branch,
        pr=pr,
        installation_id=installation_id,
        action='github:fix_pr',
        parent_task_id=review_task_id,
    )

    # Check policy
    decision = policy_decision(provenance, 'github:fix_pr')
    if not decision['allowed']:
        await record_automation_decision(
            provenance=provenance, decision=decision, task_id=review_task_id,
        )
        logger.info('fix_followup: policy denied for %s/%s', repo, pr_number)
        return None

    # Idempotency: check if a fix follow-up task already exists for this review task
    try:
        from .. import database as db
        pool = await db.get_pool()
        if pool:
            async with pool.acquire() as conn:
                existing = await conn.fetchval(
                    """
                    SELECT id FROM tasks
                    WHERE metadata->>'review_task_id' = $1
                      AND metadata->>'fix_followup' = 'true'
                      AND status NOT IN ('completed', 'failed', 'cancelled')
                    LIMIT 1
                    """,
                    review_task_id,
                )
                if existing:
                    logger.info(
                        'fix_followup: existing fix task %s for review %s, skipping duplicate',
                        existing, review_task_id,
                    )
                    return None
    except Exception as exc:
        logger.warning('fix_followup: idempotency check failed: %s', exc)

    # Parse review context
    pr_url = str(pr.get('html_url') or f'https://github.com/{repo}/pull/{pr_number}')

    # Extract changed files from provenance or review metadata
    changed_files = metadata.get('changed_files') or None
    blockers = metadata.get('blockers') or None
    last_validation_errors = metadata.get('last_validation_errors') or None

    fix_prompt = fix_followup_prompt(
        repo=repo,
        issue_number=issue_number,
        pr_number=pr_number,
        branch=branch,
        head_sha=expected_sha,
        pr_url=pr_url,
        verdict=verdict or '',
        review_summary=review_summary,
        changed_files=changed_files,
        blockers=blockers,
        last_validation_errors=last_validation_errors,
        provenance=provenance,
        attempt=attempt,
    )

    fix_metadata = {
        'workspace_id': workspace_id,
        'source': 'github-app',
        'workflow_stage': 'fix',
        'repo': repo,
        'issue_number': issue_number,
        'pr_number': pr_number,
        'branch_name': branch,
        'pr_head_sha': expected_sha,
        'github_issue_url': github_issue_url,
        'github_installation_id': installation_id,
        'worker_personality': 'builder',
        'personality': CODETETHER_PERSONALITY,
        'codetether_provenance': provenance,
        'policy_decision': decision,
        'review_task_id': review_task_id,
        'review_verdict': verdict,
        'fix_followup': 'true',
        'fix_attempt': attempt,
    }

    # Propagate parent_task_id from the review task metadata chain
    parent_task_id = metadata.get('parent_task_id')
    if parent_task_id:
        fix_metadata['parent_task_id'] = parent_task_id

    task_id = await create_and_dispatch_task(
        workspace_id=workspace_id,
        title=f'Apply PR fix #{pr_number}',
        prompt=fix_prompt,
        agent_type='build',
        model_ref=MODEL_REF,
        metadata=fix_metadata,
        task_timeout_seconds=DEFAULT_TASK_TIMEOUT,
        github_issue_url=github_issue_url,
    )

    await record_automation_decision(
        provenance=provenance, decision=decision, task_id=task_id,
    )

    logger.info(
        'fix_followup: created fix task %s for review %s (%s), attempt %d',
        task_id, review_task_id, verdict, attempt,
    )

    # Post a comment indicating the protocol-native follow-up. Keep the
    # @codetether mention in the actionable sentence for compatibility with
    # mention-based worker pickup while protocol-native follow-up rolls out.
    comment_body = (
        "## 🛠️ CodeTether Fix Follow-up\n\n"
        f"{change_request_action_line(verdict or '', task_id=task_id)}\n\n"
        f"Reviewer verdict: `{verdict}`.\n\n"
        f"Fix attempt {attempt} of {MAX_FIX_ATTEMPTS_PER_SHA}."
    )
    if review_summary:
        comment_body += f"\n\nReviewer summary:\n\n{_truncate_for_comment(review_summary)}"
    comment_body += provenance_footer(provenance, action='github:fix_pr')
    await post_issue_comment(repo, pr_number, token, comment_body)

    return task_id


async def post_change_request_followup_if_needed(
    *,
    review_task: dict[str, Any],
    token: str,
) -> bool:
    """Post a deterministic tagged follow-up when a reviewer forgets the tag.

    This is the **compatibility fallback** — it only fires when the reviewer's
    result omits the `@codetether` tag. The primary protocol-native path is
    `create_fix_followup_task()`, which does not depend on GitHub mentions.
    """
    verdict = reviewer_verdict(review_task)
    if verdict not in {'CHANGES_REQUESTED', 'BLOCKED'}:
        return False

    result = str(review_task.get('result') or '').strip()
    if CHANGE_REQUEST_MENTION.lower() in result.lower():
        return False

    metadata = review_task.get('metadata') or {}
    repo = str(metadata.get('repo') or '')
    pr_number = int(metadata.get('pr_number') or 0)
    if not (repo and pr_number):
        return False

    from .watch import post_issue_comment

    body = (
        "## 🛠️ CodeTether Review Follow-up\n\n"
        f"{change_request_action_line(verdict)}\n\n"
        f"Reviewer verdict: `{verdict}`."
    )
    if result:
        body += f"\n\nReviewer summary:\n\n{_truncate_for_comment(result)}"
    await post_issue_comment(repo, pr_number, token, body)
    return True


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


async def enable_pull_request_auto_merge(
    *,
    pr: dict[str, Any],
    merge_method: str,
    current_sha: str,
    parent_task_id: str,
    token: str,
) -> dict[str, Any]:
    """Ask GitHub to auto-merge the PR once branch protection is satisfied."""
    from .auth import github_graphql

    pull_request_id = str(pr.get('node_id') or '').strip()
    if not pull_request_id:
        raise RuntimeError('GitHub pull request node_id is missing')

    query = """
    mutation EnableCodeTetherAutoMerge(
      $pullRequestId: ID!,
      $mergeMethod: PullRequestMergeMethod!,
      $commitHeadline: String!,
      $commitBody: String!,
      $expectedHeadOid: GitObjectID!
    ) {
      enablePullRequestAutoMerge(input: {
        pullRequestId: $pullRequestId,
        mergeMethod: $mergeMethod,
        commitHeadline: $commitHeadline,
        commitBody: $commitBody,
        expectedHeadOid: $expectedHeadOid
      }) {
        pullRequest {
          number
          autoMergeRequest {
            enabledAt
            mergeMethod
          }
        }
      }
    }
    """
    data = await github_graphql(
        query,
        {
            'pullRequestId': pull_request_id,
            'mergeMethod': merge_method.upper(),
            'commitHeadline': f'Merge PR #{pr.get("number")}: CodeTether automated fix',
            'commitBody': f'Approved by CodeTether reviewer task {parent_task_id}.',
            'expectedHeadOid': current_sha,
        },
        token,
    )
    pull_request = (data.get('enablePullRequestAutoMerge') or {}).get('pullRequest') or {}
    auto_merge_request = pull_request.get('autoMergeRequest')
    if not auto_merge_request:
        raise RuntimeError('GitHub did not return an auto-merge request')
    return auto_merge_request


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
4. If anything requires changes, leave a CHANGES_REQUESTED review/comment and include `{CHANGE_REQUEST_MENTION}` in the GitHub-facing body so CodeTether gets explicitly re-engaged.
5. If the PR is safe, leave an approving review or success comment.
6. Include this exact provenance footer in any GitHub review/comment you create:{footer}

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
        # Primary path: protocol-native A2A fix follow-up
        fix_task_id = await create_fix_followup_task(review_task=review_task, token=token)
        if fix_task_id:
            logger.info(
                'Protocol-native fix follow-up %s enqueued for review %s',
                fix_task_id, review_task.get('id'),
            )
        else:
            # Compatibility fallback: @codetether mention comment
            await post_change_request_followup_if_needed(review_task=review_task, token=token)
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
            merge_failure = f'GitHub merge API rejected the merge: {exc}'
            try:
                auto_merge_request = await enable_pull_request_auto_merge(
                    pr=pr,
                    merge_method=merge_method,
                    current_sha=current_sha,
                    parent_task_id=parent_task_id,
                    token=token,
                )
            except Exception as auto_exc:
                failures = [
                    merge_failure,
                    f'GitHub auto-merge could not be enabled: {auto_exc}',
                ]
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

            await record_automation_decision(provenance=provenance, decision=decision, task_id=parent_task_id)
            enabled_at = str(auto_merge_request.get('enabledAt') or '').strip()
            message = (
                "## 🛠️ CodeTether Auto-Merge\n\n"
                f"Enabled GitHub auto-merge for PR #{pr_number} using `{merge_method}` after reviewer approval and resolved-feedback checks."
            )
            if enabled_at:
                message += f"\n\nEnabled at: `{enabled_at}`"
            message += provenance_footer(provenance, action='github:merge_pr')
            await post_issue_comment(repo, pr_number, token, message)
            return 'auto_merge_enabled'

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
