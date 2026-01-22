"""Tests for JIRA issue linking functionality."""

import pytest
import requests

from devflow.jira.client import JiraClient
from devflow.jira.exceptions import (
    JiraApiError,
    JiraAuthError,
    JiraNotFoundError,
    JiraValidationError,
)


def test_get_issue_link_types_success(mock_jira_cli, monkeypatch):
    """Test successfully fetching issue link types."""
    # Mock the REST API response for link types
    def mock_request(method, url, **kwargs):
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 200
            response._content = b'''{
                "issueLinkTypes": [
                    {"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"},
                    {"id": "10001", "name": "Relates", "inward": "relates to", "outward": "relates to"},
                    {"id": "10002", "name": "Duplicates", "inward": "is duplicated by", "outward": "duplicates"}
                ]
            }'''
            return response
        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    link_types = client.get_issue_link_types()

    assert len(link_types) == 3
    assert link_types[0]["name"] == "Blocks"
    assert link_types[0]["inward"] == "is blocked by"
    assert link_types[0]["outward"] == "blocks"
    assert link_types[1]["name"] == "Relates"
    assert link_types[2]["name"] == "Duplicates"


def test_get_issue_link_types_auth_error(mock_jira_cli, monkeypatch):
    """Test fetching issue link types with authentication error."""
    def mock_request(method, url, **kwargs):
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 401
            response._content = b'{"errorMessages":["Unauthorized"]}'
            return response
        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    with pytest.raises(JiraAuthError):
        client.get_issue_link_types()


def test_get_issue_link_types_api_error(mock_jira_cli, monkeypatch):
    """Test fetching issue link types with API error."""
    def mock_request(method, url, **kwargs):
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 500
            response._content = b'{"errorMessages":["Internal server error"]}'
            return response
        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    with pytest.raises(JiraApiError):
        client.get_issue_link_types()


def test_link_issues_blocks_outward(mock_jira_cli, monkeypatch):
    """Test linking issues with 'blocks' relationship (outward)."""
    link_created = False
    link_payload = None

    def mock_request(method, url, **kwargs):
        nonlocal link_created, link_payload

        # Mock issueLinkType endpoint
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 200
            response._content = b'''{
                "issueLinkTypes": [
                    {"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"}
                ]
            }'''
            return response

        # Mock issueLink endpoint
        if "/rest/api/2/issueLink" in url and method == "POST":
            link_created = True
            link_payload = kwargs.get("json", {})
            response = requests.Response()
            response.status_code = 201
            return response

        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    client.link_issues(
        issue_key="PROJ-12345",
        link_to_issue_key="PROJ-5678",
        link_type_description="blocks"
    )

    assert link_created
    assert link_payload["type"]["name"] == "Blocks"
    assert link_payload["outwardIssue"]["key"] == "PROJ-12345"
    assert link_payload["inwardIssue"]["key"] == "PROJ-5678"


def test_link_issues_is_blocked_by_inward(mock_jira_cli, monkeypatch):
    """Test linking issues with 'is blocked by' relationship (inward)."""
    link_created = False
    link_payload = None

    def mock_request(method, url, **kwargs):
        nonlocal link_created, link_payload

        # Mock issueLinkType endpoint
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 200
            response._content = b'''{
                "issueLinkTypes": [
                    {"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"}
                ]
            }'''
            return response

        # Mock issueLink endpoint
        if "/rest/api/2/issueLink" in url and method == "POST":
            link_created = True
            link_payload = kwargs.get("json", {})
            response = requests.Response()
            response.status_code = 201
            return response

        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    client.link_issues(
        issue_key="PROJ-12345",
        link_to_issue_key="PROJ-5678",
        link_type_description="is blocked by"
    )

    assert link_created
    assert link_payload["type"]["name"] == "Blocks"
    assert link_payload["inwardIssue"]["key"] == "PROJ-12345"
    assert link_payload["outwardIssue"]["key"] == "PROJ-5678"


