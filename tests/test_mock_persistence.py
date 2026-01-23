"""Tests for mock data persistence layer."""

import json
import threading
from pathlib import Path

import pytest

from devflow.mocks.persistence import MockDataStore


def test_mock_data_store_singleton(temp_daf_home):
    """Test that MockDataStore is a singleton."""
    store1 = MockDataStore()
    store2 = MockDataStore()

    assert store1 is store2


def test_jira_ticket_operations(temp_daf_home):
    """Test issue tracker ticket get/set operations."""
    store = MockDataStore()
    store.clear_all()

    # Initially no ticket
    ticket = store.get_jira_ticket("PROJ-12345")
    assert ticket is None

    # Set ticket
    ticket_data = {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
        }
    }
    store.set_jira_ticket("PROJ-12345", ticket_data)

    # Get ticket
    retrieved = store.get_jira_ticket("PROJ-12345")
    assert retrieved is not None
    assert retrieved["key"] == "PROJ-12345"
    assert retrieved["fields"]["summary"] == "Test ticket"


def test_jira_comments(temp_daf_home):
    """Test JIRA comment operations."""
    store = MockDataStore()
    store.clear_all()

    # Initially no comments
    comments = store.get_jira_comments("PROJ-12345")
    assert comments == []

    # Add comments
    store.add_jira_comment("PROJ-12345", "First comment")
    store.add_jira_comment("PROJ-12345", "Second comment")

    # Get comments
    comments = store.get_jira_comments("PROJ-12345")
    assert len(comments) == 2
    assert comments[0] == "First comment"
    assert comments[1] == "Second comment"


def test_jira_attachments(temp_daf_home):
    """Test JIRA attachment operations."""
    store = MockDataStore()
    store.clear_all()

    # Initially no attachments
    attachments = store.get_jira_attachments("PROJ-12345")
    assert attachments == []

    # Add attachments
    store.add_jira_attachment("PROJ-12345", "file1.txt")
    store.add_jira_attachment("PROJ-12345", "file2.pdf")

    # Get attachments
    attachments = store.get_jira_attachments("PROJ-12345")
    assert len(attachments) == 2
    assert "file1.txt" in attachments
    assert "file2.pdf" in attachments


def test_jira_transitions(temp_daf_home):
    """Test JIRA transition operations."""
    store = MockDataStore()
    store.clear_all()

    # Set up a ticket
    ticket_data = {
        "key": "PROJ-12345",
        "fields": {
            "status": {"name": "New"}
        }
    }
    store.set_jira_ticket("PROJ-12345", ticket_data)

    # Set transition
    store.set_jira_transition("PROJ-12345", "In Progress")

    # Get transition
    status = store.get_jira_transition("PROJ-12345")
    assert status == "In Progress"

    # Verify ticket status was also updated
    ticket = store.get_jira_ticket("PROJ-12345")
    assert ticket["fields"]["status"]["name"] == "In Progress"


def test_list_jira_tickets(temp_daf_home):
    """Test listing all issue tracker tickets."""
    store = MockDataStore()
    store.clear_all()

    # Add multiple tickets
    store.set_jira_ticket("PROJ-12345", {"key": "PROJ-12345", "fields": {"summary": "Ticket 1"}})
    store.set_jira_ticket("PROJ-12346", {"key": "PROJ-12346", "fields": {"summary": "Ticket 2"}})

    # List tickets
    tickets = store.list_jira_tickets()
    assert len(tickets) == 2
    keys = {t["key"] for t in tickets}
    assert "PROJ-12345" in keys
    assert "PROJ-12346" in keys


def test_github_pr_operations(temp_daf_home):
    """Test GitHub PR operations."""
    store = MockDataStore()
    store.clear_all()

    # Initially no PR
    pr = store.get_github_pr("owner/repo", 123)
    assert pr is None

    # Set PR
    pr_data = {
        "number": 123,
        "title": "Test PR",
        "state": "open",
    }
    store.set_github_pr("owner/repo", 123, pr_data)

    # Get PR
    retrieved = store.get_github_pr("owner/repo", 123)
    assert retrieved is not None
    assert retrieved["number"] == 123
    assert retrieved["title"] == "Test PR"


