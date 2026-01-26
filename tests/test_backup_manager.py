"""Tests for backup/restore manager."""

import json
import tarfile
from pathlib import Path

import pytest

from devflow.backup.manager import BackupManager
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def test_backup_manager_init(temp_daf_home):
    """Test BackupManager initialization."""
    manager = BackupManager()
    assert manager.config_loader is not None

    # Test with provided config loader
    config_loader = ConfigLoader()
    manager = BackupManager(config_loader)
    assert manager.config_loader is config_loader


def test_create_backup_basic(temp_daf_home):
    """Test creating a basic backup."""
    # Create some sessions
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="backup-test",
        goal="Test backup",
        working_directory="backup-dir",
        project_path="/backup",
        ai_agent_session_id="uuid-backup",
    )

    # Create backup
    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    assert backup_path.exists()
    assert backup_path.suffix == ".gz"
    assert "devaiflow-backup" in backup_path.name

    # Verify tar contents
    with tarfile.open(backup_path, "r:gz") as tar:
        members = tar.getnames()
        assert "sessions.json" in members
        assert any("sessions/" in name for name in members)

    # Cleanup
    backup_path.unlink()


def test_create_backup_with_custom_path(temp_daf_home):
    """Test creating backup with custom output path."""
    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="custom-backup",
        goal="Custom path backup",
        working_directory="custom-dir",
        project_path="/custom",
        ai_agent_session_id="uuid-custom",
    )

    # Create backup with custom path
    backup_manager = BackupManager(config_loader)
    custom_path = temp_daf_home / "my-backup.tar.gz"
    backup_path = backup_manager.create_backup(output_path=custom_path)

    assert backup_path == custom_path
    assert backup_path.exists()

    # Cleanup
    backup_path.unlink()


def test_create_backup_includes_session_data(temp_daf_home):
    """Test that backup includes session data."""
    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="data-backup",
        goal="Include data",
        working_directory="data-dir",
        project_path="/data",
        ai_agent_session_id="uuid-data",
    )

    # Create backup
    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    # Extract and verify sessions.json content
    with tarfile.open(backup_path, "r:gz") as tar:
        sessions_file = tar.extractfile("sessions.json")
        sessions_data = json.load(sessions_file)

        assert "sessions" in sessions_data
        assert "data-backup" in sessions_data["sessions"]
        session_data = sessions_data["sessions"]["data-backup"]
        assert session_data["goal"] == "Include data"

    # Cleanup
    backup_path.unlink()


def test_restore_backup_basic(temp_daf_home):
    """Test restoring from a backup."""
    # Create and backup sessions
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="restore-test",
        goal="Restore this",
        working_directory="restore-dir",
        project_path="/restore",
        ai_agent_session_id="uuid-restore",
    )

    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    # Clear sessions
    config_loader.sessions_file.unlink()

    # Restore
    backup_manager.restore_backup(backup_path, merge=False)

    # Verify restoration
    restored_manager = SessionManager(config_loader)
    sessions = restored_manager.index.get_sessions("restore-test")
    assert len(sessions) == 1
    assert sessions[0].goal == "Restore this"

    # Cleanup
    backup_path.unlink()


def test_restore_backup_merge_mode(temp_daf_home):
    """Test restoring backup with merge mode."""
    # Create initial session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="existing-session",
        goal="Already exists",
        working_directory="existing-dir",
        project_path="/existing",
        ai_agent_session_id="uuid-existing",
    )

    # Create and backup different session
    session_manager.create_session(
        name="new-session",
        goal="Will be restored",
        working_directory="new-dir",
        project_path="/new",
        ai_agent_session_id="uuid-new",
    )

    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    # Delete new session
    session_manager.delete_session("new-session")

    # Restore with merge
    backup_manager.restore_backup(backup_path, merge=True)

    # Both sessions should exist
    restored_manager = SessionManager(config_loader)
    existing = restored_manager.index.get_sessions("existing-session")
    new = restored_manager.index.get_sessions("new-session")

    assert len(existing) >= 1
    assert len(new) >= 1

    # Cleanup
    backup_path.unlink()


