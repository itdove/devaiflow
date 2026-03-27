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

    # Initialize config - select Local preset (option 4)
    with patch("rich.prompt.Prompt.ask", return_value="4"):
        with patch("rich.prompt.Confirm.ask", return_value=False):
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

    # Initialize config - select Local preset (option 4)
    with patch("rich.prompt.Prompt.ask", return_value="4"):
        with patch("rich.prompt.Confirm.ask", return_value=False):
            runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Mock JIRA client to verify it's NOT called
    with patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira:
        with patch("devflow.cli.commands.sync_command.sync_github_repository", return_value={'created_count': 0, 'updated_count': 0}):
            result = runner.invoke(cli, ["sync", "--repository", "owner/repo1"])

            # Verify JIRA client was NOT instantiated
            mock_jira.assert_not_called()


def test_sync_workspace_filter_shows_no_jira_message_when_jira_configured(temp_daf_home):
    """Test: daf sync -w workspace with JIRA configured shows no JIRA skip message (silent)."""
    runner = CliRunner()

    # Initialize config with JIRA configured - select Local preset (option 4) then configure JIRA manually
    with patch("rich.prompt.Prompt.ask", return_value="4"):
        with patch("rich.prompt.Confirm.ask", return_value=False):
            result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Configure JIRA (add jira_project to organization.json)
    import json
    from pathlib import Path
    org_config_path = Path(temp_daf_home) / "organization.json"
    with open(org_config_path, "r") as f:
        org_config = json.load(f)
    org_config["jira_project"] = "PROJ"
    with open(org_config_path, "w") as f:
        json.dump(org_config, f, indent=2)

    # Set JIRA_URL environment variable to simulate JIRA being configured
    with patch.dict("os.environ", {"JIRA_URL": "https://jira.example.com"}):
        with patch("devflow.cli.commands.sync_command.scan_workspace_for_repositories", return_value=[]):
            result = runner.invoke(cli, ["sync", "-w", "primary"])

            # Verify no JIRA sync skip messages (silent when using workspace filter)
            assert "skipping jira sync" not in result.output.lower()
            assert "jira not configured" not in result.output.lower()


def test_sync_repository_filter_shows_no_jira_message_when_jira_configured(temp_daf_home):
    """Test: daf sync --repository with JIRA configured shows no JIRA skip message (silent)."""
    runner = CliRunner()

    # Initialize config with JIRA configured - select Local preset (option 4) then configure JIRA manually
    with patch("rich.prompt.Prompt.ask", return_value="4"):
        with patch("rich.prompt.Confirm.ask", return_value=False):
            result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Configure JIRA
    import json
    from pathlib import Path
    org_config_path = Path(temp_daf_home) / "organization.json"
    with open(org_config_path, "r") as f:
        org_config = json.load(f)
    org_config["jira_project"] = "PROJ"
    with open(org_config_path, "w") as f:
        json.dump(org_config, f, indent=2)

    # Set JIRA_URL environment variable
    with patch.dict("os.environ", {"JIRA_URL": "https://jira.example.com"}):
        with patch("devflow.cli.commands.sync_command.sync_github_repository", return_value={'created_count': 0, 'updated_count': 0}):
            result = runner.invoke(cli, ["sync", "--repository", "owner/repo"])

            # Verify no JIRA sync skip messages (silent when using repository filter)
            assert "skipping jira sync" not in result.output.lower()
            assert "jira not configured" not in result.output.lower()


def test_sync_without_jira_configured_shows_jira_not_configured_message(temp_daf_home):
    """Test: daf sync without JIRA configured shows 'JIRA not configured' message."""
    runner = CliRunner()

    # Initialize config without JIRA - select Local preset (option 4)
    with patch("rich.prompt.Prompt.ask", return_value="4"):
        with patch("rich.prompt.Confirm.ask", return_value=False):
            result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Run sync without workspace filter (should check JIRA)
    with patch("devflow.cli.commands.sync_command.scan_workspace_for_repositories", return_value=[]):
        result = runner.invoke(cli, ["sync"])

        # Verify message indicates JIRA not configured (either "JIRA not configured" or "JIRA project not configured")
        assert ("jira not configured" in result.output.lower() or "jira project not configured" in result.output.lower())
        assert "workspace-only mode" not in result.output.lower()


