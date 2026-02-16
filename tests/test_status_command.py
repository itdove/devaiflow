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


def test_status_json_output_empty(temp_daf_home, capsys):
    """Test JSON output with no sessions."""
    import json

    show_status(output_json=True)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["success"] is True
    assert output["data"]["sessions"] == []
    assert output["data"]["groups"] == {}
    assert output["data"]["summary"]["total_sessions"] == 0


def test_status_json_output_with_sessions(temp_daf_home, capsys):
    """Test JSON output with sessions."""
    import json

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session1 = session_manager.create_session(
        name="test-session",
        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-123",
    )

    session2 = session_manager.create_session(
        name="test-session-2",
        goal="Test goal 2",
        working_directory="test-dir-2",
        project_path="/path/to/project2",
        ai_agent_session_id="uuid-2",
    )
    session2.status = "in_progress"
    session_manager.index.sessions["test-session-2"] = session2
    session_manager._mark_modified(session2)
    session_manager._save_index()

    show_status(output_json=True)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["success"] is True
    assert output["data"]["summary"]["total_sessions"] == 2
    assert output["data"]["summary"]["in_progress"] == 1
    assert output["data"]["summary"]["created"] == 1


def test_status_json_output_with_grouping(temp_daf_home, capsys):
    """Test JSON output with sprint grouping."""
    import json

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create organization config with grouping field
    org_config_path = temp_daf_home / "organization.json"
    org_data = {
        "jira_project": "TEST",
        "status_grouping_field": "sprint",
        "status_totals_field": "points",
        "sync_filters": {}
    }
    with open(org_config_path, "w") as f:
        json.dump(org_data, f)

    # Create session with sprint
    session1 = session_manager.create_session(
        name="sprint-session",
        goal="Sprint work",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    if not session1.issue_metadata:
        session1.issue_metadata = {}
    session1.issue_metadata["sprint"] = "Sprint 42"
    session1.issue_metadata["points"] = 5
    session1.status = "in_progress"
    session_manager.update_session(session1)

    session2 = session_manager.create_session(
        name="sprint-session-2",
        goal="Sprint work 2",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    if not session2.issue_metadata:
        session2.issue_metadata = {}
    session2.issue_metadata["sprint"] = "Sprint 42"
    session2.issue_metadata["points"] = 3
    session_manager.update_session(session2)

    show_status(output_json=True)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["success"] is True
    assert output["data"]["grouping_field"] == "sprint"
    assert output["data"]["totals_field"] == "points"
    assert "Sprint 42" in output["data"]["groups"]
    assert output["data"]["groups"]["Sprint 42"]["total"] == 8
    assert output["data"]["groups"]["Sprint 42"]["in_progress"] == 5


def test_status_json_output_with_active_conversation(temp_daf_home, monkeypatch, capsys):
    """Test JSON output includes active conversation."""
    import json
    import os

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="active-session",
        goal="Active work",
        working_directory="active-dir",
        project_path="/path/to/active",
        ai_agent_session_id="active-uuid",
        issue_key="PROJ-456",
    )

    # Set environment to indicate active conversation
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "active-uuid")
    monkeypatch.setenv("PWD", "/path/to/active")

    show_status(output_json=True)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["success"] is True
    assert output["data"]["active_conversation"] is not None
    assert output["data"]["active_conversation"]["session_name"] == "active-session"
    assert output["data"]["active_conversation"]["issue_key"] == "PROJ-456"
    assert output["data"]["active_conversation"]["working_directory"] == "active-dir"


