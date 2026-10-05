# Durable Forgejo mention intake

## Acceptance contract

`POST /v1/webhooks/forgejo` verifies the existing webhook HMAC and filters
self-authored/non-actionable event types before storing a receipt in PostgreSQL.
For a mention-bearing event, HTTP success means **receipt committed**, not
repository work finished. The response includes `delivery_id`, `state`, and any
recorded handoff result. A duplicate returns the same receipt; it does not create
new work. Storage failure is not acknowledged as acceptance.

The inbox is upstream of Vault, repository lookup, worker dispatch and Temporal.
No credentials, HTTP headers or raw webhook object are stored. The request body
needed by the worker is retained in the private CodeTether database, never in
Temporal history. Temporal continues to own prepare/code/review stages.

## Recovery properties

- API startup runs an independent inbox pump; Forgejo redelivery is unnecessary.
- Receipt notification is independent of workspace preparation. An unavailable
  Vault cannot silently erase an accepted request.
- A PostgreSQL session advisory lock serializes each repository/issue across
  replicas. Process/connection death releases the lock without deleting work.
- Earlier receipts and native tasks retain issue ownership until terminal;
  two different mentions cannot race into the same mutable issue workspace.
- Native Retry is checked both at the signal boundary and at stage creation.
  A superseded retry cannot resume over a newer actionable request. Ordinary
  stages finish without being aborted by queued followup comments.
- Repository/PR planning is checkpointed, fixing the target head for retries.
- Native tasks, CodeTether task work keys and Temporal workflow IDs are reused.
  Terminal native tasks and workflows are never restarted by intake replay.
- A CodeTether task row without its fire-and-forget run is repaired under the
  existing task-creation advisory lock, without repeating started/terminal work.
- Handoff results are checkpointed before the final acknowledgement. A failed
  comment POST does not redispatch work. Provider comment markers are checked
  across all pages and must be authored by the configured bot identity.
- Pending work uses capped backoff and bounded per-attempt execution. Error
  class/status and attempt count remain inspectable; raw provider errors are
  not copied into the inbox or workflow history.

This is durable at-least-once processing with idempotent handoffs, not a claim of
distributed exactly-once side effects. Database backups and normal provider
retention still matter. A provider outage retains pending work; it cannot be
turned into success by a webhook HTTP 200 alone.

## Inspecting pending intake

Use an authorized CodeTether database session to inspect
`forgejo_webhook_inbox`: `delivery_id`, `state`, `native_task_id`, `attempts`,
`error_code`, `received_at`, `updated_at`, and `next_attempt_at`. Avoid exporting
`context` or `plan` into general logs. States are `pending`, `dispatched`, and
`acknowledged`; the last state describes intake only, not completed coding work.

## Recovering pre-inbox orphan claims

Legacy `forgejo_webhook_deliveries` rows lack payloads. Do not delete them or
blindly bulk replay them. Rehydrate a named event from Forgejo, check that its
issue remains open and actionable, and refuse existing CodeTether/native work.
Run inside the configured CodeTether environment:

```bash
# Read-only eligibility check; no issue comment or task is created.
python -m a2a_server.forgejo_inbox_recovery \
  'riley/spotlessbinco#5863:issues:body'

# Explicitly enqueue that eligible request through the canonical inbox.
python -m a2a_server.forgejo_inbox_recovery \
  'riley/spotlessbinco#5863:issues:body' --enqueue
```

Enqueueing starts the normal repository-changing agent workflow. It is not a
read-only check. The legacy audit row remains intact and repeated enqueue is
idempotent. Verify the returned receipt and native task/workflow IDs afterwards.

## Rollout gate

Deploy the same reviewed server code to API and Temporal workers. Verify the
inbox table, pump, Vault Kubernetes authentication, and Temporal poller before
recovering old deliveries. Temporal handoff requires `FORGEJO_API_URL` to match
the receipt's provider; payload-derived URLs alone are insufficient because
activities load provider configuration separately. `tests/test_forgejo_inbox.py` exercises real
PostgreSQL locking/checkpoints with mocked external provider effects; its
results are not evidence of live Forgejo dispatch or completed repository work.