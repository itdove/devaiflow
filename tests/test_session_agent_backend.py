"""Tests for agent_backend persistence in sessions (issue #442).

Verifies that:
1. agent_backend is stored in Session model on creation
2. SessionManager.create_session() accepts agent_backend parameter
3. Stored agent_backend is used when reopening sessions
4. Backward compatible: sessions without agent_backend fall back to config
5. Agent-aware session existence check works correctly
6. Correct agent name is shown in messages
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from devflow.config.models import Session, ConversationContext, Conversation


class TestSessionAgentBackendField:
    """Test agent_backend field on Session model."""

    def test_session_has_agent_backend_field(self):
        """Test that Session model has agent_backend field."""
        session = Session(name="test", goal="test goal")
        assert hasattr(session, "agent_backend")

    def test_agent_backend_defaults_to_none(self):
        """Test that agent_backend defaults to None for backward compatibility."""
        session = Session(name="test", goal="test goal")
        assert session.agent_backend is None

    def test_agent_backend_can_be_set_to_claude(self):
        """Test setting agent_backend to claude."""
        session = Session(name="test", goal="test goal", agent_backend="claude")
        assert session.agent_backend == "claude"

    def test_agent_backend_can_be_set_to_opencode(self):
        """Test setting agent_backend to opencode."""
        session = Session(name="test", goal="test goal", agent_backend="opencode")
        assert session.agent_backend == "opencode"

    def test_agent_backend_can_be_set_to_ollama(self):
        """Test setting agent_backend to ollama."""
        session = Session(name="test", goal="test goal", agent_backend="ollama")
        assert session.agent_backend == "ollama"

    def test_agent_backend_serialization(self):
        """Test that agent_backend is included in JSON serialization."""
        session = Session(name="test", goal="test goal", agent_backend="opencode")
        data = session.model_dump(mode="json")
        assert "agent_backend" in data
        assert data["agent_backend"] == "opencode"

    def test_agent_backend_deserialization(self):
        """Test that agent_backend is correctly loaded from JSON."""
        data = {
            "name": "test",
            "goal": "test goal",
            "agent_backend": "opencode",
            "status": "created",
            "created": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }
        session = Session(**data)
        assert session.agent_backend == "opencode"

    def test_agent_backend_none_serialization(self):
        """Test that None agent_backend is preserved in serialization."""
        session = Session(name="test", goal="test goal")
        data = session.model_dump(mode="json")
        assert data["agent_backend"] is None

    def test_backward_compatible_without_agent_backend_key(self):
        """Test loading old sessions that don't have agent_backend key."""
        data = {
            "name": "test",
            "goal": "test goal",
            "status": "created",
            "created": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }
        session = Session(**data)
        assert session.agent_backend is None


