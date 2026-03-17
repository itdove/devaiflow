"""Utilities for detecting issue tracker backend from session metadata and issue keys."""

import re
from typing import Optional

from devflow.config.models import Config, Session


def get_backend_display_name(backend: str) -> str:
    """Get human-friendly display name for issue tracker backend.

    Args:
        backend: Backend identifier ("jira", "github", "gitlab", "mock")

    Returns:
        Display name suitable for user-facing messages

    Examples:
        >>> get_backend_display_name("jira")
        'JIRA'
        >>> get_backend_display_name("github")
        'GitHub Issues'
        >>> get_backend_display_name("gitlab")
        'GitLab Issues'
        >>> get_backend_display_name("mock")
        'Mock Issue Tracker'
    """
    display_names = {
        "jira": "JIRA",
        "github": "GitHub Issues",
        "gitlab": "GitLab Issues",
        "mock": "Mock Issue Tracker",
    }
    return display_names.get(backend, backend.upper())


def detect_backend_from_key(issue_key: str, config: Optional[Config] = None) -> str:
    """Detect issue tracker backend from issue key format.

    Uses pattern matching to identify backend type:
    - JIRA: PROJECT-NUMBER format (e.g., AAP-12345, PROJ-999, TEST-1)
      - Project key is uppercase letters/numbers
      - Followed by dash and number
      - Optionally validates against config.jira.project
    - GitHub: Everything else (#123, owner/repo#123, 123)
      - Hash format
      - Repository format
      - Plain number (when repo known from config)

    Args:
        issue_key: Issue identifier to analyze
        config: Optional configuration object for validation

    Returns:
        "jira" or "github" backend identifier

    Examples:
        >>> detect_backend_from_key("AAP-12345")
        'jira'
        >>> detect_backend_from_key("PROJ-999")
        'jira'
        >>> detect_backend_from_key("#123")
        'github'
        >>> detect_backend_from_key("owner/repo#123")
        'github'
        >>> detect_backend_from_key("123")
        'github'
    """
    if not issue_key:
        # No issue key - fall back to config or default
        if config and hasattr(config, 'issue_tracker_backend'):
            return config.issue_tracker_backend or "jira"
        return "jira"

    # JIRA pattern: PROJECT_KEY-NUMBER
    # Project key: uppercase letter followed by uppercase letters/numbers
    # Examples: AAP-12345, PROJ-999, TEST-1, A-1
    if re.match(r'^[A-Z][A-Z0-9]*-\d+$', issue_key):
        # Optionally validate against configured JIRA project
        if config and hasattr(config, 'jira') and config.jira and hasattr(config.jira, 'project') and config.jira.project:
            # Ensure project is a string (not a Mock or other object)
            if isinstance(config.jira.project, str):
                project_prefix = config.jira.project + "-"
                if issue_key.startswith(project_prefix):
                    # Matches configured project - definitely JIRA
                    return "jira"
                # Matches JIRA pattern but different project
                # Still JIRA (might be multi-project setup)
                return "jira"
        # Matches JIRA pattern
        return "jira"

    # GitHub: Anything that doesn't match JIRA pattern
    # Includes: #123, owner/repo#123, 123, my-feature-123 (lowercase)
    return "github"


def get_issue_tracker_backend(session: Session, config: Optional[Config] = None) -> str:
    """Get the issue tracker backend for a session.

    Uses three-tier detection:
    1. Session metadata (session.issue_tracker) - Most reliable
    2. Pattern matching from issue key + config validation
    3. Global config (config.issue_tracker_backend)
    4. Default fallback ("jira")

    This ensures backward compatibility with existing sessions while
    supporting mixed JIRA/GitHub sessions.

    Args:
        session: Session object
        config: Optional configuration object

    Returns:
        Backend identifier: "jira", "github", "mock", etc.

    Examples:
        >>> session = Session(name="test", issue_tracker="github")
        >>> get_issue_tracker_backend(session, None)
        'github'

        >>> session = Session(name="test", issue_key="AAP-12345")
        >>> get_issue_tracker_backend(session, None)
        'jira'

        >>> session = Session(name="test", issue_key="#123")
        >>> get_issue_tracker_backend(session, None)
        'github'
    """
    # Tier 1: Explicit session metadata (highest priority)
    if hasattr(session, 'issue_tracker') and session.issue_tracker:
        return session.issue_tracker

    # Tier 2: Infer from issue key format (backward compatibility)
    if hasattr(session, 'issue_key') and session.issue_key:
        return detect_backend_from_key(session.issue_key, config)

    # Tier 3: Global config
    if config and hasattr(config, 'issue_tracker_backend') and config.issue_tracker_backend:
        return config.issue_tracker_backend

    # Tier 4: Default fallback
    return "jira"


def validate_issue_key_format(issue_key: str, backend: str) -> bool:
    """Validate that an issue key matches the expected format for a backend.

    Args:
        issue_key: Issue identifier to validate
        backend: Expected backend type ("jira", "github")

    Returns:
        True if format matches backend, False otherwise

    Examples:
        >>> validate_issue_key_format("AAP-12345", "jira")
        True
        >>> validate_issue_key_format("#123", "jira")
        False
        >>> validate_issue_key_format("#123", "github")
        True
        >>> validate_issue_key_format("AAP-12345", "github")
        False
    """
    if backend == "jira":
        # JIRA requires PROJECT-NUMBER format
        return bool(re.match(r'^[A-Z][A-Z0-9]*-\d+$', issue_key))
    elif backend == "github":
        # GitHub accepts various formats
        # Hash format: #123
        if re.match(r'^#\d+$', issue_key):
            return True
        # Repository format: owner/repo#123
        if re.match(r'^[\w-]+/[\w.-]+#\d+$', issue_key):
            return True
        # Plain number: 123
        if re.match(r'^\d+$', issue_key):
            return True
        # None of the GitHub patterns matched
        return False
    else:
        # Unknown backend - can't validate
        return False
