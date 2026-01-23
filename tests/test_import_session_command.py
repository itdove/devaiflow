"""Tests for import-session command."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devflow.cli.commands.import_session_command import import_session
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


@pytest.fixture
def mock_discovered_session():
    """Create a mock discovered session."""
    from devflow.session.discovery import DiscoveredSession

    return DiscoveredSession(
        uuid="test-uuid-123",
        project_path="/nonexistent/test/path",  # Use non-existent path
        working_directory="test-project",
        message_count=10,
        created=datetime(2025, 1, 1, 10, 0, 0),
        last_active=datetime(2025, 1, 2, 15, 30, 0),
        first_message="Test session goal",
    )


def test_import_session_not_found(temp_daf_home, monkeypatch, capsys):
    """Test importing a session that doesn't exist."""
    # Mock discovery to return empty list
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = []

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    import_session("nonexistent-uuid")

    captured = capsys.readouterr()
    assert "Session nonexistent-uuid not found" in captured.out
    assert "daf discover" in captured.out


def test_import_session_already_managed(temp_daf_home, monkeypatch, capsys, mock_discovered_session):
    """Test importing a session that's already managed."""
    # Create existing session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="existing",
        issue_key="PROJ-123",
        goal="Already managed",
        working_directory="test-dir",
        project_path="/test",
        ai_agent_session_id="test-uuid-123",
    )

    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    import_session("test-uuid-123")

    captured = capsys.readouterr()
    assert "already managed by daf tool" in captured.out
    assert "PROJ-123" in captured.out


def test_import_session_with_jira_and_goal(temp_daf_home, monkeypatch, capsys, mock_discovered_session):
    """Test importing session with issue key and goal provided."""
    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock Confirm.ask to use current directory
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: True)

    import_session("test-uuid-123", issue_key="PROJ-999", goal="Import test")

    # Verify session was created
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("PROJ-999")

    assert len(sessions) == 1
    assert sessions[0].issue_key == "PROJ-999"
    assert sessions[0].goal == "Import test"
    # New conversation-based API
    assert sessions[0].active_conversation.ai_agent_session_id == "test-uuid-123"
    assert sessions[0].active_conversation.message_count == 10

    captured = capsys.readouterr()
    assert "Imported session for PROJ-999" in captured.out


def test_import_session_prompts_for_jira(temp_daf_home, monkeypatch, capsys, mock_discovered_session):
    """Test that import prompts for issue key if not provided."""
    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock Prompt.ask to return issue key and goal
    mock_prompt = Mock(side_effect=["PROJ-888", "Prompted import"])
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Prompt.ask", mock_prompt)

    # Mock Confirm.ask to use current directory
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: True)

    import_session("test-uuid-123")

    # Verify session was created
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("PROJ-888")

    assert len(sessions) == 1
    assert sessions[0].issue_key == "PROJ-888"


def test_import_session_empty_issue_key(temp_daf_home, monkeypatch, capsys, mock_discovered_session):
    """Test import fails when issue key is empty."""
    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock Prompt.ask to return empty issue key
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Prompt.ask", lambda *args, **kwargs: "")

    import_session("test-uuid-123")

    captured = capsys.readouterr()
    assert "issue key is required" in captured.out


def test_import_session_empty_goal(temp_daf_home, monkeypatch, capsys, mock_discovered_session):
    """Test import fails when goal is empty."""
    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock Prompt.ask to return JIRA then empty goal
    mock_prompt = Mock(side_effect=["PROJ-777", ""])
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Prompt.ask", mock_prompt)

    import_session("test-uuid-123")

    captured = capsys.readouterr()
    assert "Goal is required" in captured.out


def test_import_session_long_first_message(temp_daf_home, monkeypatch, capsys):
    """Test import truncates long first message."""
    from devflow.session.discovery import DiscoveredSession

    long_message = "A" * 150
    discovered = DiscoveredSession(
        uuid="test-long",
        project_path="/test",
        working_directory="test",
        message_count=5,
        created=datetime(2025, 1, 1),
        last_active=datetime(2025, 1, 2),
        first_message=long_message,
    )

    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [discovered]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock prompts
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Prompt.ask", lambda *args, **kwargs: "PROJ-666" if "JIRA" in args[0] else "Test")
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: True)

    import_session("test-long")

    captured = capsys.readouterr()
    assert "..." in captured.out  # Truncation indicator


def test_import_session_missing_project_path(temp_daf_home, monkeypatch, capsys):
    """Test import prompts for project path if missing."""
    from devflow.session.discovery import DiscoveredSession

    discovered = DiscoveredSession(
        uuid="test-no-path",
        project_path=None,
        working_directory=None,
        message_count=5,
        created=datetime(2025, 1, 1),
        last_active=datetime(2025, 1, 2),
        first_message="Test",
    )

    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [discovered]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock prompts - use current dir
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Prompt.ask", lambda *args, **kwargs: "PROJ-555" if "issue" in args[0] else "Test goal")
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: True)

    import_session("test-no-path")

    # Verify session was created with current directory
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("PROJ-555")

    assert len(sessions) == 1
    # New conversation-based API
    assert sessions[0].active_conversation.project_path is not None


