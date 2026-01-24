"""Test that daf open prompts for conversation selection when multiple conversations exist (PROJ-61031)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.cli.commands.open_command import open_session
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_open_always_prompts_for_conversation_selection_when_multiple_exist(tmp_path, temp_daf_home):
    """Test that daf open ALWAYS prompts for conversation selection when multiple conversations exist.

    This is the fix for PROJ-61031 - previously daf open would auto-select a conversation
    if the current directory matched one of the conversations. Now it should always prompt.
    """
    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create workspace with two repos
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo1_dir = workspace / "backend-api"
    repo1_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo1_dir, capture_output=True)

    repo2_dir = workspace / "frontend-app"
    repo2_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo2_dir, capture_output=True)

    # Configure workspace
    config = config_loader.load_config()
    if config:
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(workspace))

        ]
        config_loader.save_config(config)

    # Create session with first conversation
    session = manager.create_session(
        name="test-session",
        goal="Multi-repo feature",
        working_directory="backend-api",
        project_path=str(repo1_dir),
        branch="feature-branch",
        ai_agent_session_id="uuid-backend",
    )

    # Add second conversation
    session.add_conversation(
        working_dir="frontend-app",
        ai_agent_session_id="uuid-frontend",
        project_path=str(repo2_dir),
        branch="feature-branch",
        workspace=str(workspace),
    )
    manager.update_session(session)

    # Verify we have 2 conversations
    assert len(session.conversations) == 2

    # Mock the conversation selection function to verify it's called
    with patch("devflow.cli.commands.open_command._handle_conversation_selection_without_detection") as mock_selection:
        mock_selection.return_value = False  # User cancelled

        # Call open_session - should prompt for conversation selection
        open_session("test-session")

        # Verify that conversation selection was prompted
        mock_selection.assert_called_once()
        call_args = mock_selection.call_args
        assert call_args[0][0].name == "test-session"  # First arg is session
        assert len(call_args[0][0].conversations) == 2  # Session has 2 conversations


def test_open_single_conversation_does_not_prompt(tmp_path, temp_daf_home):
    """Test that daf open does NOT prompt when only one conversation exists."""
    from devflow.session.capture import SessionCapture

    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create workspace with one repo
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo_dir = workspace / "backend-api"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True)

    # Configure workspace
    config = config_loader.load_config()
    if config:
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(workspace))

        ]
        config_loader.save_config(config)

    # Create session with 1 conversation
    session = manager.create_session(
        name="test-session-single",
        goal="Single repo work",
        working_directory="backend-api",
        project_path=str(repo_dir),
        branch="feature-branch",
        ai_agent_session_id="uuid-backend",
    )
    manager.update_session(session)

    # Create conversation file so it's not first-time launch
    capture = SessionCapture()
    session_dir = capture.get_session_dir(str(repo_dir))
    session_dir.mkdir(parents=True, exist_ok=True)
    conversation_file = session_dir / f"uuid-backend.jsonl"
    conversation_file.write_text('{"type":"test"}\n')

    # Verify we have 1 conversation
    assert len(session.conversations) == 1

    # Mock current directory to be in a non-repo location
    with patch("devflow.cli.commands.open_command.Path.cwd") as mock_cwd:
        mock_cwd.return_value = tmp_path / "non-repo-dir"

        # Mock the conversation selection function to track if it's called
        with patch("devflow.cli.commands.open_command._handle_conversation_selection_without_detection") as mock_selection:
            # Mock subprocess and should_launch to prevent actual execution
            with patch("devflow.cli.commands.open_command.subprocess.run"):
                with patch("devflow.cli.commands.open_command.should_launch_claude_code") as mock_should_launch:
                    mock_should_launch.return_value = False

                    # Call open_session - should NOT prompt for conversation selection
                    open_session("test-session-single")

                    # Verify that conversation selection was NOT called (only 1 conversation)
                    mock_selection.assert_not_called()


def test_open_no_conversations_does_not_prompt(temp_daf_home):
    """Test that daf open does NOT prompt when no conversations exist yet."""
    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create a session with no conversations (created via daf sync)
    session = manager.create_session(
        name="test-session-no-conv",
        goal="New ticket",
    )
    # Don't add any conversations
    manager.update_session(session)

    # Verify we have 0 conversations
    assert len(session.conversations) == 0

    # Mock the conversation selection function
    with patch("devflow.cli.commands.open_command._handle_conversation_selection_without_detection") as mock_selection:
        with patch("devflow.cli.commands.open_command._prompt_for_working_directory") as mock_prompt_wd:
            mock_prompt_wd.return_value = None  # User cancelled

            # Call open_session - should NOT prompt for conversation selection
            open_session("test-session-no-conv")

            # Verify that conversation selection was NOT called (no conversations exist)
            mock_selection.assert_not_called()


def test_open_multi_conversation_ignores_current_directory_detection(tmp_path, temp_daf_home):
    """Test that multi-conversation sessions ALWAYS prompt, even when current dir matches a conversation.

    This is the key behavior change in PROJ-61031. Previously, if you were in a directory
    that matched one of the conversations, daf open would auto-select it. Now it always prompts.
    """
    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create workspace with two repos
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo1_dir = workspace / "backend-api"
    repo1_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo1_dir, capture_output=True)

    repo2_dir = workspace / "frontend-app"
    repo2_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo2_dir, capture_output=True)

    # Configure workspace
    config = config_loader.load_config()
    if config:
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(workspace))

        ]
        config_loader.save_config(config)

    # Create session with 2 conversations
    session = manager.create_session(
        name="test-session",
        goal="Multi-repo feature",
        working_directory="backend-api",
        project_path=str(repo1_dir),
        branch="feature-branch",
        ai_agent_session_id="uuid-backend",
    )
    session.add_conversation(
        working_dir="frontend-app",
        ai_agent_session_id="uuid-frontend",
        project_path=str(repo2_dir),
        branch="feature-branch",
        workspace=str(workspace),
    )
    manager.update_session(session)

    # Verify we have 2 conversations
    assert len(session.conversations) == 2

    # Mock current working directory to be backend-api (matches first conversation)
    with patch("devflow.cli.commands.open_command.Path.cwd") as mock_cwd:
        mock_cwd.return_value = repo1_dir

        # Mock conversation selection function
        with patch("devflow.cli.commands.open_command._handle_conversation_selection_without_detection") as mock_selection:
            mock_selection.return_value = False  # User cancelled

            # Call open_session from backend-api directory
            # OLD BEHAVIOR: Would auto-select backend-api conversation without prompting
            # NEW BEHAVIOR: Always prompts for conversation selection
            open_session("test-session")

            # Verify that conversation selection WAS prompted despite being in matching directory
            mock_selection.assert_called_once()
            call_args = mock_selection.call_args
            assert len(call_args[0][0].conversations) == 2


def test_open_multi_conversation_prompt_shows_all_conversations(tmp_path, temp_daf_home, capsys):
    """Test that the conversation selection prompt shows all conversations with details."""
    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Create workspace with three repos
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repo1_dir = workspace / "backend-api"
    repo1_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo1_dir, capture_output=True)

    repo2_dir = workspace / "frontend-app"
    repo2_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo2_dir, capture_output=True)

    repo3_dir = workspace / "shared-lib"
    repo3_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo3_dir, capture_output=True)

    # Configure workspace
    config = config_loader.load_config()
    if config:
        from devflow.config.models import WorkspaceDefinition

        config.repos.workspaces = [

            WorkspaceDefinition(name="default", path=str(workspace))

        ]
        config_loader.save_config(config)

    # Create session with 3 conversations
    session = manager.create_session(
        name="test-session",
        goal="Multi-repo feature",
        working_directory="backend-api",
        project_path=str(repo1_dir),
        branch="feature-branch",
        ai_agent_session_id="uuid-backend",
    )
    session.add_conversation(
        working_dir="frontend-app",
        ai_agent_session_id="uuid-frontend",
        project_path=str(repo2_dir),
        branch="feature-branch",
        workspace=str(workspace),
    )
    session.add_conversation(
        working_dir="shared-lib",
        ai_agent_session_id="uuid-shared",
        project_path=str(repo3_dir),
        branch="feature-branch",
        workspace=str(workspace),
    )
    manager.update_session(session)

    # Verify we have 3 conversations
    assert len(session.conversations) == 3

    # Mock user cancelling the prompt
    with patch("rich.prompt.IntPrompt.ask") as mock_prompt:
        # Simulate user pressing Ctrl+C to cancel
        mock_prompt.side_effect = KeyboardInterrupt()

        # Call open_session - should show all 3 conversations
        try:
            open_session("test-session")
        except (KeyboardInterrupt, SystemExit):
            pass  # Expected when user cancels

        # Capture output
        captured = capsys.readouterr()

        # Verify output shows all 3 conversations
        assert "Found 3 conversation(s)" in captured.out
        assert "backend-api" in captured.out
        assert "frontend-app" in captured.out
        assert "shared-lib" in captured.out
        assert "Create new conversation" in captured.out
