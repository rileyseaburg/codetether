# CodeTether Forgejo delivery retry investigation

## Superseding repair

The exception-only release patch below was rejected as insufficient. It is no
longer the webhook's production path. The current implementation commits a
durable inbox receipt, runs a restart-safe pump, fences issue ownership, pins
handoff identity, repairs partial task dispatch and refreshes Kubernetes Vault
tokens. See `docs/operations/forgejo-inbox.md` for the contract and explicit
legacy recovery command. Earlier evidence is retained, including the failed
connection-death test run and subsequent successful runs.

## Scope

The user clarified that the target is CodeTether's handling of `@codetether`,
not SpotlessBinCo's Stripe implementation. No Spotless source, billing state,
repository hooks, or customer subscriptions were changed. No issue replay ran.

## Live deployment/Argo: read-only observations

- Server: namespace `a2a-system`, pod
  `a2a-server-deployment-green-c49c45b56-gnxn9`.
- Image: `registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:main-4e0fe718d799`.
- The running server already contains `_opened_issue_context`.
- CodeTether database delivery key: `riley/spotlessbinco#5863:issues:body`.
- Claim timestamp: `2026-09-06 10:02:16.577413+00:00`.
- Read-only task query for that repo/issue returned no rows.
- Forgejo agent-task query for issue index 5863 returned an empty task list.
- Retained server logs contain Vault HTTP 403 / invalid-token failures from
  Git credential storage. They do not establish the original failure for 5863.
- Repository webhook-settings inspection was denied HTTP 403; hook delivery
  response details could not be recovered with the available integration token.

## Static/local finding and repair

The webhook stored a durable duplicate-suppression claim before dispatch,
but never released it when dispatch failed. Redelivery could therefore return
`duplicate-delivery` without ever creating a task. The repair releases owned
claims on handler exceptions/cancellation, preserves the original error, keeps
successful claims, and avoids releasing claims on unowned fail-open requests.

## Validation and remaining work

Mocked-local regression results: `pytest.xml` in this directory.
Rollout and end-to-end recovery: not-run. Existing orphan claims are not
automatically removed by this change. Credential health, controlled recovery
of the orphan delivery, and task-start evidence remain necessary for live proof.