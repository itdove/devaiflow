"""Tests for pause and resume commands."""

from datetime import datetime, timedelta

from devflow.cli.commands.pause_command import pause_time_tracking
from devflow.cli.commands.resume_command import resume_time_tracking
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkSession
from devflow.session.manager import SessionManager


def test_pause_time_tracking_no_active_sessions(temp_daf_home):
    """Test pause command with no active sessions."""
    pause_time_tracking()
    # Should display "No active sessions" and return without error


def test_pause_time_tracking_with_identifier(temp_daf_home):
    """Test pause command for a specific session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add active work session
    start = datetime.now()
    session.work_sessions = [WorkSession(user="testuser", start=start, end=None)]
    session.time_tracking_state = "running"
    session_manager.update_session(session)

    # Should pause successfully
    pause_time_tracking(identifier="test-session")


def test_pause_time_tracking_already_paused(temp_daf_home):
    """Test pause command when time tracking is already paused."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="paused-session",
        goal="Already paused",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )
    session.time_tracking_state = "paused"
    session_manager.update_session(session)

    # Should display warning that time tracking is not running
    pause_time_tracking(identifier="paused-session")


def test_pause_time_tracking_latest_flag(temp_daf_home):
    """Test pause command with --latest flag."""
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
    session.time_tracking_state = "running"
    session.work_sessions = [WorkSession(user="testuser", start=datetime.now(), end=None)]
    session_manager.update_session(session)

    # Should pause successfully
    pause_time_tracking(latest=True)


def test_pause_time_tracking_with_jira_key_display(temp_daf_home):
    """Test pause command displays JIRA key when present."""
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
    session.time_tracking_state = "running"
    session.work_sessions = [WorkSession(user="alice", start=datetime.now(), end=None)]
    session_manager.update_session(session)

    # Should display JIRA key in output
    pause_time_tracking(identifier="jira-session")


def test_pause_time_tracking_nonexistent_session(temp_daf_home):
    """Test pause command with non-existent session."""
    # Should return early without error
    pause_time_tracking(identifier="non-existent")


def test_pause_time_tracking_no_work_sessions(temp_daf_home):
    """Test pause command when session has no work sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="no-work",
        goal="No work yet",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )
    session.time_tracking_state = "running"
    session_manager.update_session(session)

    # Should still update state even without work sessions
    pause_time_tracking(identifier="no-work")


# Resume command tests


def test_resume_time_tracking_no_active_sessions(temp_daf_home):
    """Test resume command with no active sessions."""
    # Should display "No active sessions" and return without error
    resume_time_tracking()


def test_resume_time_tracking_with_identifier(temp_daf_home):
    """Test resume command for a specific session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )
    session.time_tracking_state = "paused"
    session_manager.update_session(session)

    # Should resume successfully
    resume_time_tracking(identifier="test-session")


def test_resume_time_tracking_already_running(temp_daf_home):
    """Test resume command when time tracking is already running."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="running-session",
        goal="Already running",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )
    session.time_tracking_state = "running"
    session_manager.update_session(session)

    # Should display warning that time tracking is already running
    resume_time_tracking(identifier="running-session")


def test_resume_time_tracking_latest_flag(temp_daf_home):
    """Test resume command with --latest flag."""
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
    session.time_tracking_state = "paused"
    session_manager.update_session(session)

    # Should resume successfully
    resume_time_tracking(latest=True)


def test_resume_time_tracking_with_jira_key_display(temp_daf_home):
    """Test resume command displays JIRA key when present."""
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
    session.time_tracking_state = "paused"
    session_manager.update_session(session)

    # Should display JIRA key in output
    resume_time_tracking(identifier="jira-session")


def test_resume_time_tracking_nonexistent_session(temp_daf_home):
    """Test resume command with non-existent session."""
    # Should return early without error
    resume_time_tracking(identifier="non-existent")


def test_pause_resume_cycle(temp_daf_home):
    """Test pausing and then resuming a session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="cycle-test",
        goal="Test pause/resume cycle",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )
    session.time_tracking_state = "running"
    session.work_sessions = [WorkSession(user="testuser", start=datetime.now(), end=None)]
    session_manager.update_session(session)

    # Pause then resume - should execute without error
    pause_time_tracking(identifier="cycle-test")
    resume_time_tracking(identifier="cycle-test")


def test_resume_time_tracking_appends_new_work_session(temp_daf_home):
    """Test resume command creates a new work session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="append-test",
        goal="Test work session append",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    # Add completed work sessions
    start = datetime.now() - timedelta(hours=3)
    end = start + timedelta(hours=2)
    session.work_sessions = [
        WorkSession(user="alice", start=start, end=end),
    ]
    session.time_tracking_state = "paused"
    session_manager.update_session(session)

    # Should append a new work session
    resume_time_tracking(identifier="append-test")

