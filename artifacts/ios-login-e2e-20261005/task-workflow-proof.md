# Explicit Tasks-screen workflow

## Implementation

- `CommandView` now exposes **Tasks & Responses**, opening `TasksView`.
- `CreateTaskSheet` calls `MonitorViewModel.createTask` and the existing task API.
- `Codebase.workerId` is decoded from the selected workspace's `worker_id`.
- Creation sends `metadata.target_worker_id`, while preserving title, prompt,
  priority, and optional context. The server's task ID is retained unchanged.
- Each task card offers **View response**. `TaskResponseView` displays that ID,
  polls `GET /v1/agent/tasks/{id}`, and shows that task's status and result text.
- No guest-mode, login bypass, fabricated task ID, or synthetic UI result was added.

## Evidence and limits

- **Mocked local:** `task-workflow-tests.xcresult` reports 6 tests, 0 failures,
  0 skips on iOS Simulator 18.6. The new test calls the actual view-model and
  client, rejects missing/wrong worker routing in the URLProtocol fixture,
  and verifies the same task ID is updated with the returned response.
- **Static/local:** the signed iOS build and deep/strict codesign check exited 0;
  see `prepared-task-workflow-build.xcresult`. This build is not yet on the phone.
- **Real platform upload/device check:** `device-list-hardware-check.json`
  records Riley's phone unavailable. The explicit hardware-UDID lock-state query
  returned CoreDevice 1000, device not found; see `hardware-udid-lock-check.json`.
- Authentication, phone task submission, local-agent execution, HTML hosting,
  and the on-phone response are still pending. Simulator tests prove none of them.