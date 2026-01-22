"""Tests for MockClaudeCode."""

import pytest
from pathlib import Path

from devflow.mocks.claude_mock import MockClaudeCode
from devflow.mocks.persistence import MockDataStore


@pytest.fixture
def mock_claude(temp_daf_home):
    """Provide a clean MockClaudeCode instance."""
    store = MockDataStore()
    store.clear_all()
    return MockClaudeCode()


def test_create_session(mock_claude):
    """Test creating a Claude Code session."""
    session_id = mock_claude.create_session(
        project_path="/path/to/project",
        initial_prompt="Initial prompt text"
    )

    assert session_id is not None
    assert len(session_id) == 36  # UUID format

    # Verify session was created
    session = mock_claude.get_session(session_id)
    assert session is not None
    assert session["project_path"] == "/path/to/project"
    assert session["active"] is True
    assert len(session["messages"]) == 1


def test_create_session_without_prompt(mock_claude):
    """Test creating a session without initial prompt."""
    session_id = mock_claude.create_session(project_path="/path/to/project")

    session = mock_claude.get_session(session_id)
    assert session is not None
    assert len(session["messages"]) == 0


def test_get_session(mock_claude):
    """Test getting a session by ID."""
    session_id = mock_claude.create_session(project_path="/path/to/project")

    session = mock_claude.get_session(session_id)
    assert session is not None
    assert session["session_id"] == session_id


def test_get_session_not_found(mock_claude):
    """Test getting a non-existent session."""
    session = mock_claude.get_session("non-existent-uuid")
    assert session is None


def test_add_message(mock_claude):
    """Test adding messages to a session."""
    session_id = mock_claude.create_session(project_path="/path/to/project")

    # Add user message
    success1 = mock_claude.add_message(session_id, "user", "Hello, Claude!")
    assert success1 is True

    # Add assistant message
    success2 = mock_claude.add_message(session_id, "assistant", "Hello! How can I help?")
    assert success2 is True

    # Verify messages
    session = mock_claude.get_session(session_id)
    assert len(session["messages"]) == 2
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "assistant"


def test_add_message_session_not_found(mock_claude):
    """Test adding a message to a non-existent session."""
    success = mock_claude.add_message("non-existent", "user", "Should fail")
    assert success is False


def test_close_session(mock_claude):
    """Test closing a session."""
    session_id = mock_claude.create_session(project_path="/path/to/project")

    # Close the session
    success = mock_claude.close_session(session_id)
    assert success is True

    # Verify session is closed
    session = mock_claude.get_session(session_id)
    assert session["active"] is False
    assert "closed_at" in session


def test_close_session_not_found(mock_claude):
    """Test closing a non-existent session."""
    success = mock_claude.close_session("non-existent")
    assert success is False


def test_resume_session(mock_claude):
    """Test resuming a closed session."""
    session_id = mock_claude.create_session(project_path="/path/to/project")

    # Close and resume
    mock_claude.close_session(session_id)
    success = mock_claude.resume_session(session_id)
    assert success is True

    # Verify session is active again
    session = mock_claude.get_session(session_id)
    assert session["active"] is True
    assert "closed_at" not in session


def test_resume_session_not_found(mock_claude):
    """Test resuming a non-existent session."""
    success = mock_claude.resume_session("non-existent")
    assert success is False


def test_list_sessions(mock_claude):
    """Test listing all sessions."""
    # Create multiple sessions
    mock_claude.create_session(project_path="/path/to/project1")
    mock_claude.create_session(project_path="/path/to/project2")

    sessions = mock_claude.list_sessions()
    assert len(sessions) == 2


def test_list_sessions_filtered_by_project(mock_claude):
    """Test listing sessions filtered by project path."""
    # Create sessions for different projects
    mock_claude.create_session(project_path="/path/to/project1")
    mock_claude.create_session(project_path="/path/to/project1")
    mock_claude.create_session(project_path="/path/to/project2")

    # List sessions for project1
    sessions = mock_claude.list_sessions(project_path="/path/to/project1")
    assert len(sessions) == 2


def test_list_sessions_active_only(mock_claude):
    """Test listing only active sessions."""
    # Create sessions
    session_id1 = mock_claude.create_session(project_path="/path/to/project")
    session_id2 = mock_claude.create_session(project_path="/path/to/project")

    # Close one session
    mock_claude.close_session(session_id1)

    # List only active sessions
    sessions = mock_claude.list_sessions(active_only=True)
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == session_id2


def test_get_message_count(mock_claude):
    """Test getting message count for a session."""
    session_id = mock_claude.create_session(project_path="/path/to/project")

    # Initially no messages
    count = mock_claude.get_message_count(session_id)
    assert count == 0

    # Add messages
    mock_claude.add_message(session_id, "user", "Message 1")
    mock_claude.add_message(session_id, "assistant", "Response 1")

    count = mock_claude.get_message_count(session_id)
    assert count == 2


def test_get_message_count_session_not_found(mock_claude):
    """Test getting message count for non-existent session."""
    count = mock_claude.get_message_count("non-existent")
    assert count == 0


def test_simulate_conversation(mock_claude):
    """Test simulating a conversation."""
    session_id = mock_claude.create_session(project_path="/path/to/project")

    # Simulate 3 exchanges
    success = mock_claude.simulate_conversation(session_id, exchanges=3)
    assert success is True

    # Verify 6 messages (3 user + 3 assistant)
    count = mock_claude.get_message_count(session_id)
    assert count == 6

    # Verify alternating roles
    session = mock_claude.get_session(session_id)
    roles = [msg["role"] for msg in session["messages"]]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]


def test_simulate_conversation_session_not_found(mock_claude):
    """Test simulating conversation for non-existent session."""
    success = mock_claude.simulate_conversation("non-existent", exchanges=3)
    assert success is False


def test_create_session_file(mock_claude, tmp_path):
    """Test creating a session .jsonl file."""
    session_id = mock_claude.create_session(
        project_path="/path/to/project",
        initial_prompt="Test prompt"
    )

    # Add more messages
    mock_claude.add_message(session_id, "assistant", "Test response")

    # Create session file
    claude_home = tmp_path / ".claude"
    session_file = mock_claude.create_session_file(session_id, claude_home=claude_home)

    assert session_file is not None
    assert session_file.exists()
    assert session_file.suffix == ".jsonl"

    # Verify file contains messages
    with open(session_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2  # 2 messages


def test_create_session_file_not_found(mock_claude, tmp_path):
    """Test creating session file for non-existent session."""
    claude_home = tmp_path / ".claude"
    session_file = mock_claude.create_session_file("non-existent", claude_home=claude_home)
    assert session_file is None
