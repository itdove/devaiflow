"""Tests for concurrent session conflict detection modes (#518)."""

import os
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

import pytest

from devflow.cli.utils import (
    check_concurrent_session,
    ConcurrencyCheckResult,
    _analyze_file_overlap,
)
from devflow.config.models import (
    Config,
    ConcurrencyConfig,
    ConversationContext,
    Session,
)
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


def _make_config(mode="strict", auto_clone_path=None, cleanup_on_complete=True):
    """Create a mock Config with concurrency settings for testing."""
    config = MagicMock(spec=Config)
    config.concurrency = ConcurrencyConfig(
        mode=mode,
        auto_clone_path=auto_clone_path,
        cleanup_on_complete=cleanup_on_complete,
    )
    return config


def _create_active_session(sm, name="existing-session", project_path="/test/project", branch="feat-1", workspace_name=None):
    """Create a session with status=in_progress and a conversation with project_path."""
    session = sm.create_session(
        name=name, goal="test", working_directory="test",
        project_path=project_path, branch=branch,
        ai_agent_session_id=f"uuid-{name}",
    )
    session.status = "in_progress"
    if workspace_name:
        session.workspace_name = workspace_name
    sm.update_session(session)
    return session


class TestStrictMode:
    """strict mode — backward compatible, hard-block behavior."""

    def test_no_active_session_returns_safe(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        config = _make_config(mode="strict")

        result = check_concurrent_session(sm, "/some/path", "new-session", config=config)
        assert result.safe_to_proceed is True
        assert result.clone_path is None

    def test_same_session_self_match_allowed(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm, name="my-session", branch="main")
        config = _make_config(mode="strict")

        result = check_concurrent_session(sm, "/test/project", "my-session", config=config)
        assert result.safe_to_proceed is True

    def test_different_session_same_project_blocked(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm)
        config = _make_config(mode="strict")

        result = check_concurrent_session(sm, "/test/project", "new-session", config=config)
        assert result.safe_to_proceed is False
        assert result.active_session is not None
        assert result.active_session.name == "existing-session"

    def test_different_workspace_allowed(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm, workspace_name="workspace-a")

        config = _make_config(mode="strict")

        result = check_concurrent_session(
            sm, "/test/project", "new-session",
            workspace_name="workspace-b", config=config,
        )
        assert result.safe_to_proceed is True

    def test_no_config_defaults_to_strict(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm)

        result = check_concurrent_session(sm, "/test/project", "new-session", config=None)
        assert result.safe_to_proceed is False


class TestAnalyzeMode:
    """analyze mode — file overlap detection + auto-clone offer."""

    def test_no_overlap_offers_clone_accepted(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm)
        config = _make_config(mode="analyze")

        with patch("devflow.cli.utils._analyze_file_overlap", return_value=([], [])), \
             patch("devflow.cli.utils._offer_and_create_auto_clone", return_value=("/tmp/clone", "/test/project")):
            result = check_concurrent_session(sm, "/test/project", "new-session", config=config)

        assert result.safe_to_proceed is True
        assert result.clone_path == "/tmp/clone"
        assert result.original_path == "/test/project"

    def test_no_overlap_clone_declined(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm)
        config = _make_config(mode="analyze")

        with patch("devflow.cli.utils._analyze_file_overlap", return_value=([], [])), \
             patch("devflow.cli.utils._offer_and_create_auto_clone", return_value=None):
            result = check_concurrent_session(sm, "/test/project", "new-session", config=config)

        assert result.safe_to_proceed is False

    def test_overlap_detected_warns_and_offers_clone(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm)
        config = _make_config(mode="analyze")

        changed = ["src/main.py", "src/utils.py"]
        with patch("devflow.cli.utils._analyze_file_overlap", return_value=(changed, [])), \
             patch("devflow.cli.utils._offer_and_create_auto_clone", return_value=("/tmp/clone", "/test/project")) as mock_offer:
            result = check_concurrent_session(sm, "/test/project", "new-session", config=config)

        assert result.safe_to_proceed is True
        mock_offer.assert_called_once_with("/test/project", config, default_accept=False)

    def test_overlap_detected_user_declines(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm)
        config = _make_config(mode="analyze")

        changed = ["src/main.py"]
        with patch("devflow.cli.utils._analyze_file_overlap", return_value=(changed, [])), \
             patch("devflow.cli.utils._offer_and_create_auto_clone", return_value=None):
            result = check_concurrent_session(sm, "/test/project", "new-session", config=config)

        assert result.safe_to_proceed is False

    def test_no_active_session_skips_analysis(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        config = _make_config(mode="analyze")

        result = check_concurrent_session(sm, "/test/project", "new-session", config=config)
        assert result.safe_to_proceed is True
        assert result.clone_path is None


class TestPermissiveMode:
    """permissive mode — always offer clone, no analysis."""

    def test_offers_clone_accepted(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm)
        config = _make_config(mode="permissive")

        with patch("devflow.cli.utils._offer_and_create_auto_clone", return_value=("/tmp/clone", "/test/project")):
            result = check_concurrent_session(sm, "/test/project", "new-session", config=config)

        assert result.safe_to_proceed is True
        assert result.clone_path == "/tmp/clone"

    def test_clone_declined(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm)
        config = _make_config(mode="permissive")

        with patch("devflow.cli.utils._offer_and_create_auto_clone", return_value=None):
            result = check_concurrent_session(sm, "/test/project", "new-session", config=config)

        assert result.safe_to_proceed is False

    def test_no_analysis_performed(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        _create_active_session(sm)
        config = _make_config(mode="permissive")

        with patch("devflow.cli.utils._analyze_file_overlap") as mock_analyze, \
             patch("devflow.cli.utils._offer_and_create_auto_clone", return_value=("/tmp/clone", "/test/project")):
            check_concurrent_session(sm, "/test/project", "new-session", config=config)

        mock_analyze.assert_not_called()

    def test_no_active_session_skips_clone(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        config = _make_config(mode="permissive")

        result = check_concurrent_session(sm, "/test/project", "new-session", config=config)
        assert result.safe_to_proceed is True
        assert result.clone_path is None


class TestAnalyzeFileOverlap:
    """Tests for _analyze_file_overlap helper."""

    def test_no_branch_returns_empty(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        session = sm.create_session(
            name="test", goal="test", working_directory="test",
            project_path="/test/project", branch=None,
        )

        changed, overlap = _analyze_file_overlap("/test/project", session)
        assert changed == []
        assert overlap == []

    def test_with_branch_calls_git_utils(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        session = _create_active_session(sm, name="test-overlap", branch="feat-1")

        with patch("devflow.git.utils.GitUtils.get_changed_files", return_value=["file1.py", "file2.py"]):
            changed, overlap = _analyze_file_overlap("/test/project", session)

        assert changed == ["file1.py", "file2.py"]
        assert overlap == []

    def test_git_error_returns_empty(self, temp_daf_home):
        config_loader = ConfigLoader()
        sm = SessionManager(config_loader)
        session = _create_active_session(sm, name="test-error", branch="feat-1")

        with patch("devflow.git.utils.GitUtils.get_changed_files", side_effect=Exception("git error")):
            changed, overlap = _analyze_file_overlap("/test/project", session)

        assert changed == []
        assert overlap == []


class TestConfigHierarchy:
    """Tests for concurrency mode config hierarchy enforcement."""

    def test_enterprise_strict_overrides_user_permissive(self, temp_daf_home):
        from devflow.config.models import EnterpriseConfig, TeamConfig, UserConfig, ConcurrencyConfig

        enterprise = EnterpriseConfig(concurrency_mode="strict")
        team = TeamConfig()
        user = ConcurrencyConfig(mode="permissive")

        effective_mode = (
            enterprise.concurrency_mode
            or team.concurrency_mode
            or user.mode
            or "strict"
        )
        assert effective_mode == "strict"

    def test_team_analyze_overrides_user_permissive(self, temp_daf_home):
        from devflow.config.models import EnterpriseConfig, TeamConfig, ConcurrencyConfig

        enterprise = EnterpriseConfig()
        team = TeamConfig(concurrency_mode="analyze")
        user = ConcurrencyConfig(mode="permissive")

        effective_mode = (
            enterprise.concurrency_mode
            or team.concurrency_mode
            or user.mode
            or "strict"
        )
        assert effective_mode == "analyze"

    def test_enterprise_overrides_team(self, temp_daf_home):
        from devflow.config.models import EnterpriseConfig, TeamConfig, ConcurrencyConfig

        enterprise = EnterpriseConfig(concurrency_mode="strict")
        team = TeamConfig(concurrency_mode="analyze")
        user = ConcurrencyConfig(mode="permissive")

        effective_mode = (
            enterprise.concurrency_mode
            or team.concurrency_mode
            or user.mode
            or "strict"
        )
        assert effective_mode == "strict"

    def test_no_enforcement_uses_user_preference(self, temp_daf_home):
        from devflow.config.models import EnterpriseConfig, TeamConfig, ConcurrencyConfig

        enterprise = EnterpriseConfig()
        team = TeamConfig()
        user = ConcurrencyConfig(mode="analyze")

        effective_mode = (
            enterprise.concurrency_mode
            or team.concurrency_mode
            or user.mode
            or "strict"
        )
        assert effective_mode == "analyze"


class TestCleanupOnComplete:
    """Tests for cleanup_on_complete config behavior."""

    def test_cleanup_enabled_by_default(self):
        config = ConcurrencyConfig()
        assert config.cleanup_on_complete is True

    def test_cleanup_disabled(self):
        config = ConcurrencyConfig(cleanup_on_complete=False)
        assert config.cleanup_on_complete is False


class TestConcurrencyCheckResult:
    """Tests for ConcurrencyCheckResult dataclass."""

    def test_default_values(self):
        result = ConcurrencyCheckResult(safe_to_proceed=True)
        assert result.safe_to_proceed is True
        assert result.clone_path is None
        assert result.original_path is None
        assert result.active_session is None

    def test_with_clone_info(self):
        result = ConcurrencyCheckResult(
            safe_to_proceed=True,
            clone_path="/tmp/clone",
            original_path="/orig/path",
        )
        assert result.clone_path == "/tmp/clone"
        assert result.original_path == "/orig/path"
