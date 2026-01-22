"""Tests for daf open --path parameter."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.git.utils import GitUtils


def test_open_with_path_selects_conversation(temp_daf_home, temp_workspace, monkeypatch):
    """Test that --path parameter selects the correct conversation."""
    # Unset AI_AGENT_SESSION_ID to avoid @require_outside_claude blocking test
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with multiple conversations
    session = session_manager.create_session(
        name="multi-repo-session",
        goal="Work across multiple repos",
        working_directory="repo1",
        project_path=str(temp_workspace / "repo1"),
        ai_agent_session_id="uuid-repo1",
    )

    # Add second conversation
    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-repo2",
        project_path=str(temp_workspace / "repo2"),
        branch="main",
        workspace=str(temp_workspace),
    )
    session_manager.update_session(session)

    runner = CliRunner()

    # Mock should_launch_claude_code to prevent launching Claude Code
    with patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False):
        # Open with --path pointing to repo2
        result = runner.invoke(cli, ["open", "multi-repo-session", "--path", str(temp_workspace / "repo2")])

    assert result.exit_code == 0
    assert "repo2" in result.output

    # Verify session was updated to use repo2
    # Create a fresh SessionManager to reload from disk (open_session creates its own instance)
    fresh_config_loader = ConfigLoader()
    fresh_session_manager = SessionManager(fresh_config_loader)
    updated_session = fresh_session_manager.get_session("multi-repo-session")
    assert updated_session.working_directory == "repo2"


def test_open_with_path_creates_new_conversation(temp_daf_home, temp_workspace, monkeypatch):
    """Test that --path parameter creates new conversation if needed."""
    # Unset AI_AGENT_SESSION_ID to avoid @require_outside_claude blocking test
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with one conversation
    session = session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="repo1",
        project_path=str(temp_workspace / "repo1"),
        ai_agent_session_id="uuid-repo1",
    )

    # Use repo2 directory (already created in temp_workspace fixture)
    # The fixture already creates repo1, repo2, and repo3
    repo2_path = temp_workspace / "repo2"

    runner = CliRunner()

    # Mock should_launch_claude_code to prevent launching Claude Code
    with patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False):
        # Open with --path pointing to repo2 (doesn't exist in session yet)
        # Input: n to skip creating git branch
        result = runner.invoke(cli, ["open", "test-session", "--path", str(repo2_path)], input="n\n")

    assert result.exit_code == 0
    assert "Creating new conversation" in result.output or "repo2" in result.output

    # Verify new conversation was created
    # Create a fresh SessionManager to reload from disk
    fresh_config_loader = ConfigLoader()
    fresh_session_manager = SessionManager(fresh_config_loader)
    updated_session = fresh_session_manager.get_session("test-session")
    assert "repo2" in updated_session.conversations
    assert updated_session.working_directory == "repo2"


def test_open_with_path_handles_repo_name(temp_daf_home, temp_workspace, monkeypatch):
    """Test that --path parameter works with repository name."""
    # Unset AI_AGENT_SESSION_ID to avoid @require_outside_claude blocking test
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with multiple conversations
    session = session_manager.create_session(
        name="multi-repo-session",
        goal="Work across multiple repos",
        working_directory="repo1",
        project_path=str(temp_workspace / "repo1"),
        ai_agent_session_id="uuid-repo1",
    )

    # Add second conversation
    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-repo2",
        project_path=str(temp_workspace / "repo2"),
        branch="main",
        workspace=str(temp_workspace),
    )
    session_manager.update_session(session)

    runner = CliRunner()

    # Mock should_launch_claude_code to prevent launching Claude Code
    with patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False):
        # Open with --path using just repo name (not full path)
        result = runner.invoke(cli, ["open", "multi-repo-session", "--path", "repo2"])

    assert result.exit_code == 0
    assert "repo2" in result.output

    # Verify session was updated to use repo2
    # Create a fresh SessionManager to reload from disk
    fresh_config_loader = ConfigLoader()
    fresh_session_manager = SessionManager(fresh_config_loader)
    updated_session = fresh_session_manager.get_session("multi-repo-session")
    assert updated_session.working_directory == "repo2"


def test_open_with_invalid_path(temp_daf_home, temp_workspace, monkeypatch):
    """Test that --path parameter handles invalid paths gracefully."""
    # Unset AI_AGENT_SESSION_ID to avoid @require_outside_claude blocking test
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="repo1",
        project_path=str(temp_workspace / "repo1"),
        ai_agent_session_id="uuid-repo1",
    )

    runner = CliRunner()

    # Try to open with invalid path
    result = runner.invoke(cli, ["open", "test-session", "--path", "/nonexistent/path"])

    assert result.exit_code == 0
    assert "Could not detect repository" in result.output or "not a git repository" in result.output


def test_open_with_path_absolute_path(temp_daf_home, temp_workspace, monkeypatch):
    """Test that --path parameter works with absolute paths."""
    # Unset AI_AGENT_SESSION_ID to avoid @require_outside_claude blocking test
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with one conversation
    session = session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="repo1",
        project_path=str(temp_workspace / "repo1"),
        ai_agent_session_id="uuid-repo1",
    )

    # Add second conversation
    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-repo2",
        project_path=str(temp_workspace / "repo2"),
        branch="main",
        workspace=str(temp_workspace),
    )
    session_manager.update_session(session)

    runner = CliRunner()

    # Mock should_launch_claude_code to prevent launching Claude Code
    with patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False):
        # Open with --path using absolute path
        result = runner.invoke(cli, ["open", "test-session", "--path", str(temp_workspace / "repo2")])

    assert result.exit_code == 0

    # Verify session was updated to use repo2
    # Create a fresh SessionManager to reload from disk
    fresh_config_loader = ConfigLoader()
    fresh_session_manager = SessionManager(fresh_config_loader)
    updated_session = fresh_session_manager.get_session("test-session")
    assert updated_session.working_directory == "repo2"


def test_open_without_path_falls_back_to_current_behavior(temp_daf_home, temp_workspace, monkeypatch):
    """Test that omitting --path parameter uses existing behavior."""
    # Unset AI_AGENT_SESSION_ID to avoid @require_outside_claude blocking test
    monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session with multiple conversations
    session = session_manager.create_session(
        name="multi-repo-session",
        goal="Work across multiple repos",
        working_directory="repo1",
        project_path=str(temp_workspace / "repo1"),
        ai_agent_session_id="uuid-repo1",
    )

    # Add second conversation
    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-repo2",
        project_path=str(temp_workspace / "repo2"),
        branch="main",
        workspace=str(temp_workspace),
    )
    session_manager.update_session(session)

    runner = CliRunner()

    # Mock should_launch_claude_code to prevent launching Claude Code
    with patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=False):
        # Open without --path - should prompt for conversation selection
        # Input: 1 to select first conversation
        result = runner.invoke(cli, ["open", "multi-repo-session"], input="1\n")

    assert result.exit_code == 0
    # Should show conversation selection prompt
    assert "conversation" in result.output.lower() or "Found 2 conversation" in result.output


@pytest.fixture
def temp_workspace(temp_daf_home):
    """Create a temporary workspace with git repositories."""
    import subprocess

    config_loader = ConfigLoader()

    # Create workspace directory
    workspace_dir = Path(tempfile.mkdtemp(prefix="test-workspace-"))

    # Create repo directories with git init and create main branch
    for repo_name in ["repo1", "repo2", "repo3"]:
        repo_path = workspace_dir / repo_name
        repo_path.mkdir()
        # Initialize git repository using subprocess
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
        # Create an initial commit so 'main' branch exists
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True, check=True)
        (repo_path / "README.md").write_text("# Test Repo")
        subprocess.run(["git", "add", "README.md"], cwd=repo_path, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True, check=True)
        # Rename master to main if needed (git init may create master on older versions)
        subprocess.run(["git", "branch", "-M", "main"], cwd=repo_path, capture_output=True)

    # Update config with workspace path
    # First ensure we have a valid config by creating default if needed
    try:
        config = config_loader.load_config()
        if config is None:
            config = config_loader.create_default_config()
    except Exception:
        config = config_loader.create_default_config()

    # Ensure repos object exists
    if not config.repos:
        from devflow.config.models import RepoConfig
        config.repos = RepoConfig(workspace=str(workspace_dir), keywords={})
    else:
        config.repos.workspace = str(workspace_dir)

    config_loader.save_config(config)

    yield workspace_dir

    # Cleanup
    shutil.rmtree(workspace_dir, ignore_errors=True)
