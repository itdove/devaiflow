"""Tests for daf init command."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader


def test_init_first_time_no_jira_token(temp_daf_home, monkeypatch):
    """Test first-time init without JIRA token using Local preset."""
    # Unset JIRA_API_TOKEN
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    runner = CliRunner()

    # Mock prompts for Local-only preset
    with patch("rich.prompt.Prompt.ask") as mock_prompt:
        # Preset selection: 4 (Local-only)
        # Workspace path
        mock_prompt.side_effect = [
            "4",  # Choose Local-only preset
            str(Path.home() / "development")  # Workspace path
        ]

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
    assert "Edit config.json manually" in result.output or "daf config edit" in result.output


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
    config.jira.project = "CUSTOM"
    config.jira.custom_field_defaults = {"workstream": "CustomWorkstream"}
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
    assert updated_config.jira.project == "CUSTOM"
    assert updated_config.jira.custom_field_defaults == {"workstream": "CustomWorkstream"}
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
    """Test first-time init with JIRA preset and field discovery."""
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

    # Mock all prompts and wizard inputs for JIRA preset
    with patch("rich.prompt.Confirm.ask") as mock_confirm, \
         patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("devflow.jira.client.JiraClient"), \
         patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields", return_value=mock_field_mappings), \
         patch("devflow.cli.main._validate_jira_url", return_value=True):
        # Prompt.ask calls:
        # 1. Preset selection: 3 (JIRA)
        # 2. JIRA URL
        # 3. JIRA Project
        # 4. Workspace path
        # 5. Visibility type (group/role)
        # 6. Visibility value (group/role name)
        mock_prompt.side_effect = [
            "3",  # Choose JIRA preset
            "https://test-jira.example.com",
            "TEST",
            str(Path.home() / "development"),
            "group",
            "Engineering Team",
        ]

        # Confirm.ask calls:
        # 1. Discover JIRA fields: Yes
        mock_confirm.side_effect = [True]

        result = runner.invoke(cli, ["init"])

    # Should succeed
    assert result.exit_code == 0
    assert "Configuration saved" in result.output or "Next Steps:" in result.output

    # Verify config was saved
    loader = ConfigLoader()
    config = loader.load_config()
    assert config.jira.url == "https://test-jira.example.com"
    assert config.jira.project == "TEST"
    # Note: field_mappings may be None in test due to mocking limitations
    # The actual field discovery happens in _discover_and_cache_jira_fields
    # which is tested separately


def test_init_first_time_with_invalid_jira_url(temp_daf_home, monkeypatch):
    """Test first-time init with invalid JIRA URL (example.com) prevents field discovery."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    runner = CliRunner()

    # Mock prompts and wizard inputs with example URL using JIRA preset
    with patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("devflow.jira.field_mapper.JiraFieldMapper.discover_fields") as mock_discover, \
         patch("devflow.cli.main._validate_jira_url", return_value=False):
        # Prompt.ask calls:
        # 1. Preset selection: 3 (JIRA)
        # 2. JIRA URL (invalid example.com)
        # 3. JIRA Project
        # 4. Workspace path
        # 5. Visibility type
        # 6. Visibility value
        mock_prompt.side_effect = [
            "3",  # Choose JIRA preset
            "https://jira.example.com",  # Invalid example URL
            "PROJ",
            str(Path.home() / "development"),
            "group",
            "Engineering Team",
        ]

        result = runner.invoke(cli, ["init"])

    # Should succeed but warn about invalid URL
    assert result.exit_code == 0
    assert "Next Steps:" in result.output  # Post-init guidance shown
    assert "JIRA URL appears to be invalid or unreachable" in result.output

    # Verify field discovery was NOT called (due to invalid URL)
    mock_discover.assert_not_called()

    # Verify config was created with user's URL (even though invalid)
    loader = ConfigLoader()
    config = loader.load_config()
    assert config.jira.url == "https://jira.example.com"


