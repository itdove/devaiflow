"""Test for workspace selection bug fix (AAP-64504).

This test verifies that _prompt_for_working_directory respects the selected
workspace when scanning for repositories, instead of always using the default workspace.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from devflow.cli.commands.open_command import _prompt_for_working_directory
from devflow.cli.utils import unified_project_selection
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkspaceDefinition
from devflow.session.manager import SessionManager


@pytest.fixture
def mock_config_multi_workspace():
    """Create a mock config with multiple workspaces."""
    mock_repos = MagicMock()
    mock_repos.workspaces = [
        WorkspaceDefinition(name="ai", path="/Users/test/development/ai"),
        WorkspaceDefinition(name="project-b", path="/Users/test/development/project-b"),
    ]
    mock_repos.last_used_workspace = "project-b"

    def get_workspace_by_name(name):
        for ws in mock_repos.workspaces:
            if ws.name == name:
                return ws
        return None
    mock_repos.get_workspace_by_name = get_workspace_by_name

    def get_default_workspace_path():
        if mock_repos.last_used_workspace:
            ws = get_workspace_by_name(mock_repos.last_used_workspace)
            return ws.path if ws else None
        return None
    mock_repos.get_default_workspace_path = get_default_workspace_path

    mock_config = MagicMock()
    mock_config.repos = mock_repos

    return mock_config


@pytest.fixture
def mock_config_loader(mock_config_multi_workspace, tmp_path):
    """Create a mock config loader."""
    config_loader = MagicMock(spec=ConfigLoader)
    config_loader.load_config.return_value = mock_config_multi_workspace

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    config_loader.sessions_dir = sessions_dir
    config_loader.sessions_file = sessions_dir / "sessions.json"

    return config_loader


@pytest.fixture
def mock_session(mock_config_loader):
    """Create a mock session."""
    with patch("devflow.utils.audit_log.log_model_provider_usage"):
        session_manager = SessionManager(mock_config_loader)
        session = session_manager.create_session(
            name="test-session",
            issue_key="AAP-12345",
            goal="Test goal"
        )
    return session


def test_prompt_for_working_directory_uses_selected_workspace(
    mock_session,
    mock_config_loader,
    mock_config_multi_workspace,
    monkeypatch,
):
    """Test that _prompt_for_working_directory uses the selected workspace from -w flag."""
    session_manager = SessionManager(mock_config_loader)

    with patch("devflow.cli.commands.open_command.get_workspace_path") as mock_get_ws, \
         patch("devflow.cli.commands.open_command.scan_workspace_repositories") as mock_scan, \
         patch("devflow.cli.commands.open_command.unified_project_selection") as mock_unified:
        mock_get_ws.return_value = "/Users/test/development/ai"
        mock_scan.return_value = ["repo-a", "repo-b"]
        mock_unified.return_value = (None, False)

        result = _prompt_for_working_directory(
            session=mock_session,
            config_loader=mock_config_loader,
            session_manager=session_manager,
            selected_workspace_name="ai"
        )

        mock_get_ws.assert_called_once_with(mock_config_multi_workspace, "ai")
        mock_scan.assert_called_once_with("/Users/test/development/ai")


def test_prompt_for_working_directory_uses_default_when_no_selection(
    mock_session,
    mock_config_loader,
    mock_config_multi_workspace,
    monkeypatch,
):
    """Test that _prompt_for_working_directory uses default workspace when no -w flag provided."""
    session_manager = SessionManager(mock_config_loader)

    with patch("devflow.cli.commands.open_command.get_workspace_path") as mock_get_ws, \
         patch("devflow.cli.commands.open_command.scan_workspace_repositories") as mock_scan, \
         patch("devflow.cli.commands.open_command.unified_project_selection") as mock_unified:
        mock_get_ws.return_value = "/Users/test/development/project-b"
        mock_scan.return_value = ["repo-x"]
        mock_unified.return_value = (None, False)

        result = _prompt_for_working_directory(
            session=mock_session,
            config_loader=mock_config_loader,
            session_manager=session_manager,
        )

        mock_scan.assert_called_once_with("/Users/test/development/project-b")
