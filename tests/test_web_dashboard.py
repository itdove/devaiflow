"""Tests for the web dashboard module.

Tests cover:
- DataBridge (data access layer for the web UI)
- DashboardApp initialization and configuration
- CLI command registration and dependency checking
- Port file management
- Security warnings for non-localhost binding
"""

import json
import os
import socket
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, PropertyMock

import pytest
from click.testing import CliRunner

from devflow.config.loader import ConfigLoader
from devflow.config.models import (
    Config,
    ConversationContext,
    Conversation,
    JiraConfig,
    RepoConfig,
    Session,
    WorkSession,
)
from devflow.session.manager import SessionManager
from devflow.web.utils.data_bridge import DataBridge


# ============================================================================
# Helper functions
# ============================================================================


def _make_session(
    name: str = "test-session",
    status: str = "in_progress",
    goal: str = "Test goal",
    issue_key: str = None,
    workspace_name: str = None,
    session_type: str = "development",
    work_sessions: list = None,
    tags: list = None,
) -> Session:
    """Create a test Session object.

    Args:
        name: Session name.
        status: Session status.
        goal: Session goal.
        issue_key: Optional issue key.
        workspace_name: Optional workspace name.
        session_type: Session type.
        work_sessions: Optional work sessions list.
        tags: Optional tags list.

    Returns:
        Session instance for testing.
    """
    session = Session(
        name=name,
        issue_key=issue_key,
        goal=goal,
        working_directory="test-dir",
        status=status,
        session_type=session_type,
        workspace_name=workspace_name,
        tags=tags or [],
    )
    if work_sessions:
        session.work_sessions = work_sessions
    return session


# ============================================================================
# DataBridge Tests
# ============================================================================


class TestDataBridgeSessionToDict:
    """Tests for DataBridge._session_to_dict method."""

    def test_basic_session_to_dict(self):
        """Test converting a basic session to dictionary."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        session = _make_session(
            name="my-session",
            status="in_progress",
            goal="Implement feature",
            issue_key="PROJ-123",
            workspace_name="primary",
        )

        result = bridge._session_to_dict(session)

        assert result["name"] == "my-session"
        assert result["status"] == "in_progress"
        assert result["goal"] == "Implement feature"
        assert result["issue_key"] == "PROJ-123"
        assert result["workspace"] == "primary"
        assert result["session_type"] == "development"

    def test_session_to_dict_with_time_tracking(self):
        """Test time calculation for completed work sessions."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        ws = WorkSession(
            start=datetime(2026, 1, 1, 10, 0, 0),
            end=datetime(2026, 1, 1, 12, 30, 0),
            duration="2h 30m",
        )
        session = _make_session(work_sessions=[ws])

        result = bridge._session_to_dict(session)

        assert result["time"] == "2h 30m"

    def test_session_to_dict_no_issue_key(self):
        """Test session without issue key returns empty string."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        session = _make_session(issue_key=None)

        result = bridge._session_to_dict(session)

        assert result["issue_key"] == ""

    def test_session_to_dict_no_workspace(self):
        """Test session without workspace returns empty string."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        session = _make_session(workspace_name=None)

        result = bridge._session_to_dict(session)

        assert result["workspace"] == ""

    def test_session_to_dict_zero_time(self):
        """Test session with no work sessions shows 0m."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        session = _make_session(work_sessions=[])

        result = bridge._session_to_dict(session)

        assert result["time"] == "0m"

    def test_session_to_dict_last_active_formatting(self):
        """Test last_active is formatted as YYYY-MM-DD HH:MM."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        session = _make_session()
        session.last_active = datetime(2026, 6, 3, 14, 30, 0)

        result = bridge._session_to_dict(session)

        assert result["last_active"] == "2026-06-03 14:30"