def test_import_session_custom_project_path(temp_daf_home, monkeypatch, capsys):
    """Test import with custom project path."""
    from devflow.session.discovery import DiscoveredSession

    discovered = DiscoveredSession(
        uuid="test-custom",
        project_path="/nonexistent",
        working_directory="test",
        message_count=5,
        created=datetime(2025, 1, 1),
        last_active=datetime(2025, 1, 2),
        first_message="Test",
    )

    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [discovered]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock prompts - don't use current dir, provide custom path
    prompt_values = ["PROJ-444", "Test goal", "/custom/path"]
    prompt_iter = iter(prompt_values)

    def mock_prompt(*args, **kwargs):
        return next(prompt_iter)

    monkeypatch.setattr("devflow.cli.commands.import_session_command.Prompt.ask", mock_prompt)
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: False)

    import_session("test-custom")

    # Verify session was created with custom path
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("PROJ-444")

    assert len(sessions) == 1
    # New conversation-based API
    assert sessions[0].active_conversation.project_path == "/custom/path"


def test_import_session_with_existing_sessions(temp_daf_home, monkeypatch, capsys, mock_discovered_session):
    """Test importing when other sessions exist for same issue key."""
    # Create existing session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="existing",
        issue_key="PROJ-333",
        goal="First session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="other-uuid",
    )

    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock confirm to proceed - this will be called twice:
    # First for "Use current directory?" - answer True
    # Second for "Create session #2?" - answer True
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: True)

    import_session("test-uuid-123", issue_key="PROJ-333", goal="Second session")

    # Verify second session was created - they will be in different session groups
    # First session: name="existing", issue_key="PROJ-333"
    # Second session: name="PROJ-333", issue_key="PROJ-333"
    session_manager = SessionManager(config_loader)

    # Get all sessions
    all_sessions = session_manager.list_sessions()
    aap_333_sessions = [s for s in all_sessions if s.issue_key == "PROJ-333"]

    assert len(aap_333_sessions) == 2
    assert any(s.name == "existing" for s in aap_333_sessions)
    assert any(s.name == "PROJ-333" for s in aap_333_sessions)

    captured = capsys.readouterr()
    assert "Found 1 existing session" in captured.out


def test_import_session_cancel_with_existing(temp_daf_home, monkeypatch, capsys, mock_discovered_session):
    """Test cancelling import when other sessions exist."""
    # Create existing session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="existing",
        issue_key="PROJ-222",
        goal="Existing",
        working_directory="dir",
        project_path="/path",
        ai_agent_session_id="other",
    )

    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock confirm to cancel - this will be called twice:
    # First for "Use current directory?" - answer True
    # Second for "Create session #2?" - answer False
    confirm_responses = [True, False]
    confirm_iter = iter(confirm_responses)
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: next(confirm_iter))

    import_session("test-uuid-123", issue_key="PROJ-222", goal="Second")

    # Verify second session was NOT created
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("PROJ-222")

    assert len(sessions) == 1  # Only the original

    captured = capsys.readouterr()
    assert "Import cancelled" in captured.out


def test_import_session_displays_info(temp_daf_home, monkeypatch, capsys, mock_discovered_session):
    """Test that import displays session info."""
    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock Confirm.ask to use current directory
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: True)

    import_session("test-uuid-123", issue_key="PROJ-111", goal="Test")

    captured = capsys.readouterr()
    assert "Session to import:" in captured.out
    assert "test-uuid-123" in captured.out
    assert "test-project" in captured.out
    assert "Messages: 10" in captured.out
    assert "2025-01-01" in captured.out


def test_import_session_sets_status_paused(temp_daf_home, monkeypatch, mock_discovered_session):
    """Test that imported sessions are marked as paused."""
    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock Confirm.ask to use current directory
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: True)

    import_session("test-uuid-123", issue_key="PROJ-100", goal="Test")

    # Verify status
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("PROJ-100")

    assert len(sessions) == 1
    assert sessions[0].status == "paused"


def test_import_session_preserves_metadata(temp_daf_home, monkeypatch, mock_discovered_session):
    """Test that import preserves created/last_active dates."""
    # Mock discovery
    mock_discovery = Mock()
    mock_discovery.discover_sessions.return_value = [mock_discovered_session]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: mock_discovery
    )

    # Mock Confirm.ask to use current directory
    monkeypatch.setattr("devflow.cli.commands.import_session_command.Confirm.ask", lambda *args, **kwargs: True)

    import_session("test-uuid-123", issue_key="PROJ-99", goal="Test")

    # Verify metadata
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    sessions = session_manager.index.get_sessions("PROJ-99")

    assert len(sessions) == 1
    assert sessions[0].created == datetime(2025, 1, 1, 10, 0, 0)
    assert sessions[0].last_active == datetime(2025, 1, 2, 15, 30, 0)
    # New conversation-based API
    assert sessions[0].active_conversation.message_count == 10
