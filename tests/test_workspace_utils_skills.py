"""Tests for devflow/utils/workspace_utils.py - workspace skills management."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from devflow.utils.workspace_utils import ensure_workspace_skills_and_commands


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def test_ensure_workspace_skills_success(temp_workspace):
    """Test successful installation of workspace skills."""
    with patch('devflow.utils.claude_commands.install_or_upgrade_slash_commands') as mock_slash:
        with patch('devflow.utils.claude_commands.install_or_upgrade_reference_skills') as mock_ref:
            # Mock successful installation
            mock_slash.return_value = (["daf-help", "daf-list"], ["daf-active"], [])
            mock_ref.return_value = (["daf-cli"], [], [])

            success, error = ensure_workspace_skills_and_commands(str(temp_workspace), quiet=True)

            assert success is True
            assert error is None
            mock_slash.assert_called_once_with(dry_run=False, quiet=True)
            mock_ref.assert_called_once_with(dry_run=False, quiet=True)


def test_ensure_workspace_skills_nonexistent_workspace(tmp_path):
    """Test with non-existent workspace directory."""
    nonexistent = tmp_path / "nonexistent"

    success, error = ensure_workspace_skills_and_commands(str(nonexistent), quiet=True)

    assert success is False
    assert "does not exist" in error.lower()


def test_ensure_workspace_skills_with_failures(temp_workspace):
    """Test handling of installation failures."""
    with patch('devflow.utils.claude_commands.install_or_upgrade_slash_commands') as mock_slash:
        with patch('devflow.utils.claude_commands.install_or_upgrade_reference_skills') as mock_ref:
            # Mock partial failure
            mock_slash.return_value = (["daf-help"], ["daf-list"], ["daf-broken"])
            mock_ref.return_value = ([], [], ["daf-cli-broken"])

            success, error = ensure_workspace_skills_and_commands(str(temp_workspace), quiet=True)

            assert success is False
            assert "Failed to install/upgrade" in error
            assert "daf-broken" in error
            assert "daf-cli-broken" in error


def test_ensure_workspace_skills_quiet_mode(temp_workspace, capsys):
    """Test quiet mode suppresses output."""
    with patch('devflow.utils.claude_commands.install_or_upgrade_slash_commands') as mock_slash:
        with patch('devflow.utils.claude_commands.install_or_upgrade_reference_skills') as mock_ref:
            mock_slash.return_value = (["daf-help"], [], [])
            mock_ref.return_value = (["daf-cli"], [], [])

            ensure_workspace_skills_and_commands(str(temp_workspace), quiet=True)

            captured = capsys.readouterr()
            # Should not print anything in quiet mode
            assert captured.out == ""


def test_ensure_workspace_skills_verbose_mode(temp_workspace, capsys):
    """Test verbose mode shows installation progress."""
    with patch('devflow.utils.claude_commands.install_or_upgrade_slash_commands') as mock_slash:
        with patch('devflow.utils.claude_commands.install_or_upgrade_reference_skills') as mock_ref:
            with patch('devflow.utils.workspace_utils.console') as mock_console:
                mock_slash.return_value = (["daf-help", "daf-list"], [], [])
                mock_ref.return_value = (["daf-cli"], [], [])

                ensure_workspace_skills_and_commands(str(temp_workspace), quiet=False)

                # Should print progress message
                mock_console.print.assert_called()
                call_args = str(mock_console.print.call_args)
                assert "Installed/upgraded" in call_args


def test_ensure_workspace_skills_all_up_to_date(temp_workspace):
    """Test when all skills are already up-to-date."""
    with patch('devflow.utils.claude_commands.install_or_upgrade_slash_commands') as mock_slash:
        with patch('devflow.utils.claude_commands.install_or_upgrade_reference_skills') as mock_ref:
            # Mock all up-to-date
            mock_slash.return_value = ([], ["daf-help", "daf-list"], [])
            mock_ref.return_value = ([], ["daf-cli"], [])

            success, error = ensure_workspace_skills_and_commands(str(temp_workspace), quiet=True)

            assert success is True
            assert error is None


def test_ensure_workspace_skills_exception_handling(temp_workspace):
    """Test handling of unexpected exceptions."""
    with patch('devflow.utils.claude_commands.install_or_upgrade_slash_commands', side_effect=Exception("Unexpected error")):
        success, error = ensure_workspace_skills_and_commands(str(temp_workspace), quiet=True)

        assert success is False
        assert "Error installing skills" in error
        assert "Unexpected error" in error


def test_ensure_workspace_skills_with_tilde_path(tmp_path, monkeypatch):
    """Test with ~ in workspace path."""
    # Mock home directory
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))

    with patch('devflow.utils.claude_commands.install_or_upgrade_slash_commands') as mock_slash:
        with patch('devflow.utils.claude_commands.install_or_upgrade_reference_skills') as mock_ref:
            mock_slash.return_value = ([], [], [])
            mock_ref.return_value = ([], [], [])

            success, error = ensure_workspace_skills_and_commands("~/workspace", quiet=True)

            assert success is True
            assert error is None


def test_ensure_workspace_skills_slash_command_failures_only(temp_workspace):
    """Test when only slash commands fail."""
    with patch('devflow.utils.claude_commands.install_or_upgrade_slash_commands') as mock_slash:
        with patch('devflow.utils.claude_commands.install_or_upgrade_reference_skills') as mock_ref:
            mock_slash.return_value = ([], [], ["daf-failed"])
            mock_ref.return_value = (["daf-cli"], [], [])

            success, error = ensure_workspace_skills_and_commands(str(temp_workspace), quiet=True)

            assert success is False
            assert "daf-failed" in error


def test_ensure_workspace_skills_reference_failures_only(temp_workspace):
    """Test when only reference skills fail."""
    with patch('devflow.utils.claude_commands.install_or_upgrade_slash_commands') as mock_slash:
        with patch('devflow.utils.claude_commands.install_or_upgrade_reference_skills') as mock_ref:
            mock_slash.return_value = (["daf-help"], [], [])
            mock_ref.return_value = ([], [], ["daf-cli-failed"])

            success, error = ensure_workspace_skills_and_commands(str(temp_workspace), quiet=True)

            assert success is False
            assert "daf-cli-failed" in error
