"""Tests for export/import manager."""

import json
import tarfile
from pathlib import Path

import pytest

from devflow.config.loader import ConfigLoader
from devflow.export.manager import ExportManager
from devflow.session.manager import SessionManager


def test_export_manager_init(temp_daf_home):
    """Test ExportManager initialization."""
    manager = ExportManager()
    assert manager.config_loader is not None

    # Test with provided config loader
    config_loader = ConfigLoader()
    manager = ExportManager(config_loader)
    assert manager.config_loader is config_loader


def test_export_all_sessions(temp_daf_home):
    """Test exporting all sessions."""
    # Create some sessions
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="session1",
        goal="First session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="session2",
        goal="Second session",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    # Export all sessions
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    assert export_path.exists()
    assert export_path.suffix == ".gz"
    # Multiple sessions export uses "Nsessions-session-export.tar.gz" format
    assert "2sessions-session-export.tar.gz" == export_path.name

    # Verify tar contents
    with tarfile.open(export_path, "r:gz") as tar:
        members = tar.getnames()
        assert "export-metadata.json" in members
        assert "sessions.json" in members

    # Cleanup
    export_path.unlink()


def test_export_specific_sessions(temp_daf_home):
    """Test exporting specific sessions by identifier."""
    # Create sessions
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="export-me",
        goal="Export this",
        working_directory="export-dir",
        project_path="/path1",
        ai_agent_session_id="uuid-export",
    )

    session_manager.create_session(
        name="keep-me",
        goal="Don't export",
        working_directory="keep-dir",
        project_path="/path2",
        ai_agent_session_id="uuid-keep",
    )

    # Export only "export-me"
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["export-me"])

    assert export_path.exists()
    # Single session without issue key uses "session-name-session-export.tar.gz" format
    assert export_path.name == "export-me-session-export.tar.gz"

    # Verify only "export-me" is in the export
    with tarfile.open(export_path, "r:gz") as tar:
        # Extract sessions.json
        sessions_file = tar.extractfile("sessions.json")
        sessions_data = json.load(sessions_file)

        assert "export-me" in sessions_data
        assert "keep-me" not in sessions_data

    # Cleanup
    export_path.unlink()


def test_export_with_custom_output_path(temp_daf_home):
    """Test export with custom output path."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Export with custom path
    export_manager = ExportManager(config_loader)
    custom_path = temp_daf_home / "my-export.tar.gz"
    export_path = export_manager.export_sessions(output_path=custom_path)

    assert export_path == custom_path
    assert export_path.exists()

    # Cleanup
    export_path.unlink()


def test_export_no_sessions_raises_error(temp_daf_home):
    """Test that exporting with no sessions raises error."""
    export_manager = ExportManager()

    with pytest.raises(ValueError, match="No sessions found to export"):
        export_manager.export_sessions()


def test_export_nonexistent_identifier_raises_error(temp_daf_home):
    """Test exporting nonexistent identifier raises error."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="existing",
        goal="Exists",
        working_directory="dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Try to export nonexistent session
    export_manager = ExportManager(config_loader)

    with pytest.raises(ValueError, match="No sessions found to export"):
        export_manager.export_sessions(identifiers=["nonexistent"])


