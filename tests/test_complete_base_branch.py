"""Tests for issue #150: Use stored base_branch in daf complete.

This test file verifies that the complete command uses the stored base_branch
from the session's active conversation instead of detecting the default branch.
"""

from pathlib import Path
from unittest.mock import Mock, patch
import subprocess

import pytest

from devflow.cli.commands.complete_command import complete_session, _get_base_branch
from devflow.config.loader import ConfigLoader
from devflow.config.models import ConversationContext
from devflow.session.manager import SessionManager
from devflow.git.utils import GitUtils


def test_get_base_branch_uses_stored_value():
    """Test that _get_base_branch returns the stored base_branch from active_conv."""
    # Create mock active conversation with base_branch set
    active_conv = Mock()
    active_conv.base_branch = "develop"

    working_dir = Path("/test")

    # Should return stored base_branch without calling GitUtils
    result = _get_base_branch(active_conv, working_dir)

    assert result == "develop"


def test_get_base_branch_fallback_to_detection():
    """Test that _get_base_branch falls back to GitUtils.get_default_branch when base_branch is None."""
    # Create mock active conversation with no base_branch
    active_conv = Mock()
    active_conv.base_branch = None

    working_dir = Path("/test")

    with patch.object(GitUtils, 'get_default_branch', return_value='main') as mock_get_default:
        result = _get_base_branch(active_conv, working_dir)

        # Should call GitUtils.get_default_branch as fallback
        mock_get_default.assert_called_once_with(working_dir)
        assert result == "main"


def test_get_base_branch_fallback_when_detection_returns_none():
    """Test that _get_base_branch returns 'main' when detection returns None."""
    active_conv = Mock()
    active_conv.base_branch = None

    working_dir = Path("/test")

    with patch.object(GitUtils, 'get_default_branch', return_value=None):
        result = _get_base_branch(active_conv, working_dir)

        # Should return "main" as last resort fallback
        assert result == "main"


def test_get_base_branch_no_active_conv():
    """Test that _get_base_branch handles None active_conv gracefully."""
    active_conv = None
    working_dir = Path("/test")

    with patch.object(GitUtils, 'get_default_branch', return_value='main') as mock_get_default:
        result = _get_base_branch(active_conv, working_dir)

        # Should call GitUtils.get_default_branch as fallback
        mock_get_default.assert_called_once_with(working_dir)
        assert result == "main"


def test_complete_uses_stored_base_branch_from_develop(temp_daf_home, monkeypatch, tmp_path, capsys):
    """Test that complete command uses stored base_branch (develop) instead of detecting default branch (main).

    This tests issue #150: When a branch is created from 'develop', the complete command
    should use 'develop' as the base branch for git diffs and PR generation, not 'main'.
    """
    # Initialize a git repo with main and develop branches
    git_repo = tmp_path / "test-repo"
    git_repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=git_repo, capture_output=True, check=True)

    # Create initial commit on main
    (git_repo / "main.txt").write_text("main content")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Main commit"], cwd=git_repo, capture_output=True, check=True)

    # Create develop branch with its own commit
    subprocess.run(["git", "checkout", "-b", "develop"], cwd=git_repo, capture_output=True, check=True)
    (git_repo / "develop.txt").write_text("develop content")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Develop commit"], cwd=git_repo, capture_output=True, check=True)

    # Create feature branch from develop
    subprocess.run(["git", "checkout", "-b", "150-test-feature"], cwd=git_repo, capture_output=True, check=True)
    (git_repo / "feature.txt").write_text("feature content")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Feature commit"], cwd=git_repo, capture_output=True, check=True)

    # Create session with base_branch set to "develop"
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="base-branch-test",
        goal="Test base_branch from develop",
        working_directory="test-repo",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-base-branch",
        branch="150-test-feature",
    )

    # Set base_branch to "develop" (simulating what daf open/new does)
    session.active_conversation.base_branch = "develop"
    # Use update_session to properly save and update the session
    session_manager.update_session(session)

    # Track that git commands were called with correct base_branch
    get_commit_log_calls = []
    get_changed_files_calls = []

    original_get_commit_log = GitUtils.get_commit_log
    original_get_changed_files = GitUtils.get_changed_files

    def mock_get_commit_log(working_dir, base_branch=None):
        get_commit_log_calls.append((str(working_dir), base_branch))
        return original_get_commit_log(working_dir, base_branch)

    def mock_get_changed_files(working_dir, base_branch=None, current_branch=None):
        get_changed_files_calls.append((str(working_dir), base_branch, current_branch))
        # Return some files to trigger PR creation flow
        if base_branch:
            return ["feature.txt"]
        return []

    # Mock GitUtils methods to track calls
    monkeypatch.setattr(GitUtils, "get_commit_log", mock_get_commit_log)
    monkeypatch.setattr(GitUtils, "get_changed_files", mock_get_changed_files)

    # Mock to avoid actual PR creation
    # Decline PR creation to keep test simple - we only care about get_changed_files being called correctly
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: None)
    monkeypatch.setattr(GitUtils, "has_uncommitted_changes", lambda path: False)
    monkeypatch.setattr(GitUtils, "has_unpushed_commits", lambda path, branch: False)

    # Complete the session
    complete_session("base-branch-test")

    # Verify that get_changed_files was called with "develop" as base_branch, not "main"
    # This is the key fix - when checking for changes, use the stored base_branch
    assert any(base == "develop" for _, base, _ in get_changed_files_calls), \
        f"Expected get_changed_files to be called with base_branch='develop', but got calls: {get_changed_files_calls}"

    # Verify NO calls used "main" as base_branch
    assert not any(base == "main" for _, base, _ in get_changed_files_calls), \
        f"get_changed_files should NOT use 'main' as base_branch, but got calls: {get_changed_files_calls}"


