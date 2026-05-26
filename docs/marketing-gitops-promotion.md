# Marketing-site GitOps image promotion

CodeTether promotes `marketing-site/` through Git, not mutable cluster state.

## Promotion flow

1. A push to `main` that changes `marketing-site/**` starts **Marketing GitOps Image Promotion**.
2. The workflow builds and pushes `us-central1-docker.pkg.dev/spotlessbinco/codetether/codetether-marketing:<branch>-<12-char-sha>`.
3. The workflow commits the new tag into `deploy/argocd/marketing.yaml`.
4. ArgoCD reads `main`, syncs `codetether-marketing`, and remains the deployment authority.
5. The workflow records a durable artifact containing:
   - image tag and full image reference
   - source Git commit
   - GitOps manifest diff / promotion commit
   - ArgoCD app health output when Argo credentials are available
   - `https://codetether.run` HTTP smoke status and response body

The pipeline intentionally has path filters so unrelated app changes do not build or promote the marketing image.

## Rollback by Git

Rollback is a normal GitOps change:

1. Find the last known-good tag in Git history or a prior workflow artifact.
2. Edit `deploy/argocd/marketing.yaml`:

   ```yaml
   image:
     repository: us-central1-docker.pkg.dev/spotlessbinco/codetether/codetether-marketing
     tag: main-<prior-good-sha>
   ```

3. Commit and push the rollback to `main`, or open a small PR and merge it:

   ```bash
   git checkout -b rollback/marketing-<tag>
   $EDITOR deploy/argocd/marketing.yaml
   git add deploy/argocd/marketing.yaml
   git commit -m "revert(marketing): roll back image to <tag>"
   git push origin rollback/marketing-<tag>
   gh pr create --base main --head rollback/marketing-<tag> \
     --title "Rollback marketing image to <tag>" \
     --body "GitOps rollback for codetether-marketing. ArgoCD remains deployment authority."
   ```

4. Let ArgoCD sync from Git. Do not use `kubectl set image`, local `helm upgrade`, or manual live-state mutation for rollback.
5. Confirm the ArgoCD app is healthy and fetch `https://codetether.run` after sync.
