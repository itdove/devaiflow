"""Tests for JIRA token expiration detection and error messaging."""

import json
from unittest.mock import MagicMock, patch

import pytest

from devflow.jira.client import JiraClient
from devflow.jira.exceptions import JiraAuthError


@pytest.fixture
def mock_env(monkeypatch):
    """Set up environment for JIRA authentication."""
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token-123")
    monkeypatch.setenv("JIRA_AUTH_TYPE", "bearer")
    monkeypatch.setenv("JIRA_URL", "https://test.jira.com")


def test_is_token_expired_with_expired_token_in_error_messages(mock_env):
    """Test token expiration detection from errorMessages array."""
    client = JiraClient()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {
        "errorMessages": ["Your API token has expired. Please generate a new token."]
    }
    mock_response.text = json.dumps(mock_response.json.return_value)

    assert client._is_token_expired(mock_response) is True


def test_is_token_expired_with_expired_in_errors_dict(mock_env):
    """Test token expiration detection from errors dict."""
    client = JiraClient()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {
        "errors": {
            "authentication": "Token expired. Please renew your API token."
        }
    }
    mock_response.text = json.dumps(mock_response.json.return_value)

    assert client._is_token_expired(mock_response) is True


def test_is_token_expired_with_expiration_keyword(mock_env):
    """Test token expiration detection with 'expiration' keyword."""
    client = JiraClient()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {
        "errorMessages": ["Token expiration date has passed"]
    }
    mock_response.text = json.dumps(mock_response.json.return_value)

    assert client._is_token_expired(mock_response) is True


def test_is_token_expired_with_invalid_token_not_expired(mock_env):
    """Test that invalid token (not expired) is detected correctly."""
    client = JiraClient()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {
        "errorMessages": ["Invalid credentials provided"]
    }
    mock_response.text = json.dumps(mock_response.json.return_value)

    assert client._is_token_expired(mock_response) is False


def test_is_token_expired_with_403_forbidden(mock_env):
    """Test that 403 forbidden is not treated as expired token."""
    client = JiraClient()

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {
        "errorMessages": ["You do not have permission to access this resource"]
    }
    mock_response.text = json.dumps(mock_response.json.return_value)

    assert client._is_token_expired(mock_response) is False


def test_is_token_expired_with_non_json_response(mock_env):
    """Test token expiration detection from plain text response."""
    client = JiraClient()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.side_effect = ValueError("Not JSON")
    mock_response.text = "Authentication token has expired. Please generate a new token."

    assert client._is_token_expired(mock_response) is True


def test_is_token_expired_with_non_json_invalid_credentials(mock_env):
    """Test that non-JSON invalid credentials is not treated as expired."""
    client = JiraClient()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.side_effect = ValueError("Not JSON")
    mock_response.text = "Invalid username or password"

    assert client._is_token_expired(mock_response) is False


def test_raise_auth_error_with_expired_token(mock_env):
    """Test that _raise_auth_error raises JiraAuthError with expiration details."""
    client = JiraClient()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {
        "errorMessages": ["Your API token has expired"]
    }
    mock_response.text = json.dumps(mock_response.json.return_value)

    with pytest.raises(JiraAuthError) as exc_info:
        client._raise_auth_error("Authentication failed", mock_response)

    error = exc_info.value
    assert error.token_expired is True
    assert error.jira_url == "https://test.jira.com"
    assert error.status_code == 401
    # Check that the error message includes helpful guidance
    error_str = str(error)
    assert "expired" in error_str.lower()
    assert "generate a new api token" in error_str.lower()
    assert "https://test.jira.com/secure/ViewProfile.jspa" in error_str


def test_raise_auth_error_with_invalid_token_not_expired(mock_env):
    """Test that _raise_auth_error handles invalid (but not expired) tokens."""
    client = JiraClient()

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {
        "errorMessages": ["Invalid credentials"]
    }
    mock_response.text = json.dumps(mock_response.json.return_value)

    with pytest.raises(JiraAuthError) as exc_info:
        client._raise_auth_error("Authentication failed", mock_response)

    error = exc_info.value
    assert error.token_expired is False
    assert error.jira_url == "https://test.jira.com"
    assert error.status_code == 401
    # Error message should not include expiration guidance
    error_str = str(error)
    assert "authentication failed" in error_str.lower()
    assert "generate a new api token" not in error_str.lower()


def test_raise_auth_error_without_response(mock_env):
    """Test that _raise_auth_error works without a response object."""
    client = JiraClient()

    with pytest.raises(JiraAuthError) as exc_info:
        client._raise_auth_error("JIRA_API_TOKEN not set")

    error = exc_info.value
    assert error.token_expired is False
    assert error.jira_url == "https://test.jira.com"
    assert error.status_code is None


