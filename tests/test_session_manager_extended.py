"""Extended tests for SessionManager."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_delete_session_by_name(temp_daf_home):
    """Test deleting a session by name."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="delete-test",
        goal="To be deleted",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-delete",
    )

    # Verify session exists
    sessions = session_manager.index.get_sessions("delete-test")
    assert len(sessions) == 1

    # Delete it
    session_manager.delete_session("delete-test")

    # Verify it's gone
    sessions = session_manager.index.get_sessions("delete-test")
    assert len(sessions) == 0


def test_delete_specific_session_by_id(temp_daf_home):
    """Test that attempting to create duplicate session names raises ValueError."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session
    session_manager.create_session(
        name="multi",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    import pytest
    with pytest.raises(ValueError, match="Session 'multi' already exists"):
        session_manager.create_session(
            name="multi",
            goal="Second",
            working_directory="dir2",
            project_path="/path2",
            ai_agent_session_id="uuid-2",
        )
    

def test_list_sessions_with_sprint_filter(temp_daf_home):
    """Test listing sessions filtered by JIRA sprint."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session1 = session_manager.create_session(
        name="sprint1",
        goal="Sprint 42 work",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.issue_metadata = {"sprint": "Sprint 42"}
    session_manager.update_session(session1)

    session2 = session_manager.create_session(
        name="sprint2",
        goal="Sprint 43 work",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.issue_metadata = {"sprint": "Sprint 43"}
    session_manager.update_session(session2)

    result = session_manager.list_sessions(sprint="Sprint 42")

    assert len(result) == 1
    assert result[0].issue_metadata.get("sprint") == "Sprint 42"


def test_list_sessions_with_jira_status_filter(temp_daf_home):
    """Test listing sessions filtered by JIRA status."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session1 = session_manager.create_session(
        name="new-task",
        goal="New task",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.issue_metadata = {"status": "New"}
    session_manager.update_session(session1)

    session2 = session_manager.create_session(
        name="done-task",
        goal="Done task",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.issue_metadata = {"status": "Done"}
    session_manager.update_session(session2)

    result = session_manager.list_sessions(issue_status="New")

    assert len(result) == 1
    assert result[0].issue_metadata.get("status") == "New"


def test_list_sessions_with_date_range(temp_daf_home):
    """Test listing sessions with date range filters."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    now = datetime.now()

    # Create recent session
    session1 = session_manager.create_session(
        name="recent",
        goal="Recent",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    # Manually set last_active after update (since update sets it to now)
    sessions = session_manager.index.get_sessions("recent")
    sessions[0].last_active = now - timedelta(days=1)
    session_manager._save_index()

    # Create old session
    session2 = session_manager.create_session(
        name="old",
        goal="Old",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    sessions = session_manager.index.get_sessions("old")
    sessions[0].last_active = now - timedelta(days=10)
    session_manager._save_index()

    # Get sessions since 5 days ago
    since = now - timedelta(days=5)
    result = session_manager.list_sessions(since=since)

    assert len(result) == 1
    assert result[0].name == "recent"


def test_list_sessions_before_date(temp_daf_home):
    """Test listing sessions before a certain date."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    now = datetime.now()

    # Create recent session
    session1 = session_manager.create_session(
        name="recent",
        goal="Recent",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    # Manually set last_active after creation
    sessions = session_manager.index.get_sessions("recent")
    sessions[0].last_active = now - timedelta(days=1)
    session_manager._save_index()

    # Create old session
    session2 = session_manager.create_session(
        name="old",
        goal="Old",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    sessions = session_manager.index.get_sessions("old")
    sessions[0].last_active = now - timedelta(days=10)
    session_manager._save_index()

    # Get sessions before 5 days ago
    before = now - timedelta(days=5)
    result = session_manager.list_sessions(before=before)

    assert len(result) == 1
    assert result[0].name == "old"


def test_add_note_to_session(temp_daf_home):
    """Test adding a note to a session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="note-test",
        goal="Test notes",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-note",
    )

    # Add a note
    session_manager.add_note("note-test", "This is a test note")

    # Verify notes file was created
    session_dir = config_loader.get_session_dir("note-test")
    notes_file = session_dir / "notes.md"

    assert notes_file.exists()

    # Verify note content
    content = notes_file.read_text()
    assert "This is a test note" in content
    assert "Session Notes: note-test" in content


def test_add_note_creates_notes_file(temp_daf_home):
    """Test that adding first note creates the notes file."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="first-note",
        goal="Test first note",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    session_dir = config_loader.get_session_dir("first-note")
    notes_file = session_dir / "notes.md"

    # Verify notes file doesn't exist yet
    assert not notes_file.exists()

    # Add first note
    session_manager.add_note("first-note", "First note ever")

    # Verify file was created
    assert notes_file.exists()


def test_add_note_appends_to_existing(temp_daf_home):
    """Test that adding notes appends to existing notes file."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="append-test",
        goal="Test appending",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Add first note
    session_manager.add_note("append-test", "First note")

    # Add second note
    session_manager.add_note("append-test", "Second note")

    # Verify both notes are in the file
    session_dir = config_loader.get_session_dir("append-test")
    notes_file = session_dir / "notes.md"
    content = notes_file.read_text()

    assert "First note" in content
    assert "Second note" in content


def test_add_note_with_issue_key(temp_daf_home):
    """Test that notes file includes issue key when present."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="jira-note",
        goal="Test with JIRA",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    session_manager.add_note("jira-note", "Test note")

    session_dir = config_loader.get_session_dir("jira-note")
    notes_file = session_dir / "notes.md"
    content = notes_file.read_text()

    assert "PROJ-12345" in content


def test_add_note_to_specific_session_in_group(temp_daf_home):
    """Test adding note to a session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session
    session_manager.create_session(
        name="multi-note",
        goal="Test session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Add note to session
    session_manager.add_note("multi-note", "Note for session")

    session_dir = config_loader.get_session_dir("multi-note")
    notes_file = session_dir / "notes.md"
    content = notes_file.read_text()

    # Note should be in file (no longer has session_id marker)
    assert "Note for session" in content
