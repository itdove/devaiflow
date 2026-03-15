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
        ai_agent_session_id="test-session-id",
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

    # Mock subprocess.run to capture the launch command
    mock_subprocess_run = MagicMock()

    # Mock should_launch_claude_code to return True (skip prompting)
    with patch('devflow.cli.commands.open_command.subprocess.run', mock_subprocess_run), \
         patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=True), \
         patch('devflow.cli.commands.open_command._display_session_summary'), \
         patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
         patch('devflow.cli.commands.open_command._validate_context_files', return_value=True):

        # Import and call open_session
        from devflow.cli.commands.open_command import open_session

        # This should not raise an exception and should call subprocess.run
        open_session("multi-project-test", output_json=False)

        # Verify subprocess.run was called (Claude was launched)
        assert mock_subprocess_run.called, "subprocess.run should have been called to launch Claude"

        # Verify the cwd parameter was set correctly (not None)
        call_kwargs = mock_subprocess_run.call_args[1]
        assert 'cwd' in call_kwargs, "cwd should be passed to subprocess.run"
        assert call_kwargs['cwd'] is not None, "cwd should not be None"
        assert call_kwargs['cwd'] == str(workspace_path), \
            f"cwd should be workspace_path ({workspace_path}), got {call_kwargs['cwd']}"


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

    # Mock subprocess.run to capture the launch command
    mock_subprocess_run = MagicMock()

    # Mock all the required functions
    with patch('devflow.cli.commands.open_command.subprocess.run', mock_subprocess_run), \
         patch('devflow.cli.commands.open_command.should_launch_claude_code', return_value=True), \
         patch('devflow.cli.commands.open_command._display_session_summary'), \
         patch('devflow.cli.commands.open_command.check_concurrent_session', return_value=True), \
         patch('devflow.cli.commands.open_command._validate_context_files', return_value=True), \
         patch('devflow.cli.commands.open_command._generate_initial_prompt', return_value="Test prompt"), \
         patch('devflow.utils.claude_commands.build_claude_command', return_value=["claude", "--session-id", "test"]):

        # Import and call open_session
        from devflow.cli.commands.open_command import open_session

        # This should not raise an exception and should call subprocess.run
        open_session("multi-project-first-launch", output_json=False)

        # Verify subprocess.run was called (Claude was launched)
        assert mock_subprocess_run.called, "subprocess.run should have been called to launch Claude"

        # Verify the cwd parameter was set correctly (not None)
        call_kwargs = mock_subprocess_run.call_args[1]
        assert 'cwd' in call_kwargs, "cwd should be passed to subprocess.run"
        assert call_kwargs['cwd'] is not None, "cwd should not be None"
        assert call_kwargs['cwd'] == str(workspace_path), \
            f"cwd should be workspace_path ({workspace_path}), got {call_kwargs['cwd']}"
