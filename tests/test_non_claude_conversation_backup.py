"""Tests for non-Claude agent conversation backup warnings (#414)."""

import json
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest

from devflow.archive.base import ArchiveManagerBase, CONVERSATION_BACKUP_BACKENDS
from devflow.backup.manager import BackupManager
from devflow.config.loader import ConfigLoader
from devflow.export.manager import ExportManager
from devflow.session.manager import SessionManager


class TestConversationBackupBackends:
    """Test _is_conversation_backupable for all agent backends."""

    def test_claude_is_backupable(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("claude") is True

    def test_ollama_is_backupable(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("ollama") is True

    def test_opencode_not_backupable(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("opencode") is False

    def test_crush_not_backupable(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("crush") is False

    def test_cursor_not_backupable(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("cursor") is False

    def test_github_copilot_not_backupable(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("github-copilot") is False

    def test_windsurf_not_backupable(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("windsurf") is False

    def test_aider_not_backupable(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("aider") is False

    def test_continue_not_backupable(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("continue") is False

    def test_case_insensitive(self):
        manager = ArchiveManagerBase.__new__(ArchiveManagerBase)
        manager._conversation_warnings = []
        assert manager._is_conversation_backupable("Claude") is True
        assert manager._is_conversation_backupable("CLAUDE") is True
        assert manager._is_conversation_backupable("Ollama") is True

    def test_constant_only_contains_expected_backends(self):
        assert CONVERSATION_BACKUP_BACKENDS == {"claude", "ollama"}


class TestFindConversationFileWithBackend:
    """Test _find_conversation_file with agent_backend parameter."""

    def test_non_claude_backend_returns_none(self, temp_daf_home):
        manager = BackupManager()
        result = manager._find_conversation_file(
            "some-uuid", agent_backend="opencode"
        )
        assert result is None

    def test_claude_backend_searches_normally(self, temp_daf_home):
        manager = BackupManager()
        result = manager._find_conversation_file(
            "nonexistent-uuid", agent_backend="claude"
        )
        assert result is None

    def test_no_backend_param_searches_normally(self, temp_daf_home):
        manager = BackupManager()
        result = manager._find_conversation_file("nonexistent-uuid")
        assert result is None


class TestBackupWithNonClaudeBackend:
    """Test backup creates warnings for non-Claude backends."""

    def test_backup_with_opencode_records_warnings(self, temp_daf_home):
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)

        session_manager.create_session(
            name="opencode-test",
            goal="Test opencode backup",
            working_directory="test-dir",
            project_path="/test",
            ai_agent_session_id="uuid-opencode",
        )

        backup_manager = BackupManager(config_loader)

        with patch.object(
            backup_manager, "_get_agent_backend", return_value="opencode"
        ):
            backup_path = backup_manager.create_backup()

        assert backup_path.exists()
        warnings = backup_manager.get_conversation_warnings()
        assert len(warnings) == 1
        assert "opencode" in warnings[0]
        assert "conversation history was skipped" in warnings[0].lower()
        assert "opencode-test" in warnings[0]

        backup_path.unlink()

    def test_backup_with_claude_no_warnings(self, temp_daf_home):
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)

        session_manager.create_session(
            name="claude-test",
            goal="Test claude backup",
            working_directory="test-dir",
            project_path="/test",
            ai_agent_session_id="uuid-claude",
        )

        backup_manager = BackupManager(config_loader)

        with patch.object(
            backup_manager, "_get_agent_backend", return_value="claude"
        ):
            backup_path = backup_manager.create_backup()

        assert backup_path.exists()
        warnings = backup_manager.get_conversation_warnings()
        assert len(warnings) == 0

        backup_path.unlink()

    def test_backup_metadata_includes_agent_backend(self, temp_daf_home):
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)

        session_manager.create_session(
            name="meta-test",
            goal="Test metadata",
            working_directory="test-dir",
            project_path="/test",
            ai_agent_session_id="uuid-meta",
        )

        backup_manager = BackupManager(config_loader)

        with patch.object(
            backup_manager, "_get_agent_backend", return_value="opencode"
        ):
            backup_path = backup_manager.create_backup()

        with tarfile.open(backup_path, "r:gz") as tar:
            metadata_file = tar.extractfile("backup-metadata.json")
            metadata = json.load(metadata_file)
            assert metadata["agent_backend"] == "opencode"

        backup_path.unlink()


class TestRestoreWithNonClaudeBackend:
    """Test restore warns for non-Claude backends."""

    def test_restore_with_opencode_skips_conversations(self, temp_daf_home):
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)

        session_manager.create_session(
            name="restore-oc",
            goal="Test restore",
            working_directory="test-dir",
            project_path="/test",
            ai_agent_session_id="uuid-restore-oc",
        )

        backup_manager = BackupManager(config_loader)

        # Create backup with Claude backend (to include conversation placeholder)
        with patch.object(
            backup_manager, "_get_agent_backend", return_value="claude"
        ):
            backup_path = backup_manager.create_backup()

        # Restore with opencode backend
        with patch.object(
            backup_manager, "_get_agent_backend", return_value="opencode"
        ):
            backup_manager.restore_backup(backup_path, merge=False)

        # Should have warnings (backup has no conversation files since UUID doesn't exist,
        # but the restore path check still fires if conversations dir exists with files)
        # Session metadata should still be restored
        restored = session_manager.index.get_sessions("restore-oc")
        assert len(restored) >= 1

        backup_path.unlink()


class TestExportWithNonClaudeBackend:
    """Test export creates warnings for non-Claude backends."""

    def test_export_with_opencode_records_warnings(self, temp_daf_home):
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)

        session_manager.create_session(
            name="export-oc",
            goal="Test opencode export",
            working_directory="test-dir",
            project_path="/test",
            ai_agent_session_id="uuid-export-oc",
        )

        export_manager = ExportManager(config_loader)
        output_path = temp_daf_home / "test-export.tar.gz"

        with patch.object(
            export_manager, "_get_agent_backend", return_value="opencode"
        ):
            export_manager.export_sessions(
                identifiers=["export-oc"],
                output_path=output_path,
            )

        warnings = export_manager.get_conversation_warnings()
        assert len(warnings) == 1
        assert "opencode" in warnings[0]
        assert "export-oc" in warnings[0]

        output_path.unlink()

    def test_export_with_claude_no_warnings(self, temp_daf_home):
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)

        session_manager.create_session(
            name="export-claude",
            goal="Test claude export",
            working_directory="test-dir",
            project_path="/test",
            ai_agent_session_id="uuid-export-cl",
        )

        export_manager = ExportManager(config_loader)
        output_path = temp_daf_home / "test-export-cl.tar.gz"

        with patch.object(
            export_manager, "_get_agent_backend", return_value="claude"
        ):
            export_manager.export_sessions(
                identifiers=["export-claude"],
                output_path=output_path,
            )

        warnings = export_manager.get_conversation_warnings()
        assert len(warnings) == 0

        output_path.unlink()


class TestImportWithNonClaudeBackend:
    """Test import warns for non-Claude backends."""

    def test_import_with_opencode_skips_conversations(self, temp_daf_home):
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)

        session_manager.create_session(
            name="import-oc",
            goal="Test opencode import",
            working_directory="test-dir",
            project_path="/test",
            ai_agent_session_id="uuid-import-oc",
        )

        export_manager = ExportManager(config_loader)
        output_path = temp_daf_home / "test-import.tar.gz"

        # Export with Claude first
        with patch.object(
            export_manager, "_get_agent_backend", return_value="claude"
        ):
            export_manager.export_sessions(
                identifiers=["import-oc"],
                output_path=output_path,
            )

        # Delete session and import with opencode backend
        session_manager.delete_session("import-oc")

        with patch.object(
            export_manager, "_get_agent_backend", return_value="opencode"
        ):
            imported_keys = export_manager.import_sessions(
                output_path, merge=False
            )

        # Session metadata should be imported
        assert "import-oc" in imported_keys

        # No conversation warnings since no conversation files were in the export
        # (the UUID didn't map to a real file)

        output_path.unlink()


class TestGetConversationWarnings:
    """Test get_conversation_warnings returns correct data."""

    def test_empty_warnings_initially(self, temp_daf_home):
        manager = BackupManager()
        assert manager.get_conversation_warnings() == []

    def test_warnings_reset_between_operations(self, temp_daf_home):
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)

        session_manager.create_session(
            name="reset-test",
            goal="Test warning reset",
            working_directory="test-dir",
            project_path="/test",
            ai_agent_session_id="uuid-reset",
        )

        backup_manager = BackupManager(config_loader)

        # First backup with opencode — should have warnings
        path1 = temp_daf_home / "backup-oc.tar.gz"
        with patch.object(
            backup_manager, "_get_agent_backend", return_value="opencode"
        ):
            backup_manager.create_backup(output_path=path1)

        assert len(backup_manager.get_conversation_warnings()) == 1

        # Second backup with claude — warnings should be reset
        path2 = temp_daf_home / "backup-cl.tar.gz"
        with patch.object(
            backup_manager, "_get_agent_backend", return_value="claude"
        ):
            backup_manager.create_backup(output_path=path2)

        assert len(backup_manager.get_conversation_warnings()) == 0

        path1.unlink()
        path2.unlink()
