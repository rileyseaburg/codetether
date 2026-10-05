# Backend-only rehearsal — NOT an iPhone-originated task

## Verified result

- **Live deployment/Argo (local worker execution):** task
  `3df87692-22b0-4a17-8efe-18b37033fb75` returned its result through the task API.
  Model requested: `github-copilot/gpt-5-mini`.
- Worker: `wrk_1791203157_35195f4f7b97da0a`; workspace: `ios-e2e-ubuntu-dev`.
- HTML: `/home/riley/A2A-Server-MCP/artifacts/ios-e2e-web/backend-rehearsal/site/index.html`.
- LAN URL: `http://192.168.50.101:8768/`.
- SHA-256: `4a22b70ffb09b3cdd904cb34291a8cfd9136c8e73c1eacecaf9acaf2c6e8dafc`.
- User service: `codetether-ios-backend-rehearsal.service`, active; PID `893866`.
- **Static/local and live deployment/Argo:** `node scripts/ios_backend_rehearsal.cjs verify`
  exited 0. The returned task result contains the matching file, URL and hash.
  Both `/` and `/index.html` returned the exact on-disk bytes and HTTP 200;
  an unrelated path returned 404. Process arguments point into this directory.
- A separate GET from `ssh mac` produced the same SHA-256, confirming LAN access.

`receipt.json`, `latest-task.json`, and `http-proof.json` contain the concrete
task and verification records. The HTML explicitly states it was not submitted
from an iPhone. These records do not establish phone authentication or submission.

## Recovery history retained

Earlier task receipts and failed/unverified results are preserved here. They
include invalid Bedrock credentials, an unavailable Copilot provider in the
worker's expired-Vault environment, misplaced files, a missing user bus, and an
orphan server process. No failed attempt was counted as a successful rehearsal.
The final corrective task replaced the rehearsal-owned process with the unit
above. Original misplaced files remain under the workspace's nested artifacts.

## Remaining gate and operational note

The physical iPhone remains unavailable by both CoreDevice ID and hardware UDID;
the latest native checks are in the parent evidence directory. The prepared
native Tasks-screen build still requires installation and manual sign-in.
The worker's repaired Vault credential is deliberately scoped to provider reads,
renewable with a 24-hour lease and 72-hour maximum lifetime; it is not a permanent
credential-management solution. No administrator token was copied to the worker.