"""Tests for branch creation from specific source branch."""

import subprocess
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from devflow.cli.commands.new_command import _handle_branch_creation
from devflow.git.utils import GitUtils


def test_list_local_branches(tmp_path):
    """Test listing local branches."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create additional branches
    subprocess.run(["git", "checkout", "-b", "feature/new-ui"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "bugfix/critical"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # List local branches
    branches = GitUtils.list_local_branches(tmp_path)

    # Should have 3 branches (sorted)
    assert len(branches) == 3
    assert "bugfix/critical" in branches
    assert "feature/new-ui" in branches
    assert "main" in branches
    # Verify they're sorted
    assert branches == sorted(branches)


def test_handle_branch_creation_from_specific_branch_with_uncommitted_changes(tmp_path):
    """Test that creating branch aborts when user declines to continue with uncommitted changes."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create another branch
    subprocess.run(["git", "checkout", "-b", "develop"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Create uncommitted changes
    (tmp_path / "uncommitted.txt").write_text("uncommitted changes")

    # Mock config
    mock_config = Mock()
    mock_config.prompts = Mock()
    mock_config.prompts.default_branch_strategy = None

    # Mock user declining to continue with uncommitted changes
    with patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test-feature'):

        # User declines to continue with uncommitted changes
        mock_confirm.return_value = False

        result = _handle_branch_creation(
            str(tmp_path),
            "AAP-12345",
            "test feature",
            auto_from_default=False,
            config=mock_config
        )

        # Should return False because user declined to continue with uncommitted changes
        assert result is False


def test_handle_branch_creation_from_specific_branch_success(tmp_path):
    """Test successful branch creation from specific source branch."""
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
    mock_config.prompts.default_branch_strategy = None

    # Mock user creating branch from develop
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test-feature'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True):

        # User says yes to create branch, accepts suggested name, selects develop as source
        mock_confirm.return_value = True
        # First Prompt.ask: branch name (accept default)
        # Second Prompt.ask: source branch (select develop)
        mock_prompt.side_effect = ["aap-12345-test-feature", "develop"]

        result = _handle_branch_creation(
            str(tmp_path),
            "AAP-12345",
            "test feature",
            auto_from_default=False,
            config=mock_config
        )

        # Should successfully create the branch and return tuple (branch_name, source_branch)
        assert isinstance(result, tuple)
        branch_name, source_branch = result
        assert branch_name == "aap-12345-test-feature"
        assert source_branch == "develop"

        # Verify we're on the new branch
        current_branch = GitUtils.get_current_branch(tmp_path)
        assert current_branch == "aap-12345-test-feature"

        # Verify the new branch has the develop.txt file (created from develop branch)
        assert (tmp_path / "develop.txt").exists()


def test_handle_branch_creation_from_current_branch(tmp_path):
    """Test branch creation from current branch (auto mode)."""
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
    mock_config.prompts.default_branch_strategy = None

    # Test auto mode (uses default source branch)
    with patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True), \
         patch.object(GitUtils, 'create_branch', return_value=True):

        # Use auto_from_default=True to skip prompts
        result = _handle_branch_creation(
            str(tmp_path),
            "AAP-12345",
            "test",
            auto_from_default=True,
            config=mock_config
        )

        # Should successfully create branch in auto mode and return tuple
        assert isinstance(result, tuple)
        branch_name, source_branch = result
        assert branch_name == "aap-12345-test"
        assert source_branch == "main"


def test_handle_branch_creation_works_for_daf_open(tmp_path):
    """Test that branch creation works when called from daf open (interactive mode)."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create develop branch
    subprocess.run(["git", "checkout", "-b", "develop"], cwd=tmp_path, capture_output=True)
    (tmp_path / "develop.txt").write_text("develop feature")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Develop feature"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock config with no default strategy
    mock_config = Mock()
    mock_config.prompts = Mock()
    mock_config.prompts.default_branch_strategy = None

    # Simulate daf open call: only passes project_path, issue_key, goal (no auto_from_default)
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-from-open'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'checkout_branch', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True), \
         patch.object(GitUtils, 'create_branch', return_value=True):

        # Simulate user choosing: yes to create branch, accept suggested name, select develop as source
        mock_confirm.return_value = True
        # First Prompt.ask: branch name (accept default)
        # Second Prompt.ask: source branch (select develop)
        mock_prompt.side_effect = ["aap-12345-from-open", "develop"]

        # Call without auto_from_default (like daf open does)
        result = _handle_branch_creation(
            str(tmp_path),
            "AAP-12345",
            "test from open",
            config=mock_config  # Pass mock config to prevent loading default
            # Note: auto_from_default not passed, defaults to False
        )

        # Should successfully create branch and return tuple
        assert isinstance(result, tuple)
        branch_name, source_branch = result
        assert branch_name == "aap-12345-from-open"
        assert source_branch == "develop"

        # Verify Prompt.ask was called for branch name and source branch
        assert mock_prompt.call_count == 2
