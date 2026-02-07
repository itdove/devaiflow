"""Tests for workspace utilities."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from devflow.utils.workspace_utils import ensure_workspace_skills_and_commands


class TestEnsureWorkspaceSkillsAndCommands:
    """Tests for ensure_workspace_skills_and_commands function."""

    def test_ensure_workspace_not_exists(self):
        """Test when workspace directory doesn't exist."""
        success, error = ensure_workspace_skills_and_commands("/nonexistent/path", quiet=True)

        assert success is False
        assert "does not exist" in error

    def test_ensure_workspace_success(self, tmp_path):
        """Test successful upgrade of workspace skills and commands."""
        # Create workspace directory
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch('devflow.utils.claude_commands.install_or_upgrade_commands') as mock_cmd:
            with patch('devflow.utils.claude_commands.install_or_upgrade_skills') as mock_skill:
                # Mock successful installation
                mock_cmd.return_value = (["cmd1"], [], [])  # changed, up_to_date, failed
                mock_skill.return_value = (["skill1"], [], [])

                success, error = ensure_workspace_skills_and_commands(str(workspace), quiet=True)

                assert success is True
                assert error is None
                mock_cmd.assert_called_once_with(str(workspace), dry_run=False, quiet=True)
                mock_skill.assert_called_once_with(str(workspace), dry_run=False, quiet=True)

    def test_ensure_workspace_with_failures(self, tmp_path):
        """Test when some installations fail."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch('devflow.utils.claude_commands.install_or_upgrade_commands') as mock_cmd:
            with patch('devflow.utils.claude_commands.install_or_upgrade_skills') as mock_skill:
                # Mock failed installation
                mock_cmd.return_value = ([], [], ["cmd1"])  # changed, up_to_date, failed
                mock_skill.return_value = ([], [], ["skill1"])

                success, error = ensure_workspace_skills_and_commands(str(workspace), quiet=True)

                assert success is False
                assert "Failed to install/upgrade" in error
                assert "cmd1" in error
                assert "skill1" in error

    def test_ensure_workspace_exception(self, tmp_path):
        """Test when an exception is raised during installation."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch('devflow.utils.claude_commands.install_or_upgrade_commands') as mock_cmd:
            # Mock exception
            mock_cmd.side_effect = Exception("Test error")

            success, error = ensure_workspace_skills_and_commands(str(workspace), quiet=True)

            assert success is False
            assert "Error installing skills/commands" in error
            assert "Test error" in error

    def test_ensure_workspace_quiet_mode(self, tmp_path):
        """Test quiet mode doesn't print output."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch('devflow.utils.claude_commands.install_or_upgrade_commands') as mock_cmd:
            with patch('devflow.utils.claude_commands.install_or_upgrade_skills') as mock_skill:
                with patch('devflow.utils.workspace_utils.console') as mock_console:
                    mock_cmd.return_value = (["cmd1"], [], [])
                    mock_skill.return_value = (["skill1"], [], [])

                    ensure_workspace_skills_and_commands(str(workspace), quiet=True)

                    # Console should not be called in quiet mode
                    mock_console.print.assert_not_called()

    def test_ensure_workspace_verbose_mode(self, tmp_path):
        """Test verbose mode prints output."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with patch('devflow.utils.claude_commands.install_or_upgrade_commands') as mock_cmd:
            with patch('devflow.utils.claude_commands.install_or_upgrade_skills') as mock_skill:
                with patch('devflow.utils.workspace_utils.console') as mock_console:
                    mock_cmd.return_value = (["cmd1"], [], [])
                    mock_skill.return_value = (["skill1"], [], [])

                    ensure_workspace_skills_and_commands(str(workspace), quiet=False)

                    # Console should be called in verbose mode
                    assert mock_console.print.call_count >= 2  # At least for commands and skills
