"""Tests for source branch numbered list selection (Issue #524)."""

from pathlib import Path
from unittest.mock import patch, Mock, call

import pytest

from devflow.cli.commands.new_command import (
    _prompt_for_source_branch,
    _prompt_for_source_branch_text,
)
from devflow.git.utils import GitUtils


class TestPromptForSourceBranch:
    """Tests for _prompt_for_source_branch numbered list."""

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    def test_shows_numbered_list_and_selects_branch(self, mock_branches, mock_prompt):
        """User selects a branch by number from the list."""
        mock_branches.return_value = ["dev/1.14.0", "main", "release-1.13"]
        mock_prompt.return_value = "2"

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result == "main"
        mock_prompt.assert_called_once()
        call_kwargs = mock_prompt.call_args
        assert call_kwargs[1]["default"] == "2"  # main is index 2, should be default

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    def test_selects_non_default_branch(self, mock_branches, mock_prompt):
        """User selects a branch that is not the default."""
        mock_branches.return_value = ["dev/1.14.0", "main", "release-1.13"]
        mock_prompt.return_value = "1"

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result == "dev/1.14.0"

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    def test_cancel_returns_none(self, mock_branches, mock_prompt):
        """User selects cancel option."""
        mock_branches.return_value = ["main", "develop"]
        mock_prompt.return_value = "4"  # cancel = len(branches) + 2 = 4

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result is None

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    @patch.object(GitUtils, "branch_exists", return_value=True)
    def test_custom_branch_falls_back_to_text(self, mock_exists, mock_branches, mock_prompt):
        """User selects custom branch option, then types branch name."""
        mock_branches.return_value = ["main", "develop"]
        # First call: select custom (option 3 = len + 1)
        # Second call: type branch name
        mock_prompt.side_effect = ["3", "feature/custom"]

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result == "feature/custom"
        assert mock_prompt.call_count == 2

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    @patch.object(GitUtils, "branch_exists", return_value=True)
    def test_falls_back_to_text_when_no_remote_branches(self, mock_exists, mock_branches, mock_prompt):
        """Falls back to text input when no remote branches found."""
        mock_branches.return_value = []
        mock_prompt.return_value = "main"

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result == "main"
        mock_prompt.assert_called_once_with("Enter source branch", default="main")

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "list_remote_branches")
    def test_default_choice_is_first_when_default_not_in_list(self, mock_branches, mock_prompt):
        """Default choice is 1 when default_base not in branch list."""
        mock_branches.return_value = ["develop", "staging"]
        mock_prompt.return_value = "1"

        result = _prompt_for_source_branch(Path("/repo"), "main")

        assert result == "develop"
        call_kwargs = mock_prompt.call_args
        assert call_kwargs[1]["default"] == "1"


class TestPromptForSourceBranchText:
    """Tests for _prompt_for_source_branch_text fallback."""

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "branch_exists", return_value=True)
    def test_accepts_valid_branch(self, mock_exists, mock_prompt):
        """Accepts a valid branch name."""
        mock_prompt.return_value = "develop"

        result = _prompt_for_source_branch_text(Path("/repo"), "main")

        assert result == "develop"

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    def test_cancel_returns_none(self, mock_prompt):
        """Returns None when user types cancel."""
        mock_prompt.return_value = "cancel"

        result = _prompt_for_source_branch_text(Path("/repo"), "main")

        assert result is None

    @patch("devflow.cli.commands.new_command.Prompt.ask")
    @patch.object(GitUtils, "branch_exists")
    def test_retries_on_invalid_then_accepts_valid(self, mock_exists, mock_prompt):
        """Retries when branch doesn't exist, accepts when valid."""
        mock_exists.side_effect = [False, True]
        mock_prompt.side_effect = ["nonexistent", "main"]

        with patch("devflow.cli.commands.new_command._show_branch_suggestions"):
            result = _prompt_for_source_branch_text(Path("/repo"), "main")

        assert result == "main"
        assert mock_prompt.call_count == 2
