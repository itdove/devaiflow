"""Tests for daf discover command."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from devflow.cli.commands.discover_command import discover_sessions


@pytest.fixture
def mock_discovered_session():
    """Create a mock discovered session."""
    session = Mock()
    session.uuid = "12345678-1234-1234-1234-123456789abc"
    session.working_directory = "/path/to/project"
    session.message_count = 42
    session.last_active = datetime(2026, 1, 15, 10, 30)
    session.first_message = "Initial prompt for this session"
    return session


@pytest.fixture
def mock_managed_session():
    """Create a mock managed session."""
    session = Mock()
    session.ai_agent_session_id = "87654321-4321-4321-4321-cba987654321"
    session.issue_key = "PROJ-12345"
    session.session_id = "test-session"
    session.name = "test-session"
    return session


class TestDiscoverSessions:
    """Tests for discover_sessions function."""

    def test_discover_no_sessions_found(self, monkeypatch):
        """Test discover when no Claude sessions exist."""
        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager'):
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = []
                    mock_discovery_class.return_value = mock_discovery

                    # Should handle gracefully
                    discover_sessions()

    def test_discover_only_unmanaged_sessions(self, mock_discovered_session, monkeypatch):
        """Test discover with only unmanaged sessions."""
        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    # Setup discovery
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [mock_discovered_session]
                    mock_discovery_class.return_value = mock_discovery

                    # Setup manager with no managed sessions
                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = []
                    mock_manager_class.return_value = mock_manager

                    discover_sessions()

    def test_discover_only_managed_sessions(self, mock_discovered_session, mock_managed_session, monkeypatch):
        """Test discover with only managed sessions."""
        # Make UUIDs match
        mock_discovered_session.uuid = mock_managed_session.ai_agent_session_id

        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    # Setup discovery
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [mock_discovered_session]
                    mock_discovery_class.return_value = mock_discovery

                    # Setup manager with matching managed session
                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = [mock_managed_session]
                    mock_manager_class.return_value = mock_manager

                    discover_sessions()

    def test_discover_mixed_sessions(self, mock_discovered_session, mock_managed_session, monkeypatch):
        """Test discover with both managed and unmanaged sessions."""
        # Create another unmanaged session
        unmanaged_session = Mock()
        unmanaged_session.uuid = "unmanaged-uuid-1234"
        unmanaged_session.working_directory = "/other/project"
        unmanaged_session.message_count = 10
        unmanaged_session.last_active = datetime(2026, 1, 10, 14, 20)
        unmanaged_session.first_message = "Another session prompt"

        # Make first session managed
        mock_discovered_session.uuid = mock_managed_session.ai_agent_session_id

        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    # Setup discovery with both sessions
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [mock_discovered_session, unmanaged_session]
                    mock_discovery_class.return_value = mock_discovery

                    # Setup manager with one managed session
                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = [mock_managed_session]
                    mock_manager_class.return_value = mock_manager

                    discover_sessions()

    def test_discover_truncates_long_messages(self, monkeypatch):
        """Test that long first messages are truncated."""
        session = Mock()
        session.uuid = "test-uuid"
        session.working_directory = "/path/to/project"
        session.message_count = 5
        session.last_active = datetime(2026, 1, 15, 10, 30)
        session.first_message = "A" * 100  # Very long message

        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [session]
                    mock_discovery_class.return_value = mock_discovery

                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = []
                    mock_manager_class.return_value = mock_manager

                    discover_sessions()

    def test_discover_truncates_long_working_directory(self, monkeypatch):
        """Test that long working directory paths are truncated."""
        session = Mock()
        session.uuid = "test-uuid"
        session.working_directory = "/" + "very/long/path/" * 10  # Very long path
        session.message_count = 5
        session.last_active = datetime(2026, 1, 15, 10, 30)
        session.first_message = "Test message"

        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [session]
                    mock_discovery_class.return_value = mock_discovery

                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = []
                    mock_manager_class.return_value = mock_manager

                    discover_sessions()

    def test_discover_handles_missing_first_message(self, monkeypatch):
        """Test discover when first_message is None."""
        session = Mock()
        session.uuid = "test-uuid"
        session.working_directory = "/path/to/project"
        session.message_count = 5
        session.last_active = datetime(2026, 1, 15, 10, 30)
        session.first_message = None  # No first message

        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [session]
                    mock_discovery_class.return_value = mock_discovery

                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = []
                    mock_manager_class.return_value = mock_manager

                    discover_sessions()

    def test_discover_handles_missing_working_directory(self, monkeypatch):
        """Test discover when working_directory is None."""
        session = Mock()
        session.uuid = "test-uuid"
        session.working_directory = None  # No working directory
        session.message_count = 5
        session.last_active = datetime(2026, 1, 15, 10, 30)
        session.first_message = "Test message"

        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [session]
                    mock_discovery_class.return_value = mock_discovery

                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = []
                    mock_manager_class.return_value = mock_manager

                    discover_sessions()

    def test_discover_displays_next_steps_for_unmanaged(self, monkeypatch):
        """Test that next steps are displayed when unmanaged sessions exist."""
        session = Mock()
        session.uuid = "test-uuid"
        session.working_directory = "/path/to/project"
        session.message_count = 5
        session.last_active = datetime(2026, 1, 15, 10, 30)
        session.first_message = "Test message"

        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [session]
                    mock_discovery_class.return_value = mock_discovery

                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = []
                    mock_manager_class.return_value = mock_manager

                    discover_sessions()

    def test_discover_multiple_managed_sessions(self, monkeypatch):
        """Test discover with multiple managed sessions."""
        # Create multiple discovered sessions
        session1 = Mock()
        session1.uuid = "uuid-1"
        session1.working_directory = "/path1"
        session1.message_count = 10
        session1.last_active = datetime(2026, 1, 15, 10, 30)
        session1.first_message = "Session 1"

        session2 = Mock()
        session2.uuid = "uuid-2"
        session2.working_directory = "/path2"
        session2.message_count = 20
        session2.last_active = datetime(2026, 1, 16, 12, 30)
        session2.first_message = "Session 2"

        # Create corresponding managed sessions
        managed1 = Mock()
        managed1.ai_agent_session_id = "uuid-1"
        managed1.issue_key = "PROJ-100"
        managed1.session_id = "session-1"

        managed2 = Mock()
        managed2.ai_agent_session_id = "uuid-2"
        managed2.issue_key = "PROJ-200"
        managed2.session_id = "session-2"

        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [session1, session2]
                    mock_discovery_class.return_value = mock_discovery

                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = [managed1, managed2]
                    mock_manager_class.return_value = mock_manager

                    discover_sessions()

    def test_discover_session_without_ai_agent_session_id(self, monkeypatch):
        """Test that managed sessions without ai_agent_session_id are handled."""
        session = Mock()
        session.uuid = "test-uuid"
        session.working_directory = "/path/to/project"
        session.message_count = 5
        session.last_active = datetime(2026, 1, 15, 10, 30)
        session.first_message = "Test message"

        # Managed session without ai_agent_session_id
        managed = Mock()
        managed.ai_agent_session_id = None  # No UUID
        managed.issue_key = "PROJ-100"
        managed.session_id = "session-1"

        # Mock environment to allow running outside Claude
        monkeypatch.delenv("AI_AGENT_SESSION_ID", raising=False)

        with patch('devflow.cli.commands.discover_command.ConfigLoader'):
            with patch('devflow.cli.commands.discover_command.SessionManager') as mock_manager_class:
                with patch('devflow.cli.commands.discover_command.SessionDiscovery') as mock_discovery_class:
                    mock_discovery = Mock()
                    mock_discovery.discover_sessions.return_value = [session]
                    mock_discovery_class.return_value = mock_discovery

                    mock_manager = Mock()
                    mock_manager.list_sessions.return_value = [managed]
                    mock_manager_class.return_value = mock_manager

                    # Should treat all as unmanaged
                    discover_sessions()
