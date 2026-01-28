"""Tests for daf jira update command."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from devflow.jira.client import JiraClient
from devflow.jira.field_mapper import JiraFieldMapper
from devflow.jira.exceptions import JiraApiError, JiraNotFoundError, JiraValidationError


@pytest.fixture
def mock_jira_client(monkeypatch):
    """Create a JiraClient with mocked API requests."""
    monkeypatch.setenv("JIRA_API_TOKEN", "mock-token")
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")

    client = JiraClient()
    return client


@pytest.fixture
def mock_field_mapper():
    """Create a mock JiraFieldMapper."""
    mapper = MagicMock(spec=JiraFieldMapper)
    mapper.get_field_id.side_effect = lambda field_name: {
        "workstream": "customfield_12319275",
        "acceptance_criteria": "customfield_12315940",
        "epic_link": "customfield_12311140",
    }.get(field_name, field_name)
    mapper._cache = {}
    return mapper


def test_update_issue_description(mock_jira_client, monkeypatch):
    """Test updating issue description."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            assert "description" in payload["fields"]
            assert payload["fields"]["description"] == "New description"
            response.status_code = 204
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    mock_jira_client.update_issue(
        "PROJ-12345",
        {"fields": {"description": "New description"}}
    )


def test_update_issue_summary(mock_jira_client, monkeypatch):
    """Test updating issue summary."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            assert "summary" in payload["fields"]
            assert payload["fields"]["summary"] == "New summary"
            response.status_code = 204
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    mock_jira_client.update_issue(
        "PROJ-12345",
        {"fields": {"summary": "New summary"}}
    )


def test_update_issue_priority(mock_jira_client, monkeypatch):
    """Test updating issue priority."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            assert "priority" in payload["fields"]
            assert payload["fields"]["priority"] == {"name": "Critical"}
            response.status_code = 204
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    mock_jira_client.update_issue(
        "PROJ-12345",
        {"fields": {"priority": {"name": "Critical"}}}
    )


def test_update_issue_assignee(mock_jira_client, monkeypatch):
    """Test updating issue assignee."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            assert "assignee" in payload["fields"]
            assert payload["fields"]["assignee"] == {"name": "jdoe"}
            response.status_code = 204
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    mock_jira_client.update_issue(
        "PROJ-12345",
        {"fields": {"assignee": {"name": "jdoe"}}}
    )


def test_update_issue_clear_assignee(mock_jira_client, monkeypatch):
    """Test clearing issue assignee."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            assert "assignee" in payload["fields"]
            assert payload["fields"]["assignee"] is None
            response.status_code = 204
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    mock_jira_client.update_issue(
        "PROJ-12345",
        {"fields": {"assignee": None}}
    )


def test_update_issue_multiple_fields(mock_jira_client, monkeypatch):
    """Test updating multiple fields at once."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            assert "description" in payload["fields"]
            assert "summary" in payload["fields"]
            assert "priority" in payload["fields"]
            assert payload["fields"]["description"] == "New description"
            assert payload["fields"]["summary"] == "New summary"
            assert payload["fields"]["priority"] == {"name": "Major"}
            response.status_code = 204
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    mock_jira_client.update_issue(
        "PROJ-12345",
        {
            "fields": {
                "description": "New description",
                "summary": "New summary",
                "priority": {"name": "Major"}
            }
        }
    )


def test_update_issue_custom_field(mock_jira_client, monkeypatch):
    """Test updating custom field (acceptance criteria)."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            assert "customfield_12315940" in payload["fields"]
            assert payload["fields"]["customfield_12315940"] == "- New criterion 1\n- New criterion 2"
            response.status_code = 204
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    mock_jira_client.update_issue(
        "PROJ-12345",
        {"fields": {"customfield_12315940": "- New criterion 1\n- New criterion 2"}}
    )


