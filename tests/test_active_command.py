"""Tests for daf active command."""

import json
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from io import StringIO

from devflow.cli.commands.active_command import (
    show_active,
    _get_recent_conversations_data,
    _show_recent_conversations
)
from devflow.config.models import Session, ConversationContext, WorkSession
from devflow.session.manager import SessionManager


def test_show_active_with_no_active_conversation(monkeypatch, temp_daf_home):
    """Test show_active when no active conversation is found."""
    with patch('devflow.cli.commands.active_command.get_active_conversation', return_value=None):
        with patch('devflow.cli.commands.active_command.console') as mock_console:
            with patch('devflow.cli.commands.active_command._show_recent_conversations'):
                show_active(output_json=False)

                # Verify message printed
                mock_console.print.assert_called()


def test_show_active_with_no_active_conversation_json(monkeypatch, temp_daf_home, capsys):
    """Test show_active JSON output when no active conversation."""
    with patch('devflow.cli.commands.active_command.get_active_conversation', return_value=None):
        with patch('devflow.cli.commands.active_command._get_recent_conversations_data', return_value=[]):
            show_active(output_json=True)

            # Capture and verify JSON output
            captured = capsys.readouterr()
            output = json.loads(captured.out)

            assert output["success"] is True
            assert output["data"]["active_conversation"] is None
            assert "recent_conversations" in output["data"]


def test_show_active_with_active_conversation_json(monkeypatch, temp_daf_home, capsys):
    """Test show_active with an active conversation (JSON output)."""
    # Create mock session
    session = Session(
        name="test-session",
        issue_key="PROJ-123",
        goal="Test goal",
        working_directory="project1",
        status="in_progress",
        created=datetime.now() - timedelta(hours=1),
        last_active=datetime.now()
    )

    session.add_conversation(
        working_dir="project1",
        ai_agent_session_id="test-uuid-1234",
        project_path="/path/to/project1",
        branch="feature-branch"
    )

    with patch('devflow.cli.commands.active_command.get_active_conversation',
               return_value=(session, session.active_conversation, "project1")):
        with patch('devflow.cli.commands.active_command.SessionManager') as mock_sm_class:
            with patch('devflow.cli.commands.active_command.ConfigLoader') as mock_loader_class:
                # Mock the config loader instance
                mock_loader = MagicMock()
                mock_loader.config = None
                mock_loader_class.return_value = mock_loader

                # Mock SessionManager - not actually used since we mock get_active_conversation
                mock_sm_class.return_value = MagicMock()

                show_active(output_json=True)

                # Capture and verify JSON output
                captured = capsys.readouterr()
                output = json.loads(captured.out)

                assert output["success"] is True
                assert output["data"]["active_conversation"]["session_name"] == "test-session"
                assert output["data"]["active_conversation"]["issue_key"] == "PROJ-123"
                assert output["data"]["active_conversation"]["working_directory"] == "project1"
                assert output["data"]["active_conversation"]["branch"] == "feature-branch"
                assert output["data"]["active_conversation"]["status"] == "in_progress"


