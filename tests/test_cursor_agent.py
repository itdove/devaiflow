"""Tests for Cursor agent."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from devflow.agent.cursor_agent import CursorAgent


def test_cursor_agent_init_default():
    """Test CursorAgent initialization with default directory."""
    agent = CursorAgent()

    assert agent.cursor_dir == Path.home() / ".cursor"
    assert agent.workspace_storage == agent.cursor_dir / "User" / "workspaceStorage"


def test_cursor_agent_init_custom_dir():
    """Test CursorAgent initialization with custom directory."""
    custom_dir = Path("/custom/cursor")
    agent = CursorAgent(cursor_dir=custom_dir)

    assert agent.cursor_dir == custom_dir
    assert agent.workspace_storage == custom_dir / "User" / "workspaceStorage"


def test_launch_session():
    """Test launching Cursor session."""
    agent = CursorAgent()

    with patch('devflow.agent.cursor_agent.subprocess.Popen') as mock_popen:
        with patch('devflow.agent.cursor_agent.require_tool'):
            process = agent.launch_session("/path/to/project")

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            assert call_args[0][0] == ["cursor", "/path/to/project"]


def test_resume_session():
    """Test resuming Cursor session."""
    agent = CursorAgent()

    with patch('devflow.agent.cursor_agent.subprocess.Popen') as mock_popen:
        with patch('devflow.agent.cursor_agent.require_tool'):
            process = agent.resume_session("session-123", "/path/to/project")

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            assert call_args[0][0] == ["cursor", "/path/to/project"]


def test_capture_session_id():
    """Test capturing session ID."""
    agent = CursorAgent()

    with patch('devflow.agent.cursor_agent.time.time', return_value=1234567890):
        session_id = agent.capture_session_id("/path/to/project")

        assert session_id.startswith("cursor-")
        assert "-path-to-project-" in session_id
        assert session_id.endswith("1234567890")


def test_get_session_file_path_fallback():
    """Test getting session file path fallback."""
    agent = CursorAgent()

    path = agent.get_session_file_path("session-123", "/path/to/project")

    # Should return a path with state.vscdb
    assert "state.vscdb" in str(path)


def test_session_exists_true():
    """Test session exists when file exists."""
    agent = CursorAgent()

    with patch.object(agent, 'get_session_file_path') as mock_get_path:
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.parent.exists.return_value = False
        mock_get_path.return_value = mock_file

        exists = agent.session_exists("session-123", "/path/to/project")

        assert exists is True


def test_session_exists_parent():
    """Test session exists when parent directory exists."""
    agent = CursorAgent()

    with patch.object(agent, 'get_session_file_path') as mock_get_path:
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_file.parent.exists.return_value = True
        mock_get_path.return_value = mock_file

        exists = agent.session_exists("session-123", "/path/to/project")

        assert exists is True


def test_get_existing_sessions():
    """Test getting existing sessions returns empty set."""
    agent = CursorAgent()

    sessions = agent.get_existing_sessions("/path/to/project")

    assert sessions == set()


def test_get_session_message_count():
    """Test getting session message count returns 0."""
    agent = CursorAgent()

    count = agent.get_session_message_count("session-123", "/path/to/project")

    assert count == 0


def test_encode_project_path():
    """Test encoding project path."""
    agent = CursorAgent()

    encoded = agent.encode_project_path("/path/to/my_project")

    assert encoded == "-path-to-my-project"


def test_get_agent_home_dir():
    """Test getting agent home directory."""
    agent = CursorAgent()

    home_dir = agent.get_agent_home_dir()

    assert home_dir == agent.cursor_dir


def test_get_agent_name():
    """Test getting agent name."""
    agent = CursorAgent()

    name = agent.get_agent_name()

    assert name == "cursor"
