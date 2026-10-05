"""Temporal configuration and lazy client lifecycle."""

from __future__ import annotations

import asyncio
import os

from dataclasses import dataclass
from pathlib import Path

from temporalio.client import Client, TLSConfig


@dataclass(frozen=True)
class TemporalSettings:
    enabled: bool
    address: str
    namespace: str
    task_queue: str
    tls_cert_path: str
    tls_key_path: str
    server_name: str

    @classmethod
    def from_env(cls) -> 'TemporalSettings':
        return cls(
            enabled=os.environ.get('FORGEJO_TEMPORAL_ENABLED', 'false').lower()
            in {'1', 'true', 'yes'},
            address=os.environ.get('TEMPORAL_ADDRESS', 'temporal:7233').strip(),
            namespace=os.environ.get('TEMPORAL_NAMESPACE', 'default').strip(),
            task_queue=os.environ.get(
                'TEMPORAL_FORGEJO_TASK_QUEUE', 'codetether-forgejo-agent'
            ).strip(),
            tls_cert_path=os.environ.get('TEMPORAL_TLS_CERT', '').strip(),
            tls_key_path=os.environ.get('TEMPORAL_TLS_KEY', '').strip(),
            server_name=os.environ.get('TEMPORAL_TLS_SERVER_NAME', '').strip(),
        )


def temporal_settings() -> TemporalSettings:
    """Read current settings so tests and runtime flags remain dynamic."""
    return TemporalSettings.from_env()


def _tls_config(settings: TemporalSettings) -> TLSConfig | bool:
    if not settings.tls_cert_path and not settings.tls_key_path:
        return False
    if not settings.tls_cert_path or not settings.tls_key_path:
        raise RuntimeError(
            'TEMPORAL_TLS_CERT and TEMPORAL_TLS_KEY must be configured together'
        )
    return TLSConfig(
        client_cert=Path(settings.tls_cert_path).read_bytes(),
        client_private_key=Path(settings.tls_key_path).read_bytes(),
        domain=settings.server_name or None,
    )


_CLIENT: Client | None = None
_CLIENT_KEY: tuple[str, str, str, str, str] | None = None
_CLIENT_LOCK = asyncio.Lock()


async def get_temporal_client() -> Client:
    """Return one process-local Temporal client for the active configuration."""
    global _CLIENT, _CLIENT_KEY
    settings = temporal_settings()
    if not settings.enabled:
        raise RuntimeError('Forgejo Temporal orchestration is disabled')
    key = (
        settings.address,
        settings.namespace,
        settings.tls_cert_path,
        settings.tls_key_path,
        settings.server_name,
    )
    async with _CLIENT_LOCK:
        if _CLIENT is None or _CLIENT_KEY != key:
            _CLIENT = await Client.connect(
                settings.address,
                namespace=settings.namespace,
                tls=_tls_config(settings),
            )
            _CLIENT_KEY = key
        return _CLIENT


def reset_temporal_client() -> None:
    """Forget the cached client; intended for tests and controlled shutdown."""
    global _CLIENT, _CLIENT_KEY
    _CLIENT = None
    _CLIENT_KEY = None
