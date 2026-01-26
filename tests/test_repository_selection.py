"""Tests for repository selection prompt in 'daf new' command (PROJ-61069)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from devflow.cli.commands.new_command import _suggest_and_select_repository
from devflow.config.loader import ConfigLoader


@pytest.fixture
def mock_workspace(tmp_path):
    """Create a mock workspace with test repositories."""
    import subprocess
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create test repositories as git repos
    for repo_name in ["repo1", "repo2", "repo3"]:
        repo_path = workspace / repo_name
        repo_path.mkdir()
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)

    return workspace


@pytest.fixture
def mock_config_loader(mock_workspace, temp_daf_home):
    """Create a mock config loader with workspace path."""
    from devflow.config.models import WorkspaceDefinition

    config_loader = ConfigLoader()
    config_loader.create_default_config()

    config = config_loader.load_config()
    config.repos.workspaces = [
        WorkspaceDefinition(name="default", path=str(mock_workspace))
    ]
    config.repos.last_used_workspace = "default"
    config_loader.save_config(config)

    return config_loader


def test_empty_input_returns_none_with_error(mock_workspace, mock_config_loader, monkeypatch):
    """Test that pressing Enter without input shows error and returns None (PROJ-61069)."""
    from rich.prompt import Prompt

    # Mock Prompt.ask to simulate empty input (pressing Enter)
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "")

    # Mock console to capture output
    console_output = []
    original_print = Console.print

    def mock_print(self, *args, **kwargs):
        # Capture the output
        if args:
            console_output.append(str(args[0]))
        return original_print(self, *args, **kwargs)

    monkeypatch.setattr(Console, "print", mock_print)

    # Call the function
    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    # Verify: Returns None
    assert result is None

    # Verify: Error message was shown
    error_messages = [msg for msg in console_output if "Empty selection not allowed" in msg]
    assert len(error_messages) > 0, f"Expected error message about empty selection, got: {console_output}"


def test_whitespace_input_returns_none_with_error(mock_workspace, mock_config_loader, monkeypatch):
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
    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    # Verify: Returns None
    assert result is None

    # Verify: Error message was shown
    error_messages = [msg for msg in console_output if "Empty selection not allowed" in msg]
    assert len(error_messages) > 0


def test_valid_number_selection_succeeds(mock_workspace, mock_config_loader, monkeypatch):
    """Test that selecting a valid number returns the correct repository."""
    from rich.prompt import Prompt

    # Mock Prompt.ask to simulate selecting first repository
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "1")

    # Call the function
    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    # Verify: Returns path to first repository
    assert result is not None
    assert "repo1" in result or "repo2" in result or "repo3" in result


def test_cancel_returns_none(mock_workspace, mock_config_loader, monkeypatch):
    """Test that entering 'cancel' returns None."""
    from rich.prompt import Prompt

    # Mock Prompt.ask to simulate cancel
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "cancel")

    # Call the function
    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    # Verify: Returns None (use current directory)
    assert result is None


def test_invalid_number_returns_none(mock_workspace, mock_config_loader, monkeypatch):
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
    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    # Verify: Returns None
    assert result is None

    # Verify: Error message was shown
    error_messages = [msg for msg in console_output if "Invalid selection" in msg]
    assert len(error_messages) > 0


def test_valid_repo_name_succeeds(mock_workspace, mock_config_loader, monkeypatch):
    """Test that entering a valid repository name returns the correct path."""
    from rich.prompt import Prompt, Confirm

    # Mock Prompt.ask to simulate entering repository name
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "repo2")

    # Mock Confirm.ask to always return True (use the path)
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: True)

    # Call the function
    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    # Verify: Returns path to repo2
    assert result is not None
    assert "repo2" in result


def test_absolute_path_succeeds(mock_workspace, mock_config_loader, monkeypatch, tmp_path):
    """Test that entering an absolute path works correctly."""
    from rich.prompt import Prompt

    # Create a test directory
    test_path = tmp_path / "custom-repo"
    test_path.mkdir()

    # Mock Prompt.ask to simulate entering absolute path
    monkeypatch.setattr(Prompt, "ask", lambda prompt: str(test_path))

    # Call the function
    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    # Verify: Returns the absolute path
    assert result == str(test_path)


def test_tilde_path_succeeds(mock_workspace, mock_config_loader, monkeypatch, tmp_path):
    """Test that entering a path with tilde (~) works correctly."""
    from rich.prompt import Prompt, Confirm

    # Mock Prompt.ask to simulate entering tilde path
    monkeypatch.setattr(Prompt, "ask", lambda prompt: "~/test-repo")

    # Mock Confirm.ask to return True if path doesn't exist
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: True)

    # Call the function
    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    # Verify: Returns expanded path (not None)
    assert result is not None
    assert "~" not in result  # Tilde should be expanded


def test_empty_input_error_message_includes_valid_options(mock_workspace, mock_config_loader, monkeypatch):
    """Test that error message for empty input includes all valid selection options (PROJ-61069)."""
    from rich.prompt import Prompt

    # Mock Prompt.ask to simulate empty input
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
    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    # Verify: Returns None
    assert result is None

    # Verify: Error message includes all valid options
    error_messages = [msg for msg in console_output if "Empty selection not allowed" in msg]
    assert len(error_messages) > 0

    # Check that error message mentions valid options
    error_msg = error_messages[0]
    assert "number" in error_msg.lower()
    assert "repository name" in error_msg.lower() or "path" in error_msg.lower()
    assert "cancel" in error_msg.lower()
