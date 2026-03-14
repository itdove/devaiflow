"""Tests for smart sync mode detection (itdove/devaiflow#147).

Tests that daf sync automatically determines what to sync based on parameters.
These tests focus on the CLI integration rather than internal function calls.
"""

from unittest.mock import Mock, patch, MagicMock

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli


def test_sync_with_workspace_filter_skips_jira(temp_daf_home):
    """Test: daf sync -w workspace → sync workspace only (skip JIRA)."""
    runner = CliRunner()

    # Initialize config
    with patch("rich.prompt.Confirm.ask", side_effect=[False, False]):
        runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Mock JIRA client to verify it's NOT called
    with patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira:
        with patch("devflow.cli.commands.sync_command.scan_workspace_for_repositories", return_value=[]):
            with patch("devflow.cli.commands.sync_command.sync_github_repository", return_value={'created_count': 0, 'updated_count': 0}):
                result = runner.invoke(cli, ["sync", "-w", "primary"])

                # Verify JIRA client was NOT instantiated
                mock_jira.assert_not_called()


def test_sync_with_repository_filter_skips_jira(temp_daf_home):
    """Test: daf sync --repository → sync repository only (skip JIRA)."""
    runner = CliRunner()

    # Initialize config
    with patch("rich.prompt.Confirm.ask", side_effect=[False, False]):
        runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Mock JIRA client to verify it's NOT called
    with patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira:
        with patch("devflow.cli.commands.sync_command.sync_github_repository", return_value={'created_count': 0, 'updated_count': 0}):
            result = runner.invoke(cli, ["sync", "--repository", "owner/repo1"])

            # Verify JIRA client was NOT instantiated
            mock_jira.assert_not_called()


