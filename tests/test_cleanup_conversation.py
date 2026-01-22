"""Tests for cleanup_conversation command."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from devflow.cli.commands.cleanup_command import (
    _extract_message_time,
    _format_size,
    _find_conversation_file,
    cleanup_conversation,
)
from devflow.config.loader import ConfigLoader
from devflow.config.models import Session
from devflow.session.manager import SessionManager


@pytest.fixture
def mock_conversation_file(tmp_path):
    """Create a mock conversation file with test messages."""
    claude_dir = tmp_path / ".claude" / "projects" / "test-project"
    claude_dir.mkdir(parents=True)

    conversation_file = claude_dir / "test-session-id.jsonl"

    # Create test messages with timestamps
    now = datetime.now()
    messages = []

    # Add 10 old messages (8 hours ago)
    for i in range(10):
        msg = {
            "id": f"msg-old-{i}",
            "timestamp": (now - timedelta(hours=8, minutes=i)).isoformat() + "Z",
            "content": f"Old message {i}",
        }
        messages.append(msg)

    # Add 5 recent messages (1 hour ago)
    for i in range(5):
        msg = {
            "id": f"msg-recent-{i}",
            "timestamp": (now - timedelta(hours=1, minutes=i)).isoformat() + "Z",
            "content": f"Recent message {i}",
        }
        messages.append(msg)

    # Write messages to file
    with open(conversation_file, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")

    return conversation_file


@pytest.fixture
def session_manager_with_session(temp_daf_home, monkeypatch):
    """Create a session manager with a test session."""
    # Set up home directory
    monkeypatch.setenv("HOME", str(temp_daf_home))

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a test session with proper conversation
    session = Session(
        name="test-session",
        issue_key="PROJ-12345",
        goal="Test session goal",
        working_directory="test-dir",
        ai_agent_session_id="test-session-id",  # Set deprecated field for cleanup_conversation
        status="active",
    )

    # Save the session
    session_manager.index.add_session(session)
    session_manager._save_index()

    return session_manager, session


def test_extract_message_time_with_timestamp():
    """Test _extract_message_time with timestamp field."""
    now = datetime.now()
    msg = {"timestamp": now.isoformat() + "Z"}
    result = _extract_message_time(msg)
    assert result is not None
    assert abs((result - now).total_seconds()) < 1


def test_extract_message_time_with_snapshot():
    """Test _extract_message_time with nested snapshot timestamp."""
    now = datetime.now()
    msg = {"snapshot": {"timestamp": now.isoformat() + "Z"}}
    result = _extract_message_time(msg)
    assert result is not None
    assert abs((result - now).total_seconds()) < 1


def test_extract_message_time_no_timestamp():
    """Test _extract_message_time returns None when no timestamp."""
    msg = {"id": "test", "content": "no timestamp"}
    result = _extract_message_time(msg)
    assert result is None


def test_format_size():
    """Test _format_size formatting."""
    assert _format_size(500) == "500.0 B"
    assert _format_size(1500) == "1.5 KB"
    assert _format_size(1500000) == "1.4 MB"
    assert _format_size(1500000000) == "1.4 GB"


def test_find_conversation_file(tmp_path, monkeypatch):
    """Test _find_conversation_file finds conversation in claude projects."""
    monkeypatch.setenv("HOME", str(tmp_path))

    # Create mock claude projects directory
    claude_dir = tmp_path / ".claude" / "projects" / "encoded-project-path"
    claude_dir.mkdir(parents=True)

    # Create conversation file
    session_id = "test-uuid-1234"
    conv_file = claude_dir / f"{session_id}.jsonl"
    conv_file.write_text('{"test": "data"}\n')

    # Should find the file
    result = _find_conversation_file(session_id)
    assert result == conv_file
    assert result.exists()


def test_find_conversation_file_not_found(tmp_path, monkeypatch):
    """Test _find_conversation_file returns None when file doesn't exist."""
    monkeypatch.setenv("HOME", str(tmp_path))

    result = _find_conversation_file("nonexistent-session-id")
    assert result is None




def test_cleanup_conversation_session_not_found(temp_daf_home, monkeypatch, capsys):
    """Test cleanup_conversation when session is not found."""
    monkeypatch.setenv("HOME", str(temp_daf_home))

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    cleanup_conversation(
        identifier="nonexistent-session",
        older_than="2h",
        dry_run=False,
        force=False,
    )

    captured = capsys.readouterr()
    assert "Session 'nonexistent-session' not found" in captured.out


def test_cleanup_conversation_no_ai_agent_session_id(
    session_manager_with_session, monkeypatch, capsys
):
    """Test cleanup_conversation when session has no Claude session ID."""
    session_manager, session = session_manager_with_session

    # Remove Claude session ID by clearing conversations
    session.conversations = {}  # Clear conversations
    session_manager.update_session(session)

    cleanup_conversation(
        identifier="test-session",
        older_than="2h",
        dry_run=False,
        force=False,
    )

    captured = capsys.readouterr()
    assert "has no Claude session ID" in captured.out


