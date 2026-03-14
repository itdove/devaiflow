"""Tests for smart sync mode detection (itdove/devaiflow#147).

Tests that daf sync automatically determines what to sync based on parameters.
"""

from unittest.mock import Mock, patch, MagicMock

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli


def test_sync_multi_backend_jira_only_mode(temp_daf_home, monkeypatch):
    """Test sync_multi_backend with sync_jira=True, sync_workspaces=False."""
    from devflow.cli.commands.sync_command import sync_multi_backend

    # Mock JIRA client and workspace scanning
    with patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira:
        with patch("devflow.cli.commands.sync_command.scan_workspace_for_repositories") as mock_scan:
            # Configure mock JIRA client
            mock_jira_instance = MagicMock()
            mock_jira_instance.list_tickets.return_value = []
            mock_jira.return_value = mock_jira_instance

            # Call with sync_jira=True, sync_workspaces=False
            sync_multi_backend(
                sync_jira=True,
                sync_workspaces=False,
                output_json=False
            )

            # Verify JIRA client was called
            mock_jira.assert_called_once()

            # Verify workspace scanning was NOT called
            mock_scan.assert_not_called()


def test_sync_multi_backend_workspace_only_mode(temp_daf_home):
    """Test sync_multi_backend with sync_jira=False, sync_workspaces=True."""
    from devflow.cli.commands.sync_command import sync_multi_backend

    # Mock JIRA client and workspace scanning
    with patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira:
        with patch("devflow.cli.commands.sync_command.scan_workspace_for_repositories") as mock_scan:
            with patch("devflow.cli.commands.sync_command.sync_github_repository", return_value={'created_count': 0, 'updated_count': 0}):
                mock_scan.return_value = []

                # Call with sync_jira=False, sync_workspaces=True
                sync_multi_backend(
                    sync_jira=False,
                    sync_workspaces=True,
                    output_json=False
                )

                # Verify JIRA client was NOT called
                mock_jira.assert_not_called()

                # Verify workspace scanning WAS called
                mock_scan.assert_called()


def test_sync_multi_backend_both_modes(temp_daf_home):
    """Test sync_multi_backend with sync_jira=True, sync_workspaces=True."""
    from devflow.cli.commands.sync_command import sync_multi_backend

    # Mock JIRA client and workspace scanning
    with patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira:
        with patch("devflow.cli.commands.sync_command.scan_workspace_for_repositories") as mock_scan:
            with patch("devflow.cli.commands.sync_command.sync_github_repository", return_value={'created_count': 0, 'updated_count': 0}):
                # Configure mock JIRA client
                mock_jira_instance = MagicMock()
                mock_jira_instance.list_tickets.return_value = []
                mock_jira.return_value = mock_jira_instance
                mock_scan.return_value = []

                # Call with both sync_jira=True and sync_workspaces=True
                sync_multi_backend(
                    sync_jira=True,
                    sync_workspaces=True,
                    output_json=False
                )

                # Verify both JIRA and workspace scanning were called
                mock_jira.assert_called_once()
                mock_scan.assert_called()


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


def test_sync_with_jira_filters_but_no_jira_url_errors(temp_daf_home, monkeypatch):
    """Test: daf sync --type without JIRA URL → error."""
    runner = CliRunner()

    # Initialize config
    with patch("rich.prompt.Confirm.ask", side_effect=[False, False]):
        runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Unset JIRA URL environment variable
    monkeypatch.delenv("JIRA_URL", raising=False)

    # Mock config to have no JIRA URL
    def mock_load_config():
        from devflow.config.models import Config, JiraConfig
        config = Config()
        config.jira = JiraConfig()
        config.jira.url = None
        return config

    with patch("devflow.config.loader.ConfigLoader.load_config", side_effect=mock_load_config):
        # Try to sync with JIRA filter
        result = runner.invoke(cli, ["sync", "--type", "Story"])

        # Verify error occurred
        assert result.exit_code != 0
        assert "JIRA filters" in result.output or "require JIRA" in result.output


def test_sync_with_jira_flag_but_no_jira_url_errors(temp_daf_home, monkeypatch):
    """Test: daf sync --jira without JIRA URL → error."""
    runner = CliRunner()

    # Initialize config
    with patch("rich.prompt.Confirm.ask", side_effect=[False, False]):
        runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Unset JIRA URL environment variable
    monkeypatch.delenv("JIRA_URL", raising=False)

    # Mock config to have no JIRA URL
    def mock_load_config():
        from devflow.config.models import Config, JiraConfig
        config = Config()
        config.jira = JiraConfig()
        config.jira.url = None
        return config

    with patch("devflow.config.loader.ConfigLoader.load_config", side_effect=mock_load_config):
        # Try to sync with --jira flag
        result = runner.invoke(cli, ["sync", "--jira"])

        # Verify error occurred
        assert result.exit_code != 0
        assert "--jira" in result.output or "require JIRA" in result.output


def test_sync_with_jira_flag_and_workspace_syncs_both(temp_daf_home):
    """Test: daf sync --jira -w workspace → sync both JIRA and workspace."""
    runner = CliRunner()

    # Initialize config
    with patch("rich.prompt.Confirm.ask", side_effect=[False, False]):
        runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Mock JIRA client and workspace scanning
    with patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira:
        with patch("devflow.cli.commands.sync_command.scan_workspace_for_repositories", return_value=[]) as mock_scan:
            with patch("devflow.cli.commands.sync_command.sync_github_repository", return_value={'created_count': 0, 'updated_count': 0}):
                # Configure mock JIRA client
                mock_jira_instance = MagicMock()
                mock_jira_instance.list_tickets.return_value = []
                mock_jira.return_value = mock_jira_instance

                result = runner.invoke(cli, ["sync", "--jira", "-w", "primary"])

                # Verify both JIRA and workspace scanning were called
                mock_jira.assert_called_once()
                mock_scan.assert_called()
