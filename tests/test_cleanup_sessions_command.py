"""Tests for daf cleanup-sessions command."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from devflow.cli.commands.cleanup_sessions_command import cleanup_sessions
from devflow.config.models import Session


def test_cleanup_sessions_no_sessions(monkeypatch, temp_daf_home):
    """Test cleanup_sessions with no sessions."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    with patch('devflow.cli.commands.cleanup_sessions_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.cleanup_sessions_command.console') as mock_console:
            # Mock empty session list
            mock_sm_instance = MagicMock()
            mock_sm_instance.list_sessions.return_value = []
            mock_sm.return_value = mock_sm_instance

            cleanup_sessions()

            # Verify message printed
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            no_sessions_shown = any("No sessions found" in str(call) for call in print_calls)
            assert no_sessions_shown


def test_cleanup_sessions_no_orphaned(monkeypatch, temp_daf_home):
    """Test cleanup_sessions with valid sessions (no orphans)."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create test session with conversation
    session = Session(
        name="valid-session",
        issue_key="PROJ-123",
        goal="Test",
        working_directory="/test",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now()
    )
    session.add_conversation(
        working_dir="/test",
        ai_agent_session_id="valid-uuid",
        project_path="/test/project",
        branch="main"
    )

    with patch('devflow.cli.commands.cleanup_sessions_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.cleanup_sessions_command.SessionCapture') as mock_capture:
            with patch('devflow.cli.commands.cleanup_sessions_command.console') as mock_console:
                # Mock SessionManager
                mock_sm_instance = MagicMock()
                mock_sm_instance.list_sessions.return_value = [session]
                mock_sm.return_value = mock_sm_instance

                # Mock SessionCapture - session exists (not orphaned)
                mock_capture_instance = MagicMock()
                mock_capture_instance.session_exists.return_value = True
                mock_capture.return_value = mock_capture_instance

                cleanup_sessions()

                # Verify no orphans message
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                no_orphans_shown = any("No orphaned sessions found" in str(call) for call in print_calls)
                assert no_orphans_shown


def test_cleanup_sessions_found_orphaned_dry_run(monkeypatch, temp_daf_home):
    """Test cleanup_sessions finds orphaned session in dry run mode."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create orphaned session
    session = Session(
        name="orphaned-session",
        issue_key="PROJ-456",
        goal="Test",
        working_directory="/test",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now()
    )
    session.add_conversation(
        working_dir="/test",
        ai_agent_session_id="orphaned-uuid",
        project_path="/test/project",
        branch="main"
    )

    with patch('devflow.cli.commands.cleanup_sessions_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.cleanup_sessions_command.SessionCapture') as mock_capture:
            with patch('devflow.cli.commands.cleanup_sessions_command.console') as mock_console:
                # Mock SessionManager
                mock_sm_instance = MagicMock()
                mock_sm_instance.list_sessions.return_value = [session]
                mock_sm.return_value = mock_sm_instance

                # Mock SessionCapture - session doesn't exist (orphaned)
                mock_capture_instance = MagicMock()
                mock_capture_instance.session_exists.return_value = False
                mock_capture.return_value = mock_capture_instance

                cleanup_sessions(dry_run=True)

                # Verify dry run message
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                dry_run_shown = any("DRY RUN" in str(call) for call in print_calls)
                assert dry_run_shown

                # Verify found orphaned session
                orphaned_shown = any("Found 1 orphaned" in str(call) for call in print_calls)
                assert orphaned_shown

                # Verify update was NOT called in dry run
                mock_sm_instance.update_session.assert_not_called()


