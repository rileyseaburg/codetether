# Failed-Check Remediation Loop

> Issue #88 · Branch `codetether/issue-88`

CodeTether automatically remediates failed GitHub checks on open pull requests.
When a third-party CI check fails, CodeTether queues a single remediation task
that fetches the failure logs, patches the branch, pushes a commit, and comments
with validation evidence — **without merging**.

## Supported Events

| GitHub Event | Action | Behavior |
|---|---|---|
| `check_run` | `completed` | Parsed if `conclusion` is `failure`, `timed_out`, `cancelled`, or `action_required`. |
| `check_suite` | `completed` | Same as `check_run` but keyed by suite ID. |
| `workflow_run` | `completed` | Same as `check_run` but uses the workflow name as the check name. |

All other events and actions are passed through to the existing mention-driven flow.

## How It Works

1. **Webhook ingress** — The existing `/v1/webhooks/github` endpoint now checks
   for `check_run`, `check_suite`, and `workflow_run` events *before* the
   mention-driven flow.
2. **Normalization** — Each event type is parsed into a `RemediationContext`
   containing: repository, PR number, branch, head SHA, check name, conclusion,
   details URL, and installation identity.
3. **Recursion guard** — Checks authored by the CodeTether GitHub App (matched
   by slug or name prefix `CodeTether`) are silently ignored to prevent infinite
   loops.
4. **Idempotency** — A SHA-256–based dedup key (`repo:check_name:head_sha`)
   ensures repeated GitHub deliveries do not spawn duplicate tasks.
5. **Task creation** — A single fire-and-forget task is queued with the
   `remediation` workflow stage and a 7-day timeout.
6. **Worker prompt** — The task prompt instructs the agent to fetch logs, patch
   the branch, push a commit, and comment with evidence. It explicitly
   prohibits merging or force-pushing.

## Required Webhook Permissions

The GitHub App must subscribe to these webhook events:

| Event | Permission |
|---|---|
| `Check runs` | **Read** (to receive failure notifications) |
| `Check suites` | **Read** |
| `Workflow runs` | **Read** |
| `Pull requests` | **Read** (to resolve PR number from check) |
| `Contents` | **Write** (to push remediation commits) |
| `Issues` | **Write** (to post PR comments) |
| `Checks` | **Write** (to publish remediation check results) |

## Limitations

- **No branch-project association**: `workflow_run` events may not include a PR
  number if the workflow was triggered on a branch rather than a PR. These events
  are logged but no task is created.
- **In-process dedup**: The current dedup set lives in process memory. On
  restart, it resets. For production hardening, add a database or Redis
  uniqueness constraint on `(repo, check_name, head_sha)`.
- **No log fetching in the webhook handler**: The handler does not fetch check
  logs directly — the worker prompt instructs the agent to do this.

## Recovery Steps

If the remediation loop is not triggering:

1. Verify webhook delivery in the GitHub App settings → Advanced.
2. Check server logs for `Remediation:` prefixed entries.
3. Ensure the GitHub App has **Read** access to `Check runs`, `Check suites`,
   and `Workflow runs` events.
4. Confirm the failed check has an associated open pull request.
5. Verify the check is **not** authored by CodeTether (self-authored checks are
   intentionally ignored).

If a remediation task was created but failed:

1. Check the task status via the CodeTether dashboard or task API.
2. The task metadata preserves `failed_check_name`, `failed_check_conclusion`,
   and `failed_check_details_url` for debugging.
3. The worker prompt instructs the agent to comment on the PR with a blocker
   summary if it cannot determine the fix.

## Architecture

```
GitHub webhook (check_run.completed)
  → /v1/webhooks/github
  → normalize_check_event() → RemediationContext
  → _is_codetether_authored() → skip if self-authored
  → is_duplicate() → skip if already queued
  → _queue_remediation_task() → fire-and-forget task
  → Worker picks up task, patches, pushes, comments
```
