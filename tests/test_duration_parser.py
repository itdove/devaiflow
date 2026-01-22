"""Tests for duration parser."""

import pytest

from devflow.utils.time_parser import parse_duration


def test_parse_duration_minutes():
    """Test parsing minutes."""
    assert parse_duration("30m") == 1800
    assert parse_duration("1m") == 60
    assert parse_duration("45m") == 2700


def test_parse_duration_hours():
    """Test parsing hours."""
    assert parse_duration("2h") == 7200
    assert parse_duration("1h") == 3600
    assert parse_duration("24h") == 86400


def test_parse_duration_days():
    """Test parsing days."""
    assert parse_duration("1d") == 86400
    assert parse_duration("7d") == 604800
    assert parse_duration("30d") == 2592000


def test_parse_duration_weeks():
    """Test parsing weeks."""
    assert parse_duration("1w") == 604800
    assert parse_duration("2w") == 1209600


def test_parse_duration_with_long_forms():
    """Test parsing with long unit names."""
    assert parse_duration("30min") == 1800
    assert parse_duration("2hr") == 7200
    assert parse_duration("1day") == 86400
    assert parse_duration("1week") == 604800


def test_parse_duration_with_plurals():
    """Test parsing with plural units."""
    assert parse_duration("2mins") == 120
    assert parse_duration("3hrs") == 10800
    assert parse_duration("5days") == 432000
    assert parse_duration("2weeks") == 1209600


def test_parse_duration_case_insensitive():
    """Test that parsing is case insensitive."""
    assert parse_duration("2H") == 7200
    assert parse_duration("30M") == 1800
    assert parse_duration("1D") == 86400
    assert parse_duration("1W") == 604800


def test_parse_duration_with_whitespace():
    """Test parsing with leading/trailing whitespace."""
    assert parse_duration("  2h  ") == 7200
    assert parse_duration("\t1d\n") == 86400


def test_parse_duration_invalid_format():
    """Test that invalid format raises ValueError."""
    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("2x")

    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("not a duration")

    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("h2")


def test_parse_duration_empty_string():
    """Test that empty string raises ValueError."""
    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("")


def test_parse_duration_no_number():
    """Test that missing number raises ValueError."""
    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("h")

    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("days")
