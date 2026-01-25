"""Tests for daf init command."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader


def test_init_first_time_no_jira_token(temp_daf_home, monkeypatch):
    """Test first-time init without JIRA token."""
    # Unset JIRA_API_TOKEN
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    runner = CliRunner()

    # Mock prompts to skip interactive parts
    # First call: Enable JIRA integration (answer No to skip wizard)
    # Second call: PR template (answer No to skip)
    with patch("rich.prompt.Confirm.ask", side_effect=[False, False]):
        result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Should succeed and create config
    assert result.exit_code == 0

    # Verify config was created
    loader = ConfigLoader()
    assert loader.config_file.exists()
    config = loader.load_config()
    assert config is not None
    assert config.jira is not None


def test_init_with_refresh_no_config_exists(temp_daf_home):
    """Test daf init --refresh when no config exists."""
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--refresh"])

    # Should fail because there's no config to refresh
    assert result.exit_code == 0  # Click doesn't exit with error code for our error messages
    assert "No configuration found" in result.output
    assert "Cannot refresh without existing config" in result.output
    assert "daf init" in result.output


def test_init_config_already_exists_no_refresh(temp_daf_home):
    """Test daf init when config already exists without --refresh flag."""
    # Create initial config
    loader = ConfigLoader()
    loader.create_default_config()

    runner = CliRunner()
    result = runner.invoke(cli, ["init"])

    # Should show helpful message
    assert result.exit_code == 0
    assert "Configuration already exists" in result.output
    assert "daf init --refresh" in result.output
    assert "Edit config.json manually" in result.output or "daf config tui" in result.output


def test_init_refresh_updates_field_mappings(temp_daf_home, mock_jira_cli, monkeypatch):
    """Test daf init --refresh updates field mappings."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    # Create initial config
    loader = ConfigLoader()
    config = loader.create_default_config()

    # Verify no field mappings initially
    assert config.jira.field_mappings is None or config.jira.field_mappings == {}

    # Mock field discovery to return test mappings
    mock_field_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream",
            "type": "array",
            "schema": "option",
            "allowed_values": ["Platform", "Platform"],
            "required_for": ["Bug", "Story"]
        },
        "epic_link": {
            "id": "customfield_12311140",
            "name": "Epic Link",
            "type": "string",
            "schema": "string",
            "allowed_values": [],
            "required_for": []
        }
    }

    runner = CliRunner()

    with patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields", return_value=mock_field_mappings):
        result = runner.invoke(cli, ["init", "--refresh"])

    # Should succeed
    assert result.exit_code == 0
    assert "Refreshing automatically discovered data" in result.output
    assert "Configuration refreshed" in result.output

    # Verify field mappings were updated
    updated_config = loader.load_config()
    assert updated_config.jira.field_mappings is not None
    assert "workstream" in updated_config.jira.field_mappings
    assert "epic_link" in updated_config.jira.field_mappings
    assert updated_config.jira.field_cache_timestamp is not None


def test_init_refresh_preserves_user_config(temp_daf_home_no_patches, mock_jira_cli, monkeypatch):
    """Test daf init --refresh preserves user-provided configuration."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    # Create initial config with custom values
    loader = ConfigLoader()
    config = loader.create_default_config()

    # Set custom user values
    config.jira.url = "https://custom-jira.example.com"
    config.jira.user = "custom-user"
    config.jira.project = "CUSTOM"
    config.jira.workstream = "CustomWorkstream"
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path="/custom/workspace")
    ]

    loader.save_config(config)

    # Mock field discovery
    mock_field_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream",
            "type": "array",
            "schema": "option",
            "allowed_values": ["Platform"],
            "required_for": []
        }
    }

    runner = CliRunner()

    with patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields", return_value=mock_field_mappings):
        result = runner.invoke(cli, ["init", "--refresh"])

    # Should succeed
    assert result.exit_code == 0

    # Verify user config was preserved
    updated_config = loader.load_config()
    assert updated_config.jira.url == "https://custom-jira.example.com"
    assert updated_config.jira.user == "custom-user"
    assert updated_config.jira.project == "CUSTOM"
    assert updated_config.jira.workstream == "CustomWorkstream"
    assert len(updated_config.repos.workspaces) == 1
    assert updated_config.repos.workspaces[0].name == "default"
    assert updated_config.repos.workspaces[0].path == "/custom/workspace"

    # Verify field mappings were updated
    assert updated_config.jira.field_mappings is not None
    assert "workstream" in updated_config.jira.field_mappings


def test_init_refresh_with_invalid_config(temp_daf_home):
    """Test daf init --refresh with invalid/corrupted config file."""
    # Create corrupted config
    loader = ConfigLoader()
    with open(loader.config_file, "w") as f:
        f.write("{ invalid json }")

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--refresh"])

    # Should handle the error gracefully
    # Note: The actual behavior depends on implementation - it might exit or show error
    assert result.exit_code != 0 or "Invalid configuration" in result.output or "Failed to load config" in result.output


def test_init_refresh_field_discovery_error(temp_daf_home, monkeypatch):
    """Test daf init --refresh when field discovery fails."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    # Create initial config
    loader = ConfigLoader()
    loader.create_default_config()

    runner = CliRunner()

    # Mock field discovery to raise an error
    with patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields", side_effect=RuntimeError("API error")):
        result = runner.invoke(cli, ["init", "--refresh"])

    # Should handle the error gracefully
    assert result.exit_code == 0
    # Error message should be shown
    assert "Could not discover fields" in result.output or "error" in result.output.lower()


