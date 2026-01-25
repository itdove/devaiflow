"""Session filter criteria for querying sessions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class SessionFilters:
    """Filter criteria for querying sessions.

    Used to filter sessions by various attributes like status, working directory,
    issue tracker fields, issue status, and time range.
    """

    status: Optional[str] = None  # Filter by session status (comma-separated for multiple)
    working_directory: Optional[str] = None  # Filter by working directory
    issue_metadata_filters: Optional[Dict[str, str]] = field(default_factory=dict)  # Filter by custom fields (e.g., {"sprint": "Sprint 1", "severity": "Critical"})
    issue_status: Optional[str] = None  # Filter by issue tracker status (comma-separated for multiple)
    since: Optional[datetime] = None  # Filter by sessions active since this datetime
    before: Optional[datetime] = None  # Filter by sessions active before this datetime