def test_init_first_time_without_jira_integration(temp_daf_home):
    """Test first-time init when user chooses Local-only (no JIRA)."""
    runner = CliRunner()

    # Mock prompts - user selects Local-only preset (option 4)
    with patch("rich.prompt.Prompt.ask") as mock_prompt:
        # 1. Preset selection: 4 (Local-only)
        # 2. Workspace path
        mock_prompt.side_effect = [
            "4",  # Choose Local-only preset
            str(Path.home() / "development")
        ]

        result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Should succeed
    assert result.exit_code == 0
    assert "Local Sessions Only Setup" in result.output
    assert "Next Steps:" in result.output

    # Verify config was created with defaults
    loader = ConfigLoader()
    config = loader.load_config()
    assert config is not None
    assert config.jira is not None
    # Should have default example URL (minimal JIRA config)
    assert config.jira.url == "https://jira.example.com"
    # Should NOT have GitHub config
    assert config.github is None


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
    config.jira.project = "OLD"
    config.jira.custom_field_defaults = {"workstream": "OldWorkstream"}
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
            "NEW",                            # JIRA Project
            "group",                          # Comment visibility type
            "New Team",                       # Comment visibility value
            "/new/workspace",                 # Workspace path
        ]

        result = runner.invoke(cli, ["init", "--reset"])

    # Should succeed
    assert result.exit_code == 0
    assert "Configuration updated" in result.output
    assert "Changes:" in result.output

    # Verify config was updated
    updated_config = loader.load_config()
    assert updated_config.jira.url == "https://new-jira.example.com"
    assert updated_config.jira.project == "NEW"
    # custom_field_defaults preserved from old config (not prompted in wizard)
    assert updated_config.jira.custom_field_defaults == {"workstream": "OldWorkstream"}
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
    config.jira.project = "CUSTOM"
    config.jira.custom_field_defaults = {"workstream": "CustomWorkstream"}
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
        # Mock responses - all use defaults (note: workstream no longer prompted, preserved from old config)
        mock_prompt.side_effect = [
            "https://custom-jira.example.com",  # JIRA URL (same)
            "CUSTOM",                            # JIRA Project (same)
            "group",                             # Comment visibility type (default)
            "Engineering Team",                  # Comment visibility value (default)
            "/custom/workspace",                 # Workspace path (same)
        ]

        result = runner.invoke(cli, ["init", "--reset"])

    # Should succeed
    assert result.exit_code == 0
    assert "Configuration updated" in result.output
    assert "No changes made" in result.output  # All values stayed the same

    # Verify config was unchanged
    updated_config = loader.load_config()
    assert updated_config.jira.url == "https://custom-jira.example.com"
    assert updated_config.jira.project == "CUSTOM"
    assert updated_config.jira.custom_field_defaults.get("workstream") == "CustomWorkstream"
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


def test_init_local_preset(temp_daf_home, monkeypatch):
    """Test daf init with Local-only preset (option 4)."""
    # Unset JIRA_API_TOKEN
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    runner = CliRunner()

    # Mock prompts
    with patch("rich.prompt.Prompt.ask") as mock_prompt:
        # Preset selection: 4 (Local-only)
        # Workspace path
        mock_prompt.side_effect = [
            "4",  # Choose Local-only preset
            "/test/workspace"  # Workspace path
        ]

        result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Should succeed
    assert result.exit_code == 0
    assert "Local Sessions Only Setup" in result.output
    assert "Next Steps:" in result.output
    assert "daf new" in result.output

    # Verify config was created
    loader = ConfigLoader()
    config = loader.load_config()
    assert config is not None
    assert len(config.repos.workspaces) == 1
    assert config.repos.workspaces[0].path == "/test/workspace"
    assert config.github is None  # No GitHub config


def test_init_github_preset(temp_daf_home, monkeypatch):
    """Test daf init with GitHub-only preset (option 1)."""
    # Unset JIRA_API_TOKEN
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    runner = CliRunner()

    # Mock prompts
    with patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("rich.prompt.Confirm.ask") as mock_confirm, \
         patch("devflow.git.utils.GitUtils.is_git_repository", return_value=True), \
         patch("devflow.git.utils.GitUtils.detect_repo_type", return_value="github"), \
         patch("devflow.git.utils.GitUtils.get_remote_url", return_value="https://github.com/user/repo.git"):
        # Preset selection: 1 (GitHub)
        # Workspace path
        # Default labels
        mock_prompt.side_effect = [
            "1",  # Choose GitHub preset
            "/test/workspace",  # Workspace path
            "backend,devaiflow",  # Default labels
        ]
        # Auto-close on complete
        mock_confirm.side_effect = [True]

        result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Should succeed
    assert result.exit_code == 0
    assert "GitHub Issues Setup" in result.output
    assert "Detected GitHub remote" in result.output
    assert "Next Steps:" in result.output
    assert "daf git new" in result.output

    # Verify config was created
    loader = ConfigLoader()
    config = loader.load_config()
    assert config is not None
    assert config.github is not None
    assert config.github.default_labels == ["backend", "devaiflow"]
    assert config.github.auto_close_on_complete is True


