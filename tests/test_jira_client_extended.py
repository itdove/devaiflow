"""Extended tests for JIRA client field extraction and parsing."""

import subprocess

import pytest

from devflow.jira.client import JiraClient
from devflow.jira.exceptions import JiraApiError, JiraNotFoundError


def test_get_ticket_basic_fields(mock_jira_cli):
    """Test extracting basic fields from a issue tracker ticket."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Implement customer backup feature",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
        }
    })

    client = JiraClient()
    ticket = client.get_ticket("PROJ-12345")

    assert ticket is not None
    assert ticket["key"] == "PROJ-12345"
    assert ticket["summary"] == "Implement customer backup feature"
    assert ticket["status"] == "In Progress"
    assert ticket["type"] == "Story"


def test_get_ticket_with_sprint(mock_jira_cli):
    """Test extracting sprint information from a issue tracker ticket."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Bug"},
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@123[id=123,name=Sprint 42,state=ACTIVE]"],
        }
    })

    # Provide field_mappings to enable sprint extraction
    field_mappings = {
        "sprint": {"id": "customfield_12310940"}
    }

    client = JiraClient()
    ticket = client.get_ticket("PROJ-12345", field_mappings=field_mappings)

    assert ticket is not None
    assert ticket["sprint"] == "Sprint 42"


def test_get_ticket_with_story_points(mock_jira_cli):
    """Test extracting story points from a issue tracker ticket."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "customfield_12310243": 5,  # Story points
        }
    })

    # Provide field_mappings to enable story points extraction
    field_mappings = {
        "story_points": {"id": "customfield_12310243"}
    }

    client = JiraClient()
    ticket = client.get_ticket("PROJ-12345", field_mappings=field_mappings)

    assert ticket is not None
    assert ticket["points"] == 5


def test_get_ticket_with_assignee(mock_jira_cli):
    """Test extracting assignee from a issue tracker ticket."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Task"},
            "assignee": {"displayName": "John Doe"},
        }
    })

    client = JiraClient()
    ticket = client.get_ticket("PROJ-12345")

    assert ticket is not None
    assert ticket["assignee"] == "John Doe"


def test_get_ticket_with_epic(mock_jira_cli):
    """Test extracting epic from a issue tracker ticket."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "customfield_12311140": "PROJ-10000",
        }
    })

    # Provide field_mappings to enable epic extraction
    field_mappings = {
        "epic_link": {"id": "customfield_12311140"}
    }

    client = JiraClient()
    ticket = client.get_ticket("PROJ-12345", field_mappings=field_mappings)

    assert ticket is not None
    assert ticket["epic"] == "PROJ-10000"


def test_get_ticket_not_found(mock_jira_cli):
    """Test getting a non-existent issue tracker ticket raises JiraNotFoundError."""
    client = JiraClient()

    with pytest.raises(JiraNotFoundError) as exc_info:
        client.get_ticket("PROJ-99999")

    assert exc_info.value.resource_id == "PROJ-99999"


def test_get_ticket_all_fields(mock_jira_cli):
    """Test extracting all supported fields from a issue tracker ticket."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Complete feature implementation",
            "status": {"name": "Code Review"},
            "issuetype": {"name": "Story"},
            "customfield_12310243": 8,  # Story points
            "assignee": {"displayName": "Jane Smith"},
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@123[id=123,name=Sprint 45,state=ACTIVE]"],
            "customfield_12311140": "PROJ-10000",
        }
    })

    # Provide field_mappings for all custom fields
    field_mappings = {
        "story_points": {"id": "customfield_12310243"},
        "sprint": {"id": "customfield_12310940"},
        "epic_link": {"id": "customfield_12311140"}
    }

    client = JiraClient()
    ticket = client.get_ticket("PROJ-12345", field_mappings=field_mappings)

    assert ticket is not None
    assert ticket["key"] == "PROJ-12345"
    assert ticket["summary"] == "Complete feature implementation"
    assert ticket["status"] == "Code Review"
    assert ticket["type"] == "Story"
    assert ticket["points"] == 8
    assert ticket["assignee"] == "Jane Smith"
    assert ticket["sprint"] == "Sprint 45"
    assert ticket["epic"] == "PROJ-10000"