def test_show_active_with_time_tracking(monkeypatch, temp_daf_home, capsys):
    """Test show_active displays current work session time."""
    session = Session(
        name="test-session",
        issue_key="PROJ-123",
        goal="Test goal",
        working_directory="project1",
        status="in_progress",
        created=datetime.now() - timedelta(hours=1),
        last_active=datetime.now()
    )

    session.add_conversation(
        working_dir="project1",
        ai_agent_session_id="test-uuid-1234",
        project_path="/path/to/project1",
        branch="feature-branch"
    )

    # Add work session with time tracking
    work_session = WorkSession(
        start=datetime.now() - timedelta(hours=2, minutes=30),
        end=None,  # Still running
        user="testuser"
    )
    session.work_sessions.append(work_session)
    session.time_tracking_state = "running"

    with patch('devflow.cli.commands.active_command.get_active_conversation',
               return_value=(session, session.active_conversation, "project1")):
        with patch('devflow.cli.commands.active_command.SessionManager') as mock_sm_class:
            with patch('devflow.cli.commands.active_command.ConfigLoader') as mock_loader_class:
                mock_loader = MagicMock()
                mock_loader.config = None
                mock_loader_class.return_value = mock_loader

                # Mock SessionManager
                mock_sm_class.return_value = MagicMock()

                show_active(output_json=True)

                # Capture and verify JSON output includes time tracking
                captured = capsys.readouterr()
                output = json.loads(captured.out)

                assert output["success"] is True
                data = output["data"]["active_conversation"]
                assert "current_work_time_seconds" in data
                assert "current_work_time_hours" in data
                assert "current_work_time_minutes" in data
                assert data["time_tracking_state"] == "running"

                # Verify time is approximately 2h 30m (150 minutes)
                assert data["current_work_time_hours"] >= 2
                assert data["current_work_time_minutes"] >= 20  # Account for test execution time


def test_get_recent_conversations_data_empty(monkeypatch, temp_daf_home):
    """Test _get_recent_conversations_data with no sessions."""
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    recent = _get_recent_conversations_data(session_manager)

    assert recent == []


def test_show_recent_conversations_empty(monkeypatch, temp_daf_home):
    """Test _show_recent_conversations with no sessions."""
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    with patch('devflow.cli.commands.active_command.console') as mock_console:
        _show_recent_conversations(session_manager)

        # Verify appropriate message displayed
        assert mock_console.print.called


def test_show_active_with_multi_project_session(monkeypatch, temp_daf_home):
    """Test show_active with a multi-project session (other conversations)."""
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Conversation, ConversationContext
    import os

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a session
    session = session_manager.create_session(
        name="multi-session",
        goal="Multi-project work",
        working_directory="project1",
        project_path="/path/to/project1",
        ai_agent_session_id="uuid-proj1",
    )

    # Add a second conversation
    conv2 = Conversation(
        active_session=ConversationContext(
            ai_agent_session_id="uuid-proj2",
            project_path="/path/to/project2",
            branch="develop",
            base_branch="main",
            created=datetime.now(),
            last_active=datetime.now(),
            message_count=5,
            prs=[],
            archived=False,
            conversation_history=["uuid-proj2"],
        ),
        archived_sessions=[],
    )
    session.conversations["project2"] = conv2
    session_manager.update_session(session)

    # Set active conversation via environment variable
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "uuid-proj1")
    monkeypatch.setenv("PWD", "/path/to/project1")

    # Call show_active
    show_active(output_json=False)
    # Should display without error and show other conversations


def test_show_active_json_with_other_conversations(monkeypatch, temp_daf_home, capsys):
    """Test show_active JSON output with other conversations."""
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Conversation, ConversationContext
    import json

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a multi-project session
    session = session_manager.create_session(
        name="multi-session",
        goal="Multi-project work",
        working_directory="project1",
        project_path="/path/to/project1",
        ai_agent_session_id="uuid-proj1",
    )

    # Add second conversation
    conv2 = Conversation(
        active_session=ConversationContext(
            ai_agent_session_id="uuid-proj2",
            project_path="/path/to/project2",
            branch="feature-x",
            base_branch="main",
            created=datetime.now(),
            last_active=datetime.now(),
            message_count=3,
            prs=[],
            archived=False,
            conversation_history=["uuid-proj2"],
        ),
        archived_sessions=[],
    )
    session.conversations["project2"] = conv2
    session_manager.update_session(session)

    # Set active conversation
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "uuid-proj1")
    monkeypatch.setenv("PWD", "/path/to/project1")

    # Call with JSON output
    show_active(output_json=True)

    output = capsys.readouterr().out
    result = json.loads(output)

    # Should include other_conversations
    assert result["success"] is True
    assert "other_conversations" in result["data"]["active_conversation"]
    assert len(result["data"]["active_conversation"]["other_conversations"]) == 1


