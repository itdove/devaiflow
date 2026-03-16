"""Test multi-project selection in daf open for synced sessions (Issue #177)."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_prompt_for_working_directory_offers_multiproject_selection(temp_daf_home, tmp_path):
    """Test that _prompt_for_working_directory offers multi-project selection when multiple repos exist.

    This verifies Issue #177: when opening a synced session without conversations,
    users should be able to select multiple projects interactively.
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Setup workspace in config
    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()

    # Create three test projects
    project1 = workspace_path / "backend-api"
    project2 = workspace_path / "frontend-app"
    project3 = workspace_path / "shared-lib"

    for proj in [project1, project2, project3]:
        proj.mkdir()
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=proj, capture_output=True)
        (proj / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=proj, capture_output=True)

    # Create config with workspace
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

    # Create a synced session without conversations (simulating daf sync)
    session = session_manager.create_session(
        name="PROJ-123",
        issue_key="PROJ-123",
        goal="Test synced session",
        working_directory=None,
        project_path=None,
    )

    # Mock user interactions
    # 1. User chooses multi-project mode: Yes
    # 2. User selects projects: "1,2" (backend-api and frontend-app)
    # 3. User accepts default branch name
    # 4. User selects base branch for each project
    mock_confirm = MagicMock()
    mock_confirm.ask.side_effect = [
        True,  # Create multi-project session? Yes
    ]

    mock_prompt = MagicMock()
    mock_prompt.ask.side_effect = [
        "1,2",  # Select projects: backend-api,frontend-app
        "PROJ-123",  # Branch name (accept default)
        "main",  # Base branch for backend-api
        "main",  # Base branch for frontend-app
    ]

    with patch('rich.prompt.Confirm.ask', mock_confirm.ask), \
         patch('rich.prompt.Prompt.ask', mock_prompt.ask), \
         patch('devflow.cli.commands.new_command._prompt_for_source_branch', return_value="main"):

        from devflow.cli.commands.open_command import _prompt_for_working_directory

        # Call the function
        result = _prompt_for_working_directory(
            session=session,
            config_loader=config_loader,
            session_manager=session_manager,
            selected_workspace_name="test-workspace",
        )

        # Verify success
        assert result is True

        # Verify session was updated with multi-project conversation
        assert len(session.conversations) == 1

        # Get the conversation
        conv_key = list(session.conversations.keys())[0]
        conv = session.conversations[conv_key]

        # Verify it's a multi-project conversation
        assert conv.active_session.is_multi_project is True
        assert len(conv.active_session.projects) == 2
        assert "backend-api" in conv.active_session.projects
        assert "frontend-app" in conv.active_session.projects


def test_prompt_for_working_directory_single_project_when_only_one_selected(temp_daf_home, tmp_path):
    """Test that selecting only one project in multi-project mode falls back to single-project."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Setup workspace in config
    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()

    # Create two test projects
    project1 = workspace_path / "backend-api"
    project2 = workspace_path / "frontend-app"

    for proj in [project1, project2]:
        proj.mkdir()
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=proj, capture_output=True)
        (proj / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=proj, capture_output=True)

    # Create config with workspace
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
        },
        "templates": {
            "auto_create": False  # Disable auto-create for this test
        }
    }
    config_file.write_text(json.dumps(config_data, indent=2))

    # Create a synced session without conversations
    session = session_manager.create_session(
        name="PROJ-124",
        issue_key="PROJ-124",
        goal="Test single project fallback",
        working_directory=None,
        project_path=None,
    )

    # Mock user interactions
    # 1. User chooses multi-project mode: Yes
    # 2. User selects only one project: "1"
    # 3. System falls back to single-project mode
    # 4. User confirms the single selection
    mock_confirm = MagicMock()
    mock_confirm.ask.side_effect = [
        True,  # Create multi-project session? Yes
    ]

    mock_prompt = MagicMock()
    mock_prompt.ask.side_effect = [
        "1",  # Select only project 1
        "1",  # Confirm single-project selection
    ]

    with patch('rich.prompt.Confirm.ask', mock_confirm.ask), \
         patch('rich.prompt.Prompt.ask', mock_prompt.ask):

        from devflow.cli.commands.open_command import _prompt_for_working_directory

        # Call the function
        result = _prompt_for_working_directory(
            session=session,
            config_loader=config_loader,
            session_manager=session_manager,
            selected_workspace_name="test-workspace",
        )

        # Verify success
        assert result is True

        # Verify session has a single-project conversation
        assert len(session.conversations) == 1
        conv_key = list(session.conversations.keys())[0]
        conv = session.conversations[conv_key]

        # Verify it's NOT a multi-project conversation
        assert conv.active_session.is_multi_project is False


def test_prompt_for_working_directory_no_multiproject_when_user_declines(temp_daf_home, tmp_path):
    """Test that declining multi-project mode continues with single-project selection."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Setup workspace in config
    workspace_path = tmp_path / "test-workspace"
    workspace_path.mkdir()

    # Create two test projects
    project1 = workspace_path / "backend-api"
    project2 = workspace_path / "frontend-app"

    for proj in [project1, project2]:
        proj.mkdir()
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=proj, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=proj, capture_output=True)
        (proj / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=proj, capture_output=True)

    # Create config with workspace
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
        },
        "templates": {
            "auto_create": False  # Disable auto-create for this test
        }
    }
    config_file.write_text(json.dumps(config_data, indent=2))

    # Create a synced session without conversations
    session = session_manager.create_session(
        name="PROJ-125",
        issue_key="PROJ-125",
        goal="Test declining multi-project",
        working_directory=None,
        project_path=None,
    )

    # Mock user interactions
    # 1. User declines multi-project mode: No
    # 2. User selects a single project: "1"
    mock_confirm = MagicMock()
    mock_confirm.ask.side_effect = [
        False,  # Create multi-project session? No
    ]

    mock_prompt = MagicMock()
    mock_prompt.ask.side_effect = [
        "1",  # Select single project
    ]

    with patch('rich.prompt.Confirm.ask', mock_confirm.ask), \
         patch('rich.prompt.Prompt.ask', mock_prompt.ask):

        from devflow.cli.commands.open_command import _prompt_for_working_directory

        # Call the function
        result = _prompt_for_working_directory(
            session=session,
            config_loader=config_loader,
            session_manager=session_manager,
            selected_workspace_name="test-workspace",
        )

        # Verify success
        assert result is True

        # Verify session has a single-project conversation
        assert len(session.conversations) == 1
        conv_key = list(session.conversations.keys())[0]
        conv = session.conversations[conv_key]

        # Verify it's NOT a multi-project conversation
        assert conv.active_session.is_multi_project is False
