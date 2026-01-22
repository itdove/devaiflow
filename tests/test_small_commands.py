"""Tests for small CLI commands: update, restore, export-md, summary."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from devflow.cli.commands.update_command import update_session
from devflow.cli.commands.restore_command import restore_backup
from devflow.cli.commands.export_md_command import export_markdown
from devflow.cli.commands.summary_command import show_summary
from devflow.config.models import Session


# ========== update_command tests ==========

def test_update_session_not_found(monkeypatch, temp_daf_home):
    """Test update_session with non-existent session."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    with patch('devflow.cli.commands.update_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.update_command.console') as mock_console:
            mock_sm_instance = MagicMock()
            mock_sm_instance.get_session.return_value = None
            mock_sm.return_value = mock_sm_instance

            update_session("nonexistent")

            # Verify error message
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("not found" in str(call).lower() for call in print_calls)


def test_update_session_with_id(monkeypatch, temp_daf_home):
    """Test update_session with provided session ID."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create real Session with conversation
    session = Session(
        name="test-session",
        issue_key="PROJ-123",
        goal="Test",
        status="created",
        created=datetime.now(),
        last_active=datetime.now()
    )
    session.add_conversation(
        working_dir="/test",
        ai_agent_session_id="old-uuid",
        project_path="/test/project",
        branch="main"
    )

    with patch('devflow.cli.commands.update_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.update_command.console') as mock_console:
            mock_sm_instance = MagicMock()
            mock_sm_instance.get_session.return_value = session
            mock_sm.return_value = mock_sm_instance

            update_session("test-session", ai_agent_session_id="new-uuid-123")

            # Verify session was updated
            mock_sm_instance.update_session.assert_called_once()
            assert session.status == "in_progress"
            assert session.active_conversation.ai_agent_session_id == "new-uuid-123"


def test_update_session_prompts_for_id(monkeypatch, temp_daf_home):
    """Test update_session prompts for ID when not provided."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create real Session with conversation
    session = Session(
        name="test-session",
        goal="Test",
        status="created",
        created=datetime.now(),
        last_active=datetime.now()
    )
    session.add_conversation(
        working_dir="/test",
        ai_agent_session_id="old-uuid",
        project_path="/test/project",
        branch="main"
    )

    with patch('devflow.cli.commands.update_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.update_command.Prompt.ask', return_value="prompted-uuid"):
            with patch('devflow.cli.commands.update_command.console'):
                mock_sm_instance = MagicMock()
                mock_sm_instance.get_session.return_value = session
                mock_sm.return_value = mock_sm_instance

                update_session("test-session")

                # Verify session was updated
                mock_sm_instance.update_session.assert_called_once()
                assert session.active_conversation.ai_agent_session_id == "prompted-uuid"


def test_update_session_empty_prompted_id(monkeypatch, temp_daf_home):
    """Test update_session when user provides empty ID."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create real Session with conversation
    session = Session(
        name="test-session",
        goal="Test",
        status="created",
        created=datetime.now(),
        last_active=datetime.now()
    )
    session.add_conversation(
        working_dir="/test",
        ai_agent_session_id="old-uuid",
        project_path="/test/project",
        branch="main"
    )

    with patch('devflow.cli.commands.update_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.update_command.Prompt.ask', return_value=""):
            with patch('devflow.cli.commands.update_command.console') as mock_console:
                mock_sm_instance = MagicMock()
                mock_sm_instance.get_session.return_value = session
                mock_sm.return_value = mock_sm_instance

                update_session("test-session")

                # Verify update was NOT called
                mock_sm_instance.update_session.assert_not_called()

                # Verify warning message
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                assert any("No session ID provided" in str(call) for call in print_calls)


# ========== restore_command tests ==========

def test_restore_backup_file_not_found(monkeypatch, temp_daf_home):
    """Test restore_backup with non-existent file."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    with patch('devflow.cli.commands.restore_command.console') as mock_console:
        restore_backup("/nonexistent/backup.zip")

        # Verify error message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("not found" in str(call).lower() for call in print_calls)