def test_restore_backup_replace_mode(temp_daf_home):
    """Test restoring backup with replace mode."""
    # Create initial session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="replace-me",
        goal="Original",
        working_directory="orig-dir",
        project_path="/orig",
        ai_agent_session_id="uuid-orig",
    )

    # Backup
    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    # Modify session
    sessions = session_manager.index.get_sessions("replace-me")
    session = sessions[0]
    session.goal = "Modified"
    session_manager.update_session(session)

    # Restore with replace (merge=False)
    backup_manager.restore_backup(backup_path, merge=False)

    # Should have original data
    restored_manager = SessionManager(config_loader)
    sessions = restored_manager.index.get_sessions("replace-me")
    assert sessions[0].goal == "Original"

    # Cleanup
    backup_path.unlink()


def test_restore_backup_nonexistent_file(temp_daf_home):
    """Test restoring from nonexistent file raises error."""
    backup_manager = BackupManager()
    nonexistent = Path("/nonexistent/backup.tar.gz")

    with pytest.raises(FileNotFoundError, match="Backup file not found"):
        backup_manager.restore_backup(nonexistent)


def test_collect_backup_data(temp_daf_home):
    """Test backup data collection."""
    from datetime import datetime
    from devflow.config.models import Session

    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="collect-test",
        goal="Collect data",
        working_directory="collect-dir",
        project_path="/collect",
        ai_agent_session_id="uuid-collect",
    )

    # Collect backup data
    backup_manager = BackupManager(config_loader)
    backup_data = backup_manager._collect_backup_data()

    assert "version" in backup_data
    assert backup_data["version"] == "1.0"
    assert "created" in backup_data
    assert "sessions" in backup_data
    assert "collect-test" in backup_data["sessions"]


def test_find_conversation_file_not_found(temp_daf_home):
    """Test finding conversation file when it doesn't exist."""
    backup_manager = BackupManager()
    result = backup_manager._find_conversation_file("nonexistent-uuid")
    assert result is None


def test_encode_path(temp_daf_home):
    """Test path encoding method."""
    backup_manager = BackupManager()

    assert backup_manager._encode_path("/path/to/project") == "-path-to-project"
    assert backup_manager._encode_path("/home/user/code") == "-home-user-code"


def test_backup_with_notes(temp_daf_home):
    """Test backup includes session notes."""
    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="notes-backup",
        goal="Backup notes",
        working_directory="notes-dir",
        project_path="/notes",
        ai_agent_session_id="uuid-notes",
    )

    # Create notes file
    session_dir = config_loader.get_session_dir("notes-backup")
    session_dir.mkdir(parents=True, exist_ok=True)
    notes_file = session_dir / "notes.md"
    notes_file.write_text("Test notes content")

    # Create backup
    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    # Verify notes are in backup
    with tarfile.open(backup_path, "r:gz") as tar:
        members = tar.getnames()
        assert any("notes.md" in name for name in members)

    # Cleanup
    backup_path.unlink()


def test_restore_backup_creates_directories(temp_daf_home):
    """Test that restore creates necessary directories."""
    # Create session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="dir-test",
        goal="Directory test",
        working_directory="dir-test",
        project_path="/dir-test",
        ai_agent_session_id="uuid-dir",
    )

    # Create backup
    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    # Clear everything
    import shutil
    if config_loader.sessions_dir.exists():
        shutil.rmtree(config_loader.sessions_dir)
    if config_loader.sessions_file.exists():
        config_loader.sessions_file.unlink()

    # Restore should recreate directories
    backup_manager.restore_backup(backup_path, merge=False)

    assert config_loader.sessions_file.exists()
    assert config_loader.sessions_dir.exists()

    # Cleanup
    backup_path.unlink()


def test_backup_empty_sessions(temp_daf_home):
    """Test creating backup when no sessions exist."""
    # No sessions created
    config_loader = ConfigLoader()
    backup_manager = BackupManager(config_loader)

    # Should still create backup (might be empty)
    backup_path = backup_manager.create_backup()
    assert backup_path.exists()

    # Cleanup
    backup_path.unlink()


