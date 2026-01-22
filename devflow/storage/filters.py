"""Session filter criteria for querying sessions."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SessionFilters:
    """Filter criteria for querying sessions.

    Used to filter sessions by various attributes like status, working directory,
    sprint, JIRA status, and time range.
    """

    status: Optional[str] = None  # Filter by session status (comma-separated for multiple)
    working_directory: Optional[str] = None  # Filter by working directory
    sprint: Optional[str] = None  # Filter by sprint
    issue_status: Optional[str] = None  # Filter by issue tracker status (comma-separated for multiple)
    since: Optional[datetime] = None  # Filter by sessions active since this datetime
    before: Optional[datetime] = None  # Filter by sessions active before this datetime