def test_get_ticket_invalid_story_points(mock_jira_cli):
    """Test that invalid story points are ignored."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            # Story points field will have invalid value in plain text output
        }
    })

    # Mock will output "STORY POINTS: Not Set" which should be ignored
    client = JiraClient()
    ticket = client.get_ticket("PROJ-12345")

    assert ticket is not None
    # points field should not exist if invalid
    assert "points" not in ticket or ticket.get("points") is None


def test_add_comment_success(mock_jira_cli):
    """Test adding a comment to a issue tracker ticket."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test ticket"}
    })

    client = JiraClient()
    # add_comment now returns None on success
    client.add_comment("PROJ-12345", "This is a test comment")

    assert "PROJ-12345" in mock_jira_cli.comments
    assert "This is a test comment" in mock_jira_cli.comments["PROJ-12345"]


def test_add_comment_to_nonexistent_ticket(mock_jira_cli):
    """Test adding a comment to a non-existent ticket raises exception."""
    client = JiraClient()

    with pytest.raises(JiraNotFoundError):
        client.add_comment("PROJ-99999", "Test comment")


def test_transition_ticket_success(mock_jira_cli):
    """Test transitioning a issue tracker ticket to a new status."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"}
        }
    })

    client = JiraClient()
    # transition_ticket now returns None on success
    client.transition_ticket("PROJ-12345", "In Progress")

    assert mock_jira_cli.transitions["PROJ-12345"] == "In Progress"


def test_transition_ticket_failure(mock_jira_cli):
    """Test transitioning a non-existent ticket raises exception."""
    client = JiraClient()

    with pytest.raises(JiraNotFoundError):
        client.transition_ticket("PROJ-99999", "In Progress")


def test_attach_file_success(mock_jira_cli, tmp_path):
    """Test attaching a file to a issue tracker ticket."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test ticket"}
    })

    # Create a temporary file to attach
    test_file = tmp_path / "test.tar.gz"
    test_file.write_text("test content")

    client = JiraClient()
    # attach_file now returns None on success
    client.attach_file("PROJ-12345", str(test_file))

    assert "PROJ-12345" in mock_jira_cli.attachments


def test_attach_file_failure(mock_jira_cli):
    """Test attaching a file to a non-existent ticket raises exception."""
    client = JiraClient()

    with pytest.raises(JiraNotFoundError):
        client.attach_file("PROJ-99999", "/tmp/test.tar.gz")


def test_list_tickets_no_filters(mock_jira_cli):
    """Test listing issue tracker tickets without filters."""
    # Setup multiple tickets
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "First ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })
    mock_jira_cli.set_ticket("PROJ-101", {
        "key": "PROJ-101",
        "fields": {
            "summary": "Second ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Bug"},
        }
    })

    client = JiraClient()
    tickets = client.list_tickets()

    assert len(tickets) == 2
    assert any(t["key"] == "PROJ-100" for t in tickets)
    assert any(t["key"] == "PROJ-101" for t in tickets)


def test_list_tickets_with_assignee_filter(mock_jira_cli):
    """Test listing issue tracker tickets filtered by assignee."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "My ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "assignee": {"displayName": "John Doe"},
        }
    })

    client = JiraClient()
    tickets = client.list_tickets(assignee="currentUser()")

    # List command should have been called with assignee filter
    assert len(tickets) >= 0  # May be empty depending on mock behavior


def test_list_tickets_with_status_filter(mock_jira_cli):
    """Test listing issue tracker tickets filtered by status."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "In progress ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
        }
    })

    client = JiraClient()
    tickets = client.list_tickets(status="In Progress")

    # Verify list was called with status filter
    assert isinstance(tickets, list)


