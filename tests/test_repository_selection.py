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


def _get_path(result):
    """Extract path from _suggest_and_select_repository result (now returns tuple)."""
    if result is None:
        return None
    paths, is_multi = result
    if paths is None:
        return None
    return paths[0] if paths else None


def test_empty_input_uses_default(mock_workspace, mock_config_loader, monkeypatch):
    """Test that pressing Enter without input uses the default selection (first repository)."""
    from rich.prompt import Prompt

    def mock_ask(prompt, **kwargs):
        return kwargs.get('default', '')

    monkeypatch.setattr(Prompt, "ask", mock_ask)

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path is not None
    assert "repo1" in path or "repo2" in path or "repo3" in path


def test_whitespace_input_returns_none_with_error(mock_workspace, mock_config_loader, monkeypatch):
    """Test that entering only whitespace shows error and returns None (PROJ-61069)."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "   ")

    console_output = []
    original_print = Console.print

    def mock_print(self, *args, **kwargs):
        if args:
            console_output.append(str(args[0]))
        return original_print(self, *args, **kwargs)

    monkeypatch.setattr(Console, "print", mock_print)

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path is None

    error_messages = [msg for msg in console_output if "Empty selection not allowed" in msg]
    assert len(error_messages) > 0


def test_valid_number_selection_succeeds(mock_workspace, mock_config_loader, monkeypatch):
    """Test that selecting a valid number returns the correct repository."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "1")

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path is not None
    assert "repo1" in path or "repo2" in path or "repo3" in path


def test_cancel_returns_none(mock_workspace, mock_config_loader, monkeypatch):
    """Test that entering 'cancel' returns None."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "cancel")

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path is None


def test_q_returns_none(mock_workspace, mock_config_loader, monkeypatch):
    """Test that entering 'q' returns None (alias for cancel)."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "q")

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path is None


def test_invalid_number_returns_none(mock_workspace, mock_config_loader, monkeypatch):
    """Test that selecting an invalid number shows error and returns None."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "999")

    console_output = []
    original_print = Console.print

    def mock_print(self, *args, **kwargs):
        if args:
            console_output.append(str(args[0]))
        return original_print(self, *args, **kwargs)

    monkeypatch.setattr(Console, "print", mock_print)

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path is None

    error_messages = [msg for msg in console_output if "Invalid selection" in msg]
    assert len(error_messages) > 0


def test_valid_repo_name_succeeds(mock_workspace, mock_config_loader, monkeypatch):
    """Test that entering a valid repository name returns the correct path."""
    from rich.prompt import Prompt, Confirm

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "repo2")
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: True)

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path is not None
    assert "repo2" in path


def test_absolute_path_succeeds(mock_workspace, mock_config_loader, monkeypatch, tmp_path):
    """Test that entering an absolute path works correctly."""
    from rich.prompt import Prompt

    test_path = tmp_path / "custom-repo"
    test_path.mkdir()

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: str(test_path))

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path == str(test_path)


def test_tilde_path_succeeds(mock_workspace, mock_config_loader, monkeypatch, tmp_path):
    """Test that entering a path with tilde (~) works correctly."""
    from rich.prompt import Prompt, Confirm

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "~/test-repo")
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: True)

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path is not None
    assert "~" not in path


def test_empty_input_error_message_includes_valid_options(mock_workspace, mock_config_loader, monkeypatch):
    """Test that error message for empty input includes all valid selection options (PROJ-61069)."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "")

    console_output = []
    original_print = Console.print

    def mock_print(self, *args, **kwargs):
        if args:
            console_output.append(str(args[0]))
        return original_print(self, *args, **kwargs)

    monkeypatch.setattr(Console, "print", mock_print)

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    path = _get_path(result)
    assert path is None

    error_messages = [msg for msg in console_output if "Empty selection not allowed" in msg]
    assert len(error_messages) > 0

    error_msg = error_messages[0]
    assert "number" in error_msg.lower()
    assert "repository name" in error_msg.lower() or "path" in error_msg.lower()
    assert "cancel" in error_msg.lower()


def test_default_selection_displayed_and_used(mock_workspace, mock_config_loader, monkeypatch):
    """Test that default selection is shown in prompt and used when Enter is pressed."""
    from rich.prompt import Prompt

    captured_default = {}

    def mock_ask(prompt, **kwargs):
        captured_default['value'] = kwargs.get('default')
        return kwargs.get('default', '')

    monkeypatch.setattr(Prompt, "ask", mock_ask)

    result = _suggest_and_select_repository(
        config_loader=mock_config_loader,
        issue_key=None,
        issue_metadata_dict=None,
    )

    assert captured_default.get('value') == "1"

    path = _get_path(result)
    assert path is not None
    assert "repo1" in path or "repo2" in path or "repo3" in path
