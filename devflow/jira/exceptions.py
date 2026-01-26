"""Custom exceptions for JIRA client operations."""


class JiraError(Exception):
    """Base exception for all JIRA-related errors."""

    def __init__(self, message: str, **kwargs):
        """Initialize JIRA error.

        Args:
            message: Error message
            **kwargs: Additional error context (stored as attributes)
        """
        super().__init__(message)
        self.message = message
        # Store any additional context as attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class JiraAuthError(JiraError):
    """Raised when JIRA authentication fails."""
    pass


class JiraApiError(JiraError):
    """Raised when JIRA REST API returns an error response.

    Attributes:
        status_code: HTTP status code
        response_text: Raw response body
        error_messages: List of error messages from JIRA
        field_errors: Dict of field-specific errors
    """

    def __init__(self, message: str, status_code: int = None,
                 response_text: str = None, error_messages: list = None,
                 field_errors: dict = None):
        """Initialize JIRA API error.

        Args:
            message: Error message
            status_code: HTTP status code
            response_text: Raw response body
            error_messages: List of error messages from JIRA
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
                # Extract error details from JIRA response
                if "errorMessages" in response_data and response_data["errorMessages"]:
                    parts.append(f"JIRA errors: {', '.join(response_data['errorMessages'])}")
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


class JiraNotFoundError(JiraError):
    """Raised when a JIRA resource is not found (404)."""

    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        """Initialize not found error.

        Args:
            message: Error message
            resource_type: Type of resource (e.g., "issue", "field")
            resource_id: ID of the resource (e.g., "PROJ-12345")
        """
        super().__init__(message)
        self.resource_type = resource_type
        self.resource_id = resource_id


class JiraValidationError(JiraError):
    """Raised when JIRA validation fails (400 with field errors)."""

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


class JiraConnectionError(JiraError):
    """Raised when connection to JIRA fails."""
    pass


class JiraConfigError(JiraError):
    """Raised when JIRA configuration is invalid or missing."""
    pass