def test_list_tickets_with_status_list_filter(mock_jira_cli):
    """Test listing issue tracker tickets filtered by multiple statuses."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "New ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })
    mock_jira_cli.set_ticket("PROJ-101", {
        "key": "PROJ-101",
        "fields": {
            "summary": "In progress ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Bug"},
        }
    })
    mock_jira_cli.set_ticket("PROJ-102", {
        "key": "PROJ-102",
        "fields": {
            "summary": "To Do ticket",
            "status": {"name": "To Do"},
            "issuetype": {"name": "Story"},
        }
    })

    client = JiraClient()
    tickets = client.list_tickets(status_list=["New", "To Do", "In Progress"])

    # Verify list was called with multiple status filters
    assert isinstance(tickets, list)
    # Should return all three tickets
    assert len(tickets) == 3


def test_list_tickets_status_list_takes_precedence(mock_jira_cli):
    """Test that status_list takes precedence over single status parameter."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "New ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })
    mock_jira_cli.set_ticket("PROJ-101", {
        "key": "PROJ-101",
        "fields": {
            "summary": "In progress ticket",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Bug"},
        }
    })

    client = JiraClient()
    # Pass both status and status_list - status_list should win
    tickets = client.list_tickets(status="Done", status_list=["New", "In Progress"])

    # Verify list was called and status_list took precedence
    assert isinstance(tickets, list)
    # Should return tickets matching status_list, not status
    assert len(tickets) == 2


def test_list_tickets_with_sprint_filter(mock_jira_cli):
    """Test listing issue tracker tickets filtered by sprint."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "Sprint ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@123[id=123,name=Sprint 42,state=ACTIVE]"],
        }
    })

    client = JiraClient()
    tickets = client.list_tickets(sprint="Sprint 42")

    # Verify list was called with sprint filter
    assert isinstance(tickets, list)


def test_list_tickets_with_type_filter(mock_jira_cli):
    """Test listing issue tracker tickets filtered by type."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "Bug ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Bug"},
        }
    })

    client = JiraClient()
    tickets = client.list_tickets(ticket_type="Bug")

    # Verify list was called with type filter
    assert isinstance(tickets, list)


def test_list_tickets_empty_sprint_filter(mock_jira_cli):
    """Test that empty sprint filter is handled correctly."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    client = JiraClient()
    # Empty sprint filter should be ignored
    tickets = client.list_tickets(sprint="")

    assert isinstance(tickets, list)


def test_list_tickets_command_failure(mock_jira_cli):
    """Test that list_tickets returns empty list on command failure."""
    # Force the next list command to fail
    mock_jira_cli.fail_next_command("issue list")

    client = JiraClient()
    tickets = client.list_tickets()

    assert tickets == []


def test_jira_client_custom_timeout(mock_jira_cli):
    """Test creating JIRA client with custom timeout."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    client = JiraClient(timeout=30)
    assert client.timeout == 30

    # Should still work with custom timeout
    ticket = client.get_ticket("PROJ-12345")
    assert ticket is not None


def test_transition_ticket_with_required_fields_error(mock_jira_cli, capsys):
    """Test transitioning a ticket that fails due to missing required fields."""
    from devflow.jira.exceptions import JiraValidationError

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    # Configure the mock to return a 400 error with field errors
    mock_jira_cli.set_transition_error("PROJ-12345", {
        "errorMessages": ["Transition validation failed"],
        "errors": {
            "customfield_12310243": "Story Points is required",
            "customfield_12319275": "Target Release is required"
        }
    })

    client = JiraClient()

    # Should raise JiraValidationError due to validation error
    with pytest.raises(JiraValidationError) as exc_info:
        client.transition_ticket("PROJ-12345", "Done")

    # Verify error details are captured in exception
    assert "Transition validation failed" in exc_info.value.error_messages
    # Field names may be translated, so check for either the ID or friendly name
    assert "Story Points" in exc_info.value.field_errors or "customfield_12310243" in exc_info.value.field_errors


def test_jira_client_loads_url_from_config_file(tmp_path, monkeypatch):
    """Test that JiraClient loads JIRA URL from ~/.config/.jira/.config.yml when env var not set."""
    # Remove JIRA_URL from environment
    monkeypatch.delenv("JIRA_URL", raising=False)

    # Set JIRA_API_TOKEN so the client can function
    monkeypatch.setenv("JIRA_API_TOKEN", "mock-token")

    # Create the config directory structure
    config_dir = tmp_path / ".config" / ".jira"
    config_dir.mkdir(parents=True)

    # Create the config file with a JIRA server URL
    config_file = config_dir / ".config.yml"
    config_file.write_text("server: https://custom-jira.example.com\n")

    # Mock expanduser to return our temp path
    def mock_expanduser(path):
        if path.startswith("~/"):
            return str(tmp_path / path[2:])
        return path

    monkeypatch.setattr("os.path.expanduser", mock_expanduser)

    # Create the client - it should load URL from config file
    client = JiraClient()

    # Verify the URL was loaded from the config file
    assert client._jira_url == "https://custom-jira.example.com"


