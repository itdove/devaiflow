"""Tests for daf backup command."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from devflow.cli.commands.backup_command import create_backup


def test_create_backup_default_output(monkeypatch, temp_daf_home):
    """Test create_backup with default output location."""
    mock_backup_file = MagicMock(spec=Path)
    mock_backup_file.stat.return_value.st_size = 5 * 1024 * 1024  # 5 MB

    with patch('devflow.cli.commands.backup_command.ConfigLoader'):
        with patch('devflow.cli.commands.backup_command.BackupManager') as mock_bm_class:
            with patch('devflow.cli.commands.backup_command.console') as mock_console:
                # Mock BackupManager instance
                mock_bm = MagicMock()
                mock_bm.create_backup.return_value = mock_backup_file
                mock_bm_class.return_value = mock_bm

                # Mock environment to allow command
                monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

                create_backup()

                # Verify BackupManager was called correctly
                mock_bm.create_backup.assert_called_once_with(None)

                # Verify console output
                assert mock_console.print.called


def test_create_backup_custom_output(monkeypatch, temp_daf_home):
    """Test create_backup with custom output path."""
    output_path = "/custom/path/backup.zip"
    mock_backup_file = MagicMock(spec=Path)
    mock_backup_file.stat.return_value.st_size = 10 * 1024 * 1024  # 10 MB

    with patch('devflow.cli.commands.backup_command.ConfigLoader'):
        with patch('devflow.cli.commands.backup_command.BackupManager') as mock_bm_class:
            with patch('devflow.cli.commands.backup_command.console') as mock_console:
                # Mock BackupManager instance
                mock_bm = MagicMock()
                mock_bm.create_backup.return_value = mock_backup_file
                mock_bm_class.return_value = mock_bm

                # Mock environment to allow command
                monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

                create_backup(output=output_path)

                # Verify BackupManager was called with custom path
                mock_bm.create_backup.assert_called_once_with(Path(output_path))


def test_create_backup_shows_size(monkeypatch, temp_daf_home):
    """Test create_backup displays backup size."""
    expected_size = 15.5 * 1024 * 1024  # 15.5 MB
    mock_backup_file = MagicMock(spec=Path)
    mock_backup_file.stat.return_value.st_size = expected_size

    with patch('devflow.cli.commands.backup_command.ConfigLoader'):
        with patch('devflow.cli.commands.backup_command.BackupManager') as mock_bm_class:
            with patch('devflow.cli.commands.backup_command.console') as mock_console:
                # Mock BackupManager instance
                mock_bm = MagicMock()
                mock_bm.create_backup.return_value = mock_backup_file
                mock_bm_class.return_value = mock_bm

                # Mock environment to allow command
                monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

                create_backup()

                # Check that size was printed
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                size_printed = any("15.50 MB" in str(call) for call in print_calls)
                assert size_printed, f"Expected size '15.50 MB' not found in: {print_calls}"


def test_create_backup_handles_error(monkeypatch, temp_daf_home):
    """Test create_backup handles errors gracefully."""
    with patch('devflow.cli.commands.backup_command.ConfigLoader'):
        with patch('devflow.cli.commands.backup_command.BackupManager') as mock_bm_class:
            with patch('devflow.cli.commands.backup_command.console') as mock_console:
                # Mock BackupManager to raise an error
                mock_bm = MagicMock()
                mock_bm.create_backup.side_effect = IOError("Permission denied")
                mock_bm_class.return_value = mock_bm

                # Mock environment to allow command
                monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

                # Verify error is raised
                with pytest.raises(IOError, match="Permission denied"):
                    create_backup()

                # Verify error message was printed
                assert mock_console.print.called
                error_printed = any("Backup failed" in str(call) for call in mock_console.print.call_args_list)
                assert error_printed


def test_create_backup_shows_warning_message(monkeypatch, temp_daf_home):
    """Test create_backup shows warning about using export for team handoff."""
    mock_backup_file = MagicMock(spec=Path)
    mock_backup_file.stat.return_value.st_size = 1024 * 1024  # 1 MB

    with patch('devflow.cli.commands.backup_command.ConfigLoader'):
        with patch('devflow.cli.commands.backup_command.BackupManager') as mock_bm_class:
            with patch('devflow.cli.commands.backup_command.console') as mock_console:
                # Mock BackupManager instance
                mock_bm = MagicMock()
                mock_bm.create_backup.return_value = mock_backup_file
                mock_bm_class.return_value = mock_bm

                # Mock environment to allow command
                monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

                create_backup()

                # Check that warning about daf export was shown
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                export_mentioned = any("daf export" in str(call) for call in print_calls)
                assert export_mentioned, "Expected warning about 'daf export' not found"


def test_create_backup_blocked_inside_claude(monkeypatch, temp_daf_home):
    """Test create_backup is blocked when running inside Claude Code."""
    # Set DEVAIFLOW_IN_SESSION to simulate running inside an AI agent session
    monkeypatch.setenv('DEVAIFLOW_IN_SESSION', '1')

    with patch('devflow.cli.commands.backup_command.BackupManager') as mock_bm_class:
        with patch('devflow.cli.commands.backup_command.console') as mock_console:
            # Mock BackupManager instance
            mock_bm = MagicMock()
            mock_bm_class.return_value = mock_bm

            # Should raise SystemExit due to @require_outside_claude decorator
            with pytest.raises(SystemExit):
                create_backup()

            # BackupManager.create_backup should NOT be called
            mock_bm.create_backup.assert_not_called()


def test_create_backup_success_message(monkeypatch, temp_daf_home):
    """Test create_backup shows success message and file location."""
    backup_path = "/tmp/my-backup-2024.zip"
    mock_backup_file = MagicMock(spec=Path)
    mock_backup_file.__str__ = lambda self: backup_path
    mock_backup_file.stat.return_value.st_size = 2.5 * 1024 * 1024  # 2.5 MB

    with patch('devflow.cli.commands.backup_command.ConfigLoader'):
        with patch('devflow.cli.commands.backup_command.BackupManager') as mock_bm_class:
            with patch('devflow.cli.commands.backup_command.console') as mock_console:
                # Mock BackupManager instance
                mock_bm = MagicMock()
                mock_bm.create_backup.return_value = mock_backup_file
                mock_bm_class.return_value = mock_bm

                # Mock environment to allow command
                monkeypatch.delenv('AI_AGENT_SESSION_ID', raising=False)

                create_backup()

                # Check for success message
                print_calls = [str(call) for call in mock_console.print.call_args_list]
                success_shown = any("successfully" in str(call).lower() for call in print_calls)
                assert success_shown, "Expected success message not found"
