"""Tests for branch conflict resolution in _handle_branch_creation."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from devflow.cli.commands.new_command import (
    _handle_branch_conflict,
    _handle_branch_creation,
    _prompt_custom_branch_name,
)
from devflow.git.utils import GitUtils


def test_handle_branch_conflict_add_suffix(tmp_path):
    """Test branch conflict resolution by adding suffix."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create the conflicting branch
    subprocess.run(["git", "checkout", "-b", "aap-12345-fix-bug"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user choosing option 1 (add suffix) with "v2"
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt:
        mock_prompt.side_effect = ["1", "v2"]  # Choice 1, suffix "v2"

        result = _handle_branch_conflict(tmp_path, "aap-12345-fix-bug")

        assert result == "aap-12345-fix-bug-v2"


def test_handle_branch_conflict_use_existing(tmp_path):
    """Test branch conflict resolution by using existing branch."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create the conflicting branch
    subprocess.run(["git", "checkout", "-b", "aap-12345-fix-bug"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user choosing option 2 (use existing)
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt:
        mock_prompt.return_value = "2"

        result = _handle_branch_conflict(tmp_path, "aap-12345-fix-bug")

        assert result == "aap-12345-fix-bug"


def test_handle_branch_conflict_custom_name(tmp_path):
    """Test branch conflict resolution with custom name."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create the conflicting branch
    subprocess.run(["git", "checkout", "-b", "aap-12345-fix-bug"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user choosing option 3 (custom name)
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt:
        mock_prompt.side_effect = ["3", "my-custom-branch"]  # Choice 3, custom name

        result = _handle_branch_conflict(tmp_path, "aap-12345-fix-bug")

        assert result == "my-custom-branch"


def test_handle_branch_conflict_skip(tmp_path):
    """Test branch conflict resolution by skipping."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create the conflicting branch
    subprocess.run(["git", "checkout", "-b", "aap-12345-fix-bug"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user choosing option 4 (skip)
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt:
        mock_prompt.return_value = "4"

        result = _handle_branch_conflict(tmp_path, "aap-12345-fix-bug")

        assert result is None


def test_handle_branch_conflict_suffix_also_exists(tmp_path):
    """Test branch conflict when suffix branch also exists, falls back to custom name."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create both conflicting branches
    subprocess.run(["git", "checkout", "-b", "aap-12345-fix-bug"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "aap-12345-fix-bug-v2"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user choosing option 1 (add suffix) with "v2", then provide custom name
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt:
        mock_prompt.side_effect = ["1", "v2", "final-attempt"]  # Choice 1, suffix "v2", then custom name

        result = _handle_branch_conflict(tmp_path, "aap-12345-fix-bug")

        assert result == "final-attempt"


def test_prompt_custom_branch_name_valid(tmp_path):
    """Test custom branch name prompt with valid name."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)

    # Mock user providing valid custom name
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt:
        mock_prompt.return_value = "my-new-branch"

        result = _prompt_custom_branch_name(tmp_path, "original-branch")

        assert result == "my-new-branch"


def test_prompt_custom_branch_name_exists_retry(tmp_path):
    """Test custom branch name prompt when name exists, user retries."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create a branch that will conflict
    subprocess.run(["git", "checkout", "-b", "existing-branch"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user providing existing name first, then choosing to retry with valid name
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm:
        mock_prompt.side_effect = ["existing-branch", "new-valid-branch"]
        mock_confirm.return_value = True  # Retry

        result = _prompt_custom_branch_name(tmp_path, "original-branch")

        assert result == "new-valid-branch"


def test_prompt_custom_branch_name_exists_cancel(tmp_path):
    """Test custom branch name prompt when name exists, user cancels."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create a branch that will conflict
    subprocess.run(["git", "checkout", "-b", "existing-branch"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user providing existing name, then choosing not to retry
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch("devflow.cli.commands.new_command.Confirm.ask") as mock_confirm:
        mock_prompt.return_value = "existing-branch"
        mock_confirm.return_value = False  # Don't retry

        result = _prompt_custom_branch_name(tmp_path, "original-branch")

        assert result is None


def test_prompt_custom_branch_name_empty(tmp_path):
    """Test custom branch name prompt with empty name, then valid."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)

    # Mock user providing empty name first, then valid name
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt:
        mock_prompt.side_effect = ["", "valid-branch"]

        result = _prompt_custom_branch_name(tmp_path, "original-branch")

        assert result == "valid-branch"


def test_handle_branch_creation_detects_conflict(tmp_path):
    """Test that _handle_branch_creation detects and handles branch conflicts."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create a branch that will conflict with the suggested name
    subprocess.run(["git", "checkout", "-b", "aap-12345-test-feature"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user choosing to use existing branch
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test-feature'), \
         patch.object(GitUtils, 'checkout_branch', return_value=True):
        mock_prompt.return_value = "2"  # Use existing branch

        result = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=True
        )

        # Should return the existing branch name
        assert result == "aap-12345-test-feature"


def test_handle_branch_creation_creates_new_with_suffix(tmp_path):
    """Test that _handle_branch_creation creates new branch with suffix on conflict."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create a branch that will conflict
    subprocess.run(["git", "checkout", "-b", "aap-12345-test-feature"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user choosing to add suffix
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test-feature'), \
         patch.object(GitUtils, 'fetch_origin', return_value=True), \
         patch.object(GitUtils, 'get_default_branch', return_value='main'), \
         patch.object(GitUtils, 'checkout_branch', return_value=True), \
         patch.object(GitUtils, 'pull_current_branch', return_value=True), \
         patch.object(GitUtils, 'create_branch', return_value=True):
        mock_prompt.side_effect = ["1", "retry"]  # Add suffix, use "retry"

        result = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=True
        )

        # Should create new branch with suffix
        assert result == "aap-12345-test-feature-retry"


def test_handle_branch_creation_skip_on_conflict(tmp_path):
    """Test that _handle_branch_creation allows skipping on conflict."""
    # Initialize a git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create a branch that will conflict
    subprocess.run(["git", "checkout", "-b", "aap-12345-test-feature"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=tmp_path, capture_output=True)

    # Mock user choosing to skip
    with patch("devflow.cli.commands.new_command.Prompt.ask") as mock_prompt, \
         patch.object(GitUtils, 'generate_branch_name', return_value='aap-12345-test-feature'):
        mock_prompt.return_value = "4"  # Skip

        result = _handle_branch_creation(
            str(tmp_path),
            "PROJ-12345",
            "test feature",
            auto_from_default=True
        )

        # Should return None (skip)
        assert result is None