def test_init_refresh_updates_timestamp(temp_daf_home, mock_jira_cli, monkeypatch):
    """Test daf init --refresh updates field_cache_timestamp."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    # Create initial config
    loader = ConfigLoader()
    config = loader.create_default_config()

    # Set an old timestamp
    old_timestamp = "2020-01-01T00:00:00"
    config.jira.field_cache_timestamp = old_timestamp
    loader.save_config(config)

    # Mock field discovery
    mock_field_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream",
            "type": "array",
            "schema": "option",
            "allowed_values": ["Platform"],
            "required_for": []
        }
    }

    runner = CliRunner()

    with patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields", return_value=mock_field_mappings):
        result = runner.invoke(cli, ["init", "--refresh"])

    # Should succeed
    assert result.exit_code == 0

    # Verify timestamp was updated
    updated_config = loader.load_config()
    assert updated_config.jira.field_cache_timestamp is not None
    assert updated_config.jira.field_cache_timestamp != old_timestamp


def test_init_first_time_with_jira_discovery(temp_daf_home, mock_jira_cli, monkeypatch):
    """Test first-time init with JIRA field discovery."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    # Mock field discovery
    mock_field_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream",
            "type": "array",
            "schema": "option",
            "allowed_values": ["Platform"],
            "required_for": []
        }
    }

    runner = CliRunner()

    # Mock all prompts and wizard inputs
    with patch("rich.prompt.Confirm.ask") as mock_confirm, \
         patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields", return_value=mock_field_mappings), \
         patch("devflow.cli.main._validate_jira_url", return_value=True):
        # Confirm prompts:
        # 1. Enable JIRA integration: Yes
        # 2. Update keywords (in wizard): No
        # 3. Discover JIRA fields: Yes
        # 4. PR template config: No
        # 5. Configure workstream: No
        mock_confirm.side_effect = [True, False, True, False, False]

        # Wizard prompts for JIRA config:
        # 1. JIRA URL
        # 2. JIRA Project
        # 3. JIRA User
        # 4. Workstream
        # 5. Workspace path
        mock_prompt.side_effect = [
            "https://test-jira.example.com",
            "TEST",
            "test-user",
            "TestWorkstream",
            str(Path.home() / "development")
        ]

        result = runner.invoke(cli, ["init"])

    # Should succeed
    assert result.exit_code == 0
    assert "Configuration saved" in result.output

    # Verify field mappings were cached
    loader = ConfigLoader()
    config = loader.load_config()
    assert config.jira.field_mappings is not None
    assert "workstream" in config.jira.field_mappings
    assert config.jira.url == "https://test-jira.example.com"
    assert config.jira.project == "TEST"


