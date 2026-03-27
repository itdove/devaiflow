"""Tests for issue #331: Branch workflow UX issues.

This test file covers two issues:
1. Missing branch selection when declining branch creation
2. New branch created from outdated base branch
"""

import subprocess
from pathlib import Path
from unittest.mock import patch, Mock, call

import pytest

from devflow.cli.commands.new_command import _handle_branch_creation
from devflow.git.utils import GitUtils


class TestBranchSelectionWhenDecliningCreation:
    """Tests for Issue #1: Missing branch selection prompt when declining branch creation."""

    def test_branch_selection_prompt_shown_when_declining_creation(self, tmp_path):
        """Test that branch selection prompt appears when user declines branch creation."""
        # Initialize a git repo with multiple branches
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        # Create additional branches
        subprocess.run(["git", "checkout", "-b", "develop"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "feature/old-work"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

        # Mock config
        mock_config = Mock()
        mock_config.prompts = Mock()
        mock_config.prompts.use_issue_key_as_branch = True

        # Mock user declining branch creation and selecting develop
        with patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
             patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
             patch.object(GitUtils, 'fetch_origin', return_value=(True, None)), \
             patch.object(GitUtils, 'merge_branch', return_value=(True, None)):

            # User declines branch creation
            mock_confirm.return_value = False
            # User selects branch 1 (develop - branches are sorted alphabetically)
            mock_prompt.return_value = "1"

            result = _handle_branch_creation(
                str(tmp_path),
                "331",
                "test issue",
                auto_from_default=False,
                config=mock_config
            )

            # Verify result is None (no branch created)
            assert result is None

            # Verify we're now on develop branch
            current_branch = GitUtils.get_current_branch(tmp_path)
            assert current_branch == "develop"

    def test_branch_selection_by_name(self, tmp_path):
        """Test that user can select branch by name instead of number."""
        # Initialize a git repo with multiple branches
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        # Create additional branches
        subprocess.run(["git", "checkout", "-b", "develop"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

        # Mock config
        mock_config = Mock()
        mock_config.prompts = Mock()
        mock_config.prompts.use_issue_key_as_branch = True

        # Mock user declining branch creation and entering branch name
        with patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
             patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
             patch.object(GitUtils, 'fetch_origin', return_value=(True, None)), \
             patch.object(GitUtils, 'merge_branch', return_value=(True, None)):

            # User declines branch creation
            mock_confirm.return_value = False
            # User types branch name "develop"
            mock_prompt.return_value = "develop"

            result = _handle_branch_creation(
                str(tmp_path),
                "331",
                "test issue",
                auto_from_default=False,
                config=mock_config
            )

            # Verify result is None (no branch created)
            assert result is None

            # Verify we're now on develop branch
            current_branch = GitUtils.get_current_branch(tmp_path)
            assert current_branch == "develop"

    def test_branch_selection_keep_current_on_enter(self, tmp_path):
        """Test that pressing Enter keeps current branch."""
        # Initialize a git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        # Create additional branch
        subprocess.run(["git", "checkout", "-b", "develop"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

        # Mock config
        mock_config = Mock()
        mock_config.prompts = Mock()
        mock_config.prompts.use_issue_key_as_branch = True

        # Mock user declining branch creation and pressing Enter (empty string)
        with patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
             patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
             patch.object(GitUtils, 'fetch_origin', return_value=(True, None)), \
             patch.object(GitUtils, 'merge_branch', return_value=(True, None)):

            # User declines branch creation
            mock_confirm.return_value = False
            # User presses Enter (empty string = keep current)
            mock_prompt.return_value = ""

            result = _handle_branch_creation(
                str(tmp_path),
                "331",
                "test issue",
                auto_from_default=False,
                config=mock_config
            )

            # Verify result is None (no branch created)
            assert result is None

            # Verify we're still on main branch
            current_branch = GitUtils.get_current_branch(tmp_path)
            assert current_branch == "main"

    def test_no_branch_selection_with_single_branch(self, tmp_path):
        """Test that branch selection is skipped when only one branch exists."""
        # Initialize a git repo with only main branch
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        # Mock config
        mock_config = Mock()
        mock_config.prompts = Mock()
        mock_config.prompts.use_issue_key_as_branch = True

        # Mock user declining branch creation
        with patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
             patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
             patch.object(GitUtils, 'fetch_origin', return_value=(True, None)), \
             patch.object(GitUtils, 'merge_branch', return_value=(True, None)):

            # User declines branch creation
            mock_confirm.return_value = False

            result = _handle_branch_creation(
                str(tmp_path),
                "331",
                "test issue",
                auto_from_default=False,
                config=mock_config
            )

            # Verify result is None (no branch created)
            assert result is None

            # Verify branch selection was NOT prompted (only one branch exists)
            # Prompt.ask should not be called for branch selection
            assert not mock_prompt.called


class TestPullBeforeCreatingBranch:
    """Tests for Issue #2: New branch created from outdated base branch."""

    def test_pull_happens_when_already_on_source_branch(self, tmp_path):
        """Test that pull happens even when already on source branch."""
        # Initialize a git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        # Mock config
        mock_config = Mock()
        mock_config.prompts = Mock()
        mock_config.prompts.use_issue_key_as_branch = True

        # Mock user creating branch from main (already on main)
        with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
             patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
             patch.object(GitUtils, 'generate_branch_name', return_value='331-test-feature'), \
             patch.object(GitUtils, 'fetch_origin', return_value=(True, None)) as mock_fetch, \
             patch.object(GitUtils, 'pull_current_branch', return_value=(True, None)) as mock_pull:

            # User says yes to create branch, accepts suggested name, selects main as source
            mock_confirm.return_value = True
            mock_prompt.side_effect = ["331-test-feature", "main"]

            result = _handle_branch_creation(
                str(tmp_path),
                "331",
                "test feature",
                auto_from_default=False,
                config=mock_config
            )

            # Verify pull was called even though we were already on main
            mock_pull.assert_called_once()

            # Verify branch was created
            assert isinstance(result, tuple)
            assert result[0] == "331-test-feature"
            assert result[1] == "main"

    def test_pull_happens_after_checkout(self, tmp_path):
        """Test that pull happens after checking out source branch."""
        # Initialize a git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        # Create develop branch
        subprocess.run(["git", "checkout", "-b", "develop"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

        # Mock config
        mock_config = Mock()
        mock_config.prompts = Mock()
        mock_config.prompts.use_issue_key_as_branch = True

        # Mock user creating branch from develop (while on main)
        with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
             patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
             patch.object(GitUtils, 'generate_branch_name', return_value='331-from-develop'), \
             patch.object(GitUtils, 'fetch_origin', return_value=(True, None)) as mock_fetch, \
             patch.object(GitUtils, 'pull_current_branch', return_value=(True, None)) as mock_pull:

            # User says yes to create branch, accepts suggested name, selects develop as source
            mock_confirm.return_value = True
            mock_prompt.side_effect = ["331-from-develop", "develop"]

            result = _handle_branch_creation(
                str(tmp_path),
                "331",
                "from develop",
                auto_from_default=False,
                config=mock_config
            )

            # Verify pull was called after checkout
            mock_pull.assert_called_once()

            # Verify branch was created from develop
            assert isinstance(result, tuple)
            assert result[0] == "331-from-develop"
            assert result[1] == "develop"

    def test_pull_failure_warns_user_in_interactive_mode(self, tmp_path):
        """Test that pull failure warns user and asks for confirmation in interactive mode."""
        # Initialize a git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        # Mock config
        mock_config = Mock()
        mock_config.prompts = Mock()
        mock_config.prompts.use_issue_key_as_branch = True

        # Mock user creating branch from main, but pull fails
        with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
             patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm, \
             patch.object(GitUtils, 'generate_branch_name', return_value='331-test'), \
             patch.object(GitUtils, 'fetch_origin', return_value=(True, None)), \
             patch.object(GitUtils, 'pull_current_branch', return_value=(False, "Network error")):

            # User says yes to create branch, accepts suggested name, selects main
            # User says NO to continue after pull failure
            mock_confirm.side_effect = [True, False]  # True for "create branch?", False for "continue anyway?"
            mock_prompt.side_effect = ["331-test", "main"]

            result = _handle_branch_creation(
                str(tmp_path),
                "331",
                "test",
                auto_from_default=False,
                config=mock_config
            )

            # Verify branch creation was cancelled due to pull failure
            assert result is None

            # Verify user was asked to confirm continuation
            assert mock_confirm.call_count == 2

    def test_pull_failure_continues_in_non_interactive_mode(self, tmp_path):
        """Test that pull failure continues in non-interactive mode."""
        # Initialize a git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        # Mock config
        mock_config = Mock()
        mock_config.prompts = Mock()
        mock_config.prompts.use_issue_key_as_branch = True

        # Mock pull failure in non-interactive mode
        with patch.object(GitUtils, 'generate_branch_name', return_value='331-test'), \
             patch.object(GitUtils, 'fetch_origin', return_value=(True, None)), \
             patch.object(GitUtils, 'pull_current_branch', return_value=(False, "Network error")):

            result = _handle_branch_creation(
                str(tmp_path),
                "331",
                "test",
                auto_from_default=False,
                config=mock_config,
                branch_name="331-test",
                source_branch="main",
                non_interactive=True
            )

            # Verify branch was created despite pull failure (non-interactive mode)
            assert isinstance(result, tuple)
            assert result[0] == "331-test"

    def test_no_pull_for_remote_branch(self, tmp_path):
        """Test that pull is skipped for remote branches (e.g., origin/main)."""
        # Initialize a git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

        # Create initial commit
        (tmp_path / "test.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

        # Mock config
        mock_config = Mock()
        mock_config.prompts = Mock()
        mock_config.prompts.use_issue_key_as_branch = True

        # Mock checkout_branch to succeed for remote branch
        with patch.object(GitUtils, 'generate_branch_name', return_value='331-test'), \
             patch.object(GitUtils, 'fetch_origin', return_value=(True, None)), \
             patch.object(GitUtils, 'checkout_branch', return_value=(True, None)), \
             patch.object(GitUtils, 'create_branch', return_value=(True, None)), \
             patch.object(GitUtils, 'pull_current_branch', return_value=(True, None)) as mock_pull:

            # Create branch from origin/main (provided via parameter)
            result = _handle_branch_creation(
                str(tmp_path),
                "331",
                "test",
                auto_from_default=False,
                config=mock_config,
                branch_name="331-test",
                source_branch="origin/main"
            )

            # Verify pull was NOT called (source branch contains '/')
            mock_pull.assert_not_called()

            # Verify branch creation was attempted (tuple returned)
            assert isinstance(result, tuple)
            assert result[0] == "331-test"
            assert result[1] == "origin/main"
