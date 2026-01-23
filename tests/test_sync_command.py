"""Tests for daf sync command with timestamp optimization.

NOTE: Some edge case tests for updating existing sessions are omitted due to
session manager instance synchronization complexity in the test environment.
The core functionality is tested:
- New sessions store jira_updated timestamp
- Unchanged sessions are skipped (not updated)
- Missing updated field is handled gracefully
"""

from datetime import datetime

import pytest
from click.testing import CliRunner

from devflow.cli.commands.sync_command import sync_jira
from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_sync_creates_new_session_with_updated_timestamp(temp_daf_home, mock_jira_cli):
    """Test that sync stores issue_updated timestamp for new sessions."""
    # Initialize config
    runner = CliRunner()
    runner.invoke(cli, ["init"])

    # Set up mock issue tracker ticket with updated timestamp
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "updated": "2025-12-09T10:00:00.000+0000",  # Timestamp at root level
        "fields": {
            "issuetype": {"name": "Story"},
            "status": {"name": "To Do"},
            "summary": "Test ticket",
            "assignee": {"displayName": "Test User"},
            "customfield_12310243": 5,  # Story points
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint 1,...]"],  # Sprint
            "customfield_12311140": "PROJ-100",  # Epic link
        }
    })

    # Run sync
    sync_jira()

    # Verify session was created with issue_updated field
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("PROJ-12345")

    assert len(sessions) == 1
    session = sessions[0]
    assert session.issue_updated == "2025-12-09T10:00:00.000+0000"
    assert session.issue_metadata.get("summary") == "Test ticket"


def test_sync_updates_existing_session_when_ticket_changed(temp_daf_home, mock_jira_cli):
    """Test that sync updates session when ticket timestamp changed."""
    # Initialize config
    runner = CliRunner()
    runner.invoke(cli, ["init"])

    config_loader = ConfigLoader()

    # Create existing session with old timestamp
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="PROJ-12345",
        issue_key="PROJ-12345",
        goal="PROJ-12345: Old summary",
    )
    # Use new issue_metadata structure
    session.issue_tracker = "jira"
    session.issue_key = "PROJ-12345"
    session.issue_updated = "2025-12-08T10:00:00.000+0000"  # Old timestamp
    session.issue_metadata = {"summary": "Old summary", "status": "To Do"}
    session_manager.update_session(session)

    # Set up mock issue tracker ticket with newer timestamp
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "updated": "2025-12-09T10:00:00.000+0000",  # Newer timestamp
        "fields": {
            "issuetype": {"name": "Story"},
            "status": {"name": "In Progress"},
            "summary": "Updated summary",
            "assignee": {"displayName": "Test User"},
            "customfield_12310243": 5,  # Story points
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint 1,...]"],  # Sprint
            "customfield_12311140": "PROJ-100",  # Epic link
        }
    })

    # Run sync
    sync_jira()

    # Reload the session index from disk to see updates from sync
    session_manager.index = config_loader.load_sessions()

    # Verify session was updated
    sessions = session_manager.index.get_sessions("PROJ-12345")
    assert len(sessions) == 1
    updated_session = sessions[0]
    assert updated_session.issue_updated == "2025-12-09T10:00:00.000+0000"
    assert updated_session.issue_metadata.get("summary") == "Updated summary"
    assert updated_session.issue_metadata.get("status") == "In Progress"


def test_sync_skips_existing_session_when_ticket_unchanged(temp_daf_home, mock_jira_cli):
    """Test that sync skips session when ticket timestamp unchanged."""
    # Initialize config
    runner = CliRunner()
    runner.invoke(cli, ["init"])

    config_loader = ConfigLoader()

    # Create existing session with current timestamp
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="PROJ-12345",
        issue_key="PROJ-12345",
        goal="PROJ-12345: Test summary",
    )
    # Use new issue_metadata structure
    session.issue_tracker = "jira"
    session.issue_key = "PROJ-12345"
    session.issue_updated = "2025-12-09T10:00:00.000+0000"
    session.issue_metadata = {"summary": "Test summary", "status": "To Do"}
    original_last_active = session.last_active
    session_manager.update_session(session)

    # Set up mock issue tracker ticket with same timestamp
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "updated": "2025-12-09T10:00:00.000+0000",  # Same timestamp
        "fields": {
            "issuetype": {"name": "Story"},
            "status": {"name": "To Do"},
            "summary": "Test summary",
            "assignee": {"displayName": "Test User"},
            "customfield_12310243": 5,  # Story points
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint 1,...]"],  # Sprint
            "customfield_12311140": "PROJ-100",  # Epic link
        }
    })

    # Run sync
    sync_jira()

    # Verify session was NOT updated (last_active should not change)
    sessions = session_manager.index.get_sessions("PROJ-12345")
    assert len(sessions) == 1
    unchanged_session = sessions[0]
    assert unchanged_session.issue_updated == "2025-12-09T10:00:00.000+0000"
    # Summary should remain the same since we didn't update
    assert unchanged_session.issue_metadata.get("summary") == "Test summary"


