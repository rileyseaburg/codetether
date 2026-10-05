# UI redesign preview — not deployed

This pass changes the information hierarchy and the main screens, not just
error handling. Whether the design feels usable is a user judgment; test
counts are not a substitute for looking at the screens.

## Look at the change

- [Before/after Tasks](tasks-before-after.png): same real task, previous and
  redesigned local UI. Original screenshots are preserved; only comparison
  headings were added to the composite.
- [Workspaces](light/workspaces-desktop.png)
- [Workspace search](light/workspace-search.png)
- [Tasks](light/tasks-desktop.png)
- [Task result](light/task-result-desktop.png)
- [Conversations](light/conversations-desktop.png)
- Mobile: [Workspaces](light/workspaces-mobile.png), [Tasks](light/tasks-mobile.png),
  [Conversations](light/conversations-mobile.png).

## Visible changes

1. Five primary navigation destinations. Billing, Settings, and Setup guide are
   separate utilities. Every other destination remains under More tools; no
   orange New badges or duplicate settings gear.
2. Neutral sidebar/header surfaces and quieter selection styling.
3. Workspace home is a picker beside a single launch composer. Search, runtime
   and connection filters, eight initial rows, and Show more accommodate the
   real 1,611-record response. Advanced setup/runtime/agent controls are labelled
   disclosures instead of competing panels. No automatic wizard interruption.
4. Tasks has a clear page header, primary action, compact queue, and wider
   readable result. Brief/timeline/metadata are secondary. Mobile has an explicit
   list/detail transition and back action.
5. Sessions uses one joined list-and-conversation surface. Workspace selection
   stays visible; model/voice/RLM/resume/refresh settings are collapsed by default.
   The composer is larger and execution details do not create a third column.
6. The floating marketing chat does not cover dashboard controls.

## Evidence and limits

- **Live deployment/Argo-backed preview:** local changed UI authenticated with
  real Keycloak and read real API data from `a2a-system/a2a-server`. No fixture
  responses or test-bypass headers were used. Desktop width 1440 and mobile
  width 390 were captured. Primary navigation stayed bounded; More tools was
  collapsed; search was available; all three pages fit the mobile viewport.
  `design-preview-light-results.json`, `preview-light.log`. This is not a
  production deployment or a claim that every business flow works.
- **Mocked local:** `npm run test:ui` exited 0: 145 checks across six projects.
  `ui-final-results.json`, `ui-final.log`.
- **Static/local:** full frontend no-emit TypeScript and scoped diff checks
  exited 0. `typecheck.log`.
- The child's labelled sample-data previews and supporting artifacts are
  preserved under `workspace-home-fixture/`, separate from real-data captures.
- The current production site has not been updated. Backend blockers documented
  in `../ui-live/RESULTS.md` are not repaired by this redesign.

The preview server and owned port-forwards were stopped. The marked test account
was disabled and logged out again (`test-user-cleanup.json`). No live task,
chat, payment, or workspace creation was submitted during this preview pass.