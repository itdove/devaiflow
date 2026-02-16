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
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=True) as mock_checkout, \
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
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=False) as mock_checkout, \
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
             patch("devflow.utils.temp_directory.GitUtils.checkout_branch", return_value=True) as mock_checkout, \
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
             patch("devflow.utils.temp_directory.GitUtils.is_git_repository", return_value=True):

            result = prompt_and_clone_to_temp(mock_git_repo)

            # Should still succeed even if no branch can be checked out
            assert result is not None
            temp_directory, original_project_path = result
            assert temp_directory == temp_dir
            assert original_project_path == str(mock_git_repo.absolute())


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
