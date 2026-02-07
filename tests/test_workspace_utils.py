"""Tests for workspace utility functions in devflow.cli.utils."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from devflow.cli.utils import (
    resolve_workspace_path,
    scan_workspace_repositories,
    prompt_repository_selection,
)
from devflow.config.models import WorkspaceDefinition


class TestResolveWorkspacePath:
    """Tests for resolve_workspace_path() utility."""

    def test_returns_none_when_config_is_none(self):
        """Should return None when config is None."""
        result = resolve_workspace_path(None, "some-workspace")
        assert result is None

    def test_returns_none_when_repos_is_none(self):
        """Should return None when config.repos is None."""
        mock_config = MagicMock()
        mock_config.repos = None
        result = resolve_workspace_path(mock_config, "some-workspace")
        assert result is None

    def test_uses_selected_workspace_when_provided(self):
        """Should use get_workspace_path when selected_workspace_name is provided."""
        mock_config = MagicMock()
        mock_config.repos.get_workspace_by_name.return_value = MagicMock(
            name="ai",
            path="/Users/test/development/ai"
        )

        result = resolve_workspace_path(mock_config, "ai")

        assert result == "/Users/test/development/ai"
        mock_config.repos.get_workspace_by_name.assert_called_once_with("ai")

    def test_uses_default_workspace_when_no_selection(self):
        """Should use get_default_workspace_path when selected_workspace_name is None."""
        mock_config = MagicMock()
        mock_config.repos.get_default_workspace_path.return_value = "/Users/test/development/default"

        result = resolve_workspace_path(mock_config, None)

        assert result == "/Users/test/development/default"
        mock_config.repos.get_default_workspace_path.assert_called_once()

    def test_returns_none_when_workspace_not_found(self):
        """Should return None when selected workspace doesn't exist."""
        mock_config = MagicMock()
        mock_config.repos.get_workspace_by_name.return_value = None

        result = resolve_workspace_path(mock_config, "nonexistent")

        assert result is None


