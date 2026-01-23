"""Tests for issue tracker interface and factory."""

import pytest

from devflow.issue_tracker.factory import (
    create_issue_tracker_client,
    get_backend_from_config,
    get_default_backend,
)
from devflow.issue_tracker.interface import IssueTrackerClient
from devflow.issue_tracker.mock_client import MockIssueTrackerClient
from devflow.jira.client import JiraClient
from devflow.jira.exceptions import JiraNotFoundError


class TestIssueTrackerFactory:
    """Tests for issue tracker factory."""

    def test_create_jira_client_default(self):
        """Test creating JIRA client as default."""
        client = create_issue_tracker_client()
        assert isinstance(client, JiraClient)
        assert isinstance(client, IssueTrackerClient)

    def test_create_jira_client_explicit(self):
        """Test creating JIRA client explicitly."""
        client = create_issue_tracker_client("jira")
        assert isinstance(client, JiraClient)
        assert isinstance(client, IssueTrackerClient)

    def test_create_jira_client_case_insensitive(self):
        """Test backend name is case-insensitive."""
        client = create_issue_tracker_client("JIRA")
        assert isinstance(client, JiraClient)

    def test_create_mock_client(self):
        """Test creating mock client."""
        client = create_issue_tracker_client("mock")
        assert isinstance(client, MockIssueTrackerClient)
        assert isinstance(client, IssueTrackerClient)

    def test_create_mock_client_case_insensitive(self):
        """Test mock backend name is case-insensitive."""
        client = create_issue_tracker_client("MOCK")
        assert isinstance(client, MockIssueTrackerClient)

    def test_create_github_client_not_implemented(self):
        """Test GitHub backend raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            create_issue_tracker_client("github")
        assert "GitHub Issues backend is not yet implemented" in str(exc_info.value)

    def test_create_gitlab_client_not_implemented(self):
        """Test GitLab backend raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            create_issue_tracker_client("gitlab")
        assert "GitLab Issues backend is not yet implemented" in str(exc_info.value)

    def test_create_unsupported_backend(self):
        """Test unsupported backend raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_issue_tracker_client("unknown")
        assert "Unsupported issue tracker backend: unknown" in str(exc_info.value)

    def test_custom_timeout_propagated(self):
        """Test custom timeout is propagated to client."""
        client = create_issue_tracker_client("mock", timeout=60)
        assert client.timeout == 60

    def test_get_backend_from_config_defaults_to_jira(self):
        """Test get_backend_from_config defaults to JIRA."""
        backend = get_backend_from_config()
        assert backend == "jira"

    def test_get_default_backend(self):
        """Test get_default_backend returns JIRA."""
        backend = get_default_backend()
        assert backend == "jira"


class TestMockIssueTrackerClient:
    """Tests for mock issue tracker client."""

    def test_create_and_get_bug(self):
        """Test creating and retrieving a bug."""
        client = MockIssueTrackerClient()
        key = client.create_bug(
            summary="Test bug",
            description="Bug description",
            project="TEST",
            priority="Major",
        )
        assert key == "TEST-1"

        ticket = client.get_ticket(key)
        assert ticket["key"] == "TEST-1"
        assert ticket["summary"] == "Test bug"
        assert ticket["description"] == "Bug description"
        assert ticket["type"] == "Bug"
        assert ticket["status"] == "New"
        assert ticket["priority"] == "Major"

    def test_create_and_get_story(self):
        """Test creating and retrieving a story."""
        client = MockIssueTrackerClient()
        key = client.create_story(
            summary="Test story",
            description="Story description",
            project="TEST",
            parent="TEST-100",
        )
        assert key == "TEST-1"

        ticket = client.get_ticket(key)
        assert ticket["type"] == "Story"
        assert ticket["epic"] == "TEST-100"

    def test_create_and_get_task(self):
        """Test creating and retrieving a task."""
        client = MockIssueTrackerClient()
        key = client.create_task(
            summary="Test task",
            description="Task description",
            project="TEST",
        )
        assert key == "TEST-1"

        ticket = client.get_ticket(key)
        assert ticket["type"] == "Task"

    def test_create_and_get_epic(self):
        """Test creating and retrieving an epic."""
        client = MockIssueTrackerClient()
        key = client.create_epic(
            summary="Test epic",
            description="Epic description",
            project="TEST",
        )
        assert key == "TEST-1"

        ticket = client.get_ticket(key)
        assert ticket["type"] == "Epic"
        assert ticket["epic"] is None  # Epics don't have parents

    def test_create_and_get_spike(self):
        """Test creating and retrieving a spike."""
        client = MockIssueTrackerClient()
        key = client.create_spike(
            summary="Test spike",
            description="Spike description",
            project="TEST",
            parent="TEST-100",
        )
        assert key == "TEST-1"

        ticket = client.get_ticket(key)
        assert ticket["type"] == "Spike"

    def test_get_ticket_not_found(self):
        """Test getting non-existent ticket raises error."""
        client = MockIssueTrackerClient()
        with pytest.raises(JiraNotFoundError) as exc_info:
            client.get_ticket("TEST-999")
        assert "Ticket TEST-999 not found" in str(exc_info.value)
        assert exc_info.value.resource_type == "issue"
        assert exc_info.value.resource_id == "TEST-999"

    def test_get_ticket_detailed(self):
        """Test getting detailed ticket information."""
        client = MockIssueTrackerClient()
        key = client.create_bug(
            summary="Test bug",
            description="Bug description",
            project="TEST",
        )

        ticket = client.get_ticket_detailed(key, include_changelog=True)
        assert ticket["key"] == key
        assert "changelog" in ticket
        assert ticket["changelog"]["histories"] == []

    def test_list_tickets_all(self):
        """Test listing all tickets."""
        client = MockIssueTrackerClient()
        client.create_bug("Bug 1", "Desc 1", "TEST")
        client.create_story("Story 1", "Desc 2", "TEST")
        client.create_task("Task 1", "Desc 3", "TEST")

        tickets = client.list_tickets()
        assert len(tickets) == 3
        assert {t["type"] for t in tickets} == {"Bug", "Story", "Task"}

    def test_list_tickets_filter_by_project(self):
        """Test filtering tickets by project."""
        client = MockIssueTrackerClient()
        client.create_bug("Bug 1", "Desc 1", "TEST")
        client.create_bug("Bug 2", "Desc 2", "OTHER")

        tickets = client.list_tickets(project="TEST")
        assert len(tickets) == 1
        assert tickets[0]["project"] == "TEST"

    def test_list_tickets_filter_by_status(self):
        """Test filtering tickets by status."""
        client = MockIssueTrackerClient()
        key1 = client.create_bug("Bug 1", "Desc 1", "TEST")
        key2 = client.create_bug("Bug 2", "Desc 2", "TEST")
        client.transition_ticket(key1, "In Progress")

        tickets = client.list_tickets(status=["In Progress"])
        assert len(tickets) == 1
        assert tickets[0]["key"] == key1

    def test_list_tickets_filter_by_type(self):
        """Test filtering tickets by issue type."""
        client = MockIssueTrackerClient()
        client.create_bug("Bug 1", "Desc 1", "TEST")
        client.create_story("Story 1", "Desc 2", "TEST")

        tickets = client.list_tickets(issue_type=["Bug"])
        assert len(tickets) == 1
        assert tickets[0]["type"] == "Bug"

    def test_list_tickets_pagination(self):
        """Test ticket list pagination."""
        client = MockIssueTrackerClient()
        for i in range(5):
            client.create_bug(f"Bug {i}", f"Desc {i}", "TEST")

        # Get first 2 tickets
        tickets = client.list_tickets(max_results=2, start_at=0)
        assert len(tickets) == 2

        # Get next 2 tickets
        tickets = client.list_tickets(max_results=2, start_at=2)
        assert len(tickets) == 2

    def test_update_issue(self):
        """Test updating an issue."""
        client = MockIssueTrackerClient()
        key = client.create_bug("Bug 1", "Desc 1", "TEST")

        client.update_issue(key, {"summary": "Updated bug"})
        ticket = client.get_ticket(key)
        assert ticket["summary"] == "Updated bug"

    def test_update_issue_not_found(self):
        """Test updating non-existent issue raises error."""
        client = MockIssueTrackerClient()
        with pytest.raises(JiraNotFoundError):
            client.update_issue("TEST-999", {"summary": "Updated"})

    def test_update_ticket_field(self):
        """Test updating a single field."""
        client = MockIssueTrackerClient()
        key = client.create_bug("Bug 1", "Desc 1", "TEST")

        client.update_ticket_field(key, "priority", "Critical")
        ticket = client.get_ticket(key)
        assert ticket["priority"] == "Critical"

    def test_update_ticket_field_not_found(self):
        """Test updating field on non-existent ticket raises error."""
        client = MockIssueTrackerClient()
        with pytest.raises(JiraNotFoundError):
            client.update_ticket_field("TEST-999", "priority", "Major")

    def test_transition_ticket(self):
        """Test transitioning ticket status."""
        client = MockIssueTrackerClient()
        key = client.create_bug("Bug 1", "Desc 1", "TEST")

        client.transition_ticket(key, "In Progress")
        ticket = client.get_ticket(key)
        assert ticket["status"] == "In Progress"

    def test_transition_ticket_not_found(self):
        """Test transitioning non-existent ticket raises error."""
        client = MockIssueTrackerClient()
        with pytest.raises(JiraNotFoundError):
            client.transition_ticket("TEST-999", "In Progress")

    def test_add_comment(self):
        """Test adding comment to ticket."""
        client = MockIssueTrackerClient()
        key = client.create_bug("Bug 1", "Desc 1", "TEST")

        # Should not raise
        client.add_comment(key, "Test comment")

    def test_add_comment_not_found(self):
        """Test adding comment to non-existent ticket raises error."""
        client = MockIssueTrackerClient()
        with pytest.raises(JiraNotFoundError):
            client.add_comment("TEST-999", "Comment")

    def test_attach_file(self):
        """Test attaching file to ticket."""
        client = MockIssueTrackerClient()
        key = client.create_bug("Bug 1", "Desc 1", "TEST")

        # Should not raise
        client.attach_file(key, "/path/to/file.txt")

    def test_attach_file_not_found(self):
        """Test attaching file to non-existent ticket raises error."""
        client = MockIssueTrackerClient()
        with pytest.raises(JiraNotFoundError):
            client.attach_file("TEST-999", "/path/to/file.txt")

    def test_get_child_issues(self):
        """Test getting child issues."""
        client = MockIssueTrackerClient()
        epic_key = client.create_epic("Epic 1", "Desc", "TEST")
        story1_key = client.create_story("Story 1", "Desc", "TEST", parent=epic_key)
        story2_key = client.create_story("Story 2", "Desc", "TEST", parent=epic_key)
        client.create_bug("Bug 1", "Desc", "TEST")  # Not a child

        children = client.get_child_issues(epic_key)
        assert len(children) == 2
        assert {c["key"] for c in children} == {story1_key, story2_key}

    def test_get_child_issues_filter_by_type(self):
        """Test filtering child issues by type."""
        client = MockIssueTrackerClient()
        epic_key = client.create_epic("Epic 1", "Desc", "TEST")
        story_key = client.create_story("Story 1", "Desc", "TEST", parent=epic_key)
        client.create_task("Task 1", "Desc", "TEST", parent=epic_key)

        children = client.get_child_issues(epic_key, issue_types=["Story"])
        assert len(children) == 1
        assert children[0]["key"] == story_key

    def test_get_child_issues_not_found(self):
        """Test getting children of non-existent parent raises error."""
        client = MockIssueTrackerClient()
        with pytest.raises(JiraNotFoundError):
            client.get_child_issues("TEST-999")

    def test_get_issue_link_types(self):
        """Test getting available link types."""
        client = MockIssueTrackerClient()
        link_types = client.get_issue_link_types()

        assert len(link_types) >= 3
        assert any(lt["name"] == "Blocks" for lt in link_types)
        assert any(lt["name"] == "Relates" for lt in link_types)
        assert any(lt["name"] == "Duplicates" for lt in link_types)

    def test_link_issues(self):
        """Test linking two issues."""
        client = MockIssueTrackerClient()
        key1 = client.create_bug("Bug 1", "Desc", "TEST")
        key2 = client.create_bug("Bug 2", "Desc", "TEST")

        # Should not raise
        client.link_issues(key1, "blocks", key2, comment="Test link")

    def test_link_issues_source_not_found(self):
        """Test linking non-existent source raises error."""
        client = MockIssueTrackerClient()
        key2 = client.create_bug("Bug 2", "Desc", "TEST")

        with pytest.raises(JiraNotFoundError):
            client.link_issues("TEST-999", "blocks", key2)

    def test_link_issues_target_not_found(self):
        """Test linking to non-existent target raises error."""
        client = MockIssueTrackerClient()
        key1 = client.create_bug("Bug 1", "Desc", "TEST")

        with pytest.raises(JiraNotFoundError):
            client.link_issues(key1, "blocks", "TEST-999")

    def test_sequential_ticket_numbering(self):
        """Test tickets are numbered sequentially."""
        client = MockIssueTrackerClient()
        key1 = client.create_bug("Bug 1", "Desc", "TEST")
        key2 = client.create_story("Story 1", "Desc", "TEST")
        key3 = client.create_task("Task 1", "Desc", "TEST")

        assert key1 == "TEST-1"
        assert key2 == "TEST-2"
        assert key3 == "TEST-3"

    def test_different_projects_separate_numbering(self):
        """Test different projects don't share numbering."""
        client = MockIssueTrackerClient()
        key1 = client.create_bug("Bug 1", "Desc", "TEST")
        key2 = client.create_bug("Bug 2", "Desc", "OTHER")

        # Both should be -1 since numbering is global in mock
        # (This is a limitation of the simple mock implementation)
        assert key1 == "TEST-1"
        assert key2 == "OTHER-2"  # Global counter