def test_list_github_prs(temp_daf_home):
    """Test listing GitHub PRs for a repository."""
    store = MockDataStore()
    store.clear_all()

    # Add PRs for different repos
    store.set_github_pr("owner/repo1", 1, {"number": 1, "title": "PR 1"})
    store.set_github_pr("owner/repo1", 2, {"number": 2, "title": "PR 2"})
    store.set_github_pr("owner/repo2", 1, {"number": 1, "title": "PR 3"})

    # List PRs for repo1
    prs = store.list_github_prs("owner/repo1")
    assert len(prs) == 2

    # List PRs for repo2
    prs = store.list_github_prs("owner/repo2")
    assert len(prs) == 1


def test_gitlab_mr_operations(temp_daf_home):
    """Test GitLab MR operations."""
    store = MockDataStore()
    store.clear_all()

    # Initially no MR
    mr = store.get_gitlab_mr("group/project", 456)
    assert mr is None

    # Set MR
    mr_data = {
        "iid": 456,
        "title": "Test MR",
        "state": "opened",
    }
    store.set_gitlab_mr("group/project", 456, mr_data)

    # Get MR
    retrieved = store.get_gitlab_mr("group/project", 456)
    assert retrieved is not None
    assert retrieved["iid"] == 456
    assert retrieved["title"] == "Test MR"


def test_list_gitlab_mrs(temp_daf_home):
    """Test listing GitLab MRs for a project."""
    store = MockDataStore()
    store.clear_all()

    # Add MRs for different projects
    store.set_gitlab_mr("group/project1", 1, {"iid": 1, "title": "MR 1"})
    store.set_gitlab_mr("group/project1", 2, {"iid": 2, "title": "MR 2"})
    store.set_gitlab_mr("group/project2", 1, {"iid": 1, "title": "MR 3"})

    # List MRs for project1
    mrs = store.list_gitlab_mrs("group/project1")
    assert len(mrs) == 2

    # List MRs for project2
    mrs = store.list_gitlab_mrs("group/project2")
    assert len(mrs) == 1


def test_claude_session_operations(temp_daf_home):
    """Test Claude Code session operations."""
    store = MockDataStore()
    store.clear_all()

    # Initially no session
    session = store.get_claude_session("uuid-123")
    assert session is None

    # Set session
    session_data = {
        "session_id": "uuid-123",
        "messages": ["message1", "message2"],
    }
    store.set_claude_session("uuid-123", session_data)

    # Get session
    retrieved = store.get_claude_session("uuid-123")
    assert retrieved is not None
    assert retrieved["session_id"] == "uuid-123"
    assert len(retrieved["messages"]) == 2


def test_list_claude_sessions(temp_daf_home):
    """Test listing all Claude Code sessions."""
    store = MockDataStore()
    store.clear_all()

    # Add multiple sessions
    store.set_claude_session("uuid-1", {"session_id": "uuid-1", "messages": []})
    store.set_claude_session("uuid-2", {"session_id": "uuid-2", "messages": []})

    # List sessions
    sessions = store.list_claude_sessions()
    assert len(sessions) == 2
    ids = {s["session_id"] for s in sessions}
    assert "uuid-1" in ids
    assert "uuid-2" in ids


def test_data_persistence_across_instances(temp_daf_home):
    """Test that data persists across MockDataStore instances."""
    # First instance - add data
    store1 = MockDataStore()
    store1.clear_all()
    store1.set_jira_ticket("PROJ-12345", {"key": "PROJ-12345", "fields": {"summary": "Test"}})

    # Get the singleton instance again (same as store1)
    # Then manually reload from disk to simulate new process
    store1._load_all()

    # Data should still be there
    ticket = store1.get_jira_ticket("PROJ-12345")
    assert ticket is not None
    assert ticket["key"] == "PROJ-12345"