def test_update_issue_workstream(mock_jira_client, monkeypatch):
    """Test updating workstream field."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            assert "customfield_12319275" in payload["fields"]
            assert payload["fields"]["customfield_12319275"] == [{"value": "Hosted Services"}]
            response.status_code = 204
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    mock_jira_client.update_issue(
        "PROJ-12345",
        {"fields": {"customfield_12319275": [{"value": "Hosted Services"}]}}
    )


def test_update_issue_failure_400(mock_jira_client, monkeypatch):
    """Test update_issue raises JiraValidationError on 400 error."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        response.status_code = 400
        response.json.return_value = {
            "errorMessages": ["Invalid field value"],
            "errors": {}
        }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    with pytest.raises(JiraValidationError):
        mock_jira_client.update_issue(
            "PROJ-12345",
            {"fields": {"description": "New description"}}
        )


def test_update_issue_failure_404(mock_jira_client, monkeypatch):
    """Test update_issue raises JiraNotFoundError on 404 error."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        response.status_code = 404
        response.text = "Issue not found"
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    with pytest.raises(JiraNotFoundError):
        mock_jira_client.update_issue(
            "PROJ-99999",
            {"fields": {"description": "New description"}}
        )


def test_update_issue_field_error(mock_jira_client, monkeypatch):
    """Test update_issue handles field errors properly."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "GET" and "/rest/api/2/field" in endpoint:
            # Mock field metadata response
            response.status_code = 200
            response.json.return_value = [
                {"id": "customfield_12319275", "name": "Workstream"},
                {"id": "customfield_12315940", "name": "Acceptance Criteria"}
            ]
        elif method == "PUT":
            response.status_code = 400
            response.json.return_value = {
                "errorMessages": [],
                "errors": {
                    "customfield_12319275": "Field value is required"
                }
            }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    with pytest.raises(JiraValidationError):
        mock_jira_client.update_issue(
            "PROJ-12345",
            {"fields": {"customfield_12319275": None}}
        )


def test_update_issue_runtime_error(mock_jira_client, monkeypatch):
    """Test update_issue raises JiraApiError on RuntimeError."""
    def mock_api_request(method, endpoint, **kwargs):
        raise RuntimeError("API connection failed")

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    with pytest.raises(JiraApiError):
        mock_jira_client.update_issue(
            "PROJ-12345",
            {"fields": {"description": "New description"}}
        )


def test_update_issue_generic_exception(mock_jira_client, monkeypatch):
    """Test update_issue raises JiraApiError on generic exceptions."""
    def mock_api_request(method, endpoint, **kwargs):
        raise Exception("Unexpected error")

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    with pytest.raises(JiraApiError):
        mock_jira_client.update_issue(
            "PROJ-12345",
            {"fields": {"description": "New description"}}
        )


def test_update_issue_git_pull_request(mock_jira_client, monkeypatch):
    """Test updating git-pull-request field."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            assert "customfield_12310220" in payload["fields"]
            assert payload["fields"]["customfield_12310220"] == "https://github.com/org/repo/pull/123"
            response.status_code = 204
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    mock_jira_client.update_issue(
        "PROJ-12345",
        {"fields": {"customfield_12310220": "https://github.com/org/repo/pull/123"}}
    )


def test_get_ticket_pr_links(mock_jira_client, monkeypatch):
    """Test getting current PR links from a ticket."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "GET" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "customfield_12310220": "https://github.com/org/repo/pull/123,https://github.com/org/repo/pull/456"
                }
            }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Provide field_mappings to enable PR link extraction
    field_mappings = {
        "git_pull_request": {"id": "customfield_12310220"}
    }

    pr_links = mock_jira_client.get_ticket_pr_links("PROJ-12345", field_mappings=field_mappings)

    assert pr_links == "https://github.com/org/repo/pull/123,https://github.com/org/repo/pull/456"