def test_init_first_time_with_invalid_jira_url(temp_daf_home, monkeypatch):
    """Test first-time init with invalid JIRA URL (example.com) prevents field discovery."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    runner = CliRunner()

    # Mock prompts and wizard inputs with example URL
    with patch("rich.prompt.Confirm.ask") as mock_confirm, \
         patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields") as mock_discover, \
         patch("devflow.cli.main._validate_jira_url", return_value=False):
        # Confirm prompts:
        # 1. Enable JIRA integration: Yes
        # 2. Update keywords (in wizard): No
        mock_confirm.side_effect = [True, False, False, False]

        # Wizard prompts - user provides example.com URL (should be detected as invalid)
        mock_prompt.side_effect = [
            "https://jira.example.com",  # Invalid example URL
            "PROJ",
            "test-user",
            "TestWorkstream",
            str(Path.home() / "development")
        ]

        result = runner.invoke(cli, ["init"])

    # Should succeed but warn about invalid URL
    assert result.exit_code == 0
    assert "Configuration saved" in result.output
    assert "JIRA URL appears to be invalid or unreachable" in result.output

    # Verify field discovery was NOT called (due to invalid URL)
    mock_discover.assert_not_called()

    # Verify config was created with user's URL (even though invalid)
    loader = ConfigLoader()
    config = loader.load_config()
    assert config.jira.url == "https://jira.example.com"


def test_init_first_time_without_jira_integration(temp_daf_home):
    """Test first-time init when user chooses not to integrate with JIRA."""
    runner = CliRunner()

    # Mock prompts - user says No to JIRA integration
    with patch("rich.prompt.Confirm.ask") as mock_confirm:
        # 1. Enable JIRA integration: No
        # 2. PR template config: No
        mock_confirm.side_effect = [False, False]

        result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Should succeed
    assert result.exit_code == 0
    assert "Created default configuration" in result.output
    assert "JIRA integration skipped" in result.output

    # Verify config was created with defaults
    loader = ConfigLoader()
    config = loader.load_config()
    assert config is not None
    assert config.jira is not None
    # Should have default example URL
    assert config.jira.url == "https://jira.example.com"


def test_init_reset_no_config_exists(temp_daf_home):
    """Test daf init --reset when no config exists."""
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--reset"])

    # Should fail because there's no config to reset
    assert result.exit_code == 0
    assert "No configuration to reset" in result.output
    assert "daf init" in result.output


def test_init_reset_and_refresh_together(temp_daf_home):
    """Test daf init --reset --refresh together (should fail)."""
    # Create initial config
    loader = ConfigLoader()
    loader.create_default_config()

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--reset", "--refresh"])

    # Should fail because both flags are mutually exclusive
    assert result.exit_code == 0
    assert "Cannot use --refresh and --reset together" in result.output


def test_init_reset_updates_config_values(temp_daf_home_no_patches, mock_jira_cli, monkeypatch):
    """Test daf init --reset updates configuration values."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    # Create initial config with custom values
    loader = ConfigLoader()
    config = loader.create_default_config()
    config.jira.url = "https://old-jira.example.com"
    config.jira.user = "old-user"
    config.jira.project = "OLD"
    config.jira.workstream = "OldWorkstream"
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path="/old/workspace")
    ]
    loader.save_config(config)

    # Mock field discovery
    mock_field_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream",
            "type": "array",
            "schema": "option",
            "allowed_values": ["Platform"],
            "required_for": []
        }
    }

    runner = CliRunner()

    # Mock prompts to provide new values
    with patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("rich.prompt.Confirm.ask", return_value=False), \
         patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields", return_value=mock_field_mappings):
        # Mock responses for wizard prompts
        mock_prompt.side_effect = [
            "https://new-jira.example.com",  # JIRA URL
            "NEW",  # JIRA Project
            "new-user",  # JIRA User
            "NewWorkstream",  # Workstream
            "/new/workspace",  # Workspace path
        ]

        result = runner.invoke(cli, ["init", "--reset"])

    # Should succeed
    assert result.exit_code == 0
    assert "Configuration updated" in result.output
    assert "Changes:" in result.output

    # Verify config was updated
    updated_config = loader.load_config()
    assert updated_config.jira.url == "https://new-jira.example.com"
    assert updated_config.jira.user == "new-user"
    assert updated_config.jira.project == "NEW"
    assert updated_config.jira.workstream == "NewWorkstream"
    assert len(updated_config.repos.workspaces) == 1
    assert updated_config.repos.workspaces[0].name == "default"
    assert updated_config.repos.workspaces[0].path == "/new/workspace"


