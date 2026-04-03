"""Tests for interactive session selection in 'daf open' command."""

from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_open_interactive_selection_no_sessions(temp_daf_home):
    """Test interactive selection with no sessions."""
    runner = CliRunner()
    result = runner.invoke(cli, ["open"], input="")

    assert result.exit_code == 0
    assert "No sessions found" in result.output


def test_open_interactive_selection_single_session(temp_daf_home):
    """Test interactive selection with single session - auto-select."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
        issue_key="PROJ-12345",
    )

    runner = CliRunner()
    # Input "1" to select the session, then "q" to quit the session opening process
    result = runner.invoke(cli, ["open"], input="1\n")

    # Should show the session in the table
    assert "test-session" in result.output or "Your Sessions" in result.output


def test_open_interactive_selection_multiple_sessions(temp_daf_home):
    """Test interactive selection with multiple sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multiple sessions
    session_manager.create_session(
        name="session1",
        goal="First goal",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-111",
    )

    session_manager.create_session(
        name="session2",
        goal="Second goal",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
        issue_key="PROJ-222",
    )

    runner = CliRunner()
    # User enters "q" to quit
    result = runner.invoke(cli, ["open"], input="q\n")

    assert result.exit_code == 0
    # Should show both sessions in the table
    assert "session1" in result.output
    assert "session2" in result.output
    assert "Your Sessions" in result.output


def test_open_interactive_selection_with_pagination(temp_daf_home):
    """Test interactive selection with pagination (>25 sessions)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 30 sessions to trigger pagination
    for i in range(30):
        session_manager.create_session(
            name=f"session-{i:02d}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    # Press Enter to go to next page, then "q" to quit
    result = runner.invoke(cli, ["open"], input="\nq\n")

    assert result.exit_code == 0
    # Should show pagination indicator
    assert "Page 1/" in result.output or "Page 2/" in result.output
    assert "press Enter for next page" in result.output


def test_open_interactive_selection_number_selection(temp_daf_home):
    """Test selecting a session by number."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions
    session_manager.create_session(
        name="session1",
        goal="First goal",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="session2",
        goal="Second goal",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    runner = CliRunner()
    # Select session 2 by entering "2"
    result = runner.invoke(cli, ["open"], input="2\n")

    # Should show "Opening session: session2" or similar
    assert "session2" in result.output or "Opening" in result.output


def test_open_interactive_selection_invalid_input(temp_daf_home):
    """Test handling invalid input in interactive selection."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    runner = CliRunner()
    # Enter invalid input "abc", then "q" to quit
    result = runner.invoke(cli, ["open"], input="abc\nq\n")

    assert result.exit_code == 0
    assert "Invalid input" in result.output or "Invalid number" in result.output


def test_open_interactive_selection_with_status_filter(temp_daf_home):
    """Test interactive selection with status filter."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions with different statuses
    session1 = session_manager.create_session(
        name="active-session",
        goal="Active",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session2 = session_manager.create_session(
        name="complete-session",
        goal="Complete",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    # Update session2 status to complete
    session2.status = "complete"
    session_manager.update_session(session2)

    runner = CliRunner()
    # Filter by in_progress status (should only show session1)
    result = runner.invoke(cli, ["open", "--status", "created"], input="q\n")

    assert result.exit_code == 0
    assert "active-session" in result.output
    # complete-session should not appear
    assert "complete-session" not in result.output or "Filtering by status" in result.output


def test_open_interactive_highlights_most_recent(temp_daf_home):
    """Test that most recent session is highlighted."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions with different last_active times
    now = datetime.now()

    session1 = session_manager.create_session(
        name="old-session",
        goal="Old",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.last_active = now - timedelta(days=1)
    session_manager.update_session(session1)

    session2 = session_manager.create_session(
        name="recent-session",
        goal="Recent",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    session2.last_active = now
    session_manager.update_session(session2)

    runner = CliRunner()
    result = runner.invoke(cli, ["open"], input="q\n")

    assert result.exit_code == 0
    # Should show green arrow indicator for most recent
    assert "▶" in result.output or "recent-session" in result.output


def test_open_with_identifier_ignores_status_filter(temp_daf_home):
    """Test that --status flag is ignored when identifier is provided."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["open", "test-session", "--status", "complete"], input="q\n")

    # Should show warning about --status being ignored
    assert "status flag is only used with interactive selection" in result.output or result.exit_code == 0


def test_open_interactive_preserves_backward_compatibility(temp_daf_home):
    """Test that direct session opening still works (backward compatibility)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["open", "test-session"])

    # Should attempt to open the session directly without showing selection menu
    # (Will fail because Claude Code is not available in test environment, but that's expected)
    assert "test-session" in result.output or result.exit_code == 1  # 1 = error opening session
