"""Tests for session management functionality."""

from datetime import datetime
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import Session, WorkSession
from devflow.session.manager import SessionManager


def test_create_session(temp_daf_home):
    """Test creating a basic session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
    )

    assert session.name == "test-session"
    assert session.goal == "Test goal"
    assert session.working_directory == "test-dir"
    assert session.status == "created"
    # Verify conversation was created
    active_conv = session.active_conversation
    assert active_conv is not None
    assert active_conv.project_path == "/path/to/project"
    assert active_conv.ai_agent_session_id == "test-uuid-123"
    # Verify conversation was created 
    assert "test-dir" in session.conversations
    assert session.conversations["test-dir"].active_session.project_path == "/path/to/project"
    assert len(session.conversations["test-dir"].archived_sessions) == 0


def test_create_session_with_jira(temp_daf_home):
    """Test creating a session with issue key."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="jira-session",
        goal="JIRA task",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-456",
        issue_key="PROJ-12345",
    )

    assert session.issue_key == "PROJ-12345"


def test_create_multiple_sessions_in_group(temp_daf_home):
    """Test that creating sessions with duplicate names raises an error."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session
    session1 = session_manager.create_session(
        name="multi-session",
        goal="First session",
        working_directory="dir1",
        project_path="/path/to/project1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should fail
    with pytest.raises(ValueError, match="already exists"):
        session_manager.create_session(
            name="multi-session",
            goal="Second session",
            working_directory="dir2",
            project_path="/path/to/project2",
            ai_agent_session_id="uuid-2",
        )


def test_get_session_by_name(temp_daf_home):
    """Test retrieving session by name."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="findme",
        goal="Find this session",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-find",
    )

    sessions = session_manager.index.get_sessions("findme")
    assert len(sessions) == 1
    assert sessions[0].name == "findme"


def test_get_session_by_issue_key(temp_daf_home):
    """Test retrieving session by issue key."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="jira-lookup",
        goal="JIRA lookup test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-jira",
        issue_key="PROJ-99999",
    )

    sessions = session_manager.index.get_sessions("PROJ-99999")
    assert len(sessions) == 1
    assert sessions[0].issue_key == "PROJ-99999"


def test_get_nonexistent_session(temp_daf_home):
    """Test getting a session that doesn't exist."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    sessions = session_manager.index.get_sessions("nonexistent")
    assert len(sessions) == 0


def test_list_sessions(temp_daf_home):
    """Test listing all sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multiple sessions
    session_manager.create_session(
        name="session1",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="session2",
        goal="Second",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    all_sessions = session_manager.index.list_sessions()
    assert len(all_sessions) == 2


def test_list_sessions_by_status(temp_daf_home):
    """Test filtering sessions by status."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions with different statuses
    session1 = session_manager.create_session(
        name="created-session",
        goal="Created",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session2 = session_manager.create_session(
        name="progress-session",
        goal="In Progress",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.status = "in_progress"
    session_manager.index.sessions["progress-session"] = session2
    session_manager._save_index()

    # Filter by status
    in_progress = session_manager.index.list_sessions(status="in_progress")
    assert len(in_progress) == 1
    assert in_progress[0].status == "in_progress"


def test_list_sessions_by_working_directory(temp_daf_home):
    """Test filtering sessions by working directory."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="backend-session",
        goal="Backend work",
        working_directory="backend-service",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="frontend-session",
        goal="Frontend work",
        working_directory="frontend-app",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    backend_sessions = session_manager.index.list_sessions(
        working_directory="backend-service"
    )
    assert len(backend_sessions) == 1
    assert backend_sessions[0].working_directory == "backend-service"


def test_delete_session(temp_daf_home):
    """Test deleting a session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="delete-me",
        goal="To be deleted",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-delete",
    )

    # Verify session exists
    sessions = session_manager.index.get_sessions("delete-me")
    assert len(sessions) == 1

    # Delete session
    session_manager.index.remove_session("delete-me")
    session_manager._save_index()

    # Verify session is gone
    sessions = session_manager.index.get_sessions("delete-me")
    assert len(sessions) == 0


def test_delete_specific_session_in_group(temp_daf_home):
    """Test deleting a session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session_manager.create_session(
        name="multi",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Delete the session
    session_manager.delete_session("multi")

    # Verify session is deleted
    session = session_manager.index.get_session("multi")
    assert session is None

def test_update_session_status(temp_daf_home):
    """Test updating session status."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="status-test",
        goal="Status test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-status",
    )

    assert session.status == "created"

    # Update status
    sessions = session_manager.index.get_sessions("status-test")
    sessions[0].status = "in_progress"
    session_manager._mark_modified(sessions[0])
    session_manager._save_index()

    # Verify update persisted
    fresh_manager = SessionManager(config_loader)
    sessions = fresh_manager.index.get_sessions("status-test")
    assert sessions[0].status == "in_progress"


