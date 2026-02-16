"""Tests for Windsurf agent."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from devflow.agent.windsurf_agent import WindsurfAgent


def test_windsurf_agent_init_default():
    """Test WindsurfAgent initialization with default directory."""
    agent = WindsurfAgent()

    assert agent.windsurf_dir == Path.home() / ".windsurf"
    assert agent.workspace_storage == agent.windsurf_dir / "User" / "workspaceStorage"


def test_windsurf_agent_init_custom_dir():
    """Test WindsurfAgent initialization with custom directory."""
    custom_dir = Path("/custom/windsurf")
    agent = WindsurfAgent(windsurf_dir=custom_dir)

    assert agent.windsurf_dir == custom_dir
    assert agent.workspace_storage == custom_dir / "User" / "workspaceStorage"


def test_launch_session():
    """Test launching Windsurf session."""
    agent = WindsurfAgent()

    with patch('devflow.agent.windsurf_agent.subprocess.Popen') as mock_popen:
        with patch('devflow.agent.windsurf_agent.require_tool'):
            process = agent.launch_session("/path/to/project")

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            assert call_args[0][0] == ["windsurf", "/path/to/project"]


def test_resume_session():
    """Test resuming Windsurf session."""
    agent = WindsurfAgent()

    with patch('devflow.agent.windsurf_agent.subprocess.Popen') as mock_popen:
        with patch('devflow.agent.windsurf_agent.require_tool'):
            process = agent.resume_session("session-123", "/path/to/project")

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            assert call_args[0][0] == ["windsurf", "/path/to/project"]


def test_capture_session_id():
    """Test capturing session ID."""
    agent = WindsurfAgent()

    with patch('devflow.agent.windsurf_agent.time.time', return_value=1234567890):
        session_id = agent.capture_session_id("/path/to/project")

        assert session_id.startswith("windsurf-")
        assert "-path-to-project-" in session_id
        assert session_id.endswith("1234567890")


def test_get_session_file_path_fallback():
    """Test getting session file path fallback."""
    agent = WindsurfAgent()

    path = agent.get_session_file_path("session-123", "/path/to/project")

    # Should return a path with state.vscdb
    assert "state.vscdb" in str(path)


def test_session_exists_true():
    """Test session exists when file exists."""
    agent = WindsurfAgent()

    with patch.object(agent, 'get_session_file_path') as mock_get_path:
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.parent.exists.return_value = False
        mock_get_path.return_value = mock_file

        exists = agent.session_exists("session-123", "/path/to/project")

        assert exists is True


def test_session_exists_parent():
    """Test session exists when parent directory exists."""
    agent = WindsurfAgent()

    with patch.object(agent, 'get_session_file_path') as mock_get_path:
        mock_file = MagicMock()
        mock_file.exists.return_value = False
        mock_file.parent.exists.return_value = True
        mock_get_path.return_value = mock_file

        exists = agent.session_exists("session-123", "/path/to/project")

        assert exists is True


def test_get_existing_sessions():
    """Test getting existing sessions returns empty set."""
    agent = WindsurfAgent()

    sessions = agent.get_existing_sessions("/path/to/project")

    assert sessions == set()


def test_get_session_message_count():
    """Test getting session message count returns 0."""
    agent = WindsurfAgent()

    count = agent.get_session_message_count("session-123", "/path/to/project")

    assert count == 0


def test_encode_project_path():
    """Test encoding project path."""
    agent = WindsurfAgent()

    encoded = agent.encode_project_path("/path/to/my_project")

    assert encoded == "-path-to-my-project"


def test_get_agent_home_dir():
    """Test getting agent home directory."""
    agent = WindsurfAgent()

    home_dir = agent.get_agent_home_dir()

    assert home_dir == agent.windsurf_dir


def test_get_agent_name():
    """Test getting agent name."""
    agent = WindsurfAgent()

    name = agent.get_agent_name()

    assert name == "windsurf"