def test_restore_backup_merge_mode(monkeypatch, temp_daf_home, tmp_path):
    """Test restore_backup in merge mode."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    # Create fake backup file
    backup_file = tmp_path / "backup.zip"
    backup_file.write_text("fake backup")

    with patch('devflow.cli.commands.restore_command.BackupManager') as mock_bm:
        with patch('devflow.cli.commands.restore_command.console') as mock_console:
            mock_bm_instance = MagicMock()
            mock_bm.return_value = mock_bm_instance

            restore_backup(str(backup_file), merge=True, force=True)

            # Verify restore was called with merge=True
            mock_bm_instance.restore_backup.assert_called_once()
            call_args = mock_bm_instance.restore_backup.call_args
            assert call_args[1]['merge'] is True


def test_restore_backup_replace_mode(monkeypatch, temp_daf_home, tmp_path):
    """Test restore_backup in replace mode."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    backup_file = tmp_path / "backup.zip"
    backup_file.write_text("fake backup")

    with patch('devflow.cli.commands.restore_command.BackupManager') as mock_bm:
        with patch('devflow.cli.commands.restore_command.console'):
            mock_bm_instance = MagicMock()
            mock_bm.return_value = mock_bm_instance

            restore_backup(str(backup_file), merge=False, force=True)

            # Verify restore was called with merge=False
            call_args = mock_bm_instance.restore_backup.call_args
            assert call_args[1]['merge'] is False


def test_restore_backup_user_cancels(monkeypatch, temp_daf_home, tmp_path):
    """Test restore_backup when user cancels."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    backup_file = tmp_path / "backup.zip"
    backup_file.write_text("fake backup")

    with patch('devflow.cli.commands.restore_command.Confirm.ask', return_value=False):
        with patch('devflow.cli.commands.restore_command.BackupManager') as mock_bm:
            with patch('devflow.cli.commands.restore_command.console') as mock_console:
                mock_bm_instance = MagicMock()
                mock_bm.return_value = mock_bm_instance

                restore_backup(str(backup_file))

                # Verify restore was NOT called
                mock_bm_instance.restore_backup.assert_not_called()

                # Verify cancelled message
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                assert any("cancelled" in str(call).lower() for call in print_calls)


def test_restore_backup_handles_error(monkeypatch, temp_daf_home, tmp_path):
    """Test restore_backup handles errors gracefully."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    backup_file = tmp_path / "backup.zip"
    backup_file.write_text("fake backup")

    with patch('devflow.cli.commands.restore_command.BackupManager') as mock_bm:
        with patch('devflow.cli.commands.restore_command.console') as mock_console:
            mock_bm_instance = MagicMock()
            mock_bm_instance.restore_backup.side_effect = IOError("Corrupt backup")
            mock_bm.return_value = mock_bm_instance

            with pytest.raises(IOError):
                restore_backup(str(backup_file), force=True)

            # Verify error was printed
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("failed" in str(call).lower() for call in print_calls)


# ========== export_md_command tests ==========

def test_export_markdown_no_identifiers(monkeypatch, temp_daf_home):
    """Test export_markdown with no identifiers."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    with patch('devflow.cli.commands.export_md_command.console') as mock_console:
        export_markdown([])

        # Verify error message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Must specify at least one" in str(call) for call in print_calls)


def test_export_markdown_single_session(monkeypatch, temp_daf_home, tmp_path):
    """Test export_markdown for single session."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    output_file = tmp_path / "session.md"

    with patch('devflow.cli.commands.export_md_command.MarkdownExporter') as mock_exporter:
        with patch('devflow.cli.commands.export_md_command.console') as mock_console:
            mock_exp_instance = MagicMock()
            mock_exp_instance.export_sessions_to_markdown.return_value = [output_file]
            mock_exporter.return_value = mock_exp_instance

            # Create the file so stat() works
            output_file.write_text("# Session Export")

            export_markdown(["session-1"], output_dir=str(tmp_path))

            # Verify exporter was called
            mock_exp_instance.export_sessions_to_markdown.assert_called_once()

            # Verify success message
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("completed successfully" in str(call).lower() for call in print_calls)


