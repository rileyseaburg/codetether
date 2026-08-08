"""TLS-verified, rotating JWKS client for SPIRE."""

import json
import threading
import time

from typing import cast
from urllib import request

from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from a2a_server.spiffe_bundle import trust_context


class SpiffeJwkClient(PyJWKClient):
    """Fetch JWKS with system roots plus the current SPIRE trust bundle."""

    def fetch_data(self) -> dict[str, object]:
        try:
            jwks_request = request.Request(self.uri, headers=self.headers)
            with request.urlopen(
                jwks_request, context=trust_context(), timeout=self.timeout
            ) as response:
                data = json.load(response)
        except (OSError, TimeoutError, ValueError) as exc:
            raise PyJWKClientConnectionError(
                f'Failed to fetch SPIRE JWKS: {exc}'
            ) from exc
        if self.jwk_set_cache is not None:
            self.jwk_set_cache.put(data)
        return data


_CACHE: dict[str, object] = {'client': None, 'at': 0.0, 'url': ''}
_LOCK = threading.Lock()


def get_client(url: str, ttl: int) -> PyJWKClient:
    """Return a cached client, refreshing it after the configured TTL."""
    now = time.monotonic()
    with _LOCK:
        expired = now - float(_CACHE['at']) > ttl
        if _CACHE['client'] is None or _CACHE['url'] != url or expired:
            client = SpiffeJwkClient(url, cache_keys=True)
            _CACHE.update(client=client, at=now, url=url)
        return cast(PyJWKClient, _CACHE['client'])
