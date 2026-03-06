"""Issue tracker abstraction layer for DevAIFlow.

This module provides an interface for issue tracking systems (JIRA, GitHub Issues, etc.)
that can be used to integrate different backends.
"""

from .interface import IssueTrackerClient
from .factory import create_issue_tracker_client
from .exceptions import (
    IssueTrackerError,
    IssueTrackerAuthError,
    IssueTrackerApiError,
    IssueTrackerNotFoundError,
    IssueTrackerValidationError,
    IssueTrackerConnectionError,
    IssueTrackerConfigError,
)

__all__ = [
    "IssueTrackerClient",
    "create_issue_tracker_client",
    "IssueTrackerError",
    "IssueTrackerAuthError",
    "IssueTrackerApiError",
    "IssueTrackerNotFoundError",
    "IssueTrackerValidationError",
    "IssueTrackerConnectionError",
    "IssueTrackerConfigError",
]
