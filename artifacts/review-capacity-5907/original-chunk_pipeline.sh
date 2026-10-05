#!/usr/bin/env bash

# Reviews every exact chunk and produces one fail-closed aggregate response.
# Uses the immutable PR context loaded by codetether-pr-review.sh.
# Parameters: manifest, stat, CI results, temp directory, aggregate response path.
# The legacy four-argument form omits CI results for local helper validation.
run_chunk_review_pipeline() {
  local manifest="$1" stat_file="$2" check_results temp_dir aggregate
  if [[ "$#" -eq 4 ]]; then
    check_results=/dev/null temp_dir="$3" aggregate="$4"
  else
    check_results="$3" temp_dir="$4" aggregate="$5"
  fi
  local count index input payload response normalized expected_sha reviews
  count="$(jq -er '.chunk_count | select(type == "number" and . > 0)' "$manifest")"
  reviews="$temp_dir/chunk-reviews.jsonl"
  : > "$reviews"
  for index in $(seq 1 "$count"); do
    input="$temp_dir/input-$index.json"
    payload="$temp_dir/payload-$index.json"
    response="$temp_dir/response-$index.json"
    normalized="$temp_dir/normalized-$index.json"
    expected_sha="$(jq -er --argjson index "$index" \
      '.chunks[] | select(.index == $index) | .sha256' "$manifest")"
    write_chunk_review_input "$input" "$manifest" "$index" "$REPO_FULL" \
      "$PR_NUMBER" "$PR_TITLE" "$PR_BODY" "$BASE_SHA" "$HEAD_SHA" "$stat_file" \
      "$check_results"
    log "Reviewing exact diff chunk $index/$count sha256=$expected_sha"
    if [[ "$CODETETHER_URL" == */v1/agent/tasks ]]; then
      write_async_payload "$input" "$payload"
      request_async_review "$CODETETHER_URL" "$CODETETHER_TOKEN" "$payload" "$response"
    else
      write_sync_payload "$input" "$payload"
      request_sync_review "$CODETETHER_URL" "$CODETETHER_TOKEN" "$payload" "$response"
    fi
    normalize_review_response "$response" "$normalized"
    append_chunk_review "$normalized" "$expected_sha" "$index" "$reviews" || {
      echo "CodeTether chunk $index/$count did not acknowledge $expected_sha with a valid review." >&2
      return 1
    }
  done
  aggregate_chunk_reviews "$reviews" "$manifest" "$aggregate" || {
    echo "CodeTether chunk coverage was incomplete; refusing aggregate review." >&2
    return 1
  }
}