class TestScanWorkspaceRepositories:
    """Tests for scan_workspace_repositories() utility."""

    def test_raises_value_error_when_workspace_not_exists(self, tmp_path):
        """Should raise ValueError when workspace directory doesn't exist."""
        nonexistent_path = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="Workspace directory does not exist"):
            scan_workspace_repositories(str(nonexistent_path))

    def test_raises_value_error_when_workspace_is_file(self, tmp_path):
        """Should raise ValueError when workspace path is a file, not a directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        with pytest.raises(ValueError, match="Workspace path is not a directory"):
            scan_workspace_repositories(str(file_path))

    def test_returns_empty_list_when_no_git_repos(self, tmp_path):
        """Should return empty list when workspace has no git repositories."""
        # Create non-git directories
        (tmp_path / "regular-dir").mkdir()
        (tmp_path / "another-dir").mkdir()

        with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=False):
            result = scan_workspace_repositories(str(tmp_path))

        assert result == []

    def test_returns_sorted_git_repos(self, tmp_path):
        """Should return sorted list of git repository names."""
        # Create mock directories
        (tmp_path / "backend-api").mkdir()
        (tmp_path / "frontend-app").mkdir()
        (tmp_path / "aaa-first").mkdir()

        # Mock is_git_repository to return True for all
        with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
            result = scan_workspace_repositories(str(tmp_path))

        # Should be sorted alphabetically
        assert result == ["aaa-first", "backend-api", "frontend-app"]

    def test_excludes_hidden_directories(self, tmp_path):
        """Should exclude directories starting with dot."""
        (tmp_path / "visible-repo").mkdir()
        (tmp_path / ".hidden-repo").mkdir()

        with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
            result = scan_workspace_repositories(str(tmp_path))

        assert result == ["visible-repo"]
        assert ".hidden-repo" not in result

    def test_expands_tilde_in_path(self, tmp_path, monkeypatch):
        """Should expand ~ to home directory."""
        # Mock home directory
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create a repo in the mocked home directory
        repo_dir = tmp_path / "repos"
        repo_dir.mkdir()
        (repo_dir / "test-repo").mkdir()

        with patch('devflow.git.utils.GitUtils.is_git_repository', return_value=True):
            result = scan_workspace_repositories("~/repos")

        assert result == ["test-repo"]


class TestPromptRepositorySelection:
    """Tests for prompt_repository_selection() utility."""

    def test_returns_none_when_empty_repo_list(self):
        """Should return None when repo_options is empty."""
        with patch('devflow.cli.utils.console') as mock_console:
            result = prompt_repository_selection([], "/path/to/workspace")

        assert result is None
        # Should print warning
        mock_console.print.assert_called()

    def test_returns_full_path_when_number_selected(self, tmp_path):
        """Should return full path when user selects by number."""
        repos = ["backend-api", "frontend-app"]

        with patch('rich.prompt.Prompt.ask', return_value="1"):
            result = prompt_repository_selection(repos, str(tmp_path))

        assert result == str(tmp_path / "backend-api")

    def test_returns_none_when_invalid_number(self, tmp_path):
        """Should return None when user selects invalid number."""
        repos = ["backend-api", "frontend-app"]

        with patch('rich.prompt.Prompt.ask', return_value="99"), \
             patch('devflow.cli.utils.console'):
            result = prompt_repository_selection(repos, str(tmp_path))

        assert result is None

    def test_returns_none_when_user_cancels(self, tmp_path):
        """Should return None when user enters 'cancel'."""
        repos = ["backend-api"]

        with patch('rich.prompt.Prompt.ask', return_value="cancel"), \
             patch('devflow.cli.utils.console'):
            result = prompt_repository_selection(repos, str(tmp_path))

        assert result is None

    def test_returns_none_when_user_enters_q(self, tmp_path):
        """Should return None when user enters 'q'."""
        repos = ["backend-api"]

        with patch('rich.prompt.Prompt.ask', return_value="q"), \
             patch('devflow.cli.utils.console'):
            result = prompt_repository_selection(repos, str(tmp_path))

        assert result is None

    def test_returns_full_path_when_repo_name_entered(self, tmp_path):
        """Should return full path when user enters repository name."""
        repos = ["backend-api", "frontend-app"]
        # Create the directory so it exists
        (tmp_path / "backend-api").mkdir()

        with patch('rich.prompt.Prompt.ask', return_value="backend-api"):
            result = prompt_repository_selection(repos, str(tmp_path))

        assert result == str(tmp_path / "backend-api")

    def test_prompts_confirmation_when_repo_not_exists(self, tmp_path):
        """Should prompt for confirmation when repository doesn't exist."""
        repos = ["backend-api"]

        with patch('rich.prompt.Prompt.ask', return_value="nonexistent-repo"), \
             patch('rich.prompt.Confirm.ask', return_value=True), \
             patch('devflow.cli.utils.console'):
            result = prompt_repository_selection(repos, str(tmp_path))

        # Should return path even though it doesn't exist (user confirmed)
        assert result == str(tmp_path / "nonexistent-repo")

    def test_returns_none_when_user_declines_nonexistent_repo(self, tmp_path):
        """Should return None when user declines to use nonexistent repository."""
        repos = ["backend-api"]

        with patch('rich.prompt.Prompt.ask', return_value="nonexistent-repo"), \
             patch('rich.prompt.Confirm.ask', return_value=False), \
             patch('devflow.cli.utils.console'):
            result = prompt_repository_selection(repos, str(tmp_path))

        assert result is None

    def test_returns_none_when_empty_selection(self, tmp_path):
        """Should return None when user enters empty string."""
        repos = ["backend-api"]

        with patch('rich.prompt.Prompt.ask', return_value=""), \
             patch('devflow.cli.utils.console'):
            result = prompt_repository_selection(repos, str(tmp_path))

        assert result is None

    def test_expands_tilde_in_workspace_path(self, tmp_path, monkeypatch):
        """Should expand ~ in workspace_path."""
        monkeypatch.setenv("HOME", str(tmp_path))
        repos = ["test-repo"]

        with patch('rich.prompt.Prompt.ask', return_value="1"):
            result = prompt_repository_selection(repos, "~/workspace")

        # Should expand ~ and return full path
        expected = str(Path("~/workspace").expanduser() / "test-repo")
        assert result == expected