def test_export_markdown_multiple_sessions(monkeypatch, temp_daf_home, tmp_path):
    """Test export_markdown for multiple sessions."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    files = [tmp_path / f"session-{i}.md" for i in range(3)]
    for f in files:
        f.write_text("# Export")

    with patch('devflow.cli.commands.export_md_command.MarkdownExporter') as mock_exporter:
        with patch('devflow.cli.commands.export_md_command.console') as mock_console:
            mock_exp_instance = MagicMock()
            mock_exp_instance.export_sessions_to_markdown.return_value = files
            mock_exporter.return_value = mock_exp_instance

            export_markdown(["s1", "s2", "s3"], output_dir=str(tmp_path))

            # Verify message shows count
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("3 session" in str(call) for call in print_calls)


def test_export_markdown_combined_mode(monkeypatch, temp_daf_home, tmp_path):
    """Test export_markdown in combined mode."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    output_file = tmp_path / "combined.md"
    output_file.write_text("# Combined")

    with patch('devflow.cli.commands.export_md_command.MarkdownExporter') as mock_exporter:
        with patch('devflow.cli.commands.export_md_command.console') as mock_console:
            mock_exp_instance = MagicMock()
            mock_exp_instance.export_sessions_to_markdown.return_value = [output_file]
            mock_exporter.return_value = mock_exp_instance

            export_markdown(["s1", "s2"], combined=True, output_dir=str(tmp_path))

            # Verify combined flag was passed
            call_args = mock_exp_instance.export_sessions_to_markdown.call_args
            assert call_args[1]['combined'] is True

            # Verify message mentions combined
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("combined" in str(call).lower() for call in print_calls)


def test_export_markdown_handles_error(monkeypatch, temp_daf_home):
    """Test export_markdown handles errors."""
    monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

    with patch('devflow.cli.commands.export_md_command.MarkdownExporter') as mock_exporter:
        with patch('devflow.cli.commands.export_md_command.console') as mock_console:
            mock_exp_instance = MagicMock()
            mock_exp_instance.export_sessions_to_markdown.side_effect = ValueError("Session not found")
            mock_exporter.return_value = mock_exp_instance

            export_markdown(["nonexistent"])

            # Verify error was printed
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("Export failed" in str(call) for call in print_calls)


# ========== summary_command tests ==========

def test_show_summary_no_sessions(monkeypatch, temp_daf_home):
    """Test show_summary with no sessions."""
    with patch('devflow.cli.commands.summary_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.summary_command.console') as mock_console:
            mock_sm_instance = MagicMock()
            mock_sm_instance.list_sessions.return_value = []
            mock_sm.return_value = mock_sm_instance

            show_summary(latest=True)

            # Verify error message
            print_calls = [str(call) for call in mock_console.print.call_args_list]
            assert any("No sessions found" in str(call) for call in print_calls)


def test_show_summary_with_identifier(monkeypatch, temp_daf_home):
    """Test show_summary with specific identifier."""
    # Create real Session without conversation (no ai_agent_session_id)
    session = Session(
        name="test-session",
        issue_key="PROJ-123",
        goal="Test",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now()
    )
    # Don't add conversation - test the no-conversation case

    with patch('devflow.cli.commands.summary_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.summary_command.get_session_with_prompt', return_value=session):
            with patch('devflow.cli.commands.summary_command.display_session_header'):
                with patch('devflow.cli.commands.summary_command.console') as mock_console:
                    with patch('devflow.cli.commands.summary_command.ConfigLoader'):
                        mock_sm_instance = MagicMock()
                        mock_sm.return_value = mock_sm_instance

                        show_summary("test-session")

                        # Verify warning about no session ID
                        print_calls = [str(call) for call in mock_console.print.call_args_list]
                        assert any("No Claude session ID" in str(call) for call in print_calls)


def test_show_summary_latest_flag(monkeypatch, temp_daf_home):
    """Test show_summary with --latest flag."""
    # Create real Session without conversation
    session = Session(
        name="latest-session",
        issue_key="PROJ-456",
        goal="Latest",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now()
    )
    # Don't add conversation - test the no-conversation case

    with patch('devflow.cli.commands.summary_command.SessionManager') as mock_sm:
        with patch('devflow.cli.commands.summary_command.get_session_with_prompt', return_value=session):
            with patch('devflow.cli.commands.summary_command.display_session_header'):
                with patch('devflow.cli.commands.summary_command.console') as mock_console:
                    with patch('devflow.cli.commands.summary_command.ConfigLoader'):
                        mock_sm_instance = MagicMock()
                        mock_sm_instance.list_sessions.return_value = [session]
                        mock_sm.return_value = mock_sm_instance

                        show_summary(latest=True)

                        # Verify it used the latest session
                        print_calls = [str(call) for call in mock_console.print.call_args_list]
                        assert any("Using session" in str(call) for call in print_calls)