def test_init_reset_preserves_unchanged_values(temp_daf_home_no_patches, mock_jira_cli, monkeypatch):
    """Test daf init --reset preserves values when user presses Enter (accepts defaults)."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    # Create initial config
    loader = ConfigLoader()
    config = loader.create_default_config()
    config.jira.url = "https://custom-jira.example.com"
    config.jira.user = "custom-user"
    config.jira.project = "CUSTOM"
    config.jira.workstream = "CustomWorkstream"
    from devflow.config.models import WorkspaceDefinition
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path="/custom/workspace")
    ]
    loader.save_config(config)

    # Mock field discovery
    mock_field_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream",
            "type": "array",
            "schema": "option",
            "allowed_values": ["Platform"],
            "required_for": []
        }
    }

    runner = CliRunner()

    # Mock prompts to use defaults (empty string returns default)
    with patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("rich.prompt.Confirm.ask", return_value=False), \
         patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields", return_value=mock_field_mappings):
        # Mock responses - all use defaults
        mock_prompt.side_effect = [
            "https://custom-jira.example.com",  # JIRA URL (same)
            "CUSTOM",  # JIRA Project (same)
            "custom-user",  # JIRA User (same)
            "CustomWorkstream",  # Workstream (same)
            "/custom/workspace",  # Workspace path (same)
        ]

        result = runner.invoke(cli, ["init", "--reset"])

    # Should succeed
    assert result.exit_code == 0
    assert "Configuration updated" in result.output
    assert "No changes made" in result.output  # All values stayed the same

    # Verify config was unchanged
    updated_config = loader.load_config()
    assert updated_config.jira.url == "https://custom-jira.example.com"
    assert updated_config.jira.user == "custom-user"
    assert updated_config.jira.project == "CUSTOM"
    assert updated_config.jira.workstream == "CustomWorkstream"
    assert len(updated_config.repos.workspaces) == 1
    assert updated_config.repos.workspaces[0].name == "default"
    assert updated_config.repos.workspaces[0].path == "/custom/workspace"


def test_init_reset_refreshes_field_mappings(temp_daf_home, mock_jira_cli, monkeypatch):
    """Test daf init --reset automatically refreshes JIRA field mappings."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    # Create initial config with old field mappings
    loader = ConfigLoader()
    config = loader.create_default_config()
    config.jira.field_mappings = {"old_field": {"id": "customfield_old"}}
    config.jira.field_cache_timestamp = "2020-01-01T00:00:00"
    loader.save_config(config)

    # Mock field discovery with new mappings
    mock_field_mappings = {
        "workstream": {
            "id": "customfield_12319275",
            "name": "Workstream",
            "type": "array",
            "schema": "option",
            "allowed_values": ["Platform"],
            "required_for": []
        }
    }

    runner = CliRunner()

    # Mock prompts to keep current values
    with patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("rich.prompt.Confirm.ask", return_value=False), \
         patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields", return_value=mock_field_mappings):
        # Mock responses - all use defaults
        mock_prompt.side_effect = [
            "https://jira.example.com",
            "PROJ",
            "your-username",
            "Platform",
            str(Path.home() / "development"),
        ]

        result = runner.invoke(cli, ["init", "--reset"])

    # Should succeed
    assert result.exit_code == 0
    assert "Discovering JIRA custom field mappings" in result.output
    assert "Configuration updated" in result.output

    # Verify field mappings were updated
    updated_config = loader.load_config()
    assert updated_config.jira.field_mappings is not None
    assert "workstream" in updated_config.jira.field_mappings
    assert "old_field" not in updated_config.jira.field_mappings
    assert updated_config.jira.field_cache_timestamp != "2020-01-01T00:00:00"


def test_init_reset_with_corrupted_config(temp_daf_home):
    """Test daf init --reset with corrupted config file."""
    # Create corrupted config
    loader = ConfigLoader()
    with open(loader.config_file, "w") as f:
        f.write("{ invalid json }")

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--reset"])

    # Should handle the error gracefully
    assert result.exit_code == 0
    assert "Could not load config" in result.output


def test_init_reset_skip_jira_discovery(temp_daf_home, monkeypatch):
    """Test daf init --reset --skip-jira-discovery skips field discovery."""
    # Unset JIRA_API_TOKEN to prevent auto-refresh from running
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    # Create initial config
    loader = ConfigLoader()
    config = loader.create_default_config()
    config.jira.field_mappings = {"old_field": {"id": "customfield_old"}}
    config.jira.field_cache_timestamp = "2020-01-01T00:00:00"
    loader.save_config(config)

    runner = CliRunner()

    # Mock prompts to keep current values AND mock field discovery to ensure it's not called
    with patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("rich.prompt.Confirm.ask", return_value=False), \
         patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields") as mock_discover:
        # Mock responses - all use defaults
        mock_prompt.side_effect = [
            "https://jira.example.com",
            "PROJ",
            "your-username",
            "Platform",
            str(Path.home() / "development"),
        ]

        result = runner.invoke(cli, ["init", "--reset", "--skip-jira-discovery"])

    # Should succeed
    assert result.exit_code == 0
    assert "Configuration updated" in result.output
    assert "Discovering JIRA custom field mappings" not in result.output

    # Verify field discovery was NOT called
    mock_discover.assert_not_called()

    # Verify field mappings were NOT updated (old ones preserved)
    updated_config = loader.load_config()
    assert "old_field" in updated_config.jira.field_mappings
    assert updated_config.jira.field_cache_timestamp == "2020-01-01T00:00:00"