def test_get_ticket_pr_links_empty(mock_jira_client, monkeypatch):
    """Test getting PR links when none exist."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "GET" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "customfield_12310220": ""
                }
            }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Provide field_mappings to enable PR link extraction
    field_mappings = {
        "git_pull_request": {"id": "customfield_12310220"}
    }

    pr_links = mock_jira_client.get_ticket_pr_links("PROJ-12345", field_mappings=field_mappings)

    assert pr_links == ""


def test_get_ticket_pr_links_as_list(mock_jira_client, monkeypatch):
    """Test getting PR links when JIRA returns them as a list (multiurl field behavior)."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "GET" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "customfield_12310220": [
                        "https://github.com/org/repo/pull/123",
                        "https://github.com/org/repo/pull/456"
                    ]
                }
            }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Provide field_mappings to enable PR link extraction
    field_mappings = {
        "git_pull_request": {"id": "customfield_12310220"}
    }

    pr_links = mock_jira_client.get_ticket_pr_links("PROJ-12345", field_mappings=field_mappings)

    # Should convert list to comma-separated string
    assert pr_links == "https://github.com/org/repo/pull/123,https://github.com/org/repo/pull/456"


def test_get_ticket_pr_links_as_empty_list(mock_jira_client, monkeypatch):
    """Test getting PR links when JIRA returns an empty list."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "GET" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "customfield_12310220": []
                }
            }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Provide field_mappings to enable PR link extraction
    field_mappings = {
        "git_pull_request": {"id": "customfield_12310220"}
    }

    pr_links = mock_jira_client.get_ticket_pr_links("PROJ-12345", field_mappings=field_mappings)

    # Should return empty string for empty list
    assert pr_links == ""


def test_get_ticket_detailed_with_pr_links(mock_jira_client, monkeypatch):
    """Test get_ticket_detailed includes PR links."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()
        if method == "GET" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "issuetype": {"name": "Story"},
                    "status": {"name": "In Progress"},
                    "summary": "Test story",
                    "description": "Test description",
                    "priority": {"name": "Major"},
                    "assignee": {"displayName": "John Doe"},
                    "reporter": {"displayName": "Jane Doe"},
                    "customfield_12310220": "https://github.com/org/repo/pull/123"
                }
            }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Provide field_mappings to enable PR link extraction
    field_mappings = {
        "git_pull_request": {"id": "customfield_12310220"}
    }

    ticket = mock_jira_client.get_ticket_detailed("PROJ-12345", field_mappings=field_mappings)

    assert ticket is not None
    assert ticket["git_pull_request"] == "https://github.com/org/repo/pull/123"


def test_get_ticket_pr_links_without_cached_field_mappings(mock_jira_client, monkeypatch):
    """Test getting PR links when git_pull_request field is not in cached field_mappings.

    This test verifies the fix for PROJ-60638 where get_ticket_pr_links would return None
    if the git_pull_request field wasn't cached, causing PR URLs to be overwritten instead
    of appended.
    """
    api_requests = []

    def mock_api_request(method, endpoint, **kwargs):
        api_requests.append((method, endpoint, kwargs))
        response = Mock()

        # Mock /rest/api/2/field for all fields
        if method == "GET" and endpoint == "/rest/api/2/field":
            response.status_code = 200
            response.json.return_value = [
                {
                    "id": "customfield_12310220",
                    "name": "Git Pull Request",
                    "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:url"}
                }
            ]
        # Mock editmeta API call for field discovery
        elif method == "GET" and "/editmeta" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "customfield_12310220": {
                        "name": "Git Pull Request",
                        "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:url"},
                        "operations": ["set"]
                    }
                }
            }
        # Mock ticket GET with PR links (must include params check)
        elif method == "GET" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            response.status_code = 200
            # Check if this is a field-specific query
            if "params" in kwargs and kwargs["params"].get("fields") == "customfield_12310220":
                response.json.return_value = {
                    "fields": {
                        "customfield_12310220": "https://github.com/org/repo/pull/123"
                    }
                }
            else:
                response.json.return_value = {
                    "fields": {
                        "customfield_12310220": "https://github.com/org/repo/pull/123"
                    }
                }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Call without field_mappings (simulating missing cache)
    pr_links = mock_jira_client.get_ticket_pr_links("PROJ-12345", field_mappings=None)

    # Should discover the field and return the existing PR link, not None
    assert pr_links == "https://github.com/org/repo/pull/123"

    # Verify that editmeta was called for discovery
    editmeta_calls = [req for req in api_requests if "/editmeta" in req[1]]
    assert len(editmeta_calls) == 1