def test_show_recent_conversations_with_multiple_sessions(temp_daf_home):
    """Test _show_recent_conversations with multiple sessions."""
    from devflow.config.loader import ConfigLoader
    from datetime import timedelta

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions with different last_active times
    for i, hours_ago in enumerate([1, 5, 25]):
        session = session_manager.create_session(
            name=f"session-{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )
        # Modify last_active time
        if "dir{i}" in session.conversations:
            session.conversations[f"dir{i}"].active_session.last_active = datetime.now() - timedelta(hours=hours_ago)
            session_manager.update_session(session)

    # Call _show_recent_conversations
    with patch('devflow.cli.commands.active_command.console') as mock_console:
        _show_recent_conversations(session_manager)

        # Should display recent conversations
        assert mock_console.print.called


def test_show_recent_conversations_time_formats(temp_daf_home):
    """Test _show_recent_conversations displays different time formats."""
    from devflow.config.loader import ConfigLoader
    from datetime import timedelta

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions with different time ranges
    # 1. Just now (< 1 minute)
    session1 = session_manager.create_session(
        name="recent",
        goal="Recent",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # 2. Minutes ago
    session2 = session_manager.create_session(
        name="minutes-ago",
        goal="Minutes",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )
    if "dir2" in session2.conversations:
        session2.conversations["dir2"].active_session.last_active = datetime.now() - timedelta(minutes=30)
        session_manager.update_session(session2)

    # 3. Hours ago
    session3 = session_manager.create_session(
        name="hours-ago",
        goal="Hours",
        working_directory="dir3",
        project_path="/path3",
        ai_agent_session_id="uuid-3",
    )
    if "dir3" in session3.conversations:
        session3.conversations["dir3"].active_session.last_active = datetime.now() - timedelta(hours=2)
        session_manager.update_session(session3)

    # Call _show_recent_conversations
    _show_recent_conversations(session_manager)
    # Should display with different time formats (just now, Xm ago, Xh ago)


def test_get_recent_conversations_data_with_sessions(temp_daf_home):
    """Test _get_recent_conversations_data with multiple sessions."""
    from devflow.config.loader import ConfigLoader
    from datetime import timedelta

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions
    for i in range(3):
        session = session_manager.create_session(
            name=f"session-{i}",
            goal=f"Goal {i}",
            working_directory=f"dir{i}",
            project_path=f"/path{i}",
            ai_agent_session_id=f"uuid-{i}",
        )
        session.issue_key = f"PROJ-{i}"
        session_manager.update_session(session)

    # Get recent conversations data
    result = _get_recent_conversations_data(session_manager)

    # Should return list of conversations
    assert isinstance(result, list)
    assert len(result) > 0
    # Each item should have required fields
    for conv in result:
        assert "session_name" in conv
        assert "working_directory" in conv
        assert "branch" in conv
        assert "last_active" in conv
        assert "seconds_ago" in conv


def test_show_active_with_issue_key(monkeypatch, temp_daf_home):
    """Test show_active displays issue key when present."""
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create session with issue key
    session = session_manager.create_session(
        name="jira-session",
        goal="JIRA work",
        working_directory="project",
        project_path="/path/to/project",
        ai_agent_session_id="uuid-active",
    )
    session.issue_key = "PROJ-12345"
    session_manager.update_session(session)

    # Set active
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "uuid-active")
    monkeypatch.setenv("PWD", "/path/to/project")

    # Call show_active
    show_active(output_json=False)
    # Should display issue key in output


def test_show_active_with_multi_project_conversation(monkeypatch, temp_daf_home, tmp_path):
    """Test show_active with a true multi-project conversation (not just multiple conversations)."""
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Conversation, ConversationContext, ProjectInfo

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multi-project conversation context with is_multi_project=True
    conversation_context = ConversationContext(
        ai_agent_session_id="uuid-multi-proj",
        project_path=str(tmp_path / "backend"),  # This should not be used
        branch="feature-branch",
        base_branch="main",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=10,
        prs=[],
        archived=False,
        conversation_history=["uuid-multi-proj"],
        is_multi_project=True,
        workspace_path=str(tmp_path),
        projects={
            "backend": ProjectInfo(
                project_path=str(tmp_path / "backend"),
                relative_path="backend",
                branch="feature-branch",
                base_branch="main",
                repo_name="backend",
            ),
            "frontend": ProjectInfo(
                project_path=str(tmp_path / "frontend"),
                relative_path="frontend",
                branch="feature-branch",
                base_branch="main",
                repo_name="frontend",
            ),
        }
    )

    # Create conversation container
    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )

    # Create session with multi-project conversation
    session = session_manager.create_session(
        name="multi-project-test",
        goal="Multi-project development",
        working_directory="backend",
        project_path=str(tmp_path / "backend"),
        branch="feature-branch",
        ai_agent_session_id="uuid-multi-proj",
    )

    # Replace the default conversation with our multi-project one
    session.conversations["backend"] = conversation
    session_manager.update_session(session)

    # Set active conversation
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "uuid-multi-proj")
    monkeypatch.setenv("PWD", str(tmp_path / "backend"))

    # Call show_active - should not raise ValueError
    show_active(output_json=False)
    # Should display multi-project information without error


