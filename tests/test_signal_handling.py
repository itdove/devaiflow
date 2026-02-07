"""Tests for signal handling when exiting Claude Code via /exit.

This module tests the fix for PROJ-60618:
- Session status not updated to 'paused' when exiting Claude Code via /exit

The fix includes:
1. Explicit file flushing (f.flush() and os.fsync()) to prevent data loss on signal
2. Enhanced logging in signal handlers for debugging
3. Proper error handling and exception reporting
"""

import os
import signal
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.cli.signal_handler import _cleanup_on_signal, setup_signal_handlers
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_signal_handler_updates_session_status(temp_daf_home, monkeypatch):
    """Test that signal handler properly updates session status to 'paused'.

    This is the primary test for PROJ-60618. It verifies that when a SIGTERM
    signal is received (when user types /exit in Claude Code), the session
    status is correctly updated to 'paused' and persisted to disk.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a test session
    session = session_manager.create_session(
        name="test-signal-session",
        goal="Test signal handling",
        working_directory="test-repo",
        project_path="/tmp/test-repo",
        ai_agent_session_id="test-uuid-signal",
    )

    # Set session to in_progress (simulating an active session)
    session.status = "in_progress"
    session_manager.update_session(session)

    # Set up signal handlers (as done in commands)
    setup_signal_handlers(session, session_manager, "test-signal-session", None)

    # Mock _prompt_for_complete_on_exit to avoid user interaction
    with patch('devflow.cli.commands.open_command._prompt_for_complete_on_exit'):
        # Mock _cleanup_temp_directory_on_exit
        with patch('devflow.cli.commands.open_command._cleanup_temp_directory_on_exit'):
            # Mock sys.exit to prevent actual exit
            with patch('sys.exit'):
                # Trigger the signal handler
                try:
                    _cleanup_on_signal(signal.SIGTERM, None)
                except SystemExit:
                    pass  # Expected

    # Reload session from disk to verify persistence
    fresh_session = session_manager.get_session("test-signal-session")

    # Verify session status was updated to 'paused'
    assert fresh_session.status == "paused", \
        f"Expected session status to be 'paused', got '{fresh_session.status}'"


def test_signal_handler_ends_work_session(temp_daf_home, monkeypatch):
    """Test that signal handler properly ends the work session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a test session
    session = session_manager.create_session(
        name="test-work-session",
        goal="Test work session tracking",
        working_directory="test-repo",
        project_path="/tmp/test-repo",
        ai_agent_session_id="test-uuid-work",
    )

    # Start a work session
    session_manager.start_work_session("test-work-session")

    # Set up signal handlers
    setup_signal_handlers(session, session_manager, "test-work-session", None)

    # Mock _prompt_for_complete_on_exit to avoid user interaction
    with patch('devflow.cli.commands.open_command._prompt_for_complete_on_exit'):
        with patch('devflow.cli.commands.open_command._cleanup_temp_directory_on_exit'):
            with patch('sys.exit'):
                try:
                    _cleanup_on_signal(signal.SIGTERM, None)
                except SystemExit:
                    pass

    # Reload session from disk
    fresh_session = session_manager.get_session("test-work-session")

    # Verify work session was ended
    assert fresh_session.time_tracking_state == "paused", \
        "Work session should be paused after signal handler"


def test_signal_handler_sets_cleanup_done_flag(temp_daf_home):
    """Test that signal handler sets the _cleanup_done flag to prevent duplicate cleanup."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-cleanup-flag",
        goal="Test cleanup flag",
        working_directory="test-repo",
        project_path="/tmp/test-repo",
        ai_agent_session_id="test-uuid-flag",
    )

    # Set up signal handlers
    setup_signal_handlers(session, session_manager, "test-cleanup-flag", None)

    # Mock dependencies
    with patch('devflow.cli.commands.open_command._prompt_for_complete_on_exit'):
        with patch('devflow.cli.commands.open_command._cleanup_temp_directory_on_exit'):
            with patch('sys.exit'):
                try:
                    _cleanup_on_signal(signal.SIGTERM, None)
                except SystemExit:
                    pass

    # Verify cleanup_done flag was set
    from devflow.cli.signal_handler import is_cleanup_done
    assert is_cleanup_done() is True, \
        "_cleanup_done flag should be True after signal handler completes"


def test_signal_handler_handles_errors_gracefully(temp_daf_home, monkeypatch, capsys):
    """Test that signal handler handles errors gracefully and logs them."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-error-handling",
        goal="Test error handling",
        working_directory="test-repo",
        project_path="/tmp/test-repo",
        ai_agent_session_id="test-uuid-error",
    )

    # Set up signal handlers
    setup_signal_handlers(session, session_manager, "test-error-handling", None)

    # Mock update_session to raise an exception
    def mock_update_error(session):
        raise RuntimeError("Simulated update error")

    # Patch update_session to raise error
    with patch.object(session_manager, 'update_session', side_effect=mock_update_error):
        with patch('sys.exit'):
            try:
                _cleanup_on_signal(signal.SIGTERM, None)
            except SystemExit:
                pass

    # Capture output to verify error was reported
    captured = capsys.readouterr()

    # Verify error message is displayed
    assert "Error during cleanup" in captured.out or "Error during cleanup" in str(captured)