def test_get_ticket_pr_links_with_empty_field_mappings(mock_jira_client, monkeypatch):
    """Test getting PR links when field_mappings is an empty dict.

    This tests the edge case where field_mappings exists but doesn't contain git_pull_request.
    """
    api_requests = []

    def mock_api_request(method, endpoint, **kwargs):
        api_requests.append((method, endpoint, kwargs))
        response = Mock()

        # Mock /rest/api/2/field for all fields
        if method == "GET" and endpoint == "/rest/api/2/field":
            response.status_code = 200
            response.json.return_value = [
                {
                    "id": "customfield_12310220",
                    "name": "Git Pull Request",
                    "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:url"}
                }
            ]
        # Mock editmeta API call for field discovery
        elif method == "GET" and "/editmeta" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "customfield_12310220": {
                        "name": "Git Pull Request",
                        "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:url"},
                        "operations": ["set"]
                    }
                }
            }
        # Mock ticket GET with multiple PR links
        elif method == "GET" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "customfield_12310220": "https://github.com/org/repo/pull/123,https://github.com/org/repo/pull/456"
                }
            }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Call with empty field_mappings
    pr_links = mock_jira_client.get_ticket_pr_links("PROJ-12345", field_mappings={})

    # Should discover the field and return the existing PR links
    assert pr_links == "https://github.com/org/repo/pull/123,https://github.com/org/repo/pull/456"


def test_get_ticket_pr_links_field_not_available(mock_jira_client, monkeypatch):
    """Test getting PR links when git_pull_request field doesn't exist for the ticket type."""

    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()

        # Mock /rest/api/2/field for all fields
        if method == "GET" and endpoint == "/rest/api/2/field":
            response.status_code = 200
            response.json.return_value = [
                {
                    "id": "summary",
                    "name": "Summary",
                    "schema": {"type": "string"}
                }
            ]
        # Mock editmeta API call - field not available
        elif method == "GET" and "/editmeta" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "summary": {
                        "name": "Summary",
                        "schema": {"type": "string"}
                    }
                    # git_pull_request field is NOT in the editable fields
                }
            }
        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Call without field_mappings - should raise JiraNotFoundError when field doesn't exist
    with pytest.raises(JiraNotFoundError):
        mock_jira_client.get_ticket_pr_links("PROJ-12345", field_mappings=None)


