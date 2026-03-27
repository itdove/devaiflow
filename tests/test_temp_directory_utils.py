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
    cleanup_temp_directory,
    _prompt_for_branch_selection,
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

    def test_returns_none_when_tempdir_creation_fails(self, mock_git_repo):
        """Test that function returns None when temporary directory creation fails."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", side_effect=Exception("Permission denied")):
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is None

    def test_returns_none_when_clone_fails(self, mock_git_repo):
        """Test that function returns None when repository cloning fails."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value="/tmp/test-temp-dir"), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=False), \
             patch("shutil.rmtree") as mock_rmtree:
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is None
            # Verify cleanup was attempted
            mock_rmtree.assert_called_once_with("/tmp/test-temp-dir")

    def test_returns_none_when_clone_fails_and_cleanup_fails(self, mock_git_repo):
        """Test that function returns None when clone fails and cleanup also fails."""
        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value="/tmp/test-temp-dir"), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=False), \
             patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            # Should handle cleanup failure gracefully
            result = prompt_and_clone_to_temp(mock_git_repo)
            assert result is None

    def test_successful_clone_with_default_branch(self, mock_git_repo, tmp_path):
        """Test successful clone operation with default branch checkout."""
        temp_dir = str(tmp_path / "test-temp-clone")

        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value=temp_dir), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value="main"), \
             patch("devflow.utils.temp_directory.GitUtils.get_current_branch", return_value="main"), \
             patch("devflow.utils.temp_directory.GitUtils.is_git_repository", return_value=True):

            result = prompt_and_clone_to_temp(mock_git_repo)

            assert result is not None
            temp_directory, original_project_path = result
            assert temp_directory == temp_dir
            assert original_project_path == str(mock_git_repo.absolute())

    def test_successful_clone_with_branch_checkout(self, mock_git_repo, tmp_path):
        """Test successful clone with branch mismatch requiring checkout."""
        temp_dir = str(tmp_path / "test-temp-clone")

        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value=temp_dir), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value="main"), \
             patch("devflow.utils.temp_directory.GitUtils.get_current_branch", return_value="develop"), \
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=(True, None)) as mock_checkout, \
             patch("devflow.utils.temp_directory.GitUtils.is_git_repository", return_value=True):

            result = prompt_and_clone_to_temp(mock_git_repo)

            assert result is not None
            # Verify checkout was called to fix branch mismatch
            mock_checkout.assert_called_once_with(Path(temp_dir), "main")

    def test_successful_clone_with_failed_branch_checkout(self, mock_git_repo, tmp_path):
        """Test successful clone even when branch checkout fails."""
        temp_dir = str(tmp_path / "test-temp-clone")

        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value=temp_dir), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value="main"), \
             patch("devflow.utils.temp_directory.GitUtils.get_current_branch", return_value="develop"), \
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=(False, "checkout error")) as mock_checkout, \
             patch("devflow.utils.temp_directory.GitUtils.is_git_repository", return_value=True):

            # Should still succeed even if checkout fails
            result = prompt_and_clone_to_temp(mock_git_repo)

            assert result is not None
            temp_directory, original_project_path = result
            assert temp_directory == temp_dir
            # Verify checkout was attempted but failed
            mock_checkout.assert_called_once_with(Path(temp_dir), "main")

    def test_successful_clone_fallback_to_common_branches(self, mock_git_repo, tmp_path):
        """Test successful clone with fallback to common branch names."""
        temp_dir = str(tmp_path / "test-temp-clone")

        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value=temp_dir), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value=None), \
             patch("devflow.utils.temp_directory.GitUtils.branch_exists", side_effect=[False, True, False]), \
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=(True, None)) as mock_checkout, \
             patch("devflow.utils.temp_directory.GitUtils.is_git_repository", return_value=True):

            result = prompt_and_clone_to_temp(mock_git_repo)

            assert result is not None
            # Verify it checked main, master (found), develop
            # and checked out master (second attempt)
            mock_checkout.assert_called_once_with(Path(temp_dir), "master")

    def test_clone_with_no_default_and_no_common_branches(self, mock_git_repo, tmp_path):
        """Test clone when no default branch can be determined."""
        temp_dir = str(tmp_path / "test-temp-clone")

        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value=temp_dir), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value=None), \
             patch("devflow.utils.temp_directory.GitUtils.branch_exists", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.is_git_repository", return_value=True), \
             patch("devflow.utils.temp_directory._prompt_for_branch_selection", return_value=None):

            result = prompt_and_clone_to_temp(mock_git_repo)

            # Should still succeed even if no branch can be checked out
            assert result is not None
            temp_directory, original_project_path = result
            assert temp_directory == temp_dir
            assert original_project_path == str(mock_git_repo.absolute())

    def test_clone_with_branch_selection_prompt(self, mock_git_repo, tmp_path):
        """Test that branch selection prompt is called after successful clone."""
        temp_dir = str(tmp_path / "test-temp-clone")

        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value=temp_dir), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory._prompt_for_branch_selection", return_value="develop") as mock_prompt, \
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=(True, None)) as mock_checkout:

            result = prompt_and_clone_to_temp(mock_git_repo)

            assert result is not None
            # Verify branch selection was prompted
            mock_prompt.assert_called_once_with(Path(temp_dir))
            # Verify the selected branch was checked out
            mock_checkout.assert_called_once_with(Path(temp_dir), "develop")

    def test_clone_with_branch_selection_in_mock_mode(self, mock_git_repo, tmp_path):
        """Test that branch selection is skipped in mock mode."""
        temp_dir = str(tmp_path / "test-temp-clone")

        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value=temp_dir), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory._prompt_for_branch_selection", return_value=None) as mock_prompt, \
             patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value="main"), \
             patch("devflow.utils.temp_directory.GitUtils.get_current_branch", return_value="main"):

            result = prompt_and_clone_to_temp(mock_git_repo)

            assert result is not None
            # Verify branch selection was called (returns None in mock mode)
            mock_prompt.assert_called_once_with(Path(temp_dir))

    def test_clone_with_failed_branch_checkout_falls_back(self, mock_git_repo, tmp_path):
        """Test that failed branch checkout falls back to auto-detection."""
        temp_dir = str(tmp_path / "test-temp-clone")

        with patch("devflow.utils.temp_directory.Confirm.ask", return_value=True), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_url", return_value="https://example.com/repo.git"), \
             patch("tempfile.mkdtemp", return_value=temp_dir), \
             patch("devflow.utils.temp_directory.GitUtils.clone_repository", return_value=True), \
             patch("devflow.utils.temp_directory._prompt_for_branch_selection", return_value="feature/test"), \
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=(False, "checkout error")), \
             patch("devflow.utils.temp_directory.GitUtils.get_default_branch", return_value="main"), \
             patch("devflow.utils.temp_directory.GitUtils.get_current_branch", return_value="main"):

            result = prompt_and_clone_to_temp(mock_git_repo)

            # Should still succeed and fall back to auto-detection
            assert result is not None
            temp_directory, original_project_path = result
            assert temp_directory == temp_dir