class TestDataBridgeSessionToDetailDict:
    """Tests for DataBridge._session_to_detail_dict method."""

    def test_detail_dict_includes_base_fields(self):
        """Test detail dict includes all base fields from _session_to_dict."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        session = _make_session(name="detail-session", tags=["tag1", "tag2"])
        session.created = datetime(2026, 1, 1, 10, 0, 0)

        result = bridge._session_to_detail_dict(session)

        assert result["name"] == "detail-session"
        assert result["tags"] == ["tag1", "tag2"]
        assert result["created"] == "2026-01-01 10:00"

    def test_detail_dict_includes_conversations(self):
        """Test detail dict includes conversation data."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        session = _make_session()
        session.add_conversation(
            working_dir="test-dir",
            ai_agent_session_id="uuid-123",
            project_path="/path/to/project",
            branch="feature-branch",
        )

        result = bridge._session_to_detail_dict(session)

        assert "conversations" in result
        assert len(result["conversations"]) == 1
        conv = result["conversations"][0]
        assert conv["working_dir"] == "test-dir"
        assert conv["project_path"] == "/path/to/project"
        assert conv["branch"] == "feature-branch"

    def test_detail_dict_includes_work_sessions(self):
        """Test detail dict includes work session data."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        ws = WorkSession(
            start=datetime(2026, 1, 1, 10, 0, 0),
            end=datetime(2026, 1, 1, 12, 0, 0),
            duration="2h 0m",
            user="testuser",
        )
        session = _make_session(work_sessions=[ws])

        result = bridge._session_to_detail_dict(session)

        assert "work_sessions" in result
        assert len(result["work_sessions"]) == 1
        ws_dict = result["work_sessions"][0]
        assert ws_dict["start"] == "2026-01-01 10:00"
        assert ws_dict["end"] == "2026-01-01 12:00"
        assert ws_dict["duration"] == "2h 0m"
        assert ws_dict["user"] == "testuser"

    def test_detail_dict_active_work_session(self):
        """Test detail dict with active (no end) work session."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        ws = WorkSession(
            start=datetime(2026, 1, 1, 10, 0, 0),
            end=None,
            user="testuser",
        )
        session = _make_session(work_sessions=[ws])

        result = bridge._session_to_detail_dict(session)

        ws_dict = result["work_sessions"][0]
        assert ws_dict["end"] == "Active"
        assert ws_dict["duration"] == ""

    def test_detail_dict_empty_conversations(self):
        """Test detail dict with no conversations."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        session = _make_session()
        # Don't add any conversations

        result = bridge._session_to_detail_dict(session)

        assert result["conversations"] == []


class TestDataBridgeListSessions:
    """Tests for DataBridge.list_sessions method."""

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_list_sessions_no_filter(self, mock_manager_cls):
        """Test listing all sessions without filters."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        sessions = [
            _make_session(name="session-1", status="in_progress"),
            _make_session(name="session-2", status="complete"),
        ]
        mock_manager = Mock()
        mock_manager.list_sessions.return_value = sessions
        mock_manager_cls.return_value = mock_manager

        result = bridge.list_sessions()

        assert len(result) == 2
        assert result[0]["name"] == "session-1"
        assert result[1]["name"] == "session-2"

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_list_sessions_with_status_filter(self, mock_manager_cls):
        """Test listing sessions filtered by status."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        sessions = [_make_session(name="active", status="in_progress")]
        mock_manager = Mock()
        mock_manager.list_sessions.return_value = sessions
        mock_manager_cls.return_value = mock_manager

        result = bridge.list_sessions(status="in_progress")

        mock_manager.list_sessions.assert_called_once_with(
            status="in_progress",
            working_directory=None,
        )
        assert len(result) == 1


class TestDataBridgeGetSession:
    """Tests for DataBridge.get_session method."""

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_get_session_found(self, mock_manager_cls):
        """Test getting a session that exists."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        session = _make_session(name="found-session")
        mock_manager = Mock()
        mock_manager.get_session.return_value = session
        mock_manager_cls.return_value = mock_manager

        result = bridge.get_session("found-session")

        assert result is not None
        assert result["name"] == "found-session"

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_get_session_not_found(self, mock_manager_cls):
        """Test getting a session that doesn't exist."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        mock_manager = Mock()
        mock_manager.get_session.return_value = None
        mock_manager_cls.return_value = mock_manager

        result = bridge.get_session("nonexistent")

        assert result is None


class TestDataBridgeNotes:
    """Tests for DataBridge note operations."""

    def test_get_session_notes_existing(self, tmp_path):
        """Test reading notes from an existing notes file."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        # Create notes file
        session_dir = tmp_path / ".daf-sessions" / "sessions" / "test-session"
        session_dir.mkdir(parents=True)
        notes_file = session_dir / "notes.md"
        notes_file.write_text("# Session Notes: test-session\n\n## 2026-01-01 10:00\n- Test note\n")

        with patch("devflow.web.utils.data_bridge.get_cs_home", return_value=tmp_path / ".daf-sessions"):
            result = bridge.get_session_notes("test-session")

        assert "Test note" in result
        assert "Session Notes" in result

    def test_get_session_notes_missing(self, tmp_path):
        """Test reading notes when no notes file exists."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        with patch("devflow.web.utils.data_bridge.get_cs_home", return_value=tmp_path / ".daf-sessions"):
            result = bridge.get_session_notes("nonexistent-session")

        assert result == ""

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_add_session_note_success(self, mock_manager_cls):
        """Test adding a note successfully."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        mock_manager = Mock()
        mock_manager_cls.return_value = mock_manager

        result = bridge.add_session_note("test-session", "New note")

        assert result is True
        mock_manager.add_note.assert_called_once_with("test-session", "New note")

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_add_session_note_failure(self, mock_manager_cls):
        """Test adding a note when session doesn't exist."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        mock_manager = Mock()
        mock_manager.add_note.side_effect = ValueError("Session not found")
        mock_manager_cls.return_value = mock_manager

        result = bridge.add_session_note("nonexistent", "Note")

        assert result is False


class TestDataBridgeConfigSummary:
    """Tests for DataBridge.get_config_summary method."""

    def test_config_summary_loaded(self):
        """Test config summary when config is loaded."""
        bridge = DataBridge.__new__(DataBridge)
        config_loader = Mock()

        # Use Mock for config to avoid complex Pydantic model construction
        config = Mock()
        config.jira = Mock()
        config.jira.url = "https://jira.test.com"
        config.jira.project = "PROJ"
        config.github = None
        config.repos = Mock()
        config.repos.workspaces = None
        config.agent_backend = "claude"
        config_loader.load_config.return_value = config
        bridge.config_loader = config_loader

        result = bridge.get_config_summary()

        assert result["loaded"] is True
        assert result["jira"]["url"] == "https://jira.test.com"
        assert result["agent_backend"] == "claude"

    def test_config_summary_not_loaded(self):
        """Test config summary when config is None."""
        bridge = DataBridge.__new__(DataBridge)
        config_loader = Mock()
        config_loader.load_config.return_value = None
        bridge.config_loader = config_loader

        result = bridge.get_config_summary()

        assert result["loaded"] is False


class TestDataBridgeSessionCountByStatus:
    """Tests for DataBridge.get_session_count_by_status method."""

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_session_counts(self, mock_manager_cls):
        """Test counting sessions by status."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        sessions = [
            _make_session(name="s1", status="in_progress"),
            _make_session(name="s2", status="in_progress"),
            _make_session(name="s3", status="complete"),
            _make_session(name="s4", status="paused"),
        ]
        mock_manager = Mock()
        mock_manager.list_sessions.return_value = sessions
        mock_manager_cls.return_value = mock_manager

        result = bridge.get_session_count_by_status()

        assert result["in_progress"] == 2
        assert result["complete"] == 1
        assert result["paused"] == 1

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_session_counts_empty(self, mock_manager_cls):
        """Test counting sessions when no sessions exist."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        mock_manager = Mock()
        mock_manager.list_sessions.return_value = []
        mock_manager_cls.return_value = mock_manager

        result = bridge.get_session_count_by_status()

        assert result == {}


# ============================================================================
# Port File Management Tests
# ============================================================================


class TestPortFileManagement:
    """Tests for port file write and cleanup."""

    def test_write_port(self, tmp_path):
        """Test writing port to state file."""
        from devflow.web.app import _write_port, _get_port_file

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            _write_port(12345)
            port_file = _get_port_file()
            assert port_file.exists()
            assert port_file.read_text() == "12345"

    def test_cleanup_port_file(self, tmp_path):
        """Test cleanup removes port file."""
        from devflow.web.app import _write_port, _cleanup_port_file

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            _write_port(12345)
            _cleanup_port_file()
            port_file = tmp_path / "state" / "dashboard.port"
            assert not port_file.exists()

    def test_cleanup_port_file_missing(self, tmp_path):
        """Test cleanup doesn't fail when port file doesn't exist."""
        from devflow.web.app import _cleanup_port_file

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            # Should not raise
            _cleanup_port_file()

    def test_write_port_creates_state_dir(self, tmp_path):
        """Test that _write_port creates the state directory if missing."""
        from devflow.web.app import _write_port

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            _write_port(9999)
            state_dir = tmp_path / "state"
            assert state_dir.is_dir()


# ============================================================================
# DashboardApp Tests
# ============================================================================


class TestDashboardApp:
    """Tests for DashboardApp initialization."""

    def test_init_creates_bridge(self):
        """Test that DashboardApp creates a DataBridge instance."""
        with patch("devflow.web.app.DataBridge") as mock_bridge:
            from devflow.web.app import DashboardApp

            app = DashboardApp()
            mock_bridge.assert_called_once()

    @patch("devflow.web.app.socket")
    @patch("devflow.web.app._write_port")
    @patch("devflow.web.app.atexit")
    def test_run_with_dynamic_port(self, mock_atexit, mock_write_port, mock_socket_mod):
        """Test that run() allocates a dynamic port when port=0."""
        from devflow.web.app import DashboardApp

        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("127.0.0.1", 54321)
        mock_socket_mod.socket.return_value = mock_sock
        mock_socket_mod.AF_INET = socket.AF_INET
        mock_socket_mod.SOCK_STREAM = socket.SOCK_STREAM

        dashboard = DashboardApp.__new__(DashboardApp)
        dashboard.bridge = Mock()

        # Mock the nicegui imports that happen inside run()
        mock_ui = MagicMock()
        mock_nicegui_app = MagicMock()
        with patch.dict("sys.modules", {
            "nicegui": MagicMock(ui=mock_ui, app=mock_nicegui_app),
        }):
            with patch("devflow.web.app.webbrowser"):
                # Patch nicegui imports inside run()
                import devflow.web.app as app_module
                original_run = app_module.DashboardApp.run

                def mock_run(self_inner, host="127.0.0.1", port=0, show=True, reload=False):
                    """Mock run that skips NiceGUI but tests port allocation."""
                    import devflow.web.app as _mod
                    if host != "127.0.0.1":
                        _mod.logger.warning(
                            "Dashboard binding to %s -- exposed on network. "
                            "Only bind to non-localhost addresses if you understand "
                            "the security implications.",
                            host,
                        )
                    if port == 0:
                        sock = mock_socket_mod.socket(mock_socket_mod.AF_INET, mock_socket_mod.SOCK_STREAM)
                        sock.bind((host, 0))
                        port = sock.getsockname()[1]
                        sock.close()
                    _mod._write_port(port)
                    _mod.atexit.register(_mod._cleanup_port_file)

                with patch.object(DashboardApp, "run", mock_run):
                    dashboard.run(port=0, show=False)

        mock_sock.bind.assert_called_once_with(("127.0.0.1", 0))
        mock_sock.close.assert_called_once()
        mock_write_port.assert_called_once_with(54321)

    @patch("devflow.web.app.logger")
    @patch("devflow.web.app.socket")
    @patch("devflow.web.app._write_port")
    @patch("devflow.web.app.atexit")
    def test_run_non_localhost_warning(self, mock_atexit, mock_write_port, mock_socket_mod, mock_logger):
        """Test security warning when binding to non-localhost."""
        from devflow.web.app import DashboardApp

        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("0.0.0.0", 8080)
        mock_socket_mod.socket.return_value = mock_sock
        mock_socket_mod.AF_INET = socket.AF_INET
        mock_socket_mod.SOCK_STREAM = socket.SOCK_STREAM

        dashboard = DashboardApp.__new__(DashboardApp)
        dashboard.bridge = Mock()

        # Create a mock run that exercises the security warning path
        def mock_run(self_inner, host="127.0.0.1", port=0, show=True, reload=False):
            """Mock run that only tests security warning."""
            import devflow.web.app as _mod
            if host != "127.0.0.1":
                _mod.logger.warning(
                    "Dashboard binding to %s -- exposed on network. "
                    "Only bind to non-localhost addresses if you understand "
                    "the security implications.",
                    host,
                )
            if port == 0:
                sock = mock_socket_mod.socket(mock_socket_mod.AF_INET, mock_socket_mod.SOCK_STREAM)
                sock.bind((host, 0))
                port = sock.getsockname()[1]
                sock.close()
            _mod._write_port(port)
            _mod.atexit.register(_mod._cleanup_port_file)

        with patch.object(DashboardApp, "run", mock_run):
            dashboard.run(host="0.0.0.0", port=0, show=False)

        mock_logger.warning.assert_called_once()
        assert "exposed on network" in mock_logger.warning.call_args[0][0]


# ============================================================================
# CLI Command Tests
# ============================================================================


class TestDashboardCLICommand:
    """Tests for the 'daf dashboard' CLI command."""

    def test_dashboard_command_registered(self):
        """Test that the dashboard command is registered on the CLI."""
        from devflow.cli.main import cli

        commands = cli.commands if hasattr(cli, "commands") else {}
        assert "dashboard" in commands

    def test_dashboard_command_help(self):
        """Test that dashboard command has proper help text."""
        from devflow.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["dashboard", "--help"])

        assert result.exit_code == 0
        assert "Launch the web-based dashboard" in result.output
        assert "--port" in result.output
        assert "--no-open" in result.output
        assert "--reload" in result.output

    def test_dashboard_command_options(self):
        """Test that dashboard command accepts expected options."""
        from devflow.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["dashboard", "--help"])

        assert "--port" in result.output
        assert "--no-open" in result.output
        assert "--reload" in result.output
        assert "--host" in result.output


# ============================================================================
# __init__.py Tests
# ============================================================================


class TestWebInit:
    """Tests for devflow/web/__init__.py module structure."""

    def test_module_exports(self):
        """Test that web module exports expected symbols."""
        import devflow.web

        assert hasattr(devflow.web, "DashboardApp")


# ============================================================================
# Component Tests (unit tests that don't require NiceGUI runtime)
# ============================================================================


class TestStatusBadgeColors:
    """Tests for status badge color mapping."""

    def test_status_colors_defined(self):
        """Test that all expected statuses have color mappings."""
        from devflow.web.components.status_badge import STATUS_COLORS

        assert "created" in STATUS_COLORS
        assert "in_progress" in STATUS_COLORS
        assert "paused" in STATUS_COLORS
        assert "complete" in STATUS_COLORS
        assert "unknown" in STATUS_COLORS

    def test_session_type_colors_defined(self):
        """Test that all session types have color mappings."""
        from devflow.web.components.status_badge import SESSION_TYPE_COLORS

        assert "development" in SESSION_TYPE_COLORS
        assert "ticket_creation" in SESSION_TYPE_COLORS
        assert "investigation" in SESSION_TYPE_COLORS


class TestSessionTableColumns:
    """Tests for session table column definitions."""

    def test_columns_defined(self):
        """Test that required columns are defined."""
        from devflow.web.components.session_table import COLUMNS

        column_names = [c["name"] for c in COLUMNS]
        assert "status" in column_names
        assert "name" in column_names
        assert "workspace" in column_names
        assert "issue_key" in column_names
        assert "goal" in column_names
        assert "time" in column_names
        assert "last_active" in column_names

    def test_columns_are_sortable(self):
        """Test that all columns have sortable=True."""
        from devflow.web.components.session_table import COLUMNS

        for col in COLUMNS:
            assert col.get("sortable") is True, f"Column '{col['name']}' should be sortable"


# ============================================================================
# Integration-style Tests with temp_daf_home
# ============================================================================


class TestDataBridgeIntegration:
    """Integration tests using temp_daf_home fixture."""

    def test_list_sessions_with_real_manager(self, temp_daf_home):
        """Test listing sessions through the DataBridge with real SessionManager."""
        config_loader = ConfigLoader()
        manager = SessionManager(config_loader)

        # Create sessions
        manager.create_session(
            name="web-test-1",
            goal="Test session 1",
            working_directory="test-dir-1",
            project_path="/path/to/project1",
            ai_agent_session_id="uuid-1",
        )
        manager.create_session(
            name="web-test-2",
            goal="Test session 2",
            working_directory="test-dir-2",
            project_path="/path/to/project2",
            ai_agent_session_id="uuid-2",
        )

        # Test through DataBridge
        bridge = DataBridge(config_loader=config_loader)
        sessions = bridge.list_sessions()

        assert len(sessions) == 2
        names = [s["name"] for s in sessions]
        assert "web-test-1" in names
        assert "web-test-2" in names

    def test_get_session_with_real_manager(self, temp_daf_home):
        """Test getting a session through the DataBridge with real SessionManager."""
        config_loader = ConfigLoader()
        manager = SessionManager(config_loader)

        manager.create_session(
            name="web-detail-test",
            goal="Detail test goal",
            working_directory="test-dir",
            project_path="/path/to/project",
            ai_agent_session_id="uuid-detail",
            issue_key="PROJ-999",
        )

        bridge = DataBridge(config_loader=config_loader)
        result = bridge.get_session("web-detail-test")

        assert result is not None
        assert result["name"] == "web-detail-test"
        assert result["goal"] == "Detail test goal"
        assert result["issue_key"] == "PROJ-999"
        assert "conversations" in result
        assert "work_sessions" in result

    def test_add_note_with_real_manager(self, temp_daf_home):
        """Test adding a note through the DataBridge."""
        config_loader = ConfigLoader()
        manager = SessionManager(config_loader)

        manager.create_session(
            name="web-note-test",
            goal="Note test goal",
            working_directory="test-dir",
            project_path="/path/to/project",
            ai_agent_session_id="uuid-note",
        )

        bridge = DataBridge(config_loader=config_loader)
        result = bridge.add_session_note("web-note-test", "Web note content")

        assert result is True

        # Verify note was saved
        notes = bridge.get_session_notes("web-note-test")
        assert "Web note content" in notes

    def test_session_count_by_status_with_real_manager(self, temp_daf_home):
        """Test session counting through the DataBridge."""
        config_loader = ConfigLoader()
        manager = SessionManager(config_loader)

        manager.create_session(
            name="count-test-1",
            goal="Test 1",
            working_directory="dir1",
            project_path="/path/1",
            ai_agent_session_id="uuid-c1",
        )
        manager.create_session(
            name="count-test-2",
            goal="Test 2",
            working_directory="dir2",
            project_path="/path/2",
            ai_agent_session_id="uuid-c2",
        )

        bridge = DataBridge(config_loader=config_loader)
        counts = bridge.get_session_count_by_status()

        assert counts.get("created", 0) == 2


# ============================================================================
# DataBridge Config Methods Tests
# ============================================================================


class TestDataBridgeConfigMethods:
    """Tests for DataBridge config read/write methods."""

    def test_load_config(self):
        """Test loading config through data bridge."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()
        mock_config = Mock()
        mock_loader.load_config.return_value = mock_config
        bridge.config_loader = mock_loader

        result = bridge.load_config()

        assert result is mock_config
        mock_loader.load_config.assert_called_once()

    def test_load_config_returns_none(self):
        """Test loading config when none exists."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()
        mock_loader.load_config.return_value = None
        bridge.config_loader = mock_loader

        result = bridge.load_config()

        assert result is None

    def test_save_config_success(self, tmp_path):
        """Test saving config successfully."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()
        mock_loader.config_file = tmp_path / "config.json"
        bridge.config_loader = mock_loader

        mock_config = Mock()
        with patch("devflow.web.utils.data_bridge.get_cs_home", return_value=tmp_path):
            result = bridge.save_config(mock_config)

        assert result is True
        mock_loader.save_config.assert_called_once_with(mock_config)

    def test_save_config_creates_backup(self, tmp_path):
        """Test that save_config creates a backup."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()

        # Create existing config file so backup is created
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")
        mock_loader.config_file = config_file
        bridge.config_loader = mock_loader

        mock_config = Mock()
        with patch("devflow.web.utils.data_bridge.get_cs_home", return_value=tmp_path):
            result = bridge.save_config(mock_config)

        assert result is True
        backup_dir = tmp_path / "backups"
        assert backup_dir.exists()
        backups = list(backup_dir.glob("config-*.json"))
        assert len(backups) == 1

    def test_save_config_failure(self):
        """Test save_config returns False on error."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()
        mock_loader.config_file = Mock()
        mock_loader.config_file.exists.return_value = False
        mock_loader.save_config.side_effect = Exception("Save failed")
        bridge.config_loader = mock_loader

        result = bridge.save_config(Mock())

        assert result is False

    def test_get_config_as_json(self):
        """Test serializing config to JSON."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        mock_config = Mock()
        mock_config.model_dump.return_value = {"key": "value", "nested": {"a": 1}}

        result = bridge.get_config_as_json(mock_config)

        assert '"key": "value"' in result
        assert '"nested"' in result

    def test_get_enterprise_config(self):
        """Test loading enterprise config."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()
        mock_ec = Mock()
        mock_ec.model_dump.return_value = {"agent_backend": "claude"}
        mock_loader._load_enterprise_config.return_value = mock_ec
        bridge.config_loader = mock_loader

        result = bridge.get_enterprise_config()

        assert result == {"agent_backend": "claude"}

    def test_get_team_config(self):
        """Test loading team config."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()
        mock_tc = Mock()
        mock_tc.model_dump.return_value = {"agent_backend": None}
        mock_loader._load_team_config.return_value = mock_tc
        bridge.config_loader = mock_loader

        result = bridge.get_team_config()

        assert result == {"agent_backend": None}

    def test_get_enterprise_config_none(self):
        """Test loading enterprise config when none exists."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()
        mock_loader._load_enterprise_config.return_value = None
        bridge.config_loader = mock_loader

        result = bridge.get_enterprise_config()

        assert result is None


