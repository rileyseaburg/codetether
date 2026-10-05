"""Maintain one Gemini Live process for every Remote Employee record."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
import urllib.request

from typing import Any


def employees(api_base: str) -> list[dict[str, Any]]:
    """Read the authoritative employee roster from the local control plane."""
    with urllib.request.urlopen(
        f'{api_base.rstrip("/")}/api/company', timeout=10
    ) as response:
        return json.load(response)['employees']


def worker_command(employee: dict[str, Any], api_base: str) -> list[str]:
    """Serialize an employee profile as argv without invoking a shell."""
    profile = employee['profile']
    return [
        sys.executable,
        '-m',
        'apps.remote_employee.gemini_live_bridge',
        '--employee-id',
        employee['id'],
        '--name',
        employee['name'],
        '--role',
        employee['role'],
        '--goal',
        employee['goal'],
        '--voice',
        profile['voice'],
        '--temperament',
        profile['temperament'],
        '--cadence',
        profile['cadence'],
        '--collaboration-style',
        profile['collaboration_style'],
        '--greeting',
        profile['greeting'],
        '--api-base',
        api_base,
        '--wait-for-ceo',
        '86400',
        '--stay-seconds',
        '86400',
    ]


async def run(api_base: str, interval: float) -> None:
    """Reconcile employee records to child voice processes until stopped."""
    if not os.getenv('GOOGLE_API_KEY'):
        raise RuntimeError('GOOGLE_API_KEY must be injected from Vault')
    processes: dict[str, asyncio.subprocess.Process] = {}
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stopping.set)
    try:
        while not stopping.is_set():
            try:
                roster = await asyncio.to_thread(employees, api_base)
            except Exception as error:
                print(f'roster unavailable: {error}', flush=True)
                await asyncio.sleep(interval)
                continue
            desired = {employee['id']: employee for employee in roster}
            for employee_id, process in list(processes.items()):
                if process.returncode is not None or employee_id not in desired:
                    if process.returncode is None:
                        process.terminate()
                        await process.wait()
                    processes.pop(employee_id)
            for employee_id, employee in desired.items():
                if employee_id in processes or not employee.get('profile'):
                    continue
                process = await asyncio.create_subprocess_exec(
                    *worker_command(employee, api_base)
                )
                processes[employee_id] = process
                print(
                    f'started employee={employee["name"]} '
                    f'voice={employee["profile"]["voice"]} pid={process.pid}',
                    flush=True,
                )
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stopping.wait(), timeout=interval)
    finally:
        for process in processes.values():
            if process.returncode is None:
                process.terminate()
        await asyncio.gather(
            *(process.wait() for process in processes.values()),
            return_exceptions=True,
        )


def main() -> None:
    """Run the roster reconciler with environment-driven local endpoints."""
    api_base = os.getenv('REMOTE_EMPLOYEE_API', 'http://127.0.0.1:8090')
    interval = float(os.getenv('REMOTE_EMPLOYEE_RECONCILE_SECONDS', '5'))
    asyncio.run(run(api_base, interval))


if __name__ == '__main__':
    main()
