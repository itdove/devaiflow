"""Time expression parser for filtering."""

from datetime import datetime, timedelta
from typing import Optional
import re


def parse_time_expression(expression: str) -> Optional[datetime]:
    """Parse a time expression into a datetime.

    Supported formats:
        - ISO dates: "2025-01-01", "2025-01-01 14:30"
        - Relative: "3 days ago", "2 weeks ago", "1 month ago"
        - Named: "today", "yesterday", "last week", "last month"

    Args:
        expression: Time expression string

    Returns:
        datetime object if parsing succeeds, None otherwise

    Examples:
        >>> parse_time_expression("2025-01-01")
        datetime(2025, 1, 1, 0, 0)

        >>> parse_time_expression("3 days ago")
        # Returns datetime 3 days before now

        >>> parse_time_expression("yesterday")
        # Returns yesterday at midnight
    """
    expression = expression.strip().lower()
    now = datetime.now()

    # ISO date formats
    # Try YYYY-MM-DD HH:MM format
    try:
        return datetime.fromisoformat(expression)
    except ValueError:
        pass

    # Try YYYY-MM-DD format
    try:
        return datetime.strptime(expression, "%Y-%m-%d")
    except ValueError:
        pass

    # Named shortcuts
    if expression == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    if expression == "yesterday":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    if expression == "last week":
        return now - timedelta(weeks=1)

    if expression == "last month":
        return now - timedelta(days=30)

    # Relative expressions: "N days ago", "N weeks ago", etc.
    # Pattern: <number> <unit> ago
    match = re.match(r"(\d+)\s+(day|days|week|weeks|month|months|hour|hours)\s+ago", expression)
    if match:
        count = int(match.group(1))
        unit = match.group(2)

        if unit in ("day", "days"):
            return now - timedelta(days=count)
        elif unit in ("week", "weeks"):
            return now - timedelta(weeks=count)
        elif unit in ("month", "months"):
            return now - timedelta(days=count * 30)  # Approximate
        elif unit in ("hour", "hours"):
            return now - timedelta(hours=count)

    # Could not parse
    return None


def parse_duration(duration_str: str) -> int:
    """Parse a duration string into seconds.

    Supported formats:
        - "30m" or "30min" - 30 minutes
        - "2h" or "2hr" - 2 hours
        - "1d" or "1day" - 1 day
        - "1w" or "1week" - 1 week

    Args:
        duration_str: Duration string (e.g., "2h", "30m", "1d")

    Returns:
        Duration in seconds

    Raises:
        ValueError: If duration format is invalid

    Examples:
        >>> parse_duration("30m")
        1800

        >>> parse_duration("2h")
        7200

        >>> parse_duration("1d")
        86400
    """
    duration_str = duration_str.strip().lower()

    # Pattern: <number><unit>
    match = re.match(r"(\d+)(m|min|h|hr|d|day|w|week)s?$", duration_str)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{duration_str}'. "
            "Use formats like: 30m, 2h, 1d, 1w"
        )

    count = int(match.group(1))
    unit = match.group(2)

    # Convert to seconds
    if unit in ("m", "min"):
        return count * 60
    elif unit in ("h", "hr"):
        return count * 3600
    elif unit in ("d", "day"):
        return count * 86400
    elif unit in ("w", "week"):
        return count * 604800

    raise ValueError(f"Unknown time unit: {unit}")
