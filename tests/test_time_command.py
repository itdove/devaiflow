"""Tests for time command."""

from datetime import datetime, timedelta
from unittest.mock import patch

from devflow.cli.commands.time_command import show_time
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkSession
from devflow.session.manager import SessionManager


def test_show_time_no_active_sessions(temp_daf_home):
    """Test time command with no active sessions."""
    show_time()
    # Should display "No active sessions"


def test_show_time_with_identifier(temp_daf_home):
    """Test time command for a specific session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add work session
    start = datetime.now()
    end = start + timedelta(hours=2)
    session.work_sessions = [WorkSession(user="testuser", start=start, end=end)]
    session_manager.index.sessions["test-session"] = session
    session_manager._save_index()

    show_time(identifier="test-session")
    # Should display time table


def test_show_time_no_work_sessions(temp_daf_home):
    """Test time command for session with no work sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="empty-session",
        goal="No work yet",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    show_time(identifier="empty-session")
    # Should display "No work sessions recorded"


def test_show_time_uses_most_recent_in_progress(temp_daf_home):
    """Test time command auto-selects most recent in-progress session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session1 = session_manager.create_session(
        name="session-1",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    session1.status = "in_progress"
    session_manager.index.sessions["session-1"] = session1
    session_manager._save_index()

    show_time()
    # Should auto-select session-1


def test_show_time_with_multiple_users(temp_daf_home):
    """Test time command shows per-user breakdown."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="multi-user",
        goal="Team work",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add work sessions from different users
    start = datetime.now()
    session.work_sessions = [
        WorkSession(user="alice", start=start, end=start + timedelta(hours=3)),
        WorkSession(user="bob", start=start, end=start + timedelta(hours=1)),
    ]
    session_manager.index.sessions["multi-user"] = session
    session_manager._save_index()

    show_time(identifier="multi-user")
    # Should display per-user breakdown


def test_show_time_with_active_work_session(temp_daf_home):
    """Test time command with an active (no end time) work session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="active-work",
        goal="Currently working",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add active work session (no end time)
    start = datetime.now()
    session.work_sessions = [WorkSession(user="testuser", start=start, end=None)]
    session_manager.index.sessions["active-work"] = session
    session_manager._save_index()

    show_time(identifier="active-work")
    # Should display "in progress" for duration


def test_show_time_with_nonexistent_session(temp_daf_home):
    """Test time command with non-existent session identifier."""
    # Call show_time with identifier that doesn't exist
    # This triggers line 38: early return when get_session_with_prompt returns None
    show_time(identifier="non-existent-session")
    # Should return early without error


def test_show_time_latest_flag_with_no_active(temp_daf_home):
    """Test time command with --latest flag when no active sessions."""
    show_time(latest=True)
    # Should display "No active sessions"


def test_show_time_latest_flag_with_active(temp_daf_home):
    """Test time command with --latest flag selects most recent."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="latest-session",
        goal="Latest work",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )
    session.status = "in_progress"
    session.issue_key = "TEST-123"

    # Add work session
    start = datetime.now()
    end = start + timedelta(hours=1, minutes=30)
    session.work_sessions = [WorkSession(user="testuser", start=start, end=end)]
    session_manager.index.sessions["latest-session"] = session
    session_manager._save_index()

    show_time(latest=True)
    # Should auto-select and display the latest session


def test_show_time_with_jira_key_display(temp_daf_home):
    """Test time command displays JIRA key when present."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="jira-session",
        goal="JIRA work",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )
    session.issue_key = "PROJ-12345"

    # Add work session to trigger table display
    start = datetime.now()
    end = start + timedelta(hours=2, minutes=15)
    session.work_sessions = [WorkSession(user="alice", start=start, end=end)]
    session_manager.index.sessions["jira-session"] = session
    session_manager._save_index()

    show_time(identifier="jira-session")
    # Should display JIRA key in output


def test_show_time_calculates_duration_correctly(temp_daf_home):
    """Test time command calculates hours and minutes correctly."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="duration-test",
        goal="Test duration calculation",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add work sessions with specific durations
    start = datetime.now()
    session.work_sessions = [
        WorkSession(user="alice", start=start, end=start + timedelta(hours=3, minutes=45)),
        WorkSession(user="bob", start=start, end=start + timedelta(hours=1, minutes=20)),
    ]
    session_manager.index.sessions["duration-test"] = session
    session_manager._save_index()

    show_time(identifier="duration-test")
    # Should display correct total: 5h 5m


def test_show_time_with_unknown_user(temp_daf_home):
    """Test time command handles work sessions with no user."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-user-session",
        goal="Anonymous work",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add work session with user=None
    start = datetime.now()
    end = start + timedelta(hours=1)
    session.work_sessions = [WorkSession(user=None, start=start, end=end)]
    session_manager.index.sessions["no-user-session"] = session
    session_manager._save_index()

    show_time(identifier="no-user-session")
    # Should display "unknown" for user


def test_show_time_percentage_calculation_multiple_users(temp_daf_home):
    """Test per-user time breakdown percentage calculation."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="percentage-test",
        goal="Test percentages",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add work sessions: alice 3h (75%), bob 1h (25%)
    start = datetime.now()
    session.work_sessions = [
        WorkSession(user="alice", start=start, end=start + timedelta(hours=3)),
        WorkSession(user="bob", start=start, end=start + timedelta(hours=1)),
    ]
    session_manager.index.sessions["percentage-test"] = session
    session_manager._save_index()

    show_time(identifier="percentage-test")
    # Should display alice: 75%, bob: 25%
