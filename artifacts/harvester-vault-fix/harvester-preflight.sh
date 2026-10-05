#!/bin/sh
# Read-only worker contract check; never installs tools or accesses credentials.
# Run as the worker UID. Supply the assigned checkout and expected branch.
set -u
failed=0
for tool in git ssh bash curl jq vault forgejo-cli node npm pnpm python3 rg make cc rustyroad; do
    if command -v "$tool" >/dev/null 2>&1; then
        printf 'TOOL_OK %s\n' "$tool"
    else
        printf 'TOOL_MISSING %s\n' "$tool"
        failed=1
    fi
done
if [ "$#" -ne 2 ]; then
    printf 'USAGE: sh harvester-preflight.sh CHECKOUT EXPECTED_BRANCH\n'
    exit 2
fi
checkout=$1
expected_branch=$2
if [ ! -d "$checkout" ]; then
    printf 'CHECKOUT_MISSING %s\n' "$checkout"
    failed=1
elif ! git -C "$checkout" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'CHECKOUT_INVALID %s\n' "$checkout"
    failed=1
else
    actual_branch=$(git -C "$checkout" symbolic-ref --quiet --short HEAD 2>/dev/null || true)
    if [ "$actual_branch" != "$expected_branch" ]; then
        printf 'BRANCH_MISMATCH expected=%s actual=%s\n' "$expected_branch" "$actual_branch"
        failed=1
    else
        printf 'CHECKOUT_OK %s branch=%s\n' "$checkout" "$actual_branch"
    fi
fi
if [ "$failed" -ne 0 ]; then
    printf 'PREFLIGHT_FAILED: do not dispatch repository-changing work\n'
else
    printf 'PREFLIGHT_OK: availability only; auth and tool versions still need checks\n'
fi
exit "$failed"