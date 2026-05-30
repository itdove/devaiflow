"""Tests for multi-project selection in daf open _prompt_for_working_directory (Issue #177)."""

import subprocess
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_prompt_for_working_directory_offers_multiproject_selection(temp_daf_home, tmp_path):
    """Test that _prompt_for_working_directory offers multi-project selection via unified_project_selection."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()

    project1 = workspace_path / "backend-api"
    project2 = workspace_path / "frontend-app"

    for proj in [project1, project2]:
        proj.mkdir()
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=proj, capture_output=True)
        (proj / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=proj, capture_output=True)

    config_file = Path.home() / ".daf-sessions" / "config.json"
    config_data = {
        "repos": {
            "workspaces": [
                {"name": "test-workspace", "path": str(workspace_path)}
            ]
        },
        "templates": {"auto_create": False}
    }
    config_file.write_text(json.dumps(config_data, indent=2))

    session = session_manager.create_session(
        name="PROJ-123",
        issue_key="PROJ-123",
        goal="Test multi-project selection",
        working_directory=None,
        project_path=None,
    )

    with patch("devflow.cli.commands.open_command.unified_project_selection") as mock_unified:
        mock_unified.return_value = ([str(project1), str(project2)], True)

        with patch("devflow.cli.commands.open_command._create_multi_project_conversation_for_open") as mock_multi:
            mock_multi.return_value = True

            from devflow.cli.commands.open_command import _prompt_for_working_directory

            result = _prompt_for_working_directory(
                session=session,
                config_loader=config_loader,
                session_manager=session_manager,
                selected_workspace_name="test-workspace",
            )

            assert result is True
            mock_unified.assert_called_once()
            mock_multi.assert_called_once()


def test_prompt_for_working_directory_single_project_when_only_one_selected(temp_daf_home, tmp_path):
    """Test that selecting only one project continues with single-project mode."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()

    project1 = workspace_path / "backend-api"
    project2 = workspace_path / "frontend-app"

    for proj in [project1, project2]:
        proj.mkdir()
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=proj, capture_output=True)
        (proj / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=proj, capture_output=True)

    config_file = Path.home() / ".daf-sessions" / "config.json"
    config_data = {
        "repos": {
            "workspaces": [
                {"name": "test-workspace", "path": str(workspace_path)}
            ]
        },
        "templates": {"auto_create": False}
    }
    config_file.write_text(json.dumps(config_data, indent=2))

    session = session_manager.create_session(
        name="PROJ-124",
        issue_key="PROJ-124",
        goal="Test single project fallback",
        working_directory=None,
        project_path=None,
    )

    with patch("devflow.cli.commands.open_command.unified_project_selection") as mock_unified:
        mock_unified.return_value = ([str(project1)], False)

        from devflow.cli.commands.open_command import _prompt_for_working_directory

        result = _prompt_for_working_directory(
            session=session,
            config_loader=config_loader,
            session_manager=session_manager,
            selected_workspace_name="test-workspace",
        )

        assert result is True
        assert len(session.conversations) == 1
        conv_key = list(session.conversations.keys())[0]
        conv = session.conversations[conv_key]
        assert conv.active_session.is_multi_project is False


def test_prompt_for_working_directory_no_multiproject_when_user_declines(temp_daf_home, tmp_path):
    """Test that declining multi-project still selects single project."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()

    project1 = workspace_path / "backend-api"
    project2 = workspace_path / "frontend-app"

    for proj in [project1, project2]:
        proj.mkdir()
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=proj, capture_output=True)
        (proj / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=proj, capture_output=True)

    config_file = Path.home() / ".daf-sessions" / "config.json"
    config_data = {
        "repos": {
            "workspaces": [
                {"name": "test-workspace", "path": str(workspace_path)}
            ]
        },
        "templates": {"auto_create": False}
    }
    config_file.write_text(json.dumps(config_data, indent=2))

    session = session_manager.create_session(
        name="PROJ-125",
        issue_key="PROJ-125",
        goal="Test decline multi-project",
        working_directory=None,
        project_path=None,
    )

    with patch("devflow.cli.commands.open_command.unified_project_selection") as mock_unified:
        mock_unified.return_value = ([str(project1)], False)

        from devflow.cli.commands.open_command import _prompt_for_working_directory

        result = _prompt_for_working_directory(
            session=session,
            config_loader=config_loader,
            session_manager=session_manager,
            selected_workspace_name="test-workspace",
        )

        assert result is True
        assert len(session.conversations) == 1