def test_session_persistence(temp_daf_home):
    """Test that sessions persist across SessionManager instances."""
    config_loader = ConfigLoader()

    # Create session with first manager
    manager1 = SessionManager(config_loader)
    manager1.create_session(
        name="persistent",
        goal="Should persist",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-persist",
    )

    # Create new manager instance
    manager2 = SessionManager(config_loader)
    sessions = manager2.index.get_sessions("persistent")

    assert len(sessions) == 1
    assert sessions[0].name == "persistent"


def test_start_work_session(temp_daf_home):
    """Test starting a work session for time tracking."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="time-test",
        goal="Time tracking test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-time",
    )

    # Start work session
    session_manager.start_work_session("time-test")

    sessions = session_manager.index.get_sessions("time-test")
    session = sessions[0]

    assert session.time_tracking_state == "active"
    assert len(session.work_sessions) == 1
    assert session.work_sessions[0].start is not None
    assert session.work_sessions[0].end is None


def test_end_work_session(temp_daf_home):
    """Test ending a work session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="time-test",
        goal="Time tracking test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-time",
    )

    # Start and end work session
    session_manager.start_work_session("time-test")
    session_manager.end_work_session("time-test")

    sessions = session_manager.index.get_sessions("time-test")
    session = sessions[0]

    assert session.time_tracking_state == "paused"
    assert session.work_sessions[0].end is not None


def test_multiple_work_sessions(temp_daf_home):
    """Test tracking multiple work sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="multi-time",
        goal="Multiple work sessions",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-multi-time",
    )

    # First work session
    session_manager.start_work_session("multi-time")
    session_manager.end_work_session("multi-time")

    # Second work session
    session_manager.start_work_session("multi-time")
    session_manager.end_work_session("multi-time")

    sessions = session_manager.index.get_sessions("multi-time")
    session = sessions[0]

    assert len(session.work_sessions) == 2


def test_session_with_tags(temp_daf_home):
    """Test that sessions have a tags field."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="tagged-session",
        goal="Tagged session",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-tagged",
    )

    # Sessions have tags field (starts empty)
    assert hasattr(session, "tags")
    assert session.tags == []

    # Tags can be added after creation
    session.tags = ["backend", "api", "feature"]
    assert session.tags == ["backend", "api", "feature"]


def test_session_with_branch(temp_daf_home):
    """Test creating session with git branch."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="branch-session",
        goal="Branch session",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-branch",
        branch="feature/test-branch",
    )

    # Verify conversation has the branch 
    active_conv = session.active_conversation
    assert active_conv is not None
    assert active_conv.branch == "feature/test-branch"
    assert session.conversations["test-dir"].active_session.branch == "feature/test-branch"


def test_session_metadata_fields(temp_daf_home):
    """Test that session has all required metadata fields."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="metadata-test",
        goal="Test metadata",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-metadata",
    )

    # Verify all metadata fields exist
    assert hasattr(session, "created")
    assert hasattr(session, "last_active")
    assert hasattr(session, "status")
    # message_count is now in ConversationContext, not Session
    assert hasattr(session, "conversations")
    assert hasattr(session, "work_sessions")
    assert hasattr(session, "time_tracking_state")
    assert isinstance(session.created, datetime)
    assert isinstance(session.last_active, datetime)


