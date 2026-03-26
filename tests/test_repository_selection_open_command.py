"""Tests for repository selection in 'daf open' command (PROJ-61069)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from devflow.cli.commands.open_command import _prompt_for_working_directory
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


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


@pytest.fixture
def mock_session(mock_workspace, temp_daf_home):
    """Create a mock session for testing."""
    from devflow.session.manager import SessionManager
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a test session without conversations to simulate a session without working directory
    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        issue_key=None,
        # Don't pass project_path so no conversation is created
    )

    return session


def test_empty_input_uses_default(mock_workspace, mock_config_loader, mock_session, monkeypatch):
    """Test that pressing Enter without input uses the default selection (first repository)."""
    from rich.prompt import Prompt, Confirm

    # Mock Confirm.ask to decline multi-project mode (Issue #177)
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: False)

    # Mock Prompt.ask to simulate empty input (pressing Enter) - returns default
    def mock_ask(prompt, **kwargs):
        # When user presses Enter, Prompt.ask returns the default value
        return kwargs.get('default', '')

    monkeypatch.setattr(Prompt, "ask", mock_ask)

    # Create session manager
    session_manager = SessionManager(mock_config_loader)

    # Call the function
    result = _prompt_for_working_directory(
        session=mock_session,
        config_loader=mock_config_loader,
        session_manager=session_manager,
    )

    # Verify: Returns True (successfully set working directory using default)
    assert result is True


def test_whitespace_input_returns_false_with_error(mock_workspace, mock_config_loader, mock_session, monkeypatch):
    """Test that entering only whitespace shows error and returns False (PROJ-61069)."""
    from rich.prompt import Prompt, Confirm

    # Mock Confirm.ask to decline multi-project mode (Issue #177)
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: False)

    # Mock Prompt.ask to simulate whitespace input
    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "   ")

    # Create session manager
    session_manager = SessionManager(mock_config_loader)

    # Call the function
    result = _prompt_for_working_directory(
        session=mock_session,
        config_loader=mock_config_loader,
        session_manager=session_manager,
    )

    # Verify: Returns False (function handled whitespace input gracefully)
    assert result is False
    # Note: Error message is shown in console output, verified manually in test run


def test_valid_number_selection_succeeds(mock_workspace, mock_config_loader, mock_session, monkeypatch):
    """Test that selecting a valid number returns True."""
    from rich.prompt import Prompt, Confirm

    # Mock Confirm.ask to decline multi-project mode (Issue #177)
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: False)

    # Mock Prompt.ask to simulate selecting first repository
    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "1")

    # Create session manager
    session_manager = SessionManager(mock_config_loader)

    # Call the function
    result = _prompt_for_working_directory(
        session=mock_session,
        config_loader=mock_config_loader,
        session_manager=session_manager,
    )

    # Verify: Returns True (successfully set working directory)
    assert result is True

    # Verify: Session was updated with selected path in active conversation
    updated_session = session_manager.get_session(mock_session.name)
    assert updated_session.active_conversation is not None, "Expected session to have an active conversation"
    assert updated_session.active_conversation.project_path is not None, "Expected project_path to be set in active conversation"


def test_cancel_returns_false(mock_workspace, mock_config_loader, mock_session, monkeypatch):
    """Test that entering 'cancel' returns False."""
    from rich.prompt import Prompt, Confirm

    # Mock Confirm.ask to decline multi-project mode (Issue #177)
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: False)

    # Mock Prompt.ask to simulate cancel
    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "cancel")

    # Create session manager
    session_manager = SessionManager(mock_config_loader)

    # Call the function
    result = _prompt_for_working_directory(
        session=mock_session,
        config_loader=mock_config_loader,
        session_manager=session_manager,
    )

    # Verify: Returns False (user cancelled)
    assert result is False


def test_q_returns_false(mock_workspace, mock_config_loader, mock_session, monkeypatch):
    """Test that entering 'q' returns False (alias for cancel)."""
    from rich.prompt import Prompt, Confirm

    # Mock Confirm.ask to decline multi-project mode (Issue #177)
    monkeypatch.setattr(Confirm, "ask", lambda prompt, default=False: False)

    # Mock Prompt.ask to simulate 'q'
    monkeypatch.setattr(Prompt, "ask", lambda prompt, **kwargs: "q")

    # Create session manager
    session_manager = SessionManager(mock_config_loader)

    # Call the function
    result = _prompt_for_working_directory(
        session=mock_session,
        config_loader=mock_config_loader,
        session_manager=session_manager,
    )

    # Verify: Returns False (user cancelled)
    assert result is False
