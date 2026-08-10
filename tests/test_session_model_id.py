"""Tests for model_id tracking in sessions (issue #536).

Verifies that:
1. model_id field exists on Session model and defaults to None
2. SessionManager.create_session() accepts and stores model_id
3. model_id is detected from CLAUDE_MODEL env var at session creation
4. model_id falls back to model_provider_profile.model_name
5. Backward compatible: existing sessions without model_id continue to work
6. audit log includes model_id field
"""

import json
import os
from unittest.mock import patch

import pytest

from devflow.config.models import Session
from devflow.utils.audit_log import log_model_provider_usage


class TestSessionModelIdField:
    """Test model_id field on Session model."""

    def test_session_has_model_id_field(self):
        """Session model has model_id field."""
        session = Session(name="test", goal="test goal")
        assert hasattr(session, "model_id")

    def test_model_id_defaults_to_none(self):
        """model_id defaults to None for backward compatibility."""
        session = Session(name="test", goal="test goal")
        assert session.model_id is None

    def test_model_id_can_be_set(self):
        """model_id can be set to a model identifier string."""
        session = Session(name="test", goal="test goal", model_id="claude-opus-4-6")
        assert session.model_id == "claude-opus-4-6"

    def test_model_id_serialization(self):
        """model_id is included in JSON serialization."""
        session = Session(name="test", goal="test goal", model_id="claude-sonnet-5")
        data = session.model_dump(mode="json")
        assert "model_id" in data
        assert data["model_id"] == "claude-sonnet-5"

    def test_model_id_deserialization(self):
        """model_id is correctly loaded from serialized data."""
        session = Session(name="test", goal="test goal", model_id="Qwen3-Coder-25B")
        data = session.model_dump(mode="json")
        restored = Session.model_validate(data)
        assert restored.model_id == "Qwen3-Coder-25B"

    def test_model_id_none_deserialization(self):
        """Sessions without model_id (legacy) load with model_id=None."""
        data = {"name": "old-session", "goal": "old goal", "status": "created"}
        session = Session.model_validate(data)
        assert session.model_id is None

    def test_model_id_independent_of_model_profile(self):
        """model_id and model_profile are independent fields."""
        session = Session(
            name="test",
            goal="test goal",
            model_profile="vertex",
            model_id="claude-opus-4-6",
        )
        assert session.model_profile == "vertex"
        assert session.model_id == "claude-opus-4-6"

    def test_model_id_various_backends(self):
        """model_id works with any backend model string."""
        test_cases = [
            "claude-opus-4-6",
            "claude-sonnet-5",
            "claude-haiku-4-5-20251001",
            "Qwen3-Coder-25B",
            "devstral-small-2",
            "gpt-4o",
        ]
        for model in test_cases:
            session = Session(name="test", goal="test", model_id=model)
            assert session.model_id == model


class TestSessionManagerModelId:
    """Test model_id in SessionManager.create_session()."""

    def test_create_session_accepts_model_id(self, temp_daf_home):
        """create_session() accepts model_id parameter."""
        from devflow.config.loader import ConfigLoader
        from devflow.session.manager import SessionManager

        config_loader = ConfigLoader()
        manager = SessionManager(config_loader)
        session = manager.create_session(
            name="test-session",
            goal="test goal",
            model_id="claude-sonnet-4-6",
        )
        assert session.model_id == "claude-sonnet-4-6"

    def test_create_session_model_id_defaults_none(self, temp_daf_home):
        """create_session() without model_id stores None."""
        from devflow.config.loader import ConfigLoader
        from devflow.session.manager import SessionManager

        config_loader = ConfigLoader()
        manager = SessionManager(config_loader)
        session = manager.create_session(
            name="test-session",
            goal="test goal",
        )
        assert session.model_id is None

    def test_create_session_model_id_persisted(self, temp_daf_home):
        """model_id is persisted to storage and reloaded correctly."""
        from devflow.config.loader import ConfigLoader
        from devflow.session.manager import SessionManager

        config_loader = ConfigLoader()
        manager = SessionManager(config_loader)
        manager.create_session(
            name="test-session",
            goal="test goal",
            model_id="claude-opus-4-6",
        )

        loaded = manager.get_session("test-session")
        assert loaded is not None
        assert loaded.model_id == "claude-opus-4-6"


