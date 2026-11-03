"""Tests for smart sync mode detection (itdove/devaiflow#147).

Tests that daf sync automatically determines what to sync based on parameters.
These tests focus on the CLI integration rather than internal function calls.
"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.jira.exceptions import JiraAuthError


def _configure_jira() -> CliRunner:
    """Initialize a local config with JIRA enabled for sync integration tests."""
    runner = CliRunner()
    with (
        patch("rich.prompt.Prompt.ask", return_value="4"),
        patch("rich.prompt.Confirm.ask", return_value=False),
    ):
        runner.invoke(cli, ["init", "--skip-jira-discovery"])

    config_loader = ConfigLoader()
    config = config_loader.load_config()
    assert config and config.jira
    config.jira.url = "https://jira.example.com"
    config.jira.project = "PROJ"
    config.jira.field_cache_auto_refresh = False
    config_loader.save_config(config)
    return runner


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


@pytest.mark.parametrize("token_expired", [False, True])
def test_sync_jira_auth_failure_is_explicit_in_json(temp_daf_home, token_expired):
    """JIRA 401s are errors, not successful syncs with zero results."""
    runner = _configure_jira()
    token = "test-token-not-for-output"
    auth_error = JiraAuthError(
        f"Invalid credentials: {token}",
        token_expired=token_expired,
        jira_url="https://jira.example.com",
        status_code=401,
    )

    with (
        patch.dict(
            "os.environ",
            {"JIRA_URL": "https://jira.example.com", "JIRA_API_TOKEN": token},
        ),
        patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira,
    ):
        mock_jira.return_value.list_tickets.side_effect = auth_error
        result = runner.invoke(cli, ["sync", "--jira", "--json"])

    assert result.exit_code == 0, result.output
    assert result.output.lstrip().startswith("{"), repr(result.output)
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["error"]["code"] == "JIRA_AUTHENTICATION_FAILED"
    assert "JIRA_API_TOKEN" in payload["error"]["message"]
    assert token not in result.output
    assert "Found 0 JIRA tickets" not in result.output
    if token_expired:
        assert "expired" in payload["error"]["message"].lower()
    else:
        assert "invalid or expired" in payload["error"]["message"].lower()


def test_sync_jira_auth_failure_has_guidance_in_text_output(temp_daf_home):
    """Text output clearly explains a rejected credential and recovery steps."""
    runner = _configure_jira()
    token = "test-token-not-for-output"

    with (
        patch.dict(
            "os.environ",
            {"JIRA_URL": "https://jira.example.com", "JIRA_API_TOKEN": token},
        ),
        patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira,
    ):
        mock_jira.return_value.list_tickets.side_effect = JiraAuthError(
            "Invalid credentials",
            jira_url="https://jira.example.com",
            status_code=401,
        )
        result = runner.invoke(cli, ["sync", "--jira"])

    assert result.exit_code == 0, result.output
    assert "JIRA authentication failed" in result.output
    assert "invalid or expired" in result.output.lower()
    assert "JIRA_API_TOKEN" in result.output
    assert "Sync finished with errors" in result.output
    assert "Sync complete" not in result.output
    assert token not in result.output


def test_sync_jira_empty_results_remain_successful(temp_daf_home):
    """A successful JIRA query with no matches remains distinct from auth failure."""
    runner = _configure_jira()

    with (
        patch.dict("os.environ", {"JIRA_URL": "https://jira.example.com"}),
        patch("devflow.cli.commands.sync_command.JiraClient") as mock_jira,
    ):
        mock_jira.return_value.list_tickets.return_value = []
        result = runner.invoke(cli, ["sync", "--jira", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["success"] is True
    assert "error" not in payload
    assert payload["data"]["backends"]["jira"] == {"created": 0, "updated": 0}
