"""
Webhook signature utilities for webhook verification.

This module provides utilities for generating and verifying HMAC-SHA256
signatures on webhook payloads, allowing automation platforms to verify
that webhooks are actually from CodeTether.
"""

import hashlib
import hmac
import os
from typing import Optional

# Webhook signing secret (configure via environment variable)
DEFAULT_WEBHOOK_SECRET = None


def get_webhook_secret() -> str:
    """Get the webhook signing secret from environment."""
    return (
        os.environ.get('CODETETHER_WEBHOOK_SECRET', DEFAULT_WEBHOOK_SECRET)
        or ''
    )


def generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload.

    Args:
        payload: The raw JSON payload string
        secret: The webhook signing secret

    Returns:
        Signature in format "sha256=<hex_digest>"
    """
    digest = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f'sha256={digest}'


def verify_webhook_signature(
    payload: str, signature: Optional[str], secret: str
) -> bool:
    """Verify webhook signature.

    Args:
        payload: The raw JSON payload string
        signature: The signature header value (e.g., "sha256=abc123...")
        secret: The webhook signing secret

    Returns:
        True if signature is valid, False otherwise
    """
    if not signature:
        return False

    expected = generate_webhook_signature(payload, secret)

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected)


class TimestampVerificationError(Exception):
    """Raised when webhook timestamp is outside valid window."""


def verify_webhook_timestamp(
    timestamp_header: Optional[str], max_age_seconds: int = 300
) -> None:
    """Verify that webhook timestamp is within acceptable window.

    Args:
        timestamp_header: The timestamp from X-CodeTether-Timestamp header
        max_age_seconds: Maximum age in seconds (default 5 minutes)

    Raises:
        TimestampVerificationError: If timestamp is missing or too old
    """
    import time

    if not timestamp_header:
        raise TimestampVerificationError('Missing timestamp header')

    try:
        timestamp = int(timestamp_header)
        current_time = int(time.time())

        # Check if timestamp is within acceptable window
        if abs(current_time - timestamp) > max_age_seconds:
            raise TimestampVerificationError(
                f'Timestamp too old or in future (max age: {max_age_seconds}s)'
            )
    except ValueError:
        raise TimestampVerificationError('Invalid timestamp format')
