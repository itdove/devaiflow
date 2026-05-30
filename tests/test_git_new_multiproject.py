"""Tests for multi-project support in daf git new command (Issue #179)."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.cli.commands.git_new_command import create_git_issue_session, _prompt_for_target_repository
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


@pytest.fixture
def mock_workspace_with_multiple_repos(tmp_path):
    """Create a workspace with multiple git repositories."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    for repo_name in ["backend-api", "frontend-app", "database"]:
        repo_path = workspace / repo_name
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

    return workspace


@pytest.fixture
def config_with_workspace(mock_workspace_with_multiple_repos):
    """Create a config with the mock workspace."""
    config = MagicMock()
    config.repos.workspaces = {"test-workspace": str(mock_workspace_with_multiple_repos)}
    config.repos.default_workspace = "test-workspace"
    config.github.issue_types = ["bug", "enhancement", "task"]
    config.claude_code.launch_mode = "disabled"
    return config


class TestGitNewMultiProjectSelection:
    """Test multi-project selection in daf git new (Issue #179)."""

    @patch("devflow.cli.commands.git_new_command.should_launch_claude_code", return_value=False)
    @patch("devflow.session.manager.SessionManager")
    @patch("devflow.config.loader.ConfigLoader")
    @patch("devflow.cli.commands.git_new_command.unified_project_selection")
    @patch("devflow.cli.commands.git_new_command.scan_workspace_repositories")
    @patch("devflow.cli.commands.git_new_command.select_workspace")
    @patch("devflow.cli.commands.git_new_command.get_workspace_path")
    @patch("rich.prompt.Prompt.ask")
    @patch("devflow.utils.is_mock_mode", return_value=True)
    def test_git_new_with_multiproject_selection_and_target_repo(
        self,
        mock_is_mock_mode,
        mock_prompt_ask,
        mock_get_ws_path,
        mock_select_workspace,
        mock_scan_repos,
        mock_unified_select,
        mock_config_loader,
        mock_session_manager,
        mock_should_launch,
        mock_workspace_with_multiple_repos,
        config_with_workspace,
    ):
        """Test that daf git new supports multi-project selection with target repo selection."""
        mock_select_workspace.return_value = "test-workspace"
        mock_get_ws_path.return_value = str(mock_workspace_with_multiple_repos)
        mock_scan_repos.return_value = ["backend-api", "frontend-app", "database"]

        # unified_project_selection returns multi-project result
        mock_unified_select.return_value = (
            [str(mock_workspace_with_multiple_repos / "backend-api"),
             str(mock_workspace_with_multiple_repos / "frontend-app")],
            True
        )

        # Target repo selection
        mock_prompt_ask.return_value = "1"

        mock_config_loader.return_value.load_config.return_value = config_with_workspace

        mock_session = MagicMock()
        mock_session.name = "test-session"
        mock_session_manager.return_value.create_session.return_value = mock_session

        create_git_issue_session(
            goal="Add Redis caching",
            issue_type="enhancement",
            name="test-session",
            path=None,
            branch=None,
            parent=None,
            workspace="test-workspace",
            repository=None,
        )

        mock_unified_select.assert_called_once()

    @patch("devflow.session.manager.SessionManager")
    @patch("devflow.config.loader.ConfigLoader")
    @patch("devflow.cli.commands.git_new_command.unified_project_selection")
    @patch("devflow.cli.commands.git_new_command.scan_workspace_repositories")
    @patch("devflow.cli.commands.git_new_command.select_workspace")
    @patch("devflow.cli.commands.git_new_command.get_workspace_path")
    @patch("devflow.utils.is_mock_mode", return_value=True)
    def test_git_new_single_project_fallback(
        self,
        mock_is_mock_mode,
        mock_get_ws_path,
        mock_select_workspace,
        mock_scan_repos,
        mock_unified_select,
        mock_config_loader,
        mock_session_manager,
        mock_workspace_with_multiple_repos,
        config_with_workspace,
    ):
        """Test that declining multi-project mode falls back to single-project."""
        mock_select_workspace.return_value = "test-workspace"
        mock_get_ws_path.return_value = str(mock_workspace_with_multiple_repos)
        mock_scan_repos.return_value = ["backend-api", "frontend-app", "database"]

        # Single-project result
        mock_unified_select.return_value = (
            [str(mock_workspace_with_multiple_repos / "backend-api")],
            False
        )

        mock_config_loader.return_value.load_config.return_value = config_with_workspace

        mock_session = MagicMock()
        mock_session.name = "test-session"
        mock_session_manager.return_value.create_session.return_value = mock_session

        create_git_issue_session(
            goal="Fix bug",
            issue_type="bug",
            name="test-session",
            path=None,
            branch=None,
            parent=None,
            workspace="test-workspace",
            repository=None,
        )

        mock_unified_select.assert_called_once()
        mock_session_manager.return_value.create_session.assert_called()