class TestSessionManagerCreateWithAgentBackend:
    """Test SessionManager.create_session() with agent_backend parameter."""

    def test_create_session_with_agent_backend(self, tmp_path):
        """Test that create_session stores agent_backend."""
        from devflow.session.manager import SessionManager
        from devflow.config.loader import ConfigLoader

        config_dir = tmp_path / ".daf-sessions"
        config_dir.mkdir()

        config_loader = ConfigLoader(config_dir=config_dir)
        session_manager = SessionManager(config_loader=config_loader)

        session = session_manager.create_session(
            name="test-session",
            goal="test goal",
            agent_backend="opencode",
        )

        assert session.agent_backend == "opencode"

    def test_create_session_without_agent_backend(self, tmp_path):
        """Test that create_session defaults agent_backend to None."""
        from devflow.session.manager import SessionManager
        from devflow.config.loader import ConfigLoader

        config_dir = tmp_path / ".daf-sessions"
        config_dir.mkdir()

        config_loader = ConfigLoader(config_dir=config_dir)
        session_manager = SessionManager(config_loader=config_loader)

        session = session_manager.create_session(
            name="test-session",
            goal="test goal",
        )

        assert session.agent_backend is None

    def test_create_session_agent_backend_persisted(self, tmp_path):
        """Test that agent_backend is persisted to disk and can be loaded."""
        from devflow.session.manager import SessionManager
        from devflow.config.loader import ConfigLoader

        config_dir = tmp_path / ".daf-sessions"
        config_dir.mkdir()

        config_loader = ConfigLoader(config_dir=config_dir)
        session_manager = SessionManager(config_loader=config_loader)

        session_manager.create_session(
            name="test-session",
            goal="test goal",
            agent_backend="opencode",
        )

        # Load it back
        loaded_session = session_manager.get_session("test-session")
        assert loaded_session is not None
        assert loaded_session.agent_backend == "opencode"

    def test_agent_backend_persisted_in_metadata_json_file(self, tmp_path):
        """Test that agent_backend is written to metadata.json on disk (issue #507)."""
        from devflow.session.manager import SessionManager
        from devflow.config.loader import ConfigLoader

        config_dir = tmp_path / ".daf-sessions"
        config_dir.mkdir()

        config_loader = ConfigLoader(config_dir=config_dir)
        session_manager = SessionManager(config_loader=config_loader)

        session_manager.create_session(
            name="test-persist",
            goal="test goal",
            agent_backend="opencode",
        )

        # Read the actual metadata.json file from disk
        metadata_file = config_dir / "sessions" / "test-persist" / "metadata.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            metadata = json.load(f)

        assert "agent_backend" in metadata
        assert metadata["agent_backend"] == "opencode"

    def test_metadata_without_agent_backend_loads_gracefully(self, tmp_path):
        """Test backward compat: metadata.json without agent_backend defaults to None."""
        from devflow.session.manager import SessionManager
        from devflow.config.loader import ConfigLoader

        config_dir = tmp_path / ".daf-sessions"
        config_dir.mkdir()

        config_loader = ConfigLoader(config_dir=config_dir)
        session_manager = SessionManager(config_loader=config_loader)

        # Create session normally, then strip agent_backend from metadata.json
        session_manager.create_session(
            name="test-compat",
            goal="test goal",
            agent_backend="claude",
        )

        metadata_file = config_dir / "sessions" / "test-compat" / "metadata.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        del metadata["agent_backend"]

        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        # Rebuild session from metadata — should not error, agent_backend should be None
        session = Session(**metadata)
        assert session.agent_backend is None

    def test_update_session_persists_changed_agent_backend(self, tmp_path):
        """Test that updating agent_backend and calling update_session persists to disk."""
        from devflow.session.manager import SessionManager
        from devflow.config.loader import ConfigLoader

        config_dir = tmp_path / ".daf-sessions"
        config_dir.mkdir()

        config_loader = ConfigLoader(config_dir=config_dir)
        session_manager = SessionManager(config_loader=config_loader)

        session = session_manager.create_session(
            name="test-reopen",
            goal="test goal",
            agent_backend="claude",
        )

        # Simulate reopening with --agent opencode
        session.agent_backend = "opencode"
        session_manager.update_session(session)

        # Verify metadata.json on disk reflects the change
        metadata_file = config_dir / "sessions" / "test-reopen" / "metadata.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["agent_backend"] == "opencode"


class TestEffectiveAgentBackendResolution:
    """Test the resolution logic: session.agent_backend > config.agent_backend > 'claude'."""

    def test_session_backend_takes_precedence(self):
        """Test that session's stored backend takes precedence over config."""
        session = Session(name="test", goal="test", agent_backend="opencode")
        config_backend = "claude"

        effective = session.agent_backend or config_backend
        assert effective == "opencode"

    def test_config_backend_used_when_session_is_none(self):
        """Test that config backend is used when session has no stored backend."""
        session = Session(name="test", goal="test", agent_backend=None)
        config_backend = "opencode"

        effective = session.agent_backend or config_backend
        assert effective == "opencode"

    def test_default_claude_when_both_none(self):
        """Test that 'claude' is the final fallback."""
        session = Session(name="test", goal="test", agent_backend=None)
        config_backend = None

        effective = session.agent_backend or (config_backend or "claude")
        assert effective == "claude"