def test_complete_uses_stored_base_branch_from_main(temp_daf_home, monkeypatch, tmp_path, capsys):
    """Test that complete command uses stored base_branch (main) when branch was created from main.

    This verifies the fix works correctly for the normal case (main branch).
    """
    # Initialize a git repo
    git_repo = tmp_path / "test-repo-main"
    git_repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=git_repo, capture_output=True, check=True)

    # Create initial commit on main
    (git_repo / "main.txt").write_text("main content")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Main commit"], cwd=git_repo, capture_output=True, check=True)

    # Create feature branch from main
    subprocess.run(["git", "checkout", "-b", "150-from-main"], cwd=git_repo, capture_output=True, check=True)
    (git_repo / "feature.txt").write_text("feature content")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Feature commit"], cwd=git_repo, capture_output=True, check=True)

    # Create session with base_branch set to "main"
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="base-branch-main-test",
        goal="Test base_branch from main",
        working_directory="test-repo-main",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-base-main",
        branch="150-from-main",
    )

    # Set base_branch to "main"
    session.active_conversation.base_branch = "main"
    # Use update_session to properly save and update the session
    session_manager.update_session(session)

    # Track git command calls
    get_commit_log_calls = []
    get_changed_files_calls = []

    original_get_commit_log = GitUtils.get_commit_log

    def mock_get_commit_log(working_dir, base_branch=None):
        get_commit_log_calls.append((str(working_dir), base_branch))
        return original_get_commit_log(working_dir, base_branch)

    def mock_get_changed_files(working_dir, base_branch=None, current_branch=None):
        get_changed_files_calls.append((str(working_dir), base_branch, current_branch))
        # Return some files to trigger checking
        if base_branch:
            return ["feature.txt"]
        return []

    monkeypatch.setattr(GitUtils, "get_commit_log", mock_get_commit_log)
    monkeypatch.setattr(GitUtils, "get_changed_files", mock_get_changed_files)

    # Mock to avoid actual PR creation
    # Decline PR creation to keep test simple - we only care about get_changed_files being called correctly
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: None)
    monkeypatch.setattr(GitUtils, "has_uncommitted_changes", lambda path: False)
    monkeypatch.setattr(GitUtils, "has_unpushed_commits", lambda path, branch: False)

    # Complete the session
    complete_session("base-branch-main-test")

    # Verify that get_changed_files was called with "main" as base_branch
    assert any(base == "main" for _, base, _ in get_changed_files_calls), \
        f"Expected get_changed_files to be called with base_branch='main', but got calls: {get_changed_files_calls}"


def test_complete_fallback_to_detected_default_for_old_sessions(temp_daf_home, monkeypatch, tmp_path, capsys):
    """Test that complete command falls back to detecting default branch for old sessions without base_branch.

    This ensures backward compatibility with sessions created before the base_branch field existed.
    """
    # Initialize a git repo
    git_repo = tmp_path / "test-repo-old"
    git_repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=git_repo, capture_output=True, check=True)

    # Create initial commit
    (git_repo / "main.txt").write_text("main content")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Main commit"], cwd=git_repo, capture_output=True, check=True)

    # Create feature branch
    subprocess.run(["git", "checkout", "-b", "150-old-session"], cwd=git_repo, capture_output=True, check=True)
    (git_repo / "feature.txt").write_text("feature content")
    subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Feature commit"], cwd=git_repo, capture_output=True, check=True)

    # Create session WITHOUT base_branch (simulating old session)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="old-session-test",
        goal="Test fallback for old session",
        working_directory="test-repo-old",
        project_path=str(git_repo),
        ai_agent_session_id="uuid-old",
        branch="150-old-session",
    )

    # Explicitly set base_branch to None to simulate old session
    session.active_conversation.base_branch = None
    # Use update_session to properly save and update the session
    session_manager.update_session(session)

    # Track that get_default_branch was called as fallback
    get_default_branch_called = []

    original_get_default_branch = GitUtils.get_default_branch

    def mock_get_default_branch(working_dir):
        get_default_branch_called.append(str(working_dir))
        return original_get_default_branch(working_dir)

    monkeypatch.setattr(GitUtils, "get_default_branch", mock_get_default_branch)

    # Mock other methods
    monkeypatch.setattr("devflow.cli.commands.complete_command.Confirm.ask", lambda *args, **kwargs: False)
    monkeypatch.setattr("devflow.cli.commands.complete_command._get_pr_for_branch", lambda w, b: None)
    monkeypatch.setattr(GitUtils, "has_uncommitted_changes", lambda path: False)
    monkeypatch.setattr(GitUtils, "has_unpushed_commits", lambda path, branch: False)
    monkeypatch.setattr(GitUtils, "get_commit_log", lambda *args, **kwargs: "")
    # Return some files to trigger PR creation flow
    monkeypatch.setattr(GitUtils, "get_changed_files", lambda *args, **kwargs: ["feature.txt"])
    monkeypatch.setattr("devflow.cli.commands.complete_command._create_pr_mr", lambda *args, **kwargs: None)

    # Complete the session
    complete_session("old-session-test")

    # Verify that get_default_branch was called as fallback
    assert len(get_default_branch_called) > 0, \
        "Expected get_default_branch to be called as fallback for old session without base_branch"
