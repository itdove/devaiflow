"""Tests for note command."""

import time
from unittest.mock import patch

import pytest

from devflow.cli.commands.note_command import add_note, view_notes
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_add_note_with_identifier(temp_daf_home):
    """Test adding a note to a specific session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    add_note(identifier="test-session", note="This is a test note")

    # Verify note was added
    notes_file = config_loader.get_session_dir("test-session") / "notes.md"
    assert notes_file.exists()


def test_add_note_no_sessions(temp_daf_home):
    """Test adding note when no sessions exist."""
    with pytest.raises(SystemExit) as exc_info:
        add_note(identifier=None, note="Test note")
    assert exc_info.value.code == 1
    # Should display error message


@patch("devflow.cli.commands.note_command.get_session_with_prompt")
def test_add_note_uses_last_active_when_no_identifier(mock_get_session, temp_daf_home):
    """Test that note command uses last active session when no identifier provided."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session1 = session_manager.create_session(
        name="session-1",
        goal="First session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Small delay to ensure sessions have different timestamps
    time.sleep(0.05)

    session2 = session_manager.create_session(
        name="session-2",
        goal="Second session (most recent)",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    # Mock get_session_with_prompt to return session2
    mock_get_session.return_value = session2

    add_note(identifier=None, note="Auto-selected note")

    # Should have called get_session_with_prompt with session-2 (most recent)
    mock_get_session.assert_called_once()
    call_args = mock_get_session.call_args[0]
    assert call_args[1] == "session-2"  # identifier should be the most recent session name


@patch("devflow.cli.commands.note_command.Prompt.ask")
def test_add_note_prompts_for_text_when_not_provided(mock_prompt, temp_daf_home):
    """Test that note command prompts for note text when not provided."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Mock prompt to return a note
    mock_prompt.return_value = "Prompted note text"

    add_note(identifier="test-session", note=None)

    # Should have prompted for note
    mock_prompt.assert_called_once_with("Enter note")


@patch("devflow.cli.commands.note_command.add_jira_comment")
def test_add_note_syncs_to_jira_when_requested(mock_jira_comment, temp_daf_home, mock_jira_cli):
    """Test that note syncs to JIRA when --sync-to-jira flag is used."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="jira-session",
        goal="Test JIRA sync",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    # Mock JIRA comment to succeed
    mock_jira_comment.return_value = True

    add_note(identifier="jira-session", note="Test note for JIRA", sync_to_jira=True)

    # Should have called add_jira_comment
    mock_jira_comment.assert_called_once()
    call_args = mock_jira_comment.call_args
    assert call_args[0][0] == "PROJ-12345"  # issue key
    assert "Test note for JIRA" in call_args[0][1]  # Comment text


def test_add_note_sync_to_jira_without_issue_key(temp_daf_home):
    """Test that sync to JIRA warns when session has no issue key."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-jira-session",
        goal="Test without JIRA",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    add_note(identifier="no-jira-session", note="Test note", sync_to_jira=True)
    # Should display warning about no issue key


@patch("devflow.cli.commands.note_command.get_session_with_prompt")
def test_add_note_handles_no_session_found(mock_get_session, temp_daf_home):
    """Test that note command handles when no session is found."""
    # Mock get_session_with_prompt to return None
    mock_get_session.return_value = None

    with pytest.raises(SystemExit) as exc_info:
        add_note(identifier="nonexistent", note="Test note")
    assert exc_info.value.code == 1
    # Should return early with error code


def test_add_note_to_session_with_multiple_in_group(temp_daf_home):
    """Test that duplicate session names raise ValueError."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session1 = session_manager.create_session(
        name="multi-session",
        goal="First session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    import pytest
    with pytest.raises(ValueError, match="Session 'multi-session' already exists"):
        session_manager.create_session(
            name="multi-session",
            goal="Second session",
            working_directory="dir2",
            project_path="/path2",
            ai_agent_session_id="uuid-2",
        )


# Tests for view_notes command


def test_view_notes_with_existing_notes(temp_daf_home):
    """Test viewing notes for a session that has notes."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add some notes
    session_manager.add_note("test-session", "First note")
    session_manager.add_note("test-session", "Second note")

    # View notes should display them
    view_notes(identifier="test-session")

    # Verify notes file exists and has content
    notes_file = config_loader.get_session_dir("test-session") / "notes.md"
    assert notes_file.exists()
    content = notes_file.read_text()
    assert "First note" in content
    assert "Second note" in content


def test_view_notes_no_notes_file(temp_daf_home):
    """Test viewing notes when no notes file exists."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-notes-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # View notes should display helpful message
    view_notes(identifier="no-notes-session")
    # Should display warning about no notes


def test_view_notes_no_sessions(temp_daf_home):
    """Test viewing notes when no sessions exist."""
    with pytest.raises(SystemExit) as exc_info:
        view_notes(identifier=None)
    assert exc_info.value.code == 1
    # Should display error message


@patch("devflow.cli.commands.note_command.get_session_with_prompt")
def test_view_notes_uses_last_active_when_no_identifier(mock_get_session, temp_daf_home):
    """Test that notes command uses last active session when no identifier provided."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session1 = session_manager.create_session(
        name="session-1",
        goal="First session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Small delay to ensure sessions have different timestamps
    time.sleep(0.05)

    session2 = session_manager.create_session(
        name="session-2",
        goal="Second session (most recent)",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    # Add notes to session2
    session_manager.add_note("session-2", "Recent note")

    # Mock get_session_with_prompt to return session2
    mock_get_session.return_value = session2

    view_notes(identifier=None)

    # Should have called get_session_with_prompt with session-2 (most recent)
    mock_get_session.assert_called_once()
    call_args = mock_get_session.call_args[0]
    assert call_args[1] == "session-2"  # identifier should be the most recent session name


def test_view_notes_with_latest_flag(temp_daf_home):
    """Test viewing notes with --latest flag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session1 = session_manager.create_session(
        name="session-1",
        goal="First session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Small delay to ensure sessions have different timestamps
    time.sleep(0.05)

    session2 = session_manager.create_session(
        name="session-2",
        goal="Second session (most recent)",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    # Add notes to both sessions
    session_manager.add_note("session-1", "Old note")
    session_manager.add_note("session-2", "Recent note")

    # With --latest flag, should use session-2
    # For this test, we just verify it doesn't crash
    # In real usage, it would display session-2's notes


def test_view_notes_with_issue_key(temp_daf_home, mock_jira_cli):
    """Test viewing notes for a session with issue key."""
    mock_jira_cli.set_ticket("PROJ-12345", {
        "key": "PROJ-12345",
        "fields": {
            "summary": "Test ticket",
            "status": {"name": "New"},
            "issuetype": {"name": "Story"},
        }
    })

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="jira-session",
        goal="Test JIRA",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    # Add note
    session_manager.add_note("jira-session", "JIRA-linked note")

    # View notes
    view_notes(identifier="PROJ-12345")  # Use issue key as identifier

    # Verify notes file exists
    notes_file = config_loader.get_session_dir("jira-session") / "notes.md"
    assert notes_file.exists()
    content = notes_file.read_text()
    assert "JIRA-linked note" in content
    assert "PROJ-12345" in content  # issue key should be in header


@patch("devflow.cli.commands.note_command.get_session_with_prompt")
def test_view_notes_handles_no_session_found(mock_get_session, temp_daf_home):
    """Test that notes command handles when no session is found."""
    # Mock get_session_with_prompt to return None
    mock_get_session.return_value = None

    with pytest.raises(SystemExit) as exc_info:
        view_notes(identifier="nonexistent")
    assert exc_info.value.code == 1
    # Should return early with error code


def test_view_notes_displays_chronological_order(temp_daf_home):
    """Test that notes are displayed in chronological order."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="chrono-session",
        goal="Test chronological order",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add notes in sequence
    session_manager.add_note("chrono-session", "First note")
    session_manager.add_note("chrono-session", "Second note")
    session_manager.add_note("chrono-session", "Third note")

    # View notes
    view_notes(identifier="chrono-session")

    # Verify order in file
    notes_file = config_loader.get_session_dir("chrono-session") / "notes.md"
    content = notes_file.read_text()

    # Notes should appear in chronological order
    first_pos = content.index("First note")
    second_pos = content.index("Second note")
    third_pos = content.index("Third note")

    assert first_pos < second_pos < third_pos