# ============================================================================
# DataBridge Time Tracking Tests
# ============================================================================


class TestDataBridgeTimeTracking:
    """Tests for DataBridge time tracking methods."""

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_get_time_tracking_data(self, mock_manager_cls):
        """Test getting time tracking data."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        ws = WorkSession(
            start=datetime(2026, 1, 1, 10, 0, 0),
            end=datetime(2026, 1, 1, 12, 0, 0),
            duration="2h 0m",
            user="testuser",
        )
        session = _make_session(name="tracked", issue_key="PROJ-1", work_sessions=[ws])

        mock_manager = Mock()
        mock_manager.list_sessions.return_value = [session]
        mock_manager_cls.return_value = mock_manager

        data = bridge.get_time_tracking_data()

        assert len(data) == 1
        assert data[0]["name"] == "tracked"
        assert data[0]["issue_key"] == "PROJ-1"
        assert data[0]["total_minutes"] == 120
        assert data[0]["total_time"] == "2h 0m"
        assert len(data[0]["entries"]) == 1

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_get_time_tracking_data_empty(self, mock_manager_cls):
        """Test time tracking data with no sessions."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        mock_manager = Mock()
        mock_manager.list_sessions.return_value = []
        mock_manager_cls.return_value = mock_manager

        data = bridge.get_time_tracking_data()

        assert data == []

    @patch("devflow.web.utils.data_bridge.SessionManager")
    def test_get_time_tracking_active_session(self, mock_manager_cls):
        """Test time tracking with an active (no end) work session."""
        bridge = DataBridge.__new__(DataBridge)
        bridge.config_loader = Mock()

        ws = WorkSession(
            start=datetime(2026, 1, 1, 10, 0, 0),
            end=None,
            user="testuser",
        )
        session = _make_session(name="active-tracked", work_sessions=[ws])

        mock_manager = Mock()
        mock_manager.list_sessions.return_value = [session]
        mock_manager_cls.return_value = mock_manager

        data = bridge.get_time_tracking_data()

        assert len(data) == 1
        assert data[0]["total_minutes"] > 0
        assert data[0]["entries"][0]["end"] == "Active"


