"""Tests for message utility functions."""

from datetime import datetime, timezone

from pod_os_client.message.utils import get_timestamp, get_timestamp_from_datetime


def test_get_timestamp():
    """Test get_timestamp returns properly formatted timestamp."""
    ts = get_timestamp()
    
    # Should start with + for positive timestamps
    assert ts.startswith("+")
    
    # Should have exactly 6 decimal places
    parts = ts.split(".")
    assert len(parts) == 2
    assert len(parts[1]) == 6
    
    # Should be parseable as float
    float_val = float(ts)
    assert float_val > 0


def test_get_timestamp_from_datetime():
    """Test get_timestamp_from_datetime converts datetime correctly."""
    # Known datetime
    dt = datetime(2024, 12, 25, 15, 30, 45, 123456, tzinfo=timezone.utc)
    ts = get_timestamp_from_datetime(dt)
    
    # Should start with + for dates after epoch
    assert ts.startswith("+")
    
    # Should have exactly 6 decimal places
    parts = ts.split(".")
    assert len(parts) == 2
    assert len(parts[1]) == 6
    
    # Should be parseable as float
    float_val = float(ts)
    assert float_val > 0
    
    # Verify timestamp corresponds to the datetime
    # December 25, 2024, 15:30:45.123456 UTC
    expected_seconds = dt.timestamp()
    actual_seconds = float(ts)
    assert abs(actual_seconds - expected_seconds) < 0.001  # Within 1ms


def test_timestamp_negative_datetime():
    """Test timestamp for dates before epoch."""
    # Date before 1970
    dt = datetime(1960, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
    ts = get_timestamp_from_datetime(dt)
    
    # Should start with - for dates before epoch
    assert ts.startswith("-")
    
    # Should have exactly 6 decimal places
    parts = ts.split(".")
    assert len(parts) == 2
    assert len(parts[1]) == 6


def test_timestamp_microsecond_precision():
    """Test that microsecond precision is preserved."""
    dt = datetime(2024, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
    ts = get_timestamp_from_datetime(dt)
    
    # Extract fractional part
    decimal_part = ts.split(".")[1]
    
    # Should have 6 digits
    assert len(decimal_part) == 6
    
    # The microseconds should be represented
    # (exact representation may vary due to floating point)
    assert "123" in decimal_part or "124" in decimal_part  # Allow for rounding
