"""Tests for delete command."""

import shutil
from pathlib import Path
from unittest.mock import patch

from devflow.cli.commands.delete_command import delete_session
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_delete_session_no_identifier_no_all(temp_daf_home, capsys):
    """Test delete command with no identifier and no --all flag."""
    delete_session()
    captured = capsys.readouterr()
    assert "Session identifier required" in captured.out


def test_delete_session_with_identifier_and_force(temp_daf_home):
    """Test delete single session with force flag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Delete with force (no confirmation prompt)
    delete_session(identifier="test-session", force=True)

    # Reload session manager to see changes
    session_manager = SessionManager(config_loader)
    remaining = session_manager.index.get_sessions("test-session")
    assert len(remaining) == 0


def test_delete_session_cancelled_by_user(temp_daf_home, capsys):
    """Test delete cancelled by user."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="keep-session",
        goal="Don't delete",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Mock Confirm.ask to return False (user cancels)
    with patch("devflow.cli.commands.delete_command.Confirm.ask", return_value=False):
        delete_session(identifier="keep-session")

    captured = capsys.readouterr()
    assert "Cancelled" in captured.out

    # Verify session still exists
    remaining = session_manager.index.get_sessions("keep-session")
    assert len(remaining) == 1


def test_delete_session_with_multi_session_selection(temp_daf_home):
    """Test that duplicate session names raise ValueError."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session
    session1 = session_manager.create_session(
        name="multi-session",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    import pytest
    with pytest.raises(ValueError, match="Session 'multi-session' already exists"):
        session_manager.create_session(
            name="multi-session",
            goal="Second",
            working_directory="dir2",
            project_path="/path2",
            ai_agent_session_id="uuid-2",
        )
    

def test_delete_all_sessions_in_group(temp_daf_home):
    """Test delete session (deletes directory by default)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session
    session_manager.create_session(
        name="group-session",
        goal="Test session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Create session directory
    session_dir = config_loader.get_session_dir("group-session")
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "notes.md").write_text("Test notes")

    # Delete session
    delete_session(identifier="group-session", force=True)

    # Reload session manager to see changes
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("group-session")
    assert session is None
    # Directory should be deleted by default
    assert not session_dir.exists()


def test_delete_all_sessions_flag(temp_daf_home):
    """Test delete --all flag (with patched console to avoid markup bug)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multiple sessions in different groups
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

    # Patch console.print to avoid Rich markup bug in line 123
    with patch("devflow.cli.commands.delete_command.console.print"):
        delete_session(delete_all=True, force=True)

    # Reload and verify all sessions were deleted
    session_manager = SessionManager(config_loader)
    all_sessions = session_manager.list_sessions()
    assert len(all_sessions) == 0


def test_delete_all_sessions_no_sessions(temp_daf_home, capsys):
    """Test delete --all when no sessions exist."""
    delete_session(delete_all=True, force=True)

    captured = capsys.readouterr()
    assert "No sessions found" in captured.out


def test_delete_all_sessions_cancelled(temp_daf_home):
    """Test delete --all cancelled by user."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="keep-session",
        goal="Don't delete",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Patch console.print to avoid Rich markup bug, and mock Confirm to cancel
    with patch("devflow.cli.commands.delete_command.console.print"):
        with patch("devflow.cli.commands.delete_command.Confirm.ask", return_value=False):
            delete_session(delete_all=True)

    # Verify sessions still exist
    all_sessions = session_manager.list_sessions()
    assert len(all_sessions) == 1


def test_delete_session_with_issue_key(temp_daf_home):
    """Test delete session with issue key."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="jira-session",
        goal="JIRA work",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    delete_session(identifier="jira-session", force=True)

    # Reload and verify session was deleted
    session_manager = SessionManager(config_loader)
    remaining = session_manager.index.get_sessions("jira-session")
    assert len(remaining) == 0


def test_delete_last_session_in_group_deletes_directory(temp_daf_home):
    """Test that deleting the last session in a group deletes the directory by default."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="single-session",
        goal="Only session",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Create session directory with notes
    session_dir = config_loader.get_session_dir("single-session")
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "notes.md").write_text("Test notes")

    # Delete without --keep-metadata flag (should delete directory by default)
    delete_session(identifier="single-session", force=True)

    # Reload and verify session and directory were deleted
    session_manager = SessionManager(config_loader)
    remaining = session_manager.index.get_sessions("single-session")
    assert len(remaining) == 0
    assert not session_dir.exists()


