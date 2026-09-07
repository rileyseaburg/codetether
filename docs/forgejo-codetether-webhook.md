# Forgejo `@codetether` webhook

CodeTether exposes a native Forgejo-compatible webhook at:

```text
POST /v1/webhooks/forgejo
```

It accepts Forgejo (`X-Forgejo-*`) and Gitea-compatible (`X-Gitea-*`) headers.
Mentions in newly opened issues, issue comments, and PR conversation comments
are committed to a durable inbox before any external operation. The response
contains a `delivery_id` and intake state; it is not proof of task completion.
See [durable intake and orphan recovery](operations/forgejo-inbox.md).

## CodeTether configuration

Configure these variables on the A2A server deployment:

| Variable | Required | Description |
|---|---:|---|
| `FORGEJO_API_URL` | yes | Forgejo API root, e.g. `https://forge.example/api/v1`. Its HTTPS host is also added to the git clone allowlist. |
| `FORGEJO_TOKEN` | yes | Token for the CodeTether bot account. Store it in a Kubernetes Secret or Vault-backed environment source. |
| `FORGEJO_WEBHOOK_SECRET` | yes | Shared HMAC-SHA256 webhook secret. |
| `FORGEJO_BOT_USERNAME` | no | Bot login used for loop prevention; defaults to `codetether`. |

The bot token needs repository read/write access, issue read/write access, and pull-request read/write access. It must be able to clone, push branches, create pull requests, and post issue/PR comments.

## Forgejo repository webhook

In **Repository settings → Webhooks → Add webhook → Forgejo**, configure:

- **Target URL:** `https://<codetether-host>/v1/webhooks/forgejo`
- **HTTP method:** `POST`
- **Content type:** `application/json`
- **Secret:** the same value as `FORGEJO_WEBHOOK_SECRET`
- **Events:** Issues and issue comments (Forgejo PR conversations use issue-comment payloads).
- **Active:** enabled

Use Forgejo's webhook test delivery and confirm an HTTP 200 response. A bad signature returns 401; missing server configuration returns 503.

## Supported behavior

- New actionable mentions queue durable work, including `@codetether still not working` retries.
- Editing a comment to add the first mention dispatches work.
- Editing an already-mentioned comment does not dispatch duplicate work.
- Bot-authored comments are ignored to prevent loops.
- Non-actionable mentions receive guidance.
- Duplicate deliveries reuse one receipt. Distinct mentions wait for prior issue/PR work rather than disappearing behind an active-task check.
- Issue requests create a `codetether/issue-<number>` branch and instruct the worker to open a Forgejo PR.
- PR requests target the current PR head branch.
- Forgejo metadata remains tagged as `source=forgejo-webhook` and `platform=forgejo`; it is not represented as GitHub work.

## Smoke test

Post this in a Forgejo issue or PR conversation:

```text
@codetether handle this issue
```

Expected receipt notification from the inbox worker (after durable acceptance,
independent of Vault/workspace preparation):

```text
## 🛠️ CodeTether Fix

Your request is queued durably.
```

Then confirm a task with metadata `source=forgejo-webhook`, the expected repository and issue number, and a connected worker with the `persistent-workspace` capability.