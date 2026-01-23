"""Factory for creating issue tracker client instances.

This module provides a factory function that creates the appropriate
issue tracker client based on configuration.
"""

from typing import Optional

from devflow.issue_tracker.interface import IssueTrackerClient


def create_issue_tracker_client(backend: Optional[str] = None, timeout: int = 30) -> IssueTrackerClient:
    """Create an issue tracker client based on backend configuration.

    Args:
        backend: Backend type ("jira", "github", "gitlab", "mock", etc.).
                 If None, reads from config or defaults to "jira".
        timeout: Timeout for API requests in seconds

    Returns:
        IssueTrackerClient implementation for the specified backend

    Raises:
        ValueError: If backend type is not supported
        ImportError: If backend implementation is not available

    Examples:
        >>> # Create JIRA client (default)
        >>> client = create_issue_tracker_client()
        >>> client = create_issue_tracker_client("jira")
        >>>
        >>> # Create mock client for testing
        >>> client = create_issue_tracker_client("mock")
        >>>
        >>> # Create GitHub Issues client (future)
        >>> client = create_issue_tracker_client("github")
    """
    # If no backend specified, try to read from config
    if backend is None:
        backend = get_backend_from_config()

    backend = backend.lower()

    if backend == "jira":
        from devflow.jira.client import JiraClient
        return JiraClient(timeout=timeout)
    elif backend == "mock":
        from devflow.issue_tracker.mock_client import MockIssueTrackerClient
        return MockIssueTrackerClient(timeout=timeout)
    elif backend == "github":
        # Future implementation
        raise NotImplementedError(
            "GitHub Issues backend is not yet implemented. "
            "See devflow/issue_tracker/interface.py for the interface to implement."
        )
    elif backend == "gitlab":
        # Future implementation
        raise NotImplementedError(
            "GitLab Issues backend is not yet implemented. "
            "See devflow/issue_tracker/interface.py for the interface to implement."
        )
    else:
        raise ValueError(
            f"Unsupported issue tracker backend: {backend}. "
            f"Supported backends: jira, mock (more coming soon)"
        )


def get_backend_from_config() -> str:
    """Get the issue tracker backend from configuration.

    Returns:
        Backend name from config, or "jira" as default

    Note:
        Falls back to "jira" if config cannot be loaded or field is not set.
        This ensures backward compatibility with existing installations.

        If DAF_MOCK_MODE=1 environment variable is set, always returns "mock"
        regardless of configuration. This enables integration testing.
    """
    import os

    # Check for mock mode environment variable first
    if os.getenv("DAF_MOCK_MODE") == "1":
        return "mock"

    try:
        from devflow.config.loader import ConfigLoader
        config_loader = ConfigLoader()
        if config_loader.config_file.exists():
            config = config_loader.load_config()
            if config:
                return getattr(config, "issue_tracker_backend", "jira")
    except Exception:
        # If config loading fails, fall back to default
        pass

    return "jira"


def get_default_backend() -> str:
    """Get the default issue tracker backend.

    Returns:
        Default backend name ("jira")

    Deprecated:
        Use get_backend_from_config() instead to read from configuration.
    """
    return get_backend_from_config()