def test_multiple_pr_creation_scenario(mock_jira_client, monkeypatch):
    """Test the full scenario of creating multiple PRs for the same ticket.

    This is an integration test simulating the bug scenario:
    1. First PR created - JIRA has no PRs
    2. Second PR created - JIRA has first PR, should append not overwrite

    Verifies the fix for PROJ-60638.
    """
    # Track the current state of PR links in JIRA
    jira_pr_state = ""
    api_requests = []

    def mock_api_request(method, endpoint, **kwargs):
        nonlocal jira_pr_state
        api_requests.append((method, endpoint, kwargs))
        response = Mock()

        # Mock /rest/api/2/field for all fields
        if method == "GET" and endpoint == "/rest/api/2/field":
            response.status_code = 200
            response.json.return_value = [
                {
                    "id": "customfield_12310220",
                    "name": "Git Pull Request",
                    "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:url"}
                }
            ]
        # Mock editmeta API call for field discovery
        elif method == "GET" and "/editmeta" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "customfield_12310220": {
                        "name": "Git Pull Request",
                        "schema": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:url"},
                        "operations": ["set"]
                    }
                }
            }
        # Mock ticket GET with current PR state
        elif method == "GET" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "fields": {
                    "customfield_12310220": jira_pr_state
                }
            }
        # Mock ticket PUT to update PR field
        elif method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            payload = kwargs.get("json", {})
            if "customfield_12310220" in payload.get("fields", {}):
                jira_pr_state = payload["fields"]["customfield_12310220"]
            response.status_code = 204

        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Scenario: First PR creation (no existing PRs, no cached field mapping)
    current_prs = mock_jira_client.get_ticket_pr_links("PROJ-12345", field_mappings=None)
    assert current_prs == ""  # No existing PRs

    # Add first PR
    new_pr_url = "https://github.com/org/repo/pull/123"
    updated_prs = new_pr_url if not current_prs else f"{current_prs},{new_pr_url}"
    mock_jira_client.update_ticket_field("PROJ-12345", "customfield_12310220", updated_prs)
    assert jira_pr_state == "https://github.com/org/repo/pull/123"

    # Scenario: Second PR creation (one existing PR, still no cached field mapping)
    current_prs = mock_jira_client.get_ticket_pr_links("PROJ-12345", field_mappings=None)

    # This is the critical assertion - should return the existing PR, not None
    assert current_prs == "https://github.com/org/repo/pull/123"

    # Add second PR
    new_pr_url = "https://github.com/org/repo/pull/456"
    updated_prs = f"{current_prs},{new_pr_url}"
    mock_jira_client.update_ticket_field("PROJ-12345", "customfield_12310220", updated_prs)

    # Verify both PRs are present (not overwritten)
    assert jira_pr_state == "https://github.com/org/repo/pull/123,https://github.com/org/repo/pull/456"


def test_cli_field_option_filters_non_custom_fields(monkeypatch):
    """Test that --field option filters out non-custom fields to avoid duplicate kwargs.

    This test verifies the fix for PROJ-60124 where using --field with hardcoded
    fields (like acceptance_criteria, workstream, etc.) caused TypeError due to
    duplicate keyword arguments.
    """
    # Mock the config field mappings directly at the point where they're accessed
    mock_field_mappings = {
        "acceptance_criteria": {
            "id": "customfield_12315940",
            "name": "Acceptance Criteria",
            "type": "string"
        },
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream",
            "type": "array"
        },
        "summary": {
            "id": "summary",
            "name": "Summary",
            "type": "string"
        },
        "priority": {
            "id": "priority",
            "name": "Priority",
            "type": "priority"
        },
        "epic_link": {
            "id": "customfield_12311140",
            "name": "Epic Link",
            "type": "string"
        }
    }

    from devflow.config.models import JiraConfig

    # Create a minimal mock config
    class MockConfig:
        def __init__(self):
            self.jira = type('obj', (object,), {
                'field_mappings': mock_field_mappings,
                'url': 'https://jira.example.com'
            })()

    # Test the filtering logic directly
    from devflow.cli.commands.jira_update_dynamic import create_jira_update_command

    # Mock ConfigLoader to return our mock config
    def mock_load_config(self):
        return MockConfig()

    monkeypatch.setattr("devflow.config.loader.ConfigLoader.load_config", mock_load_config)

    # Mock update_jira_issue to prevent actual API calls
    update_called = []

    def mock_update(**kwargs):
        update_called.append(kwargs)

    monkeypatch.setattr("devflow.cli.commands.jira_update_command.update_jira_issue", mock_update)
    monkeypatch.setenv("JIRA_API_TOKEN", "mock-token")

    # Create the command and test it
    command = create_jira_update_command()

    from click.testing import CliRunner
    runner = CliRunner()

    # Test 1: Using --field with a non-custom field (acceptance_criteria)
    # This should filter it out and warn, preventing the TypeError
    result = runner.invoke(command, [
        'PROJ-12345',
        '--field', 'acceptance_criteria=Test'
    ])

    # The key assertion: should NOT have TypeError
    assert "TypeError" not in result.output
    assert "got multiple values for keyword argument" not in result.output

    # Test 2: Using --field with a custom field (epic_link) should work
    update_called.clear()
    result = runner.invoke(command, [
        'PROJ-12345',
        '--field', 'epic_link=PROJ-59000'
    ])

    assert "TypeError" not in result.output
    # Custom field should be passed through in custom_fields dict
    if update_called:
        assert 'custom_fields' in update_called[0]
        assert 'epic_link' in update_called[0]['custom_fields']


