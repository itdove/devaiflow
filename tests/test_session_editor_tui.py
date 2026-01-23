"""Tests for session editor TUI."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from devflow.ui.session_editor_tui import (
    PathValidator,
    NonEmptyValidator,
    JiraKeyValidator,
    UUIDValidator,
    SessionInput,
    SessionSelect,
    ConversationEntry,
    AddConversationScreen,
    SessionEditorTUI,
    run_session_editor_tui,
)
from devflow.config.models import Session, ConversationContext


# ============================================================================
# Validator Tests
# ============================================================================


def test_path_validator_valid():
    """Test path validator with valid paths."""
    validator = PathValidator()

    # Valid paths
    assert validator.validate("/tmp").is_valid
    assert validator.validate("~/test").is_valid
    assert validator.validate("/some/path/that/does/not/exist").is_valid


def test_path_validator_invalid():
    """Test path validator with invalid/empty paths."""
    validator = PathValidator()

    # Empty path (required)
    result = validator.validate("")
    assert not result.is_valid
    assert "required" in str(result.failure_descriptions).lower()

    result = validator.validate("   ")
    assert not result.is_valid


def test_non_empty_validator():
    """Test non-empty validator."""
    validator = NonEmptyValidator()

    # Valid (non-empty)
    assert validator.validate("test").is_valid
    assert validator.validate("value").is_valid

    # Invalid (empty)
    result = validator.validate("")
    assert not result.is_valid
    assert "required" in str(result.failure_descriptions).lower()

    result = validator.validate("   ")
    assert not result.is_valid


def test_issue_key_validator_valid():
    """Test issue key validator with valid keys."""
    validator = JiraKeyValidator()

    # Valid JIRA keys
    assert validator.validate("PROJ-12345").is_valid
    assert validator.validate("PROJ-1").is_valid
    assert validator.validate("TEST-999999").is_valid
    assert validator.validate("").is_valid  # Allow empty for optional field


def test_issue_key_validator_invalid():
    """Test issue key validator with invalid keys."""
    validator = JiraKeyValidator()

    # Invalid JIRA keys
    result = validator.validate("invalid")
    assert not result.is_valid
    assert "PROJECT-NUMBER" in str(result.failure_descriptions)

    result = validator.validate("PROJ12345")  # Missing hyphen
    assert not result.is_valid

    result = validator.validate("aap-12345")  # Lowercase project key
    assert not result.is_valid

    result = validator.validate("PROJ-")  # Missing number
    assert not result.is_valid


def test_uuid_validator_valid():
    """Test UUID validator with valid UUIDs."""
    validator = UUIDValidator()

    # Valid UUIDs
    assert validator.validate("12345678-1234-1234-1234-123456789abc").is_valid
    assert validator.validate("a1b2c3d4-e5f6-7890-abcd-ef1234567890").is_valid
    assert validator.validate("00000000-0000-0000-0000-000000000000").is_valid


def test_uuid_validator_invalid():
    """Test UUID validator with invalid UUIDs."""
    validator = UUIDValidator()

    # Invalid UUIDs
    result = validator.validate("")
    assert not result.is_valid
    assert "required" in str(result.failure_descriptions).lower()

    result = validator.validate("not-a-uuid")
    assert not result.is_valid
    assert "uuid" in str(result.failure_descriptions).lower()

    result = validator.validate("12345678-1234-1234-1234")  # Too short
    assert not result.is_valid

    result = validator.validate("12345678-1234-1234-1234-123456789abcdef")  # Too long
    assert not result.is_valid


# ============================================================================
# Widget Tests
# ============================================================================


def test_session_input_initialization():
    """Test SessionInput widget initialization."""
    widget = SessionInput(
        label="Test Field",
        field_key="test_field",
        value="test_value",
        help_text="This is help text",
        required=True,
    )

    assert widget.field_key == "test_field"
    assert widget._label == "Test Field"
    assert widget._value == "test_value"
    assert widget._help_text == "This is help text"
    assert widget._required is True
    assert widget._read_only is False


def test_session_input_read_only():
    """Test SessionInput with read-only flag."""
    widget = SessionInput(
        label="Session ID",
        field_key="session_id",
        value="123",
        read_only=True,
    )

    assert widget._read_only is True
    assert widget.get_value() == "123"  # Should return the value directly


def test_session_select_initialization():
    """Test SessionSelect widget initialization."""
    choices = [
        ("Created", "created"),
        ("In Progress", "in_progress"),
        ("Complete", "complete"),
    ]

    widget = SessionSelect(
        label="Status",
        field_key="status",
        choices=choices,
        value="in_progress",
        help_text="Current session status",
    )

    assert widget.field_key == "status"
    assert widget._label == "Status"
    assert widget._choices == choices
    assert widget._value == "in_progress"
    assert widget._help_text == "Current session status"


def test_conversation_entry_initialization():
    """Test ConversationEntry widget initialization."""
    conv = ConversationContext(
        ai_agent_session_id="12345678-1234-1234-1234-123456789abc",
        project_path="/path/to/project",
        branch="feature-branch",
        message_count=5,
    )

    widget = ConversationEntry(
        conv_key="repo#session-1",
        conversation=conv,
    )

    assert widget.conv_key == "repo#session-1"
    assert widget.conversation == conv


# ============================================================================
# Session Editor TUI Tests
# ============================================================================


@pytest.fixture
def mock_session(tmp_path):
    """Create a mock session for testing."""
    session = Session(
        name="test-session",
        issue_key="PROJ-12345",
        goal="Test goal",
        session_type="development",
        status="active",
        created=datetime(2024, 1, 1, 12, 0, 0),
        time_tracking_state="paused",
    )

    # Add a conversation with existing temp path
    project_path = tmp_path / "project"
    project_path.mkdir(parents=True, exist_ok=True)

    conv = ConversationContext(
        ai_agent_session_id="12345678-1234-1234-1234-123456789abc",
        project_path=str(project_path),
        branch="feature-branch",
        message_count=10,
    )
    session.conversations = {"repo#session-1": conv}

    return session


@pytest.fixture
def mock_session_manager(mock_session):
    """Create a mock session manager."""
    with patch('devflow.ui.session_editor_tui.SessionManager') as MockSessionManager:
        mock_manager = Mock()
        mock_manager.get_session.return_value = mock_session
        mock_manager.save_session.return_value = None
        MockSessionManager.return_value = mock_manager
        yield mock_manager


@pytest.fixture
def mock_config_loader():
    """Create a mock config loader."""
    with patch('devflow.ui.session_editor_tui.ConfigLoader') as MockConfigLoader:
        mock_loader = Mock()
        mock_loader.session_home = Path("/tmp/.daf-sessions")
        mock_loader.config_file = Path("/tmp/.daf-sessions/config.json")
        mock_loader.get_session_dir.return_value = Path("/tmp/.daf-sessions/sessions/test-session")
        MockConfigLoader.return_value = mock_loader
        yield mock_loader


def test_session_editor_tui_initialization(mock_session, mock_session_manager, mock_config_loader):
    """Test SessionEditorTUI initialization."""
    app = SessionEditorTUI("test-session")

    assert app.session_identifier == "test-session"
    assert app.session == mock_session
    assert app.modified is False
    assert app.TITLE == "DevAIFlow - Edit Session: test-session"


def test_session_editor_tui_initialization_session_not_found(mock_config_loader):
    """Test SessionEditorTUI initialization with non-existent session."""
    with patch('devflow.ui.session_editor_tui.SessionManager') as MockSessionManager:
        mock_manager = Mock()
        mock_manager.get_session.return_value = None
        MockSessionManager.return_value = mock_manager

        with pytest.raises(RuntimeError, match="Session not found"):
            SessionEditorTUI("non-existent-session")


def test_collect_values(mock_session, mock_session_manager, mock_config_loader, monkeypatch):
    """Test _collect_values method."""
    app = SessionEditorTUI("test-session")

    # Mock query_one to return mock widgets
    mock_goal_input = Mock()
    mock_goal_input.value = "Updated goal"

    mock_status_select = Mock()
    mock_status_select.value = "completed"

    mock_session_type_select = Mock()
    mock_session_type_select.value = "ticket_creation"

    mock_issue_key_input = Mock()
    mock_issue_key_input.value = "PROJ-99999"

    def mock_query_one(selector, widget_type=None):
        """Mock query_one to return appropriate mock widgets."""
        if "goal" in selector:
            return mock_goal_input
        elif "status" in selector:
            return mock_status_select
        elif "session_type" in selector:
            return mock_session_type_select
        elif "issue_key" in selector:
            return mock_issue_key_input
        return Mock(value="")

    app.query_one = mock_query_one

    # Call _collect_values
    app._collect_values()

    # Verify values were collected
    assert app.session.goal == "Updated goal"
    assert app.session.status == "completed"
    assert app.session.session_type == "ticket_creation"
    assert app.session.issue_key == "PROJ-99999"
    assert app.modified is True


def test_validate_all_valid(mock_session, mock_session_manager, mock_config_loader):
    """Test _validate_all with valid session data."""
    app = SessionEditorTUI("test-session")

    # Session has valid data
    errors = app._validate_all()
    assert len(errors) == 0


def test_validate_all_invalid_issue_key(mock_session, mock_session_manager, mock_config_loader):
    """Test _validate_all with invalid issue key."""
    app = SessionEditorTUI("test-session")

    # Set invalid issue key
    app.session.issue_key = "invalid-key"

    errors = app._validate_all()
    assert len(errors) > 0
    assert any("issue key" in err for err in errors)


def test_validate_all_invalid_conversation_uuid(mock_session, mock_session_manager, mock_config_loader):
    """Test _validate_all with invalid conversation UUID."""
    app = SessionEditorTUI("test-session")

    # Add conversation with invalid UUID
    conv = ConversationContext(
        ai_agent_session_id="not-a-valid-uuid",
        project_path="/path/to/project",
        branch="feature-branch",
    )
    app.session.conversations["bad-conv"] = conv

    errors = app._validate_all()
    assert len(errors) > 0
    assert any("UUID format" in err for err in errors)


def test_validate_all_nonexistent_project_path(mock_session, mock_session_manager, mock_config_loader):
    """Test _validate_all with non-existent project path."""
    app = SessionEditorTUI("test-session")

    # Add conversation with non-existent path
    conv = ConversationContext(
        ai_agent_session_id="12345678-1234-1234-1234-123456789abc",
        project_path="/this/path/does/not/exist",
        branch="feature-branch",
    )
    app.session.conversations["bad-path-conv"] = conv

    errors = app._validate_all()
    assert len(errors) > 0
    assert any("does not exist" in err for err in errors)


def test_create_backup(mock_session, mock_session_manager, mock_config_loader, tmp_path):
    """Test _create_backup creates backup file."""
    # Override session_home to use tmp_path
    mock_config_loader.session_home = tmp_path
    mock_config_loader.get_session_dir.return_value = tmp_path / "sessions" / "test-session"

    app = SessionEditorTUI("test-session")

    # Create session directory and metadata file
    session_dir = tmp_path / "sessions" / "test-session"
    session_dir.mkdir(parents=True)
    metadata_file = session_dir / "metadata.json"
    metadata_file.write_text('{"name": "test-session"}')

    # Create backup
    backup_path = app._create_backup()

    # Verify backup was created
    assert backup_path.exists()
    assert backup_path.parent == tmp_path / "backups"
    assert "test-session" in backup_path.name


def test_action_save(mock_session, mock_session_manager, mock_config_loader, tmp_path, monkeypatch):
    """Test action_save method."""
    # Override session_home to use tmp_path
    mock_config_loader.session_home = tmp_path

    app = SessionEditorTUI("test-session")

    # Mock methods
    app._collect_values = Mock()
    app._validate_all = Mock(return_value=[])  # No validation errors
    app.notify = Mock()

    # Create backup directory
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)

    # Call action_save
    app.action_save()

    # Verify methods were called
    app._collect_values.assert_called_once()
    app._validate_all.assert_called_once()
    mock_session_manager.save_session.assert_called_once_with(app.session)
    # Verify success notification was called (check that notify was called with severity="information")
    notify_calls = [call for call in app.notify.call_args_list if call.kwargs.get("severity") == "information"]
    assert len(notify_calls) >= 1  # At least one success notification


def test_action_save_validation_errors(mock_session, mock_session_manager, mock_config_loader):
    """Test action_save with validation errors."""
    app = SessionEditorTUI("test-session")

    # Mock methods
    app._collect_values = Mock()
    app._validate_all = Mock(return_value=["Validation error 1", "Validation error 2"])
    app.notify = Mock()

    # Call action_save
    app.action_save()

    # Verify save was NOT called
    mock_session_manager.save_session.assert_not_called()

    # Verify error notification was shown
    app.notify.assert_called_once()
    call_args = app.notify.call_args
    assert call_args.kwargs["severity"] == "error"
    assert "Validation errors" in call_args.args[0]


def test_refresh_conversations_list(mock_session, mock_session_manager, mock_config_loader):
    """Test _refresh_conversations_list method."""
    app = SessionEditorTUI("test-session")

    # Mock the list container
    mock_container = Mock()
    app.query_one = Mock(return_value=mock_container)

    # Call refresh
    app._refresh_conversations_list()

    # Verify container was updated
    mock_container.remove_children.assert_called_once()
    mock_container.mount.assert_called()  # Should mount ConversationEntry widgets


def test_run_session_editor_tui(mock_session, mock_session_manager, mock_config_loader):
    """Test run_session_editor_tui function."""
    with patch.object(SessionEditorTUI, 'run') as mock_run:
        run_session_editor_tui("test-session")
        mock_run.assert_called_once()


# ============================================================================
# Add Conversation Screen Tests
# ============================================================================


def test_add_conversation_screen_initialization():
    """Test AddConversationScreen initialization in add mode."""
    screen = AddConversationScreen()

    assert screen.existing_conv is None
    assert screen.conv_key is None
    assert screen.is_edit_mode is False


def test_add_conversation_screen_edit_mode():
    """Test AddConversationScreen initialization in edit mode."""
    conv = ConversationContext(
        ai_agent_session_id="12345678-1234-1234-1234-123456789abc",
        project_path="/path/to/project",
        branch="feature-branch",
    )

    screen = AddConversationScreen(existing_conv=conv, conv_key="repo#session-1")

    assert screen.existing_conv == conv
    assert screen.conv_key == "repo#session-1"
    assert screen.is_edit_mode is True


def test_session_editor_tui_with_active_time_tracking(tmp_path, mock_session_manager, mock_config_loader):
    """Test SessionEditorTUI can open sessions with time_tracking_state='active'.

    Regression test for PROJ-61017: daf edit crashes with InvalidSelectValueError
    when session has time_tracking_state='active'.
    """
    # Create a session with active time tracking state
    session = Session(
        name="active-session",
        issue_key="PROJ-61017",
        goal="Test active time tracking",
        session_type="development",
        status="in_progress",
        created=datetime(2024, 1, 1, 12, 0, 0),
        time_tracking_state="active",  # This was causing the crash
    )

    # Mock the session manager to return our session
    mock_session_manager.get_session.return_value = session

    # This should NOT raise InvalidSelectValueError
    app = SessionEditorTUI("active-session")

    # Verify the app initialized correctly
    assert app.session_identifier == "active-session"
    assert app.session == session
    assert app.session.time_tracking_state == "active"
