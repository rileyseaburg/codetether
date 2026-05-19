# GitHub App permissions

CodeTether's GitHub App uses repository-scoped installation tokens for PR and issue automation.

## Required permissions

| Permission | Access | Why |
| --- | --- | --- |
| Metadata | Read | Required by GitHub for app installations and repository lookup. |
| Contents | Write | Clone and push automation branches and read repository refs. |
| Issues | Write | Post progress, blocker, and completion comments on issues and PRs. |
| Pull requests | Write | Create review comments and run merge-steward actions. |
| Checks | Write | Publish rich CodeTether task evidence as GitHub Check Runs. |

## GitHub Actions budget note

Publishing Check Runs or commit statuses through the GitHub REST API does not start GitHub Actions workflow jobs and does not consume GitHub-hosted runner minutes. GitHub Actions billing is based on workflow runner minutes plus Actions artifact/cache storage; CodeTether status publishing creates commit-attached API records only.

## Runtime publishing mode

Set `GITHUB_APP_STATUS_PUBLISHER` to control which commit-attached API path is used:

| Value | Behavior | Required permission | Actions runner minutes |
| --- | --- | --- | --- |
| `checks` | Create/update rich Check Runs, then use commit statuses if Checks are not permitted. This is the default. | `Checks: write`; optionally `Commit statuses: write` for the secondary path. | No |
| `statuses` | Skip the Checks API and publish legacy commit statuses only. | `Commit statuses: write` | No |
| `off` | Do not publish GitHub commit-attached status records. | None for status publishing | No |

## Secondary status permission

| Permission | Access | Why |
| --- | --- | --- |
| Commit statuses | Write | Publish legacy commit status records when rich Check Runs are unavailable. |

If neither `Checks: write` nor `Commit statuses: write` is granted, CodeTether still completes the internal task workflow, but GitHub rejects platform-attached status publishing with `403 Resource not accessible by integration`. The server logs include this remediation:

```text
Grant the GitHub App Checks: write permission, or Statuses: write for fallback commit statuses.
```

## Current live evidence example

On 2026-05-18, the live `codetether` app identity was:

```json
{
  "app_id": 3332571,
  "html_url": "https://github.com/apps/codetether",
  "name": "codetether",
  "owner_login": "rileyseaburg",
  "owner_type": "User",
  "slug": "codetether"
}
```

The live installation for `rileyseaburg/codetether` had installation ID `122795782` and only these repository permissions:

```json
{
  "contents": "write",
  "issues": "write",
  "metadata": "read",
  "pull_requests": "write"
}
```

That installation minted tokens successfully, but GitHub rejected both status publishing routes:

```text
POST /repos/rileyseaburg/codetether/check-runs -> 403 Resource not accessible by integration
POST /repos/rileyseaburg/codetether/statuses/<sha> -> 403 Resource not accessible by integration
```

Add and approve `Checks: write` to enable rich Check Runs, or add and approve `Commit statuses: write` to enable legacy commit statuses.

## Updating the live GitHub App permissions

GitHub App repository permissions are changed in the GitHub App settings UI, not through this service's Kubernetes deployment.
For the current app, open <https://github.com/apps/codetether> as an app owner/manager, edit the app's repository permissions, and request one of:

- **Checks: Read and write**, preferred for rich CodeTether Check Runs.
- **Commit statuses: Read and write**, sufficient when `GITHUB_APP_STATUS_PUBLISHER=statuses` or for the secondary commit-status path.

After the app owner saves a new permission request, the installed account owner must approve the updated permissions for the installation on `rileyseaburg/codetether`. Until the updated installation permissions show either `"checks": "write"` or `"statuses": "write"`, GitHub will continue returning `403 Resource not accessible by integration` for commit-attached status publishing.
