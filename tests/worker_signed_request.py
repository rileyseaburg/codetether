"""Minimal request carrying signed headers and raw JSON bytes."""


class SignedRequest:
    """Request-like test value consumed by mutation authorization."""

    def __init__(self, headers: dict[str, str], body: bytes = b'{}') -> None:
        self.headers = headers
        self._body = body

    async def body(self) -> bytes:
        return self._body
