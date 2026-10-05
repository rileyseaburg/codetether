#!/usr/bin/env python3
"""Regenerate the act-runner Deployment with a live VAULT_TOKEN refresh loop.

Reads the live deployment dump, rewrites the runner entrypoint so job-env's
VAULT_TOKEN refreshes from the vault-agent sink (act_runner re-reads env_file
per job), and writes the patched manifest for kubectl apply.
"""

from pathlib import Path

import yaml


OLD = (
    "printf 'VAULT_TOKEN=%s\\n' "
    '"$(cat /vault/runtime/token)" >> /data/job-env'
)
REFRESH = OLD + """
# Keep VAULT_TOKEN in job-env fresh: the vault-agent renews the sink token
# for the pod lifetime, but this file is a one-shot snapshot. act_runner
# re-reads env_file per job, so a background refresh loop keeps every job
# working instead of only the first hour after pod start (spotlessbinco PR
# #5848 review failed 403 invalid-token 2h15m after pod start).
refresh_job_env() {
  tmp=/data/.job-env.tmp
  { grep -v '^VAULT_TOKEN=' /data/job-env; \\
    printf 'VAULT_TOKEN=%s\\n' "$(cat /vault/runtime/token)"; } > "$tmp" \\
    && cat "$tmp" > /data/job-env && rm -f "$tmp"
}
( while true; do sleep 240; refresh_job_env || true; done ) &"""
EXEC = "exec act_runner --config /etc/act-runner/config.yaml daemon"


def patch(live: dict) -> dict:
    """Return the deployment with the runner entrypoint refresh loop added."""
    live.pop('status', None)
    live['metadata'].pop('annotations', None)
    for c in live['spec']['template']['spec']['containers']:
        if c['name'] == 'runner':
            args = c['args'][0]
            assert OLD in args and EXEC in args
            c['args'] = [args.replace(OLD, REFRESH)]
    return live


def main() -> None:
    """Regenerate the patched manifest from the live deployment dump."""
    src = Path('forgejo-act-runner-dind-live.yaml')
    dst = Path('forgejo-act-runner-dind-fixed.yaml')
    with src.open() as f:
        live = yaml.safe_load(f)
    with dst.open('w') as f:
        yaml.dump(patch(live), f, default_flow_style=False)
    print(f'patched manifest written: {dst}')


if __name__ == '__main__':
    main()
