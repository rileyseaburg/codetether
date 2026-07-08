#!/usr/bin/env bash
# Open a temporary PR, invoke the CodeTether synchronous review stream, print
# worker output live, then close/delete the temporary PR branch.
#
# Required:
#   CODETETHER_SYNC_STREAM_URL  e.g. https://a2a.example/v1/agent/tasks/sync/stream
#   CODETETHER_AUTH_TOKEN       bearer token for the A2A API
# Optional:
#   CODETETHER_PR_BASE          base branch (default: main)
#   CODETETHER_PR_TITLE         PR title
#   CODETETHER_REVIEW_TIMEOUT   seconds to wait server-side (default: 900)
#   CODETETHER_DRY_RUN          if 1, create/close the PR but skip API call

set -euo pipefail

BASE_BRANCH="${CODETETHER_PR_BASE:-main}"
RUN_ID="${CODETETHER_RUN_ID:-$(date +%s)}"
BRANCH="codetether-sync-review-smoke-${RUN_ID}"
TITLE="${CODETETHER_PR_TITLE:-CodeTether sync review smoke ${RUN_ID}}"
TIMEOUT_SECONDS="${CODETETHER_REVIEW_TIMEOUT:-900}"
STREAM_URL="${CODETETHER_SYNC_STREAM_URL:-}"
AUTH_TOKEN="${CODETETHER_AUTH_TOKEN:-}"
DRY_RUN="${CODETETHER_DRY_RUN:-0}"
TMPFILE=""
PR_NUMBER=""

cleanup() {
  set +e
  if [[ -n "${PR_NUMBER}" ]]; then
    gh pr close "${PR_NUMBER}" --delete-branch --comment "Closing CodeTether sync review smoke PR ${RUN_ID}." >/dev/null 2>&1
  fi
  git push origin --delete "${BRANCH}" >/dev/null 2>&1
  git checkout - >/dev/null 2>&1 || true
  git branch -D "${BRANCH}" >/dev/null 2>&1 || true
  [[ -n "${TMPFILE}" ]] && rm -f "${TMPFILE}"
}
trap cleanup EXIT

if [[ "${DRY_RUN}" != "1" ]]; then
  if [[ -z "${STREAM_URL}" ]]; then
    echo "CODETETHER_SYNC_STREAM_URL is required unless CODETETHER_DRY_RUN=1" >&2
    exit 2
  fi
  if [[ -z "${AUTH_TOKEN}" ]]; then
    echo "CODETETHER_AUTH_TOKEN is required unless CODETETHER_DRY_RUN=1" >&2
    exit 2
  fi
fi

current_branch=$(git branch --show-current)
git fetch origin "${BASE_BRANCH}" >/dev/null
git checkout -B "${BRANCH}" "origin/${BASE_BRANCH}" >/dev/null
mkdir -p .codetether/smoke
printf 'CodeTether sync review smoke %s\n' "${RUN_ID}" > ".codetether/smoke/${RUN_ID}.txt"
git add ".codetether/smoke/${RUN_ID}.txt"
git commit -m "test: codetether sync review smoke ${RUN_ID}" >/dev/null
git push -u origin "${BRANCH}" >/dev/null

PR_URL=$(gh pr create \
  --base "${BASE_BRANCH}" \
  --head "${BRANCH}" \
  --title "${TITLE}" \
  --body "Temporary CodeTether sync review smoke PR. This PR is created and closed automatically." \
)
PR_NUMBER=$(gh pr view "${PR_URL}" --json number --jq '.number')
HEAD_SHA=$(gh pr view "${PR_URL}" --json headRefOid --jq '.headRefOid')
REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')

echo "SMOKE_PR_URL=${PR_URL}"
echo "SMOKE_PR_NUMBER=${PR_NUMBER}"
echo "SMOKE_PR_HEAD_SHA=${HEAD_SHA}"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "DRY_RUN=1; skipping sync-stream API call"
  exit 0
fi

TMPFILE=$(mktemp)
jq -n \
  --arg title "CodeTether PR Review" \
  --arg prompt "Review PR ${PR_URL} at head ${HEAD_SHA}. Return APPROVED, CHANGES_REQUESTED, or BLOCKED with validation evidence." \
  --arg repo "${REPO}" \
  --arg pr_url "${PR_URL}" \
  --arg head_sha "${HEAD_SHA}" \
  --argjson pr_number "${PR_NUMBER}" \
  --argjson timeout_seconds "${TIMEOUT_SECONDS}" \
  '{
    title: $title,
    prompt: $prompt,
    agent_type: "review",
    priority: 100,
    workspace_id: "global",
    timeout_seconds: $timeout_seconds,
    poll_interval_seconds: 0.5,
    metadata: {
      source: "codetether-sync-review-smoke",
      workflow_stage: "review",
      repo: $repo,
      pr_url: $pr_url,
      pr_number: $pr_number,
      head_sha: $head_sha
    }
  }' > "${TMPFILE}"

terminal_event=$(
  curl -fsS -N \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -H 'Content-Type: application/json' \
    --data-binary "@${TMPFILE}" \
    "${STREAM_URL}" \
  | tee /dev/stderr \
  | jq -cr 'select(.event == "done" or .event == "timeout")' \
  | tail -n 1
)

if [[ -z "${terminal_event}" ]]; then
  echo "No terminal sync-stream event received" >&2
  exit 1
fi

success=$(jq -r '.success // false' <<<"${terminal_event}")
event=$(jq -r '.event' <<<"${terminal_event}")
status=$(jq -r '.status // "unknown"' <<<"${terminal_event}")
echo "TERMINAL_EVENT=${event}"
echo "TERMINAL_STATUS=${status}"
echo "TERMINAL_SUCCESS=${success}"

if [[ "${event}" != "done" || "${success}" != "true" ]]; then
  exit 1
fi