def test_status_json_output_with_ungrouped_sessions(temp_daf_home, capsys):
    """Test JSON output with ungrouped sessions."""
    import json

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create organization config with grouping field
    org_config_path = temp_daf_home / "organization.json"
    org_data = {
        "jira_project": "TEST",
        "status_grouping_field": "sprint",
        "sync_filters": {}
    }
    with open(org_config_path, "w") as f:
        json.dump(org_data, f)

    # Create session without sprint
    session = session_manager.create_session(
        name="ungrouped-session",
        goal="No sprint",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    show_status(output_json=True)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["success"] is True
    assert len(output["data"]["ungrouped_sessions"]) == 1
    assert output["data"]["ungrouped_sessions"][0]["name"] == "ungrouped-session"


def test_status_console_output_with_active_conversation(temp_daf_home, monkeypatch, capsys):
    """Test console output includes active conversation panel."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="active-session",
        goal="Active work",
        working_directory="active-dir",
        project_path="/path/to/active",
        ai_agent_session_id="active-uuid",
        issue_key="PROJ-789",
    )

    # Set environment to indicate active conversation
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "active-uuid")
    monkeypatch.setenv("PWD", "/path/to/active")

    show_status(output_json=False)

    captured = capsys.readouterr()

    assert "Currently Active" in captured.out
    assert "active-session" in captured.out
    assert "PROJ-789" in captured.out
    assert "Active work" in captured.out


def test_status_console_output_with_running_time_tracking(temp_daf_home, monkeypatch, capsys):
    """Test console output with running time tracking."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="active-session",
        goal="Active work",
        working_directory="active-dir",
        project_path="/path/to/active",
        ai_agent_session_id="active-uuid",
    )

    # Add running work session
    start = datetime.now() - timedelta(hours=1, minutes=30)
    session.work_sessions = [WorkSession(user="testuser", start=start, end=None)]
    session.time_tracking_state = "running"
    session_manager.index.sessions["active-session"] = session
    session_manager._save_index()

    # Set environment to indicate active conversation
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "active-uuid")
    monkeypatch.setenv("PWD", "/path/to/active")

    show_status(output_json=False)

    captured = capsys.readouterr()

    assert "Currently Active" in captured.out
    assert "Time (this session):" in captured.out


def test_status_console_output_with_grouping_and_totals(temp_daf_home, capsys):
    """Test console output with grouping and totals display."""
    import json

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create organization config with grouping and totals fields
    org_config_path = temp_daf_home / "organization.json"
    org_data = {
        "jira_project": "TEST",
        "status_grouping_field": "sprint",
        "status_totals_field": "points",
        "sync_filters": {}
    }
    with open(org_config_path, "w") as f:
        json.dump(org_data, f)

    # Create session with sprint and points
    session = session_manager.create_session(
        name="sprint-session",
        goal="Sprint work",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["sprint"] = "Sprint 42"
    session.issue_metadata["points"] = 5
    session.status = "in_progress"
    session_manager.update_session(session)

    show_status(output_json=False)

    captured = capsys.readouterr()

    assert "Sprint: Sprint 42" in captured.out
    assert "Progress:" in captured.out
    assert "5 pts" in captured.out


def test_status_console_output_ungrouped_with_grouping_field(temp_daf_home, capsys):
    """Test console output shows 'No Sprint Sessions' header when grouping configured."""
    import json

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create organization config with grouping field
    org_config_path = temp_daf_home / "organization.json"
    org_data = {
        "jira_project": "TEST",
        "status_grouping_field": "sprint",
        "sync_filters": {}
    }
    with open(org_config_path, "w") as f:
        json.dump(org_data, f)

    # Create session without sprint
    session = session_manager.create_session(
        name="ungrouped-session",
        goal="No sprint",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    show_status(output_json=False)

    captured = capsys.readouterr()

    assert "No Sprint Sessions" in captured.out


def test_status_console_output_ungrouped_without_grouping_field(temp_daf_home, capsys):
    """Test console output shows 'All Sessions' header when no grouping configured."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session
    session = session_manager.create_session(
        name="session",
        goal="Work",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    show_status(output_json=False)

    captured = capsys.readouterr()

    assert "All Sessions" in captured.out


def test_status_session_with_issue_key(temp_daf_home, capsys):
    """Test status displays issue key in session summary."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="jira-session",
        goal="JIRA work",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    show_status(output_json=False)

    captured = capsys.readouterr()

    assert "PROJ-12345" in captured.out


def test_status_session_with_custom_totals_field(temp_daf_home, capsys):
    """Test status displays custom totals field (not just points)."""
    import json

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create organization config with custom totals field
    org_config_path = temp_daf_home / "organization.json"
    org_data = {
        "jira_project": "TEST",
        "status_grouping_field": "release",
        "status_totals_field": "effort_hours",
        "sync_filters": {}
    }
    with open(org_config_path, "w") as f:
        json.dump(org_data, f)

    # Create session with release and effort_hours
    session = session_manager.create_session(
        name="release-session",
        goal="Release work",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["release"] = "Release 1.0"
    session.issue_metadata["effort_hours"] = 8
    session_manager.update_session(session)

    show_status(output_json=False)

    captured = capsys.readouterr()

    assert "Release: Release 1.0" in captured.out
    assert "8 effort hours" in captured.out
