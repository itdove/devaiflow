"""Custom exceptions for issue tracker client operations.

This module provides backend-agnostic exceptions used by all issue tracker
implementations (JIRA, GitHub, GitLab, etc.).
"""


class IssueTrackerError(Exception):
    """Base exception for all issue tracker-related errors."""

    def __init__(self, message: str, **kwargs):
        """Initialize issue tracker error.

        Args:
            message: Error message
            **kwargs: Additional error context (stored as attributes)
        """
        super().__init__(message)
        self.message = message
        # Store any additional context as attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class IssueTrackerAuthError(IssueTrackerError):
    """Raised when issue tracker authentication fails.

    Attributes:
        token_expired: True if authentication failure is due to expired token
        jira_url: JIRA URL for token regeneration (JIRA-specific)
    """

    def __init__(self, message: str, token_expired: bool = False, jira_url: str = None, **kwargs):
        """Initialize authentication error.

        Args:
            message: Error message
            token_expired: True if authentication failure is due to expired token
            jira_url: JIRA URL for token regeneration
            **kwargs: Additional error context (stored as attributes)
        """
        super().__init__(message, **kwargs)
        self.token_expired = token_expired
        self.jira_url = jira_url

    def __str__(self) -> str:
        """Return detailed error message with token expiration guidance."""
        if self.token_expired and self.jira_url:
            return (
                f"{self.message}\n\n"
                f"Your JIRA API token has expired. To fix this:\n"
                f"1. Generate a new API token at {self.jira_url}/secure/ViewProfile.jspa\n"
                f"2. Update your JIRA_API_TOKEN environment variable with the new token\n"
                f"3. Reload your shell (e.g., 'source ~/.zshrc' or restart your terminal)"
            )
        return self.message


class IssueTrackerApiError(IssueTrackerError):
    """Raised when issue tracker REST API returns an error response.

    Attributes:
        status_code: HTTP status code
        response_text: Raw response body
        error_messages: List of error messages from the API
        field_errors: Dict of field-specific errors
    """

    def __init__(self, message: str, status_code: int = None,
                 response_text: str = None, error_messages: list = None,
                 field_errors: dict = None):
        """Initialize issue tracker API error.

        Args:
            message: Error message
            status_code: HTTP status code
            response_text: Raw response body
            error_messages: List of error messages from the API
            field_errors: Dict of field-specific errors
        """
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.error_messages = error_messages or []
        self.field_errors = field_errors or {}

    def __str__(self) -> str:
        """Return detailed error message including API response details."""
        parts = [self.message]

        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")

        if self.response_text:
            # Try to parse and prettify JSON response
            import json
            try:
                response_data = json.loads(self.response_text)
                # Extract error details from API response
                if "errorMessages" in response_data and response_data["errorMessages"]:
                    parts.append(f"API errors: {', '.join(response_data['errorMessages'])}")
                if "errors" in response_data and response_data["errors"]:
                    field_errors_str = ", ".join([f"{k}: {v}" for k, v in response_data["errors"].items()])
                    parts.append(f"Field errors: {field_errors_str}")
                # If no structured errors, show raw response (truncated)
                if not ("errorMessages" in response_data or "errors" in response_data):
                    response_preview = self.response_text[:200]
                    if len(self.response_text) > 200:
                        response_preview += "..."
                    parts.append(f"Response: {response_preview}")
            except (json.JSONDecodeError, Exception):
                # Not JSON or parsing failed - show raw response (truncated)
                response_preview = self.response_text[:200]
                if len(self.response_text) > 200:
                    response_preview += "..."
                parts.append(f"Response: {response_preview}")

        return " - ".join(parts)


class IssueTrackerNotFoundError(IssueTrackerError):
    """Raised when an issue tracker resource is not found (404)."""

    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        """Initialize not found error.

        Args:
            message: Error message
            resource_type: Type of resource (e.g., "issue", "field")
            resource_id: ID of the resource (e.g., "PROJ-12345", "#123")
        """
        super().__init__(message)
        self.resource_type = resource_type
        self.resource_id = resource_id


class IssueTrackerValidationError(IssueTrackerError):
    """Raised when issue tracker validation fails (400 with field errors)."""

    def __init__(self, message: str, field_errors: dict = None, error_messages: list = None):
        """Initialize validation error.

        Args:
            message: Error message
            field_errors: Dict of field-specific validation errors
            error_messages: List of general validation errors
        """
        super().__init__(message)
        self.field_errors = field_errors or {}
        self.error_messages = error_messages or []


class IssueTrackerConnectionError(IssueTrackerError):
    """Raised when connection to issue tracker fails."""
    pass


class IssueTrackerConfigError(IssueTrackerError):
    """Raised when issue tracker configuration is invalid or missing."""
    pass