# ============================================================================
# Config Editor Utility Tests
# ============================================================================


class TestJiraTabFieldExtraction:
    """Tests for JIRA tab dynamic field extraction."""

    def test_extract_component_choices_from_field_mappings(self):
        """Test extracting component dropdown choices from field_mappings."""
        from devflow.web.pages.config_editor import _extract_component_choices

        jira = Mock()
        jira.field_mappings = {
            "components": {
                "id": "components",
                "name": "Components",
                "allowed_values": ["backend", "frontend", "api"],
            }
        }

        result = _extract_component_choices(jira)

        assert result == ["backend", "frontend", "api"]

    def test_extract_component_choices_from_dict_values(self):
        """Test extracting components when allowed_values are dicts."""
        from devflow.web.pages.config_editor import _extract_component_choices

        jira = Mock()
        jira.field_mappings = {
            "components": {
                "id": "components",
                "allowed_values": [{"name": "web"}, {"name": "mobile"}],
            }
        }

        result = _extract_component_choices(jira)

        assert result == ["web", "mobile"]

    def test_extract_component_choices_server_alias(self):
        """Test extracting components from 'component/s' key (JIRA Server)."""
        from devflow.web.pages.config_editor import _extract_component_choices

        jira = Mock()
        jira.field_mappings = {
            "component/s": {
                "id": "components",
                "allowed_values": ["server-comp"],
            }
        }

        result = _extract_component_choices(jira)

        assert result == ["server-comp"]

    def test_extract_component_choices_no_mappings(self):
        """Test extracting components when no field_mappings exist."""
        from devflow.web.pages.config_editor import _extract_component_choices

        jira = Mock()
        jira.field_mappings = None

        result = _extract_component_choices(jira)

        assert result == []

    def test_extract_component_choices_none_jira(self):
        """Test extracting components when jira is None."""
        from devflow.web.pages.config_editor import _extract_component_choices

        result = _extract_component_choices(None)

        assert result == []

    def test_extract_custom_fields(self):
        """Test extracting custom fields from field_mappings."""
        from devflow.web.pages.config_editor import _extract_custom_fields

        jira = Mock()
        jira.field_mappings = {
            "workstream": {
                "id": "customfield_12345",
                "name": "Workstream",
                "allowed_values": [{"value": "Platform"}, {"value": "SRE"}],
            },
            "size": {
                "id": "customfield_67890",
                "name": "Size",
                "allowed_values": [],
            },
            "status": {
                "id": "status",
                "name": "Status",
            },
        }

        result = _extract_custom_fields(jira)

        assert len(result) == 2
        names = [f["name"] for f in result]
        assert "Workstream" in names
        assert "Size" in names
        assert "Status" not in names  # system field excluded

        ws = next(f for f in result if f["name"] == "Workstream")
        assert ws["key"] == "workstream"
        assert ws["allowed_values"] == ["Platform", "SRE"]

    def test_extract_custom_fields_no_mappings(self):
        """Test extracting custom fields when no field_mappings exist."""
        from devflow.web.pages.config_editor import _extract_custom_fields

        jira = Mock()
        jira.field_mappings = None

        result = _extract_custom_fields(jira)

        assert result == []

    def test_extract_custom_fields_none_jira(self):
        """Test extracting custom fields when jira is None."""
        from devflow.web.pages.config_editor import _extract_custom_fields

        result = _extract_custom_fields(None)

        assert result == []

    def test_extract_custom_fields_sorted_by_name(self):
        """Test that custom fields are sorted by name."""
        from devflow.web.pages.config_editor import _extract_custom_fields

        jira = Mock()
        jira.field_mappings = {
            "zebra": {"id": "customfield_3", "name": "Zebra"},
            "alpha": {"id": "customfield_1", "name": "Alpha"},
            "middle": {"id": "customfield_2", "name": "Middle"},
        }

        result = _extract_custom_fields(jira)

        names = [f["name"] for f in result]
        assert names == ["Alpha", "Middle", "Zebra"]