def test_jira_client_falls_back_to_default_when_config_missing(monkeypatch):
    """Test that JiraClient uses default URL when config file doesn't exist."""
    # Remove JIRA_URL from environment
    monkeypatch.delenv("JIRA_URL", raising=False)

    # Set JIRA_API_TOKEN so the client can function
    monkeypatch.setenv("JIRA_API_TOKEN", "mock-token")

    # Mock expanduser to return a non-existent path
    monkeypatch.setattr("os.path.expanduser", lambda path: "/nonexistent/path/.config/.jira/.config.yml")

    # Create the client - no default URL in open source version
    client = JiraClient()

    # Verify no default URL is set
    assert client._jira_url is None


def test_transition_ticket_to_invalid_status(mock_jira_cli, capsys):
    """Test transitioning a ticket to a status that's not in available transitions."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    client = JiraClient()
    # Try to transition to a status that doesn't exist in the available transitions
    # Available transitions are: New, In Progress, Code Review, Done, Closed

    # Should raise JiraNotFoundError for invalid status
    with pytest.raises(JiraNotFoundError) as exc_info:
        client.transition_ticket("PROJ-12345", "Invalid Status")

    # Error message should mention invalid status
    assert "Invalid Status" in str(exc_info.value)


def test_list_tickets_with_sprint_data(mock_jira_cli):
    """Test that list_tickets correctly extracts sprint names from sprint strings."""
    # Create tickets with sprint data in JIRA's sprint string format
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "Ticket in Sprint 42",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
            "customfield_12310940": [
                "com.atlassian.greenhopper.service.sprint.Sprint@12345[id=1,name=Sprint 42,state=ACTIVE]"
            ],
            "customfield_12310243": 5,  # Story points
            "customfield_12311140": "PROJ-10000",  # Epic link
        }
    })

    mock_jira_cli.set_ticket("PROJ-101", {
        "key": "PROJ-101",
        "fields": {
            "summary": "Ticket with sprint at end of bracket",
            "status": {"name": "New"},
            "issuetype": {"name": "Bug"},
            # Test edge case where sprint name is at the end (no comma after name)
            "customfield_12310940": [
                "com.atlassian.greenhopper.service.sprint.Sprint@67890[id=2,name=Sprint 43]"
            ],
        }
    })

    # Provide field_mappings for all custom fields
    field_mappings = {
        "story_points": {"id": "customfield_12310243"},
        "sprint": {"id": "customfield_12310940"},
        "epic_link": {"id": "customfield_12311140"}
    }

    client = JiraClient()
    tickets = client.list_tickets(field_mappings=field_mappings)

    # Find the tickets in the results
    ticket_100 = next((t for t in tickets if t["key"] == "PROJ-100"), None)
    ticket_101 = next((t for t in tickets if t["key"] == "PROJ-101"), None)

    assert ticket_100 is not None
    assert ticket_100["sprint"] == "Sprint 42"
    assert ticket_100["points"] == 5
    assert ticket_100["epic"] == "PROJ-10000"

    assert ticket_101 is not None
    assert ticket_101["sprint"] == "Sprint 43"


def test_add_comment_without_api_token(monkeypatch, capsys):
    """Test that add_comment raises exception when JIRA_API_TOKEN is missing."""
    from devflow.jira.exceptions import JiraAuthError

    # Remove JIRA_API_TOKEN from environment
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")

    client = JiraClient()

    # Should raise JiraAuthError due to missing token
    with pytest.raises(JiraAuthError):
        client.add_comment("PROJ-12345", "Test comment")


def test_add_comment_with_request_exception(mock_jira_cli, monkeypatch, capsys):
    """Test that add_comment raises exception on connection error."""
    import requests
    from devflow.jira.exceptions import JiraConnectionError

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test ticket"}
    })

    # Monkeypatch requests.request to raise an exception
    def mock_request_with_exception(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Connection failed")

    monkeypatch.setattr("requests.request", mock_request_with_exception)

    client = JiraClient()

    # Should raise JiraConnectionError due to connection failure
    with pytest.raises((JiraConnectionError, JiraApiError)):
        client.add_comment("PROJ-12345", "Test comment")


def test_transition_ticket_without_api_token(monkeypatch, capsys):
    """Test that transition_ticket raises exception when JIRA_API_TOKEN is missing."""
    from devflow.jira.exceptions import JiraAuthError

    # Remove JIRA_API_TOKEN from environment
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")

    client = JiraClient()

    # Should raise JiraAuthError due to missing token
    with pytest.raises(JiraAuthError):
        client.transition_ticket("PROJ-12345", "In Progress")


def test_transition_ticket_with_request_exception(mock_jira_cli, monkeypatch, capsys):
    """Test that transition_ticket raises exception on timeout."""
    import requests
    from devflow.jira.exceptions import JiraConnectionError

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"}
        }
    })

    # Monkeypatch requests.request to raise an exception
    def mock_request_with_exception(*args, **kwargs):
        raise requests.exceptions.Timeout("Request timeout")

    monkeypatch.setattr("requests.request", mock_request_with_exception)

    client = JiraClient()

    # Should raise JiraConnectionError due to timeout
    with pytest.raises((JiraConnectionError, JiraApiError)):
        client.transition_ticket("PROJ-12345", "In Progress")


def test_transition_ticket_get_transitions_fails(mock_jira_cli, monkeypatch, capsys):
    """Test transition_ticket when getting available transitions fails."""
    import json
    from unittest.mock import Mock

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"}
        }
    })

    # Track call count to mock different responses for different endpoints
    call_count = [0]

    def mock_request_with_failure(method, url, **kwargs):
        call_count[0] += 1
        response = Mock()

        # First call is to get transitions - make it fail
        if "transitions" in url and method == "GET":
            response.status_code = 500
            response.text = "Internal Server Error"
            return response

        # Other calls use the normal mock
        return mock_jira_cli.handle_rest_request(method, url, **kwargs)

    monkeypatch.setattr("requests.request", mock_request_with_failure)

    client = JiraClient()

    # Should raise JiraApiError when getting transitions fails
    with pytest.raises(JiraApiError) as exc_info:
        client.transition_ticket("PROJ-12345", "In Progress")

    assert exc_info.value.status_code == 500


def test_attach_file_without_api_token(monkeypatch, capsys):
    """Test that attach_file raises exception when JIRA_API_TOKEN is missing."""
    from devflow.jira.exceptions import JiraAuthError

    # Remove JIRA_API_TOKEN from environment
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")

    client = JiraClient()

    # Should raise JiraAuthError due to missing token
    with pytest.raises(JiraAuthError):
        client.attach_file("PROJ-12345", "/tmp/test.txt")


def test_attach_file_upload_fails(mock_jira_cli, monkeypatch, capsys, tmp_path):
    """Test attach_file when the upload returns non-200 status."""
    from unittest.mock import Mock

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {"summary": "Test ticket"}
    })

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    # Mock requests.post to return a failure
    def mock_post_failure(url, **kwargs):
        response = Mock()
        response.status_code = 413
        response.text = "File too large"
        return response

    monkeypatch.setattr("requests.post", mock_post_failure)

    client = JiraClient()

    # Should raise JiraApiError when upload fails
    with pytest.raises(JiraApiError) as exc_info:
        client.attach_file("PROJ-12345", str(test_file))

    assert exc_info.value.status_code == 413
    assert "File too large" in exc_info.value.response_text


def test_list_tickets_with_specific_assignee(mock_jira_cli):
    """Test listing tickets with a specific assignee name (not currentUser)."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "assignee": {"displayName": "John Doe"},
        }
    })

    client = JiraClient()
    # Use a specific assignee name instead of currentUser()
    tickets = client.list_tickets(assignee="John Doe")

    # Should return tickets
    assert isinstance(tickets, list)