def test_init_gitlab_preset(temp_daf_home, monkeypatch):
    """Test daf init with GitLab-only preset (option 2)."""
    # Unset JIRA_API_TOKEN
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    runner = CliRunner()

    # Mock prompts
    with patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("rich.prompt.Confirm.ask") as mock_confirm, \
         patch("devflow.git.utils.GitUtils.is_git_repository", return_value=True), \
         patch("devflow.git.utils.GitUtils.detect_repo_type", return_value="gitlab"), \
         patch("devflow.git.utils.GitUtils.get_remote_url", return_value="https://gitlab.com/user/repo.git"):
        # Preset selection: 2 (GitLab)
        # Workspace path
        # Default labels (empty)
        mock_prompt.side_effect = [
            "2",  # Choose GitLab preset
            "/test/workspace",  # Workspace path
            "",  # Default labels (empty)
        ]
        # Auto-close on complete
        mock_confirm.side_effect = [False]

        result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Should succeed
    assert result.exit_code == 0
    assert "GitLab Issues Setup" in result.output
    assert "Detected GitLab remote" in result.output
    assert "Next Steps:" in result.output
    assert "daf git new" in result.output

    # Verify config was created
    loader = ConfigLoader()
    config = loader.load_config()
    assert config is not None
    assert config.github is not None
    assert config.github.default_labels == []
    assert config.github.auto_close_on_complete is False


def test_init_jira_preset(temp_daf_home, monkeypatch):
    """Test daf init with JIRA-only preset (option 3)."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    runner = CliRunner()

    # Mock prompts
    with patch("rich.prompt.Prompt.ask") as mock_prompt:
        # Preset selection: 3 (JIRA)
        # JIRA URL
        # JIRA Project
        # Workspace path
        # Comment visibility type
        # Comment visibility value
        mock_prompt.side_effect = [
            "3",  # Choose JIRA preset
            "https://test-jira.example.com",  # JIRA URL
            "TEST",  # JIRA Project
            "/test/workspace",  # Workspace path
            "group",  # Visibility type
            "Engineering Team",  # Visibility value
        ]

        result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Should succeed
    assert result.exit_code == 0
    assert "JIRA Setup" in result.output
    assert "JIRA_API_TOKEN environment variable is set" in result.output
    assert "Next Steps:" in result.output
    assert "daf jira new" in result.output

    # Verify config was created
    loader = ConfigLoader()
    config = loader.load_config()
    assert config is not None
    assert config.jira.url == "https://test-jira.example.com"
    assert config.jira.project == "TEST"
    assert config.jira.comment_visibility_type == "group"
    assert config.jira.comment_visibility_value == "Engineering Team"


def test_init_preset_auto_detection(temp_daf_home, monkeypatch):
    """Test that init wizard auto-detects issue tracker and suggests default."""
    # Set JIRA_API_TOKEN
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")

    runner = CliRunner()

    # Mock prompts and auto-detection
    with patch("rich.prompt.Prompt.ask") as mock_prompt, \
         patch("devflow.git.utils.GitUtils.is_git_repository", return_value=True), \
         patch("devflow.git.utils.GitUtils.detect_repo_type", return_value="github"):
        # Should default to option 1 (GitHub) since detected from git
        # But JIRA token is also set, so JIRA should show as detected
        mock_prompt.side_effect = [
            "4",  # Choose Local-only to skip complex setup
            "/test/workspace"  # Workspace path
        ]

        result = runner.invoke(cli, ["init", "--skip-jira-discovery"])

    # Should show detection hints
    assert result.exit_code == 0
    assert "detected from git remote" in result.output or "JIRA_API_TOKEN detected" in result.output