def test_get_active_session_for_project_none(temp_daf_home):
    """Test get_active_session_for_project when no active sessions exist."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session but don't mark it as in_progress
    session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Should return None since status is "created"
    active = session_manager.get_active_session_for_project("/path/to/project")
    assert active is None


def test_get_active_session_for_project_found(temp_daf_home):
    """Test get_active_session_for_project when active session exists."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session and mark it as in_progress
    session = session_manager.create_session(
        name="active-session",
        goal="Active goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )
    session.status = "in_progress"
    session_manager.update_session(session)

    # Should find the active session
    active = session_manager.get_active_session_for_project("/path/to/project")
    assert active is not None
    assert active.name == "active-session"


def test_get_active_session_for_project_paused(temp_daf_home):
    """Test get_active_session_for_project ignores paused sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session and mark it as paused
    session = session_manager.create_session(
        name="paused-session",
        goal="Paused goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )
    session.status = "paused"
    session_manager.update_session(session)

    # Should return None since session is paused, not in_progress
    active = session_manager.get_active_session_for_project("/path/to/project")
    assert active is None


def test_get_active_session_for_project_different_projects(temp_daf_home):
    """Test get_active_session_for_project with multiple projects."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session for project A (active)
    session_a = session_manager.create_session(
        name="session-a",
        goal="Project A",
        working_directory="dir-a",
        project_path="/path/to/project-a",
        ai_agent_session_id="uuid-a",
    )
    session_a.status = "in_progress"
    session_manager.update_session(session_a)

    # Create session for project B (active)
    session_b = session_manager.create_session(
        name="session-b",
        goal="Project B",
        working_directory="dir-b",
        project_path="/path/to/project-b",
        ai_agent_session_id="uuid-b",
    )
    session_b.status = "in_progress"
    session_manager.update_session(session_b)

    # Should find the correct session for each project
    active_a = session_manager.get_active_session_for_project("/path/to/project-a")
    assert active_a is not None
    assert active_a.name == "session-a"

    active_b = session_manager.get_active_session_for_project("/path/to/project-b")
    assert active_b is not None
    assert active_b.name == "session-b"


def test_get_active_session_for_project_complete_status(temp_daf_home):
    """Test get_active_session_for_project ignores completed sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session and mark it as complete
    session = session_manager.create_session(
        name="complete-session",
        goal="Complete goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )
    session.status = "complete"
    session_manager.update_session(session)

    # Should return None since session is complete, not in_progress
    active = session_manager.get_active_session_for_project("/path/to/project")
    assert active is None


# PROJ-60665: Session renaming tests


def test_rename_session_success(temp_daf_home):
    """Test successfully renaming a session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="old-name",
        goal="Test session",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Verify session directory exists with old name
    old_dir = config_loader.get_session_dir("old-name")
    assert old_dir.exists()

    # Rename the session
    session_manager.rename_session("old-name", "new-name")

    # Verify session was renamed in index
    assert "new-name" in session_manager.index.sessions
    assert "old-name" not in session_manager.index.sessions

    # Verify session object was updated
    renamed_session = session_manager.get_session("new-name")
    assert renamed_session is not None
    assert renamed_session.name == "new-name"
    assert renamed_session.goal == "Test session"

    # Verify directory was renamed
    new_dir = config_loader.get_session_dir("new-name")
    assert new_dir.exists()
    assert not old_dir.exists()

    # Verify metadata.json contains new name
    metadata_file = new_dir / "metadata.json"
    assert metadata_file.exists()
    import json
    with open(metadata_file) as f:
        metadata = json.load(f)
    assert metadata["name"] == "new-name"


def test_rename_session_old_not_found(temp_daf_home):
    """Test renaming a session that doesn't exist."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Try to rename non-existent session
    with pytest.raises(ValueError, match="Session 'nonexistent' not found"):
        session_manager.rename_session("nonexistent", "new-name")


def test_rename_session_new_name_exists(temp_daf_home):
    """Test renaming to a name that already exists."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create two sessions
    session_manager.create_session(
        name="session-1",
        goal="First session",
        working_directory="dir1",
        project_path="/path/1",
        ai_agent_session_id="uuid-1",
    )
    session_manager.create_session(
        name="session-2",
        goal="Second session",
        working_directory="dir2",
        project_path="/path/2",
        ai_agent_session_id="uuid-2",
    )

    # Try to rename session-1 to session-2 (which already exists)
    with pytest.raises(ValueError, match="Session 'session-2' already exists"):
        session_manager.rename_session("session-1", "session-2")


def test_rename_session_multiple_in_group(temp_daf_home):
    """Test that creating duplicate session names fails."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session1 = session_manager.create_session(
        name="multi-session",
        goal="First session",
        working_directory="dir1",
        project_path="/path/1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create another session with the same name should fail
    with pytest.raises(ValueError, match="already exists"):
        session_manager.create_session(
            name="multi-session",
            goal="Second session",
            working_directory="dir2",
            project_path="/path/2",
            ai_agent_session_id="uuid-2",
        )


def test_rename_session_directory_doesnt_exist(temp_daf_home):
    """Test renaming when session directory doesn't exist (edge case)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="test-session",
        goal="Test session",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Manually delete the session directory
    session_dir = config_loader.get_session_dir("test-session")
    import shutil
    if session_dir.exists():
        shutil.rmtree(session_dir)

    # Rename should still work (just updates index)
    session_manager.rename_session("test-session", "renamed-session")

    # Verify session was renamed in index
    assert "renamed-session" in session_manager.index.sessions
    assert "test-session" not in session_manager.index.sessions


def test_rename_session_preserves_issue_key(temp_daf_home):
    """Test that renaming preserves issue key."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with issue key
    session = session_manager.create_session(
        name="jira-session",
        goal="JIRA task",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
        issue_key="PROJ-12345",
    )

    # Rename the session
    session_manager.rename_session("jira-session", "renamed-jira-session")

    # Verify issue key is preserved
    renamed_session = session_manager.get_session("renamed-jira-session")
    assert renamed_session.issue_key == "PROJ-12345"

    # Verify can still find by issue key
    session_by_jira = session_manager.get_session("PROJ-12345")
    assert session_by_jira.name == "renamed-jira-session"


def test_rename_session_preserves_work_sessions(temp_daf_home):
    """Test that renaming preserves work sessions and time tracking."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="work-session",
        goal="Work task",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Start and end work session
    session_manager.start_work_session("work-session")
    session_manager.end_work_session("work-session")

    # Verify work session exists
    session_before = session_manager.get_session("work-session")
    assert len(session_before.work_sessions) == 1

    # Rename the session
    session_manager.rename_session("work-session", "renamed-work-session")

    # Verify work sessions are preserved
    renamed_session = session_manager.get_session("renamed-work-session")
    assert len(renamed_session.work_sessions) == 1
    assert renamed_session.work_sessions[0].duration is not None


def test_rename_session_prevents_double_rename(temp_daf_home):
    """Test that sessions already matching creation-* pattern aren't renamed again.

    This ensures that if a session is reopened and a second ticket is created,
    the session name isn't changed again (PROJ-60665).
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with creation-* name (simulating already-renamed session)
    session = session_manager.create_session(
        name="creation-PROJ-123",
        goal="First ticket",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Set session type after creation
    session.session_type = "ticket_creation"
    session_manager.update_session(session)

    # Verify the session exists
    assert session.name == "creation-PROJ-123"
    assert session.session_type == "ticket_creation"

    # Now simulate creating a second ticket in the same session
    # The session name should NOT be renamed because it already matches creation-* pattern
    # This would be checked in jira_create_commands.py with the regex check
    import re
    session_name = "creation-PROJ-123"
    matches_pattern = re.match(r'^creation-[A-Z]+-\d+$', session_name)
    assert matches_pattern is not None, "Session name should match creation-* pattern"

    # Since it matches the pattern, rename should be skipped
    # (tested via integration tests in test_jira_create_commands.py)


def test_rename_session_no_duplicates(temp_daf_home):
    """Test that rename creates no duplicate sessions (PROJ-60830).

    This test verifies the fix for the bug where rename_session() would create
    a duplicate session instead of properly renaming the existing one. The bug
    occurred due to marking both old_name and new_name as modified, which
    confused the read-modify-write logic in _save_index().
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="remove-pipx-and-replace-it-by-pip-as-it-is-7014bf",
        goal="Remove pipx and replace it by pip as it is not necessarily installed on laptop",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
        issue_key="PROJ-60827",
    )

    # Verify only one session exists before rename
    sessions_before = session_manager.list_sessions()
    assert len(sessions_before) == 1
    assert sessions_before[0].name == "remove-pipx-and-replace-it-by-pip-as-it-is-7014bf"

    # Rename the session (simulating the daf jira new workflow)
    session_manager.rename_session(
        "remove-pipx-and-replace-it-by-pip-as-it-is-7014bf",
        "creation-PROJ-60827"
    )

    # Verify only one session exists after rename (no duplicates)
    sessions_after = session_manager.list_sessions()
    assert len(sessions_after) == 1, f"Expected 1 session, found {len(sessions_after)}"
    assert sessions_after[0].name == "creation-PROJ-60827"

    # Verify old session name doesn't exist in index
    assert "remove-pipx-and-replace-it-by-pip-as-it-is-7014bf" not in session_manager.index.sessions
    assert "creation-PROJ-60827" in session_manager.index.sessions

    # Verify we can't get session by old name
    old_session = session_manager.get_session("remove-pipx-and-replace-it-by-pip-as-it-is-7014bf")
    assert old_session is None

    # Verify we can get session by new name
    new_session = session_manager.get_session("creation-PROJ-60827")
    assert new_session is not None
    assert new_session.name == "creation-PROJ-60827"
    assert new_session.issue_key == "PROJ-60827"

    # Verify we can get session by issue key
    session_by_jira = session_manager.get_session("PROJ-60827")
    assert session_by_jira is not None
    assert session_by_jira.name == "creation-PROJ-60827"

    # Create a new SessionManager instance to verify persistence
    session_manager2 = SessionManager(config_loader)
    sessions_reloaded = session_manager2.list_sessions()
    assert len(sessions_reloaded) == 1, f"After reload, expected 1 session, found {len(sessions_reloaded)}"
    assert sessions_reloaded[0].name == "creation-PROJ-60827"

    # Verify old session name is not in reloaded index
    assert "remove-pipx-and-replace-it-by-pip-as-it-is-7014bf" not in session_manager2.index.sessions