def test_export_includes_metadata(temp_daf_home):
    """Test that export includes proper metadata."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test",
        goal="Test",
        working_directory="dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Export
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    # Check metadata
    with tarfile.open(export_path, "r:gz") as tar:
        metadata_file = tar.extractfile("export-metadata.json")
        metadata = json.load(metadata_file)

        assert metadata["version"] == "1.0"
        assert "created" in metadata
        assert metadata["session_count"] == 1
        # Conversations are now always included for team handoff
        assert metadata["includes_conversations"] is True

    # Cleanup
    export_path.unlink()


def test_import_sessions(temp_daf_home):
    """Test importing sessions."""
    # Create and export sessions
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="import-test",
        goal="Import this",
        working_directory="import-dir",
        project_path="/import-path",
        ai_agent_session_id="uuid-import",
    )

    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["import-test"])

    # Import with merge=False to replace (since it already exists)
    imported_keys = export_manager.import_sessions(export_path, merge=False)

    assert "import-test" in imported_keys

    # Reload session manager to see imported sessions
    imported_manager = SessionManager(config_loader)
    imported_sessions = imported_manager.index.get_sessions("import-test")
    assert len(imported_sessions) >= 1
    assert any(s.goal == "Import this" for s in imported_sessions)

    # Cleanup
    export_path.unlink()


def test_import_nonexistent_file_raises_error(temp_daf_home):
    """Test importing nonexistent file raises error."""
    export_manager = ExportManager()
    nonexistent_path = Path("/nonexistent/export.tar.gz")

    with pytest.raises(FileNotFoundError, match="Export file not found"):
        export_manager.import_sessions(nonexistent_path)


def test_import_invalid_export_file_raises_error(temp_daf_home):
    """Test importing invalid export file raises error."""
    # Create invalid tar file (missing sessions.json)
    invalid_export = temp_daf_home / "invalid-export.tar.gz"

    with tarfile.open(invalid_export, "w:gz") as tar:
        # Add only metadata, no sessions.json
        import io
        metadata = {"version": "1.0"}
        json_str = json.dumps(metadata)
        json_bytes = json_str.encode("utf-8")

        tarinfo = tarfile.TarInfo(name="export-metadata.json")
        tarinfo.size = len(json_bytes)
        tar.addfile(tarinfo, io.BytesIO(json_bytes))

    export_manager = ExportManager()

    with pytest.raises(ValueError, match="Invalid export file: sessions.json not found"):
        export_manager.import_sessions(invalid_export)

    # Cleanup
    invalid_export.unlink()


def test_import_merge_mode(temp_daf_home):
    """Test importing with merge=True (default)."""
    # Create existing session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="existing",
        goal="Already exists",
        working_directory="existing-dir",
        project_path="/existing",
        ai_agent_session_id="uuid-existing",
    )

    # Create and export different session
    session_manager.create_session(
        name="new-session",
        goal="Will be imported",
        working_directory="new-dir",
        project_path="/new",
        ai_agent_session_id="uuid-new",
    )

    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["new-session"])

    # Delete the new session
    session_manager.delete_session("new-session")

    # Import with merge=True
    export_manager.import_sessions(export_path, merge=True)

    # Reload session manager to see imported sessions
    session_manager = SessionManager(config_loader)

    # Both sessions should exist
    existing_sessions = session_manager.index.get_sessions("existing")
    new_sessions = session_manager.index.get_sessions("new-session")

    assert len(existing_sessions) == 1
    assert len(new_sessions) == 1

    # Cleanup
    export_path.unlink()


def test_import_replace_mode(temp_daf_home):
    """Test importing with merge=False (replace mode)."""
    # Create and export a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="replace-me",
        goal="Original version",
        working_directory="orig-dir",
        project_path="/orig",
        ai_agent_session_id="uuid-orig",
    )

    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    # Modify the session
    sessions = session_manager.index.get_sessions("replace-me")
    session = sessions[0]
    session.goal = "Modified version"
    session_manager.update_session(session)

    # Import with merge=False (should replace)
    export_manager.import_sessions(export_path, merge=False)

    # Reload to see changes
    session_manager = SessionManager(config_loader)

    # Session should have original goal
    imported = session_manager.index.get_sessions("replace-me")
    assert imported[0].goal == "Original version"

    # Cleanup
    export_path.unlink()


def test_encode_path(temp_daf_home):
    """Test path encoding method."""
    export_manager = ExportManager()

    assert export_manager._encode_path("/path/to/project") == "-path-to-project"
    assert export_manager._encode_path("/home/user/code") == "-home-user-code"


def test_find_conversation_file_not_found(temp_daf_home):
    """Test finding conversation file when it doesn't exist."""
    export_manager = ExportManager()

    result = export_manager._find_conversation_file("nonexistent-uuid")
    assert result is None


def test_create_export_data(temp_daf_home):
    """Test export data creation."""
    from datetime import datetime
    from devflow.config.models import Session

    session1 = Session(        name="test1",
        goal="Goal 1",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
        created_at=datetime.now(),
    )

    session2 = Session(        name="test2",
        goal="Goal 2",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
        created_at=datetime.now(),
    )

    sessions = {
        "test1": session1,
        "test2": session2,
    }

    export_manager = ExportManager()
    export_data = export_manager._create_export_data(sessions)

    assert export_data["metadata"]["version"] == "1.0"
    assert export_data["metadata"]["session_count"] == 2
    # Conversations are always included for team handoff
    assert export_data["metadata"]["includes_conversations"] is True
    assert "test1" in export_data["sessions"]
    assert "test2" in export_data["sessions"]


def test_export_excludes_diagnostic_logs(temp_daf_home):
    """Test that export EXCLUDES diagnostic logs for privacy (PROJ-60802).

    Diagnostic logs are global files containing information from ALL sessions.
    Session exports are for team handoffs and should only include session-specific data.
    For full system backups with diagnostic logs, use 'daf backup' instead.
    """
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Create some diagnostic logs
    logs_dir = temp_daf_home / "logs"
    logs_dir.mkdir(exist_ok=True)

    complete_log = logs_dir / "complete.log"
    complete_log.write_text("Complete log content\nLine 2\n")

    open_log = logs_dir / "open.log"
    open_log.write_text("Open log content\nLine 2\n")

    # Export session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    # Verify logs are NOT included in export (PROJ-60802)
    with tarfile.open(export_path, "r:gz") as tar:
        members = tar.getnames()
        assert "logs/complete.log" not in members
        assert "logs/open.log" not in members

    # Cleanup
    export_path.unlink()


