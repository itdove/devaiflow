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
