# Forgejo agent orchestration with Temporal

Temporal is the durable source of truth for Forgejo coding-agent stage
transitions. Forgejo remains the authenticated repository-scoped read model for
tasks, events, controls, issue/PR links, and session pages. CodeTether remains
the execution backend.

## Security boundary

Workflow history may contain only:

- Forgejo task/repository/issue/PR identifiers;
- CodeTether task/session identifiers;
- branch and commit SHA;
- stage/status/verdict enums; and
- bounded attempt counters.

Prompts, credentials, clone URLs, transcripts, tool inputs/results, environment
maps, and provider payloads are loaded inside activities and must never be
returned to workflow history. Full transcripts remain in CodeTether storage;
redacted events are projected into Forgejo.

## CodeTether configuration

The API and dedicated Temporal worker require:

```text
FORGEJO_TEMPORAL_ENABLED=true
TEMPORAL_ADDRESS=temporal-frontend.temporal.svc.cluster.local:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_FORGEJO_TASK_QUEUE=codetether-forgejo-agent
FORGEJO_API_URL=https://forgejo.example/api/v1
FORGEJO_TOKEN=<secret>
FORGEJO_WEBHOOK_SECRET=<shared control HMAC secret>
DATABASE_URL=<secret>
```

For mTLS, also set `TEMPORAL_TLS_CERT`, `TEMPORAL_TLS_KEY`, and optionally
`TEMPORAL_TLS_SERVER_NAME`. Mount certificate/key files read-only.

The Helm chart values are:

```yaml
temporal:
  enabled: true
  address: temporal-frontend.temporal.svc.cluster.local:7233
  namespace: default
  taskQueue: codetether-forgejo-agent
  replicas: 1
```

`temporal.enabled=false` is the default. Enabling it creates the dedicated
`<release>-temporal-worker` Deployment and configures all API deployment modes
to start/signal workflows.

## Forgejo configuration

Forgejo sends native Cancel/Retry controls to CodeTether with HMAC-SHA256 over
the exact JSON request body:

```ini
[codetether]
CONTROL_URL = https://api.codetether.run/v1/webhooks/forgejo/agent-control
CONTROL_SECRET = <same value as CodeTether FORGEJO_WEBHOOK_SECRET>
```

The URL must use HTTPS (loopback HTTP is accepted for tests only). When
`CONTROL_URL` is configured, delivery is fail-closed: Forgejo changes no task
state unless CodeTether returns a 2xx response. Requests expire after five
minutes. Repeated cancel/retry signals are idempotent at workflow state level.

## Rollout order

1. Create the Temporal namespace and retention policy.
2. Store Temporal TLS material, Forgejo token, database URL, and control HMAC in
   Kubernetes Secrets. Never place them in Helm values or workflow arguments.
3. Deploy the CodeTether image with `temporalio` installed while
   `temporal.enabled=false`.
4. Enable the worker only and verify one poller is attached to
   `codetether-forgejo-agent`.
5. Configure Forgejo `[codetether]` control delivery.
6. Enable `FORGEJO_TEMPORAL_ENABLED` on one canary CodeTether API deployment.
7. Run one private-repository task through prepare, code, review, and terminal
   projection. Verify the native Forgejo session page and Temporal history.
8. Exercise Cancel during an active stage and Retry after a failed attempt.
9. Expand API traffic only after the canary succeeds.

Do not enable both the legacy Forgejo control poller and Temporal control path.
The application disables the legacy control poller when
`FORGEJO_TEMPORAL_ENABLED=true`, and legacy terminal review reconciliation
explicitly excludes Temporal-managed tasks.

## Canary acceptance evidence

Capture:

- Temporal namespace, workflow ID, run ID, task queue, and terminal status;
- CodeTether API/worker image digest and pod names;
- Forgejo repository/task ID and native session URL;
- prepare/code/review/fix task IDs as applicable;
- redacted event count and proof that sensitive sentinel strings are absent;
- Cancel activity observation and Retry `continue_as_new` attempt number;
- worker/API restart counts and post-canary health.

Never publish raw Temporal history if it contains unexpected sensitive data.
Treat such a finding as a release blocker and purge the canary namespace/history
according to the Temporal environment's retention/deletion policy.

## Rollback

Immediate rollback is non-destructive:

1. Set `temporal.enabled=false` / `FORGEJO_TEMPORAL_ENABLED=false` on CodeTether.
2. Scale `<release>-temporal-worker` to zero.
3. Remove or comment Forgejo `CONTROL_URL` so native cancel/retry reverts to its
   local state transition behavior.
4. Restore the previous CodeTether image if application rollback is required.
5. Leave Temporal history intact for diagnosis; it contains only the bounded
   non-sensitive contracts above.
6. Legacy control polling resumes when the feature flag is false.

Do not terminate running workflows until their active CodeTether task IDs and
Forgejo task IDs have been captured. Cancellation is preferred to termination
because activities heartbeat and can revoke active run leases cleanly.