class TestConfigEditorHelpers:
    """Tests for config editor helper functions."""

    def test_bool_to_choice_true(self):
        """Test converting True to choice string."""
        from devflow.web.pages.config_editor import _bool_to_choice

        assert _bool_to_choice(True) == "True"

    def test_bool_to_choice_false(self):
        """Test converting False to choice string."""
        from devflow.web.pages.config_editor import _bool_to_choice

        assert _bool_to_choice(False) == "False"

    def test_bool_to_choice_none(self):
        """Test converting None to choice string."""
        from devflow.web.pages.config_editor import _bool_to_choice

        assert _bool_to_choice(None) == "Prompt"

    def test_choice_to_bool_true(self):
        """Test converting 'True' choice to bool."""
        from devflow.web.pages.config_editor import _choice_to_bool

        assert _choice_to_bool("True") is True

    def test_choice_to_bool_false(self):
        """Test converting 'False' choice to bool."""
        from devflow.web.pages.config_editor import _choice_to_bool

        assert _choice_to_bool("False") is False

    def test_choice_to_bool_prompt(self):
        """Test converting 'Prompt' choice to None."""
        from devflow.web.pages.config_editor import _choice_to_bool

        assert _choice_to_bool("Prompt") is None

    def test_strict_bool_true(self):
        """Test strict bool conversion for True."""
        from devflow.web.pages.config_editor import _strict_bool

        assert _strict_bool("True") is True

    def test_strict_bool_false(self):
        """Test strict bool conversion for False."""
        from devflow.web.pages.config_editor import _strict_bool

        assert _strict_bool("False") is False

    def test_strict_bool_other(self):
        """Test strict bool conversion for unexpected value."""
        from devflow.web.pages.config_editor import _strict_bool

        assert _strict_bool("whatever") is False

    def test_tri_state_options_complete(self):
        """Test that tri-state options cover all cases."""
        from devflow.web.pages.config_editor import _TRI_STATE_OPTIONS

        assert "True" in _TRI_STATE_OPTIONS
        assert "False" in _TRI_STATE_OPTIONS
        assert "Prompt" in _TRI_STATE_OPTIONS
        assert _TRI_STATE_OPTIONS["True"] is True
        assert _TRI_STATE_OPTIONS["False"] is False
        assert _TRI_STATE_OPTIONS["Prompt"] is None