class TestTargetRepositorySelection:
    """Test target repository selection for git new (Issue #179)."""

    @patch("rich.prompt.Prompt.ask")
    def test_target_repo_selection_by_number(self, mock_prompt, tmp_path):
        """Test selecting target repository by number."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        project_paths = []
        for repo_name in ["backend-api", "frontend-app", "database"]:
            repo_path = workspace / repo_name
            repo_path.mkdir()
            project_paths.append(str(repo_path))

        mock_prompt.return_value = "2"

        result = _prompt_for_target_repository(project_paths, repository=None)

        assert result == project_paths[1]
        assert "frontend-app" in result


    @patch("rich.prompt.Prompt.ask")
    def test_target_repo_selection_by_name(self, mock_prompt, tmp_path):
        """Test selecting target repository by name."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        project_paths = []
        for repo_name in ["backend-api", "frontend-app", "database"]:
            repo_path = workspace / repo_name
            repo_path.mkdir()
            project_paths.append(str(repo_path))

        mock_prompt.return_value = "database"

        result = _prompt_for_target_repository(project_paths, repository=None)

        assert result == project_paths[2]
        assert "database" in result


    @patch("rich.prompt.Prompt.ask")
    def test_target_repo_selection_invalid(self, mock_prompt, tmp_path):
        """Test invalid target repository selection."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        project_paths = []
        for repo_name in ["backend-api", "frontend-app"]:
            repo_path = workspace / repo_name
            repo_path.mkdir()
            project_paths.append(str(repo_path))

        mock_prompt.return_value = "5"

        result = _prompt_for_target_repository(project_paths, repository=None)

        assert result is None


class TestMultiProjectGitPromptBuilder:
    """Test multi-project prompt generation for git new."""

    def test_multiproject_git_prompt_includes_all_projects(self, tmp_path):
        """Test that multi-project git prompt mentions all selected projects."""
        from devflow.cli.commands.git_new_command import (
            _build_multiproject_issue_creation_prompt,
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        project_paths = []
        for repo_name in ["backend-api", "frontend-app", "database"]:
            repo_path = workspace / repo_name
            repo_path.mkdir()
            project_paths.append(str(repo_path))

        target_repo_path = project_paths[0]

        mock_config = MagicMock()

        prompt = _build_multiproject_issue_creation_prompt(
            issue_type="enhancement",
            goal="Add Redis caching",
            config=mock_config,
            name="test-session",
            project_paths=project_paths,
            workspace=str(workspace),
            target_repo_path=target_repo_path,
            parent=None,
            repository=None,
        )

        assert "backend-api" in prompt
        assert "frontend-app" in prompt
        assert "database" in prompt
        assert "MULTI-PROJECT" in prompt or "multi-project" in prompt
        assert "READ-ONLY" in prompt
        assert "Do NOT modify" in prompt or "DO NOT modify" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
