"""Tests for model provider profile management commands."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from devflow.config.models import Config, JiraConfig, RepoConfig, ModelProviderConfig, ModelProviderProfile


@pytest.fixture
def mock_config():
    """Create a test config with model provider profiles."""
    return Config(
        jira=JiraConfig(url="https://jira.example.com", transitions={}),
        repos=RepoConfig(),
        model_provider=ModelProviderConfig(
            default_profile="anthropic",
            profiles={
                "anthropic": ModelProviderProfile(name="anthropic"),
                "vertex": ModelProviderProfile(
                    name="vertex",
                    use_vertex=True,
                    vertex_project_id="my-project-123",
                    vertex_region="us-east5",
                ),
                "llama-cpp": ModelProviderProfile(
                    name="llama-cpp",
                    base_url="http://localhost:8000",
                    auth_token="llama-cpp",
                    api_key="",
                    model_name="devstral-small-2",
                ),
            }
        )
    )


@pytest.fixture
def mock_config_loader(mock_config):
    """Create a mock config loader."""
    from devflow.config.loader import ConfigLoader

    loader = Mock(spec=ConfigLoader)
    loader.load_config.return_value = mock_config
    loader.save_config.return_value = None
    return loader


def test_list_profiles_success(mock_config_loader, capsys):
    """Test listing model provider profiles successfully."""
    from devflow.cli.commands.provider_commands import list_profiles

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        list_profiles(output_json=False)

    captured = capsys.readouterr()
    assert "anthropic" in captured.out
    assert "vertex" in captured.out
    assert "llama-cpp" in captured.out


def test_list_profiles_json(mock_config_loader, capsys):
    """Test listing profiles with JSON output."""
    from devflow.cli.commands.provider_commands import list_profiles

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        list_profiles(output_json=True)

    captured = capsys.readouterr()
    assert '"success": true' in captured.out
    assert '"default_profile": "anthropic"' in captured.out


def test_list_profiles_no_config(capsys):
    """Test listing profiles when no config exists."""
    from devflow.cli.commands.provider_commands import list_profiles

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_loader):
        list_profiles(output_json=False)

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


def test_list_profiles_empty(mock_config_loader, capsys):
    """Test listing profiles when none configured."""
    from devflow.cli.commands.provider_commands import list_profiles

    # Clear profiles
    mock_config_loader.load_config.return_value.model_provider.profiles = {}

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        list_profiles(output_json=False)

    captured = capsys.readouterr()
    assert "No model provider profiles configured" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_add_profile_anthropic(mock_config_loader, capsys):
    """Test adding Anthropic profile."""
    from devflow.cli.commands.provider_commands import add_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.provider_commands.Prompt.ask') as mock_prompt:
            with patch('devflow.cli.commands.provider_commands.Confirm.ask') as mock_confirm:
                # Simulate interactive input
                mock_prompt.side_effect = [
                    "openrouter",  # name
                    "1",  # provider type (Anthropic)
                    "",  # model_name (empty)
                ]
                mock_confirm.return_value = False  # Not default

                add_profile(name=None, interactive=True, output_json=False)

    captured = capsys.readouterr()
    assert "Added profile: openrouter" in captured.out
    assert mock_config_loader.save_config.called


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_add_profile_vertex(mock_config_loader, capsys):
    """Test adding Vertex AI profile."""
    from devflow.cli.commands.provider_commands import add_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.provider_commands.Prompt.ask') as mock_prompt:
            with patch('devflow.cli.commands.provider_commands.Confirm.ask') as mock_confirm:
                # Simulate interactive input for Vertex AI
                mock_prompt.side_effect = [
                    "my-vertex",  # name
                    "2",  # provider type (Vertex AI)
                    "my-gcp-project",  # project_id
                    "us-central1",  # region
                    "",  # model_name (empty)
                ]
                mock_confirm.return_value = False  # Not default

                add_profile(name=None, interactive=True, output_json=False)

    captured = capsys.readouterr()
    assert "Added profile: my-vertex" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_add_profile_llama_cpp(mock_config_loader, capsys):
    """Test adding llama.cpp profile."""
    from devflow.cli.commands.provider_commands import add_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.provider_commands.Prompt.ask') as mock_prompt:
            with patch('devflow.cli.commands.provider_commands.Confirm.ask') as mock_confirm:
                # Simulate interactive input for llama.cpp
                mock_prompt.side_effect = [
                    "local-llama",  # name
                    "3",  # provider type (llama.cpp)
                    "http://localhost:8001",  # base_url
                    "my-model",  # model_name
                ]
                mock_confirm.return_value = False  # Not default

                add_profile(name=None, interactive=True, output_json=False)

    captured = capsys.readouterr()
    assert "Added profile: local-llama" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_add_profile_custom(mock_config_loader, capsys):
    """Test adding custom provider profile."""
    from devflow.cli.commands.provider_commands import add_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.provider_commands.Prompt.ask') as mock_prompt:
            with patch('devflow.cli.commands.provider_commands.Confirm.ask') as mock_confirm:
                # Simulate interactive input for custom provider
                mock_prompt.side_effect = [
                    "custom-provider",  # name
                    "4",  # provider type (Custom)
                    "https://api.custom.com",  # base_url
                    "my-token",  # auth_token
                    "my-api-key",  # api_key
                    "gpt-4",  # model_name
                ]
                mock_confirm.return_value = False  # Not default

                add_profile(name=None, interactive=True, output_json=False)

    captured = capsys.readouterr()
    assert "Added profile: custom-provider" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_add_profile_no_config(capsys):
    """Test adding profile when no config exists."""
    from devflow.cli.commands.provider_commands import add_profile

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_loader):
        add_profile(name="test", interactive=False, output_json=False)

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_add_profile_already_exists(mock_config_loader, capsys):
    """Test adding profile with duplicate name."""
    from devflow.cli.commands.provider_commands import add_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        add_profile(name="anthropic", interactive=False, output_json=False)

    captured = capsys.readouterr()
    assert "Profile already exists: anthropic" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_add_profile_empty_name(mock_config_loader, capsys):
    """Test adding profile with empty name."""
    from devflow.cli.commands.provider_commands import add_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        add_profile(name="", interactive=False, output_json=False)

    captured = capsys.readouterr()
    assert "Profile name cannot be empty" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_remove_profile_success(mock_config_loader, capsys):
    """Test removing a profile successfully."""
    from devflow.cli.commands.provider_commands import remove_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.provider_commands.Confirm.ask', return_value=True):
            remove_profile(name="llama-cpp", output_json=False)

    captured = capsys.readouterr()
    assert "Removed profile: llama-cpp" in captured.out
    assert mock_config_loader.save_config.called


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_remove_profile_no_config(capsys):
    """Test removing profile when no config exists."""
    from devflow.cli.commands.provider_commands import remove_profile

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_loader):
        remove_profile(name="test", output_json=False)

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_remove_profile_not_found(mock_config_loader, capsys):
    """Test removing non-existent profile."""
    from devflow.cli.commands.provider_commands import remove_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.provider_commands.Confirm.ask', return_value=True):
            remove_profile(name="nonexistent", output_json=False)

    captured = capsys.readouterr()
    assert "Profile not found: nonexistent" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_remove_profile_cancel(mock_config_loader, capsys):
    """Test canceling profile removal."""
    from devflow.cli.commands.provider_commands import remove_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.provider_commands.Confirm.ask', return_value=False):
            remove_profile(name="vertex", output_json=False)

    captured = capsys.readouterr()
    assert "Cancelled" in captured.out
    assert not mock_config_loader.save_config.called


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_remove_default_profile_sets_new_default(mock_config_loader, capsys):
    """Test removing default profile sets new default."""
    from devflow.cli.commands.provider_commands import remove_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.provider_commands.Confirm.ask', return_value=True):
            remove_profile(name="anthropic", output_json=False)

    captured = capsys.readouterr()
    assert "Removed profile: anthropic" in captured.out
    assert "new default" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_set_default_profile_success(mock_config_loader, capsys):
    """Test setting default profile successfully."""
    from devflow.cli.commands.provider_commands import set_default_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        set_default_profile(name="vertex", output_json=False)

    captured = capsys.readouterr()
    assert "Set 'vertex' as default profile" in captured.out
    assert mock_config_loader.save_config.called


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_set_default_profile_no_config(capsys):
    """Test setting default profile when no config exists."""
    from devflow.cli.commands.provider_commands import set_default_profile

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_loader):
        set_default_profile(name="test", output_json=False)

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_set_default_profile_not_found(mock_config_loader, capsys):
    """Test setting non-existent profile as default."""
    from devflow.cli.commands.provider_commands import set_default_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        set_default_profile(name="nonexistent", output_json=False)

    captured = capsys.readouterr()
    assert "Profile not found: nonexistent" in captured.out


@patch('devflow.cli.commands.provider_commands.require_outside_claude', lambda f: f)
def test_set_default_profile_already_default(mock_config_loader, capsys):
    """Test setting already-default profile."""
    from devflow.cli.commands.provider_commands import set_default_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        set_default_profile(name="anthropic", output_json=False)

    captured = capsys.readouterr()
    assert "already the default" in captured.out


def test_show_profile_success(mock_config_loader, capsys):
    """Test showing profile configuration."""
    from devflow.cli.commands.provider_commands import show_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        show_profile(name="vertex", output_json=False)

    captured = capsys.readouterr()
    assert "Profile: vertex" in captured.out
    assert "Vertex AI" in captured.out
    assert "my-project-123" in captured.out


def test_show_profile_default(mock_config_loader, capsys):
    """Test showing default profile when name not provided."""
    from devflow.cli.commands.provider_commands import show_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        show_profile(name=None, output_json=False)

    captured = capsys.readouterr()
    assert "Profile: anthropic" in captured.out
    assert "Default profile" in captured.out


def test_show_profile_json(mock_config_loader, capsys):
    """Test showing profile with JSON output."""
    from devflow.cli.commands.provider_commands import show_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        show_profile(name="llama-cpp", output_json=True)

    captured = capsys.readouterr()
    assert '"success": true' in captured.out
    assert '"name": "llama-cpp"' in captured.out


def test_show_profile_no_config(capsys):
    """Test showing profile when no config exists."""
    from devflow.cli.commands.provider_commands import show_profile

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_loader):
        show_profile(name="test", output_json=False)

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


def test_show_profile_not_found(mock_config_loader, capsys):
    """Test showing non-existent profile."""
    from devflow.cli.commands.provider_commands import show_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        show_profile(name="nonexistent", output_json=False)

    captured = capsys.readouterr()
    assert "Profile not found: nonexistent" in captured.out


def test_test_profile_success(mock_config_loader, capsys):
    """Test validating a profile successfully."""
    from devflow.cli.commands.provider_commands import test_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        test_profile(name="vertex", output_json=False)

    captured = capsys.readouterr()
    assert "Profile configuration is valid" in captured.out


def test_test_profile_validation_issues(mock_config_loader, capsys):
    """Test profile with validation issues."""
    from devflow.cli.commands.provider_commands import test_profile

    # Create profile with issues
    invalid_profile = ModelProviderProfile(
        name="invalid",
        use_vertex=True,
        vertex_project_id=None,  # Missing required field
    )
    mock_config_loader.load_config.return_value.model_provider.profiles["invalid"] = invalid_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        test_profile(name="invalid", output_json=False)

    captured = capsys.readouterr()
    assert "Validation failed" in captured.out
    assert "vertex_project_id not set" in captured.out


def test_test_profile_invalid_url(mock_config_loader, capsys):
    """Test profile with invalid base URL."""
    from devflow.cli.commands.provider_commands import test_profile

    # Create profile with invalid URL
    invalid_profile = ModelProviderProfile(
        name="invalid-url",
        base_url="not-a-url",  # Invalid format
    )
    mock_config_loader.load_config.return_value.model_provider.profiles["invalid-url"] = invalid_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        test_profile(name="invalid-url", output_json=False)

    captured = capsys.readouterr()
    assert "Validation failed" in captured.out
    assert "Invalid base_url format" in captured.out


def test_test_profile_json(mock_config_loader, capsys):
    """Test profile validation with JSON output."""
    from devflow.cli.commands.provider_commands import test_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        test_profile(name="vertex", output_json=True)

    captured = capsys.readouterr()
    assert '"success": true' in captured.out
    assert '"valid": true' in captured.out


def test_test_profile_no_config(capsys):
    """Test testing profile when no config exists."""
    from devflow.cli.commands.provider_commands import test_profile

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_loader):
        test_profile(name="test", output_json=False)

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


def test_test_profile_not_found(mock_config_loader, capsys):
    """Test testing non-existent profile."""
    from devflow.cli.commands.provider_commands import test_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        test_profile(name="nonexistent", output_json=False)

    captured = capsys.readouterr()
    assert "Profile not found: nonexistent" in captured.out


def test_test_profile_default(mock_config_loader, capsys):
    """Test testing default profile when name not provided."""
    from devflow.cli.commands.provider_commands import test_profile

    with patch('devflow.cli.commands.provider_commands.ConfigLoader', return_value=mock_config_loader):
        test_profile(name=None, output_json=False)

    captured = capsys.readouterr()
    assert "Testing profile: anthropic" in captured.out
