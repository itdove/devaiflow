"""Tests for repository selection in 'daf jira new' command (PROJ-61069)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from devflow.cli.commands.jira_new_command import _prompt_for_repository_selection
from devflow.config.loader import ConfigLoader


@pytest.fixture
def mock_workspace(tmp_path):
    """Create a mock workspace with test repositories."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create test repositories
    (workspace / "repo1").mkdir()
    (workspace / "repo2").mkdir()
    (workspace / "repo3").mkdir()

    return workspace


@pytest.fixture
def mock_config(mock_workspace, temp_daf_home):
    """Create a mock config with workspace path."""
    config_loader = ConfigLoader()
    config_loader.create_default_config()

    config = config_loader.load_config()
    config.repos.workspace = str(mock_workspace)
    config_loader.save_config(config)

    return config


def test_empty_input_returns_none_with_error(mock_workspace, mock_config, monkeypatch):
    """Test that pressing Enter without input shows error and returns None (PROJ-61069)."""
    from rich.prompt import Prompt

    # Mock Prompt.ask to simulate empty input (pressing Enter)
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "")

    # Mock console to capture output
    console_output = []
    original_print = Console.print

    def mock_print(self, *args, **kwargs):
        if args:
            console_output.append(str(args[0]))
        return original_print(self, *args, **kwargs)

    monkeypatch.setattr(Console, "print", mock_print)

    # Call the function
    result = _prompt_for_repository_selection(config=mock_config)

    # Verify: Returns None
    assert result is None

    # Verify: Error message was shown
    error_messages = [msg for msg in console_output if "Empty selection not allowed" in msg]
    assert len(error_messages) > 0, f"Expected error message about empty selection, got: {console_output}"


def test_whitespace_input_returns_none_with_error(mock_workspace, mock_config, monkeypatch):
    """Test that entering only whitespace shows error and returns None (PROJ-61069)."""
    from rich.prompt import Prompt

    # Mock Prompt.ask to simulate whitespace input
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "   ")

    # Mock console to capture output
    console_output = []
    original_print = Console.print

    def mock_print(self, *args, **kwargs):
        if args:
            console_output.append(str(args[0]))
        return original_print(self, *args, **kwargs)

    monkeypatch.setattr(Console, "print", mock_print)

    # Call the function
    result = _prompt_for_repository_selection(config=mock_config)

    # Verify: Returns None
    assert result is None

    # Verify: Error message was shown
    error_messages = [msg for msg in console_output if "Empty selection not allowed" in msg]
    assert len(error_messages) > 0


def test_valid_number_selection_succeeds(mock_workspace, mock_config, monkeypatch):
    """Test that selecting a valid number returns the correct repository path."""
    from rich.prompt import Prompt

    # Mock Prompt.ask to simulate selecting first repository
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "1")

    # Call the function
    result = _prompt_for_repository_selection(config=mock_config)

    # Verify: Returns path to first repository
    assert result is not None
    assert "repo1" in result or "repo2" in result or "repo3" in result


def test_cancel_returns_none(mock_workspace, mock_config, monkeypatch):
    """Test that entering 'cancel' returns None."""
    from rich.prompt import Prompt

    # Mock Prompt.ask to simulate cancel
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "cancel")

    # Call the function
    result = _prompt_for_repository_selection(config=mock_config)

    # Verify: Returns None (user cancelled)
    assert result is None


def test_valid_repo_name_succeeds(mock_workspace, mock_config, monkeypatch):
    """Test that entering a valid repository name returns the correct path."""
    from rich.prompt import Prompt, Confirm

    # Mock Prompt.ask to simulate entering repository name
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "repo2")

    # Mock Confirm.ask to always return True (use the path)
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: True)

    # Call the function
    result = _prompt_for_repository_selection(config=mock_config)

    # Verify: Returns path to repo2
    assert result is not None
    assert "repo2" in result


def test_invalid_number_returns_none(mock_workspace, mock_config, monkeypatch):
    """Test that selecting an invalid number shows error and returns None."""
    from rich.prompt import Prompt

    # Mock Prompt.ask to simulate invalid number (out of range)
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "999")

    # Mock console to capture output
    console_output = []
    original_print = Console.print

    def mock_print(self, *args, **kwargs):
        if args:
            console_output.append(str(args[0]))
        return original_print(self, *args, **kwargs)

    monkeypatch.setattr(Console, "print", mock_print)

    # Call the function
    result = _prompt_for_repository_selection(config=mock_config)

    # Verify: Returns None
    assert result is None

    # Verify: Error message was shown
    error_messages = [msg for msg in console_output if "Invalid selection" in msg]
    assert len(error_messages) > 0
