"""Tests for MockJiraClient."""

import pytest

from devflow.mocks.jira_mock import MockJiraClient
from devflow.mocks.persistence import MockDataStore


@pytest.fixture
def mock_jira(temp_daf_home):
    """Provide a clean MockJiraClient instance."""
    store = MockDataStore()
    store.clear_all()
    return MockJiraClient()


def test_create_ticket(mock_jira):
    """Test creating a issue tracker ticket."""
    ticket = mock_jira.create_ticket(
        issue_type="Story",
        summary="Test story",
        description="Test description",
        project="PROJ"
    )

    assert ticket is not None
    assert ticket["key"] == "PROJ-1"
    assert ticket["fields"]["issuetype"]["name"] == "Story"
    assert ticket["fields"]["summary"] == "Test story"
    assert ticket["fields"]["description"] == "Test description"
    assert ticket["fields"]["status"]["name"] == "New"


def test_get_ticket(mock_jira):
    """Test getting a issue tracker ticket."""
    # Create a ticket first
    mock_jira.create_ticket(
        issue_type="Bug",
        summary="Test bug",
        project="PROJ"
    )

    # Get the ticket
    ticket = mock_jira.get_ticket("PROJ-1")

    assert ticket is not None
    assert ticket["key"] == "PROJ-1"
    assert ticket["fields"]["summary"] == "Test bug"


def test_get_ticket_not_found(mock_jira):
    """Test getting a non-existent ticket."""
    ticket = mock_jira.get_ticket("PROJ-99999")
    assert ticket is None


def test_update_ticket(mock_jira):
    """Test updating a issue tracker ticket."""
    # Create a ticket
    mock_jira.create_ticket(
        issue_type="Task",
        summary="Test task",
        project="PROJ"
    )

    # Update the ticket
    success = mock_jira.update_ticket("PROJ-1", summary="Updated task")
    assert success is True

    # Verify update
    ticket = mock_jira.get_ticket("PROJ-1")
    assert ticket["fields"]["summary"] == "Updated task"


def test_update_ticket_not_found(mock_jira):
    """Test updating a non-existent ticket."""
    success = mock_jira.update_ticket("PROJ-99999", summary="Should fail")
    assert success is False


def test_add_comment(mock_jira):
    """Test adding a comment to a ticket."""
    # Create a ticket
    mock_jira.create_ticket(
        issue_type="Story",
        summary="Test story",
        project="PROJ"
    )

    # Add comments
    success1 = mock_jira.add_comment("PROJ-1", "First comment")
    success2 = mock_jira.add_comment("PROJ-1", "Second comment")

    assert success1 is True
    assert success2 is True

    # Verify comments were stored
    store = MockDataStore()
    comments = store.get_jira_comments("PROJ-1")
    assert len(comments) == 2
    assert comments[0] == "First comment"
    assert comments[1] == "Second comment"


def test_add_comment_ticket_not_found(mock_jira):
    """Test adding a comment to a non-existent ticket."""
    success = mock_jira.add_comment("PROJ-99999", "Should fail")
    assert success is False


def test_add_attachment(mock_jira):
    """Test adding an attachment to a ticket."""
    # Create a ticket
    mock_jira.create_ticket(
        issue_type="Bug",
        summary="Test bug",
        project="PROJ"
    )

    # Add attachment
    success = mock_jira.add_attachment("PROJ-1", "/tmp/test-file.tar.gz")
    assert success is True

    # Verify attachment was stored
    store = MockDataStore()
    attachments = store.get_jira_attachments("PROJ-1")
    assert len(attachments) == 1
    assert attachments[0] == "test-file.tar.gz"


def test_add_attachment_ticket_not_found(mock_jira):
    """Test adding an attachment to a non-existent ticket."""
    success = mock_jira.add_attachment("PROJ-99999", "/tmp/test.txt")
    assert success is False


def test_transition_ticket(mock_jira):
    """Test transitioning a ticket to a new status."""
    # Create a ticket
    mock_jira.create_ticket(
        issue_type="Story",
        summary="Test story",
        project="PROJ"
    )

    # Transition to In Progress
    success = mock_jira.transition_ticket("PROJ-1", "In Progress")
    assert success is True

    # Verify status changed
    ticket = mock_jira.get_ticket("PROJ-1")
    assert ticket["fields"]["status"]["name"] == "In Progress"


def test_transition_ticket_not_found(mock_jira):
    """Test transitioning a non-existent ticket."""
    success = mock_jira.transition_ticket("PROJ-99999", "In Progress")
    assert success is False