def test_transition_ticket_only(mock_jira_client, monkeypatch):
    """Test transitioning ticket status without updating any fields."""
    transitions_fetched = False
    transition_performed = False

    def mock_api_request(method, endpoint, **kwargs):
        nonlocal transitions_fetched, transition_performed
        response = Mock()

        # Mock GET transitions
        if method == "GET" and "/transitions" in endpoint:
            transitions_fetched = True
            response.status_code = 200
            response.json.return_value = {
                "transitions": [
                    {"id": "11", "to": {"name": "In Progress"}},
                    {"id": "21", "to": {"name": "Review"}},
                    {"id": "31", "to": {"name": "Closed"}}
                ]
            }
        # Mock POST transition
        elif method == "POST" and "/transitions" in endpoint:
            transition_performed = True
            payload = kwargs.get("json", {})
            assert payload["transition"]["id"] == "11"
            response.status_code = 204

        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Transition ticket
    mock_jira_client.transition_ticket("PROJ-12345", "In Progress")

    assert transitions_fetched
    assert transition_performed


def test_transition_ticket_invalid_status(mock_jira_client, monkeypatch):
    """Test transitioning to invalid status raises JiraNotFoundError."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()

        # Mock GET transitions
        if method == "GET" and "/transitions" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "transitions": [
                    {"id": "11", "to": {"name": "In Progress"}},
                    {"id": "21", "to": {"name": "Review"}}
                ]
            }

        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Try to transition to invalid status
    with pytest.raises(JiraNotFoundError) as exc_info:
        mock_jira_client.transition_ticket("PROJ-12345", "Invalid Status")

    assert "Invalid Status" in str(exc_info.value)
    assert "Available transitions:" in str(exc_info.value)


def test_transition_ticket_with_validation_error(mock_jira_client, monkeypatch):
    """Test transitioning when transition requires additional fields."""
    def mock_api_request(method, endpoint, **kwargs):
        response = Mock()

        # Mock GET transitions
        if method == "GET" and "/transitions" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "transitions": [
                    {"id": "31", "to": {"name": "Closed"}}
                ]
            }
        # Mock POST transition with validation error
        elif method == "POST" and "/transitions" in endpoint:
            response.status_code = 400
            response.json.return_value = {
                "errorMessages": ["Resolution is required when closing"],
                "errors": {
                    "resolution": "This field is required"
                }
            }

        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Try to transition without required fields
    with pytest.raises(JiraValidationError) as exc_info:
        mock_jira_client.transition_ticket("PROJ-12345", "Closed")

    assert exc_info.value.field_errors.get("resolution") == "This field is required"


def test_update_with_status_transition(mock_jira_client, monkeypatch):
    """Test updating fields and transitioning status in the same command."""
    field_updated = False
    status_transitioned = False

    def mock_api_request(method, endpoint, **kwargs):
        nonlocal field_updated, status_transitioned
        response = Mock()

        # Mock PUT for field update
        if method == "PUT" and "/rest/api/2/issue/PROJ-12345" in endpoint:
            field_updated = True
            payload = kwargs.get("json", {})
            assert "priority" in payload["fields"]
            response.status_code = 204
        # Mock GET transitions
        elif method == "GET" and "/transitions" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "transitions": [
                    {"id": "21", "to": {"name": "Review"}}
                ]
            }
        # Mock POST transition
        elif method == "POST" and "/transitions" in endpoint:
            status_transitioned = True
            response.status_code = 204

        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # First update fields
    mock_jira_client.update_issue(
        "PROJ-12345",
        {"fields": {"priority": {"name": "Major"}}}
    )

    # Then transition
    mock_jira_client.transition_ticket("PROJ-12345", "Review")

    assert field_updated
    assert status_transitioned


def test_transition_ticket_case_insensitive(mock_jira_client, monkeypatch):
    """Test that status transition is case-insensitive."""
    transition_performed = False

    def mock_api_request(method, endpoint, **kwargs):
        nonlocal transition_performed
        response = Mock()

        # Mock GET transitions
        if method == "GET" and "/transitions" in endpoint:
            response.status_code = 200
            response.json.return_value = {
                "transitions": [
                    {"id": "11", "to": {"name": "In Progress"}}
                ]
            }
        # Mock POST transition
        elif method == "POST" and "/transitions" in endpoint:
            transition_performed = True
            payload = kwargs.get("json", {})
            assert payload["transition"]["id"] == "11"
            response.status_code = 204

        return response

    monkeypatch.setattr(mock_jira_client, "_api_request", mock_api_request)

    # Transition with different case
    mock_jira_client.transition_ticket("PROJ-12345", "in progress")

    assert transition_performed


def test_update_single_field_does_not_include_config_defaults():
    """Test that updating a single field does not include system_field_defaults from config.

    This tests the fix for AAP-64346: when updating a single custom field like acceptance_criteria,
    the update should NOT include system_field_defaults from config (components, labels, etc.)
    as those may be non-editable fields that would cause the update to fail.
    """
    from devflow.cli.commands.jira_update_command import update_jira_issue
    from devflow.config.models import Config, JiraConfig, RepoConfig
    from unittest.mock import patch, MagicMock

    # Create a config with system_field_defaults
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            transitions={},  # Required field
            system_field_defaults={
                "components": [{"name": "ansible-saas"}],
                "labels": ["backend"],
                "attachment": []  # Non-editable field that would cause error
            },
            field_mappings={
                "acceptance_criteria": {
                    "id": "customfield_12315940",
                    "name": "Acceptance Criteria",
                    "type": "string"
                }
            }
        ),
        repos=RepoConfig(workspaces=[])  # Required field
    )

    # Track what fields are in the update payload
    update_payload_fields = None

    def mock_update_issue(issue_key, payload):
        nonlocal update_payload_fields
        update_payload_fields = list(payload["fields"].keys())

    with patch('devflow.cli.commands.jira_update_command.ConfigLoader') as mock_config_loader, \
         patch('devflow.cli.commands.jira_update_command.JiraClient') as mock_client_class, \
         patch('devflow.cli.commands.jira_update_command.JiraFieldMapper') as mock_mapper_class:

        # Mock ConfigLoader
        mock_loader_instance = MagicMock()
        mock_loader_instance.load_config.return_value = config
        mock_config_loader.return_value = mock_loader_instance

        # Mock JiraClient
        mock_client = MagicMock()
        mock_client.update_issue.side_effect = mock_update_issue
        mock_client_class.return_value = mock_client

        # Mock JiraFieldMapper
        mock_mapper = MagicMock()
        mock_mapper.discover_editable_fields.return_value = config.jira.field_mappings
        mock_mapper.field_mappings = config.jira.field_mappings
        mock_mapper_class.return_value = mock_mapper

        # Update only acceptance_criteria field
        # The bug would cause this to also try to update components, labels, and attachment from system_field_defaults
        update_jira_issue(
            issue_key="AAP-64346",
            custom_fields={"acceptance_criteria": "- [] Test criterion"},
            system_fields={}  # No system fields explicitly provided
        )

        # Verify that ONLY the acceptance_criteria field is in the payload
        # NOT components, labels, or attachment from system_field_defaults
        assert update_payload_fields is not None, "update_issue was not called"
        assert "customfield_12315940" in update_payload_fields, "acceptance_criteria field should be in payload"
        assert "components" not in update_payload_fields, "components from config defaults should NOT be in payload"
        assert "labels" not in update_payload_fields, "labels from config defaults should NOT be in payload"
        assert "attachment" not in update_payload_fields, "attachment from config defaults should NOT be in payload"

        # Should only have the one custom field we specified
        assert len(update_payload_fields) == 1, f"Expected 1 field, got {len(update_payload_fields)}: {update_payload_fields}"
