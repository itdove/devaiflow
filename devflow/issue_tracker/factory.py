"""Factory for creating issue tracker client instances.

This module provides a factory function that creates the appropriate
issue tracker client based on configuration.
"""

from typing import Optional

from devflow.issue_tracker.interface import IssueTrackerClient


def create_issue_tracker_client(
    backend: Optional[str] = None,
    timeout: int = 30,
    hostname: Optional[str] = None,
    repository: Optional[str] = None
) -> IssueTrackerClient:
    """Create an issue tracker client based on backend configuration.

    Args:
        backend: Backend type ("jira", "github", "gitlab", "mock", etc.).
                 If None, reads from config or defaults to "jira".
        timeout: Timeout for API requests in seconds
        hostname: Hostname for enterprise instances (e.g., "gitlab.cee.redhat.com").
                  Only applicable for GitHub/GitLab backends.
        repository: Repository in owner/repo format (GitHub) or group/project (GitLab).
                    If provided, overrides config. Only applicable for GitHub/GitLab.

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
        >>> # Create GitHub Issues client with repository
        >>> client = create_issue_tracker_client("github", repository="owner/repo")
        >>>
        >>> # Create GitLab client for enterprise instance
        >>> client = create_issue_tracker_client("gitlab", hostname="gitlab.cee.redhat.com", repository="group/project")
    """
    import os

    # Check for mock mode environment variable first - overrides everything
    if os.getenv("DAF_MOCK_MODE") == "1":
        backend = "mock"
    # If no backend specified, try to read from config
    elif backend is None:
        backend = get_backend_from_config()

    backend = backend.lower()

    if backend == "jira":
        from devflow.jira.client import JiraClient
        return JiraClient(timeout=timeout)
    elif backend == "mock":
        from devflow.issue_tracker.mock_client import MockIssueTrackerClient
        return MockIssueTrackerClient(timeout=timeout)
    elif backend == "github":
        from devflow.github.issues_client import GitHubClient

        # Use provided repository or try to get from config
        repo = repository
        if not repo:
            try:
                from devflow.config.loader import ConfigLoader
                config_loader = ConfigLoader()
                if config_loader.config_file.exists():
                    config = config_loader.load_config()
                    if config and hasattr(config, 'github') and config.github:
                        repo = config.github.repository
            except Exception:
                pass

        return GitHubClient(timeout=timeout, repository=repo)
    elif backend == "gitlab":
        from devflow.gitlab.issues_client import GitLabClient

        # Use provided repository or try to get from config
        repo = repository
        if not repo:
            try:
                from devflow.config.loader import ConfigLoader
                config_loader = ConfigLoader()
                if config_loader.config_file.exists():
                    config = config_loader.load_config()
                    if config and hasattr(config, 'gitlab') and config.gitlab:
                        repo = config.gitlab.repository
            except Exception:
                pass

        return GitLabClient(timeout=timeout, repository=repo, hostname=hostname)
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
