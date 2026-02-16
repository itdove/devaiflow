"""Tests for session/capture.py - SessionCapture wrapper class."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from devflow.session.capture import SessionCapture


@pytest.fixture
def mock_agent():
    """Create a mock agent interface."""
    agent = MagicMock()
    agent.get_agent_home_dir.return_value = Path.home() / ".test-agent"
    agent.encode_project_path.return_value = "-path-to-project"
    agent.get_existing_sessions.return_value = {"session-1", "session-2"}
    agent.launch_session.return_value = Mock(spec=subprocess.Popen)
    agent.resume_session.return_value = Mock(spec=subprocess.Popen)
    agent.capture_session_id.return_value = "captured-session-id"
    agent.session_exists.return_value = True
    agent.get_session_message_count.return_value = 42
    return agent


def test_session_capture_init_with_agent(mock_agent):
    """Test SessionCapture initialization with custom agent."""
    capture = SessionCapture(agent=mock_agent)

    assert capture.agent == mock_agent
    assert capture.claude_dir == Path.home() / ".test-agent"
    assert capture.projects_dir == capture.claude_dir / "projects"
    mock_agent.get_agent_home_dir.assert_called_once()


def test_session_capture_init_default_agent():
    """Test SessionCapture initialization with default Claude agent."""
    pytest.importorskip("devflow.agent.claude_agent")

    capture = SessionCapture()

    assert capture.agent is not None
    assert capture.claude_dir is not None
    assert capture.projects_dir == capture.claude_dir / "projects"


def test_session_capture_init_with_claude_dir():
    """Test SessionCapture initialization with custom claude_dir."""
    pytest.importorskip("devflow.agent.claude_agent")

    custom_dir = Path("/custom/claude/dir")
    capture = SessionCapture(claude_dir=custom_dir)

    assert capture.agent is not None


def test_encode_project_path(mock_agent):
    """Test encode_project_path delegates to agent."""
    capture = SessionCapture(agent=mock_agent)

    result = capture.encode_project_path("/path/to/project")

    assert result == "-path-to-project"
    mock_agent.encode_project_path.assert_called_once_with("/path/to/project")


def test_get_session_dir(mock_agent):
    """Test get_session_dir returns correct path."""
    capture = SessionCapture(agent=mock_agent)

    result = capture.get_session_dir("/path/to/project")

    assert result == capture.projects_dir / "-path-to-project"
    mock_agent.encode_project_path.assert_called_once_with("/path/to/project")


def test_get_existing_sessions(mock_agent):
    """Test get_existing_sessions delegates to agent."""
    capture = SessionCapture(agent=mock_agent)

    result = capture.get_existing_sessions("/path/to/project")

    assert result == {"session-1", "session-2"}
    mock_agent.get_existing_sessions.assert_called_once_with("/path/to/project")


def test_launch_claude_code(mock_agent):
    """Test launch_claude_code delegates to agent.launch_session."""
    capture = SessionCapture(agent=mock_agent)

    result = capture.launch_claude_code("/path/to/project")

    assert isinstance(result, subprocess.Popen)
    mock_agent.launch_session.assert_called_once_with("/path/to/project")


def test_capture_new_session(mock_agent):
    """Test capture_new_session delegates to agent.capture_session_id."""
    capture = SessionCapture(agent=mock_agent)

    result = capture.capture_new_session(
        project_path="/path/to/project",
        timeout=20,
        poll_interval=1.0
    )

    assert result == "captured-session-id"
    mock_agent.capture_session_id.assert_called_once_with(
        "/path/to/project", 20, 1.0
    )


def test_capture_new_session_default_params(mock_agent):
    """Test capture_new_session with default parameters."""
    capture = SessionCapture(agent=mock_agent)

    result = capture.capture_new_session("/path/to/project")

    assert result == "captured-session-id"
    mock_agent.capture_session_id.assert_called_once_with(
        "/path/to/project", 10, 0.5
    )


def test_resume_claude_code(mock_agent):
    """Test resume_claude_code delegates to agent.resume_session."""
    capture = SessionCapture(agent=mock_agent)

    result = capture.resume_claude_code("session-123", "/path/to/project")

    assert isinstance(result, subprocess.Popen)
    mock_agent.resume_session.assert_called_once_with("session-123", "/path/to/project")


def test_session_exists(mock_agent):
    """Test session_exists delegates to agent."""
    capture = SessionCapture(agent=mock_agent)

    result = capture.session_exists("session-123", "/path/to/project")

    assert result is True
    mock_agent.session_exists.assert_called_once_with("session-123", "/path/to/project")


def test_get_session_message_count(mock_agent):
    """Test get_session_message_count delegates to agent."""
    capture = SessionCapture(agent=mock_agent)

    result = capture.get_session_message_count("session-123", "/path/to/project")

    assert result == 42
    mock_agent.get_session_message_count.assert_called_once_with("session-123", "/path/to/project")