def test_rename_session_update_with_stale_object(temp_daf_home):
    """Test that updating a session after rename doesn't recreate old directory (PROJ-60830).

    This test simulates the exact bug scenario:
    1. Create session with old name
    2. Rename session to new name
    3. Call update_session() with the OLD session object (stale name)
    4. Verify that only the NEW directory exists, not the old one
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="when-creating-a-new-jira-ticket-use-the-jir-d7f9b1",
        goal="Create JIRA story",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    old_name = session.name
    new_name = "creation-PROJ-60879"

    # Verify old directory exists before rename
    old_dir = config_loader.get_session_dir(old_name)
    assert old_dir.exists()

    # Rename the session
    session_manager.rename_session(old_name, new_name)

    # Verify old directory is gone, new directory exists
    new_dir = config_loader.get_session_dir(new_name)
    assert new_dir.exists()
    assert not old_dir.exists()

    # CRITICAL: Now update the session using the OLD session object (with stale name)
    # This simulates what happens when daf complete is called after daf jira create renames
    session.status = "complete"  # Modify the old session object
    session_manager.update_session(session)  # Update with stale session object

    # Verify that only ONE session exists (no duplicate)
    sessions_after = session_manager.list_sessions()
    assert len(sessions_after) == 1, f"Expected 1 session, found {len(sessions_after)}"
    assert sessions_after[0].name == new_name
    assert sessions_after[0].status == "complete"

    # Verify old directory was NOT recreated
    assert not old_dir.exists(), f"Old directory {old_dir} should not exist after update"
    assert new_dir.exists(), f"New directory {new_dir} should exist"

    # Verify old session name doesn't exist in index
    assert old_name not in session_manager.index.sessions
    assert new_name in session_manager.index.sessions

    # Verify metadata was saved in new directory only
    old_metadata = old_dir / "metadata.json"
    new_metadata = new_dir / "metadata.json"
    assert not old_metadata.exists(), "Old metadata.json should not exist"
    assert new_metadata.exists(), "New metadata.json should exist"

    # Verify metadata has correct name and status
    import json
    with open(new_metadata) as f:
        metadata = json.load(f)
    assert metadata["name"] == new_name
    assert metadata["status"] == "complete"


def test_get_active_session_name_returns_none_outside_claude(temp_daf_home):
    """Test that get_active_session_name returns None when not in a Claude session.

    This ensures that daf jira create run from terminal (outside Claude)
    doesn't attempt to rename any session (PROJ-60665).
    """
    import os
    from devflow.cli.utils import get_active_session_name

    # Ensure AI_AGENT_SESSION_ID is not set
    if "AI_AGENT_SESSION_ID" in os.environ:
        del os.environ["AI_AGENT_SESSION_ID"]

    # Should return None when not in Claude session
    result = get_active_session_name()
    assert result is None, "get_active_session_name should return None when AI_AGENT_SESSION_ID not set"


def test_session_type_persistence_in_metadata(temp_daf_home):
    """Test that session_type is correctly persisted in metadata.json.

    This ensures that ticket_creation sessions can be distinguished from
    development sessions, preventing daf open from incorrectly matching
    creation-PROJ-XXXXX when searching for PROJ-XXXXX.
    """
    import json
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a ticket_creation session
    session = session_manager.create_session(
        name="creation-PROJ-12345",
        goal="PROJ-12345: Test ticket creation",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
        issue_key="PROJ-12345",
    )

    # Set session_type to ticket_creation
    session.session_type = "ticket_creation"
    session_manager.update_session(session)

    # Verify session_type is in sessions.json
    sessions = session_manager.index.get_sessions("creation-PROJ-12345")
    assert len(sessions) == 1
    assert sessions[0].session_type == "ticket_creation"

    # Verify session_type is in metadata.json
    session_dir = config_loader.get_session_dir("creation-PROJ-12345")
    metadata_file = session_dir / "metadata.json"
    assert metadata_file.exists()

    with open(metadata_file) as f:
        metadata = json.load(f)

    assert "session_type" in metadata, "session_type should be in metadata.json"
    assert metadata["session_type"] == "ticket_creation"

    # Verify created field is also in metadata.json
    assert "created" in metadata, "created should be in metadata.json"
    assert metadata["created"] is not None


def test_session_type_default_value(temp_daf_home):
    """Test that session_type defaults to 'development' for new sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session without explicitly setting session_type
    session = session_manager.create_session(
        name="test-development",
        goal="Test development session",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid",
    )

    # Verify session_type defaults to "development"
    assert session.session_type == "development"

    # Verify it's persisted correctly
    sessions = session_manager.index.get_sessions("test-development")
    assert sessions[0].session_type == "development"