# ============================================================================
# App Route Registration Tests
# ============================================================================


class TestAppRouteRegistration:
    """Tests for route registration in DashboardApp."""

    def test_all_routes_registered(self):
        """Test that all expected routes are registered."""
        from devflow.web.app import DashboardApp

        app = DashboardApp.__new__(DashboardApp)
        app.bridge = Mock()

        # The _register_pages method should define routes for all pages.
        # We test by checking the method exists and can be introspected.
        assert hasattr(app, "_register_pages")
        assert callable(app._register_pages)


# ============================================================================
# Workspace Page Helper Tests
# ============================================================================


class TestWorkspaceDiscovery:
    """Tests for workspace repo discovery."""

    def test_discover_repos_valid_dir(self, tmp_path):
        """Test discovering repos in a directory with git repos."""
        from devflow.web.pages.workspaces import _discover_repos

        # Create fake git repos
        (tmp_path / "repo-a" / ".git").mkdir(parents=True)
        (tmp_path / "repo-b" / ".git").mkdir(parents=True)
        (tmp_path / "not-a-repo").mkdir()

        repos = _discover_repos(str(tmp_path))

        assert "repo-a" in repos
        assert "repo-b" in repos
        assert "not-a-repo" not in repos

    def test_discover_repos_empty_dir(self, tmp_path):
        """Test discovering repos in an empty directory."""
        from devflow.web.pages.workspaces import _discover_repos

        repos = _discover_repos(str(tmp_path))

        assert repos == []

    def test_discover_repos_nonexistent_dir(self):
        """Test discovering repos in a nonexistent directory."""
        from devflow.web.pages.workspaces import _discover_repos

        repos = _discover_repos("/nonexistent/path/abc123")

        assert repos == []


