"""Tests for daf import command with improved prompt clarity (PROJ-61022)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.cli.commands.import_command import import_sessions
from devflow.config.loader import ConfigLoader
from devflow.export.manager import ExportManager
from devflow.session.manager import SessionManager


@pytest.fixture
def export_with_sessions(temp_daf_home):
    """Create an export file with test sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create test sessions
    session_manager.create_session(
        name="PROJ-11111",
        issue_key="PROJ-11111",
        goal="First session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="PROJ-22222",
        issue_key="PROJ-22222",
        goal="Second session",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    # Export sessions
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    # Delete the sessions so tests can recreate them to simulate conflicts
    # This is needed because session groups are removed - each session must have unique name
    session_manager.delete_session("PROJ-11111")
    session_manager.delete_session("PROJ-22222")

    return export_path


def test_import_shows_export_contents(temp_daf_home, export_with_sessions, capsys, monkeypatch):
    """Test that import displays export file contents before prompting."""
    # Mock Confirm.ask to cancel import
    monkeypatch.setattr("devflow.cli.commands.import_command.Confirm.ask", lambda *args, **kwargs: False)

    # Run import
    import_sessions(str(export_with_sessions))

    # Check output
    captured = capsys.readouterr()
    assert "Export file contains:" in captured.out
    assert "Sessions: 2" in captured.out
    assert "PROJ-11111" in captured.out
    assert "PROJ-22222" in captured.out

    # Cleanup
    export_with_sessions.unlink()


def test_import_shows_conflicts_merge_mode(temp_daf_home, export_with_sessions, capsys, monkeypatch):
    """Test that import shows conflicts in merge mode."""
    # Create a conflicting session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session_manager.create_session(
        name="PROJ-11111",
        issue_key="PROJ-11111",
        goal="Existing session",
        working_directory="existing-dir",
        project_path="/existing-path",
        ai_agent_session_id="existing-uuid",
    )

    # Mock Confirm.ask to cancel import
    monkeypatch.setattr("devflow.cli.commands.import_command.Confirm.ask", lambda *args, **kwargs: False)

    # Run import in merge mode
    import_sessions(str(export_with_sessions), merge=True)

    # Check output
    captured = capsys.readouterr()
    assert "Existing sessions found: PROJ-11111" in captured.out
    assert "will be skipped" in captured.out
    assert "existing sessions preserved" in captured.out.lower()

    # Cleanup
    export_with_sessions.unlink()


def test_import_shows_conflicts_replace_mode(temp_daf_home, export_with_sessions, capsys, monkeypatch):
    """Test that import shows conflicts in replace mode."""
    # Create a conflicting session (both PROJ-11111 and PROJ-22222 will conflict)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    session_manager.create_session(
        name="PROJ-11111",
        issue_key="PROJ-11111",
        goal="Existing session",
        working_directory="existing-dir",
        project_path="/existing-path",
        ai_agent_session_id="existing-uuid",
    )

    session_manager.create_session(
        name="PROJ-22222",
        issue_key="PROJ-22222",
        goal="Second existing session",
        working_directory="existing-dir2",
        project_path="/existing-path2",
        ai_agent_session_id="existing-uuid2",
    )

    # Mock Confirm.ask to cancel import
    monkeypatch.setattr("devflow.cli.commands.import_command.Confirm.ask", lambda *args, **kwargs: False)

    # Run import in replace mode
    import_sessions(str(export_with_sessions), merge=False)

    # Check output
    captured = capsys.readouterr()
    assert "Existing sessions found: PROJ-11111, PROJ-22222" in captured.out
    assert "OVERWRITTEN" in captured.out

    # Cleanup
    export_with_sessions.unlink()


def test_import_no_conflicts(temp_daf_home, capsys, monkeypatch):
    """Test import prompt when there are no conflicts."""
    # Create a fresh export without existing sessions in target
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create sessions
    session_manager.create_session(
        name="PROJ-33333",
        issue_key="PROJ-33333",
        goal="Fresh session",
        working_directory="fresh-dir",
        project_path="/fresh-path",
        ai_agent_session_id="fresh-uuid",
    )

    # Export sessions
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    # Delete the session to simulate importing to a different machine
    session_manager.delete_session("PROJ-33333")

    # Mock Confirm.ask to cancel import
    monkeypatch.setattr("devflow.cli.commands.import_command.Confirm.ask", lambda *args, **kwargs: False)

    # Run import (no existing sessions)
    import_sessions(str(export_path), merge=True)

    # Check output
    captured = capsys.readouterr()
    assert "Export file contains:" in captured.out
    assert "PROJ-33333" in captured.out
    # Should not show conflict warnings
    assert "Existing sessions found" not in captured.out

    # Cleanup
    export_path.unlink()


def test_import_force_skips_prompt(temp_daf_home, export_with_sessions, capsys):
    """Test that --force flag skips confirmation prompt."""
    # Run import with force flag
    import_sessions(str(export_with_sessions), force=True)

    # Check that import proceeded
    captured = capsys.readouterr()
    assert "Importing sessions..." in captured.out
    assert "Import completed successfully" in captured.out
    # Should still show export contents
    assert "Export file contains:" in captured.out

    # Cleanup
    export_with_sessions.unlink()


def test_import_file_not_found(temp_daf_home, capsys):
    """Test import with non-existent file."""
    import_sessions("/nonexistent/export.tar.gz")

    captured = capsys.readouterr()
    assert "Export file not found" in captured.out


def test_import_invalid_file(temp_daf_home, capsys, tmp_path):
    """Test import with invalid export file."""
    # Create invalid file
    invalid_file = tmp_path / "invalid.tar.gz"
    invalid_file.write_text("not a valid tar file")

    import_sessions(str(invalid_file))

    captured = capsys.readouterr()
    assert "Failed to read export file" in captured.out
