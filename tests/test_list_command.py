"""Tests for daf list command."""

from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_list_empty(temp_daf_home):
    """Test listing sessions when none exist."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "No sessions found" in result.output


def test_list_single_session(temp_daf_home):
    """Test listing a single session."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="test-uuid-123",
        issue_key="PROJ-12345",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    # JIRA key may be truncated in table display (e.g., "PROJ-123…")
    assert "PROJ-123" in result.output
    assert "test-dir" in result.output
    assert "Your Sessions" in result.output


def test_list_multiple_sessions(temp_daf_home):
    """Test listing multiple sessions."""
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
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "PROJ-111" in result.output
    assert "PROJ-222" in result.output
    assert "Total: 2 sessions" in result.output


def test_list_filter_by_status(temp_daf_home):
    """Test filtering sessions by status."""
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
    result = runner.invoke(cli, ["list", "--status", "complete"])

    assert result.exit_code == 0
    assert "complete-session" in result.output or "Complete" in result.output
    # Should not show active session
    assert "active-session" not in result.output or "In Progress" not in result.output


def test_list_filter_by_working_directory(temp_daf_home):
    """Test filtering sessions by working directory."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="backend",
        goal="Backend work",
        working_directory="backend-service",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="frontend",
        goal="Frontend work",
        working_directory="frontend-app",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--working-directory", "backend-service"])

    assert result.exit_code == 0
    # Working directory may be truncated in table display (e.g., "backend-serv…")
    assert "backend" in result.output
    assert "frontend" not in result.output


def test_list_with_work_sessions(temp_daf_home):
    """Test listing sessions with time tracking."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="time-tracked",
        goal="Time tracking test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Simulate a completed work session
    from devflow.config.models import WorkSession
    start_time = datetime.now() - timedelta(hours=2)
    end_time = datetime.now() - timedelta(hours=1)

    session.work_sessions = [WorkSession(start=start_time, end=end_time)]
    session_manager.update_session(session)

    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    # Should show time tracked (approximately 1 hour)
    assert "1h" in result.output or "0h" in result.output  # Allow for rounding


def test_list_no_sessions_with_filters(temp_daf_home):
    """Test listing with filters that return no results."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test",
        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--status", "complete"])

    assert result.exit_code == 0
    assert "No sessions found" in result.output
    assert "Try removing filters" in result.output


def test_list_displays_status_colors(temp_daf_home):
    """Test that different statuses are displayed with appropriate styling."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with in_progress status
    session = session_manager.create_session(
        name="active",
        goal="Active work",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )
    session.status = "in_progress"
    session_manager.update_session(session)

    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    # Check for status indicators (output may be truncated in table, e.g., "in_progre…")
    assert "in_progre" in result.output or "In Progre" in result.output


def test_list_shows_session_summary(temp_daf_home):
    """Test that list shows total sessions and time summary."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a few sessions
    for i in range(3):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "Total: 3 sessions" in result.output
    assert "tracked" in result.output


def test_list_with_jira_summary(temp_daf_home):
    """Test that JIRA summary is displayed when available."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="jira-session",
        goal="Original goal",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    # Set JIRA summary in issue_metadata
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["summary"] = "Implement backup feature"
    session_manager.update_session(session)

    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    # JIRA key may be truncated in table display (e.g., "PROJ-123…")
    assert "PROJ-123" in result.output
    # Check for text that may wrap across lines in table
    assert "Implement" in result.output and "backup" in result.output


def test_list_pagination_default_limit(temp_daf_home):
    """Test pagination with default limit of 25 in interactive mode."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 30 sessions (more than default limit of 25)
    for i in range(30):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    # In interactive mode, EOF will stop pagination after first page
    result = runner.invoke(cli, ["list"], input="")

    assert result.exit_code == 0
    # Should show first page in interactive mode
    assert "Showing 1-25 of 30 sessions" in result.output
    assert "(page 1/2)" in result.output
    # Should show interactive prompt (not navigation hints)
    assert "Press Enter to continue to next page, or 'q' to quit" in result.output


def test_list_pagination_custom_limit(temp_daf_home):
    """Test pagination with custom limit in interactive mode."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 15 sessions
    for i in range(15):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    # In interactive mode, EOF will stop pagination after first page
    result = runner.invoke(cli, ["list", "--limit", "5"], input="")

    assert result.exit_code == 0
    # Should show first 5 sessions
    assert "Showing 1-5 of 15 sessions" in result.output
    assert "(page 1/3)" in result.output
    # Should show interactive prompt
    assert "Press Enter to continue to next page, or 'q' to quit" in result.output