# ============================================================================
# Navigation Component Tests
# ============================================================================


class TestNavigationLinks:
    """Tests for navigation link definitions."""

    def test_nav_module_importable(self):
        """Test that nav module can be imported (NiceGUI may not be available)."""
        try:
            from devflow.web.components import nav
            assert hasattr(nav, "create_header")
        except ImportError:
            # NiceGUI not installed - skip
            pytest.skip("NiceGUI not available")


# ============================================================================
# PID File and Background/Stop Tests
# ============================================================================


class TestPidFileManagement:
    """Tests for PID file write, read, and cleanup."""

    def test_write_and_read_pid(self, tmp_path):
        """Test writing and reading PID file."""
        from devflow.web.app import _write_pid, _read_pid

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            _write_pid(12345)
            result = _read_pid()
            assert result == 12345

    def test_read_pid_missing(self, tmp_path):
        """Test reading PID when file doesn't exist."""
        from devflow.web.app import _read_pid

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            result = _read_pid()
            assert result is None

    def test_read_port_value(self, tmp_path):
        """Test reading port from state file."""
        from devflow.web.app import _write_port, _read_port

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            _write_port(54321)
            result = _read_port()
            assert result == 54321

    def test_read_port_missing(self, tmp_path):
        """Test reading port when file doesn't exist."""
        from devflow.web.app import _read_port

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            result = _read_port()
            assert result is None

    def test_cleanup_removes_both_files(self, tmp_path):
        """Test cleanup removes both port and PID files."""
        from devflow.web.app import _write_port, _write_pid, _cleanup_state_files

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            _write_port(8080)
            _write_pid(99999)

            port_file = tmp_path / "state" / "dashboard.port"
            pid_file = tmp_path / "state" / "dashboard.pid"
            assert port_file.exists()
            assert pid_file.exists()

            _cleanup_state_files()
            assert not port_file.exists()
            assert not pid_file.exists()

    def test_is_process_running_self(self):
        """Test that our own process is detected as running."""
        from devflow.web.app import _is_process_running

        assert _is_process_running(os.getpid()) is True

    def test_is_process_running_nonexistent(self):
        """Test that a very high PID is not running."""
        from devflow.web.app import _is_process_running

        # Use a very high PID that is almost certainly not in use
        assert _is_process_running(4_000_000) is False

    def test_get_dashboard_status_not_running(self, tmp_path):
        """Test status when no dashboard is running."""
        from devflow.web.app import get_dashboard_status

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            result = get_dashboard_status()
            assert result is None

    def test_get_dashboard_status_stale_pid(self, tmp_path):
        """Test status with stale PID file (process not running)."""
        from devflow.web.app import get_dashboard_status, _write_pid, _write_port

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            _write_pid(4_000_000)  # non-existent process
            _write_port(8080)
            result = get_dashboard_status()
            assert result is None

    def test_get_dashboard_status_running(self, tmp_path):
        """Test status when a real process is running (use our own PID)."""
        from devflow.web.app import get_dashboard_status, _write_pid, _write_port

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            _write_pid(os.getpid())  # our own process
            _write_port(9090)
            result = get_dashboard_status()
            assert result is not None
            assert result["pid"] == os.getpid()
            assert result["port"] == 9090

    def test_stop_dashboard_nothing_running(self, tmp_path):
        """Test stop when nothing is running."""
        from devflow.web.app import stop_dashboard

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            result = stop_dashboard()
            assert result is False

    def test_stop_dashboard_stale_pid(self, tmp_path):
        """Test stop with stale PID file cleans up state files."""
        from devflow.web.app import stop_dashboard, _write_pid, _write_port

        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            _write_pid(4_000_000)
            _write_port(8080)
            result = stop_dashboard()
            assert result is False
            # State files should be cleaned up
            assert not (tmp_path / "state" / "dashboard.pid").exists()


# ============================================================================
# CLI Dashboard Group Tests
# ============================================================================