class TestAgentAwareSessionExistence:
    """Test that agent.session_exists() is used correctly for different backends."""

    def test_claude_session_exists_checks_file(self, tmp_path):
        """Test that ClaudeAgent.session_exists() checks .jsonl file."""
        from devflow.agent import ClaudeAgent

        agent = ClaudeAgent(claude_dir=tmp_path / ".claude")

        # Create the expected directory and file
        project_path = str(tmp_path / "my-project")
        os.makedirs(project_path, exist_ok=True)

        session_id = str(uuid.uuid4())
        encoded = agent.encode_project_path(project_path)
        session_dir = tmp_path / ".claude" / "projects" / encoded
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / f"{session_id}.jsonl").write_text('{"type":"test"}')

        assert agent.session_exists(session_id, project_path) is True

    def test_claude_session_not_exists_when_no_file(self, tmp_path):
        """Test that ClaudeAgent.session_exists() returns False when no file."""
        from devflow.agent import ClaudeAgent

        agent = ClaudeAgent(claude_dir=tmp_path / ".claude")
        project_path = str(tmp_path / "my-project")
        os.makedirs(project_path, exist_ok=True)

        session_id = str(uuid.uuid4())
        assert agent.session_exists(session_id, project_path) is False

    @patch("devflow.agent.opencode_agent.OpenCodeAgent.get_existing_sessions")
    def test_opencode_session_exists_queries_cli(self, mock_get_sessions, tmp_path):
        """Test that OpenCodeAgent.session_exists() queries via CLI."""
        from devflow.agent import OpenCodeAgent

        agent = OpenCodeAgent(opencode_dir=tmp_path / ".config" / "opencode")
        session_id = "ses_abc123def456"
        mock_get_sessions.return_value = {session_id, "ses_other"}

        assert agent.session_exists(session_id, str(tmp_path)) is True

    @patch("devflow.agent.opencode_agent.OpenCodeAgent.get_existing_sessions")
    def test_opencode_session_not_exists_when_not_in_list(self, mock_get_sessions, tmp_path):
        """Test that OpenCodeAgent.session_exists() returns False when ID not in list."""
        from devflow.agent import OpenCodeAgent

        agent = OpenCodeAgent(opencode_dir=tmp_path / ".config" / "opencode")
        mock_get_sessions.return_value = {"ses_other"}

        assert agent.session_exists("ses_abc123", str(tmp_path)) is False


class TestAgentBackendInExportImport:
    """Test that agent_backend is preserved during export/import."""

    def test_agent_backend_included_in_export(self):
        """Test that agent_backend is NOT excluded from session export."""
        session = Session(
            name="test",
            goal="test goal",
            agent_backend="opencode",
        )
        # The export code uses model_dump(exclude={'workspace_name'})
        # agent_backend should NOT be in the exclude set
        data = session.model_dump(mode="json", exclude={"workspace_name"})
        assert "agent_backend" in data
        assert data["agent_backend"] == "opencode"

    def test_agent_backend_none_excluded_from_export_is_fine(self):
        """Test that None agent_backend is handled in export."""
        session = Session(name="test", goal="test goal", agent_backend=None)
        data = session.model_dump(mode="json", exclude={"workspace_name"})
        assert data["agent_backend"] is None


class TestCopyConversationSkippedForNonFileAgents:
    """Test that _copy_conversation_to/from_temp is skipped for non-file-based agents."""

    def test_copy_conversation_skipped_for_opencode(self, tmp_path):
        """Test that conversation file copy is skipped for OpenCode sessions."""
        from devflow.cli.commands.open_command import _copy_conversation_to_temp

        session = Session(
            name="test",
            goal="test goal",
            agent_backend="opencode",
        )
        conv = ConversationContext(
            ai_agent_session_id="ses_abc123",
            project_path=str(tmp_path / "project"),
            original_project_path=str(tmp_path / "original"),
        )
        conversation = Conversation(active_session=conv)
        session.conversations["test-repo"] = conversation
        session.working_directory = "test-repo"

        # Should return False and skip without error
        result = _copy_conversation_to_temp(session, str(tmp_path / "temp"))
        assert result is False

    def test_copy_conversation_skipped_for_opencode_from_temp(self, tmp_path):
        """Test that conversation file save is skipped for OpenCode sessions."""
        from devflow.cli.commands.open_command import _copy_conversation_from_temp

        session = Session(
            name="test",
            goal="test goal",
            agent_backend="opencode",
        )
        conv = ConversationContext(
            ai_agent_session_id="ses_abc123",
            project_path=str(tmp_path / "project"),
            original_project_path=str(tmp_path / "original"),
        )
        conversation = Conversation(active_session=conv)
        session.conversations["test-repo"] = conversation
        session.working_directory = "test-repo"

        # Should return False and skip without error
        result = _copy_conversation_from_temp(session, str(tmp_path / "temp"))
        assert result is False
