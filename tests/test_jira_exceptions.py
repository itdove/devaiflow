"""Tests for JIRA exception classes."""

import json
import pytest

from devflow.jira.exceptions import (
    JiraError,
    JiraAuthError,
    JiraApiError,
    JiraNotFoundError,
    JiraValidationError,
    JiraConnectionError,
    JiraConfigError,
)


def test_jira_error_basic():
    """Test JiraError with basic message."""
    error = JiraError("Something went wrong")

    assert str(error) == "Something went wrong"
    assert error.message == "Something went wrong"


def test_jira_error_with_kwargs():
    """Test JiraError with additional context kwargs."""
    error = JiraError("Error occurred", code=500, details="Server error")

    assert error.message == "Error occurred"
    assert error.code == 500
    assert error.details == "Server error"


def test_jira_auth_error():
    """Test JiraAuthError inherits from JiraError."""
    error = JiraAuthError("Invalid credentials")

    assert isinstance(error, JiraError)
    assert str(error) == "Invalid credentials"


def test_jira_connection_error():
    """Test JiraConnectionError inherits from JiraError."""
    error = JiraConnectionError("Connection refused")

    assert isinstance(error, JiraError)
    assert str(error) == "Connection refused"


def test_jira_config_error():
    """Test JiraConfigError inherits from JiraError."""
    error = JiraConfigError("Missing API token")

    assert isinstance(error, JiraError)
    assert str(error) == "Missing API token"


def test_jira_api_error_basic():
    """Test JiraApiError with basic message."""
    error = JiraApiError("API request failed")

    assert error.message == "API request failed"
    assert error.status_code is None
    assert error.response_text is None
    assert error.error_messages == []
    assert error.field_errors == {}


def test_jira_api_error_with_status_code():
    """Test JiraApiError with HTTP status code."""
    error = JiraApiError("API error", status_code=500)

    error_str = str(error)
    assert "API error" in error_str
    assert "(HTTP 500)" in error_str


def test_jira_api_error_with_json_response_error_messages():
    """Test JiraApiError with JSON response containing errorMessages."""
    response = {
        "errorMessages": ["Field 'summary' is required", "Invalid issue type"]
    }
    error = JiraApiError(
        "Validation failed",
        status_code=400,
        response_text=json.dumps(response)
    )

    error_str = str(error)
    assert "Validation failed" in error_str
    assert "(HTTP 400)" in error_str
    assert "JIRA errors:" in error_str
    assert "Field 'summary' is required" in error_str
    assert "Invalid issue type" in error_str


def test_jira_api_error_with_json_response_field_errors():
    """Test JiraApiError with JSON response containing field errors."""
    response = {
        "errors": {
            "summary": "Summary is required",
            "assignee": "User not found"
        }
    }
    error = JiraApiError(
        "Validation failed",
        status_code=400,
        response_text=json.dumps(response)
    )

    error_str = str(error)
    assert "Validation failed" in error_str
    assert "Field errors:" in error_str
    assert "summary: Summary is required" in error_str
    assert "assignee: User not found" in error_str


def test_jira_api_error_with_json_response_no_structured_errors():
    """Test JiraApiError with JSON response but no structured errors."""
    response = {"custom_field": "some value"}
    error = JiraApiError(
        "Unexpected response",
        status_code=500,
        response_text=json.dumps(response)
    )

    error_str = str(error)
    assert "Unexpected response" in error_str
    assert "Response:" in error_str


def test_jira_api_error_with_long_response():
    """Test JiraApiError truncates long responses."""
    long_response = "x" * 250  # Longer than 200 characters
    error = JiraApiError(
        "Error",
        status_code=500,
        response_text=long_response
    )

    error_str = str(error)
    assert "Response:" in error_str
    assert "..." in error_str  # Should be truncated


def test_jira_api_error_with_invalid_json():
    """Test JiraApiError with non-JSON response."""
    error = JiraApiError(
        "Server error",
        status_code=500,
        response_text="<html>Internal Server Error</html>"
    )

    error_str = str(error)
    assert "Server error" in error_str
    assert "(HTTP 500)" in error_str
    assert "Response:" in error_str
    assert "<html>Internal Server Error</html>" in error_str


def test_jira_api_error_string_repr_exception_handling():
    """Test JiraApiError __str__ handles exceptions gracefully."""
    # Create error with response that will cause exception during parsing
    error = JiraApiError(
        "Error",
        status_code=500,
        response_text=None
    )

    # Should not raise exception
    error_str = str(error)
    assert "Error" in error_str


def test_jira_not_found_error():
    """Test JiraNotFoundError with resource details."""
    error = JiraNotFoundError(
        "Resource not found",
        resource_type="issue",
        resource_id="PROJ-12345"
    )

    assert isinstance(error, JiraError)
    assert error.message == "Resource not found"
    assert error.resource_type == "issue"
    assert error.resource_id == "PROJ-12345"


def test_jira_not_found_error_without_details():
    """Test JiraNotFoundError without resource details."""
    error = JiraNotFoundError("Not found")

    assert error.resource_type is None
    assert error.resource_id is None


def test_jira_validation_error():
    """Test JiraValidationError with field errors."""
    error = JiraValidationError(
        "Validation failed",
        field_errors={"summary": "Required"},
        error_messages=["Invalid input"]
    )

    assert isinstance(error, JiraError)
    assert error.message == "Validation failed"
    assert error.field_errors == {"summary": "Required"}
    assert error.error_messages == ["Invalid input"]


def test_jira_validation_error_defaults():
    """Test JiraValidationError with default empty collections."""
    error = JiraValidationError("Validation failed")

    assert error.field_errors == {}
    assert error.error_messages == []


def test_jira_api_error_stores_all_parameters():
    """Test JiraApiError stores all initialization parameters."""
    error = JiraApiError(
        "Error",
        status_code=400,
        response_text="error text",
        error_messages=["msg1", "msg2"],
        field_errors={"field1": "error1"}
    )

    assert error.status_code == 400
    assert error.response_text == "error text"
    assert error.error_messages == ["msg1", "msg2"]
    assert error.field_errors == {"field1": "error1"}
