"""Test for workspace selection bug fix (AAP-64504).

This test verifies that _prompt_for_working_directory respects the selected
workspace when scanning for repositories, instead of always using the default workspace.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from devflow.cli.commands.open_command import _prompt_for_working_directory
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkspaceDefinition
from devflow.session.manager import SessionManager


@pytest.fixture
def mock_config_multi_workspace():
    """Create a mock config with multiple workspaces."""
    # Create mock repos object
    mock_repos = MagicMock()
    mock_repos.workspaces = [
        WorkspaceDefinition(name="ai", path="/Users/test/development/ai"),
        WorkspaceDefinition(name="project-b", path="/Users/test/development/project-b"),
    ]
    mock_repos.last_used_workspace = "project-b"  # Default is project-b

    # Mock get_workspace_by_name method
    def get_workspace_by_name(name):
        for ws in mock_repos.workspaces:
            if ws.name == name:
                return ws
        return None
    mock_repos.get_workspace_by_name = get_workspace_by_name

    # Mock get_default_workspace_path method
    def get_default_workspace_path():
        if mock_repos.last_used_workspace:
            ws = get_workspace_by_name(mock_repos.last_used_workspace)
            return ws.path if ws else None
        return None
    mock_repos.get_default_workspace_path = get_default_workspace_path

    # Create mock config object
    mock_config = MagicMock()
    mock_config.repos = mock_repos

    return mock_config


@pytest.fixture
def mock_config_loader(mock_config_multi_workspace, tmp_path):
    """Create a mock config loader."""
    config_loader = MagicMock(spec=ConfigLoader)
    config_loader.load_config.return_value = mock_config_multi_workspace
    config_loader.sessions_dir = tmp_path / "sessions"
    config_loader.sessions_dir.mkdir(parents=True, exist_ok=True)
    config_loader.sessions_file = config_loader.sessions_dir / "sessions.json"
    return config_loader


@pytest.fixture
def mock_session(mock_config_loader):
    """Create a mock session."""
    session_manager = SessionManager(mock_config_loader)
    session = session_manager.create_session(
        name="test-session",
        issue_key="AAP-12345",
        goal="Test goal"
    )
    return session


def test_prompt_for_working_directory_uses_selected_workspace(
    mock_session,
    mock_config_loader,
    mock_config_multi_workspace,
    monkeypatch,
):
    """Test that _prompt_for_working_directory uses the selected workspace from -w flag.
    
    Bug: When user runs 'daf open AAP-12345 -w ai', the function should scan
    /Users/test/development/ai, not the default workspace /Users/test/development/project-b.
    """
    # Create session manager
    session_manager = SessionManager(mock_config_loader)
    
    # Mock Path to avoid filesystem operations
    mock_ai_workspace = MagicMock(spec=Path)
    mock_ai_workspace.expanduser.return_value = mock_ai_workspace
    mock_ai_workspace.exists.return_value = True
    mock_ai_workspace.is_dir.return_value = True
    mock_ai_workspace.__str__.return_value = "/Users/test/development/ai"
    
    # Mock iterdir to return empty list (no repos for simplicity)
    mock_ai_workspace.iterdir.return_value = []
    
    # Mock Path constructor to return our mock workspace
    def mock_path_constructor(path_str):
        if str(path_str) == "/Users/test/development/ai":
            return mock_ai_workspace
        return MagicMock(spec=Path)
    
    # Mock Prompt to simulate user input
    mock_prompt = MagicMock()
    mock_prompt.ask.return_value = "cancel"  # User cancels after seeing the prompt
    
    with patch('devflow.cli.commands.open_command.Path', side_effect=mock_path_constructor), \
         patch('rich.prompt.Prompt', mock_prompt), \
         patch('devflow.cli.commands.open_command.console') as mock_console:
        
        # Call the function with selected_workspace_name="ai"
        result = _prompt_for_working_directory(
            session=mock_session,
            config_loader=mock_config_loader,
            session_manager=session_manager,
            selected_workspace_name="ai"  # User specified -w ai
        )
        
        # Verify that the correct workspace path was used for scanning
        # Find the console.print call that shows "Scanning workspace:"
        scanning_calls = [
            call for call in mock_console.print.call_args_list
            if len(call[0]) > 0 and "Scanning workspace:" in str(call[0][0])
        ]
        
        # Should have printed the AI workspace path, not project-b
        assert len(scanning_calls) > 0, "Should have printed 'Scanning workspace:' message"
        scanning_message = str(scanning_calls[0][0][0])
        assert "/Users/test/development/ai" in scanning_message, \
            f"Should scan AI workspace, but got: {scanning_message}"
        assert "/Users/test/development/project-b" not in scanning_message, \
            f"Should NOT scan project-b workspace, but got: {scanning_message}"


def test_prompt_for_working_directory_uses_default_when_no_selection(
    mock_session,
    mock_config_loader,
    mock_config_multi_workspace,
    monkeypatch,
):
    """Test that _prompt_for_working_directory uses default workspace when no -w flag provided.
    
    This verifies backward compatibility - when no workspace is selected,
    the function should use the default workspace (last_used_workspace).
    """
    # Create session manager
    session_manager = SessionManager(mock_config_loader)
    
    # Mock Path to avoid filesystem operations
    mock_default_workspace = MagicMock(spec=Path)
    mock_default_workspace.expanduser.return_value = mock_default_workspace
    mock_default_workspace.exists.return_value = True
    mock_default_workspace.is_dir.return_value = True
    mock_default_workspace.__str__.return_value = "/Users/test/development/project-b"
    
    # Mock iterdir to return empty list
    mock_default_workspace.iterdir.return_value = []
    
    # Mock Path constructor
    def mock_path_constructor(path_str):
        if str(path_str) == "/Users/test/development/project-b":
            return mock_default_workspace
        return MagicMock(spec=Path)
    
    # Mock Prompt to simulate user input
    mock_prompt = MagicMock()
    mock_prompt.ask.return_value = "cancel"
    
    with patch('devflow.cli.commands.open_command.Path', side_effect=mock_path_constructor), \
         patch('rich.prompt.Prompt', mock_prompt), \
         patch('devflow.cli.commands.open_command.console') as mock_console:
        
        # Call the function WITHOUT selected_workspace_name (backward compatibility)
        result = _prompt_for_working_directory(
            session=mock_session,
            config_loader=mock_config_loader,
            session_manager=session_manager
            # selected_workspace_name NOT provided
        )
        
        # Verify that the default workspace was used
        scanning_calls = [
            call for call in mock_console.print.call_args_list
            if len(call[0]) > 0 and "Scanning workspace:" in str(call[0][0])
        ]
        
        assert len(scanning_calls) > 0, "Should have printed 'Scanning workspace:' message"
        scanning_message = str(scanning_calls[0][0][0])
        assert "/Users/test/development/project-b" in scanning_message, \
            f"Should scan default (project-b) workspace, but got: {scanning_message}"