def test_export_without_logs_succeeds(temp_daf_home):
    """Test that export succeeds even without diagnostic logs."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Do NOT create logs directory

    # Export should still succeed
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    assert export_path.exists()

    # Verify no logs directory in export
    with tarfile.open(export_path, "r:gz") as tar:
        members = tar.getnames()
        assert not any(m.startswith("logs/") for m in members)

    # Cleanup
    export_path.unlink()


def test_import_without_diagnostic_logs_succeeds(temp_daf_home):
    """Test that import succeeds without diagnostic logs (PROJ-60802).

    Session exports don't include diagnostic logs (they're global files).
    Import should succeed without logs since exports don't contain them.
    """
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Create diagnostic logs (they won't be included in export)
    logs_dir = temp_daf_home / "logs"
    logs_dir.mkdir(exist_ok=True)

    complete_log = logs_dir / "complete.log"
    complete_log.write_text("Exported complete log\nWith diagnostic info\n")

    # Export session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    # Clear existing logs to simulate import on different machine
    complete_log.unlink()

    # Import sessions - should succeed without logs
    imported_keys = export_manager.import_sessions(export_path, merge=False)

    # Verify import succeeded
    assert len(imported_keys) == 1
    assert "test-session" in imported_keys

    # Verify logs were NOT restored (exports don't contain them)
    imported_logs_dir = temp_daf_home / "logs" / "imported"
    assert not imported_logs_dir.exists()

    # Cleanup
    export_path.unlink()


def test_export_import_preserves_notes(temp_daf_home):
    """Test that session notes are preserved during export/import cycle (PROJ-60697)."""
    # Create a session with notes
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="session-with-notes",
        goal="Test notes preservation",
        working_directory="test-dir",
        project_path="/test-path",
        ai_agent_session_id="uuid-notes",
    )

    # Add notes to the session
    session_manager.add_note("session-with-notes", "First note from developer A")
    session_manager.add_note("session-with-notes", "Second note from developer A")

    # Verify notes file exists
    session_dir = config_loader.get_session_dir("session-with-notes")
    notes_file = session_dir / "notes.md"
    assert notes_file.exists()

    # Read original notes content
    original_notes = notes_file.read_text()
    assert "First note from developer A" in original_notes
    assert "Second note from developer A" in original_notes

    # Export the session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["session-with-notes"])

    # Verify notes.md is included in the export archive
    with tarfile.open(export_path, "r:gz") as tar:
        members = tar.getnames()
        assert "sessions/session-with-notes/notes.md" in members

        # Verify notes content in archive
        notes_content = tar.extractfile("sessions/session-with-notes/notes.md").read().decode("utf-8")
        assert "First note from developer A" in notes_content
        assert "Second note from developer A" in notes_content

    # Simulate import on a different machine by deleting the session
    # Delete using identifier (removes all sessions for the group)
    session_manager.delete_session("session-with-notes")

    # Reload session manager to verify deletion
    session_manager_after_delete = SessionManager(config_loader)
    deleted_sessions = session_manager_after_delete.index.get_sessions("session-with-notes")
    assert len(deleted_sessions) == 0

    # Import the session
    imported_keys = export_manager.import_sessions(export_path, merge=False)
    assert "session-with-notes" in imported_keys

    # Verify notes are restored
    restored_notes_file = config_loader.get_session_dir("session-with-notes") / "notes.md"
    assert restored_notes_file.exists()

    # Verify notes content is preserved
    restored_notes = restored_notes_file.read_text()
    assert "First note from developer A" in restored_notes
    assert "Second note from developer A" in restored_notes

    # Add a new note after import (simulating developer B)
    session_manager_after_import = SessionManager(config_loader)
    session_manager_after_import.add_note("session-with-notes", "Third note from developer B")

    # Verify all notes are present
    final_notes = restored_notes_file.read_text()
    assert "First note from developer A" in final_notes
    assert "Second note from developer A" in final_notes
    assert "Third note from developer B" in final_notes

    # Cleanup
    export_path.unlink()


def test_export_includes_notes_in_session_directory(temp_daf_home):
    """Test that notes.md is included when exporting session directories (PROJ-60697)."""
    # Create a session with notes
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-notes",
        goal="Test notes inclusion",
        working_directory="test-dir",
        project_path="/test-path",
        ai_agent_session_id="uuid-1",
    )

    # Add a note
    session_manager.add_note("test-notes", "Important note about implementation")

    # Export the session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["test-notes"])

    # Verify session directory is included in export
    with tarfile.open(export_path, "r:gz") as tar:
        members = tar.getnames()

        # Check session directory exists
        assert "sessions/test-notes/notes.md" in members

        # Check metadata.json exists (created during session creation)
        assert "sessions/test-notes/metadata.json" in members

    # Cleanup
    export_path.unlink()


def test_import_creates_notes_if_present_in_export(temp_daf_home):
    """Test that import creates notes.md if it's present in export archive (PROJ-60697)."""
    # Create a session with notes
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="import-notes-test",
        goal="Test import notes",
        working_directory="test-dir",
        project_path="/test-path",
        ai_agent_session_id="uuid-import",
    )

    # Add notes
    session_manager.add_note("import-notes-test", "Note before export")

    # Export
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["import-notes-test"])

    # Delete the session and its directory
    session_manager.delete_session("import-notes-test")

    # Import
    imported_keys = export_manager.import_sessions(export_path, merge=False)

    # Verify notes file was created during import
    notes_file = config_loader.get_session_dir("import-notes-test") / "notes.md"
    assert notes_file.exists()

    # Verify notes content
    notes_content = notes_file.read_text()
    assert "Note before export" in notes_content

    # Cleanup
    export_path.unlink()


def test_check_missing_repositories_with_existing_repos(temp_daf_home, tmp_path):
    """Test _check_missing_repositories when all repositories exist."""
    # Create a session with project_path in temp workspace
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a real directory to represent the repository
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    repo_path = workspace / "existing-repo"
    repo_path.mkdir(parents=True)

    session_manager.create_session(
        name="test-session",
        goal="Test existing repo",
        working_directory="test",
        project_path=str(repo_path),
        ai_agent_session_id="uuid-1",
    )

    # Check for missing repos
    export_manager = ExportManager(config_loader)
    sessions_index = config_loader.load_sessions()
    missing_repos = export_manager._check_missing_repositories(sessions_index, str(workspace))

    # Should be empty since repo exists
    assert len(missing_repos) == 0


