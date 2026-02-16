"""Extended tests for mocks/jira_mock.py to improve coverage."""

import pytest
from devflow.mocks.jira_mock import MockJiraClient


def test_get_ticket_detailed_with_comments():
    """Test get_ticket_detailed includes comments when requested."""
    mock = MockJiraClient()

    ticket = mock.create_ticket(
        issue_type="Bug",
        summary="Test ticket",
        description="Test description",
        project="TEST"
    )
    key = ticket["key"]

    # Add comments
    mock.add_comment(key, "First comment")
    mock.add_comment(key, "Second comment")

    # Get detailed with comments
    detailed = mock.get_ticket_detailed(key, include_comments=True)

    assert "comments" in detailed
    assert len(detailed["comments"]) >= 2


def test_get_ticket_detailed_with_changelog():
    """Test get_ticket_detailed includes changelog when requested."""
    mock = MockJiraClient()

    ticket = mock.create_ticket(
        issue_type="Story",
        summary="Test story",
        project="TEST"
    )
    key = ticket["key"]

    # Get detailed with changelog
    detailed = mock.get_ticket_detailed(key, include_changelog=True)

    assert "changelog" in detailed


def test_add_attachment_success():
    """Test adding attachment to ticket."""
    mock = MockJiraClient()

    ticket = mock.create_ticket(
        issue_type="Bug",
        summary="Test",
        project="TEST"
    )
    key = ticket["key"]

    # Add attachment
    result = mock.add_attachment(key, "/path/to/file.txt")

    assert result is True


def test_add_attachment_ticket_not_found():
    """Test adding attachment to non-existent ticket."""
    mock = MockJiraClient()

    result = mock.add_attachment("NONEXISTENT-123", "/path/to/file.txt")

    assert result is False


def test_get_available_transitions_new_ticket():
    """Test getting available transitions for new ticket."""
    mock = MockJiraClient()

    ticket = mock.create_ticket(
        issue_type="Bug",
        summary="Test",
        project="TEST"
    )
    key = ticket["key"]

    transitions = mock.get_available_transitions(key)

    assert len(transitions) > 0


def test_get_available_transitions_not_found():
    """Test getting transitions for non-existent ticket."""
    mock = MockJiraClient()

    transitions = mock.get_available_transitions("NONEXISTENT-123")

    assert transitions == []


def test_search_issues_returns_tickets():
    """Test search_issues returns matching tickets."""
    mock = MockJiraClient()

    # Create test tickets
    mock.create_ticket(issue_type="Bug", summary="Bug 1", project="TEST")
    mock.create_ticket(issue_type="Story", summary="Story 1", project="TEST")

    # Search for all tickets
    result = mock.search_issues("project = TEST")

    assert "issues" in result
    assert len(result["issues"]) >= 2
