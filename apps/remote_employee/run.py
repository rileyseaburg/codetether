"""Run Remote Employee using credentials from the existing LiveKit cluster.

Credentials stay in process memory and are never printed or written to disk.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from pathlib import Path

import yaml


def load_livekit_from_cluster(namespace: str) -> None:
    """Load the first configured LiveKit key pair without printing it."""
    command = [
        'kubectl',
        '-n',
        namespace,
        'get',
        'configmap',
        'livekit-server',
        '-o',
        'json',
    ]
    try:
        raw = subprocess.run(
            command, check=True, capture_output=True, text=True
        ).stdout
        data = json.loads(raw).get('data', {})
        config = yaml.safe_load(data.get('config.yaml', '')) or {}
        keys = config.get('keys') or {}
        api_key, api_secret = next(iter(keys.items()))
    except (
        subprocess.CalledProcessError,
        ValueError,
        StopIteration,
        TypeError,
    ) as error:
        raise RuntimeError(
            f'Could not load LiveKit configuration from namespace {namespace}'
        ) from error
    os.environ.setdefault('LIVEKIT_API_KEY', str(api_key))
    os.environ.setdefault('LIVEKIT_API_SECRET', str(api_secret))
    os.environ.setdefault('LIVEKIT_PUBLIC_URL', 'wss://live.quantum-forge.net')


def main() -> None:
    """Validate startup security, load configuration, and serve the app."""
    parser = argparse.ArgumentParser(description='Run the Remote Employee MVP')
    parser.add_argument('--namespace', default='quantum-forge')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=8090, type=int)
    parser.add_argument('--no-cluster-config', action='store_true')
    args = parser.parse_args()
    remote_auth = os.getenv('REMOTE_EMPLOYEE_ADMIN_TOKEN')
    trusted_lan = os.getenv('REMOTE_EMPLOYEE_TRUSTED_LAN', '').lower() in {
        '1',
        'true',
        'yes',
    }
    if args.host not in {'127.0.0.1', '::1', 'localhost'} and not (
        remote_auth or trusted_lan
    ):
        parser.error(
            'Set REMOTE_EMPLOYEE_ADMIN_TOKEN or REMOTE_EMPLOYEE_TRUSTED_LAN=1 '
            'for a non-loopback host'
        )
    if not args.no_cluster_config:
        load_livekit_from_cluster(args.namespace)

    repository = Path(__file__).resolve().parents[2]
    if str(repository) not in sys.path:
        sys.path.insert(0, str(repository))
    import uvicorn  # noqa: PLC0415

    from apps.remote_employee.server import create_app  # noqa: PLC0415

    print(f'Remote Employee: http://{args.host}:{args.port}')
    print(
        'LiveKit: wss://live.quantum-forge.net (credentials loaded in memory)'
    )
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == '__main__':
    main()
