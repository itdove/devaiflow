"""Tests for JIRA field mapper empty response handling."""

from unittest.mock import Mock

import pytest

from devflow.jira.field_mapper import JiraFieldMapper


def test_fetch_all_fields_empty_list():
    """Test that _fetch_all_fields raises error when API returns empty list."""
    mock_client = Mock()

    # Mock empty response
    empty_response = Mock()
    empty_response.status_code = 200
    empty_response.json.return_value = []

    mock_client._api_request.return_value = empty_response

    mapper = JiraFieldMapper(mock_client)

    # Should raise RuntimeError with helpful message
    with pytest.raises(RuntimeError, match="JIRA API returned 0 fields"):
        mapper._fetch_all_fields()


def test_fetch_all_fields_invalid_format():
    """Test that _fetch_all_fields raises error when API returns invalid format."""
    mock_client = Mock()

    # Mock invalid response (dict instead of list)
    invalid_response = Mock()
    invalid_response.status_code = 200
    invalid_response.json.return_value = {"error": "something"}

    mock_client._api_request.return_value = invalid_response

    mapper = JiraFieldMapper(mock_client)

    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="invalid response format"):
        mapper._fetch_all_fields()


def test_discover_fields_empty_response_error_message():
    """Test that discover_fields provides helpful error when fields list is empty."""
    mock_client = Mock()

    # Mock empty response
    empty_response = Mock()
    empty_response.status_code = 200
    empty_response.json.return_value = []

    mock_client._api_request.return_value = empty_response

    mapper = JiraFieldMapper(mock_client)

    # Should raise RuntimeError with helpful message about permissions
    with pytest.raises(RuntimeError) as exc_info:
        mapper.discover_fields("PROJ")

    error_message = str(exc_info.value)
    assert "JIRA API returned 0 fields" in error_message
    assert "permissions" in error_message.lower()
    assert "configuration" in error_message.lower()