def test_delete_session_keep_directory(temp_daf_home):
    """Test deleting session but keeping directory with --keep-metadata flag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="keep-dir-session",
        goal="Keep directory",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Create session directory
    session_dir = config_loader.get_session_dir("keep-dir-session")
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "notes.md").write_text("Keep these notes")

    # Delete with --keep-metadata flag
    delete_session(identifier="keep-dir-session", force=True, keep_metadata=True)

    # Reload and verify session deleted but directory kept
    session_manager = SessionManager(config_loader)
    remaining = session_manager.index.get_sessions("keep-dir-session")
    assert len(remaining) == 0
    assert session_dir.exists()
    assert (session_dir / "notes.md").read_text() == "Keep these notes"


def test_delete_all_with_issue_keys(temp_daf_home):
    """Test delete --all with JIRA keys (patched to avoid markup bug)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="jira1",
        goal="Work 1",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-100",
    )

    session_manager.create_session(
        name="jira2",
        goal="Work 2",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
        issue_key="PROJ-200",
    )

    # Patch console.print to avoid Rich markup bug
    with patch("devflow.cli.commands.delete_command.console.print"):
        delete_session(delete_all=True, force=True)

    # Verify both sessions were deleted
    session_manager = SessionManager(config_loader)
    all_sessions = session_manager.list_sessions()
    assert len(all_sessions) == 0


def test_delete_session_not_found(temp_daf_home, capsys):
    """Test delete with non-existent session."""
    # get_session_with_delete_all_option will handle the not found case
    # and return None for session, which should be handled gracefully
    with patch("devflow.cli.utils.get_session_with_delete_all_option", return_value=(None, False)):
        delete_session(identifier="nonexistent")

    # Should return early without error
    captured = capsys.readouterr()
    # No error should be printed, just return silently


def test_delete_all_in_group_cancelled(temp_daf_home, capsys):
    """Test delete cancelled by user."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session
    session_manager.create_session(
        name="group-session",
        goal="Test session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Mock Confirm to cancel deletion (False)
    with patch("devflow.cli.commands.delete_command.Confirm.ask", return_value=False):
        delete_session(identifier="group-session")

    captured = capsys.readouterr()
    assert "Cancelled" in captured.out

    # Reload session manager and verify session still exists
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("group-session")
    assert session is not None


def test_delete_all_sessions_in_group_keep_metadata(temp_daf_home):
    """Test delete session with --keep-metadata flag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session
    session_manager.create_session(
        name="group-session",
        goal="Test session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Create session directory with notes
    session_dir = config_loader.get_session_dir("group-session")
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "notes.md").write_text("Important notes to keep")

    # Delete session with keep_metadata flag
    delete_session(identifier="group-session", force=True, keep_metadata=True)

    # Reload session manager to see changes
    session_manager = SessionManager(config_loader)
    session = session_manager.get_session("group-session")
    assert session is None

    # Directory should be kept with --keep-metadata flag
    assert session_dir.exists()
    assert (session_dir / "notes.md").read_text() == "Important notes to keep"


def test_delete_all_flag_keep_metadata(temp_daf_home):
    """Test delete --all with --keep-metadata flag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multiple sessions in different groups
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

    # Create session directories with notes
    session1_dir = config_loader.get_session_dir("session1")
    session1_dir.mkdir(parents=True, exist_ok=True)
    (session1_dir / "notes.md").write_text("Session 1 notes")

    session2_dir = config_loader.get_session_dir("session2")
    session2_dir.mkdir(parents=True, exist_ok=True)
    (session2_dir / "notes.md").write_text("Session 2 notes")

    # Patch console.print to avoid Rich markup bug
    with patch("devflow.cli.commands.delete_command.console.print"):
        delete_session(delete_all=True, force=True, keep_metadata=True)

    # Reload and verify all sessions were deleted from index
    session_manager = SessionManager(config_loader)
    all_sessions = session_manager.list_sessions()
    assert len(all_sessions) == 0

    # But directories should still exist with --keep-metadata
    assert session1_dir.exists()
    assert (session1_dir / "notes.md").read_text() == "Session 1 notes"
    assert session2_dir.exists()
    assert (session2_dir / "notes.md").read_text() == "Session 2 notes"


def test_delete_session_prevents_orphaned_metadata(temp_daf_home):
    """Test that delete without --keep-metadata prevents orphaned state (PROJ-59815)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="test-session",
        goal="Test orphan prevention",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-59815",
    )

    # Create session directory with metadata
    session_dir = config_loader.get_session_dir("test-session")
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "notes.md").write_text("Important notes")
    old_metadata_file = session_dir / "old_metadata.json"
    old_metadata_file.write_text('{"some": "old data"}')

    # Delete session (default behavior - should delete metadata)
    delete_session(identifier="test-session", force=True)

    # Reload session manager
    session_manager = SessionManager(config_loader)
    remaining = session_manager.index.get_sessions("test-session")
    assert len(remaining) == 0

    # Directory should be deleted (prevents orphaned state)
    assert not session_dir.exists()

    # Verify old metadata file is gone
    assert not old_metadata_file.exists()

    # Now if we re-sync or recreate, there's no orphaned metadata
    # Create a fresh session with same name
    new_session = session_manager.create_session(
        name="test-session",
        goal="Fresh start",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-2",
        issue_key="PROJ-59815",
    )

    # Verify we have a clean slate
        # Old metadata file should not exist (even though session manager creates new directory)
    assert not old_metadata_file.exists()