def test_get_ticket_with_expired_token_raises_helpful_error(mock_env):
    """Test that get_ticket raises helpful error message for expired tokens."""
    client = JiraClient()

    # Mock the API request to return 401 with expiration message
    with patch("requests.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "errorMessages": ["Your API token has expired. Please renew it."]
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_request.return_value = mock_response

        with pytest.raises(JiraAuthError) as exc_info:
            client.get_ticket("PROJ-12345")

        error = exc_info.value
        assert error.token_expired is True
        error_str = str(error)
        assert "expired" in error_str.lower()
        assert "https://test.jira.com/secure/ViewProfile.jspa" in error_str


def test_add_comment_with_expired_token_raises_helpful_error(mock_env):
    """Test that add_comment raises helpful error message for expired tokens."""
    client = JiraClient()

    # Mock the API request to return 401 with expiration message
    with patch("requests.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "errorMessages": ["Token expiration date has passed"]
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_request.return_value = mock_response

        with pytest.raises(JiraAuthError) as exc_info:
            client.add_comment("PROJ-12345", "Test comment")

        error = exc_info.value
        assert error.token_expired is True
        error_str = str(error)
        assert "generate a new api token" in error_str.lower()


def test_create_issue_with_expired_token_raises_helpful_error(mock_env):
    """Test that create_issue raises helpful error message for expired tokens."""
    client = JiraClient()

    # Mock the API request to return 401 with expiration message
    with patch("requests.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "errorMessages": ["API token has expired"]
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_request.return_value = mock_response

        # Mock field mapper
        mock_field_mapper = MagicMock()
        mock_field_mapper.get_field_id.return_value = None

        with pytest.raises(JiraAuthError) as exc_info:
            client.create_issue(
                issue_type="Story",
                summary="Test story",
                description="Test description",
                priority="Major",
                project_key="PROJ",
                field_mapper=mock_field_mapper
            )

        error = exc_info.value
        assert error.token_expired is True


def test_issue_tracker_auth_error_str_with_expiration(mock_env):
    """Test IssueTrackerAuthError __str__ method with token expiration."""
    error = JiraAuthError(
        "Authentication failed",
        token_expired=True,
        jira_url="https://test.jira.com"
    )

    error_str = str(error)
    assert "Authentication failed" in error_str
    assert "Your JIRA API token has expired" in error_str
    assert "https://test.jira.com/secure/ViewProfile.jspa" in error_str
    assert "Update your JIRA_API_TOKEN environment variable" in error_str
    assert "Reload your shell" in error_str


def test_issue_tracker_auth_error_str_without_expiration(mock_env):
    """Test IssueTrackerAuthError __str__ method without token expiration."""
    error = JiraAuthError(
        "Authentication failed",
        token_expired=False,
        jira_url="https://test.jira.com"
    )

    error_str = str(error)
    assert error_str == "Authentication failed"
    assert "expired" not in error_str.lower()


def test_issue_tracker_auth_error_str_without_jira_url(mock_env):
    """Test IssueTrackerAuthError __str__ method without JIRA URL."""
    error = JiraAuthError(
        "Authentication failed",
        token_expired=True,
        jira_url=None
    )

    error_str = str(error)
    assert error_str == "Authentication failed"
    assert "generate a new api token" not in error_str.lower()


def test_token_expiration_case_insensitive(mock_env):
    """Test that token expiration detection is case-insensitive."""
    client = JiraClient()

    test_cases = [
        {"errorMessages": ["TOKEN EXPIRED"]},
        {"errorMessages": ["Token Expired"]},
        {"errorMessages": ["token expired"]},
        {"errorMessages": ["The token has EXPIRED"]},
        {"errorMessages": ["Expiration date passed"]},
        {"errorMessages": ["EXPIRATION: token no longer valid"]},
    ]

    for test_case in test_cases:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = test_case
        mock_response.text = json.dumps(test_case)

        assert client._is_token_expired(mock_response) is True, f"Failed for: {test_case}"


def test_is_token_expired_handles_malformed_response_gracefully(mock_env):
    """Test that _is_token_expired handles malformed responses without crashing."""
    client = JiraClient()

    # Test with None response
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.side_effect = AttributeError("No json method")
    mock_response.text = None

    # Should not crash, just return False
    assert client._is_token_expired(mock_response) is False


def test_update_issue_with_expired_token(mock_env):
    """Test that update_issue raises helpful error for expired tokens."""
    client = JiraClient()

    with patch("requests.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "errorMessages": ["Your token has expired"]
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_request.return_value = mock_response

        with pytest.raises(JiraAuthError) as exc_info:
            client.update_issue(
                "PROJ-12345",
                {"fields": {"summary": "New summary"}}
            )

        error = exc_info.value
        assert error.token_expired is True
        assert "generate a new api token" in str(error).lower()
