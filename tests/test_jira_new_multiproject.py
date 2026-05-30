"""Tests for multi-project support in daf jira new command (Issue #179)."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.cli.commands.jira_new_command import create_jira_ticket_session
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
    config.jira.project = "PROJ"
    config.jira.custom_field_defaults = {}
    config.claude_code.launch_mode = "disabled"
    return config


class TestJiraNewMultiProjectSelection:
    """Test multi-project selection in daf jira new (Issue #179)."""

    @patch("devflow.cli.commands.jira_new_command.should_launch_claude_code", return_value=False)
    @patch("devflow.session.manager.SessionManager")
    @patch("devflow.config.loader.ConfigLoader")
    @patch("devflow.cli.commands.jira_new_command.unified_project_selection")
    @patch("devflow.cli.commands.jira_new_command.scan_workspace_repositories")
    @patch("devflow.cli.commands.jira_new_command.select_workspace")
    @patch("devflow.cli.commands.jira_new_command.get_workspace_path")
    @patch("devflow.utils.is_mock_mode", return_value=True)
    def test_jira_new_with_multiproject_selection(
        self,
        mock_is_mock_mode,
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
        """Test that daf jira new supports multi-project selection."""
        mock_select_workspace.return_value = "test-workspace"
        mock_get_ws_path.return_value = str(mock_workspace_with_multiple_repos)
        mock_scan_repos.return_value = ["backend-api", "frontend-app", "database"]

        mock_unified_select.return_value = (
            [str(mock_workspace_with_multiple_repos / "backend-api"),
             str(mock_workspace_with_multiple_repos / "frontend-app")],
            True
        )

        mock_config_loader.return_value.load_config.return_value = config_with_workspace

        mock_session = MagicMock()
        mock_session.name = "test-session"
        mock_session_manager.return_value.create_session.return_value = mock_session

        create_jira_ticket_session(
            goal="Add Redis caching",
            issue_type="story",
            parent="PROJ-1234",
            name="test-session",
            path=None,
            branch=None,
            workspace="test-workspace",
            affects_versions=None,
        )

        mock_unified_select.assert_called_once()


    @patch("devflow.session.manager.SessionManager")
    @patch("devflow.config.loader.ConfigLoader")
    @patch("devflow.cli.commands.jira_new_command.unified_project_selection")
    @patch("devflow.cli.commands.jira_new_command.scan_workspace_repositories")
    @patch("devflow.cli.commands.jira_new_command.select_workspace")
    @patch("devflow.cli.commands.jira_new_command.get_workspace_path")
    @patch("devflow.utils.is_mock_mode", return_value=True)
    def test_jira_new_single_project_fallback(
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

        mock_unified_select.return_value = (
            [str(mock_workspace_with_multiple_repos / "backend-api")],
            False
        )

        mock_config_loader.return_value.load_config.return_value = config_with_workspace

        mock_session = MagicMock()
        mock_session.name = "test-session"
        mock_session_manager.return_value.create_session.return_value = mock_session

        create_jira_ticket_session(
            goal="Fix bug",
            issue_type="bug",
            parent="PROJ-1234",
            name="test-session",
            path=None,
            branch=None,
            workspace="test-workspace",
            affects_versions=None,
        )

        mock_unified_select.assert_called_once()
        mock_session_manager.return_value.create_session.assert_called()


class TestMultiProjectTicketCreationSession:
    """Test multi-project ticket creation session creation."""

    def test_create_multiproject_ticket_session_no_branches(self, tmp_path):
        """Test that multi-project ticket creation sessions skip branch creation."""
        from devflow.cli.commands.ticket_creation_multiproject import (
            create_multi_project_ticket_creation_session,
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        project_paths = []
        for repo_name in ["backend-api", "frontend-app"]:
            repo_path = workspace / repo_name
            repo_path.mkdir()
            git_dir = repo_path / ".git"
            git_dir.mkdir()
            project_paths.append(str(repo_path))

        mock_config = MagicMock()
        mock_session_manager = MagicMock()

        mock_session = MagicMock()
        mock_session.name = "test-session"
        mock_session_manager.create_session.return_value = mock_session

        session, ai_agent_session_id = create_multi_project_ticket_creation_session(
            session_manager=mock_session_manager,
            config=mock_config,
            name="test-session",
            goal="Create JIRA ticket: Add caching",
            project_paths=project_paths,
            workspace_path=str(workspace),
            selected_workspace_name="test-workspace",
            session_type="ticket_creation",
            issue_type="story",
        )

        assert session == mock_session
        assert ai_agent_session_id is not None
        assert session.session_type == "ticket_creation"
        session.add_multi_project_conversation.assert_called_once()


class TestMultiProjectPromptBuilder:
    """Test multi-project prompt generation."""

    def test_multiproject_prompt_includes_all_projects(self, tmp_path):
        """Test that multi-project prompt mentions all selected projects."""
        from devflow.cli.commands.jira_new_command import (
            _build_multiproject_ticket_creation_prompt,
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        project_paths = []
        for repo_name in ["backend-api", "frontend-app", "database"]:
            repo_path = workspace / repo_name
            repo_path.mkdir()
            project_paths.append(str(repo_path))

        mock_config = MagicMock()
        mock_config.jira.project = "PROJ"
        mock_config.jira.custom_field_defaults = {}

        prompt = _build_multiproject_ticket_creation_prompt(
            issue_type="story",
            goal="Add Redis caching",
            config=mock_config,
            name="test-session",
            project_paths=project_paths,
            workspace=str(workspace),
            parent="PROJ-1234",
            affects_versions=None,
        )

        assert "backend-api" in prompt
        assert "frontend-app" in prompt
        assert "database" in prompt
        assert "MULTI-PROJECT" in prompt or "multi-project" in prompt
        assert "READ-ONLY" in prompt
        assert "Do NOT modify" in prompt or "DO NOT modify" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
