"""Tests for info command."""

from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

from devflow.cli.commands.info_command import session_info
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkSession
from devflow.session.manager import SessionManager


def test_session_info_no_sessions(temp_daf_home, capsys):
    """Test info command with no sessions."""
    session_info(identifier=None, uuid_only=False, conversation_id=None)
    captured = capsys.readouterr()
    assert "No sessions found" in captured.out


def test_session_info_with_identifier(temp_daf_home, capsys):
    """Test info command for a specific session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        branch="test-branch",
        ai_agent_session_id="uuid-test-123",
    )
    session.issue_key = "TEST-123"
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["summary"] = "Test JIRA Summary"
    session.issue_metadata["status"] = "In Progress"
    session_manager.update_session(session)

    session_info(identifier="test-session", uuid_only=False, conversation_id=None)
    captured = capsys.readouterr()

    # Verify output contains session info
    assert "Session Information" in captured.out
    assert "test-session" in captured.out
    assert "TEST-123" in captured.out
    assert "Test JIRA Summary" in captured.out
    assert "In Progress" in captured.out
    assert "Test goal" in captured.out
    assert "uuid-test-123" in captured.out
    assert "test-dir" in captured.out
    assert "/path/to/project" in captured.out
    assert "test-branch" in captured.out


def test_session_info_uuid_only(temp_daf_home, capsys):
    """Test info command with --uuid-only flag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-uuid",
        goal="Test UUID output",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-for-output",
    )

    session_info(identifier="test-uuid", uuid_only=True, conversation_id=None)
    captured = capsys.readouterr()

    # Should only output the UUID
    assert captured.out.strip() == "uuid-for-output"
    assert "Session Information" not in captured.out


def test_session_info_latest_session(temp_daf_home, capsys):
    """Test info command without identifier uses latest session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multiple sessions
    session1 = session_manager.create_session(
        name="old-session",
        goal="Older session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-old",
    )

    # Ensure session1 is older by setting last_active explicitly
    session1.last_active = datetime.now() - timedelta(hours=2)
    session_manager.index.sessions["old-session"] = session1
    session_manager._save_index()

    session2 = session_manager.create_session(
        name="recent-session",
        goal="More recent",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-recent",
    )

    # Make session2 more recent
    session2.last_active = datetime.now()
    session_manager.index.sessions["recent-session"] = session2
    session_manager._save_index()

    session_info(identifier=None, uuid_only=False, conversation_id=None)
    captured = capsys.readouterr()

    # Should show the most recent session
    assert "recent-session" in captured.out
    assert "uuid-recent" in captured.out


def test_session_info_nonexistent_session(temp_daf_home, capsys):
    """Test info command with non-existent session."""
    session_info(identifier="nonexistent", uuid_only=False, conversation_id=None)
    captured = capsys.readouterr()

    assert "not found" in captured.out.lower()


def test_session_info_with_issue_key(temp_daf_home, capsys):
    """Test info command using issue key as identifier."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="feature-branch",
        goal="Implement feature",
        working_directory="backend",
        project_path="/path/to/backend",
        ai_agent_session_id="uuid-jira-test",
    )
    session.issue_key = "PROJ-456"
    session_manager.update_session(session)

    session_info(identifier="PROJ-456", uuid_only=False, conversation_id=None)
    captured = capsys.readouterr()

    assert "feature-branch" in captured.out
    assert "PROJ-456" in captured.out
    assert "uuid-jira-test" in captured.out


def test_session_info_multiple_conversations(temp_daf_home, capsys):
    """Test info displays all conversations in a session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="multi-conv",
        goal="Multi-repo work",
        working_directory="backend",
        project_path="/path/to/backend",
        branch="feature-branch",
        ai_agent_session_id="uuid-backend",
    )

    # Add a second conversation
    session.add_conversation(
        working_dir="frontend",
        ai_agent_session_id="uuid-frontend",
        project_path="/path/to/frontend",
        branch="feature-branch",
    )

    session_manager.update_session(session)

    session_info(identifier="multi-conv", uuid_only=False, conversation_id=None)
    captured = capsys.readouterr()

    # Should show both conversations
    assert "Conversations: 2" in captured.out
    assert "backend" in captured.out
    assert "frontend" in captured.out
    assert "uuid-backend" in captured.out
    assert "uuid-frontend" in captured.out


def test_session_info_specific_conversation(temp_daf_home, capsys):
    """Test info with --conversation-id flag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="multi-conv",
        goal="Multi-repo work",
        working_directory="backend",
        project_path="/path/to/backend",
        branch="main",
        ai_agent_session_id="uuid-backend",
    )

    # Add a second conversation
    session.add_conversation(
        working_dir="frontend",
        ai_agent_session_id="uuid-frontend",
        project_path="/path/to/frontend",
        branch="main",
    )

    session_manager.update_session(session)

    # Show only second conversation
    session_info(identifier="multi-conv", uuid_only=False, conversation_id=2)
    captured = capsys.readouterr()

    # Should show only the second conversation
    assert "frontend" in captured.out
    assert "uuid-frontend" in captured.out
    # Should not show "Conversations: 2" header when filtering to specific conversation
    assert "#2" in captured.out


def test_session_info_uuid_only_with_conversation_id(temp_daf_home, capsys):
    """Test --uuid-only with --conversation-id flag."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="multi-uuid",
        goal="Multi-repo UUID test",
        working_directory="repo1",
        project_path="/path/to/repo1",
        ai_agent_session_id="uuid-repo1",
    )

    session.add_conversation(
        working_dir="repo2",
        ai_agent_session_id="uuid-repo2",
        project_path="/path/to/repo2",
        branch="main",
    )

    session_manager.update_session(session)

    # Get UUID of second conversation only
    session_info(identifier="multi-uuid", uuid_only=True, conversation_id=2)
    captured = capsys.readouterr()

    # Should output only the UUID of the second conversation
    assert captured.out.strip() == "uuid-repo2"


def test_session_info_with_time_tracking(temp_daf_home, capsys):
    """Test info displays time tracking information."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="timed-session",
        goal="Session with time",
        working_directory="project",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-timed",
    )

    # Add work sessions
    start = datetime.now()
    session.work_sessions = [
        WorkSession(user="alice", start=start, end=start + timedelta(hours=2, minutes=30)),
        WorkSession(user="bob", start=start, end=start + timedelta(hours=1, minutes=15)),
    ]
    session_manager.update_session(session)

    session_info(identifier="timed-session", uuid_only=False, conversation_id=None)
    captured = capsys.readouterr()

    # Should show time tracking
    assert "Time Tracking:" in captured.out
    # Total should be 3h 45m
    assert "3h 45m" in captured.out


def test_session_info_invalid_conversation_id(temp_daf_home, capsys):
    """Test info with invalid conversation ID."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="single-conv",
        goal="Only one conversation",
        working_directory="repo",
        project_path="/path/to/repo",
        ai_agent_session_id="uuid-single",
    )

    # Try to access conversation #2 when only #1 exists
    session_info(identifier="single-conv", uuid_only=False, conversation_id=2)
    captured = capsys.readouterr()

    assert "Invalid conversation ID" in captured.out


def test_session_info_no_conversations(temp_daf_home, capsys):
    """Test info with a session that has no conversations (edge case)."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session without conversation (shouldn't happen in practice, but test edge case)
    session = session_manager.create_session(
        name="empty-conv",
        goal="No conversations",
        working_directory=None,
        project_path=None,
        ai_agent_session_id=None,
    )

    session_info(identifier="empty-conv", uuid_only=False, conversation_id=None)
    captured = capsys.readouterr()

    assert "No conversations found" in captured.out
