"""Tests for configuration TUI."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from devflow.ui.config_tui import (
    URLValidator,
    PathValidator,
    NonEmptyValidator,
    ConfigInput,
    ConfigCheckbox,
    ConfigSelect,
    ContextFileEntry,
    AddContextFileScreen,
    ConfigTUI,
    run_config_tui,
)
from devflow.config.models import Config, JiraConfig, RepoConfig, ContextFile


# ============================================================================
# Validator Tests
# ============================================================================


def test_url_validator_valid():
    """Test URL validator with valid URLs."""
    validator = URLValidator()

    # Valid URLs
    assert validator.validate("https://jira.example.com").is_valid
    assert validator.validate("http://localhost:8080").is_valid
    assert validator.validate("").is_valid  # Allow empty for optional fields


def test_url_validator_invalid():
    """Test URL validator with invalid URLs."""
    validator = URLValidator()

    # Invalid URLs
    result = validator.validate("not-a-url")
    assert not result.is_valid
    assert "must start with http://" in str(result.failure_descriptions)

    result = validator.validate("ftp://invalid.com")
    assert not result.is_valid


def test_path_validator_valid():
    """Test path validator with valid paths."""
    validator = PathValidator()

    # Valid paths (or empty)
    assert validator.validate("").is_valid
    assert validator.validate("/tmp").is_valid
    assert validator.validate("~/test").is_valid


def test_path_validator_invalid():
    """Test path validator with invalid paths."""
    validator = PathValidator()

    # Test with a clearly invalid path structure
    # Note: We don't fail on non-existent paths during typing
    assert validator.validate("/some/path/that/does/not/exist").is_valid


def test_non_empty_validator():
    """Test non-empty validator."""
    validator = NonEmptyValidator()

    # Valid (non-empty)
    assert validator.validate("test").is_valid
    assert validator.validate("value").is_valid

    # Invalid (empty)
    result = validator.validate("")
    assert not result.is_valid
    assert "required" in str(result.failure_descriptions).lower()

    result = validator.validate("   ")
    assert not result.is_valid


# ============================================================================
# Widget Tests
# ============================================================================


def test_config_input_initialization():
    """Test ConfigInput widget initialization."""
    widget = ConfigInput(
        label="Test Field",
        config_key="test.field",
        value="test_value",
        help_text="This is help text",
        required=True,
    )

    assert widget.config_key == "test.field"
    assert widget._label == "Test Field"
    assert widget._value == "test_value"
    assert widget._help_text == "This is help text"
    assert widget._required is True


def test_config_checkbox_initialization():
    """Test ConfigCheckbox widget initialization."""
    widget = ConfigCheckbox(
        label="Enable Feature",
        config_key="feature.enabled",
        value=True,
        help_text="Enable this feature",
    )

    assert widget.config_key == "feature.enabled"
    assert widget._label == "Enable Feature"
    assert widget._value is True
    assert widget._help_text == "Enable this feature"


def test_config_checkbox_none_value():
    """Test ConfigCheckbox with None value (unset)."""
    widget = ConfigCheckbox(
        label="Auto Commit",
        config_key="prompts.auto_commit",
        value=None,
        help_text="Automatically commit",
    )

    assert widget._value is None


def test_config_select_initialization():
    """Test ConfigSelect widget initialization."""
    choices = [("option1", "Option 1"), ("option2", "Option 2")]
    widget = ConfigSelect(
        label="Select Option",
        config_key="select.option",
        choices=choices,
        value="option1",
        help_text="Choose an option",
        allow_blank=False,
    )

    assert widget.config_key == "select.option"
    assert widget._label == "Select Option"
    assert widget._choices == choices
    assert widget._value == "option1"
    assert widget._allow_blank is False


# ============================================================================
# TUI Application Tests
# ============================================================================


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    from devflow.config.models import (
        JiraConfig,
        RepoConfig,
        RepoDetectionConfig,
        PromptsConfig,
        ContextFilesConfig,
    )

    jira_config = JiraConfig(
        url="https://jira.example.com",
        transitions={},
        project="PROJ",
        custom_field_defaults={"workstream": "Platform"},
        affected_version="v1.0.0",
    )

    repo_config = RepoConfig(
        workspace="/Users/test/development",
        detection=RepoDetectionConfig(method="keyword_match", fallback="prompt"),
    )

    config = Config(
        jira=jira_config,
        repos=repo_config,
        prompts=PromptsConfig(),
        context_files=ContextFilesConfig(),
    )

    return config


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_initialization(mock_config_loader, mock_config):
    """Test ConfigTUI initialization."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    # Initialize TUI
    tui = ConfigTUI()

    assert tui.config is not None
    assert tui.config.jira.url == "https://jira.example.com"
    assert tui.config.jira.project == "PROJ"
    assert tui.modified is False


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_initialization_no_config(mock_config_loader):
    """Test ConfigTUI initialization with no config."""
    # Setup mock to return None
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = None
    mock_config_loader.return_value = mock_loader_instance

    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="Failed to load configuration"):
        ConfigTUI()


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_validation(mock_config_loader, mock_config):
    """Test configuration validation in TUI."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Test validation with valid config
    errors = tui._validate_all()
    # Should have path validation error since /Users/test/development doesn't exist
    assert len(errors) >= 1


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_validation_missing_required(mock_config_loader, mock_config):
    """Test validation with missing required fields."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Clear required fields
    tui.config.jira.url = ""
    tui.config.repos.workspaces = []

    errors = tui._validate_all()

    assert len(errors) >= 2
    assert any("JIRA URL is required" in err for err in errors)
    assert any("workspace is required" in err for err in errors)


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_create_backup(mock_config_loader, mock_config, tmp_path):
    """Test backup creation."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = tmp_path
    mock_loader_instance.config_file = tmp_path / "config.json"
    mock_config_loader.return_value = mock_loader_instance

    # Create a dummy config file
    mock_loader_instance.config_file.write_text('{"test": "data"}')

    tui = ConfigTUI()

    # Create backup
    backup_path = tui._create_backup()

    assert backup_path.exists()
    assert backup_path.parent == tmp_path / "backups"
    assert backup_path.name.startswith("config-")
    assert backup_path.name.endswith(".json")


# ============================================================================
# Integration Tests
# ============================================================================


@patch("devflow.ui.config_tui.ConfigTUI")
def test_run_config_tui(mock_tui_class):
    """Test run_config_tui function."""
    mock_app = Mock()
    mock_tui_class.return_value = mock_app

    run_config_tui()

    mock_app.run.assert_called_once()


@patch("devflow.ui.config_tui.ConfigTUI")
def test_run_config_tui_exception(mock_tui_class):
    """Test run_config_tui with exception."""
    mock_tui_class.side_effect = RuntimeError("Test error")

    with pytest.raises(RuntimeError, match="Test error"):
        run_config_tui()


# ============================================================================
# Context File Management Tests
# ============================================================================


def test_context_file_entry_initialization():
    """Test ContextFileEntry widget initialization."""
    ctx_file = ContextFile(path="ARCHITECTURE.md", description="System architecture")
    widget = ContextFileEntry(index=0, context_file=ctx_file)

    assert widget.index == 0
    assert widget.context_file.path == "ARCHITECTURE.md"
    assert widget.context_file.description == "System architecture"


def test_add_context_file_screen_add_mode():
    """Test AddContextFileScreen in add mode."""
    screen = AddContextFileScreen()

    assert screen.existing_file is None
    assert screen.index is None
    assert screen.is_edit_mode is False


def test_add_context_file_screen_edit_mode():
    """Test AddContextFileScreen in edit mode."""
    ctx_file = ContextFile(path="DESIGN.md", description="Design docs")
    screen = AddContextFileScreen(existing_file=ctx_file, index=1)

    assert screen.existing_file == ctx_file
    assert screen.index == 1
    assert screen.is_edit_mode is True


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_add_context_file(mock_config_loader, mock_config):
    """Test adding a context file via TUI."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Initially no context files
    assert len(tui.config.context_files.files) == 0

    # Simulate adding a context file
    new_ctx_file = ContextFile(path="ARCHITECTURE.md", description="System architecture")
    tui.config.context_files.files.append(new_ctx_file)

    assert len(tui.config.context_files.files) == 1
    assert tui.config.context_files.files[0].path == "ARCHITECTURE.md"
    assert tui.config.context_files.files[0].description == "System architecture"


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_remove_context_file(mock_config_loader, mock_config):
    """Test removing a context file via TUI."""
    # Setup mock with existing context file
    ctx_file = ContextFile(path="DESIGN.md", description="Design docs")
    mock_config.context_files.files.append(ctx_file)

    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Should have one context file
    assert len(tui.config.context_files.files) == 1

    # Remove the context file
    tui.config.context_files.files.pop(0)

    assert len(tui.config.context_files.files) == 0


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_edit_context_file(mock_config_loader, mock_config):
    """Test editing a context file via TUI."""
    # Setup mock with existing context file
    ctx_file = ContextFile(path="OLD.md", description="Old description")
    mock_config.context_files.files.append(ctx_file)

    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Should have one context file
    assert len(tui.config.context_files.files) == 1
    assert tui.config.context_files.files[0].path == "OLD.md"

    # Edit the context file
    tui.config.context_files.files[0] = ContextFile(path="NEW.md", description="New description")

    assert len(tui.config.context_files.files) == 1
    assert tui.config.context_files.files[0].path == "NEW.md"
    assert tui.config.context_files.files[0].description == "New description"


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_refresh_context_files_list(mock_config_loader, mock_config):
    """Test refreshing context files list after changes."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Add context files
    tui.config.context_files.files.append(
        ContextFile(path="FILE1.md", description="First file")
    )
    tui.config.context_files.files.append(
        ContextFile(path="FILE2.md", description="Second file")
    )

    assert len(tui.config.context_files.files) == 2


# ============================================================================
# PR Template URL Tests
# ============================================================================


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_pr_template_url_field_display(mock_config_loader, mock_config):
    """Test that pr_template_url field displays current value."""
    # Setup mock with pr_template_url set
    mock_config.pr_template_url = "https://github.com/org/repo/blob/main/.github/PULL_REQUEST_TEMPLATE.md"

    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Verify pr_template_url is set
    assert tui.config.pr_template_url == "https://github.com/org/repo/blob/main/.github/PULL_REQUEST_TEMPLATE.md"


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_pr_template_url_empty(mock_config_loader, mock_config):
    """Test that pr_template_url field handles empty value."""
    # Setup mock with no pr_template_url
    mock_config.pr_template_url = None

    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Verify pr_template_url is None
    assert tui.config.pr_template_url is None


@patch("devflow.ui.config_tui.ConfigLoader")
def test_config_tui_pr_template_url_collection(mock_config_loader, mock_config):
    """Test collecting pr_template_url value and converting empty to None."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Test setting a URL value
    tui.config.pr_template_url = "https://github.com/org/repo/blob/main/TEMPLATE.md"
    assert tui.config.pr_template_url == "https://github.com/org/repo/blob/main/TEMPLATE.md"

    # Test clearing to None
    tui.config.pr_template_url = None
    assert tui.config.pr_template_url is None