def test_check_missing_repositories_with_missing_repos(temp_daf_home, tmp_path):
    """Test _check_missing_repositories when repositories are missing."""
    # Create a session with project_path that doesn't exist
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    missing_repo_path = workspace / "missing-repo"
    # Don't create the directory - it should be missing

    session_manager.create_session(
        name="test-session",
        goal="Test missing repo",
        working_directory="test",
        project_path=str(missing_repo_path),
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    # Check for missing repos
    export_manager = ExportManager(config_loader)
    sessions_index = config_loader.load_sessions()
    missing_repos = export_manager._check_missing_repositories(sessions_index, str(workspace))

    # Should detect the missing repo
    assert len(missing_repos) == 1
    assert missing_repos[0]['repo_name'] == "missing-repo"
    assert missing_repos[0]['project_path'] == str(missing_repo_path)
    assert missing_repos[0]['session_name'] == "test-session"
    assert missing_repos[0]['issue_key'] == "PROJ-12345"


def test_check_missing_repositories_with_remote_url(temp_daf_home, tmp_path):
    """Test _check_missing_repositories includes remote_url when available."""
    # Create a session with remote_url set
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    missing_repo_path = workspace / "missing-repo"

    session = session_manager.create_session(
        name="test-session",
        goal="Test with remote URL",
        working_directory="test",
        project_path=str(missing_repo_path),
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    # Manually set remote_url in the conversation 
    for conversation in session.conversations.values():
        conversation.active_session.remote_url = "https://github.com/user/repo.git"

    # Save the updated session by reloading, modifying, and saving
    sessions_index = config_loader.load_sessions()
    for conv in sessions_index.sessions["test-session"].conversations.values():
        conv.active_session.remote_url = "https://github.com/user/repo.git"
    config_loader.save_sessions(sessions_index)

    # Check for missing repos
    export_manager = ExportManager(config_loader)
    sessions_index = config_loader.load_sessions()
    missing_repos = export_manager._check_missing_repositories(sessions_index, str(workspace))

    # Should detect the missing repo with remote URL
    assert len(missing_repos) == 1
    assert missing_repos[0]['remote_url'] == "https://github.com/user/repo.git"


def test_check_missing_repositories_with_multiple_sessions(temp_daf_home, tmp_path):
    """Test _check_missing_repositories with multiple sessions."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)

    # Create first session with existing repo
    existing_repo = workspace / "existing-repo"
    existing_repo.mkdir(parents=True)
    session_manager.create_session(
        name="session-1",
        goal="Existing repo",
        working_directory="test1",
        project_path=str(existing_repo),
        ai_agent_session_id="uuid-1",
    )

    # Create second session with missing repo
    missing_repo = workspace / "missing-repo"
    session_manager.create_session(
        name="session-2",
        goal="Missing repo",
        working_directory="test2",
        project_path=str(missing_repo),
        ai_agent_session_id="uuid-2",
        issue_key="PROJ-12345",
    )

    # Check for missing repos
    export_manager = ExportManager(config_loader)
    sessions_index = config_loader.load_sessions()
    missing_repos = export_manager._check_missing_repositories(sessions_index, str(workspace))

    # Should detect only the missing repo
    assert len(missing_repos) == 1
    assert missing_repos[0]['repo_name'] == "missing-repo"


def test_check_missing_repositories_no_duplicates(temp_daf_home, tmp_path):
    """Test _check_missing_repositories doesn't report duplicates."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    missing_repo = workspace / "missing-repo"

    # Create two sessions pointing to the same missing repo
    session_manager.create_session(
        name="session-1",
        goal="First session",
        working_directory="test1",
        project_path=str(missing_repo),
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="session-2",
        goal="Second session",
        working_directory="test2",
        project_path=str(missing_repo),
        ai_agent_session_id="uuid-2",
    )

    # Check for missing repos
    export_manager = ExportManager(config_loader)
    sessions_index = config_loader.load_sessions()
    missing_repos = export_manager._check_missing_repositories(sessions_index, str(workspace))

    # Should only report the missing repo once (no duplicates)
    assert len(missing_repos) == 1
    assert missing_repos[0]['repo_name'] == "missing-repo"


def test_import_sessions_warns_about_missing_repos(temp_daf_home, tmp_path, capsys, monkeypatch):
    """Test that import_sessions displays warning for missing repositories."""
    # Create and export a session with a repository that won't exist on import
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Create a temporary repo for export
    export_repo = tmp_path / "export-repo"
    export_repo.mkdir(parents=True)

    session_manager.create_session(
        name="test-import",
        goal="Test import warning",
        working_directory="test",
        project_path=str(export_repo),
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    # Export the session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["test-import"])

    # Delete the session and repo
    session_manager.delete_session("test-import")
    import shutil
    shutil.rmtree(export_repo)

    # Import the session (repo doesn't exist now)
    imported_keys = export_manager.import_sessions(export_path, merge=False)

    # Verify import succeeded
    assert "test-import" in imported_keys

    # Verify warning was displayed (captured output)
    captured = capsys.readouterr()
    assert "Missing repositories detected" in captured.out or "⚠" in captured.out

    # Cleanup
    export_path.unlink()


def test_export_captures_remote_url(temp_daf_home, tmp_path, monkeypatch):
    """Test that export captures git remote URL for conversations."""
    # Mock GitUtils.get_remote_url to return a test URL
    from devflow.git import utils as git_utils_module

    def mock_get_remote_url(path):
        return "https://github.com/test/repo.git"

    monkeypatch.setattr(git_utils_module.GitUtils, "get_remote_url", staticmethod(mock_get_remote_url))

    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    repo_path = tmp_path / "test-repo"
    repo_path.mkdir(parents=True)

    session_manager.create_session(
        name="test-export-url",
        goal="Test remote URL capture",
        working_directory="test",
        project_path=str(repo_path),
        ai_agent_session_id="uuid-1",
    )

    # Export the session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["test-export-url"])

    # Verify export succeeded
    assert export_path.exists()

    # Extract and check sessions.json
    import tarfile
    with tarfile.open(export_path, "r:gz") as tar:
        sessions_file = tar.extractfile("sessions.json")
        sessions_data = json.load(sessions_file)

        # Check that remote_url was captured
        session_data = sessions_data["test-export-url"]

        # Check conversations have remote_url 
        conversations = session_data.get("conversations", {})
        assert len(conversations) > 0

        for conversation in conversations.values():
            # Conversation is now an object with active_session and archived_sessions
            active_session = conversation.get("active_session")
            assert active_session is not None
            assert active_session.get("remote_url") == "https://github.com/test/repo.git"

    # Cleanup
    export_path.unlink()


def test_export_with_issue_key_uses_issue_key_in_filename(temp_daf_home):
    """Test that export with issue key uses issue key in default filename (PROJ-60714)."""
    # Create a session with issue key
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test issue key export",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    # Export the session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["test-session"])

    assert export_path.exists()
    # Should use issue key in filename
    assert export_path.name == "PROJ-12345-session-export.tar.gz"
    # Should be in workspace directory (default: Path.home() / "development")
    config = config_loader.load_config()
    expected_dir = Path.home() / "development"
    assert export_path.parent == expected_dir

    # Cleanup
    export_path.unlink()


def test_export_without_issue_key_uses_session_name(temp_daf_home):
    """Test that export without issue key uses session name in default filename (PROJ-60714)."""
    # Create a session without issue key
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="my-session",
        goal="Test without JIRA",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Export the session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["my-session"])

    assert export_path.exists()
    # Should use session name in filename
    assert export_path.name == "my-session-session-export.tar.gz"
    # Should be in workspace directory
    expected_dir = Path.home() / "development"
    assert export_path.parent == expected_dir

    # Cleanup
    export_path.unlink()




def test_export_multiple_sessions_uses_count_based_naming(temp_daf_home):
    """Test that exporting multiple sessions uses count-based naming (PROJ-60714)."""
    # Create multiple sessions
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="session1",
        goal="First",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-11111",
    )

    session_manager.create_session(
        name="session2",
        goal="Second",
        working_directory="dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
        issue_key="PROJ-22222",
    )

    session_manager.create_session(
        name="session3",
        goal="Third",
        working_directory="dir3",
        project_path="/path3",
        ai_agent_session_id="uuid-3",
        issue_key="PROJ-33333",
    )

    # Export all sessions
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    assert export_path.exists()
    # Should use count-based naming for multiple sessions
    assert export_path.name == "3sessions-session-export.tar.gz"
    # Should be in workspace directory
    expected_dir = Path.home() / "development"
    assert export_path.parent == expected_dir

    # Cleanup
    export_path.unlink()


def test_export_no_timestamp_in_default_filename(temp_daf_home):
    """Test that default export filename does not include timestamp (PROJ-60714)."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test no timestamp",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
        issue_key="PROJ-12345",
    )

    # Export the session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["test-session"])

    # Filename should be exactly "PROJ-12345-session-export.tar.gz" with no timestamp
    assert export_path.name == "PROJ-12345-session-export.tar.gz"
    # Should not contain date/time patterns
    import re
    # Check for timestamp patterns like 20231215_143045
    assert not re.search(r'\d{8}_\d{6}', export_path.name)

    # Cleanup
    export_path.unlink()


def test_import_places_conversation_file_in_correct_directory(temp_daf_home, tmp_path):
    """Test that import places conversation file in correct directory based on cwd field (PROJ-60776)."""
    import shutil

    # Create a session with a specific project path
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    test_project_path = str(tmp_path / "test-project")
    Path(test_project_path).mkdir(parents=True, exist_ok=True)

    session_manager.create_session(
        name="cwd-test",
        goal="Test cwd field",
        working_directory="test",
        project_path=test_project_path,
        ai_agent_session_id="12345678-1234-1234-1234-123456789abc",
        issue_key="PROJ-99999",
    )

    # Create a mock conversation file in ~/.claude/projects/
    # First, encode the path the way Claude does
    export_manager = ExportManager(config_loader)
    encoded_path = export_manager._encode_path(test_project_path)

    claude_projects_dir = Path.home() / ".claude" / "projects" / encoded_path
    claude_projects_dir.mkdir(parents=True, exist_ok=True)

    # Create conversation file with proper structure (using "cwd" field)
    conversation_file = claude_projects_dir / "12345678-1234-1234-1234-123456789abc.jsonl"
    with open(conversation_file, "w") as f:
        # First line must have cwd field (not workingDirectory)
        first_msg = {"cwd": test_project_path, "sessionId": "12345678-1234-1234-1234-123456789abc"}
        f.write(json.dumps(first_msg) + "\n")
        f.write(json.dumps({"role": "user", "content": "test message"}) + "\n")

    # Export the session
    export_path = export_manager.export_sessions(identifiers=["cwd-test"])

    # Delete the session and conversation file
    session_manager.delete_session("cwd-test")
    shutil.rmtree(claude_projects_dir)

    # Import the session
    imported_keys = export_manager.import_sessions(export_path, merge=False)

    # Verify import succeeded
    assert "cwd-test" in imported_keys

    # Verify conversation file was placed in correct directory
    expected_conversation_file = claude_projects_dir / "12345678-1234-1234-1234-123456789abc.jsonl"
    assert expected_conversation_file.exists(), f"Conversation file not found at {expected_conversation_file}"

    # Verify the conversation file has correct content
    with open(expected_conversation_file, "r") as f:
        first_line = f.readline()
        first_msg = json.loads(first_line)
        assert first_msg["cwd"] == test_project_path, "cwd field should be preserved"
        assert first_msg["sessionId"] == "12345678-1234-1234-1234-123456789abc"

    # Cleanup
    export_path.unlink()


def test_import_conversation_file_without_cwd_uses_session_metadata(temp_daf_home, tmp_path):
    """Test that import uses session metadata when conversation file has no cwd field (PROJ-61025).

    This happens when the first message in a conversation file is a 'file-history-snapshot'
    which doesn't contain a cwd field. The import should scan all messages and fall back
    to session metadata if no cwd is found.
    """
    import shutil

    # Create a session with a specific project path
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    test_project_path = str(tmp_path / "test-no-cwd-project")
    Path(test_project_path).mkdir(parents=True, exist_ok=True)

    session_manager.create_session(
        name="no-cwd-test",
        goal="Test conversation file without cwd field",
        working_directory="test",
        project_path=test_project_path,
        ai_agent_session_id="aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb",
        issue_key="PROJ-61025",
    )

    # Create a mock conversation file in ~/.claude/projects/
    export_manager = ExportManager(config_loader)
    encoded_path = export_manager._encode_path(test_project_path)

    claude_projects_dir = Path.home() / ".claude" / "projects" / encoded_path
    claude_projects_dir.mkdir(parents=True, exist_ok=True)

    # Create conversation file with file-history-snapshot as first message (no cwd field)
    conversation_file = claude_projects_dir / "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb.jsonl"
    with open(conversation_file, "w") as f:
        # First message: file-history-snapshot (no cwd field) - simulates real Claude Code behavior
        first_msg = {
            "type": "file-history-snapshot",
            "sessionId": "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb",
            "files": []
        }
        f.write(json.dumps(first_msg) + "\n")

        # Second message: user message (also no cwd field)
        second_msg = {"role": "user", "content": "test message"}
        f.write(json.dumps(second_msg) + "\n")

        # Third message: tool use with cwd
        third_msg = {
            "role": "assistant",
            "content": "tool response",
            "cwd": test_project_path
        }
        f.write(json.dumps(third_msg) + "\n")

    # Export the session
    export_path = export_manager.export_sessions(identifiers=["no-cwd-test"])

    # Delete the session and conversation file
    session_manager.delete_session("no-cwd-test")
    shutil.rmtree(claude_projects_dir)

    # Import the session
    imported_keys = export_manager.import_sessions(export_path, merge=False)

    # Verify import succeeded
    assert "no-cwd-test" in imported_keys

    # Verify conversation file was placed in correct directory
    # (even though first message had no cwd field)
    expected_conversation_file = claude_projects_dir / "aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb.jsonl"
    assert expected_conversation_file.exists(), f"Conversation file not found at {expected_conversation_file}"

    # Verify the conversation file has correct content (all 3 messages preserved)
    with open(expected_conversation_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 3, "All 3 messages should be preserved"

        # First message should be file-history-snapshot
        first_msg = json.loads(lines[0])
        assert first_msg["type"] == "file-history-snapshot"
        assert "cwd" not in first_msg

        # Third message should have cwd
        third_msg = json.loads(lines[2])
        assert third_msg["cwd"] == test_project_path

    # Cleanup
    export_path.unlink()


def test_import_conversation_file_no_cwd_anywhere_uses_session_metadata(temp_daf_home, tmp_path):
    """Test fallback to session metadata when no message in conversation file has cwd (PROJ-61025)."""
    import shutil

    # Create a session with a specific project path
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    test_project_path = str(tmp_path / "test-fallback-project")
    Path(test_project_path).mkdir(parents=True, exist_ok=True)

    session_manager.create_session(
        name="fallback-test",
        goal="Test fallback to session metadata",
        working_directory="test",
        project_path=test_project_path,
        ai_agent_session_id="cccccccc-4444-5555-6666-dddddddddddd",
        issue_key="PROJ-61025-B",
    )

    # Create a mock conversation file
    export_manager = ExportManager(config_loader)
    encoded_path = export_manager._encode_path(test_project_path)

    claude_projects_dir = Path.home() / ".claude" / "projects" / encoded_path
    claude_projects_dir.mkdir(parents=True, exist_ok=True)

    # Create conversation file with NO cwd field in ANY message
    conversation_file = claude_projects_dir / "cccccccc-4444-5555-6666-dddddddddddd.jsonl"
    with open(conversation_file, "w") as f:
        # All messages without cwd field
        f.write(json.dumps({"type": "file-history-snapshot", "sessionId": "cccccccc-4444-5555-6666-dddddddddddd"}) + "\n")
        f.write(json.dumps({"role": "user", "content": "test message"}) + "\n")
        f.write(json.dumps({"role": "assistant", "content": "response"}) + "\n")

    # Export the session
    export_path = export_manager.export_sessions(identifiers=["fallback-test"])

    # Delete the session and conversation file
    session_manager.delete_session("fallback-test")
    shutil.rmtree(claude_projects_dir)

    # Import the session
    imported_keys = export_manager.import_sessions(export_path, merge=False)

    # Verify import succeeded
    assert "fallback-test" in imported_keys

    # Verify conversation file was placed in correct directory using session metadata
    expected_conversation_file = claude_projects_dir / "cccccccc-4444-5555-6666-dddddddddddd.jsonl"
    assert expected_conversation_file.exists(), f"Conversation file not found at {expected_conversation_file}"

    # Verify the conversation file has correct content
    with open(expected_conversation_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 3, "All 3 messages should be preserved"

    # Cleanup
    export_path.unlink()


def test_backup_restore_places_conversation_file_in_correct_directory(temp_daf_home, tmp_path):
    """Test that backup restore places conversation file in correct directory based on cwd field (PROJ-60776)."""
    import shutil
    import tarfile
    from devflow.backup.manager import BackupManager

    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    test_project_path = str(tmp_path / "backup-test-project")
    Path(test_project_path).mkdir(parents=True, exist_ok=True)

    created_session = session_manager.create_session(
        name="backup-cwd-test",
        goal="Test backup cwd field",
        working_directory="test",
        project_path=test_project_path,
        ai_agent_session_id="87654321-4321-4321-4321-cba987654321",
        issue_key="PROJ-88888",
    )

    # Manually create a backup tarball with a conversation file that has the "cwd" field
    backup_path = tmp_path / "test-backup.tar.gz"

    with tarfile.open(backup_path, "w:gz") as tar:
        # Add backup metadata
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"version": "1.0", "archive_type": "backup", "created": "2024-01-01T00:00:00"}, f)
            metadata_path = f.name
        tar.add(metadata_path, arcname="backup-metadata.json")
        Path(metadata_path).unlink()

        # Add sessions.json
        sessions_file = config_loader.sessions_file
        if sessions_file.exists():
            tar.add(sessions_file, arcname="sessions.json")

        # Add session directory
        session_dir = config_loader.sessions_dir / "backup-cwd-test"
        if session_dir.exists():
            tar.add(session_dir, arcname="sessions/backup-cwd-test")

        # Create and add conversation file with "cwd" field (not "workingDirectory")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            # First line has "cwd" field
            first_msg = {"cwd": test_project_path, "sessionId": "87654321-4321-4321-4321-cba987654321"}
            f.write(json.dumps(first_msg) + "\n")
            f.write(json.dumps({"role": "user", "content": "backup test message"}) + "\n")
            conversation_temp = f.name

        # Add to tar with the naming convention used by backup manager
        tar.add(conversation_temp, arcname="conversations/backup-cwd-test-1-87654321-4321-4321-4321-cba987654321.jsonl")
        Path(conversation_temp).unlink()

    # Delete the session
    session_manager.delete_session("backup-cwd-test")

    # Restore from backup
    backup_manager = BackupManager(config_loader)
    backup_manager.restore_backup(backup_path)

    # Verify conversation file was placed in correct directory based on "cwd" field
    export_manager = ExportManager(config_loader)
    encoded_path = export_manager._encode_path(test_project_path)
    claude_projects_dir = Path.home() / ".claude" / "projects" / encoded_path
    expected_conversation_file = claude_projects_dir / "87654321-4321-4321-4321-cba987654321.jsonl"

    assert expected_conversation_file.exists(), f"Conversation file not found at {expected_conversation_file}"

    # Verify the conversation file has correct content
    with open(expected_conversation_file, "r") as f:
        first_line = f.readline()
        first_msg = json.loads(first_line)
        assert first_msg["cwd"] == test_project_path, "cwd field should be preserved in backup restore"
        assert first_msg["sessionId"] == "87654321-4321-4321-4321-cba987654321"

    # Cleanup
    backup_path.unlink()


def test_backup_restore_conversation_file_without_cwd_uses_session_metadata(temp_daf_home, tmp_path):
    """Test that backup restore uses session metadata when conversation file has no cwd field (PROJ-61025)."""
    import shutil
    import tarfile
    import tempfile
    from devflow.backup.manager import BackupManager

    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    test_project_path = str(tmp_path / "backup-no-cwd-project")
    Path(test_project_path).mkdir(parents=True, exist_ok=True)

    created_session = session_manager.create_session(
        name="backup-no-cwd-test",
        goal="Test backup with no cwd field",
        working_directory="test",
        project_path=test_project_path,
        ai_agent_session_id="eeeeeeee-7777-8888-9999-ffffffffffff",
        issue_key="PROJ-61025-C",
    )

    # Create backup tarball with conversation file that has NO cwd field
    backup_path = tmp_path / "test-backup-no-cwd.tar.gz"

    with tarfile.open(backup_path, "w:gz") as tar:
        # Add backup metadata
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"version": "1.0", "archive_type": "backup", "created": "2024-01-01T00:00:00"}, f)
            metadata_path = f.name
        tar.add(metadata_path, arcname="backup-metadata.json")
        Path(metadata_path).unlink()

        # Add sessions.json
        sessions_file = config_loader.sessions_file
        if sessions_file.exists():
            tar.add(sessions_file, arcname="sessions.json")

        # Add session directory
        session_dir = config_loader.sessions_dir / "backup-no-cwd-test"
        if session_dir.exists():
            tar.add(session_dir, arcname="sessions/backup-no-cwd-test")

        # Create conversation file with file-history-snapshot (no cwd field)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            # First message: file-history-snapshot (no cwd)
            f.write(json.dumps({"type": "file-history-snapshot", "sessionId": "eeeeeeee-7777-8888-9999-ffffffffffff"}) + "\n")
            # Second message: user message (no cwd)
            f.write(json.dumps({"role": "user", "content": "backup test"}) + "\n")
            conversation_temp = f.name

        tar.add(conversation_temp, arcname="conversations/backup-no-cwd-test-1-eeeeeeee-7777-8888-9999-ffffffffffff.jsonl")
        Path(conversation_temp).unlink()

    # Delete the session
    session_manager.delete_session("backup-no-cwd-test")

    # Restore from backup
    backup_manager = BackupManager(config_loader)
    backup_manager.restore_backup(backup_path)

    # Verify conversation file was placed in correct directory using session metadata
    export_manager = ExportManager(config_loader)
    encoded_path = export_manager._encode_path(test_project_path)
    claude_projects_dir = Path.home() / ".claude" / "projects" / encoded_path
    expected_conversation_file = claude_projects_dir / "eeeeeeee-7777-8888-9999-ffffffffffff.jsonl"

    assert expected_conversation_file.exists(), f"Conversation file not found at {expected_conversation_file}"

    # Verify the conversation file has correct content
    with open(expected_conversation_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2, "Both messages should be preserved"

    # Cleanup
    backup_path.unlink()


def test_peek_export_file(temp_daf_home):
    """Test peeking at export file metadata without full extraction."""
    # Create test sessions
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="PROJ-12345",
        issue_key="PROJ-12345",
        goal="First test session",
        working_directory="test-dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    session_manager.create_session(
        name="PROJ-67890",
        issue_key="PROJ-67890",
        goal="Second test session",
        working_directory="test-dir2",
        project_path="/path2",
        ai_agent_session_id="uuid-2",
    )

    # Export sessions
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions()

    # Peek at export file
    peek_data = export_manager.peek_export_file(export_path)

    # Verify peek data
    assert peek_data["session_count"] == 2
    assert "PROJ-12345" in peek_data["session_keys"]
    assert "PROJ-67890" in peek_data["session_keys"]
    assert peek_data["created"] != "unknown"

    # Cleanup
    export_path.unlink()


def test_peek_export_file_not_found(temp_daf_home):
    """Test peek with non-existent export file."""
    config_loader = ConfigLoader()
    export_manager = ExportManager(config_loader)

    with pytest.raises(FileNotFoundError):
        export_manager.peek_export_file(Path("/nonexistent/export.tar.gz"))


def test_peek_export_file_backup_archive(temp_daf_home):
    """Test peek rejects backup archives."""
    from devflow.backup.manager import BackupManager

    # Create a backup instead of export
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="test-session",
        goal="Test",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-test",
    )

    # Create backup
    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    # Try to peek at backup file (should reject)
    export_manager = ExportManager(config_loader)
    with pytest.raises(ValueError, match="backup archive"):
        export_manager.peek_export_file(backup_path)

    # Cleanup
    backup_path.unlink()


def test_peek_export_file_single_session(temp_daf_home):
    """Test peek with single session export."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="PROJ-99999",
        issue_key="PROJ-99999",
        goal="Single session",
        working_directory="single-dir",
        project_path="/single-path",
        ai_agent_session_id="uuid-single",
    )

    # Export single session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["PROJ-99999"])

    # Peek at export file
    peek_data = export_manager.peek_export_file(export_path)

    # Verify peek data
    assert peek_data["session_count"] == 1
    assert len(peek_data["session_keys"]) == 1
    assert "PROJ-99999" in peek_data["session_keys"]

    # Cleanup
    export_path.unlink()


