"""Tests for unified project selection used by 'daf jira new' and other commands."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from devflow.cli.utils import unified_project_selection
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


def test_empty_input_uses_default(mock_workspace, monkeypatch):
    """Test that pressing Enter without input uses the default selection (first repository)."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: kwargs.get('default', ''))

    result, is_multi = unified_project_selection(
        workspace_path=str(mock_workspace),
        repo_options=["repo1", "repo2", "repo3"],
    )

    assert result is not None
    assert len(result) == 1
    assert "repo1" in result[0]
    assert is_multi is False


def test_whitespace_input_returns_none_with_error(mock_workspace, monkeypatch):
    """Test that entering only whitespace shows error and returns None."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "   ")

    console_output = []
    original_print = Console.print

    def mock_print(self, *args, **kwargs):
        if args:
            console_output.append(str(args[0]))
        return original_print(self, *args, **kwargs)

    monkeypatch.setattr(Console, "print", mock_print)

    result, is_multi = unified_project_selection(
        workspace_path=str(mock_workspace),
        repo_options=["repo1", "repo2", "repo3"],
    )

    assert result is None
    error_messages = [msg for msg in console_output if "Empty selection not allowed" in msg]
    assert len(error_messages) > 0


def test_valid_number_selection_succeeds(mock_workspace, monkeypatch):
    """Test that selecting a valid number returns the correct repository path."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "1")

    result, is_multi = unified_project_selection(
        workspace_path=str(mock_workspace),
        repo_options=["repo1", "repo2", "repo3"],
    )

    assert result is not None
    assert len(result) == 1
    assert "repo1" in result[0]


def test_cancel_returns_none(mock_workspace, monkeypatch):
    """Test that entering 'cancel' returns None."""
    from rich.prompt import Prompt

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "cancel")

    result, is_multi = unified_project_selection(
        workspace_path=str(mock_workspace),
        repo_options=["repo1", "repo2", "repo3"],
    )

    assert result is None


def test_valid_repo_name_succeeds(mock_workspace, monkeypatch):
    """Test that entering a valid repository name returns the correct path."""
    from rich.prompt import Prompt, Confirm

    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "repo2")
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: True)

    result, is_multi = unified_project_selection(
        workspace_path=str(mock_workspace),
        repo_options=["repo1", "repo2", "repo3"],
    )

    assert result is not None
    assert "repo2" in result[0]


def test_invalid_number_returns_none(mock_workspace, monkeypatch):
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

    result, is_multi = unified_project_selection(
        workspace_path=str(mock_workspace),
        repo_options=["repo1", "repo2", "repo3"],
    )

    assert result is None
    error_messages = [msg for msg in console_output if "Invalid selection" in msg]
    assert len(error_messages) > 0
