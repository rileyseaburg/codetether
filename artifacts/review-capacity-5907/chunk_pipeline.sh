#!/usr/bin/env bash

source "$(dirname "${BASH_SOURCE[0]}")/chunk_worker.sh"

# Reviews all exact chunks with bounded parallelism and complete aggregation.
# Parameters: manifest, stat, optional CI results, temp directory, aggregate.
# Side effects: creates per-chunk artifacts; never publishes partial approval.
# Example: run_chunk_review_pipeline manifest.json stat.txt checks.json /tmp/review result.json
run_chunk_review_pipeline() {
  local manifest="$1" stat_file="$2" check_results temp_dir aggregate
  if [[ "$#" -eq 4 ]]; then
    check_results=/dev/null temp_dir="$3" aggregate="$4"
  else
    check_results="$3" temp_dir="$4" aggregate="$5"
  fi
  local count index reviews concurrency max_count
  local -a pids=()
  concurrency="${CODETETHER_REVIEW_CHUNK_CONCURRENCY:-1}"
  max_count="${CODETETHER_REVIEW_CHUNK_MAX_COUNT:-128}"
  if [[ ! "$concurrency" =~ ^[1-4]$ || ! "$max_count" =~ ^[1-9][0-9]{0,2}$ ]]; then
    echo "Invalid bounded chunk-review scheduling configuration." >&2
    return 1
  fi
  count="$(jq -er '.chunk_count | select(type == "number" and . > 0)' "$manifest")" || return 1
  if (( count > max_count )); then
    echo "Complete review requires $count chunks; capacity is $max_count. Refusing partial review." >&2
    return 1
  fi
  reviews="$temp_dir/chunk-reviews.jsonl"
  : > "$reviews"
  for index in $(seq 1 "$count"); do
    : > "$temp_dir/chunk-review-$index.jsonl"
    (
      # Only the parent owns cleanup of the shared review directory.
      trap - EXIT
      review_exact_chunk "$manifest" "$stat_file" "$check_results" \
        "$temp_dir" "$index" "$count"
    ) &
    pids+=("$!")
    if (( ${#pids[@]} >= concurrency || index == count )); then
      wait_review_batch "${pids[@]}" || {
        echo "A chunk review failed; refusing incomplete aggregate review." >&2
        return 1
      }
      pids=()
    fi
  done
  for index in $(seq 1 "$count"); do
    [[ -s "$temp_dir/chunk-review-$index.jsonl" ]] || return 1
    cat "$temp_dir/chunk-review-$index.jsonl" >> "$reviews" || return 1
  done
  aggregate_chunk_reviews "$reviews" "$manifest" "$aggregate" || {
    echo "CodeTether chunk coverage was incomplete; refusing aggregate review." >&2
    return 1
  }
}