def test_export_excludes_workspace_name(temp_daf_home):
    """Test that export excludes workspace_name field for portable team handoffs (AAP-63987)."""
    # Create a session with workspace_name set
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="test-workspace",
        goal="Test workspace name exclusion",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-1",
    )

    # Set workspace_name after creation
    session.workspace_name = "feat-caching"
    session_manager.update_session(session)

    # Export the session
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["test-workspace"])

    # Extract and verify workspace_name is NOT in the export
    with tarfile.open(export_path, "r:gz") as tar:
        sessions_file = tar.extractfile("sessions.json")
        sessions_data = json.load(sessions_file)

        session_data = sessions_data["test-workspace"]
        assert "workspace_name" not in session_data, "workspace_name should be excluded from export"

    # Cleanup
    export_path.unlink()


def test_import_without_workspace_name(temp_daf_home):
    """Test that import succeeds when workspace_name is not in exported data (AAP-63987)."""
    # Create a session with workspace_name
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session = session_manager.create_session(
        name="import-workspace-test",
        goal="Test import without workspace_name",
        working_directory="test-dir",
        project_path="/path",
        ai_agent_session_id="uuid-import",
    )

    # Set workspace_name after creation
    session.workspace_name = "primary"
    session_manager.update_session(session)

    # Export (workspace_name should be excluded)
    export_manager = ExportManager(config_loader)
    export_path = export_manager.export_sessions(identifiers=["import-workspace-test"])

    # Delete the session
    session_manager.delete_session("import-workspace-test")

    # Import the session
    imported_keys = export_manager.import_sessions(export_path, merge=False)

    # Verify import succeeded
    assert "import-workspace-test" in imported_keys

    # Reload session manager and verify workspace_name is None
    session_manager = SessionManager(config_loader)
    imported_sessions = session_manager.index.get_sessions("import-workspace-test")
    assert len(imported_sessions) == 1
    assert imported_sessions[0].workspace_name is None, "workspace_name should be None after import"

    # Cleanup
    export_path.unlink()