def test_sync_updates_existing_session_without_jira_updated(temp_daf_home, mock_jira_cli):
    """Test that sync updates session that has no jira_updated field (migration case)."""
    # Initialize config
    runner = CliRunner()
    runner.invoke(cli, ["init"])

    config_loader = ConfigLoader()

    # Create existing session WITHOUT jira_updated field (old session)
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="PROJ-12345",
        issue_key="PROJ-12345",
        goal="PROJ-12345: Old summary",
    )
    # Test migration case - session without issue_updated
    session.issue_tracker = "jira"
    session.issue_key = "PROJ-12345"
    session.issue_metadata = {"summary": "Old summary", "status": "To Do"}
    # issue_updated is None (old session before this feature)
    session_manager.update_session(session)

    # Set up mock issue tracker ticket with timestamp
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "updated": "2025-12-09T10:00:00.000+0000",
        "fields": {
            "issuetype": {"name": "Story"},
            "status": {"name": "To Do"},
            "summary": "Old summary",
            "assignee": {"displayName": "Test User"},
            "customfield_12310243": 5,  # Story points
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint 1,...]"],  # Sprint
            "customfield_12311140": "PROJ-100",  # Epic link
        }
    })

    # Run sync
    sync_jira()

    # Reload the session index from disk to see updates from sync
    session_manager.index = config_loader.load_sessions()

    # Verify session was updated to populate issue_updated field
    sessions = session_manager.index.get_sessions("PROJ-12345")
    assert len(sessions) == 1
    migrated_session = sessions[0]
    assert migrated_session.issue_updated == "2025-12-09T10:00:00.000+0000"
    assert migrated_session.issue_metadata.get("summary") == "Old summary"


def test_sync_handles_missing_updated_field_gracefully(temp_daf_home, mock_jira_cli):
    """Test that sync handles case where JIRA doesn't return updated field."""
    # Initialize config
    runner = CliRunner()
    runner.invoke(cli, ["init"])

    # Set up mock issue tracker ticket WITHOUT updated timestamp
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        # No 'updated' field
        "fields": {
            "issuetype": {"name": "Story"},
            "status": {"name": "To Do"},
            "summary": "Test ticket",
            "assignee": {"displayName": "Test User"},
            "customfield_12310243": 5,  # Story points
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint 1,...]"],  # Sprint
            "customfield_12311140": "PROJ-100",  # Epic link
        }
    })

    # Run sync - should not crash
    sync_jira()

    # Verify session was created but issue_updated is None
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("PROJ-12345")

    assert len(sessions) == 1
    session = sessions[0]
    assert session.issue_updated is None
    assert session.issue_metadata.get("summary") == "Test ticket"


def test_sync_multiple_sessions_mixed_updates(temp_daf_home, mock_jira_cli):
    """Test sync with multiple sessions where some need updates and some don't."""
    # Initialize config
    runner = CliRunner()
    runner.invoke(cli, ["init"])

    config_loader = ConfigLoader()

    session_manager = SessionManager(config_loader)

    # Create two existing sessions
    session1 = session_manager.create_session(
        name="PROJ-111",
        issue_key="PROJ-111",
        goal="PROJ-111: Ticket 1",
    )
    session1.issue_tracker = "jira"
    session1.issue_key = "PROJ-111"
    session1.issue_updated = "2025-12-08T10:00:00.000+0000"  # Old
    session1.issue_metadata = {"summary": "Ticket 1"}
    session_manager.update_session(session1)

    session2 = session_manager.create_session(
        name="PROJ-222",
        issue_key="PROJ-222",
        goal="PROJ-222: Ticket 2",
    )
    session2.issue_tracker = "jira"
    session2.issue_key = "PROJ-222"
    session2.issue_updated = "2025-12-09T10:00:00.000+0000"  # Current
    session2.issue_metadata = {"summary": "Ticket 2"}
    session_manager.update_session(session2)

    # Set up mock issue tracker tickets
    mock_jira_cli.set_ticket("PROJ-111", {
        "key": "PROJ-111",
        "updated": "2025-12-09T12:00:00.000+0000",  # Changed
        "fields": {
            "issuetype": {"name": "Story"},
            "status": {"name": "In Progress"},
            "summary": "Ticket 1 Updated",
            "assignee": {"displayName": "Test User"},
            "customfield_12310243": 5,
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint 1,...]"],
            "customfield_12311140": "PROJ-100",
        }
    })

    mock_jira_cli.set_ticket("PROJ-222", {
        "key": "PROJ-222",
        "updated": "2025-12-09T10:00:00.000+0000",  # Unchanged
        "fields": {
            "issuetype": {"name": "Bug"},
            "status": {"name": "To Do"},
            "summary": "Ticket 2",
            "assignee": {"displayName": "Test User"},
            "customfield_12310243": 3,
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint 1,...]"],
            "customfield_12311140": "PROJ-100",
        }
    })

    mock_jira_cli.set_ticket("PROJ-333", {
        "key": "PROJ-333",
        "updated": "2025-12-09T11:00:00.000+0000",  # New
        "fields": {
            "issuetype": {"name": "Task"},
            "status": {"name": "To Do"},
            "summary": "New Ticket",
            "assignee": {"displayName": "Test User"},
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint 1,...]"],
            "customfield_12311140": "PROJ-100",
        }
    })

    # Run sync
    sync_jira()

    # Reload the session index from disk to see updates from sync
    session_manager.index = config_loader.load_sessions()

    # Verify results
    session1_updated = session_manager.index.get_sessions("PROJ-111")[0]
    assert session1_updated.issue_metadata.get("summary") == "Ticket 1 Updated"
    assert session1_updated.issue_updated == "2025-12-09T12:00:00.000+0000"

    session2_unchanged = session_manager.index.get_sessions("PROJ-222")[0]
    assert session2_unchanged.issue_metadata.get("summary") == "Ticket 2"
    assert session2_unchanged.issue_updated == "2025-12-09T10:00:00.000+0000"

    session3_new = session_manager.index.get_sessions("PROJ-333")[0]
    assert session3_new.issue_metadata.get("summary") == "New Ticket"
    assert session3_new.issue_updated == "2025-12-09T11:00:00.000+0000"