def test_get_available_transitions(mock_jira):
    """Test getting available transitions."""
    # Create a ticket
    mock_jira.create_ticket(
        issue_type="Story",
        summary="Test story",
        project="PROJ"
    )

    # Get transitions for New status
    transitions = mock_jira.get_available_transitions("PROJ-1")
    assert len(transitions) > 0
    assert any(t["name"] == "In Progress" for t in transitions)

    # Transition to In Progress
    mock_jira.transition_ticket("PROJ-1", "In Progress")

    # Get transitions for In Progress status
    transitions = mock_jira.get_available_transitions("PROJ-1")
    assert any(t["name"] == "Review" for t in transitions)
    assert any(t["name"] == "Done" for t in transitions)


def test_get_available_transitions_ticket_not_found(mock_jira):
    """Test getting transitions for non-existent ticket."""
    transitions = mock_jira.get_available_transitions("PROJ-99999")
    assert transitions == []


def test_list_tickets(mock_jira):
    """Test listing all tickets."""
    # Create multiple tickets
    mock_jira.create_ticket(issue_type="Story", summary="Story 1", project="PROJ")
    mock_jira.create_ticket(issue_type="Bug", summary="Bug 1", project="PROJ")
    mock_jira.create_ticket(issue_type="Task", summary="Task 1", project="PROJ")

    # List tickets
    tickets = mock_jira.list_tickets()
    assert len(tickets) == 3


def test_list_tickets_with_max_results(mock_jira):
    """Test listing tickets with max_results limit."""
    # Create multiple tickets
    for i in range(10):
        mock_jira.create_ticket(issue_type="Story", summary=f"Story {i}", project="PROJ")

    # List with limit
    tickets = mock_jira.list_tickets(max_results=5)
    assert len(tickets) == 5


def test_list_tickets_with_jql_filter(mock_jira):
    """Test listing tickets with JQL filter."""
    # Create tickets with different statuses
    mock_jira.create_ticket(issue_type="Story", summary="Story 1", project="PROJ")
    mock_jira.create_ticket(issue_type="Story", summary="Story 2", project="PROJ")

    # Transition one to In Progress
    mock_jira.transition_ticket("PROJ-1", "In Progress")

    # Filter by status
    tickets = mock_jira.list_tickets(jql="status = 'In Progress'")
    assert len(tickets) == 1
    assert tickets[0]["key"] == "PROJ-1"


def test_get_field_metadata(mock_jira):
    """Test getting field metadata."""
    metadata = mock_jira.get_field_metadata()

    assert len(metadata) > 0
    assert any(f["name"] == "Story Points" for f in metadata)
    assert any(f["name"] == "Sprint" for f in metadata)
    assert any(f["name"] == "Epic Link" for f in metadata)


def test_search_issues(mock_jira):
    """Test searching for issues."""
    # Create multiple tickets
    mock_jira.create_ticket(issue_type="Story", summary="Story 1", project="PROJ")
    mock_jira.create_ticket(issue_type="Bug", summary="Bug 1", project="PROJ")

    # Transition one to In Progress
    mock_jira.transition_ticket("PROJ-1", "In Progress")

    # Search
    results = mock_jira.search_issues(jql="status = 'In Progress'", max_results=10)

    assert "issues" in results
    assert "total" in results
    assert results["total"] == 1
    assert results["issues"][0]["key"] == "PROJ-1"


def test_get_ticket_detailed(mock_jira):
    """Test getting detailed ticket with changelog."""
    # Create a ticket
    mock_jira.create_ticket(
        issue_type="Story",
        summary="Test story",
        project="PROJ"
    )

    # Get detailed ticket
    ticket = mock_jira.get_ticket_detailed("PROJ-1")

    assert ticket is not None
    assert ticket["key"] == "PROJ-1"
    assert "changelog" in ticket


def test_create_ticket_with_custom_fields(mock_jira):
    """Test creating a ticket with custom fields."""
    ticket = mock_jira.create_ticket(
        issue_type="Story",
        summary="Test story",
        project="PROJ",
        story_points=5,
        sprint="Sprint 2025-50"
    )

    assert ticket["fields"]["story_points"] == 5
    assert ticket["fields"]["sprint"] == "Sprint 2025-50"


def test_multiple_projects(mock_jira):
    """Test creating tickets in multiple projects."""
    # Create tickets in different projects
    ticket1 = mock_jira.create_ticket(issue_type="Story", summary="PROJ Story", project="PROJ")
    ticket2 = mock_jira.create_ticket(issue_type="Bug", summary="TESTPROJ Bug", project="TESTPROJ")

    assert ticket1["key"] == "PROJ-1"
    assert ticket2["key"] == "TESTPROJ-1"

    # Create another PROJ ticket
    ticket3 = mock_jira.create_ticket(issue_type="Task", summary="PROJ Task", project="PROJ")
    assert ticket3["key"] == "PROJ-2"