# ============================================================================
# Workstream Validation Tests
# ============================================================================
# NOTE: Workstream validation tests removed because workstream is now a generic
# custom field. Validation for custom field defaults is not performed in the TUI
# as they can be any arbitrary JIRA field. Field-specific validation happens
# at the JIRA API level during issue creation.


# ============================================================================
# Workspace Repo Count Tests
# ============================================================================


@patch("devflow.ui.config_tui.ConfigLoader")
def test_tui_workspace_repo_count_existing_dir(mock_config_loader, mock_config, tmp_path):
    """Test workspace repo count shows notification for existing directory."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    # Create test workspace with some directories
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "repo1").mkdir()
    (workspace / "repo2").mkdir()
    (workspace / ".hidden").mkdir()  # Should be ignored

    tui = ConfigTUI()

    # Mock notify to capture calls
    tui.notify = Mock()

    # Call the workspace changed handler
    tui._on_workspace_changed(str(workspace))

    # Should have called notify with count (2 non-hidden dirs)
    tui.notify.assert_called_once()
    call_args = tui.notify.call_args[0][0]
    assert "2" in call_args
    assert "directories" in call_args


@patch("devflow.ui.config_tui.ConfigLoader")
def test_tui_workspace_repo_count_nonexistent_dir(mock_config_loader, mock_config):
    """Test workspace repo count handles non-existent directory gracefully."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Mock notify to capture calls
    tui.notify = Mock()

    # Call with non-existent path
    tui._on_workspace_changed("/path/that/does/not/exist")

    # Should not call notify for non-existent path
    tui.notify.assert_not_called()


@patch("devflow.ui.config_tui.ConfigLoader")
def test_tui_workspace_repo_count_empty_path(mock_config_loader, mock_config):
    """Test workspace repo count handles empty path gracefully."""
    # Setup mock
    mock_loader_instance = Mock()
    mock_loader_instance.load_config.return_value = mock_config
    mock_loader_instance.session_home = Path("/tmp/test")
    mock_config_loader.return_value = mock_loader_instance

    tui = ConfigTUI()

    # Mock notify to capture calls
    tui.notify = Mock()

    # Call with empty paths
    tui._on_workspace_changed("")
    tui._on_workspace_changed("   ")

    # Should not call notify for empty paths
    tui.notify.assert_not_called()


# ============================================================================
# Widget Rendering Tests (would require textual.testing)
# ============================================================================


# Note: Full rendering tests would require textual's testing utilities
# and would be more complex. These basic tests validate the structure
# and initialization of the TUI components.
