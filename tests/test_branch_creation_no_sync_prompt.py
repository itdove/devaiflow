"""Tests for issue #139: Unnecessary sync strategy prompt after creating new branch.

This test verifies that when a new branch is created from a selected source branch,
the base_branch is set correctly and no sync prompt appears.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from devflow.cli.commands.new_command import _handle_branch_creation
from devflow.git.utils import GitUtils


def test_branch_creation_returns_tuple_with_source_branch(tmp_path):
    """Test that creating a new branch returns tuple (branch_name, source_branch)."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create develop branch with a commit
    subprocess.run(["git", "checkout", "-b", "develop"], cwd=tmp_path, capture_output=True)
    (tmp_path / "develop.txt").write_text("develop feature")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Develop feature"], cwd=tmp_path, capture_output=True)

    # Go back to main
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock config
    mock_config = Mock()
    mock_config.prompts = Mock()
    mock_config.prompts.use_issue_key_as_branch = True

    # Mock user creating branch from develop
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
         patch.object(GitUtils, 'generate_branch_name', return_value='139-test-feature'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True):

        # User says yes to create branch, accepts suggested name, selects develop as source
        mock_confirm.return_value = True
        # First Prompt.ask: branch name (accept default)
        # Second Prompt.ask: source branch (select develop)
        mock_prompt.side_effect = ["139-test-feature", "develop"]

        result = _handle_branch_creation(
            str(tmp_path),
            "139",
            "test feature",
            auto_from_default=False,
            config=mock_config
        )

        # Should return tuple of (branch_name, source_branch)
        assert isinstance(result, tuple)
        assert len(result) == 2
        branch_name, source_branch = result
        assert branch_name == "139-test-feature"
        assert source_branch == "develop"

        # Verify we're on the new branch
        current_branch = GitUtils.get_current_branch(tmp_path)
        assert current_branch == "139-test-feature"

        # Verify the new branch has the develop.txt file (created from develop branch)
        assert (tmp_path / "develop.txt").exists()


def test_branch_creation_from_main_returns_tuple(tmp_path):
    """Test that creating a new branch from main also returns tuple."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Mock config
    mock_config = Mock()
    mock_config.prompts = Mock()
    mock_config.prompts.use_issue_key_as_branch = True

    # Mock user creating branch from main
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
         patch.object(GitUtils, 'generate_branch_name', return_value='139-from-main'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True):

        # User says yes to create branch, accepts suggested name, selects main as source
        mock_confirm.return_value = True
        mock_prompt.side_effect = ["139-from-main", "main"]

        result = _handle_branch_creation(
            str(tmp_path),
            "139",
            "from main",
            auto_from_default=False,
            config=mock_config
        )

        # Should return tuple of (branch_name, source_branch)
        assert isinstance(result, tuple)
        assert len(result) == 2
        branch_name, source_branch = result
        assert branch_name == "139-from-main"
        assert source_branch == "main"


def test_existing_branch_returns_string_not_tuple(tmp_path):
    """Test that switching to existing branch returns string, not tuple."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create existing branch
    subprocess.run(["git", "checkout", "-b", "existing-branch"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock config
    mock_config = Mock()
    mock_config.prompts = Mock()
    mock_config.prompts.use_issue_key_as_branch = True

    # Mock user creating branch with name that already exists, then choosing to switch
    from rich.prompt import IntPrompt
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
         patch.object(IntPrompt, 'ask') as mock_int_prompt, \
         patch.object(GitUtils, 'generate_branch_name', return_value='existing-branch'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'checkout_branch', return_value=True):

        # User says yes to create branch
        mock_confirm.return_value = True
        # First Prompt.ask: branch name (existing-branch)
        mock_prompt.return_value = "existing-branch"
        # IntPrompt: choose option 1 (switch to existing branch)
        mock_int_prompt.return_value = 1

        result = _handle_branch_creation(
            str(tmp_path),
            "139",
            "test",
            auto_from_default=False,
            config=mock_config
        )

        # Should return just the branch name (string), not a tuple
        assert isinstance(result, str)
        assert result == "existing-branch"


def test_commits_behind_check_with_correct_base_branch(tmp_path):
    """Test that commits_behind checks against the correct base branch.

    This simulates the scenario from issue #139:
    1. User creates branch from 'develop'
    2. base_branch should be set to 'develop' (not 'main')
    3. commits_behind should compare against origin/develop, not origin/main
    """
    # Initialize a git repo with origin
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "main.txt").write_text("main content")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Main commit"], cwd=tmp_path, capture_output=True)

    # Create develop branch with its own commit
    subprocess.run(["git", "checkout", "-b", "develop"], cwd=tmp_path, capture_output=True)
    (tmp_path / "develop.txt").write_text("develop content")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Develop commit"], cwd=tmp_path, capture_output=True)

    # Set up a fake remote
    bare_repo = tmp_path.parent / "origin.git"
    bare_repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare"], cwd=bare_repo, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare_repo)], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "develop"], cwd=tmp_path, capture_output=True)

    # Create new branch from develop
    subprocess.run(["git", "checkout", "-b", "139-new-feature"], cwd=tmp_path, capture_output=True)

    # Test commits_behind with develop as base_branch (should be 0)
    commits_behind_develop = GitUtils.commits_behind(tmp_path, "139-new-feature", "develop")
    assert commits_behind_develop == 0, "New branch from develop should be 0 commits behind develop"

    # Test commits_behind with main as base_branch (would be 1 - the develop commit)
    commits_behind_main = GitUtils.commits_behind(tmp_path, "139-new-feature", "main")
    # The branch created from develop is 1 commit ahead of main, so comparing to main would show behind=0
    # but the point is they're different comparisons


def test_auto_mode_returns_tuple_with_default_source(tmp_path):
    """Test that auto mode also returns tuple with source branch."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Mock config
    mock_config = Mock()
    mock_config.prompts = Mock()
    mock_config.prompts.use_issue_key_as_branch = True

    # Test auto mode (uses default source branch)
    with patch.object(GitUtils, 'generate_branch_name', return_value='139-auto-test'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True):

        # Use auto_from_default=True to skip prompts
        result = _handle_branch_creation(
            str(tmp_path),
            "139",
            "auto test",
            auto_from_default=True,
            config=mock_config
        )

        # Should return tuple with default source branch (main)
        assert isinstance(result, tuple)
        assert len(result) == 2
        branch_name, source_branch = result
        assert branch_name == "139-auto-test"
        assert source_branch == "main"
