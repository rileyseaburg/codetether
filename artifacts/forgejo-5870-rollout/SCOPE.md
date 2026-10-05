# Current user scope and access constraints

- Repair CodeTether's live Forgejo intake; Spotless incident text is reproduction
  context, not authorization for manual Spotless source/billing changes.
- User explicitly prohibits mux. Do not list, read, message, steer, or interact
  with mux sessions, including via agent tools that route to mux.
- Continue using the CodeTether repository, Forgejo CI, and Kubernetes interfaces.
- A prior agent.message routed into mux; no further such calls are permitted.

Rollout review: https://forgejo.quantum-forge.io/riley/codetether/pulls/45
The live image observed before rollout was main-4e0fe718d799; issue 5870 had a
legacy delivery claim and no task at the time of inspection.