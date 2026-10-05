# Live UI validation — partial success, backend blockers remain

## Environment and scope

**Live deployment/Argo evidence:** changed UI at `http://localhost:3001`, real
Keycloak at `https://auth.quantum-forge.io`, and real API service
`a2a-system/a2a-server` through the application's existing proxy and an
authenticated Kubernetes port-forward. API pod:
`a2a-server-deployment-green-c49c45b56-gnxn9`, image
`registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:main-4e0fe718d799`.
The pod was ready with zero restarts in the final observation.

No API response mocks, route stubs, test-bypass headers, injected sessions,
mocked clock, or persisted browser authentication state were used. Browser
credentials were retrieved from Vault, entered into real Keycloak forms, and
never written to logs or source. Raw network traces were deliberately disabled.

The changed frontend was **not deployed**. The production marketing app remains
on its prior image/revision. See `argo-state.json`, `current-api-pod.json`, and
the source manifests for identities and exact scope.

## Proven flows and failed gates

| Deliverable | Outcome and evidence |
| --- | --- |
| Real sign-in | **Live deployment/Argo:** real authorization included PKCE S256/state; the callback established a usable authenticated session. `real-refresh-window-results.json` |
| Real automatic refresh | **Live deployment/Argo:** waited for the actual 15-minute token window; Auth.js obtained a changed token, same subject, expiry advancing from `1788726471` to `1788727317`, with no session error. `real-refresh-window-results.json` |
| Worker chat | **Live deployment/Argo:** task `ba84c696-4cbf-4848-af75-c606a6d12d59` was created by the Workers UI, returned HTTP 200, reached `completed`, and displayed `UI_LIVE_CB1E678F_CHAT`. Requested model `openai-codex:gpt-5.5-fast`; requested worker `wrk_1788615130_9a92d44ce732eae5`. `task-chat-transport-fixed-results.json`, `live-worker-chat.png` |
| Tasks dispatch | **Live deployment/Argo, broken confirmation gate:** POST `/v1/tasks/dispatch` returned HTTP 500, but persisted task `task-c6c758cfaf3d` later reached `completed` and its exact nonce result appeared in the Tasks UI. No duplicate was submitted. Logs show `TaskLimitExceeded: User not found` during queueing. This is not a passing end-to-end dispatch contract. `verified-ui-results-results.json`, `verified-task-result.png`, `current-api-errors.txt` |
| Billing display | **Live deployment/Argo:** real API returns `plan: enterprise` and `tasks_limit: -1`; corrected Settings and Billing render Enterprise and `8 / Unlimited`. This verifies response/display integration, not payment or accounting correctness. `final-session-evidence-results.json`, `verified-settings.png`, `verified-billing.png` |
| Signup | **Blocked, live deployment/Argo:** real POST `/v1/tenants/signup` returns HTTP 500 / Keycloak admin `invalid_grant`. The current API pod has neither `KEYCLOAK_ADMIN_USERNAME` nor `KEYCLOAK_ADMIN_PASSWORD` configured. No test tenant was created. `current-signup-results.json`, `current-provisioner-credential-presence.json` |
| Provider keys | **Blocked, live deployment/Argo:** `/v1/agent/api-keys` and `/v1/agent/vault/status` return HTTP 500. Runtime errors include `AttributeError: 'Security' object has no attribute 'credentials'`. This is not a provider-key rejection or proof of a model outage. `final-session-evidence-results.json`, `current-api-errors.txt` |
| Token-billing summary | **Blocked for this editor test identity, live deployment/Argo:** endpoint returned HTTP 403; no role escalation was performed. `current-api-results.json` |
| Persisted Sessions history/pagination | **Not-run live:** the nonce chat task returned null top-level workspace/session IDs, so no unrelated session history was inspected. Existing mocked-local pagination tests remain separate evidence. `final-session-evidence-results.json` |
| Stripe checkout/payment | **Not-run live:** no payment, checkout session, charge, or subscription change was attempted. |

## Fixes learned from the live run

1. Kept PKCE and state enabled in development as well as production so local
   integration cannot conceal cookie/callback failures.
2. Credential forms use native POST fallback and remain disabled until their
   client submit handlers are attached.
3. `useTenantApi` no longer converts a same-origin loopback HTTP proxy to HTTPS.
   The prior behavior caused real `ERR_SSL_PROTOCOL_ERROR` requests. Remote
   URLs still require HTTPS. The worker-chat rerun exercised this correction.
4. Normalized the real `plan` response and `-1` unlimited-quota sentinel in
   Settings and Billing. Settings now obtains usage from the usage endpoint
   instead of inventing zero values from subscription data.
5. A task dispatch HTTP 5xx now warns that the task may already exist, preserves
   the draft, and refreshes the queue rather than implying no task was created.
   This last warning branch has **mocked local** regression coverage; the
   defective backend was not deliberately invoked again to create a duplicate.

## Important diagnostic corrections

- Python HTTP probes received Cloudflare 403/1010, but **real browser** health
  probes returned HTTP 200 on both public hostnames. Do not interpret the bot
  probe result as a general public outage. `public-browser-results.json`.
- Duplicate ingress definitions advertise the same API hostname. The initial
  private route hit legacy `a2a-server/codetether-a2a-server`, whose 512Mi
  container OOM-restarted twice during the investigation. The final route uses
  Argo-managed `a2a-system/a2a-server`, not that legacy pod. The earlier proxy
  500s are not evidence that the current API endpoints all fail.
- Cross-origin authenticated fetches from localhost to the public API failed;
  successful API checks used the existing same-origin proxy to the real service.
  Public-hosted execution of the changed UI remains unverified.
- The pre-existing Vault login was rejected, and an exact-username lookup found
  no match. The shared credential was not reset. A separate marked test identity
  was created through Keycloak's admin API with the existing editor role.

## Test resources and cleanup

- Keycloak test user: `28d1d4f6-59a1-48b4-bbaa-ce5b839d90c9`.
- Credential path: `kv/codetether/playwright/ui-live-cb1e678f` (no values in artifacts).
- **Live deployment/Argo:** test user was disabled and its sessions logged out
  after validation; GET confirmed `enabled: false`. `test-user-cleanup.json`.
- Both completed task records are retained in `created-tasks.json` and the live
  service. No existing production credentials, resource limits, ingress rules, or deployments
  were changed. No payment was made.
- The local UI and owned port-forwards were stopped; generated Next types were
  restored. Earlier run logs and failure results are retained.

## Local regression evidence

- **Mocked local:** `npm run test:ui` — 128 tests, exit 0.
  `ui-final-complete-results.json`, `ui-final-complete.log`.
- **Static/local:** `npm run test:auth` — 9 helper checks, exit 0.
  `auth-final.log`.
- **Static/local:** TypeScript no-emit check and scoped diff check — exit 0.
  `typecheck-last.log`.

The result is **not full production sign-off**. Real auth, refresh, worker-chat,
task-result display, and billing-display integration have evidence; signup,
provider-key services, and safe dispatch acknowledgement require backend fixes.