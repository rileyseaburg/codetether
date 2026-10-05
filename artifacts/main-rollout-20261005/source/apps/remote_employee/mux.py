"""Authenticated client for the locally installed CodeTether mux protocol."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import shlex

from pathlib import Path
from typing import Any


ANSI_ESCAPE = re.compile(
    r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))'
)


class MuxError(RuntimeError):
    """A safe-to-display CodeTether mux operation error."""


class MuxGateway:
    """Owns mux lifecycle and window-zero CodeTether turns."""

    def __init__(
        self,
        *,
        binary: str | None = None,
        registry_dir: Path | None = None,
    ):
        self.binary = binary or os.getenv('CODETETHER_BIN', 'codetether')
        data_dir = os.getenv('CODETETHER_DATA_DIR')
        self.registry_dir = registry_dir or (
            Path(data_dir) / 'mux'
            if data_dir
            else Path.home() / '.local/share/codetether-agent/mux'
        )

    async def create(self, name: str, workspace: Path) -> None:
        process = await asyncio.create_subprocess_exec(
            self.binary,
            'mux',
            'new',
            '-d',
            name,
            str(workspace),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.wait(), timeout=15)
        if process.returncode != 0:
            raise MuxError(f'CodeTether mux exited {process.returncode}')

    async def kill(self, name: str) -> None:
        process = await asyncio.create_subprocess_exec(
            self.binary,
            'mux',
            'kill',
            name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.wait(), timeout=15)
        if process.returncode != 0:
            raise MuxError(f'CodeTether mux exited {process.returncode}')

    def _record(self, name: str) -> dict[str, Any]:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name):
            raise MuxError('Invalid mux name')
        path = self.registry_dir / f'{name}.json'
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            raise MuxError(f'Cannot read mux {name}: {error}') from error

        host, separator, port = str(record.get('address', '')).rpartition(':')
        if not separator or not port.isdigit():
            raise MuxError('Mux registry contains an invalid address')
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise MuxError('Refusing a non-loopback mux address')
        except ValueError as error:
            raise MuxError('Mux registry contains an invalid host') from error
        return record

    async def _connect(
        self, name: str
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        record = self._record(name)
        host, _, port = record['address'].rpartition(':')
        reader, writer = await asyncio.open_connection(
            host, int(port), limit=1_100_000
        )
        await self._write(
            writer, {'type': 'authenticate', 'token': record['token']}
        )
        response = await self._read(reader)
        if response.get('type') != 'authenticated':
            writer.close()
            await writer.wait_closed()
            raise MuxError(response.get('message', 'Mux authentication failed'))
        return reader, writer

    @staticmethod
    async def _write(
        writer: asyncio.StreamWriter, payload: dict[str, Any]
    ) -> None:
        writer.write(
            json.dumps(payload, separators=(',', ':')).encode() + b'\n'
        )
        await writer.drain()

    @staticmethod
    async def _read(reader: asyncio.StreamReader) -> dict[str, Any]:
        raw = await asyncio.wait_for(reader.readline(), timeout=10)
        if not raw:
            raise MuxError('Mux server closed the connection')
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise MuxError('Mux returned an invalid response') from error

    async def _request(
        self, name: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        reader, writer = await self._connect(name)
        try:
            await self._write(writer, payload)
            response = await self._read(reader)
            if response.get('type') == 'error':
                raise MuxError(response.get('message', 'Mux request failed'))
            return response
        finally:
            writer.close()
            await writer.wait_closed()

    async def start_task(  # noqa: PLR0913
        self,
        *,
        mux_name: str,
        employee_name: str,
        role: str,
        company_goal: str,
        objective: str,
        completion_marker: str,
    ) -> None:
        prompt = (
            f'You are {employee_name}, the company {role}. '
            f'The company goal is: {company_goal}\n\n'
            f'Your assigned objective is: {objective}\n\n'
            'Work autonomously in the current workspace using the available '
            'tools. Keep changes focused, validate your work, and finish with '
            'a concise report containing outcome, evidence, blockers, and any '
            'proposed delegation, meeting, or hire. Do not hire, spend money, '
            'deploy, or contact external people without '
            'explicit CEO approval.'
        )
        run_command = shlex.join([self.binary, 'run', prompt])
        marker = shlex.quote(completion_marker)
        command = f'{run_command}; rc=$?; printf "\\n{marker}:%s\\n" "$rc"\n'
        response = await self._request(
            mux_name,
            {
                'type': 'program',
                'request': {
                    'action': 'input',
                    'window_id': 0,
                    'data': list(command.encode()),
                },
            },
        )
        if response.get('type') != 'acknowledged':
            raise MuxError('Mux did not accept the CodeTether command')

    async def read_task(self, mux_name: str, offset: int) -> dict[str, Any]:
        response = await self._request(
            mux_name,
            {
                'type': 'program',
                'request': {'action': 'read', 'window_id': 0, 'offset': offset},
            },
        )
        if response.get('type') != 'program_output':
            raise MuxError('Mux did not return program output')
        raw = bytes(response.get('data', []))
        output = ANSI_ESCAPE.sub('', raw.decode(errors='replace')).replace(
            '\r', ''
        )
        return {
            'output': output,
            'offset': int(response.get('next_offset', offset)),
        }

    async def reachable(self, name: str) -> bool:
        try:
            reader, writer = await self._connect(name)
            writer.close()
            await writer.wait_closed()
            del reader
            return True
        except (TimeoutError, MuxError, OSError):
            return False
