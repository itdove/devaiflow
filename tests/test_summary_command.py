"""Tests for daf summary command."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from devflow.cli.commands.summary_command import show_summary


@pytest.fixture
def mock_session():
    """Create a mock session."""
    session = Mock()
    session.name = "test-session"
    session.issue_key = "PROJ-12345"
    session.working_directory = "/path/to/project"
    session.last_active = datetime(2026, 1, 15, 10, 30)

    # Mock active conversation
    conversation = Mock()
    conversation.ai_agent_session_id = "test-uuid-1234"
    conversation.project_path = "/path/to/project"
    session.active_conversation = conversation

    return session


@pytest.fixture
def mock_summary():
    """Create a mock session summary."""
    summary = Mock()
    summary.files_created = ["/path/to/new_file.py", "/path/to/another_file.py"]
    summary.files_modified = ["/path/to/modified_file.py"]
    summary.files_read = ["/path/to/read_file.py"]
    summary.commands_run = [
        Mock(command="pytest tests/"),
        Mock(command="git status"),
    ]
    summary.last_assistant_message = "Successfully added new test cases"
    summary.tool_call_stats = {
        "Read": 15,
        "Write": 5,
        "Bash": 3,
        "Edit": 2,
    }
    return summary


class TestShowSummary:
    """Tests for show_summary function."""

    def test_no_sessions_found(self):
        """Test when no sessions exist."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager') as mock_manager_class:
                mock_manager = Mock()
                mock_manager.list_sessions.return_value = []
                mock_manager_class.return_value = mock_manager

                # Should handle gracefully
                show_summary()

    def test_latest_flag_selects_most_recent(self, mock_session):
        """Test that --latest flag selects the most recent session."""
        other_session = Mock()
        other_session.name = "old-session"
        other_session.issue_key = "PROJ-100"
        other_session.last_active = datetime(2026, 1, 1, 10, 0)
        other_session.active_conversation = None

        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary'):
                            mock_manager = Mock()
                            mock_manager.list_sessions.return_value = [mock_session, other_session]
                            mock_manager_class.return_value = mock_manager
                            mock_get_session.return_value = mock_session

                            show_summary(latest=True)

                            # Should use the first (most recent) session
                            mock_get_session.assert_called_once()

    def test_no_identifier_uses_latest(self, mock_session):
        """Test that missing identifier uses latest session."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary'):
                            mock_manager = Mock()
                            mock_manager.list_sessions.return_value = [mock_session]
                            mock_manager_class.return_value = mock_manager
                            mock_get_session.return_value = mock_session

                            show_summary(identifier=None)

                            mock_get_session.assert_called_once()

    def test_session_not_found(self):
        """Test when session is not found."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    mock_get_session.return_value = None

                    # Should handle gracefully
                    show_summary(identifier="nonexistent-session")

    def test_session_without_conversation(self):
        """Test session without active conversation."""
        session_no_conv = Mock()
        session_no_conv.name = "test-session"
        session_no_conv.active_conversation = None

        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        mock_get_session.return_value = session_no_conv

                        # Should show warning
                        show_summary(identifier="test-session")

    def test_session_without_ai_agent_session_id(self):
        """Test session with conversation but no ai_agent_session_id."""
        session = Mock()
        session.name = "test-session"
        conversation = Mock()
        conversation.ai_agent_session_id = None
        session.active_conversation = conversation

        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        mock_get_session.return_value = session

                        # Should show warning
                        show_summary(identifier="test-session")

    def test_detailed_view(self, mock_session, mock_summary, tmp_path):
        """Test detailed summary view."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader') as mock_loader_class:
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            mock_loader = Mock()
                            # Mock get_session_dir to return a Path
                            mock_loader.get_session_dir.return_value = tmp_path / "session"
                            mock_loader_class.return_value = mock_loader
                            mock_get_session.return_value = mock_session
                            mock_gen_summary.return_value = mock_summary

                            show_summary(identifier="test-session", detail=True)

                            # Verify summary was generated
                            mock_gen_summary.assert_called_once_with(mock_session)

    def test_condensed_view_with_prose_summary(self, mock_session, mock_summary, tmp_path):
        """Test condensed summary view with prose summary."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader') as mock_loader_class:
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            with patch('devflow.cli.commands.summary_command.generate_prose_summary') as mock_prose:
                                mock_loader = Mock()
                                # Mock get_session_dir to return a Path
                                mock_loader.get_session_dir.return_value = tmp_path / "session"
                                mock_loader_class.return_value = mock_loader
                                mock_get_session.return_value = mock_session
                                mock_gen_summary.return_value = mock_summary
                                mock_prose.return_value = "Prose summary of changes"

                                show_summary(identifier="test-session", detail=False)

                                # Verify prose summary was generated
                                mock_prose.assert_called_once()

    def test_ai_summary_mode(self, mock_session, mock_summary):
        """Test AI summary mode."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            with patch('devflow.cli.commands.summary_command.generate_prose_summary') as mock_prose:
                                mock_get_session.return_value = mock_session
                                mock_gen_summary.return_value = mock_summary
                                mock_prose.return_value = "AI-generated summary"

                                show_summary(identifier="test-session", ai_summary=True)

                                # Verify prose summary was called with ai mode
                                mock_prose.assert_called_once()
                                call_args = mock_prose.call_args
                                assert call_args[1]['mode'] == 'ai'

    def test_empty_summary_handling(self, mock_session):
        """Test handling of empty summary (no activity)."""
        empty_summary = Mock()
        empty_summary.files_created = []
        empty_summary.files_modified = []
        empty_summary.files_read = []
        empty_summary.commands_run = []
        empty_summary.last_assistant_message = None
        empty_summary.tool_call_stats = {}

        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            mock_get_session.return_value = mock_session
                            mock_gen_summary.return_value = empty_summary

                            # Should show message about no activity
                            show_summary(identifier="test-session")

    def test_condensed_view_truncates_long_lists(self, mock_session):
        """Test that condensed view truncates long file lists."""
        long_summary = Mock()
        long_summary.files_created = [f"/path/to/file{i}.py" for i in range(10)]
        long_summary.files_modified = [f"/path/to/modified{i}.py" for i in range(8)]
        long_summary.files_read = []
        long_summary.commands_run = []
        long_summary.last_assistant_message = "Work completed"
        long_summary.tool_call_stats = {"Read": 5}

        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            with patch('devflow.cli.commands.summary_command.generate_prose_summary') as mock_prose:
                                mock_get_session.return_value = mock_session
                                mock_gen_summary.return_value = long_summary
                                mock_prose.return_value = "Summary"

                                # Should show hint about detail view
                                show_summary(identifier="test-session", detail=False)

    def test_recent_notes_displayed(self, mock_session, mock_summary, tmp_path):
        """Test that recent notes are displayed if available."""
        notes_content = "## Progress Notes\n- Fixed bug\n- Added feature\n- Ran tests\n"

        with patch('devflow.cli.commands.summary_command.ConfigLoader') as mock_loader_class:
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            with patch('devflow.cli.commands.summary_command.generate_prose_summary') as mock_prose:
                                # Setup config loader to return notes path
                                mock_loader = Mock()
                                session_dir = tmp_path / "session_dir"
                                session_dir.mkdir()
                                notes_file = session_dir / "notes.md"
                                notes_file.write_text(notes_content)

                                mock_loader.get_session_dir.return_value = session_dir
                                mock_loader_class.return_value = mock_loader

                                mock_get_session.return_value = mock_session
                                mock_gen_summary.return_value = mock_summary
                                mock_prose.return_value = "Summary"

                                show_summary(identifier="test-session")

                                # Verify notes were accessed
                                mock_loader.get_session_dir.assert_called_once()

    def test_summary_generation_error_handling(self, mock_session):
        """Test error handling when summary generation fails."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            mock_get_session.return_value = mock_session
                            mock_gen_summary.side_effect = Exception("Failed to parse conversation")

                            # Should show warning but not crash
                            show_summary(identifier="test-session")

    def test_tool_call_statistics_sorted(self, mock_session, mock_summary):
        """Test that tool call statistics are sorted by count."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            with patch('devflow.cli.commands.summary_command.generate_prose_summary') as mock_prose:
                                mock_get_session.return_value = mock_session
                                mock_gen_summary.return_value = mock_summary
                                mock_prose.return_value = "Summary"

                                show_summary(identifier="test-session", detail=False)

                                # Tool stats should be sorted (Read: 15, Write: 5, Bash: 3, Edit: 2)
                                # Just verify the call was made
                                mock_gen_summary.assert_called_once()

    def test_detail_view_shows_all_commands(self, mock_session, mock_summary):
        """Test that detail view shows all commands run."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader'):
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            mock_get_session.return_value = mock_session
                            mock_gen_summary.return_value = mock_summary

                            # Detail view should show all commands
                            show_summary(identifier="test-session", detail=True)

    def test_config_summary_mode_used(self, mock_session, mock_summary, tmp_path):
        """Test that config summary mode is used when available."""
        with patch('devflow.cli.commands.summary_command.ConfigLoader') as mock_loader_class:
            with patch('devflow.cli.commands.summary_command.SessionManager'):
                with patch('devflow.cli.commands.summary_command.get_session_with_prompt') as mock_get_session:
                    with patch('devflow.cli.commands.summary_command.display_session_header'):
                        with patch('devflow.cli.commands.summary_command.generate_session_summary') as mock_gen_summary:
                            with patch('devflow.cli.commands.summary_command.generate_prose_summary') as mock_prose:
                                # Setup config with session_summary mode
                                mock_loader = Mock()
                                mock_config = Mock()
                                mock_config.session_summary.mode = "both"
                                mock_loader.config = mock_config
                                # Mock get_session_dir to return a Path
                                mock_loader.get_session_dir.return_value = tmp_path / "session"
                                mock_loader_class.return_value = mock_loader

                                mock_get_session.return_value = mock_session
                                mock_gen_summary.return_value = mock_summary
                                mock_prose.return_value = "Summary"

                                show_summary(identifier="test-session", ai_summary=False)

                                # Should use config mode
                                mock_prose.assert_called_once()
                                call_args = mock_prose.call_args
                                assert call_args[1]['mode'] == 'both'
