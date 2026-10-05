# Trusted Forgejo PR publication recovery

## Live Forgejo evidence

- Original native task: `riley/spotlessbinco` task 467, issue 5892.
- Completed CodeTether task: `7818974d-d7d8-407e-9857-7b55e217f690`.
- Remote branch: `codetether/issue-5892`.
- Verified head before and after publication:
  `b4b7b201fe0b48bdf3776afc539589c0018a7e52`.
- Published PR: https://forgejo.quantum-forge.io/riley/spotlessbinco/pulls/5897
- Replaying publication returned PR 5897, with no second creation.
- Issue update:
  https://forgejo.quantum-forge.io/riley/spotlessbinco/issues/5892#issuecomment-16176
- The PR body explicitly identifies compilation/tests/runtime verification as
  not run by the publisher. The original failed workflow attempt was not
  relabelled as successful. No code task was rerun or Git ref rewritten.
- No Vault policies were widened and no secret was sent to the model.

## Live deployment/Argo

- API and Temporal worker deployments in `a2a-system` rolled onto
  `registry.quantum-forge.net/cluster-ci-cache/a2a-server-mcp:publish-e9d28ce0a1de`.
- Image digest:
  `sha256:0219fcbc9a7607dc19fced5b2294d2241fe5896f62d2327415161a98210abd5e`.
- API pod used for publication: `a2a-server-deployment-green-66f84fb8f4-jlwmm`.
- Harvester model, existing worker tools, PR 5873 pause, and disabled unsolicited
  status remediation were preserved.

## Validation and failure attribution

- Focused CI-like / mocked local: 73 checks passed; includes real PostgreSQL
  publication locking/output-checkpoint coverage with mocked provider calls.
  Evidence: `tests-indexed.xml`.
- The initial all-state historical PR scan timed out before publication.
  The recovery uses Forgejo's indexed commit-to-PR lookup, output checkpoints,
  and open-PR reconciliation instead. Earlier test artifacts are preserved.
- Docker build, registry push, and runtime import smoke were observed exit 0.
- This is PR-publication proof, not proof that the Spotless fix compiles,
  resolves the production incident, or has been deployed.