def test_new_command_signal_handler_updates_session(temp_daf_home):
    """Test that new_command signal handler also updates session status properly."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-new-signal",
        goal="Test new command signal",
        working_directory="test-repo",
        project_path="/tmp/test-repo",
        ai_agent_session_id="test-uuid-new",
    )

    session.status = "in_progress"
    session_manager.update_session(session)

    # Set up signal handlers (unified for all commands now)
    setup_signal_handlers(session, session_manager, "test-new-signal", None)

    # Mock dependencies
    with patch('devflow.cli.commands.open_command._prompt_for_complete_on_exit'):
        with patch('sys.exit'):
            try:
                _cleanup_on_signal(signal.SIGTERM, None)
            except SystemExit:
                pass

    # Reload session from disk
    fresh_session = session_manager.get_session("test-new-signal")

    # Verify status was updated
    assert fresh_session.status == "paused", \
        f"Expected session status to be 'paused', got '{fresh_session.status}'"


def test_file_flush_and_fsync_on_save(temp_daf_home):
    """Test that session saves include explicit flush and fsync calls.

    This test verifies the fix for the race condition where sys.exit(0)
    might terminate the process before file buffers are flushed to disk.

    We verify this by checking the actual code has the flush and fsync calls.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-flush",
        goal="Test file flush",
        working_directory="test-repo",
        project_path="/tmp/test-repo",
        ai_agent_session_id="test-uuid-flush",
    )

    # Update session status - this should trigger file writes with flush/fsync
    session.status = "paused"
    session_manager.update_session(session)

    # Reload session from disk to verify it was persisted correctly
    fresh_session = session_manager.get_session("test-flush")

    # Verify the session was properly saved and can be reloaded
    assert fresh_session is not None, "Session should be persisted to disk"
    assert fresh_session.status == "paused", "Session status should be persisted"

    # Verify the code has the correct fix by checking the source
    # Storage abstraction moved implementation to FileBackend
    from devflow.storage import file_backend as file_backend_module
    import inspect

    # Check that FileBackend.save_index has flush and fsync calls
    save_index_source = inspect.getsource(file_backend_module.FileBackend.save_index)
    assert "flush()" in save_index_source, "FileBackend.save_index should call flush()"
    assert "fsync" in save_index_source, "FileBackend.save_index should call os.fsync()"

    # Check that FileBackend.save_session_metadata has flush and fsync calls
    save_metadata_source = inspect.getsource(file_backend_module.FileBackend.save_session_metadata)
    assert "flush()" in save_metadata_source, "FileBackend.save_session_metadata should call flush()"
    assert "fsync" in save_metadata_source, "FileBackend.save_session_metadata should call os.fsync()"


def test_signal_handler_cleanup_temp_directory(temp_daf_home):
    """Test that signal handler cleans up temporary directory for ticket_creation sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="test-signal-cleanup-")

    # Create a session with temp directory
    session = session_manager.create_session(
        name="test-temp-cleanup",
        goal="Test temp cleanup",
        working_directory="test-repo",
        project_path=temp_dir,
        ai_agent_session_id="test-uuid-temp",
    )

    # Set session_type and temp_directory metadata
    session.session_type = "ticket_creation"
    if session.active_conversation:
        session.active_conversation.temp_directory = temp_dir
        session_manager.update_session(session)

    # Verify temp directory exists
    assert Path(temp_dir).exists(), "Temp directory should exist before cleanup"

    # Set up signal handlers
    setup_signal_handlers(session, session_manager, "test-temp-cleanup", None)

    # Mock dependencies
    with patch('devflow.cli.commands.open_command._prompt_for_complete_on_exit'):
        with patch('sys.exit'):
            try:
                _cleanup_on_signal(signal.SIGTERM, None)
            except SystemExit:
                pass

    # Verify temp directory was cleaned up
    assert not Path(temp_dir).exists(), "Temp directory should be removed after cleanup"


def test_signal_handler_logging(temp_daf_home, monkeypatch):
    """Test that signal handler logs debugging information."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-logging",
        goal="Test logging",
        working_directory="test-repo",
        project_path="/tmp/test-repo",
        ai_agent_session_id="test-uuid-log",
    )

    # Set up signal handlers
    setup_signal_handlers(session, session_manager, "test-logging", None)

    # Track log calls
    log_messages = []

    def mock_log_error(message):
        log_messages.append(message)

    # Mock _log_error function
    with patch('devflow.cli.signal_handler._log_error', side_effect=mock_log_error):
        with patch('devflow.cli.commands.open_command._prompt_for_complete_on_exit'):
            with patch('devflow.cli.commands.open_command._cleanup_temp_directory_on_exit'):
                with patch('sys.exit'):
                    try:
                        _cleanup_on_signal(signal.SIGTERM, None)
                    except SystemExit:
                        pass

    # Verify logging occurred
    assert len(log_messages) >= 2, "Should log at least 2 messages (start and complete)"
    assert any("Updating session" in msg for msg in log_messages), \
        "Should log session update start"
    assert any("Session update completed" in msg for msg in log_messages), \
        "Should log session update completion"
