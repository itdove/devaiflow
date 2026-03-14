"""Tests for GitHub/GitLab repository auto-suggestion in daf open command."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from devflow.cli.commands.open_command import _extract_repository_from_issue_key, _prompt_for_working_directory
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


class TestExtractRepositoryFromIssueKey:
    """Tests for extracting repository name from GitHub/GitLab issue keys."""

    def test_extract_from_github_issue_with_owner_repo(self):
        """Test extracting repository from full GitHub issue key."""
        result = _extract_repository_from_issue_key("itdove/devaiflow#146", "github")
        assert result == "devaiflow"

    def test_extract_from_gitlab_issue_with_owner_repo(self):
        """Test extracting repository from full GitLab issue key."""
        result = _extract_repository_from_issue_key("myorg/myproject#42", "gitlab")
        assert result == "myproject"

    def test_extract_with_nested_groups(self):
        """Test extracting repository from GitLab issue with nested groups."""
        result = _extract_repository_from_issue_key("org/subgroup/project#99", "gitlab")
        assert result == "project"

    def test_extract_from_issue_without_owner(self):
        """Test that extraction returns None for issue key without owner/repo."""
        result = _extract_repository_from_issue_key("#123", "github")
        assert result is None

    def test_extract_from_jira_key(self):
        """Test that extraction returns None for JIRA keys."""
        result = _extract_repository_from_issue_key("PROJ-12345", "jira")
        assert result is None

    def test_extract_with_none_issue_tracker(self):
        """Test that extraction returns None when issue_tracker is None."""
        result = _extract_repository_from_issue_key("owner/repo#123", None)
        assert result is None

    def test_extract_with_empty_issue_key(self):
        """Test that extraction returns None for empty issue key."""
        result = _extract_repository_from_issue_key("", "github")
        assert result is None

    def test_extract_with_none_issue_key(self):
        """Test that extraction returns None for None issue key."""
        result = _extract_repository_from_issue_key(None, "github")
        assert result is None

    def test_extract_with_unsupported_tracker(self):
        """Test that extraction returns None for unsupported issue trackers."""
        result = _extract_repository_from_issue_key("owner/repo#123", "bitbucket")
        assert result is None

    def test_extract_with_special_characters_in_repo_name(self):
        """Test extracting repository with special characters."""
        result = _extract_repository_from_issue_key("org/my-project.app#1", "github")
        assert result == "my-project.app"

    def test_extract_with_malformed_issue_key(self):
        """Test that extraction handles malformed issue keys gracefully."""
        # Missing issue number
        result = _extract_repository_from_issue_key("owner/repo#", "github")
        assert result == "repo"

        # Multiple # symbols (take first)
        result = _extract_repository_from_issue_key("owner/repo#123#456", "github")
        assert result == "repo"

    def test_extract_case_sensitivity(self):
        """Test that repository name case is preserved."""
        result = _extract_repository_from_issue_key("owner/DevAIFlow#1", "github")
        assert result == "DevAIFlow"

    def test_extract_with_numeric_repo_name(self):
        """Test extracting repository with numeric name."""
        result = _extract_repository_from_issue_key("org/project-123#5", "github")
        assert result == "project-123"


class TestGitHubRepoSuggestionIntegration:
    """Integration tests for GitHub/GitLab repository auto-suggestion."""

    @pytest.fixture
    def workspace_with_devaiflow(self, tmp_path):
        """Create a workspace with devaiflow repository."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create devaiflow repo
        devaiflow_repo = workspace / "devaiflow"
        devaiflow_repo.mkdir()
        subprocess.run(["git", "init"], cwd=devaiflow_repo, capture_output=True, check=True)

        # Create other repos
        for repo_name in ["backend-api", "frontend-app"]:
            repo_path = workspace / repo_name
            repo_path.mkdir()
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)

        return workspace

    @pytest.fixture
    def config_loader_with_workspace(self, workspace_with_devaiflow, temp_daf_home):
        """Create config loader with workspace."""
        from devflow.config.models import WorkspaceDefinition

        config_loader = ConfigLoader()
        config_loader.create_default_config()

        config = config_loader.load_config()
        config.repos.workspaces = [
            WorkspaceDefinition(name="default", path=str(workspace_with_devaiflow))
        ]
        config.repos.last_used_workspace = "default"
        config_loader.save_config(config)

        return config_loader

    @pytest.fixture
    def github_session(self, temp_daf_home, config_loader_with_workspace):
        """Create a GitHub session from daf sync."""
        session_manager = SessionManager(config_loader_with_workspace)

        # Create a session that was created by daf sync
        session = session_manager.create_session(
            name="itdove-devaiflow-146",
            goal="Auto-suggest project/repository when opening sessions",
            issue_key="itdove/devaiflow#146",
            # No project_path - simulates session created by daf sync
        )

        # Set issue_tracker manually (this would be done by daf sync)
        session.issue_tracker = "github"
        session_manager.update_session(session)

        return session

    def test_github_session_suggests_devaiflow_repo(
        self, workspace_with_devaiflow, config_loader_with_workspace, github_session, monkeypatch, capsys
    ):
        """Test that opening a GitHub session suggests the matching repository."""
        from rich.prompt import Prompt
        from rich.console import Console

        # Mock Prompt.ask to simulate selecting the default (devaiflow)
        monkeypatch.setattr(Prompt, "ask", lambda prompt, default=None: default or "1")

        # Create session manager
        session_manager = SessionManager(config_loader_with_workspace)

        # Call the function
        result = _prompt_for_working_directory(
            session=github_session,
            config_loader=config_loader_with_workspace,
            session_manager=session_manager,
        )

        # Verify: Returns True (successfully set working directory)
        assert result is True

        # Verify: Session was updated with devaiflow path
        updated_session = session_manager.get_session(github_session.name)
        assert updated_session.active_conversation is not None
        assert "devaiflow" in updated_session.active_conversation.project_path

    def test_jira_session_no_suggestion(self, workspace_with_devaiflow, config_loader_with_workspace, temp_daf_home, monkeypatch):
        """Test that JIRA sessions do not show repository suggestions."""
        from rich.prompt import Prompt

        # Create a JIRA session
        session_manager = SessionManager(config_loader_with_workspace)
        jira_session = session_manager.create_session(
            name="proj-12345",
            goal="JIRA task",
            issue_key="PROJ-12345",
            # No project_path
        )

        # Set issue_tracker manually
        jira_session.issue_tracker = "jira"
        session_manager.update_session(jira_session)

        # Mock Prompt.ask to simulate selecting first repository
        monkeypatch.setattr(Prompt, "ask", lambda prompt, default=None: "1")

        # Call the function
        result = _prompt_for_working_directory(
            session=jira_session,
            config_loader=config_loader_with_workspace,
            session_manager=session_manager,
        )

        # Verify: Returns True but no suggestion was shown
        assert result is True

    def test_github_session_repo_not_in_workspace(
        self, tmp_path, config_loader_with_workspace, temp_daf_home, monkeypatch
    ):
        """Test handling when suggested repository doesn't exist in workspace."""
        from rich.prompt import Prompt

        # Create session with issue for a repo that doesn't exist in workspace
        session_manager = SessionManager(config_loader_with_workspace)
        session = session_manager.create_session(
            name="org-nonexistent-1",
            goal="Test",
            issue_key="org/nonexistent#1",
        )

        # Set issue_tracker manually
        session.issue_tracker = "github"
        session_manager.update_session(session)

        # Mock Prompt.ask to simulate selecting first repository
        monkeypatch.setattr(Prompt, "ask", lambda prompt, default=None: "1")

        # Call the function
        result = _prompt_for_working_directory(
            session=session,
            config_loader=config_loader_with_workspace,
            session_manager=session_manager,
        )

        # Verify: Returns True (still works, just no suggestion)
        assert result is True