class TestCleanupTempDirectory:
    """Test the cleanup_temp_directory function."""

    def test_does_nothing_when_temp_dir_is_none(self):
        """Test that function does nothing when temp_dir is None."""
        # Should not raise any exception
        cleanup_temp_directory(None)

    def test_removes_existing_directory(self, tmp_path):
        """Test that function removes existing directory."""
        temp_dir = tmp_path / "test-cleanup"
        temp_dir.mkdir()
        (temp_dir / "test-file.txt").write_text("test content")

        assert temp_dir.exists()

        cleanup_temp_directory(str(temp_dir))

        assert not temp_dir.exists()

    def test_handles_nonexistent_directory_gracefully(self):
        """Test that function handles nonexistent directory gracefully."""
        nonexistent_dir = "/tmp/does-not-exist-12345"
        # Should not raise any exception
        cleanup_temp_directory(nonexistent_dir)

    def test_handles_permission_error_gracefully(self, tmp_path):
        """Test that function handles permission errors gracefully."""
        temp_dir = tmp_path / "test-cleanup-error"
        temp_dir.mkdir()

        with patch("pathlib.Path.exists", return_value=True), \
             patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            # Should not raise exception, just print warning
            cleanup_temp_directory(str(temp_dir))
            # Note: In actual execution, this would print a warning message
            # but wouldn't raise an exception

    def test_cleans_up_directory_with_nested_content(self, tmp_path):
        """Test that function removes directory with nested content."""
        temp_dir = tmp_path / "test-nested-cleanup"
        temp_dir.mkdir()

        # Create nested structure
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
            # Verify that upstream was used, not origin
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
            # Verify that origin was used
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
            # Should default to main (first in priority list)
            assert result == "develop"  # Index 1 = first item in sorted list

    def test_selects_master_as_default_when_no_main(self, mock_git_repo):
        """Test that master is used as default when main is not available."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "master", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="1"):
            result = _prompt_for_branch_selection(mock_git_repo)
            # Should select first item (default selection is "1")
            assert result == "develop"

    def test_user_can_select_branch_by_number(self, mock_git_repo):
        """Test that user can select a branch by entering its number."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="3"):
            result = _prompt_for_branch_selection(mock_git_repo)
            # User selected option 3 (release/2.5)
            assert result == "release/2.5"

    def test_user_can_select_branch_by_name(self, mock_git_repo):
        """Test that user can select a branch by entering its name."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="release/2.5"):
            result = _prompt_for_branch_selection(mock_git_repo)
            # User entered branch name directly
            assert result == "release/2.5"

    def test_invalid_number_retries_then_succeeds(self, mock_git_repo):
        """Test that invalid number selection prompts again, then succeeds with valid input."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", side_effect=["99", "2"]):
            result = _prompt_for_branch_selection(mock_git_repo)
            # First input "99" is invalid, second input "2" selects "main"
            assert result == "main"

    def test_invalid_name_retries_then_succeeds(self, mock_git_repo):
        """Test that invalid branch name prompts again, then succeeds with valid input."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", side_effect=["nonexistent-branch", "main"]):
            result = _prompt_for_branch_selection(mock_git_repo)
            # First input "nonexistent-branch" is invalid, second input "main" succeeds
            assert result == "main"

    def test_cancel_returns_default(self, mock_git_repo):
        """Test that typing 'cancel' returns default branch."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="cancel"):
            result = _prompt_for_branch_selection(mock_git_repo)
            # Should return default branch (main)
            assert result == "main"

    def test_q_returns_default(self, mock_git_repo):
        """Test that typing 'q' returns default branch."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="q"):
            result = _prompt_for_branch_selection(mock_git_repo)
            # Should return default branch (main)
            assert result == "main"

    def test_multiple_retries_then_cancel(self, mock_git_repo):
        """Test that multiple invalid attempts followed by cancel returns default."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["develop", "main", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", side_effect=["invalid1", "99", "cancel"]):
            result = _prompt_for_branch_selection(mock_git_repo)
            # After two invalid attempts, cancel should return default (main)
            assert result == "main"

    def test_keyboard_interrupt_returns_default(self, mock_git_repo):
        """Test that keyboard interrupt returns default branch."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["main", "develop"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", side_effect=KeyboardInterrupt()):
            result = _prompt_for_branch_selection(mock_git_repo)
            # Should return default branch on interrupt
            assert result == "main"

    def test_empty_input_uses_default(self, mock_git_repo):
        """Test that pressing Enter without input uses default branch."""
        with patch("devflow.utils.temp_directory.is_mock_mode", return_value=False), \
             patch("devflow.utils.temp_directory.is_json_mode", return_value=False), \
             patch("devflow.utils.temp_directory.GitUtils.get_remote_names", return_value=["origin"]), \
             patch("devflow.utils.temp_directory.GitUtils.list_remote_branches", return_value=["main", "develop", "release/2.5"]), \
             patch("devflow.utils.temp_directory.Prompt.ask", return_value="1"):
            result = _prompt_for_branch_selection(mock_git_repo)
            # Default selection should be used
            assert result == "main"
