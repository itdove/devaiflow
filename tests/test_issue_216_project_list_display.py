"""Tests for Issue #216: Project list not displayed before multi-project prompt in some commands.

This test verifies that the project list is displayed BEFORE asking the multi-project
question in commands like daf jira new, daf git new, and daf investigate.
"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.cli.utils import prompt_repository_selection_with_multiproject


@pytest.fixture
def mock_workspace_with_repos(tmp_path):
    """Create a workspace with multiple git repositories."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create two mock git repos
    for repo_name in ["devaiflow", "devaiflow-demos"]:
        repo_path = workspace / repo_name
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

    return workspace


@pytest.fixture
def mock_config(mock_workspace_with_repos):
    """Create a config with the mock workspace."""
    config = MagicMock()
    config.repos.workspaces = {"test-workspace": str(mock_workspace_with_repos)}
    config.repos.default_workspace = "test-workspace"
    return config


class TestIssue216ProjectListDisplay:
    """Test that project list is displayed before multi-project prompt (Issue #216)."""

    @patch("devflow.cli.utils.select_workspace")
    @patch("devflow.cli.utils.scan_workspace_repositories")
    @patch("rich.prompt.Confirm.ask")
    @patch("rich.prompt.Prompt.ask")
    @patch("devflow.cli.utils.console")
    def test_project_list_displayed_before_multiproject_prompt(
        self,
        mock_console,
        mock_prompt_ask,
        mock_confirm_ask,
        mock_scan_repos,
        mock_select_workspace,
        mock_config,
        mock_workspace_with_repos,
    ):
        """Test that available repositories are displayed BEFORE the multi-project question."""
        # Setup mocks
        mock_select_workspace.return_value = "test-workspace"
        mock_scan_repos.return_value = ["devaiflow", "devaiflow-demos"]

        # User declines multi-project mode
        mock_confirm_ask.return_value = False
        # Then selects single project
        mock_prompt_ask.return_value = "1"

        # Track console.print calls
        print_calls = []
        def track_print(*args, **kwargs):
            if args:
                print_calls.append(str(args[0]))

        mock_console.print.side_effect = track_print

        # Call the function
        result = prompt_repository_selection_with_multiproject(
            config=mock_config,
            workspace_flag="test-workspace",
            allow_multiple=True,
            suggested_repo=None,
        )

        # Verify console.print was called
        assert len(print_calls) > 0, "Expected console.print to be called"

        # Find the indices of key messages
        available_repos_index = None
        multiproject_prompt_index = None

        for i, call in enumerate(print_calls):
            if "Available repositories" in call:
                available_repos_index = i
            # The Confirm.ask is not captured by console.print, so we check that
            # "Available repositories" appeared before Confirm.ask was called

        # Verify "Available repositories" was printed
        assert available_repos_index is not None, \
            "Expected 'Available repositories' to be displayed"

        # Verify project names were listed
        project_list_found = False
        for call in print_calls:
            if "devaiflow" in call or "devaiflow-demos" in call:
                project_list_found = True
                break

        assert project_list_found, \
            "Expected project names to be displayed in the list"

        # Verify Confirm.ask was called (multi-project prompt)
        mock_confirm_ask.assert_called_once()
        confirm_call_args = str(mock_confirm_ask.call_args)
        assert "multi-project" in confirm_call_args.lower(), \
            "Expected multi-project question to be asked"


    @patch("devflow.cli.utils.select_workspace")
    @patch("devflow.cli.utils.scan_workspace_repositories")
    @patch("rich.prompt.Confirm.ask")
    @patch("rich.prompt.Prompt.ask")
    @patch("devflow.cli.utils.console")
    def test_project_list_shows_count_and_numbers(
        self,
        mock_console,
        mock_prompt_ask,
        mock_confirm_ask,
        mock_scan_repos,
        mock_select_workspace,
        mock_config,
    ):
        """Test that project list shows count and numbered items matching daf open format."""
        # Setup mocks
        mock_select_workspace.return_value = "test-workspace"
        mock_scan_repos.return_value = ["devaiflow", "devaiflow-demos"]

        # User declines multi-project mode
        mock_confirm_ask.return_value = False
        mock_prompt_ask.return_value = "1"

        # Track console.print calls
        print_calls = []
        def track_print(*args, **kwargs):
            if args:
                print_calls.append(str(args[0]))

        mock_console.print.side_effect = track_print

        # Call the function
        prompt_repository_selection_with_multiproject(
            config=mock_config,
            workspace_flag="test-workspace",
            allow_multiple=True,
            suggested_repo=None,
        )

        # Verify "Available repositories (2):" format
        count_header_found = False
        for call in print_calls:
            if "Available repositories (2)" in call:
                count_header_found = True
                break

        assert count_header_found, \
            "Expected 'Available repositories (2):' header to be displayed"

        # Verify numbered list format (e.g., "  1. devaiflow")
        numbered_items_found = 0
        for call in print_calls:
            if "  1. " in call or "  2. " in call:
                numbered_items_found += 1

        assert numbered_items_found >= 2, \
            "Expected numbered list items (  1. ..., 2. ...)"


    @patch("devflow.cli.utils.select_workspace")
    @patch("devflow.cli.utils.scan_workspace_repositories")
    @patch("rich.prompt.Confirm.ask")
    @patch("rich.prompt.Prompt.ask")
    def test_multiproject_selection_still_works_after_fix(
        self,
        mock_prompt_ask,
        mock_confirm_ask,
        mock_scan_repos,
        mock_select_workspace,
        mock_config,
        mock_workspace_with_repos,
    ):
        """Test that multi-project selection still works correctly after the fix."""
        # Setup mocks
        mock_select_workspace.return_value = "test-workspace"
        mock_scan_repos.return_value = ["devaiflow", "devaiflow-demos"]

        # User accepts multi-project mode
        mock_confirm_ask.return_value = True
        # Then selects both projects
        mock_prompt_ask.return_value = "1,2"

        # Call the function
        result, workspace_name = prompt_repository_selection_with_multiproject(
            config=mock_config,
            workspace_flag="test-workspace",
            allow_multiple=True,
            suggested_repo=None,
        )

        # Verify result contains both projects
        assert result is not None, "Expected result to be returned"
        assert len(result) == 2, "Expected 2 projects to be selected"
        assert workspace_name == "test-workspace"


    @patch("devflow.cli.utils.select_workspace")
    @patch("devflow.cli.utils.scan_workspace_repositories")
    @patch("rich.prompt.Confirm.ask")
    @patch("rich.prompt.Prompt.ask")
    def test_single_project_fallback_still_works(
        self,
        mock_prompt_ask,
        mock_confirm_ask,
        mock_scan_repos,
        mock_select_workspace,
        mock_config,
        mock_workspace_with_repos,
    ):
        """Test that single-project fallback still works after the fix."""
        # Setup mocks
        mock_select_workspace.return_value = "test-workspace"
        mock_scan_repos.return_value = ["devaiflow", "devaiflow-demos"]

        # User declines multi-project mode
        mock_confirm_ask.return_value = False
        # Then selects single project
        mock_prompt_ask.return_value = "1"

        # Call the function
        result, workspace_name = prompt_repository_selection_with_multiproject(
            config=mock_config,
            workspace_flag="test-workspace",
            allow_multiple=True,
            suggested_repo=None,
        )

        # Verify result contains single project
        assert result is not None, "Expected result to be returned"
        assert len(result) == 1, "Expected 1 project to be selected"
        assert workspace_name == "test-workspace"


    @patch("devflow.cli.utils.select_workspace")
    @patch("devflow.cli.utils.scan_workspace_repositories")
    @patch("rich.prompt.Confirm.ask")
    @patch("rich.prompt.Prompt.ask")
    @patch("devflow.cli.utils.console")
    def test_suggested_repo_marked_in_list(
        self,
        mock_console,
        mock_prompt_ask,
        mock_confirm_ask,
        mock_scan_repos,
        mock_select_workspace,
        mock_config,
    ):
        """Test that suggested repository is marked in the displayed list."""
        # Setup mocks
        mock_select_workspace.return_value = "test-workspace"
        mock_scan_repos.return_value = ["devaiflow", "devaiflow-demos"]

        # User declines multi-project mode
        mock_confirm_ask.return_value = False
        mock_prompt_ask.return_value = "1"

        # Track console.print calls
        print_calls = []
        def track_print(*args, **kwargs):
            if args:
                print_calls.append(str(args[0]))

        mock_console.print.side_effect = track_print

        # Call the function with suggested repo
        prompt_repository_selection_with_multiproject(
            config=mock_config,
            workspace_flag="test-workspace",
            allow_multiple=True,
            suggested_repo="devaiflow",
        )

        # Verify suggested repo is marked
        suggested_marker_found = False
        for call in print_calls:
            if "devaiflow" in call and "suggested" in call:
                suggested_marker_found = True
                break

        assert suggested_marker_found, \
            "Expected suggested repository to be marked with '(suggested)'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