def test_restore_preserves_existing_on_merge(temp_daf_home):
    """Test that merge mode preserves existing sessions."""
    # Create existing session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="preserve-me",
        goal="Keep this",
        working_directory="preserve-dir",
        project_path="/preserve",
        ai_agent_session_id="uuid-preserve",
    )

    # Create empty backup (or backup without this session)
    backup_manager = BackupManager(config_loader)

    # Create a second session to backup
    session_manager.create_session(
        name="other-session",
        goal="Other",
        working_directory="other-dir",
        project_path="/other",
        ai_agent_session_id="uuid-other",
    )

    backup_path = backup_manager.create_backup()

    # Delete the other session before restore
    session_manager.delete_session("other-session")

    # Restore with merge
    backup_manager.restore_backup(backup_path, merge=True)

    # Original session should still exist
    restored_manager = SessionManager(config_loader)
    sessions = restored_manager.index.get_sessions("preserve-me")
    assert len(sessions) >= 1

    # Cleanup
    backup_path.unlink()


def test_backup_multiple_sessions_same_group(temp_daf_home):
    """Test that attempting to create duplicate session names raises ValueError."""
    import pytest

    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="multi-backup",
        goal="First session",
        working_directory="dir1",
        project_path="/path1",
        ai_agent_session_id="uuid-1",
    )

    # Attempting to create second session with same name should raise ValueError
    with pytest.raises(ValueError, match="Session 'multi-backup' already exists"):
        session_manager.create_session(
            name="multi-backup",
            goal="Second session",
            working_directory="dir2",
            project_path="/path2",
            ai_agent_session_id="uuid-2",
        )


def test_backup_includes_diagnostic_logs(temp_daf_home):
    """Test that backup includes diagnostic logs (PROJ-60657)."""
    # Create a session
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="log-backup",
        goal="Test logs",
        working_directory="log-dir",
        project_path="/log",
        ai_agent_session_id="uuid-log",
    )

    # Create diagnostic logs
    logs_dir = temp_daf_home / "logs"
    logs_dir.mkdir(exist_ok=True)

    complete_log = logs_dir / "complete.log"
    complete_log.write_text("Backup complete log\n")

    open_log = logs_dir / "open.log"
    open_log.write_text("Backup open log\n")

    # Create backup
    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    # Verify logs are included
    with tarfile.open(backup_path, "r:gz") as tar:
        members = tar.getnames()
        assert "logs/complete.log" in members
        assert "logs/open.log" in members

        # Verify content
        complete_content = tar.extractfile("logs/complete.log").read().decode("utf-8")
        assert "Backup complete log" in complete_content

    # Cleanup
    backup_path.unlink()


def test_restore_restores_diagnostic_logs(temp_daf_home):
    """Test that restore restores diagnostic logs to namespaced location (PROJ-60657)."""
    # Create session with logs
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="restore-logs",
        goal="Test restore logs",
        working_directory="restore-dir",
        project_path="/restore",
        ai_agent_session_id="uuid-restore-logs",
    )

    # Create diagnostic logs
    logs_dir = temp_daf_home / "logs"
    logs_dir.mkdir(exist_ok=True)

    complete_log = logs_dir / "complete.log"
    complete_log.write_text("Restore test log\n")

    # Create backup
    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    # Clear logs
    complete_log.unlink()

    # Restore backup
    backup_manager.restore_backup(backup_path, merge=False)

    # Verify logs are restored to imported/ directory
    imported_logs_dir = temp_daf_home / "logs" / "imported"
    assert imported_logs_dir.exists()

    # Should have one timestamped subdirectory
    subdirs = list(imported_logs_dir.iterdir())
    assert len(subdirs) == 1

    # Check log was restored
    restored_log = subdirs[0] / "complete.log"
    assert restored_log.exists()
    content = restored_log.read_text()
    assert "Restore test log" in content

    # Cleanup
    backup_path.unlink()


def test_backup_without_logs_succeeds(temp_daf_home):
    """Test that backup succeeds without diagnostic logs."""
    # Create session without logs
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    session_manager.create_session(
        name="no-logs",
        goal="No logs",
        working_directory="no-logs-dir",
        project_path="/no-logs",
        ai_agent_session_id="uuid-no-logs",
    )

    # Create backup (no logs directory)
    backup_manager = BackupManager(config_loader)
    backup_path = backup_manager.create_backup()

    assert backup_path.exists()

    # Verify no logs in backup
    with tarfile.open(backup_path, "r:gz") as tar:
        members = tar.getnames()
        assert not any(m.startswith("logs/") for m in members)

    # Cleanup
    backup_path.unlink()