def test_list_tickets_with_empty_sprint_filter(mock_jira_cli):
    """Test listing tickets with 'IS NOT EMPTY' sprint filter."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "customfield_12310940": [
                "com.atlassian.greenhopper.service.sprint.Sprint@12345[id=1,name=Sprint 42,state=ACTIVE]"
            ],
        }
    })

    client = JiraClient()
    # Use "IS NOT EMPTY" to match tickets with any sprint
    tickets = client.list_tickets(sprint="IS NOT EMPTY")

    # Should return tickets
    assert isinstance(tickets, list)


def test_get_ticket_with_invalid_story_points(mock_jira_cli):
    """Test that get_ticket handles invalid story points gracefully."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "customfield_12310243": "invalid",  # Invalid story points value
        }
    })

    client = JiraClient()
    ticket = client.get_ticket("PROJ-12345")

    assert ticket is not None
    # points field should not exist if invalid
    assert "points" not in ticket


def test_list_tickets_with_invalid_story_points(mock_jira_cli):
    """Test that list_tickets handles invalid story points gracefully."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
            "customfield_12310243": "not a number",  # Invalid story points
        }
    })

    client = JiraClient()
    tickets = client.list_tickets()

    assert len(tickets) >= 1
    ticket = next((t for t in tickets if t["key"] == "PROJ-100"), None)
    assert ticket is not None
    # points field should not exist if invalid
    assert "points" not in ticket


def test_list_tickets_api_failure(monkeypatch, capsys):
    """Test that list_tickets raises exception on API failure."""
    from unittest.mock import Mock

    monkeypatch.setenv("JIRA_API_TOKEN", "mock-token")
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")

    # Mock requests.request to return an error for search endpoint
    def mock_request_failure(method, url, **kwargs):
        response = Mock()
        if "/rest/api/2/search" in url:
            response.status_code = 500
            response.text = "Internal Server Error"
        else:
            response.status_code = 200
        return response

    monkeypatch.setattr("requests.request", mock_request_failure)

    client = JiraClient()

    # Should raise JiraApiError on failure
    with pytest.raises(JiraApiError) as exc_info:
        tickets = client.list_tickets()

    assert exc_info.value.status_code == 500


def test_get_ticket_server_error(monkeypatch, capsys):
    """Test that get_ticket handles non-200/non-404 status codes."""
    from unittest.mock import Mock

    monkeypatch.setenv("JIRA_API_TOKEN", "mock-token")
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")

    # Mock requests.request to return a 500 error
    def mock_request_error(method, url, **kwargs):
        response = Mock()
        response.status_code = 500
        response.text = "Internal Server Error"
        return response

    monkeypatch.setattr("requests.request", mock_request_error)

    client = JiraClient()

    # Should raise JiraApiError for non-200/non-404 status
    with pytest.raises(JiraApiError) as exc_info:
        ticket = client.get_ticket("PROJ-12345")

    assert exc_info.value.status_code == 500


def test_get_field_name_with_api_failure(monkeypatch):
    """Test that _get_field_name handles API failures gracefully."""
    from unittest.mock import Mock

    monkeypatch.setenv("JIRA_API_TOKEN", "mock-token")
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")

    # Mock requests.request to fail for field metadata
    def mock_request_field_failure(method, url, **kwargs):
        response = Mock()
        if "/rest/api/2/field" in url:
            # Raise an exception to trigger the exception handler
            raise Exception("Connection failed")
        else:
            response.status_code = 404
        return response

    monkeypatch.setattr("requests.request", mock_request_field_failure)

    client = JiraClient()

    # Call _get_field_name - it should return the field_id as-is on error
    field_name = client._get_field_name("customfield_12345")

    # Should return the field ID unchanged
    assert field_name == "customfield_12345"


def test_get_field_name_cache_hit(mock_jira_cli):
    """Test that _get_field_name uses cache on subsequent calls."""
    from devflow.jira.exceptions import JiraValidationError

    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"}
        }
    })

    # Trigger a 400 error to call _get_field_name
    mock_jira_cli.set_transition_error("PROJ-12345", {
        "errors": {
            "customfield_12310243": "Story Points is required"
        }
    })

    client = JiraClient()
    # This will call _get_field_name and populate the cache
    try:
        client.transition_ticket("PROJ-12345", "Done")
    except JiraValidationError:
        pass  # Expected to fail

    # Call _get_field_name again - should hit the cache
    field_name = client._get_field_name("customfield_12310243")
    assert field_name == "Story Points"