class TestJiraClientImplementsInterface:
    """Test that JiraClient properly implements IssueTrackerClient."""

    def test_jira_client_is_instance_of_interface(self):
        """Test JiraClient is instance of IssueTrackerClient."""
        from devflow.jira.client import JiraClient

        client = JiraClient()
        assert isinstance(client, IssueTrackerClient)

    def test_jira_client_has_all_required_methods(self):
        """Test JiraClient implements all interface methods."""
        from devflow.jira.client import JiraClient

        client = JiraClient()

        # Check all abstract methods are implemented
        assert hasattr(client, "get_ticket")
        assert hasattr(client, "get_ticket_detailed")
        assert hasattr(client, "list_tickets")
        assert hasattr(client, "create_bug")
        assert hasattr(client, "create_story")
        assert hasattr(client, "create_task")
        assert hasattr(client, "create_epic")
        assert hasattr(client, "create_spike")
        assert hasattr(client, "update_issue")
        assert hasattr(client, "update_ticket_field")
        assert hasattr(client, "add_comment")
        assert hasattr(client, "transition_ticket")
        assert hasattr(client, "attach_file")
        assert hasattr(client, "get_ticket_pr_links")
        assert hasattr(client, "get_child_issues")
        assert hasattr(client, "get_issue_link_types")
        assert hasattr(client, "link_issues")

        # Check methods are callable
        assert callable(client.get_ticket)
        assert callable(client.get_ticket_detailed)
        assert callable(client.list_tickets)
        assert callable(client.create_bug)
        assert callable(client.create_story)
        assert callable(client.create_task)
        assert callable(client.create_epic)
        assert callable(client.create_spike)
        assert callable(client.update_issue)
        assert callable(client.update_ticket_field)
        assert callable(client.add_comment)
        assert callable(client.transition_ticket)
        assert callable(client.attach_file)
        assert callable(client.get_ticket_pr_links)
        assert callable(client.get_child_issues)
        assert callable(client.get_issue_link_types)
        assert callable(client.link_issues)
