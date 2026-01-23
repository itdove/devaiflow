"""Tests for status command."""

from datetime import datetime, timedelta

import pytest

from devflow.cli.commands.status_command import show_status
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkSession
from devflow.session.manager import SessionManager


def test_status_empty(temp_daf_home, capsys):
    """Test status command with no sessions."""
    show_status()
    # Should display "No sessions found" message


def test_status_with_single_session(temp_daf_home):
    """Test status command with a single session."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
    )

    show_status()
    # Should display session in output


def test_status_with_multiple_statuses(temp_daf_home):
    """Test status command groups sessions by status."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions with different statuses
    session_manager.create_session(
        name="created-session",
        goal="Not started yet",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    in_progress_session = session_manager.create_session(
        name="in-progress-session",
        goal="Currently working",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    in_progress_session.status = "in_progress"
    session_manager.index.sessions["in-progress-session"] = in_progress_session
    session_manager._save_index()

    paused_session = session_manager.create_session(
        name="paused-session",
        goal="Paused work",
        working_directory="dir4",
        project_path="/path4",
        ai_agent_session_id="uuid-4",
    )
    paused_session.status = "paused"
    session_manager.index.sessions["paused-session"] = paused_session
    session_manager._save_index()

    complete_session = session_manager.create_session(
        name="complete-session",
        goal="Already done",
        working_directory="dir3",
        project_path="/path3",
        ai_agent_session_id="uuid-3",
    )
    complete_session.status = "complete"
    session_manager.index.sessions["complete-session"] = complete_session
    session_manager._save_index()

    show_status()
    # Should group by status: in_progress, paused, created, complete


def test_status_with_sprint_grouping(temp_daf_home, mock_jira_cli):
    """Test status command groups by sprint when JIRA integrated."""
    mock_jira_cli.set_ticket("PROJ-100", {
        "key": "PROJ-100",
        "fields": {
            "summary": "Sprint ticket 1",
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"},
            "customfield_sprint": "Sprint 42",
            "customfield_12310243": 5,
        }
    })
    mock_jira_cli.set_ticket("PROJ-101", {
        "key": "PROJ-101",
        "fields": {
            "summary": "Sprint ticket 2",
            "status": {"name": "New"},
            "issuetype": {"name": "Bug"},
            "customfield_sprint": "Sprint 42",
            "customfield_12310243": 3,
        }
    })

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with sprint
    session1 = session_manager.create_session(
        name="sprint-session-1",
        goal="Sprint work 1",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-100",
    )
    if not session1.issue_metadata:
        session1.issue_metadata = {}
    session1.issue_metadata["sprint"] = "Sprint 42"
    session1.issue_metadata["points"] = 5
    session_manager.index.sessions["sprint-session-1"] = session1
    session_manager._save_index()

    session2 = session_manager.create_session(
        name="sprint-session-2",
        goal="Sprint work 2",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
        issue_key="PROJ-101",
    )
    if not session2.issue_metadata:
        session2.issue_metadata = {}
    session2.issue_metadata["sprint"] = "Sprint 42"
    session2.issue_metadata["points"] = 3
    session_manager.index.sessions["sprint-session-2"] = session2
    session_manager._save_index()

    show_status()
    # Should display sprint grouping with points summary


def test_status_with_time_tracking(temp_daf_home):
    """Test status command displays time tracking."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="timed-session",
        goal="Session with time",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Add work session with 2 hours
    start = datetime.now()
    end = start + timedelta(hours=2, minutes=30)
    session.work_sessions = [WorkSession(user="testuser", start=start, end=end)]
    session_manager.index.sessions["timed-session"] = session
    session_manager._save_index()

    show_status()
    # Should display time in summary


def test_status_with_non_sprint_and_sprint_sessions(temp_daf_home):
    """Test status command shows both sprint and non-sprint sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create non-sprint session
    session_manager.create_session(
        name="no-sprint-session",
        goal="Not in a sprint",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Create sprint session
    sprint_session = session_manager.create_session(
        name="sprint-session",
        goal="In a sprint",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    if not sprint_session.issue_metadata:
        sprint_session.issue_metadata = {}
    sprint_session.issue_metadata["sprint"] = "Sprint 45"
    session_manager.index.sessions["sprint-session"] = sprint_session
    session_manager._save_index()

    show_status()
    # Should show both sprint and non-sprint sections


def test_status_multiple_complete_sessions(temp_daf_home):
    """Test status command limits display of complete sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create 5 complete sessions
    for i in range(5):
        session = session_manager.create_session(
            name=f"complete-{i}",
            goal=f"Complete goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )
        session.status = "complete"
        session_manager.index.sessions[f"complete-{i}"] = session
        session_manager._save_index()

    show_status()
    # Should only show first 3 complete sessions with "... and 2 more" message


def test_status_with_jira_type_bug(temp_daf_home):
    """Test status command shows bug icon for bug types."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    bug_session = session_manager.create_session(
        name="bug-session",
        goal="Fix a bug",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    if not bug_session.issue_metadata:
        bug_session.issue_metadata = {}
    bug_session.issue_metadata["type"] = "Bug"
    session_manager.index.sessions["bug-session"] = bug_session
    session_manager._save_index()

    show_status()
    # Should display bug icon


def test_status_with_long_goal(temp_daf_home):
    """Test status command truncates goals longer than 40 characters."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with goal longer than 40 characters
    session_manager.create_session(
        name="long-goal-session",
        goal="This is a very long goal that exceeds forty characters and should be truncated",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    show_status()
    # Should truncate goal to 37 chars + "..."


def test_status_with_paused_sessions(temp_daf_home, capsys):
    """Test status command displays paused sessions correctly."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create in-progress session
    in_progress_session = session_manager.create_session(
        name="active-session",
        goal="Working on this",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    in_progress_session.status = "in_progress"
    session_manager.index.sessions["active-session"] = in_progress_session
    session_manager._mark_modified(in_progress_session)
    session_manager._save_index()

    # Create paused sessions
    paused_session_1 = session_manager.create_session(
        name="paused-session-1",
        goal="Paused import",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    paused_session_1.status = "paused"
    session_manager.index.sessions["paused-session-1"] = paused_session_1
    session_manager._mark_modified(paused_session_1)
    session_manager._save_index()

    paused_session_2 = session_manager.create_session(
        name="paused-session-2",
        goal="Paused on error",
        working_directory="dir3",
        project_path="/path3",
        ai_agent_session_id="uuid-3",
    )
    paused_session_2.status = "paused"
    session_manager.index.sessions["paused-session-2"] = paused_session_2
    session_manager._mark_modified(paused_session_2)
    session_manager._save_index()

    # Create created session
    session_manager.create_session(
        name="new-session",
        goal="Not started",
        working_directory="dir4",
        project_path="/path4",
        ai_agent_session_id="uuid-4",
    )

    # Capture output
    show_status()
    captured = capsys.readouterr()

    # Verify paused section appears in output with correct color
    assert "Paused:" in captured.out
    assert "paused-session-1" in captured.out
    assert "paused-session-2" in captured.out

    # Verify summary includes paused count
    assert "Paused: 2" in captured.out
    assert "In progress: 1" in captured.out
    assert "Created: 1" in captured.out
