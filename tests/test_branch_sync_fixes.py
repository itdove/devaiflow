"""Tests for branch sync fixes from issue #324.

This test file covers the three critical bugs fixed:
1. commits_behind() ignoring branch parameter and using HEAD instead
2. _handle_branch_checkout() not returning status
3. Missing verification that checkout succeeded before sync
"""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devflow.git.utils import GitUtils


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_commits_behind_uses_branch_parameter_not_head(tmp_path):
    """Test that commits_behind uses the branch parameter, not HEAD.

    This tests the fix for Bug #1: commits_behind() was using HEAD instead of
    the branch parameter, causing incorrect "commits behind" counts when HEAD
    was not on the session branch.

    Scenario:
    1. Create branch-a from main
    2. Create branch-b from main with additional commit
    3. Checkout main (HEAD is now on main, not branch-a)
    4. commits_behind(path, "branch-a", "main") should return 0
       (because branch-a is up-to-date with main)
    5. Before the fix, it would return the count for HEAD (main) instead
    """
    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "main.txt").write_text("main content")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Main commit"], cwd=tmp_path, capture_output=True)

    # Set up a fake remote
    bare_repo = tmp_path.parent / "origin.git"
    bare_repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare"], cwd=bare_repo, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare_repo)], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=tmp_path, capture_output=True)

    # Create branch-a from main (up-to-date with main)
    subprocess.run(["git", "checkout", "-b", "branch-a"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "branch-a"], cwd=tmp_path, capture_output=True)

    # Go back to main and add a new commit (simulating branch-b being merged)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)
    (tmp_path / "new.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "New commit on main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=tmp_path, capture_output=True)

    # Now HEAD is on main, but we want to check if branch-a is behind
    # Fetch to get latest remote state
    subprocess.run(["git", "fetch", "origin"], cwd=tmp_path, capture_output=True)

    # Check commits_behind for branch-a (should be 1, since main has moved ahead)
    commits_behind = GitUtils.commits_behind(tmp_path, "branch-a", "main")

    # branch-a is 1 commit behind main (the "New commit on main")
    assert commits_behind == 1, (
        f"Expected branch-a to be 1 commit behind main, got {commits_behind}. "
        "This test verifies that commits_behind uses the branch parameter, not HEAD."
    )


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_commits_behind_when_head_differs_from_branch(tmp_path):
    """Test commits_behind when HEAD is on a different branch than the one being checked.

    This is the exact scenario from the bug report:
    - User is on main
    - Reopening a session for branch-a
    - commits_behind(path, "branch-a", "main") should check branch-a, not HEAD (main)
    """
    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "file1.txt").write_text("content 1")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Commit 1"], cwd=tmp_path, capture_output=True)

    # Set up remote
    bare_repo = tmp_path.parent / "test_origin.git"
    bare_repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare"], cwd=bare_repo, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare_repo)], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=tmp_path, capture_output=True)

    # Create feature branch from main (at commit 1)
    subprocess.run(["git", "checkout", "-b", "feature-123"], cwd=tmp_path, capture_output=True)

    # Switch back to main
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Verify HEAD is on main
    current_branch = GitUtils.get_current_branch(tmp_path)
    assert current_branch == "main", f"Expected to be on main, but on {current_branch}"

    # Fetch latest
    subprocess.run(["git", "fetch", "origin"], cwd=tmp_path, capture_output=True)

    # Check commits_behind for feature-123 (should be 0, it's up-to-date with main)
    commits_behind = GitUtils.commits_behind(tmp_path, "feature-123", "main")

    # feature-123 was created from main and main hasn't moved, so it should be 0 commits behind
    assert commits_behind == 0, (
        f"Expected feature-123 to be 0 commits behind main, got {commits_behind}. "
        "Before fix, this would return incorrect count because it checked HEAD instead of feature-123."
    )


def test_handle_branch_checkout_returns_true_when_already_on_branch(tmp_path):
    """Test that _handle_branch_checkout returns True when already on the correct branch.

    This tests the fix for Bug #2: _handle_branch_checkout now returns bool instead of None.
    """
    from devflow.cli.commands.open_command import _handle_branch_checkout

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Test checkout when already on the branch
    result = _handle_branch_checkout(str(tmp_path), "main", None)

    assert result is True, "Expected True when already on the correct branch"


def test_handle_branch_checkout_returns_false_when_not_git_repo(tmp_path):
    """Test that _handle_branch_checkout returns False when path is not a git repository."""
    from devflow.cli.commands.open_command import _handle_branch_checkout

    # Don't initialize git repo
    result = _handle_branch_checkout(str(tmp_path), "main", None)

    assert result is False, "Expected False when not a git repository"


@patch("devflow.cli.commands.open_command.Confirm.ask")
def test_handle_branch_checkout_returns_false_when_user_declines(mock_confirm, tmp_path):
    """Test that _handle_branch_checkout returns False when user declines to checkout.

    This tests Bug #2: the function should return False when checkout is declined.
    """
    from devflow.cli.commands.open_command import _handle_branch_checkout

    # Initialize git repo with two branches
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create feature branch
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, capture_output=True)

    # Switch back to main
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # User declines to checkout
    mock_confirm.return_value = False

    # Test checkout when user declines
    result = _handle_branch_checkout(str(tmp_path), "feature", None)

    assert result is False, "Expected False when user declines to checkout"


@patch("devflow.cli.commands.open_command.Confirm.ask")
def test_handle_branch_checkout_returns_true_when_user_accepts(mock_confirm, tmp_path):
    """Test that _handle_branch_checkout returns True when checkout succeeds."""
    from devflow.cli.commands.open_command import _handle_branch_checkout

    # Initialize git repo with two branches
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create feature branch
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, capture_output=True)

    # Switch back to main
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # User accepts checkout
    mock_confirm.return_value = True

    # Test checkout when user accepts
    result = _handle_branch_checkout(str(tmp_path), "feature", None)

    assert result is True, "Expected True when checkout succeeds"
    # Verify we're actually on the feature branch
    assert GitUtils.get_current_branch(tmp_path) == "feature"


def test_check_and_sync_fails_when_not_on_expected_branch(tmp_path):
    """Test that _check_and_sync_with_base_branch returns False when not on expected branch.

    This tests the fix for Bug #3: safety check added to verify current branch
    before proceeding with sync.
    """
    from devflow.cli.commands.open_command import _check_and_sync_with_base_branch

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create feature branch
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=tmp_path, capture_output=True)

    # Switch back to main
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Now try to sync "feature" branch while HEAD is on "main"
    # This should fail the safety check
    result = _check_and_sync_with_base_branch(
        str(tmp_path),
        "feature",  # Expected to be on feature
        "main",
        "test-session",
        None,
        None,
        None,
    )

    assert result is False, (
        "Expected False when not on expected branch. "
        "This safety check prevents syncing the wrong branch."
    )
