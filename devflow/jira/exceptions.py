"""Custom exceptions for JIRA client operations.

BACKWARD COMPATIBILITY LAYER
=============================
This module now provides backward-compatible aliases for the renamed
backend-agnostic exception hierarchy in devflow.issue_tracker.exceptions.

New code should import from devflow.issue_tracker.exceptions directly.
Existing JIRA-specific code can continue importing from here without changes.

Migration path:
- Old: from devflow.jira.exceptions import JiraError
- New: from devflow.issue_tracker.exceptions import IssueTrackerError
"""

# Import backend-agnostic exceptions
from devflow.issue_tracker.exceptions import (
    IssueTrackerError,
    IssueTrackerAuthError,
    IssueTrackerApiError,
    IssueTrackerNotFoundError,
    IssueTrackerValidationError,
    IssueTrackerConnectionError,
    IssueTrackerConfigError,
)

# Backward-compatible aliases for existing JIRA code
JiraError = IssueTrackerError
JiraAuthError = IssueTrackerAuthError
JiraApiError = IssueTrackerApiError
JiraNotFoundError = IssueTrackerNotFoundError
JiraValidationError = IssueTrackerValidationError
JiraConnectionError = IssueTrackerConnectionError
JiraConfigError = IssueTrackerConfigError

# Export all for backward compatibility
__all__ = [
    # Backend-agnostic names (preferred)
    "IssueTrackerError",
    "IssueTrackerAuthError",
    "IssueTrackerApiError",
    "IssueTrackerNotFoundError",
    "IssueTrackerValidationError",
    "IssueTrackerConnectionError",
    "IssueTrackerConfigError",
    # JIRA aliases (backward compatibility)
    "JiraError",
    "JiraAuthError",
    "JiraApiError",
    "JiraNotFoundError",
    "JiraValidationError",
    "JiraConnectionError",
    "JiraConfigError",
]
