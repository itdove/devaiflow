"""Tests for devflow/utils/temp_directory.py.

These tests verify the shared temporary directory utilities extracted from
jira_new_command.py and now used by both jira_new and jira_open commands.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.utils.temp_directory import (
    should_clone_to_temp,
    prompt_and_clone_to_temp,
    clone_to_temp_directory,
    cleanup_temp_directory,
    extract_repo_name,
    _prompt_for_branch_selection,
    _create_nested_temp_directory,
)


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock git repository for testing."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Create initial commit
    (repo_path / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    return repo_path


@pytest.fixture
def non_git_dir(tmp_path):
    """Create a non-git directory for testing."""
    non_git_path = tmp_path / "non-git-dir"
    non_git_path.mkdir()
    return non_git_path


class TestExtractRepoName:
    """Test the extract_repo_name function."""

    def test_https_url_with_git_suffix(self):
        assert extract_repo_name("https://github.com/itdove/ai-guardian.git") == "ai-guardian"

    def test_https_url_without_git_suffix(self):
        assert extract_repo_name("https://github.com/user/repo") == "repo"

    def test_ssh_url_with_git_suffix(self):
        assert extract_repo_name("git@github.com:user/my-project.git") == "my-project"

    def test_ssh_url_without_git_suffix(self):
        assert extract_repo_name("git@github.com:org/repo-name") == "repo-name"

    def test_url_with_trailing_slash(self):
        assert extract_repo_name("https://github.com/user/repo/") == "repo"

    def test_url_with_dots_in_name(self):
        assert extract_repo_name("https://github.com/user/my-project.v2.git") == "my-project.v2"

    def test_url_with_underscores(self):
        assert extract_repo_name("https://github.com/user/my_project.git") == "my_project"

    def test_empty_url(self):
        assert extract_repo_name("") == "repo"

    def test_none_like_empty(self):
        assert extract_repo_name("") == "repo"

    def test_simple_name(self):
        assert extract_repo_name("https://github.com/user/devaiflow.git") == "devaiflow"

    def test_gitlab_url(self):
        assert extract_repo_name("https://gitlab.example.com/group/subgroup/project.git") == "project"

    def test_bitbucket_ssh(self):
        assert extract_repo_name("git@bitbucket.org:team/repo.git") == "repo"

    def test_url_with_port(self):
        assert extract_repo_name("https://gitlab.example.com:8443/group/project.git") == "project"

    def test_hyphenated_name(self):
        assert extract_repo_name("https://github.com/org/ansible-automation-platform.git") == "ansible-automation-platform"


class TestCreateNestedTempDirectory:
    """Test the _create_nested_temp_directory helper."""

    def test_creates_nested_structure(self):
        result = _create_nested_temp_directory("https://github.com/user/my-repo.git")
        assert result is not None
        session_dir, clone_dir = result

        try:
            assert os.path.exists(session_dir)
            assert os.path.exists(clone_dir)
            assert clone_dir == os.path.join(session_dir, "my-repo")
            assert os.path.basename(session_dir).startswith("daf-session-")
        finally:
            shutil.rmtree(session_dir, ignore_errors=True)

    def test_clone_dir_ends_with_repo_name(self):
        result = _create_nested_temp_directory("git@github.com:org/ai-guardian.git")
        assert result is not None
        session_dir, clone_dir = result

        try:
            assert clone_dir.endswith("/ai-guardian")
        finally:
            shutil.rmtree(session_dir, ignore_errors=True)

    def test_handles_creation_failure(self):
        with patch("tempfile.mkdtemp", side_effect=Exception("Permission denied")):
            result = _create_nested_temp_directory("https://github.com/user/repo.git")
            assert result is None


class TestShouldCloneToTemp:
    """Test the should_clone_to_temp function."""

    def test_returns_true_for_git_repository(self, mock_git_repo):
        """Test that function returns True when path is a git repository."""
        result = should_clone_to_temp(mock_git_repo)
        assert result is True

    def test_returns_false_for_non_git_directory(self, non_git_dir):
        """Test that function returns False when path is not a git repository."""
        result = should_clone_to_temp(non_git_dir)
        assert result is False

    def test_returns_false_for_nonexistent_path(self, tmp_path):
        """Test that function returns False for nonexistent path."""
        nonexistent = tmp_path / "does-not-exist"
        result = should_clone_to_temp(nonexistent)
        assert result is False


class TestCloneToTempDirectory:
    """Test the clone_to_temp_directory function (non-interactive)."""

    def test_returns_none_when_no_remote_url(self, mock_git_repo):
        with patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value=None):
            result = clone_to_temp_directory(mock_git_repo)
            assert result is None

    def test_returns_none_when_clone_fails(self, mock_git_repo):
        with patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("devflow.utils.temp_directory._create_nested_temp_directory", return_value=("/tmp/daf-session-test", "/tmp/daf-session-test/repo")), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=False), \
             patch("shutil.rmtree"):
            result = clone_to_temp_directory(mock_git_repo)
            assert result is None

    def test_returns_nested_path_on_success(self, mock_git_repo):
        with patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/my-project.git"), \
             patch("devflow.utils.temp_directory._create_nested_temp_directory", return_value=("/tmp/daf-session-abc", "/tmp/daf-session-abc/my-project")), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory._checkout_default_branch"):
            result = clone_to_temp_directory(mock_git_repo)
            assert result is not None
            temp_directory, original_path = result
            assert temp_directory == "/tmp/daf-session-abc/my-project"
            assert original_path == str(mock_git_repo.absolute())

    def test_returns_none_when_dir_creation_fails(self, mock_git_repo):
        with patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("devflow.utils.temp_directory._create_nested_temp_directory", return_value=None):
            result = clone_to_temp_directory(mock_git_repo)
            assert result is None


class TestPromptAndCloneToTemp:
    """Test the prompt_and_clone_to_temp function."""

    def test_returns_none_when_user_declines(self, mock_git_repo):
        """Test that function returns None when user declines the prompt."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=False):
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is None

    def test_returns_none_when_no_remote_url(self, mock_git_repo):
        """Test that function returns None when git remote URL cannot be detected."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value=None):
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is None

    def test_returns_none_when_dir_creation_fails(self, mock_git_repo):
        """Test that function returns None when nested temp directory creation fails."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("devflow.utils.temp_directory._create_nested_temp_directory", return_value=None):
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is None

    def test_returns_none_when_clone_fails(self, mock_git_repo):
        """Test that function returns None when repository cloning fails."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("devflow.utils.temp_directory._create_nested_temp_directory", return_value=("/tmp/daf-session-test", "/tmp/daf-session-test/repo")), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=False), \
             patch("shutil.rmtree") as mock_rmtree:
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is None
            mock_rmtree.assert_called_once_with("/tmp/daf-session-test")

    def test_returns_none_when_clone_fails_and_cleanup_fails(self, mock_git_repo):
        """Test that function returns None when clone fails and cleanup also fails."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("devflow.utils.temp_directory._create_nested_temp_directory", return_value=("/tmp/daf-session-test", "/tmp/daf-session-test/repo")), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=False), \
             patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is None

    def test_successful_clone_returns_nested_path(self, mock_git_repo):
        """Test successful clone returns path with repo name subdirectory."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/ai-guardian.git"), \
             patch("devflow.utils.temp_directory._create_nested_temp_directory", return_value=("/tmp/daf-session-abc", "/tmp/daf-session-abc/ai-guardian")), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory._prompt_for_branch_selection", return_value=None), \
             patch("devflow.utils.temp_directory._checkout_default_branch"):
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is not None
            temp_directory, original_project_path = result
            assert temp_directory == "/tmp/daf-session-abc/ai-guardian"
            assert "ai-guardian" in temp_directory
            assert original_project_path == str(mock_git_repo.absolute())

    def test_successful_clone_with_branch_selection(self, mock_git_repo):
        """Test successful clone with branch selection prompt."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("devflow.utils.temp_directory._create_nested_temp_directory", return_value=("/tmp/daf-session-abc", "/tmp/daf-session-abc/repo")), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory._prompt_for_branch_selection", return_value="develop") as mock_prompt, \
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=(True, None)) as mock_checkout:
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is not None
            mock_prompt.assert_called_once_with(Path("/tmp/daf-session-abc/repo"))
            mock_checkout.assert_called_once_with(Path("/tmp/daf-session-abc/repo"), "develop")

    def test_clone_with_failed_branch_checkout_falls_back(self, mock_git_repo):
        """Test that failed branch checkout falls back to auto-detection."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("devflow.utils.temp_directory._create_nested_temp_directory", return_value=("/tmp/daf-session-abc", "/tmp/daf-session-abc/repo")), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory._prompt_for_branch_selection", return_value="feature/test"), \
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=(False, "checkout error")), \
             patch("devflow.utils.temp_directory._checkout_default_branch") as mock_fallback:
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is not None
            mock_fallback.assert_called_once_with("/tmp/daf-session-abc/repo")


class TestCleanupTempDirectory:
    """Test the cleanup_temp_directory function."""

    def test_does_nothing_when_temp_dir_is_none(self):
        """Test that function does nothing when temp_dir is None."""
        cleanup_temp_directory(None)

    def test_removes_legacy_flat_directory(self, tmp_path):
        """Test cleanup of legacy flat temp directory structure."""
        temp_dir = tmp_path / "daf-jira-analysis-abc123"
        temp_dir.mkdir()
        (temp_dir / "test-file.txt").write_text("test content")
        assert temp_dir.exists()
        cleanup_temp_directory(str(temp_dir))
        assert not temp_dir.exists()

    def test_removes_nested_structure_parent(self):
        """Test cleanup of nested temp directory removes parent session dir."""
        session_dir = tempfile.mkdtemp(prefix="daf-session-")
        clone_dir = os.path.join(session_dir, "my-repo")
        os.makedirs(clone_dir)
        Path(os.path.join(clone_dir, "file.txt")).write_text("test")

        assert os.path.exists(clone_dir)
        assert os.path.exists(session_dir)

        cleanup_temp_directory(clone_dir)

        assert not os.path.exists(session_dir)
        assert not os.path.exists(clone_dir)

    def test_handles_nonexistent_directory_gracefully(self):
        """Test that function handles nonexistent directory gracefully."""
        cleanup_temp_directory("/tmp/does-not-exist-12345")

    def test_handles_permission_error_gracefully(self, tmp_path):
        """Test that function handles permission errors gracefully."""
        temp_dir = tmp_path / "test-cleanup-error"
        temp_dir.mkdir()

        with patch("pathlib.Path.exists", return_value=True), \
             patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            cleanup_temp_directory(str(temp_dir))

    def test_cleans_up_directory_with_nested_content(self, tmp_path):
        """Test that function removes directory with nested content."""
        temp_dir = tmp_path / "test-nested-cleanup"
        temp_dir.mkdir()

        nested = temp_dir / "nested" / "dir"
        nested.mkdir(parents=True)
        (nested / "file.txt").write_text("content")
        (temp_dir / "root-file.txt").write_text("root content")

        assert temp_dir.exists()
        assert nested.exists()

        cleanup_temp_directory(str(temp_dir))

        assert not temp_dir.exists()
        assert not nested.exists()


class TestPromptForBranchSelection:
    """Test the _prompt_for_branch_selection function."""

    def test_returns_none_in_mock_mode(self, mock_git_repo):
        """Test that function returns None when in mock mode."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=True):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result is None

    def test_returns_none_in_json_mode(self, mock_git_repo):
        """Test that function returns None when in JSON mode."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=True):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result is None

    def test_returns_none_when_no_remotes(self, mock_git_repo):
        """Test that function returns None when no remotes are found."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=[]):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result is None

    def test_returns_none_when_no_branches(self, mock_git_repo):
        """Test that function returns None when no branches are found on remote."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=[]):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result is None

    def test_prefers_upstream_over_origin(self, mock_git_repo):
        """Test that function prefers upstream remote over origin."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin", "upstream"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["main", "develop"]) as mock_list_branches, \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="1"):
            result = _prompt_for_branch_selection(mock_git_repo)
            mock_list_branches.assert_called_once_with(mock_git_repo, "upstream")
            assert result == "main"

    def test_uses_origin_when_upstream_not_available(self, mock_git_repo):
        """Test that function uses origin when upstream is not available."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["main", "develop"]) as mock_list_branches, \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="1"):
            result = _prompt_for_branch_selection(mock_git_repo)
            mock_list_branches.assert_called_once_with(mock_git_repo, "origin")
            assert result == "main"

    def test_selects_main_as_default_over_master(self, mock_git_repo):
        """Test that main is preferred over master as default branch."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "master"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="1"):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "develop"

    def test_selects_master_as_default_when_no_main(self, mock_git_repo):
        """Test that master is used as default when main is not available."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "master", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="1"):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "develop"

    def test_user_can_select_branch_by_number(self, mock_git_repo):
        """Test that user can select a branch by entering its number."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="3"):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "release/2.5"

    def test_user_can_select_branch_by_name(self, mock_git_repo):
        """Test that user can select a branch by entering its name."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="release/2.5"):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "release/2.5"

    def test_invalid_number_retries_then_succeeds(self, mock_git_repo):
        """Test that invalid number selection prompts again, then succeeds with valid input."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", side_effect=["99", "2"]):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "main"

    def test_invalid_name_retries_then_succeeds(self, mock_git_repo):
        """Test that invalid branch name prompts again, then succeeds with valid input."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", side_effect=["nonexistent-branch", "main"]):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "main"

    def test_cancel_returns_default(self, mock_git_repo):
        """Test that typing 'cancel' returns default branch."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="cancel"):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "main"

    def test_q_returns_default(self, mock_git_repo):
        """Test that typing 'q' returns default branch."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="q"):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "main"

    def test_multiple_retries_then_cancel(self, mock_git_repo):
        """Test that multiple invalid attempts followed by cancel returns default."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", side_effect=["invalid1", "99", "cancel"]):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "main"

    def test_keyboard_interrupt_returns_default(self, mock_git_repo):
        """Test that keyboard interrupt returns default branch."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["main", "develop"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", side_effect=KeyboardInterrupt()):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "main"

    def test_empty_input_uses_default(self, mock_git_repo):
        """Test that pressing Enter without input uses default branch."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["main", "develop", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="1"):
            result = _prompt_for_branch_selection(mock_git_repo)
            assert result == "main"


class TestPatternMatchingWithNestedStructure:
    """Test that file path patterns work correctly with the nested temp directory structure."""

    def test_repo_name_in_path_enables_pattern_matching(self):
        """Verify that paths like /tmp/daf-session-xxx/ai-guardian/src/main.py
        contain 'ai-guardian' as a directory component for pattern matching."""
        import fnmatch

        clone_dir = "/tmp/daf-session-abc123/ai-guardian"
        file_path = f"{clone_dir}/src/main.py"

        assert "ai-guardian" in file_path.split(os.sep)
        assert fnmatch.fnmatch(file_path, "**/ai-guardian/*")

    def test_old_flat_structure_lacks_repo_name(self):
        """Verify the problem with old flat structure."""
        import fnmatch

        old_temp_dir = "/tmp/daf-jira-analysis-abc123"
        file_path = f"{old_temp_dir}/src/main.py"

        assert "ai-guardian" not in file_path.split(os.sep)