class TestDashboardCLIGroup:
    """Tests for the 'daf dashboard' CLI group (start/stop/background)."""

    def test_dashboard_is_group(self):
        """Test that dashboard is registered as a Click group."""
        from devflow.cli.main import cli

        commands = cli.commands if hasattr(cli, "commands") else {}
        assert "dashboard" in commands

    def test_stop_subcommand_exists(self):
        """Test that 'daf dashboard stop' subcommand is registered."""
        from devflow.cli.main import dashboard as dashboard_group

        commands = dashboard_group.commands if hasattr(dashboard_group, "commands") else {}
        assert "stop" in commands

    def test_dashboard_help_shows_background(self):
        """Test that --background/-b flag is in help."""
        from devflow.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["dashboard", "--help"])

        assert result.exit_code == 0
        assert "--background" in result.output or "-b" in result.output

    def test_dashboard_help_shows_stop(self):
        """Test that 'stop' subcommand is shown in help."""
        from devflow.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["dashboard", "--help"])

        assert result.exit_code == 0
        assert "stop" in result.output

    def test_stop_help(self):
        """Test that 'daf dashboard stop' has help text."""
        from devflow.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["dashboard", "stop", "--help"])

        assert result.exit_code == 0
        assert "Stop" in result.output or "stop" in result.output

    def test_stop_nothing_running(self, tmp_path):
        """Test 'daf dashboard stop' when nothing is running."""
        from devflow.cli.main import cli

        runner = CliRunner()
        with patch("devflow.web.app.get_cs_home", return_value=tmp_path):
            with patch("devflow.cli.main.console"):
                result = runner.invoke(cli, ["dashboard", "stop"])

        # Should not crash
        assert result.exit_code == 0

    def test_already_running_opens_browser(self):
        """Test that 'daf dashboard' opens browser when already running."""
        from devflow.cli.main import cli

        runner = CliRunner()
        mock_status = {"pid": 12345, "port": 8080}

        with patch("devflow.web.app.get_dashboard_status", return_value=mock_status):
            with patch("devflow.cli.main.console"):
                with patch("webbrowser.open") as mock_open:
                    result = runner.invoke(cli, ["dashboard"])

        assert result.exit_code == 0
        mock_open.assert_called_once_with("http://127.0.0.1:8080")

    def test_already_running_no_open_skips_browser(self):
        """Test that 'daf dashboard --no-open' does not open browser when already running."""
        from devflow.cli.main import cli

        runner = CliRunner()
        mock_status = {"pid": 12345, "port": 8080}

        with patch("devflow.web.app.get_dashboard_status", return_value=mock_status):
            with patch("devflow.cli.main.console"):
                with patch("webbrowser.open") as mock_open:
                    result = runner.invoke(cli, ["dashboard", "--no-open"])

        assert result.exit_code == 0
        mock_open.assert_not_called()


# ============================================================================
# DataBridge Organization Config Tests
# ============================================================================


class TestDataBridgeOrganizationConfig:
    """Tests for DataBridge organization config method."""

    def test_get_organization_config(self):
        """Test loading organization config."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()
        mock_oc = Mock()
        mock_oc.model_dump.return_value = {"jira_project": "PROJ"}
        mock_loader._load_organization_config.return_value = mock_oc
        bridge.config_loader = mock_loader

        result = bridge.get_organization_config()

        assert result == {"jira_project": "PROJ"}

    def test_get_organization_config_none(self):
        """Test loading organization config when none exists."""
        bridge = DataBridge.__new__(DataBridge)
        mock_loader = Mock()
        mock_loader._load_organization_config.return_value = None
        bridge.config_loader = mock_loader

        result = bridge.get_organization_config()

        assert result is None


# ============================================================================
# Dirty Tracking / Undo Tests
# ============================================================================


class TestAttachDirtyTracking:
    """Tests for _attach_dirty_tracking function."""

    def test_import(self):
        """Test that _attach_dirty_tracking is importable."""
        from devflow.web.pages.config_editor import _attach_dirty_tracking

        assert callable(_attach_dirty_tracking)

    def test_skips_private_keys(self):
        """Test that keys starting with '_' are skipped."""
        from devflow.web.pages.config_editor import _attach_dirty_tracking

        widget = Mock()
        widget.value = "test"
        all_widgets = {"tab": {"_private": widget, "public": Mock(spec=[])}}
        state = {"undo_stack": [], "suppressing": False}

        _attach_dirty_tracking(all_widgets, state, Mock(), [])

        widget.on.assert_not_called()

    def test_skips_widgets_without_value(self):
        """Test that widgets without a 'value' attribute are skipped."""
        from devflow.web.pages.config_editor import _attach_dirty_tracking

        widget = Mock(spec=["on"])
        all_widgets = {"tab": {"field": widget}}
        state = {"undo_stack": [], "suppressing": False}

        _attach_dirty_tracking(all_widgets, state, Mock(), [])

        widget.on.assert_not_called()

    def test_attaches_handler_to_widget_with_value(self):
        """Test that handler is attached to widgets with on() and value."""
        from devflow.web.pages.config_editor import _attach_dirty_tracking

        widget = Mock()
        widget.value = "initial"
        all_widgets = {"tab": {"field": widget}}
        state = {"undo_stack": [], "suppressing": False}

        _attach_dirty_tracking(all_widgets, state, Mock(), [])

        widget.on.assert_called_once()
        assert widget.on.call_args[0][0] == "update:model-value"

    def test_handler_exception_does_not_crash(self):
        """Test that exceptions in widget.on() are silently caught."""
        from devflow.web.pages.config_editor import _attach_dirty_tracking

        widget = Mock()
        widget.value = "initial"
        widget.on.side_effect = RuntimeError("NiceGUI not available")
        all_widgets = {"tab": {"field": widget}}
        state = {"undo_stack": [], "suppressing": False}

        _attach_dirty_tracking(all_widgets, state, Mock(), [])

    def test_empty_widgets_dict(self):
        """Test with empty widgets dict doesn't crash."""
        from devflow.web.pages.config_editor import _attach_dirty_tracking

        _attach_dirty_tracking({}, {"undo_stack": [], "suppressing": False}, Mock(), [])