def test_cleanup_sessions_cleans_with_force(monkeypatch, temp_daf_home):
    """Test cleanup_sessions cleans orphaned sessions with force flag."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create orphaned session
    session = Session(
        name="orphaned-session",
        issue_key="PROJ-789",
        goal="Test",
        working_directory="/test",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now()
    )
    session.add_conversation(
        working_dir="/test",
        ai_agent_session_id="orphaned-uuid-123",
        project_path="/test/project",
        branch="main"
    )

    with patch('devflow.cli.commands.cleanup_sessions_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.cleanup_sessions_command.SessionCapture') as mock_capture:
            with patch('devflow.cli.commands.cleanup_sessions_command.console') as mock_console:
                # Mock SessionManager
                mock_sm_instance = MagicMock()
                mock_sm_instance.list_sessions.return_value = [session]
                mock_sm.return_value = mock_sm_instance

                # Mock SessionCapture - session doesn't exist (orphaned)
                mock_capture_instance = MagicMock()
                mock_capture_instance.session_exists.return_value = False
                mock_capture.return_value = mock_capture_instance

                cleanup_sessions(force=True)

                # Verify found orphaned session
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                found_orphaned = any("Found 1 orphaned" in str(call) for call in print_calls)
                assert found_orphaned, f"Expected 'Found 1 orphaned' not in: {print_calls}"

                # Verify cleanup process started
                cleaning_shown = any("Cleaning up orphaned" in str(call) for call in print_calls)
                assert cleaning_shown, f"Expected 'Cleaning up orphaned' not in: {print_calls}"


def test_cleanup_sessions_user_cancels(monkeypatch, temp_daf_home):
    """Test cleanup_sessions when user cancels confirmation."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create orphaned session
    session = Session(
        name="orphaned-session",
        issue_key="PROJ-111",
        goal="Test",
        working_directory="/test",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now()
    )
    session.add_conversation(
        working_dir="/test",
        ai_agent_session_id="orphaned-uuid-456",
        project_path="/test/project",
        branch="main"
    )

    with patch('devflow.cli.commands.cleanup_sessions_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.cleanup_sessions_command.SessionCapture') as mock_capture:
            with patch('devflow.cli.commands.cleanup_sessions_command.Confirm.ask', return_value=False):
                with patch('devflow.cli.commands.cleanup_sessions_command.console') as mock_console:
                    # Mock SessionManager
                    mock_sm_instance = MagicMock()
                    mock_sm_instance.list_sessions.return_value = [session]
                    mock_sm.return_value = mock_sm_instance

                    # Mock SessionCapture - session doesn't exist (orphaned)
                    mock_capture_instance = MagicMock()
                    mock_capture_instance.session_exists.return_value = False
                    mock_capture.return_value = mock_capture_instance

                    cleanup_sessions(force=False)

                    # Verify cancelled message
                    print_calls = [str(call) for call in mock_console.print.call_args_list]
                    cancelled_shown = any("Cancelled" in str(call) for call in print_calls)
                    assert cancelled_shown

                    # Verify update was NOT called
                    mock_sm_instance.update_session.assert_not_called()


def test_cleanup_sessions_handles_update_error(monkeypatch, temp_daf_home):
    """Test cleanup_sessions handles errors during update."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create orphaned session
    session = Session(
        name="orphaned-session",
        issue_key="PROJ-222",
        goal="Test",
        working_directory="/test",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now()
    )
    session.add_conversation(
        working_dir="/test",
        ai_agent_session_id="orphaned-uuid-789",
        project_path="/test/project",
        branch="main"
    )

    with patch('devflow.cli.commands.cleanup_sessions_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.cleanup_sessions_command.SessionCapture') as mock_capture:
            with patch('devflow.cli.commands.cleanup_sessions_command.console') as mock_console:
                # Mock SessionManager with error on update
                mock_sm_instance = MagicMock()
                mock_sm_instance.list_sessions.return_value = [session]
                mock_sm_instance.update_session.side_effect = Exception("Database error")
                mock_sm.return_value = mock_sm_instance

                # Mock SessionCapture - session doesn't exist (orphaned)
                mock_capture_instance = MagicMock()
                mock_capture_instance.session_exists.return_value = False
                mock_capture.return_value = mock_capture_instance

                cleanup_sessions(force=True)

                # Verify error was printed
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                error_shown = any("Failed to clean" in str(call) for call in print_calls)
                assert error_shown


def test_cleanup_sessions_skips_sessions_without_conversation(monkeypatch, temp_daf_home):
    """Test cleanup_sessions skips sessions without active conversation."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create session without conversation
    session = Session(
        name="no-conversation-session",
        issue_key="PROJ-333",
        goal="Test",
        working_directory="/test",
        status="created",
        created=datetime.now(),
        last_active=datetime.now()
    )
    # Don't add conversation

    with patch('devflow.cli.commands.cleanup_sessions_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.cleanup_sessions_command.SessionCapture') as mock_capture:
            with patch('devflow.cli.commands.cleanup_sessions_command.console') as mock_console:
                # Mock SessionManager
                mock_sm_instance = MagicMock()
                mock_sm_instance.list_sessions.return_value = [session]
                mock_sm.return_value = mock_sm_instance

                # Mock SessionCapture
                mock_capture_instance = MagicMock()
                mock_capture.return_value = mock_capture_instance

                cleanup_sessions()

                # Verify session_exists was NOT called (session skipped)
                mock_capture_instance.session_exists.assert_not_called()

                # Verify no orphans message
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                no_orphans_shown = any("No orphaned sessions found" in str(call) for call in print_calls)
                assert no_orphans_shown


def test_cleanup_sessions_blocked_inside_claude(monkeypatch, temp_daf_home):
    """Test cleanup_sessions is blocked when running inside Claude Code."""
    # Set DEVAIFLOW_IN_SESSION to simulate running inside an AI agent session
    monkeypatch.setenv('DEVAIFLOW_IN_SESSION', '1')

    with patch('devflow.cli.commands.cleanup_sessions_command.SessionManager') as mock_sm:
        # Should raise SystemExit due to @require_outside_claude decorator
        with pytest.raises(SystemExit):
            cleanup_sessions()

        # SessionManager should not be instantiated
        mock_sm.assert_not_called()