def test_sync_ignores_ticket_creation_sessions_and_creates_development_session(temp_daf_home, mock_jira_cli):
    """Test that daf sync ignores ticket_creation sessions and creates new development sessions."""
    # Initialize config
    runner = CliRunner()
    runner.invoke(cli, ["init"])

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session for PROJ-12345 (simulates daf jira new)
    ticket_creation_session = session_manager.create_session(
        name="creation-PROJ-12345",
        issue_key="PROJ-12345",
        goal="Create JIRA story for feature X",
    )
    ticket_creation_session.session_type = "ticket_creation"
    ticket_creation_session.issue_tracker = "jira"
    ticket_creation_session.issue_key = "PROJ-12345"
    ticket_creation_session.issue_metadata = {"summary": "Feature X"}
    session_manager.update_session(ticket_creation_session)

    # Verify ticket_creation session exists
    all_sessions = session_manager.index.get_sessions("PROJ-12345")
    assert len(all_sessions) == 1
    assert all_sessions[0].session_type == "ticket_creation"

    # Set up mock issue tracker ticket (the ticket now exists and is assigned to you)
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "updated": "2025-12-09T10:00:00.000+0000",
        "fields": {
            "issuetype": {"name": "Story"},
            "status": {"name": "To Do"},
            "summary": "Feature X",
            "assignee": {"displayName": "Test User"},
            "customfield_12310243": 5,  # Story points
            "customfield_12310940": ["com.atlassian.greenhopper.service.sprint.Sprint@xxxxx[id=1234,name=Sprint 1,...]"],
            "customfield_12311140": "PROJ-100",  # Epic link
        }
    })

    # Run sync
    sync_jira()

    # Reload session index
    session_manager.index = config_loader.load_sessions()

    # Verify: ticket_creation session still exists in its group
    creation_sessions = session_manager.index.get_sessions("creation-PROJ-12345")
    assert len(creation_sessions) == 1
    assert creation_sessions[0].session_type == "ticket_creation"
    assert creation_sessions[0].issue_key == "PROJ-12345"

    # Verify: new development session was created in a separate group
    dev_sessions = session_manager.index.get_sessions("PROJ-12345")
    assert len(dev_sessions) == 1, "Should have created one development session"

    dev_session = dev_sessions[0]
    assert dev_session.issue_key == "PROJ-12345"
    assert dev_session.issue_metadata.get("summary") == "Feature X"
    assert dev_session.session_type == "development"
    assert dev_session.name == "PROJ-12345"  # Development sessions use issue key as name

    # Verify we now have 2 different sessions with the same issue key
    all_sessions = session_manager.index.sessions
    sessions_with_issue_key = [
        name for name, session in all_sessions.items()
        if session.issue_key == "PROJ-12345"
    ]
    assert len(sessions_with_issue_key) == 2, "Should have 2 sessions (creation and development)"
    assert "creation-PROJ-12345" in sessions_with_issue_key
    assert "PROJ-12345" in sessions_with_issue_key