def test_show_active_multi_project_json_output(monkeypatch, temp_daf_home, tmp_path, capsys):
    """Test show_active JSON output for multi-project conversation."""
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Conversation, ConversationContext, ProjectInfo
    import json

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create multi-project conversation context
    conversation_context = ConversationContext(
        ai_agent_session_id="uuid-multi-json",
        project_path=str(tmp_path / "backend"),
        branch="develop",
        base_branch="main",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=5,
        prs=[],
        archived=False,
        conversation_history=["uuid-multi-json"],
        is_multi_project=True,
        workspace_path=str(tmp_path),
        projects={
            "backend-api": ProjectInfo(
                project_path=str(tmp_path / "backend-api"),
                relative_path="backend-api",
                branch="develop",
                base_branch="main",
                repo_name="backend-api",
            ),
            "frontend-ui": ProjectInfo(
                project_path=str(tmp_path / "frontend-ui"),
                relative_path="frontend-ui",
                branch="develop",
                base_branch="main",
                repo_name="frontend-ui",
            ),
        }
    )

    conversation = Conversation(
        active_session=conversation_context,
        archived_sessions=[]
    )

    # Create session
    session = session_manager.create_session(
        name="multi-json-test",
        goal="Test multi-project JSON",
        working_directory="backend-api",
        project_path=str(tmp_path / "backend-api"),
        branch="develop",
        ai_agent_session_id="uuid-multi-json",
    )

    session.conversations["backend-api"] = conversation
    session_manager.update_session(session)

    # Set active
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "uuid-multi-json")
    monkeypatch.setenv("PWD", str(tmp_path / "backend-api"))

    # Call with JSON output
    show_active(output_json=True)

    output = capsys.readouterr().out
    result = json.loads(output)

    # Verify JSON structure
    assert result["success"] is True
    active = result["data"]["active_conversation"]

    # Should have multi-project fields
    assert active["is_multi_project"] is True
    assert active["workspace_path"] == str(tmp_path)
    assert "projects" in active
    assert len(active["projects"]) == 2

    # Verify project details
    project_names = {p["name"] for p in active["projects"]}
    assert "backend-api" in project_names
    assert "frontend-ui" in project_names

    # Verify each project has required fields
    for project in active["projects"]:
        assert "name" in project
        assert "path" in project
        assert "branch" in project
        assert project["branch"] == "develop"

    # Should NOT have single-project fields
    assert "branch" not in active or active.get("branch") is None
    assert "project_path" not in active or active.get("project_path") is None