def test_thread_safety(temp_daf_home):
    """Test thread-safe operations."""
    store = MockDataStore()
    store.clear_all()

    results = []

    def add_tickets(thread_id):
        """Add tickets from a thread."""
        for i in range(10):
            key = f"PROJ-{thread_id}-{i}"
            store.set_jira_ticket(key, {"key": key, "fields": {"thread": thread_id}})
        results.append(thread_id)

    # Create multiple threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=add_tickets, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Verify all threads completed
    assert len(results) == 5

    # Verify all tickets were added
    tickets = store.list_jira_tickets()
    assert len(tickets) == 50  # 5 threads * 10 tickets each


def test_clear_all(temp_daf_home):
    """Test clearing all mock data."""
    store = MockDataStore()

    # Add data to all services
    store.set_jira_ticket("PROJ-12345", {"key": "PROJ-12345"})
    store.set_github_pr("owner/repo", 1, {"number": 1})
    store.set_gitlab_mr("group/project", 1, {"iid": 1})
    store.set_claude_session("uuid-1", {"session_id": "uuid-1"})

    # Clear all
    store.clear_all()

    # Verify all data is cleared
    assert store.get_jira_ticket("PROJ-12345") is None
    assert store.get_github_pr("owner/repo", 1) is None
    assert store.get_gitlab_mr("group/project", 1) is None
    assert store.get_claude_session("uuid-1") is None


def test_clear_service(temp_daf_home):
    """Test clearing data for a specific service."""
    store = MockDataStore()
    store.clear_all()

    # Add data to multiple services
    store.set_jira_ticket("PROJ-12345", {"key": "PROJ-12345"})
    store.set_github_pr("owner/repo", 1, {"number": 1})

    # Clear only JIRA
    store.clear_service("jira")

    # Verify JIRA data is cleared but GitHub data remains
    assert store.get_jira_ticket("PROJ-12345") is None
    assert store.get_github_pr("owner/repo", 1) is not None


def test_export_import_data(temp_daf_home):
    """Test exporting and importing mock data."""
    store = MockDataStore()
    store.clear_all()

    # Add some data
    store.set_jira_ticket("PROJ-12345", {"key": "PROJ-12345", "fields": {"summary": "Test"}})
    store.set_github_pr("owner/repo", 1, {"number": 1, "title": "PR 1"})

    # Export data
    exported = store.export_data()
    assert "jira" in exported
    assert "github" in exported
    assert "PROJ-12345" in exported["jira"]["tickets"]

    # Clear and import
    store.clear_all()
    assert store.get_jira_ticket("PROJ-12345") is None

    store.import_data(exported)

    # Verify data is restored
    ticket = store.get_jira_ticket("PROJ-12345")
    assert ticket is not None
    assert ticket["key"] == "PROJ-12345"

    pr = store.get_github_pr("owner/repo", 1)
    assert pr is not None
    assert pr["number"] == 1


def test_load_session_index_not_exists(temp_daf_home):
    """Test loading session index when file doesn't exist."""
    store = MockDataStore()
    store.clear_all()

    index = store.load_session_index()
    assert index is None


def test_save_and_load_session_index(temp_daf_home):
    """Test saving and loading session index."""
    store = MockDataStore()
    store.clear_all()

    # Create session index data
    index_data = {
        "sessions": {
            "test-session": [
                {
                    "name": "test-session",
                    "session_id": 1,
                    "goal": "Test goal",
                    "working_directory": "/path/to/project",
                    "project_path": "/path/to/project",
                    "ai_agent_session_id": "uuid-123",
                }
            ]
        }
    }

    # Save index
    store.save_session_index(index_data)

    # Load index
    loaded = store.load_session_index()
    assert loaded is not None
    assert "sessions" in loaded
    assert "test-session" in loaded["sessions"]
    assert len(loaded["sessions"]["test-session"]) == 1
    assert loaded["sessions"]["test-session"][0]["name"] == "test-session"


def test_clear_all_removes_sessions(temp_daf_home):
    """Test that clear_all also removes session index."""
    store = MockDataStore()

    # Save some session data
    index_data = {
        "sessions": {
            "test": [{"name": "test", "session_id": 1}]
        }
    }
    store.save_session_index(index_data)

    # Verify it exists
    assert store.load_session_index() is not None

    # Clear all
    store.clear_all()

    # Verify sessions are cleared
    assert store.load_session_index() is None
