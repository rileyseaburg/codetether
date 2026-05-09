# CodeTether GitHub Task Smoke Test

This document records end-to-end smoke tests for the CodeTether GitHub App issue workflow.

| Field             | Value                            |
| ----------------- | -------------------------------- |
| Latest issue      | #58                              |
| Latest branch     | `codetether/issue-58`            |
| Latest date (UTC) | 2026-05-07                       |
| Latest status     | Fresh harvester pickup verified  |

## Purpose

Confirm that CodeTether can:

1. Acknowledge an issue mention.
2. Queue the corresponding A2A task for a persistent harvester worker.
3. Have a harvester worker receive and claim the task.
4. Create a feature branch and documentation-only pull request that references the originating issue.
5. Report pickup status without changing production behavior.

## Smoke test history

### Issue #39 — automated PR creation

| Field      | Value                     |
| ---------- | ------------------------- |
| Issue      | #39                       |
| Branch     | `codetether/issue-39`     |
| Date (UTC) | 2026-04-24                |
| Status     | Verified via automated PR |

This smoke test confirmed that CodeTether could receive an issue trigger (`@codetether fix this please`), create the `codetether/issue-39` feature branch, commit a documentation change, and open a pull request that references and closes the originating issue.

### Issue #58 — harvester pickup retry

| Field      | Value                           |
| ---------- | ------------------------------- |
| Issue      | #58                             |
| Branch     | `codetether/issue-58`           |
| Date (UTC) | 2026-05-07                      |
| Status     | Fresh harvester pickup verified |

- The GitHub App acknowledged the fresh issue mention on issue #58.
- The stale/unclaimed prior pickup was superseded by this run on `codetether/issue-58`.
- A harvester worker created and claimed the CodeTether task for the issue retry path.
- No destructive repair was needed; the prior credential-helper and fire-and-forget task-run fixes were already present in the repository history.
- This PR is intentionally documentation-only and does not change production behavior.

## Validation

The smallest relevant validation is a repository-local documentation check confirming this smoke record still names the issue, branch, verified status, and no-production-change scope for each recorded smoke test.
