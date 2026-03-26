"""Tests for agent management commands (Story 7)."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from devflow.config.models import Config, JiraConfig, RepoConfig


@pytest.fixture
def mock_config(tmp_path):
    """Create a test config with agent backend."""
    return Config(
        jira=JiraConfig(url="https://jira.example.com", transitions={}),
        repos=RepoConfig(workspaces=[]),
        agent_backend="claude"
    )


@pytest.fixture
def mock_config_loader(mock_config):
    """Create a mock config loader."""
    from devflow.config.loader import ConfigLoader

    loader = Mock(spec=ConfigLoader)
    loader.load_config.return_value = mock_config
    loader.save_config.return_value = None
    return loader


# Test detect_agent_installation


def test_detect_agent_installation_claude_installed():
    """Test detecting Claude Code when installed."""
    from devflow.cli.commands.agent_commands import detect_agent_installation

    with patch('devflow.cli.commands.agent_commands.shutil.which', return_value="/usr/local/bin/claude"):
        with patch('devflow.cli.commands.agent_commands.get_tool_version', return_value="1.0.0"):
            result = detect_agent_installation("claude")

    assert result["installed"] is True
    assert result["cli_path"] == "/usr/local/bin/claude"
    assert result["version"] == "1.0.0"
    assert result["additional_requirements"] == []


def test_detect_agent_installation_not_installed():
    """Test detecting agent when not installed."""
    from devflow.cli.commands.agent_commands import detect_agent_installation

    with patch('devflow.cli.commands.agent_commands.shutil.which', return_value=None):
        result = detect_agent_installation("claude")

    assert result["installed"] is False
    assert result["cli_path"] is None
    assert result["version"] is None


def test_detect_agent_installation_ollama_missing_claude():
    """Test detecting Ollama when Claude is missing."""
    from devflow.cli.commands.agent_commands import detect_agent_installation

    def mock_which(cmd):
        if cmd == "ollama":
            return "/usr/local/bin/ollama"
        return None

    with patch('devflow.cli.commands.agent_commands.shutil.which', side_effect=mock_which):
        with patch('devflow.cli.commands.agent_commands.get_tool_version', return_value="0.1.0"):
            result = detect_agent_installation("ollama")

    assert result["installed"] is True
    assert result["cli_path"] == "/usr/local/bin/ollama"
    assert "claude (Claude Code CLI)" in result["additional_requirements"]


def test_detect_agent_installation_ollama_all_requirements_met():
    """Test detecting Ollama when all requirements met."""
    from devflow.cli.commands.agent_commands import detect_agent_installation

    def mock_which(cmd):
        return f"/usr/local/bin/{cmd}"

    with patch('devflow.cli.commands.agent_commands.shutil.which', side_effect=mock_which):
        with patch('devflow.cli.commands.agent_commands.get_tool_version', return_value="0.1.0"):
            result = detect_agent_installation("ollama")

    assert result["installed"] is True
    assert result["additional_requirements"] == []


# Test get_all_agents_status


def test_get_all_agents_status():
    """Test getting status of all agents."""
    from devflow.cli.commands.agent_commands import get_all_agents_status

    with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
        mock_detect.return_value = {
            "installed": True,
            "cli_path": "/usr/local/bin/claude",
            "version": "1.0.0",
            "additional_requirements": [],
        }

        result = get_all_agents_status()

    assert "claude" in result
    assert "ollama" in result
    assert "github-copilot" in result
    assert "cursor" in result
    assert "windsurf" in result
    assert "aider" in result
    assert "continue" in result

    # Check structure
    assert result["claude"]["name"] == "Claude Code"
    assert result["claude"]["installed"] is True
    assert result["claude"]["status"] == "fully-tested"


# Test list_agents


def test_list_agents_display(capsys):
    """Test list_agents displays table."""
    from devflow.cli.commands.agent_commands import list_agents

    with patch('devflow.cli.commands.agent_commands.get_all_agents_status') as mock_status:
        with patch('devflow.cli.commands.agent_commands.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = Config(
                jira=JiraConfig(url="https://jira.example.com", transitions={}),
                repos=RepoConfig(workspaces=[]),
                agent_backend="claude"
            )
            mock_status.return_value = {
                "claude": {
                    "name": "Claude Code",
                    "description": "Test description",
                    "status": "fully-tested",
                    "installed": True,
                    "cli_path": "/usr/local/bin/claude",
                    "version": "1.0.0",
                    "cli_command": "claude",
                    "install_url": "https://example.com",
                    "features": {},
                    "notes": None,
                    "additional_requirements": [],
                }
            }

            list_agents(output_json=False)

    captured = capsys.readouterr()
    assert "Claude Code" in captured.out
    assert "Stable" in captured.out or "fully-tested" in captured.out.lower()


def test_list_agents_json():
    """Test list_agents JSON output."""
    from devflow.cli.commands.agent_commands import list_agents

    with patch('devflow.cli.commands.agent_commands.get_all_agents_status') as mock_status:
        with patch('devflow.cli.commands.agent_commands.ConfigLoader') as mock_loader:
            with patch('devflow.cli.utils.output_json') as mock_json:
                mock_loader.return_value.load_config.return_value = Config(
                    jira=JiraConfig(url="https://jira.example.com", transitions={}),
                    repos=RepoConfig(workspaces=[]),
                    agent_backend="claude"
                )
                mock_status.return_value = {"claude": {"installed": True}}

                list_agents(output_json=True)

                mock_json.assert_called_once()
                call_args = mock_json.call_args[1]
                assert call_args["success"] is True
                assert "agents" in call_args["data"]
                assert "default_agent" in call_args["data"]


def test_list_agents_no_config_uses_default():
    """Test list_agents uses default when no config."""
    from devflow.cli.commands.agent_commands import list_agents

    with patch('devflow.cli.commands.agent_commands.get_all_agents_status') as mock_status:
        with patch('devflow.cli.commands.agent_commands.ConfigLoader') as mock_loader:
            with patch('devflow.cli.utils.output_json') as mock_json:
                mock_loader.return_value.load_config.return_value = None
                mock_status.return_value = {}

                list_agents(output_json=True)

                mock_json.assert_called_once()
                call_args = mock_json.call_args[1]
                assert call_args["data"]["default_agent"] == "claude"


# Test set_default_agent


@patch('devflow.cli.commands.agent_commands.require_outside_claude', lambda f: f)
def test_set_default_agent_success(mock_config_loader, capsys):
    """Test setting default agent successfully."""
    from devflow.cli.commands.agent_commands import set_default_agent

    with patch('devflow.cli.commands.agent_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
            mock_detect.return_value = {
                "installed": True,
                "cli_path": "/usr/local/bin/claude",
                "version": "1.0.0",
                "additional_requirements": [],
            }

            set_default_agent("claude", output_json=False)

    captured = capsys.readouterr()
    assert "Default agent set to: Claude Code" in captured.out
    assert mock_config_loader.save_config.called


@patch('devflow.cli.commands.agent_commands.require_outside_claude', lambda f: f)
def test_set_default_agent_invalid_name(mock_config_loader, capsys):
    """Test setting default agent with invalid name."""
    from devflow.cli.commands.agent_commands import set_default_agent

    with patch('devflow.cli.commands.agent_commands.ConfigLoader', return_value=mock_config_loader):
        set_default_agent("invalid-agent", output_json=False)

    captured = capsys.readouterr()
    assert "Invalid agent: invalid-agent" in captured.out
    assert not mock_config_loader.save_config.called


@patch('devflow.cli.commands.agent_commands.require_outside_claude', lambda f: f)
def test_set_default_agent_not_installed(mock_config_loader, capsys):
    """Test setting default agent when not installed."""
    from devflow.cli.commands.agent_commands import set_default_agent

    with patch('devflow.cli.commands.agent_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
            mock_detect.return_value = {
                "installed": False,
                "cli_path": None,
                "version": None,
                "additional_requirements": [],
            }

            set_default_agent("cursor", output_json=False)

    captured = capsys.readouterr()
    assert "is not installed" in captured.out
    assert not mock_config_loader.save_config.called


@patch('devflow.cli.commands.agent_commands.require_outside_claude', lambda f: f)
def test_set_default_agent_missing_requirements(mock_config_loader, capsys):
    """Test setting default agent with missing requirements."""
    from devflow.cli.commands.agent_commands import set_default_agent

    with patch('devflow.cli.commands.agent_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
            mock_detect.return_value = {
                "installed": True,
                "cli_path": "/usr/local/bin/ollama",
                "version": "0.1.0",
                "additional_requirements": ["claude (Claude Code CLI)"],
            }

            set_default_agent("ollama", output_json=False)

    captured = capsys.readouterr()
    assert "Missing requirements:" in captured.out
    assert "claude (Claude Code CLI)" in captured.out
    assert not mock_config_loader.save_config.called


@patch('devflow.cli.commands.agent_commands.require_outside_claude', lambda f: f)
def test_set_default_agent_no_config(capsys):
    """Test setting default agent when no config exists."""
    from devflow.cli.commands.agent_commands import set_default_agent

    mock_loader = Mock()
    mock_loader.load_config.return_value = None

    with patch('devflow.cli.commands.agent_commands.ConfigLoader', return_value=mock_loader):
        with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
            mock_detect.return_value = {
                "installed": True,
                "cli_path": "/usr/local/bin/claude",
                "version": "1.0.0",
                "additional_requirements": [],
            }

            set_default_agent("claude", output_json=False)

    captured = capsys.readouterr()
    assert "No configuration found" in captured.out


@patch('devflow.cli.commands.agent_commands.require_outside_claude', lambda f: f)
def test_set_default_agent_json_success(mock_config_loader):
    """Test setting default agent JSON output."""
    from devflow.cli.commands.agent_commands import set_default_agent

    with patch('devflow.cli.commands.agent_commands.ConfigLoader', return_value=mock_config_loader):
        with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
            with patch('devflow.cli.utils.output_json') as mock_json:
                mock_detect.return_value = {
                    "installed": True,
                    "cli_path": "/usr/local/bin/claude",
                    "version": "1.0.0",
                    "additional_requirements": [],
                }

                set_default_agent("claude", output_json=True)

                mock_json.assert_called_once()
                call_args = mock_json.call_args[1]
                assert call_args["success"] is True
                assert call_args["data"]["agent"] == "claude"


# Test test_agent


def test_test_agent_success(capsys):
    """Test testing agent successfully."""
    from devflow.cli.commands.agent_commands import test_agent

    with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
        mock_detect.return_value = {
            "installed": True,
            "cli_path": "/usr/local/bin/claude",
            "version": "1.0.0",
            "additional_requirements": [],
        }

        test_agent("claude", output_json=False)

    captured = capsys.readouterr()
    assert "Testing Claude Code" in captured.out
    assert "CLI available:" in captured.out
    assert "is ready to use" in captured.out


def test_test_agent_not_installed(capsys):
    """Test testing agent when not installed."""
    from devflow.cli.commands.agent_commands import test_agent

    with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
        mock_detect.return_value = {
            "installed": False,
            "cli_path": None,
            "version": None,
            "additional_requirements": [],
        }

        test_agent("cursor", output_json=False)

    captured = capsys.readouterr()
    assert "Testing Cursor" in captured.out
    assert "CLI not found:" in captured.out
    assert "is not ready" in captured.out


def test_test_agent_missing_requirements(capsys):
    """Test testing agent with missing requirements."""
    from devflow.cli.commands.agent_commands import test_agent

    with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
        mock_detect.return_value = {
            "installed": True,
            "cli_path": "/usr/local/bin/ollama",
            "version": "0.1.0",
            "additional_requirements": ["claude (Claude Code CLI)"],
        }

        test_agent("ollama", output_json=False)

    captured = capsys.readouterr()
    assert "Missing requirements:" in captured.out
    assert "claude (Claude Code CLI)" in captured.out
    assert "is not ready" in captured.out


def test_test_agent_uses_default(capsys):
    """Test testing default agent when no name specified."""
    from devflow.cli.commands.agent_commands import test_agent

    with patch('devflow.cli.commands.agent_commands.ConfigLoader') as mock_loader:
        with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
            mock_loader.return_value.load_config.return_value = Config(
                jira=JiraConfig(url="https://jira.example.com", transitions={}),
                repos=RepoConfig(workspaces=[]),
                agent_backend="claude"
            )
            mock_detect.return_value = {
                "installed": True,
                "cli_path": "/usr/local/bin/claude",
                "version": "1.0.0",
                "additional_requirements": [],
            }

            test_agent(None, output_json=False)

    captured = capsys.readouterr()
    assert "Testing default agent: claude" in captured.out


def test_test_agent_json():
    """Test testing agent JSON output."""
    from devflow.cli.commands.agent_commands import test_agent

    with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
        with patch('devflow.cli.utils.output_json') as mock_json:
            mock_detect.return_value = {
                "installed": True,
                "cli_path": "/usr/local/bin/claude",
                "version": "1.0.0",
                "additional_requirements": [],
            }

            test_agent("claude", output_json=True)

            mock_json.assert_called_once()
            call_args = mock_json.call_args[1]
            assert call_args["success"] is True
            assert call_args["data"]["agent"] == "claude"
            assert call_args["data"]["tests"]["cli_available"] is True
            assert call_args["data"]["tests"]["requirements_met"] is True


# Test show_agent_info


def test_show_agent_info_success(capsys):
    """Test showing agent info successfully."""
    from devflow.cli.commands.agent_commands import show_agent_info

    with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
        mock_detect.return_value = {
            "installed": True,
            "cli_path": "/usr/local/bin/claude",
            "version": "1.0.0",
            "additional_requirements": [],
        }

        show_agent_info("claude", output_json=False)

    captured = capsys.readouterr()
    assert "Claude Code" in captured.out
    assert "Installed:" in captured.out
    assert "Supported Features:" in captured.out


def test_show_agent_info_not_installed(capsys):
    """Test showing agent info when not installed."""
    from devflow.cli.commands.agent_commands import show_agent_info

    with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
        mock_detect.return_value = {
            "installed": False,
            "cli_path": None,
            "version": None,
            "additional_requirements": [],
        }

        show_agent_info("cursor", output_json=False)

    captured = capsys.readouterr()
    assert "Cursor" in captured.out
    assert "Not installed" in captured.out
    assert "Installation:" in captured.out


def test_show_agent_info_with_notes(capsys):
    """Test showing agent info with notes."""
    from devflow.cli.commands.agent_commands import show_agent_info

    with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
        mock_detect.return_value = {
            "installed": True,
            "cli_path": "/usr/local/bin/ollama",
            "version": "0.1.0",
            "additional_requirements": [],
        }

        show_agent_info("ollama", output_json=False)

    captured = capsys.readouterr()
    assert "Notes:" in captured.out
    assert "Requires both 'ollama' and 'claude' CLI tools" in captured.out


def test_show_agent_info_uses_default(capsys):
    """Test showing default agent info when no name specified."""
    from devflow.cli.commands.agent_commands import show_agent_info

    with patch('devflow.cli.commands.agent_commands.ConfigLoader') as mock_loader:
        with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
            mock_loader.return_value.load_config.return_value = Config(
                jira=JiraConfig(url="https://jira.example.com", transitions={}),
                repos=RepoConfig(workspaces=[]),
                agent_backend="claude"
            )
            mock_detect.return_value = {
                "installed": True,
                "cli_path": "/usr/local/bin/claude",
                "version": "1.0.0",
                "additional_requirements": [],
            }

            show_agent_info(None, output_json=False)

    captured = capsys.readouterr()
    assert "Showing default agent: claude" in captured.out


def test_show_agent_info_json():
    """Test showing agent info JSON output."""
    from devflow.cli.commands.agent_commands import show_agent_info

    with patch('devflow.cli.commands.agent_commands.detect_agent_installation') as mock_detect:
        with patch('devflow.cli.utils.output_json') as mock_json:
            mock_detect.return_value = {
                "installed": True,
                "cli_path": "/usr/local/bin/claude",
                "version": "1.0.0",
                "additional_requirements": [],
            }

            show_agent_info("claude", output_json=True)

            mock_json.assert_called_once()
            call_args = mock_json.call_args[1]
            assert call_args["success"] is True
            assert call_args["data"]["agent"] == "claude"
            assert call_args["data"]["name"] == "Claude Code"
            assert "features" in call_args["data"]


def test_show_agent_info_invalid_agent(capsys):
    """Test showing info for invalid agent."""
    from devflow.cli.commands.agent_commands import show_agent_info

    show_agent_info("invalid-agent", output_json=False)

    captured = capsys.readouterr()
    assert "Invalid agent: invalid-agent" in captured.out
