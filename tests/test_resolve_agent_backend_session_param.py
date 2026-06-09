"""Tests for resolve_agent_backend() receiving session parameter.

Regression tests for issue #500: resolve_agent_backend() was called with
only config=config at multiple call sites, missing session=session. This
caused the backend to fall back to the config default instead of using the
session's actual agent_backend.
"""

from devflow.agent.factory import resolve_agent_backend
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def _create_test_session(session_manager, name="backend-test", agent_backend="claude"):
    """Create a test session with a specific agent_backend."""
    session = session_manager.create_session(
        name=name,
        goal="Test backend resolution",
        working_directory="test-dir",
        project_path="/test",
        ai_agent_session_id="uuid-backend-1",
    )
    session.agent_backend = agent_backend
    session_manager.update_session(session)
    return session


def test_update_command_passes_session_to_resolve_agent_backend(temp_daf_home, monkeypatch, capsys):
    """Test that update_command passes session to resolve_agent_backend.

    Regression test for issue #500.
    """
    from devflow.cli.commands.update_command import update_session

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    _create_test_session(session_manager, name="update-test", agent_backend="claude")
    session_manager.start_work_session("update-test")

    calls = []
    original_resolve = resolve_agent_backend

    def tracking_resolve(**kwargs):
        calls.append(kwargs)
        return original_resolve(**kwargs)

    monkeypatch.setattr(
        "devflow.cli.commands.update_command.resolve_agent_backend",
        tracking_resolve,
    )

    update_session("update-test", ai_agent_session_id="new-uuid-123")

    assert len(calls) > 0, "resolve_agent_backend should have been called"
    for i, call in enumerate(calls):
        assert "session" in call, (
            f"Call #{i+1} to resolve_agent_backend missing session parameter: {call}"
        )
        assert call["session"] is not None, (
            f"Call #{i+1} to resolve_agent_backend passed session=None"
        )


def test_summary_command_passes_session_to_resolve_agent_backend(temp_daf_home, monkeypatch, capsys):
    """Test that summary_command passes session to resolve_agent_backend.

    Regression test for issue #500.
    """
    from devflow.cli.commands.summary_command import show_summary

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = _create_test_session(session_manager, name="summary-test", agent_backend="claude")
    session_manager.start_work_session("summary-test")

    calls = []
    original_resolve = resolve_agent_backend

    def tracking_resolve(**kwargs):
        calls.append(kwargs)
        return original_resolve(**kwargs)

    monkeypatch.setattr(
        "devflow.cli.commands.summary_command.resolve_agent_backend",
        tracking_resolve,
    )

    show_summary("summary-test")

    # resolve_agent_backend is only called when conversation has data and prose summary is generated
    # If called, it must pass session
    for i, call in enumerate(calls):
        assert "session" in call, (
            f"Call #{i+1} to resolve_agent_backend missing session parameter: {call}"
        )
        assert call["session"] is not None, (
            f"Call #{i+1} to resolve_agent_backend passed session=None"
        )


def test_markdown_exporter_passes_session_to_resolve_agent_backend(temp_daf_home, monkeypatch):
    """Test that MarkdownExporter passes session to resolve_agent_backend.

    Regression test for issue #500: _format_session_activity and _format_statistics
    both call resolve_agent_backend.
    """
    from devflow.export.markdown import MarkdownExporter

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session = _create_test_session(session_manager, name="export-test", agent_backend="claude")

    calls = []
    original_resolve = resolve_agent_backend

    def tracking_resolve(**kwargs):
        calls.append(kwargs)
        return original_resolve(**kwargs)

    monkeypatch.setattr(
        "devflow.export.markdown.resolve_agent_backend",
        tracking_resolve,
    )

    exporter = MarkdownExporter(config_loader=config_loader)
    exporter.export_session_to_markdown(session, include_activity=True, include_statistics=True)

    # resolve_agent_backend is called from _format_session_activity and _format_statistics
    for i, call in enumerate(calls):
        assert "session" in call, (
            f"Call #{i+1} to resolve_agent_backend missing session parameter: {call}"
        )
        assert call["session"] is not None, (
            f"Call #{i+1} to resolve_agent_backend passed session=None"
        )


def test_import_session_passes_session_to_resolve_agent_backend(temp_daf_home, monkeypatch, capsys):
    """Test that import_session passes session to resolve_agent_backend.

    Regression test for issue #500.
    """
    from datetime import datetime
    from devflow.cli.commands.import_session_command import import_session
    from devflow.session.discovery import DiscoveredSession

    mock_discovered = DiscoveredSession(
        uuid="uuid-discovered-1",
        project_path="/test",
        message_count=5,
        created=datetime.now(),
        last_active=datetime.now(),
        working_directory="test-dir",
    )

    calls = []
    original_resolve = resolve_agent_backend

    def tracking_resolve(**kwargs):
        calls.append(kwargs)
        return original_resolve(**kwargs)

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.resolve_agent_backend",
        tracking_resolve,
    )

    # Mock SessionDiscovery to return our test session
    class MockDiscovery:
        def discover_sessions(self):
            return [mock_discovered]

    monkeypatch.setattr(
        "devflow.cli.commands.import_session_command.SessionDiscovery",
        lambda: MockDiscovery(),
    )

    import_session(
        uuid="uuid-discovered-1",
        issue_key="IMPORT-123",
        goal="Test import",
        path="/test",
        yes=True,
    )

    assert len(calls) > 0, "resolve_agent_backend should have been called"
    for i, call in enumerate(calls):
        assert "session" in call, (
            f"Call #{i+1} to resolve_agent_backend missing session parameter: {call}"
        )
        assert call["session"] is not None, (
            f"Call #{i+1} to resolve_agent_backend passed session=None"
        )
