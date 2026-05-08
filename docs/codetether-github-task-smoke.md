# CodeTether GitHub Task Smoke Test

This document records an end-to-end smoke test for the CodeTether GitHub App issue workflow.

| Field       | Value                          |
|-------------|--------------------------------|
| Issue       | #58                            |
| Branch      | `codetether/issue-58`          |
| Date (UTC)  | 2026-05-07                     |
| Status      | Fresh harvester pickup verified |

## Purpose

Confirm that CodeTether can:

1. Acknowledge an issue mention (`@codetether please retry this stale automation task...`).
2. Queue the corresponding A2A task for a persistent harvester worker.
3. Have a harvester worker receive and claim the task.
4. Report pickup status with a documentation-only PR.

## 2026-05-07 retry result

- The GitHub App acknowledged the fresh issue mention on issue #58.
- The stale/unclaimed prior pickup was superseded by this run on `codetether/issue-58`.
- A harvester worker created and claimed the CodeTether task for the issue retry path.
- No destructive repair was needed; the prior credential-helper and fire-and-forget task-run fixes were already present in the repository history.
- This PR is intentionally documentation-only and does not change production behavior.

## Validation

The smallest relevant validation is a repository-local documentation check confirming this smoke record still names the issue, branch, verified pickup status, and no-production-change scope.
