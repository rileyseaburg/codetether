#!/usr/bin/env bash

# Reviews one exact chunk into its own result file; never appends shared output.
# Parameters: manifest, stat, CI evidence, temp directory, chunk index, count.
# Side effects: writes only this chunk's request, response and verified result.
# Example: review_exact_chunk manifest.json stat.txt checks.json /tmp/review 1 8
review_exact_chunk() {
  local manifest="$1" stat_file="$2" checks="$3" temp_dir="$4"
  local index="$5" count="$6" expected_sha
  local input="$temp_dir/input-$index.json" payload="$temp_dir/payload-$index.json"
  local response="$temp_dir/response-$index.json"
  local normalized="$temp_dir/normalized-$index.json"
  expected_sha="$(jq -er --argjson index "$index" \
    '.chunks[] | select(.index == $index) | .sha256' "$manifest")" || return 1
  write_chunk_review_input "$input" "$manifest" "$index" "$REPO_FULL" \
    "$PR_NUMBER" "$PR_TITLE" "$PR_BODY" "$BASE_SHA" "$HEAD_SHA" \
    "$stat_file" "$checks" || return 1
  log "Reviewing exact diff chunk $index/$count sha256=$expected_sha"
  if [[ "$CODETETHER_URL" == */v1/agent/tasks ]]; then
    write_async_payload "$input" "$payload" || return 1
    request_async_review "$CODETETHER_URL" "$CODETETHER_TOKEN" \
      "$payload" "$response" || return 1
  else
    write_sync_payload "$input" "$payload" || return 1
    request_sync_review "$CODETETHER_URL" "$CODETETHER_TOKEN" \
      "$payload" "$response" || return 1
  fi
  normalize_review_response "$response" "$normalized" || return 1
  append_chunk_review "$normalized" "$expected_sha" "$index" \
    "$temp_dir/chunk-review-$index.jsonl" || {
    echo "Chunk $index/$count did not acknowledge its exact hash." >&2
    return 1
  }
}

# Waits for a bounded batch; drains every launched child even if one fails.
# Parameters: process IDs. Returns nonzero if any child failed.
# Example: wait_review_batch "$first_pid" "$second_pid"
wait_review_batch() {
  local pid failed=0
  for pid in "$@"; do wait "$pid" || failed=1; done
  return "$failed"
}