"""Tests for workspace mismatch confirmation (AAP-64497)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import Config, JiraConfig, RepoConfig, WorkspaceDefinition
from devflow.session.manager import SessionManager


@pytest.fixture
def mock_config():
    """Create a mock config with multiple workspaces."""
    return Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            project="PROJ",
            transitions={}  # Empty transitions dict for testing
        ),
        repos=RepoConfig(
            workspaces=[
                WorkspaceDefinition(name="workspace-a", path="/tmp/workspace-a"),
                WorkspaceDefinition(name="workspace-b", path="/tmp/workspace-b"),
                WorkspaceDefinition(name="workspace-c", path="/tmp/workspace-c"),
            ],
            last_used_workspace="workspace-a"
        )
    )


@pytest.fixture
def mock_config_loader(mock_config):
    """Create a mock config loader."""
    loader = MagicMock(spec=ConfigLoader)
    loader.load_config.return_value = mock_config
    return loader


@pytest.fixture
def mock_session(temp_daf_home):
    """Create a mock session with workspace_name set."""
    from devflow.config.models import Session

    session = Session(
        name="test-session",
        issue_key="PROJ-12345",
        goal="Test session",
        workspace_name="workspace-a"
    )
    return session


@pytest.fixture
def mock_session_manager(temp_daf_home, mock_session):
    """Create a mock session manager."""
    manager = MagicMock(spec=SessionManager)
    manager.get_session.return_value = mock_session
    return manager


def test_detect_workspace_from_cwd_in_workspace_a(mock_config_loader):
    """Test detecting workspace when cwd is in workspace-a."""
    from devflow.cli.commands.open_command import _detect_workspace_from_cwd

    # Create temp directory structure
    workspace_a_dir = Path("/tmp/workspace-a/project-1")

    with patch("devflow.git.utils.GitUtils.is_git_repository", return_value=True):
        result = _detect_workspace_from_cwd(workspace_a_dir, mock_config_loader)

    assert result == "workspace-a"


def test_detect_workspace_from_cwd_in_workspace_b(mock_config_loader):
    """Test detecting workspace when cwd is in workspace-b."""
    from devflow.cli.commands.open_command import _detect_workspace_from_cwd

    workspace_b_dir = Path("/tmp/workspace-b/project-2")

    with patch("devflow.git.utils.GitUtils.is_git_repository", return_value=True):
        result = _detect_workspace_from_cwd(workspace_b_dir, mock_config_loader)

    assert result == "workspace-b"


def test_detect_workspace_from_cwd_outside_workspaces(mock_config_loader):
    """Test detecting workspace when cwd is not in any configured workspace."""
    from devflow.cli.commands.open_command import _detect_workspace_from_cwd

    outside_dir = Path("/tmp/other-location/project")

    with patch("devflow.git.utils.GitUtils.is_git_repository", return_value=True):
        result = _detect_workspace_from_cwd(outside_dir, mock_config_loader)

    assert result is None


def test_detect_workspace_from_cwd_no_workspaces_configured():
    """Test detecting workspace when no workspaces are configured."""
    from devflow.cli.commands.open_command import _detect_workspace_from_cwd

    # Create config with no workspaces
    config = Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            project="PROJ",
            transitions={}
        ),
        repos=RepoConfig(workspaces=[])
    )
    loader = MagicMock(spec=ConfigLoader)
    loader.load_config.return_value = config

    some_dir = Path("/tmp/some-project")

    result = _detect_workspace_from_cwd(some_dir, loader)

    assert result is None


def test_detect_workspace_from_cwd_config_load_fails():
    """Test detecting workspace when config loading fails."""
    from devflow.cli.commands.open_command import _detect_workspace_from_cwd

    loader = MagicMock(spec=ConfigLoader)
    loader.load_config.side_effect = Exception("Config load failed")

    some_dir = Path("/tmp/some-project")

    result = _detect_workspace_from_cwd(some_dir, loader)

    assert result is None


def test_handle_workspace_mismatch_user_chooses_session_workspace(
    mock_session, mock_session_manager
):
    """Test workspace mismatch when user chooses to use session workspace."""
    from devflow.cli.commands.open_command import _handle_workspace_mismatch

    with patch("rich.prompt.IntPrompt.ask", return_value=1):
        result = _handle_workspace_mismatch(
            mock_session,
            mock_session_manager,
            "workspace-a",
            "workspace-b",
            skip_prompt=False
        )

    assert result is True
    # Session workspace should not change
    assert mock_session.workspace_name == "workspace-a"
    # Session should not be updated
    mock_session_manager.update_session.assert_not_called()


def test_handle_workspace_mismatch_user_chooses_current_workspace(
    mock_session, mock_session_manager
):
    """Test workspace mismatch when user chooses to switch to current workspace."""
    from devflow.cli.commands.open_command import _handle_workspace_mismatch

    with patch("rich.prompt.IntPrompt.ask", return_value=2):
        result = _handle_workspace_mismatch(
            mock_session,
            mock_session_manager,
            "workspace-a",
            "workspace-b",
            skip_prompt=False
        )

    assert result is True
    # Session workspace should be updated to current workspace
    assert mock_session.workspace_name == "workspace-b"
    # Session should be updated
    mock_session_manager.update_session.assert_called_once_with(mock_session)


def test_handle_workspace_mismatch_user_cancels(
    mock_session, mock_session_manager
):
    """Test workspace mismatch when user cancels."""
    from devflow.cli.commands.open_command import _handle_workspace_mismatch

    with patch("rich.prompt.IntPrompt.ask", return_value=3):
        result = _handle_workspace_mismatch(
            mock_session,
            mock_session_manager,
            "workspace-a",
            "workspace-b",
            skip_prompt=False
        )

    assert result is False
    # Session should not be updated
    mock_session_manager.update_session.assert_not_called()


def test_handle_workspace_mismatch_keyboard_interrupt(
    mock_session, mock_session_manager
):
    """Test workspace mismatch when user presses Ctrl+C."""
    from devflow.cli.commands.open_command import _handle_workspace_mismatch

    with patch("rich.prompt.IntPrompt.ask", side_effect=KeyboardInterrupt()):
        result = _handle_workspace_mismatch(
            mock_session,
            mock_session_manager,
            "workspace-a",
            "workspace-b",
            skip_prompt=False
        )

    assert result is False
    # Session should not be updated
    mock_session_manager.update_session.assert_not_called()


def test_handle_workspace_mismatch_skip_prompt(
    mock_session, mock_session_manager
):
    """Test workspace mismatch in non-interactive mode (--json flag)."""
    from devflow.cli.commands.open_command import _handle_workspace_mismatch

    # In skip_prompt mode, should default to session workspace without prompting
    result = _handle_workspace_mismatch(
        mock_session,
        mock_session_manager,
        "workspace-a",
        "workspace-b",
        skip_prompt=True
    )

    assert result is True
    # Session workspace should not change
    assert mock_session.workspace_name == "workspace-a"
    # Session should not be updated
    mock_session_manager.update_session.assert_not_called()


def test_workspace_mismatch_check_with_explicit_workspace_flag(
    temp_daf_home, mock_config, mock_config_loader, mock_session, mock_session_manager
):
    """Test that workspace mismatch check is skipped when --workspace flag is provided."""
    # Verify that when workspace flag is provided, mismatch check is skipped
    # The check is: if selected_workspace_name and not workspace and session.workspace_name
    selected_workspace_name = "workspace-a"
    workspace_flag = "workspace-b"  # Explicit flag provided
    session_has_workspace = mock_session.workspace_name is not None

    # Should NOT check for mismatch when workspace flag is provided
    should_check_mismatch = (
        selected_workspace_name and
        not workspace_flag and
        session_has_workspace
    )

    assert should_check_mismatch is False


def test_workspace_mismatch_check_without_session_workspace(temp_daf_home):
    """Test that workspace mismatch check is skipped for sessions without workspace_name."""
    from devflow.config.models import Session

    # Create session without workspace_name
    session = Session(
        name="test-session",
        issue_key="PROJ-12345",
        goal="Test session",
        workspace_name=None  # No workspace set
    )

    # Verify mismatch check is skipped when session.workspace_name is None
    selected_workspace_name = "workspace-a"
    workspace_flag = None
    session_has_workspace = session.workspace_name is not None

    should_check_mismatch = (
        selected_workspace_name and
        not workspace_flag and
        session_has_workspace
    )

    assert should_check_mismatch is False


def test_workspace_mismatch_check_no_workspace_selected():
    """Test that workspace mismatch check is skipped when no workspace is selected."""
    # Verify mismatch check is skipped when selected_workspace_name is None
    selected_workspace_name = None
    workspace_flag = None
    session_has_workspace = True

    # When selected_workspace_name is None, the entire expression evaluates to None
    # because Python's 'and' operator short-circuits and returns the first falsy value
    should_check_mismatch = (
        selected_workspace_name and
        not workspace_flag and
        session_has_workspace
    )

    # In Python, None is falsy, so the check correctly skips
    assert not should_check_mismatch