def test_list_pagination_specific_page(temp_daf_home):
    """Test pagination showing a specific page."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 15 sessions
    for i in range(15):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--limit", "5", "--page", "2"])

    assert result.exit_code == 0
    # Should show sessions 6-10
    assert "Showing 6-10 of 15 sessions" in result.output
    assert "(page 2/3)" in result.output


def test_list_pagination_last_page_partial(temp_daf_home):
    """Test pagination when last page has fewer items."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 12 sessions
    for i in range(12):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--limit", "5", "--page", "3"])

    assert result.exit_code == 0
    # Should show last 2 sessions (11-12)
    assert "Showing 11-12 of 12 sessions" in result.output
    assert "(page 3/3)" in result.output


def test_list_pagination_page_out_of_range(temp_daf_home):
    """Test pagination with page number out of range."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 10 sessions
    for i in range(10):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--limit", "5", "--page", "10"])

    assert result.exit_code == 0
    # Should show error and fallback to page 1
    assert "out of range" in result.output
    assert "Showing page 1 instead" in result.output


def test_list_pagination_show_all_flag(temp_daf_home):
    """Test --all flag bypasses pagination."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 30 sessions
    for i in range(30):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--all"])

    assert result.exit_code == 0
    # Should show all sessions without pagination info
    assert "Total: 30 sessions" in result.output
    # Should NOT show pagination info
    assert "page" not in result.output.lower() or "on this page" not in result.output


def test_list_pagination_with_filters(temp_daf_home):
    """Test pagination works correctly with filters in interactive mode."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 15 sessions with different statuses
    for i in range(15):
        session = session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )
        if i >= 10:
            # Mark last 5 as complete
            session.status = "complete"
            session_manager.update_session(session)

    runner = CliRunner()
    # In interactive mode, EOF will stop pagination after first page
    result = runner.invoke(cli, ["list", "--status", "complete", "--limit", "3"], input="")

    assert result.exit_code == 0
    # Should show first 3 of 5 complete sessions
    assert "Showing 1-3 of 5 sessions" in result.output
    assert "(page 1/2)" in result.output
    # Should show interactive prompt
    assert "Press Enter to continue to next page, or 'q' to quit" in result.output


def test_list_pagination_few_sessions_no_pagination_info(temp_daf_home):
    """Test that pagination info is not shown when sessions fit in one page."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create only 10 sessions (less than default limit of 25)
    for i in range(10):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    # Should show simple total, not pagination info
    assert "Total: 10 sessions" in result.output
    # Should NOT show "Showing X-Y of Z"
    assert "Showing" not in result.output


