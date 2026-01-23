"""Tests for JIRA client authentication types."""

import os
from unittest.mock import MagicMock, patch

import pytest

from devflow.jira.client import JiraClient
from devflow.jira.exceptions import JiraAuthError


@pytest.fixture
def mock_env_bearer(monkeypatch):
    """Set up environment for bearer authentication."""
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token-123")
    monkeypatch.setenv("JIRA_AUTH_TYPE", "bearer")
    monkeypatch.setenv("JIRA_URL", "https://test.jira.com")


@pytest.fixture
def mock_env_basic(monkeypatch):
    """Set up environment for basic authentication."""
    monkeypatch.setenv("JIRA_API_TOKEN", "test-basic-token")
    monkeypatch.setenv("JIRA_AUTH_TYPE", "basic")
    monkeypatch.setenv("JIRA_URL", "https://test.jira.com")


@pytest.fixture
def mock_env_no_auth_type(monkeypatch):
    """Set up environment without JIRA_AUTH_TYPE (should default to bearer)."""
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token-default")
    monkeypatch.setenv("JIRA_URL", "https://test.jira.com")
    # Don't set JIRA_AUTH_TYPE to test default behavior


def test_get_auth_header_bearer(mock_env_bearer):
    """Test that bearer auth type generates correct header."""
    client = JiraClient()
    auth_header = client._get_auth_header()

    assert auth_header == "Bearer test-token-123"


def test_get_auth_header_basic(mock_env_basic):
    """Test that basic auth type generates correct header."""
    client = JiraClient()
    auth_header = client._get_auth_header()

    assert auth_header == "Basic test-basic-token"


def test_get_auth_header_default_to_bearer(mock_env_no_auth_type):
    """Test that auth type defaults to bearer when not specified."""
    client = JiraClient()
    auth_header = client._get_auth_header()

    assert auth_header == "Bearer test-token-default"


def test_get_auth_header_no_token(monkeypatch):
    """Test that _get_auth_header raises error when JIRA_API_TOKEN not set."""
    # Don't set JIRA_API_TOKEN
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    client = JiraClient()

    with pytest.raises(JiraAuthError, match="JIRA_API_TOKEN not set"):
        client._get_auth_header()


def test_api_request_uses_bearer_auth(mock_env_bearer):
    """Test that API requests use bearer authentication header."""
    client = JiraClient()

    # Mock the requests.request call
    with patch("requests.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "key": "PROJ-12345",
            "fields": {
                "summary": "Test",
                "status": {"name": "New"},
                "issuetype": {"name": "Story"}
            }
        }
        mock_request.return_value = mock_response

        # Make an API request
        response = client._api_request("GET", "/rest/api/2/issue/PROJ-12345")

        # Verify the request was made with correct auth header
        assert mock_request.called
        call_kwargs = mock_request.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-token-123"


def test_api_request_uses_basic_auth(mock_env_basic):
    """Test that API requests use basic authentication header."""
    client = JiraClient()

    # Mock the requests.request call
    with patch("requests.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "key": "PROJ-12345",
            "fields": {
                "summary": "Test",
                "status": {"name": "New"},
                "issuetype": {"name": "Story"}
            }
        }
        mock_request.return_value = mock_response

        # Make an API request
        response = client._api_request("GET", "/rest/api/2/issue/PROJ-12345")

        # Verify the request was made with correct auth header
        assert mock_request.called
        call_kwargs = mock_request.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["Authorization"] == "Basic test-basic-token"


def test_get_ticket_uses_auth_header(mock_env_bearer):
    """Test that get_ticket method uses the correct auth header."""
    client = JiraClient()

    # Mock the requests.request call
    with patch("requests.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "key": "PROJ-12345",
            "fields": {
                "summary": "Test ticket",
                "status": {"name": "New"},
                "issuetype": {"name": "Story"}
            }
        }
        mock_request.return_value = mock_response

        # Get a ticket
        ticket = client.get_ticket("PROJ-12345")

        # Verify the request was made with correct auth header
        assert mock_request.called
        call_kwargs = mock_request.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-token-123"

        # Verify ticket data was returned
        assert ticket is not None
        assert ticket["key"] == "PROJ-12345"


def test_attach_file_uses_auth_header(mock_env_bearer, tmp_path):
    """Test that attach_file method uses the correct auth header."""
    client = JiraClient()

    # Create a temporary file to attach
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # Mock the requests.post call
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Attach file - now returns None on success
        client.attach_file("PROJ-12345", str(test_file))

        # Verify the request was made with correct auth header
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-token-123"


def test_auth_type_case_insensitive(monkeypatch):
    """Test that JIRA_AUTH_TYPE is case-insensitive."""
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    monkeypatch.setenv("JIRA_AUTH_TYPE", "BEARER")  # Uppercase
    monkeypatch.setenv("JIRA_URL", "https://test.jira.com")

    client = JiraClient()
    auth_header = client._get_auth_header()

    # Should be normalized to lowercase and work correctly
    assert auth_header == "Bearer test-token"


def test_unknown_auth_type_defaults_to_bearer(monkeypatch):
    """Test that unknown auth types default to bearer."""
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    monkeypatch.setenv("JIRA_AUTH_TYPE", "unknown-type")
    monkeypatch.setenv("JIRA_URL", "https://test.jira.com")

    client = JiraClient()
    auth_header = client._get_auth_header()

    # Should default to bearer for unknown types
    assert auth_header == "Bearer test-token"
