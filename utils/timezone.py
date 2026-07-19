from datetime import datetime, timezone


def ensure_utc_datetime(value: datetime | None) -> datetime | None:
    """Normalize a datetime to timezone-aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    if value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_db_timestamp(value: datetime | None) -> datetime | None:
    """Convert a datetime to the naive UTC form used by existing timestamp columns."""
    normalized = ensure_utc_datetime(value)
    if normalized is None:
        return None
    return normalized.replace(tzinfo=None)


def utc_now() -> datetime:
    """Return the current UTC datetime as a timezone-aware value."""
    return datetime.now(timezone.utc)