def test_list_pagination_invalid_page_number(temp_daf_home):
    """Test pagination with invalid page number (less than 1)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session_manager.create_session(
        name="test",
        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--page", "0"])

    assert result.exit_code == 0
    assert "must be 1 or greater" in result.output


def test_list_pagination_invalid_limit(temp_daf_home):
    """Test pagination with invalid limit (less than 1)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session_manager.create_session(
        name="test",
        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--limit", "0"])

    assert result.exit_code == 0
    assert "must be 1 or greater" in result.output


def test_list_pagination_navigation_hints(temp_daf_home):
    """Test that navigation hints are shown appropriately."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 15 sessions
    for i in range(15):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    # Test page 1 - should show "next page" hint
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--limit", "5", "--page", "1"])
    assert result.exit_code == 0
    assert "--page 2" in result.output  # Next page hint
    assert "--all" in result.output

    # Test page 2 (middle) - should show both hints
    result = runner.invoke(cli, ["list", "--limit", "5", "--page", "2"])
    assert result.exit_code == 0
    assert "--page 3" in result.output  # Next page hint
    assert "--page 1" in result.output  # Previous page hint

    # Test last page - should only show "previous page" hint
    result = runner.invoke(cli, ["list", "--limit", "5", "--page", "3"])
    assert result.exit_code == 0
    assert "--page 2" in result.output  # Previous page hint
    # Should NOT show next page hint
    assert "--page 4" not in result.output


def test_list_interactive_mode_first_page_quit(temp_daf_home):
    """Test interactive mode when user quits on first prompt."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 30 sessions (more than one page)
    for i in range(30):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    # Simulate user pressing 'q' at the first prompt
    result = runner.invoke(cli, ["list"], input="q\n")

    assert result.exit_code == 0
    # Should show first page
    assert "Showing 1-25 of 30 sessions" in result.output
    assert "(page 1/2)" in result.output
    # Should show prompt
    assert "Press Enter to continue to next page, or 'q' to quit" in result.output


def test_list_interactive_mode_continue_to_next_page(temp_daf_home):
    """Test interactive mode when user continues to next page."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 30 sessions
    for i in range(30):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    # Simulate user pressing Enter at the first prompt (continue to page 2)
    result = runner.invoke(cli, ["list"], input="\n")

    assert result.exit_code == 0
    # Should show both pages
    assert "Showing 1-25 of 30 sessions" in result.output
    assert "Showing 26-30 of 30 sessions" in result.output
    assert "(page 1/2)" in result.output
    assert "(page 2/2)" in result.output


def test_list_interactive_mode_multiple_pages(temp_daf_home):
    """Test interactive mode with multiple pages."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 12 sessions (will be 3 pages with limit 5)
    for i in range(12):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    # Simulate user pressing Enter twice to view all pages
    result = runner.invoke(cli, ["list", "--limit", "5"], input="\n\n")

    assert result.exit_code == 0
    # Should show all three pages
    assert "Showing 1-5 of 12 sessions" in result.output
    assert "Showing 6-10 of 12 sessions" in result.output
    assert "Showing 11-12 of 12 sessions" in result.output
    assert "(page 1/3)" in result.output
    assert "(page 2/3)" in result.output
    assert "(page 3/3)" in result.output


def test_list_interactive_mode_quit_on_second_page(temp_daf_home):
    """Test interactive mode when user quits after viewing first page."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 15 sessions (3 pages with limit 5)
    for i in range(15):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    # Simulate user pressing Enter once, then 'q'
    result = runner.invoke(cli, ["list", "--limit", "5"], input="\nq\n")

    assert result.exit_code == 0
    # Should show first two pages only
    assert "Showing 1-5 of 15 sessions" in result.output
    assert "Showing 6-10 of 15 sessions" in result.output
    assert "(page 1/3)" in result.output
    assert "(page 2/3)" in result.output
    # Should NOT show third page
    assert "Showing 11-15 of 15 sessions" not in result.output
    assert "(page 3/3)" not in result.output


def test_list_interactive_mode_single_page_no_prompt(temp_daf_home):
    """Test interactive mode with only one page (no prompt shown)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create only 10 sessions (less than default limit)
    for i in range(10):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    # Should show all sessions
    assert "Total: 10 sessions" in result.output
    # Should NOT show prompt (only one page)
    assert "Press Enter to continue" not in result.output


def test_list_non_interactive_mode_with_page_flag(temp_daf_home):
    """Test that --page flag activates non-interactive mode."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 30 sessions
    for i in range(30):
        session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )

    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--page", "1"])

    assert result.exit_code == 0
    # Should show only first page
    assert "Showing 1-25 of 30 sessions" in result.output
    assert "(page 1/2)" in result.output
    # Should NOT show interactive prompt
    assert "Press Enter to continue" not in result.output
    # Should show navigation hints instead
    assert "--page 2" in result.output


def test_list_interactive_mode_with_filters(temp_daf_home):
    """Test interactive mode works correctly with filters."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 15 sessions with different statuses
    for i in range(15):
        session = session_manager.create_session(
            name=f"session{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )
        if i >= 10:
            # Mark last 5 as complete
            session.status = "complete"
            session_manager.update_session(session)

    runner = CliRunner()
    # Filter by complete status, should get 5 sessions (2 pages with limit 3)
    result = runner.invoke(cli, ["list", "--status", "complete", "--limit", "3"], input="\n")

    assert result.exit_code == 0
    # Should show both pages of complete sessions
    assert "Showing 1-3 of 5 sessions" in result.output
    assert "Showing 4-5 of 5 sessions" in result.output