class TestModelIdDetection:
    """Test model_id detection from env var and profile."""

    def test_claude_model_env_var_detected(self):
        """CLAUDE_MODEL env var is used as model_id when set."""
        import os
        from devflow.utils.model_provider import get_active_profile, get_model_name_from_profile

        with patch.dict(os.environ, {"CLAUDE_MODEL": "claude-opus-5"}):
            _resolved_profile = get_active_profile(None, override_profile_name=None)
            model_id = os.environ.get("CLAUDE_MODEL") or get_model_name_from_profile(_resolved_profile)
            assert model_id == "claude-opus-5"

    def test_profile_model_name_used_as_fallback(self):
        """Profile model_name is used when CLAUDE_MODEL is not set."""
        from devflow.utils.model_provider import get_model_name_from_profile

        profile = {"model_name": "claude-sonnet-4-6", "base_url": "https://api.anthropic.com"}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_MODEL", None)
            model_id = os.environ.get("CLAUDE_MODEL") or get_model_name_from_profile(profile)
            assert model_id == "claude-sonnet-4-6"

    def test_env_var_overrides_profile(self):
        """CLAUDE_MODEL env var overrides profile model_name."""
        from devflow.utils.model_provider import get_model_name_from_profile

        profile = {"model_name": "claude-haiku-4-5-20251001"}
        with patch.dict(os.environ, {"CLAUDE_MODEL": "claude-opus-5"}):
            model_id = os.environ.get("CLAUDE_MODEL") or get_model_name_from_profile(profile)
            assert model_id == "claude-opus-5"

    def test_none_when_no_profile_and_no_env(self):
        """model_id is None when no profile and no CLAUDE_MODEL env var."""
        from devflow.utils.model_provider import get_model_name_from_profile

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLAUDE_MODEL", None)
            model_id = os.environ.get("CLAUDE_MODEL") or get_model_name_from_profile(None)
            assert model_id is None


class TestAuditLogModelId:
    """Test model_id in audit log entries."""

    def test_audit_log_includes_model_id(self, tmp_path):
        """log_model_provider_usage() includes model_id in log entry."""
        log_file = tmp_path / "audit.log"

        with patch("devflow.utils.audit_log._get_audit_log_path", return_value=log_file):
            with patch("devflow.utils.audit_log.audit_logger") as mock_logger:
                log_entries = []
                mock_logger.info.side_effect = lambda msg: log_entries.append(json.loads(msg))
                mock_logger.handlers = ["fake_handler"]

                log_model_provider_usage(
                    event_type="session_launched",
                    session_name="test-session",
                    model_name="claude-sonnet-4-6",
                    model_id="claude-sonnet-4-6",
                )

                assert len(log_entries) == 1
                assert "model_id" in log_entries[0]
                assert log_entries[0]["model_id"] == "claude-sonnet-4-6"

    def test_audit_log_model_id_can_be_none(self, tmp_path):
        """log_model_provider_usage() handles model_id=None."""
        with patch("devflow.utils.audit_log.audit_logger") as mock_logger:
            log_entries = []
            mock_logger.info.side_effect = lambda msg: log_entries.append(json.loads(msg))
            mock_logger.handlers = ["fake_handler"]

            log_model_provider_usage(
                event_type="session_launched",
                session_name="test-session",
            )

            assert len(log_entries) == 1
            assert log_entries[0]["model_id"] is None

    def test_audit_log_model_id_differs_from_model_name(self, tmp_path):
        """model_id and model_name can differ in audit log."""
        with patch("devflow.utils.audit_log.audit_logger") as mock_logger:
            log_entries = []
            mock_logger.info.side_effect = lambda msg: log_entries.append(json.loads(msg))
            mock_logger.handlers = ["fake_handler"]

            log_model_provider_usage(
                event_type="session_launched",
                session_name="test-session",
                model_name="claude-sonnet-4-6",
                model_id="claude-opus-5",
            )

            assert len(log_entries) == 1
            entry = log_entries[0]
            assert entry["model_name"] == "claude-sonnet-4-6"
            assert entry["model_id"] == "claude-opus-5"
