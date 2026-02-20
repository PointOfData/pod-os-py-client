"""Pod-OS message utility functions."""

from datetime import datetime

__all__ = ["get_timestamp", "get_timestamp_from_datetime"]


def get_timestamp() -> str:
    """Get current timestamp in POSIX microseconds format.

    Returns timestamp as string with 6 decimal places and +/- sign
    relative to January 1, 1970 00:00:00 UTC.

    Returns:
        Timestamp string (e.g., "+1708185600.123456")

    Example:
        >>> ts = get_timestamp()
        >>> ts.startswith('+')
        True
        >>> len(ts.split('.')[1])
        6
    """
    now = datetime.now()
    # Convert to microseconds as float
    timestamp = now.timestamp()

    # Format with exactly 6 decimal places and +/- sign
    if timestamp >= 0:
        return f"+{timestamp:.6f}"
    return f"{timestamp:.6f}"


def get_timestamp_from_datetime(dt: datetime) -> str:
    """Convert datetime to POSIX microsecond timestamp string.

    Args:
        dt: Datetime object to convert

    Returns:
        Timestamp string with 6 decimal places and +/- sign

    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2024, 12, 25, 15, 30, 45, 123456, tzinfo=timezone.utc)
        >>> ts = get_timestamp_from_datetime(dt)
        >>> ts.startswith('+')
        True
    """
    timestamp = dt.timestamp()

    # Format with exactly 6 decimal places and +/- sign
    if timestamp >= 0:
        return f"+{timestamp:.6f}"
    return f"{timestamp:.6f}"
