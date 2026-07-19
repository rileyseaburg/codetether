"""Worker heartbeat freshness policy."""

from datetime import UTC, datetime


def is_recent(value: str | None, max_age_seconds: int = 120) -> bool:
    """Return whether a serialized heartbeat is within the active window."""
    if not value:
        return False
    try:
        normalized = value.replace('Z', '+00:00')
        last = datetime.fromisoformat(normalized)
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return (datetime.now(UTC) - last).total_seconds() <= max_age_seconds
    except ValueError:
        return False