def test_link_issues_case_insensitive(mock_jira_cli, monkeypatch):
    """Test that link type matching is case-insensitive."""
    link_created = False

    def mock_request(method, url, **kwargs):
        nonlocal link_created

        # Mock issueLinkType endpoint
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 200
            response._content = b'''{
                "issueLinkTypes": [
                    {"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"}
                ]
            }'''
            return response

        # Mock issueLink endpoint
        if "/rest/api/2/issueLink" in url and method == "POST":
            link_created = True
            response = requests.Response()
            response.status_code = 201
            return response

        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    # Test uppercase
    client.link_issues(
        issue_key="PROJ-12345",
        link_to_issue_key="PROJ-5678",
        link_type_description="BLOCKS"
    )

    assert link_created


def test_link_issues_invalid_link_type(mock_jira_cli, monkeypatch):
    """Test linking with invalid link type raises validation error."""
    def mock_request(method, url, **kwargs):
        # Mock issueLinkType endpoint
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 200
            response._content = b'''{
                "issueLinkTypes": [
                    {"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"},
                    {"id": "10001", "name": "Relates", "inward": "relates to", "outward": "relates to"}
                ]
            }'''
            return response

        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    with pytest.raises(JiraValidationError) as exc_info:
        client.link_issues(
            issue_key="PROJ-12345",
            link_to_issue_key="PROJ-5678",
            link_type_description="invalid type"
        )

    # Check error message contains available types
    assert "Invalid linked issue type" in str(exc_info.value)
    assert "blocks" in exc_info.value.error_messages[0]
    assert "is blocked by" in exc_info.value.error_messages[0]
    assert "relates to" in exc_info.value.error_messages[0]


def test_link_issues_not_found_error(mock_jira_cli, monkeypatch):
    """Test linking with non-existent issue."""
    def mock_request(method, url, **kwargs):
        # Mock issueLinkType endpoint
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 200
            response._content = b'''{
                "issueLinkTypes": [
                    {"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"}
                ]
            }'''
            return response

        # Mock issueLink endpoint with 404
        if "/rest/api/2/issueLink" in url and method == "POST":
            response = requests.Response()
            response.status_code = 404
            response._content = b'{"errorMessages":["Issue not found"]}'
            return response

        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    with pytest.raises(JiraNotFoundError):
        client.link_issues(
            issue_key="PROJ-12345",
            link_to_issue_key="PROJ-99999",
            link_type_description="blocks"
        )


def test_link_issues_with_comment(mock_jira_cli, monkeypatch):
    """Test linking issues with a comment."""
    link_payload = None

    def mock_request(method, url, **kwargs):
        nonlocal link_payload

        # Mock issueLinkType endpoint
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 200
            response._content = b'''{
                "issueLinkTypes": [
                    {"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"}
                ]
            }'''
            return response

        # Mock issueLink endpoint
        if "/rest/api/2/issueLink" in url and method == "POST":
            link_payload = kwargs.get("json", {})
            response = requests.Response()
            response.status_code = 201
            return response

        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    client.link_issues(
        issue_key="PROJ-12345",
        link_to_issue_key="PROJ-5678",
        link_type_description="blocks",
        comment="Blocking this issue because..."
    )

    assert link_payload is not None
    assert "comment" in link_payload
    assert link_payload["comment"]["body"] == "Blocking this issue because..."


def test_link_issues_validation_error_400(mock_jira_cli, monkeypatch):
    """Test linking issues with validation error from JIRA API."""
    def mock_request(method, url, **kwargs):
        # Mock issueLinkType endpoint
        if "/rest/api/2/issueLinkType" in url:
            response = requests.Response()
            response.status_code = 200
            response._content = b'''{
                "issueLinkTypes": [
                    {"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"}
                ]
            }'''
            return response

        # Mock issueLink endpoint with 400
        if "/rest/api/2/issueLink" in url and method == "POST":
            response = requests.Response()
            response.status_code = 400
            response._content = b'''{
                "errorMessages": ["Link already exists"],
                "errors": {"linkType": "Duplicate link"}
            }'''
            return response

        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request)

    client = JiraClient()
    with pytest.raises(JiraValidationError) as exc_info:
        client.link_issues(
            issue_key="PROJ-12345",
            link_to_issue_key="PROJ-5678",
            link_type_description="blocks"
        )

    assert "Validation failed" in str(exc_info.value)
    assert "Link already exists" in exc_info.value.error_messages
    assert "linkType" in exc_info.value.field_errors
