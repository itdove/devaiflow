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
    """Test that creating branch from specific source aborts when there are uncommitted changes."""
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

    # Mock user selecting strategy 3 (from specific branch)
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test-feature'):

        # User says yes to create branch, then selects strategy 3
        mock_confirm.return_value = True
        mock_prompt.return_value = "3"  # Strategy 3: from specific branch

        result = _handle_branch_creation(
            str(tmp_path),
            "AAP-12345",
            "test feature",
            auto_from_default=False,
            config=mock_config
        )

        # Should return None because of uncommitted changes
        assert result is None


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

    # Mock user selecting strategy 3 (from specific branch) and selecting develop (branch index 1)
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test-feature'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True):

        # User says yes to create branch, selects strategy 3, then selects branch 1 (develop)
        mock_confirm.return_value = True
        mock_prompt.side_effect = ["3", "1"]  # Strategy 3, then branch choice 1

        result = _handle_branch_creation(
            str(tmp_path),
            "AAP-12345",
            "test feature",
            auto_from_default=False,
            config=mock_config
        )

        # Should successfully create the branch
        assert result == "aap-12345-test-feature"

        # Verify we're on the new branch
        current_branch = GitUtils.get_current_branch(tmp_path)
        assert current_branch == "aap-12345-test-feature"

        # Verify the new branch has the develop.txt file (created from develop branch)
        assert (tmp_path / "develop.txt").exists()


def test_handle_branch_creation_strategy_options(tmp_path):
    """Test that all three strategy options are available."""
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

    # Test that strategy prompt accepts choices "1", "2", and "3"
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'get_default_branch', return_value='main'), \
         patch.object(GitUtils, 'checkout_branch', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True), \
         patch.object(GitUtils, 'create_branch', return_value=True):

        mock_confirm.return_value = True
        mock_prompt.return_value = "1"  # Strategy 1: from current

        result = _handle_branch_creation(
            str(tmp_path),
            "AAP-12345",
            "test",
            auto_from_default=False,
            config=mock_config
        )

        # Check that Prompt.ask was called with choices including "3"
        strategy_call = None
        for call in mock_prompt.call_args_list:
            if call[1].get('choices') == ["1", "2", "3"]:
                strategy_call = call
                break

        assert strategy_call is not None, "Strategy prompt should include choices ['1', '2', '3']"


def test_handle_branch_creation_works_for_daf_open(tmp_path):
    """Test that branch creation with strategy 3 works when called from daf open (no auto_from_default param)."""
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

        # Simulate user choosing: yes to create branch, strategy 3, select develop (branch 1)
        mock_confirm.return_value = True
        mock_prompt.side_effect = ["3", "1"]  # Strategy 3, branch 1 (develop)

        # Call without auto_from_default (like daf open does)
        result = _handle_branch_creation(
            str(tmp_path),
            "AAP-12345",
            "test from open",
            config=mock_config  # Pass mock config to prevent loading default
            # Note: auto_from_default not passed, defaults to False
        )

        # Should successfully create branch
        assert result == "aap-12345-from-open"

        # Verify strategy prompt was called with all 3 options
        strategy_call = None
        for call in mock_prompt.call_args_list:
            if call[1].get('choices') == ["1", "2", "3"]:
                strategy_call = call
                break

        assert strategy_call is not None, "Strategy prompt should be shown with all 3 choices"
