"""Extended tests for CLI utility functions."""

from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from devflow.cli.utils import (
    add_jira_comment,
    display_session_header,
    get_session_with_delete_all_option,
)
from devflow.config.loader import ConfigLoader
from devflow.config.models import Session, WorkSession
from devflow.jira.exceptions import JiraApiError
from devflow.session.manager import SessionManager


def test_display_session_header_basic(capsys):
    """Test displaying session header with basic info."""
    session = Session(
        name="test-session",        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=10,
        ai_agent_session_id="test-uuid",
    )

    display_session_header(session)

    # Capture console output isn't straightforward with rich, so we just verify it runs without error
    # The function uses rich.Console which writes to stderr by default


def test_display_session_header_with_jira(capsys):
    """Test displaying session header with issue key."""
    session = Session(
        name="test-session",        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=5,
        issue_key="PROJ-12345",
    )

    display_session_header(session)
    # Function should include issue key in output


def test_display_session_header_with_branch(capsys):
    """Test displaying session header with git branch."""
    session = Session(
        name="test-session",        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=3,
        branch="feature/test-branch",
    )

    display_session_header(session)
    # Function should include branch in output


def test_display_session_header_with_time_single_user(capsys):
    """Test displaying session header with time tracking (single user)."""
    session = Session(
        name="test-session",        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=15,
    )

    # Add work sessions (2 hours 30 minutes total)
    start = datetime.now()
    end = start + timedelta(hours=2, minutes=30)
    session.work_sessions = [
        WorkSession(
            user="testuser",
            start=start,
            end=end,
        )
    ]

    display_session_header(session)
    # Function should display "2h 30m" for single user


def test_display_session_header_with_time_multiple_users(capsys):
    """Test displaying session header with time tracking (multiple users)."""
    session = Session(
        name="test-session",        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        status="in_progress",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=20,
    )

    # Add work sessions from two users
    start = datetime.now()
    session.work_sessions = [
        WorkSession(
            user="alice",
            start=start,
            end=start + timedelta(hours=2),
        ),
        WorkSession(
            user="bob",
            start=start,
            end=start + timedelta(hours=1),
        ),
    ]

    display_session_header(session)
    # Function should display total time and breakdown by user


def test_display_session_header_no_time(capsys):
    """Test displaying session header with no time tracking."""
    session = Session(
        name="test-session",        goal="Test goal",
        working_directory="test-dir",
        project_path="/path/to/project",
        status="created",
        created=datetime.now(),
        last_active=datetime.now(),
        message_count=0,
    )

    display_session_header(session)
    # Function should not display time when total is 0


def test_get_session_with_delete_all_option_single_session(temp_daf_home):
    """Test get_session_with_delete_all_option with single session returns it directly."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="single",
        goal="Single session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    result, delete_all = get_session_with_delete_all_option(session_manager, "single")

    assert result is not None
    assert result.name == "single"
    assert delete_all is False


def test_get_session_with_delete_all_option_not_found(temp_daf_home):
    """Test get_session_with_delete_all_option when no sessions exist."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    result, delete_all = get_session_with_delete_all_option(
        session_manager, "nonexistent"
    )

    assert result is None
    assert delete_all is False


@patch("devflow.cli.utils.IntPrompt.ask")
def test_get_session_with_delete_all_option_select_specific(
    mock_ask, temp_daf_home
):
    """Test that creating duplicate session names raises ValueError.

    Session groups have been removed - each session must have a unique name.
    """
    import pytest

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session
    session_manager.create_session(
        name="multi",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    with pytest.raises(ValueError, match="Session 'multi' already exists"):
        session_manager.create_session(
            name="multi",
            goal="Second",
            working_directory="dir2",
            project_path="/path2",
            ai_agent_session_id="uuid-2",
        )


@patch("devflow.cli.utils.IntPrompt.ask")
def test_get_session_with_delete_all_option_delete_all(mock_ask, temp_daf_home):
    """Test that creating duplicate session names raises ValueError.

    Session groups have been removed - each session must have a unique name.
    """
    import pytest

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session
    session_manager.create_session(
        name="multi",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    with pytest.raises(ValueError, match="Session 'multi' already exists"):
        session_manager.create_session(
            name="multi",
            goal="Second",
            working_directory="dir2",
            project_path="/path2",
            ai_agent_session_id="uuid-2",
        )


@patch("devflow.cli.utils.IntPrompt.ask")
def test_get_session_with_delete_all_option_invalid_choice(mock_ask, temp_daf_home):
    """Test that creating duplicate session names raises ValueError.

    Session groups have been removed - each session must have a unique name.
    """
    import pytest

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create first session
    session_manager.create_session(
        name="multi",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    with pytest.raises(ValueError, match="Session 'multi' already exists"):
        session_manager.create_session(
            name="multi",
            goal="Second",
            working_directory="dir2",
            project_path="/path2",
            ai_agent_session_id="uuid-2",
        )


@patch("devflow.cli.utils.JiraClient")
def test_add_jira_comment_success(mock_jira_class):
    """Test adding JIRA comment successfully."""
    mock_client = MagicMock()
    # add_comment now returns None on success
    mock_client.add_comment.return_value = None
    mock_jira_class.return_value = mock_client

    result = add_jira_comment("PROJ-12345", "Test comment")

    assert result is True
    mock_client.add_comment.assert_called_once_with("PROJ-12345", "Test comment")


@patch("devflow.cli.utils.JiraClient")
def test_add_jira_comment_success_silent(mock_jira_class):
    """Test adding JIRA comment with silent_success flag."""
    mock_client = MagicMock()
    # add_comment now returns None on success
    mock_client.add_comment.return_value = None
    mock_jira_class.return_value = mock_client

    result = add_jira_comment("PROJ-12345", "Test comment", silent_success=True)

    assert result is True


@patch("devflow.cli.utils.JiraClient")
def test_add_jira_comment_failure(mock_jira_class):
    """Test JIRA comment addition failure."""
    mock_client = MagicMock()
    # add_comment now raises exception on failure
    mock_client.add_comment.side_effect = JiraApiError("Failed to add comment", status_code=400)
    mock_jira_class.return_value = mock_client

    result = add_jira_comment("PROJ-12345", "Test comment")

    assert result is False


@patch("devflow.cli.utils.JiraClient")
def test_add_jira_comment_file_not_found(mock_jira_class):
    """Test JIRA comment when CLI is not installed."""
    mock_jira_class.side_effect = FileNotFoundError("jira CLI not found")

    result = add_jira_comment("PROJ-12345", "Test comment")

    assert result is False


@patch("devflow.cli.utils.JiraClient")
def test_add_jira_comment_exception(mock_jira_class):
    """Test JIRA comment with general exception."""
    mock_jira_class.side_effect = Exception("Network error")

    result = add_jira_comment("PROJ-12345", "Test comment")

    assert result is False


@patch("devflow.cli.utils.JiraClient")
def test_add_jira_comment_custom_timeout(mock_jira_class):
    """Test adding JIRA comment with custom timeout."""
    mock_client = MagicMock()
    # add_comment now returns None on success
    mock_client.add_comment.return_value = None
    mock_jira_class.return_value = mock_client

    result = add_jira_comment("PROJ-12345", "Test comment", timeout=30)

    assert result is True
    mock_jira_class.assert_called_once_with(timeout=30)
