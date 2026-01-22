"""Tests for session-in-progress check (PROJ-60925).

This module tests that daf new and daf open commands check for active sessions
BEFORE performing any git operations (branch creation or checkout).
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.cli.commands.new_command import create_new_session
from devflow.cli.commands.open_command import open_session
from devflow.config.loader import ConfigLoader
from devflow.config.models import Session
from devflow.session.manager import SessionManager


class GitRepoInfo:
    """Wrapper for git repo path with metadata."""
    def __init__(self, path, default_branch):
        self.path = path
        self.default_branch = default_branch

    def __str__(self):
        return str(self.path)

    def __fspath__(self):
        return str(self.path)


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock git repository."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True, capture_output=True)

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True, capture_output=True)

    # Get the actual default branch name (could be master or main depending on git version)
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    )
    default_branch = result.stdout.strip()

    return GitRepoInfo(repo_path, default_branch)


def test_daf_new_checks_active_session_before_branch_creation(temp_daf_home, mock_git_repo):
    """Test that daf new checks for active sessions BEFORE creating branch.

    Scenario from PROJ-60925:
    1. Session A is active in the repository
    2. User runs daf new for Session B
    3. daf new should exit BEFORE creating any branch
    4. Repository should remain on original branch
    """
    # Get the default branch (could be master or main depending on git version)
    original_branch = mock_git_repo.default_branch

    # Setup: Create and activate session A
    manager = SessionManager()
    session_a = manager.create_session(
        name="session-a",
        goal="Feature A",
        working_directory="test-repo",
        project_path=str(mock_git_repo),
        branch=original_branch,
        ai_agent_session_id="uuid-a",
    )
    session_a.status = "in_progress"
    manager.update_session(session_a)

    # Verify we're on the expected branch
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=mock_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    assert result.stdout.strip() == original_branch

    # Mock should_launch_claude_code to prevent Claude Code from launching
    with patch("devflow.cli.commands.new_command.should_launch_claude_code", return_value=False):
        # Attempt to create session B (should fail due to active session A)
        create_new_session(
            name="session-b",
            goal="Feature B",
            path=str(mock_git_repo),
            branch=None,  # Let it auto-create branch
        )

    # Verify: Repository should still be on original branch (no branch created)
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=mock_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    current_branch = result.stdout.strip()
    assert current_branch == original_branch, "Repository branch should not have changed"

    # Verify: No new branch was created
    result = subprocess.run(
        ["git", "branch", "--list"],
        cwd=mock_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    branches = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n")]
    assert "session-b" not in branches, "Session B branch should not have been created"

    # Verify: Session B was not created
    session_b = manager.get_session("session-b")
    assert session_b is None, "Session B should not have been created"


def test_daf_open_checks_active_session_before_branch_checkout(temp_daf_home, mock_git_repo, monkeypatch):
    """Test that daf open checks for active sessions BEFORE checking out branch.

    Scenario from PROJ-60925:
    1. Session A is active on branch feature-a
    2. User runs daf open session-b (which has branch feature-b)
    3. daf open should exit BEFORE checking out feature-b
    4. Repository should remain on feature-a
    """
    # Setup: Create session A and B
    manager = SessionManager()

    # Create and activate session A on feature-a branch
    subprocess.run(["git", "checkout", "-b", "feature-a"], cwd=mock_git_repo, check=True, capture_output=True)
    session_a = manager.create_session(
        name="session-a",
        goal="Feature A",
        working_directory="test-repo",
        project_path=str(mock_git_repo),
        branch="feature-a",
        ai_agent_session_id="uuid-a",
    )
    session_a.status = "in_progress"
    manager.update_session(session_a)

    # Create session B on feature-b branch (but not active)
    subprocess.run(["git", "checkout", "-b", "feature-b"], cwd=mock_git_repo, check=True, capture_output=True)
    session_b = manager.create_session(
        name="session-b",
        goal="Feature B",
        working_directory="test-repo",
        project_path=str(mock_git_repo),
        branch="feature-b",
        ai_agent_session_id="uuid-b",
    )
    session_b.status = "paused"
    manager.update_session(session_b)

    # Switch back to feature-a (simulating session A being active)
    subprocess.run(["git", "checkout", "feature-a"], cwd=mock_git_repo, check=True, capture_output=True)

    # Verify we're on feature-a
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=mock_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    assert result.stdout.strip() == "feature-a"

    # Change to the repository directory to avoid workspace detection issues
    monkeypatch.chdir(mock_git_repo)

    # Mock should_launch_claude_code to prevent Claude Code from launching
    with patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False):
        # Attempt to open session B (should fail due to active session A)
        open_session("session-b")

    # Verify: Repository should still be on feature-a (not switched to feature-b)
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=mock_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    current_branch = result.stdout.strip()
    assert current_branch == "feature-a", "Repository should remain on session A's branch"

    # Verify: Session A should still be in_progress
    session_a_check = manager.get_session("session-a")
    assert session_a_check.status == "in_progress"

    # Verify: Session B should still be paused (not activated)
    session_b_check = manager.get_session("session-b")
    assert session_b_check.status == "paused"


def test_check_concurrent_session_util_function(temp_daf_home, mock_git_repo):
    """Test the check_concurrent_session utility function directly."""
    from devflow.cli.utils import check_concurrent_session

    # Setup: Create and activate session A
    manager = SessionManager()
    session_a = manager.create_session(
        name="session-a",
        goal="Feature A",
        working_directory="test-repo",
        project_path=str(mock_git_repo),
        branch="main",
        ai_agent_session_id="uuid-a",
    )
    session_a.status = "in_progress"
    manager.update_session(session_a)

    # Test: Check should fail when trying to create session B in same project
    result = check_concurrent_session(manager, str(mock_git_repo), "session-b", action="create")
    assert result is False, "Should return False when another session is active"

    # Test: Check should succeed when trying to resume session A itself
    result = check_concurrent_session(manager, str(mock_git_repo), "session-a", action="open")
    assert result is True, "Should return True when checking the same session"

    # Test: Complete session A
    session_a.status = "complete"
    manager.update_session(session_a)

    # Test: Check should succeed when no active sessions exist
    result = check_concurrent_session(manager, str(mock_git_repo), "session-b", action="create")
    assert result is True, "Should return True when no active sessions exist"


def test_daf_new_allows_same_session_in_different_project(temp_daf_home, mock_git_repo, tmp_path):
    """Test that daf new allows adding conversation to session in different project (multi-conversation)."""
    # Create second repository
    repo2_path = tmp_path / "test-repo-2"
    repo2_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo2_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo2_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo2_path, check=True, capture_output=True)
    (repo2_path / "README.md").write_text("# Test Repo 2")
    subprocess.run(["git", "add", "."], cwd=repo2_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo2_path, check=True, capture_output=True)

    # Setup: Create and activate session A in repo 1
    manager = SessionManager()
    session_a1 = manager.create_session(
        name="session-a",
        goal="Feature A in repo 1",
        working_directory="test-repo",
        project_path=str(mock_git_repo),
        branch="main",
        ai_agent_session_id="uuid-a1",
    )
    session_a1.status = "in_progress"
    manager.update_session(session_a1)

    # Mock prompts and should_launch_claude_code
    with patch("devflow.cli.commands.new_command.should_launch_claude_code", return_value=False), \
         patch("devflow.cli.commands.new_command.Confirm.ask", return_value=True), \
         patch("devflow.cli.commands.new_command.Prompt.ask", return_value="2"):
        # Attempt to create session A in repo 2 (should succeed - adds conversation to existing session)
        create_new_session(
            name="session-a",
            goal="Feature A in repo 2",
            path=str(repo2_path),
            branch=None,
        )

    # Verify: New behavior adds conversation to existing session instead of creating new session
    manager_reload = SessionManager()
    sessions = manager_reload.index.get_sessions("session-a")
    assert len(sessions) == 1, "Should have 1 session (multi-conversation architecture)"

    # Verify the session has 2 conversations
    session = sessions[0]
    assert len(session.conversations) == 2, "Session should have 2 conversations"
    assert "test-repo" in session.conversations
    assert "test-repo-2" in session.conversations


def test_daf_open_allows_resuming_same_session(temp_daf_home, mock_git_repo, monkeypatch):
    """Test that daf open allows resuming the currently active session."""
    # Get the default branch (could be master or main depending on git version)
    default_branch = mock_git_repo.default_branch

    # Setup: Create and activate session A
    manager = SessionManager()
    session_a = manager.create_session(
        name="session-a",
        goal="Feature A",
        working_directory="test-repo",
        project_path=str(mock_git_repo),
        branch=default_branch,
        ai_agent_session_id="uuid-a",
    )
    session_a.status = "in_progress"
    manager.update_session(session_a)

    # Change to the repository directory to avoid workspace detection issues
    monkeypatch.chdir(mock_git_repo)

    # Mock should_launch_claude_code and any branch creation prompts
    with patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False), \
         patch("devflow.cli.commands.open_command.Confirm.ask", return_value=True):
        # Attempt to open session A itself (should succeed - same session)
        open_session("session-a")

    # Verify: Session A should still be in_progress
    session_a_check = manager.get_session("session-a")
    assert session_a_check.status == "in_progress"


def test_daf_open_checks_active_session_before_branch_creation_first_launch(temp_daf_home, mock_git_repo, monkeypatch):
    """Test that daf open checks for active sessions BEFORE creating branch on first launch.

    This test specifically addresses PROJ-61152 where daf open was performing git branch
    creation BEFORE checking for concurrent sessions on first launch (synced sessions).

    Scenario:
    1. Session A is active in the repository
    2. Session B exists but has no branch yet (first launch scenario)
    3. User runs daf open session-b
    4. daf open should exit BEFORE creating any branch for session B
    5. Repository should remain on session A's branch
    6. No new branch should be created
    """
    # Get the default branch (could be master or main depending on git version)
    default_branch = mock_git_repo.default_branch

    # Setup: Create and activate session A on main/master branch
    manager = SessionManager()
    session_a = manager.create_session(
        name="session-a",
        goal="Feature A",
        working_directory="test-repo",
        project_path=str(mock_git_repo),
        branch=default_branch,
        ai_agent_session_id="uuid-a",
    )
    session_a.status = "in_progress"
    manager.update_session(session_a)

    # Create session B with default branch (simulating synced session that hasn't been opened yet)
    # This will have branch="main" by default, but since it's a first-launch scenario
    # without an active Claude session, it would normally trigger branch creation prompts
    session_b = manager.create_session(
        name="session-b",
        goal="Feature B",
        working_directory="test-repo",
        project_path=str(mock_git_repo),
        branch=None,  # Will default to "main"
        ai_agent_session_id="uuid-b",
    )
    session_b.status = "paused"
    manager.update_session(session_b)

    # Now clear the branch to simulate a session that needs branch creation
    # This mimics what happens when sessions are synced from JIRA
    session_b.active_conversation.branch = ""
    manager.update_session(session_b)

    # Verify we're on the default branch
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=mock_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    assert result.stdout.strip() == default_branch

    # List all branches before opening session B
    result = subprocess.run(
        ["git", "branch", "--list"],
        cwd=mock_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    branches_before = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n")]

    # Change to the repository directory to avoid workspace detection issues
    monkeypatch.chdir(mock_git_repo)

    # Mock should_launch_claude_code to prevent Claude Code from launching
    with patch("devflow.cli.commands.open_command.should_launch_claude_code", return_value=False):
        # Attempt to open session B (should fail due to active session A)
        # This should exit BEFORE creating any branch
        open_session("session-b")

    # Verify: Repository should still be on default branch (not switched)
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=mock_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    current_branch = result.stdout.strip()
    assert current_branch == default_branch, f"Repository should remain on {default_branch}, but is on {current_branch}"

    # Verify: No new branch was created for session B
    result = subprocess.run(
        ["git", "branch", "--list"],
        cwd=mock_git_repo,
        capture_output=True,
        text=True,
        check=True
    )
    branches_after = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n")]
    assert branches_before == branches_after, "No new branches should have been created"

    # Verify: Session B should not have a branch set
    # Reload manager to get fresh data
    manager_reload = SessionManager()
    session_b_check = manager_reload.get_session("session-b")
    session_b_active = session_b_check.active_conversation
    assert session_b_active is None or session_b_active.branch == "", "Session B should not have a branch assigned"

    # Verify: Session A should still be in_progress
    session_a_check = manager.get_session("session-a")
    assert session_a_check.status == "in_progress"

    # Verify: Session B should still be paused (not activated)
    assert session_b_check.status == "paused"
