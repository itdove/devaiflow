"""Test for multi-project session workspace_path fallback bug fix."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from devflow.config.loader import ConfigLoader
from devflow.config.models import Conversation, ConversationContext, ProjectInfo, WorkspaceDefinition
from devflow.session.manager import SessionManager


def test_open_multiproject_session_with_none_workspace_path(temp_daf_home, tmp_path):
    """Test that multi-project sessions with None workspace_path can launch Claude.

    This test verifies the bug fix where multi-project sessions created before
    workspace_path was added to ConversationContext would fail to launch because
    active_conv.workspace_path was None, causing launch_dir to be None, which
    prevented subprocess.run from being called.

    The fix ensures we fall back to the workspace_path computed from config
    when active_conv.workspace_path is None.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Setup workspace in config
    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()

    # Create two test projects
    project1 = workspace_path / "project1"
    project2 = workspace_path / "project2"
    project1.mkdir()
    project2.mkdir()

    # Initialize as git repos
    for proj in [project1, project2]:
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=proj, capture_output=True)
        (proj / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=proj, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "test-branch"], cwd=proj, capture_output=True)

    # Create config with workspace by writing to config.json
    import json
    config_file = Path.home() / ".daf-sessions" / "config.json"
    config_data = {
        "repos": {
            "workspaces": [
                {
                    "name": "test-workspace",
                    "path": str(workspace_path)
                }
            ]
        }
    }
    config_file.write_text(json.dumps(config_data, indent=2))

    # Create a multi-project session with workspace_path=None (simulating old session)
    session = session_manager.create_session(
        name="multi-project-test",
        goal="Test multi-project",
        working_directory="multiproject-test",
    )

    # Manually create a multi-project conversation with workspace_path=None
    conv_context = ConversationContext(
        ai_agent_session_id="12345678-1234-5678-1234-567812345678",
        is_multi_project=True,
        workspace_path=None,  # This is the bug condition - should be set but is None
        projects={
            "project1": ProjectInfo(
                project_path=str(project1),
                repo_name="project1",
                branch="test-branch",
                base_branch="main"
            ),
            "project2": ProjectInfo(
                project_path=str(project2),
                repo_name="project2",
                branch="test-branch",
                base_branch="main"
            )
        }
    )

    # Wrap in Conversation object (sessions.conversations stores Conversation objects)
    conv = Conversation(active_session=conv_context)
    session.conversations["multiproject-test"] = conv
    session.working_directory = "multiproject-test"
    session.workspace_name = "test-workspace"
    session_manager.update_session(session)

    # Mock subprocess.run to prevent actual CLI launch
    mock_subprocess_run = MagicMock()

    # Mock should_launch_claude_code to return True (skip prompting)
    with patch('subprocess.run', mock_subprocess_run), \
         patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=True), \
         patch('devflow.cli.commands.open_command._display_session_summary'), \
         patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
         patch('devflow.cli.commands.open_command._validate_context_files', return_value=True):

        # Import and call open_session
        from devflow.cli.commands.open_command import open_session

        # This should not raise an exception and should call subprocess.run
        open_session("multi-project-test", output_json=False)

        # Verify subprocess.run was called with Claude resume
        assert mock_subprocess_run.called, "subprocess.run should have been called"

        # Verify the command includes --resume with the session ID
        call_args = mock_subprocess_run.call_args[0][0]
        assert "--resume" in call_args, "Command should include --resume flag"
        assert "12345678-1234-5678-1234-567812345678" in call_args, "Command should include session ID"


def test_open_multiproject_session_first_launch_with_none_workspace_path(temp_daf_home, tmp_path):
    """Test first-time launch of multi-project session with None workspace_path.

    This tests the same bug but for the first-time launch code path.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Setup workspace in config
    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()

    # Create two test projects
    project1 = workspace_path / "project1"
    project2 = workspace_path / "project2"
    project1.mkdir()
    project2.mkdir()

    # Initialize as git repos
    for proj in [project1, project2]:
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=proj, capture_output=True)
        (proj / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=proj, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "test-branch"], cwd=proj, capture_output=True)

    # Create config with workspace by writing to config.json
    import json
    config_file = Path.home() / ".daf-sessions" / "config.json"
    config_data = {
        "repos": {
            "workspaces": [
                {
                    "name": "test-workspace",
                    "path": str(workspace_path)
                }
            ]
        }
    }
    config_file.write_text(json.dumps(config_data, indent=2))

    # Create a multi-project session for first-time launch
    session = session_manager.create_session(
        name="multi-project-first-launch",
        goal="Test multi-project first launch",
        working_directory="multiproject-first-launch",
    )

    # Manually create a multi-project conversation without ai_agent_session_id (first launch)
    conv_context = ConversationContext(
        ai_agent_session_id="",  # Empty means first launch
        is_multi_project=True,
        workspace_path=None,  # Bug condition
        projects={
            "project1": ProjectInfo(
                project_path=str(project1),
                repo_name="project1",
                branch="test-branch",
                base_branch="main"
            ),
            "project2": ProjectInfo(
                project_path=str(project2),
                repo_name="project2",
                branch="test-branch",
                base_branch="main"
            )
        }
    )

    # Wrap in Conversation object (sessions.conversations stores Conversation objects)
    conv = Conversation(active_session=conv_context)
    session.conversations["multiproject-first-launch"] = conv
    session.working_directory = "multiproject-first-launch"
    session.workspace_name = "test-workspace"
    session_manager.update_session(session)

    # Mock agent launch to capture the launch command
    mock_process = MagicMock()
    mock_process.wait = MagicMock()
    mock_agent = MagicMock()
    mock_agent.launch_with_prompt.return_value = mock_process

    # Mock all the required functions
    with patch('devflow.agent.create_agent_client', return_value=mock_agent), \
         patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=True), \
         patch('devflow.cli.commands.open_command._display_session_summary'), \
         patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
         patch('devflow.cli.commands.open_command._validate_context_files', return_value=True), \
         patch('devflow.cli.commands.open_command._generate_initial_prompt', return_value="Test prompt"):

        # Import and call open_session
        from devflow.cli.commands.open_command import open_session

        # This should not raise an exception and should call agent.launch_with_prompt
        open_session("multi-project-first-launch", output_json=False)

        # Verify agent.launch_with_prompt was called (Claude was launched)
        assert mock_agent.launch_with_prompt.called, "agent.launch_with_prompt should have been called"

        # Verify process.wait was called
        assert mock_process.wait.called, "process.wait should have been called"

        # Verify the project_path parameter was set correctly (workspace_path)
        call_kwargs = mock_agent.launch_with_prompt.call_args[1]
        assert 'project_path' in call_kwargs, "project_path should be passed to launch_with_prompt"
        assert call_kwargs['project_path'] is not None, "project_path should not be None"
        assert call_kwargs['project_path'] == str(workspace_path), \
            f"project_path should be workspace_path ({workspace_path}), got {call_kwargs['project_path']}"
