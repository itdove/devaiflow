"""Tests for time expression parser."""

from datetime import datetime, timedelta

import pytest

from devflow.utils.time_parser import parse_time_expression, parse_duration


def test_parse_iso_date():
    """Test parsing ISO date format."""
    result = parse_time_expression("2025-01-15")

    assert result is not None
    assert result.year == 2025
    assert result.month == 1
    assert result.day == 15


def test_parse_iso_datetime():
    """Test parsing ISO datetime format."""
    result = parse_time_expression("2025-01-15 14:30")

    assert result is not None
    assert result.year == 2025
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 14
    assert result.minute == 30


def test_parse_today():
    """Test parsing 'today'."""
    result = parse_time_expression("today")
    now = datetime.now()

    assert result is not None
    assert result.year == now.year
    assert result.month == now.month
    assert result.day == now.day
    assert result.hour == 0
    assert result.minute == 0
    assert result.second == 0


def test_parse_yesterday():
    """Test parsing 'yesterday'."""
    result = parse_time_expression("yesterday")
    yesterday = datetime.now() - timedelta(days=1)

    assert result is not None
    assert result.year == yesterday.year
    assert result.month == yesterday.month
    assert result.day == yesterday.day
    assert result.hour == 0
    assert result.minute == 0


def test_parse_last_week():
    """Test parsing 'last week'."""
    result = parse_time_expression("last week")
    expected = datetime.now() - timedelta(weeks=1)

    assert result is not None
    # Allow 1 minute tolerance for test execution time
    assert abs((result - expected).total_seconds()) < 60


def test_parse_last_month():
    """Test parsing 'last month'."""
    result = parse_time_expression("last month")
    expected = datetime.now() - timedelta(days=30)

    assert result is not None
    # Allow 1 minute tolerance
    assert abs((result - expected).total_seconds()) < 60


def test_parse_days_ago():
    """Test parsing 'N days ago'."""
    result = parse_time_expression("3 days ago")
    expected = datetime.now() - timedelta(days=3)

    assert result is not None
    assert abs((result - expected).total_seconds()) < 60


def test_parse_weeks_ago():
    """Test parsing 'N weeks ago'."""
    result = parse_time_expression("2 weeks ago")
    expected = datetime.now() - timedelta(weeks=2)

    assert result is not None
    assert abs((result - expected).total_seconds()) < 60


def test_parse_months_ago():
    """Test parsing 'N months ago'."""
    result = parse_time_expression("1 month ago")
    expected = datetime.now() - timedelta(days=30)

    assert result is not None
    assert abs((result - expected).total_seconds()) < 60


def test_parse_hours_ago():
    """Test parsing 'N hours ago'."""
    result = parse_time_expression("5 hours ago")
    expected = datetime.now() - timedelta(hours=5)

    assert result is not None
    assert abs((result - expected).total_seconds()) < 60


def test_parse_singular_units():
    """Test parsing with singular units."""
    result_day = parse_time_expression("1 day ago")
    result_week = parse_time_expression("1 week ago")
    result_hour = parse_time_expression("1 hour ago")

    assert result_day is not None
    assert result_week is not None
    assert result_hour is not None


def test_parse_case_insensitive():
    """Test that parsing is case insensitive."""
    result_upper = parse_time_expression("TODAY")
    result_mixed = parse_time_expression("YeStErDaY")
    result_lower = parse_time_expression("last week")

    assert result_upper is not None
    assert result_mixed is not None
    assert result_lower is not None


def test_parse_with_whitespace():
    """Test parsing with extra whitespace."""
    result = parse_time_expression("  3 days ago  ")

    assert result is not None


def test_parse_invalid_expression():
    """Test parsing invalid expression."""
    result = parse_time_expression("invalid")

    assert result is None


def test_parse_invalid_date():
    """Test parsing invalid date."""
    result = parse_time_expression("2025-13-45")  # Invalid month and day

    assert result is None


def test_parse_empty_string():
    """Test parsing empty string."""
    result = parse_time_expression("")

    assert result is None


def test_parse_malformed_relative():
    """Test parsing malformed relative expression."""
    result = parse_time_expression("three days ago")  # Words instead of numbers

    assert result is None


def test_parse_unsupported_unit():
    """Test parsing unsupported time unit."""
    result = parse_time_expression("3 years ago")  # Years not supported

    assert result is None


# Tests for parse_duration()


def test_parse_duration_minutes():
    """Test parsing duration in minutes."""
    assert parse_duration("30m") == 1800
    assert parse_duration("30min") == 1800
    assert parse_duration("30mins") == 1800


def test_parse_duration_hours():
    """Test parsing duration in hours."""
    assert parse_duration("2h") == 7200
    assert parse_duration("2hr") == 7200
    assert parse_duration("2hrs") == 7200


def test_parse_duration_days():
    """Test parsing duration in days."""
    assert parse_duration("1d") == 86400
    assert parse_duration("1day") == 86400
    assert parse_duration("1days") == 86400


def test_parse_duration_weeks():
    """Test parsing duration in weeks."""
    assert parse_duration("1w") == 604800
    assert parse_duration("1week") == 604800
    assert parse_duration("1weeks") == 604800


def test_parse_duration_case_insensitive():
    """Test that duration parsing is case insensitive."""
    assert parse_duration("30M") == 1800
    assert parse_duration("2H") == 7200
    assert parse_duration("1D") == 86400


def test_parse_duration_with_whitespace():
    """Test parsing duration with whitespace."""
    assert parse_duration("  30m  ") == 1800
    assert parse_duration("  2h  ") == 7200


def test_parse_duration_invalid_format():
    """Test parsing invalid duration format."""
    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("invalid")

    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("30")  # Missing unit

    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("m30")  # Wrong order

    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("thirty minutes")  # Words instead of numbers


def test_parse_duration_empty_string():
    """Test parsing empty duration string."""
    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("")


def test_parse_duration_unknown_unit_fallback():
    """Test the unknown time unit fallback error (edge case for code coverage).

    This tests the unreachable fallback case in parse_duration where a unit
    passes the regex but isn't handled in the if-elif chain. This is logically
    impossible in normal operation, but we test it for 100% coverage by
    monkeypatching the regex match.
    """
    import re
    from unittest.mock import Mock
    from devflow.utils import time_parser

    # Create a mock match object that returns an unknown unit
    mock_match = Mock()
    mock_match.group.side_effect = lambda x: "5" if x == 1 else "unknown"

    # Monkeypatch re.match to return our mock
    original_match = re.match

    def mock_re_match(pattern, string):
        if pattern.startswith(r"(\d+)(m|min"):
            return mock_match
        return original_match(pattern, string)

    time_parser.re.match = mock_re_match

    try:
        with pytest.raises(ValueError, match="Unknown time unit: unknown"):
            parse_duration("5unknown")
    finally:
        # Restore original re.match
        time_parser.re.match = original_match
