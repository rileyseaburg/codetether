# A2A Monitor app/platform integration contract

The native app and the API/worker execution path must be evaluated together.

## Agent, project, model and conversation identity

- Discover live workers through `GET /v1/agent/workers?online_only=true`. Conversation workers advertise `session-context`.
- A shared clone root does not make every descendant registration that worker's project. Explicit workspace ownership wins; exact advertised folders may supply missing ownership.
- Decode both legacy string model IDs and structured model catalog entries. Keep provider-qualified IDs, including nested OpenRouter IDs, unchanged.
- New Session offers a searchable model picker. It must not dispatch an empty model and silently invoke a worker's potentially disabled default backend.
- Persist the chosen model per work session. Changing models is permitted only between turns.
- Submit to the selected workspace with `target_worker_id`, `target_agent_name`, and a stable `context_id`. Follow-ups use the worker's actual session ID, or the pinned context ID where required by the worker protocol.
- A failed turn and its task ID remain visible. Retry creates a new task in the same conversation; it does not overwrite the failed record.
- A returned error is not success merely because another field says `completed`.
- Do not reinterpret a disabled provider backend as proof that a particular model is unavailable. Show actionable configuration/model-selection guidance and retain technical details.
- Build workers may edit files and finalize Git changes. The UI must disclose this behavior and show the selected directory.

## Regression and release gates

- **Mocked local:** `WorkerModelOptionTests`, `ProjectDiscoveryTests`, `WorkSessionTests`, and `TaskHTTPContractTests` cover discovery, canonical IDs, explicit/default model selection, failed-turn recovery, conversation identity and HTTP errors.
- **Live deployment/simulator:** `WorkSessionUITests` uses an isolated service-auth bridge, not user credentials. It must tap a model option (not type an ID), submit real work, receive two replies, and verify worker-side model/workspace/session identity and both terminal statuses.
- **Focused CI-like:** build the device app, sign with Vault distribution material in an isolated keychain, verify deep/strict signatures and registered-device provisioning, and remove temporary private-key material.
- **Live deployment/Argo:** publish the IPA on NAS, update its HTTPS OTA manifest/landing page, and verify public bytes/hash, range requests and download allowlisting.
- **Real platform upload:** install as an in-place update on the exact paired iPhone; inspect the installed build and successful process launch. This alone does not prove a signed-in user task.
- Never enter the user's passwords, device passcode or OAuth codes. When the phone is unreachable or sign-in is required, state that boundary explicitly.

## Build 5 evidence

- Reported failure: task `3541aeb2-304e-4010-9685-f920c39a515e` had no requested/stored model and failed against a disabled OpenAI Codex ChatGPT backend. Exact resolved model was not emitted; do not invent one.
- Live picker flow: `artifacts/agent-workflow-validation/app-api-repair/live-ui-v11/proof.json`.
- Release regression/signing/download: `artifacts/agent-workflow-validation/delivery-v5/`.
- The reported Spotlessbinco project's stale worker binding was handed off only after checking the former worker was not online, no task was running, and the interactive worker advertised the exact local folder. Project files were not modified.
- Build 5 was published. Direct installation was blocked because CoreDevice reported Riley's iPhone unavailable; do not claim the physical device was updated.