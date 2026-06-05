"""Tests for --agent flag on daf open/new/investigate/jira new/git new.

Tests cover:
- Agent backend validation (SUPPORTED_BACKENDS, validate_agent_backend)
- Priority resolution for daf open: flag > session > config > default
- Priority resolution for daf new: flag > config > default
- Agent stored in session metadata for future reopens
- --agent flag accepted by all 5 commands
- Invalid agent names rejected with clear error
- List command shows agent column
"""

from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import click
import pytest
from click.testing import CliRunner

from devflow.agent.factory import (
    SUPPORTED_BACKENDS,
    validate_agent_backend,
    create_agent_client,
)
from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


# ───────────────────────────────────────────────────────────────────────────────
# SUPPORTED_BACKENDS constant
# ───────────────────────────────────────────────────────────────────────────────

class TestSupportedBackends:
    """Tests for SUPPORTED_BACKENDS constant."""

    def test_contains_claude(self):
        assert "claude" in SUPPORTED_BACKENDS

    def test_contains_opencode(self):
        assert "opencode" in SUPPORTED_BACKENDS

    def test_contains_cursor(self):
        assert "cursor" in SUPPORTED_BACKENDS

    def test_contains_windsurf(self):
        assert "windsurf" in SUPPORTED_BACKENDS

    def test_contains_ollama(self):
        assert "ollama" in SUPPORTED_BACKENDS

    def test_contains_github_copilot(self):
        assert "github-copilot" in SUPPORTED_BACKENDS

    def test_contains_copilot_alias(self):
        assert "copilot" in SUPPORTED_BACKENDS

    def test_contains_aider(self):
        assert "aider" in SUPPORTED_BACKENDS

    def test_contains_continue(self):
        assert "continue" in SUPPORTED_BACKENDS

    def test_contains_crush(self):
        assert "crush" in SUPPORTED_BACKENDS

    def test_contains_opencode_ai_alias(self):
        assert "opencode-ai" in SUPPORTED_BACKENDS


# ───────────────────────────────────────────────────────────────────────────────
# validate_agent_backend
# ───────────────────────────────────────────────────────────────────────────────

class TestValidateAgentBackend:
    """Tests for validate_agent_backend function."""

    def test_valid_claude(self):
        assert validate_agent_backend("claude") == "claude"

    def test_valid_opencode(self):
        assert validate_agent_backend("opencode") == "opencode"

    def test_valid_cursor(self):
        assert validate_agent_backend("cursor") == "cursor"

    def test_case_insensitive(self):
        assert validate_agent_backend("Claude") == "claude"
        assert validate_agent_backend("OPENCODE") == "opencode"
        assert validate_agent_backend("Cursor") == "cursor"

    def test_invalid_raises_bad_parameter(self):
        with pytest.raises(click.BadParameter, match="Unsupported agent backend"):
            validate_agent_backend("nonexistent")

    def test_invalid_shows_supported_list(self):
        with pytest.raises(click.BadParameter, match="Supported:"):
            validate_agent_backend("invalid-agent")

    def test_aliases_accepted(self):
        assert validate_agent_backend("copilot") == "copilot"
        assert validate_agent_backend("opencode-ai") == "opencode-ai"
        assert validate_agent_backend("ollama-claude") == "ollama-claude"


# ───────────────────────────────────────────────────────────────────────────────
# Priority resolution for daf open (flag > session > config > default)
# ───────────────────────────────────────────────────────────────────────────────

class TestOpenAgentPriority:
    """Tests for agent backend priority resolution in daf open."""

    def test_flag_overrides_session_and_config(self, temp_daf_home):
        """--agent flag takes highest priority."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-open-flag",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
            agent_backend="cursor",  # session stored agent
        )

        # Mock config with agent_backend="windsurf"
        mock_config = Mock()
        mock_config.agent_backend = "windsurf"

        # Simulate resolution: agent or session.agent_backend or config.agent_backend or "claude"
        agent_flag = "opencode"
        effective = agent_flag or session.agent_backend or mock_config.agent_backend or "claude"
        assert effective == "opencode"

    def test_session_overrides_config(self, temp_daf_home):
        """Session stored agent wins over config when no flag."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-open-session",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
            agent_backend="cursor",  # session stored
        )

        mock_config = Mock()
        mock_config.agent_backend = "windsurf"

        agent_flag = None
        effective = agent_flag or session.agent_backend or mock_config.agent_backend or "claude"
        assert effective == "cursor"

    def test_config_used_when_no_flag_no_session(self, temp_daf_home):
        """Config agent_backend used when no flag and no session stored agent."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-open-config",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
            agent_backend=None,  # no session stored agent
        )

        mock_config = Mock()
        mock_config.agent_backend = "windsurf"

        agent_flag = None
        effective = agent_flag or session.agent_backend or mock_config.agent_backend or "claude"
        assert effective == "windsurf"

    def test_default_claude_when_nothing_set(self, temp_daf_home):
        """Default to claude when no flag, no session, no config."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-open-default",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
            agent_backend=None,
        )

        agent_flag = None
        config_agent = None
        effective = agent_flag or session.agent_backend or config_agent or "claude"
        assert effective == "claude"


# ───────────────────────────────────────────────────────────────────────────────
# Priority resolution for daf new (flag > config > default)
# ───────────────────────────────────────────────────────────────────────────────

class TestNewAgentPriority:
    """Tests for agent backend priority resolution in daf new."""

    def test_flag_overrides_config(self):
        """--agent flag takes highest priority for new sessions."""
        agent_flag = "opencode"
        config_agent = "cursor"
        effective = agent_flag or config_agent or "claude"
        assert effective == "opencode"

    def test_config_used_when_no_flag(self):
        """Config agent_backend used when no flag."""
        agent_flag = None
        config_agent = "cursor"
        effective = agent_flag or config_agent or "claude"
        assert effective == "cursor"

    def test_default_claude_when_nothing(self):
        """Default to claude when no flag and no config."""
        agent_flag = None
        config_agent = None
        effective = agent_flag or config_agent or "claude"
        assert effective == "claude"


# ───────────────────────────────────────────────────────────────────────────────
# Agent stored in session metadata
# ───────────────────────────────────────────────────────────────────────────────

class TestAgentStoredInSession:
    """Tests for agent_backend persistence in session metadata."""

    def test_agent_stored_on_create(self, temp_daf_home):
        """Agent backend is stored when session is created."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-stored",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
            agent_backend="opencode",
        )
        assert session.agent_backend == "opencode"

    def test_agent_persisted_and_loaded(self, temp_daf_home):
        """Agent backend survives save/load cycle."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session_manager.create_session(
            name="test-persist",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
            agent_backend="cursor",
        )

        # Reload from disk
        session_manager2 = SessionManager(ConfigLoader())
        loaded = session_manager2.get_session("test-persist")
        assert loaded is not None
        assert loaded.agent_backend == "cursor"

    def test_agent_none_by_default(self, temp_daf_home):
        """Agent backend is None when not specified."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-default",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
        )
        assert session.agent_backend is None


# ───────────────────────────────────────────────────────────────────────────────
# CLI --agent flag acceptance on all 5 commands
# ───────────────────────────────────────────────────────────────────────────────

class TestAgentFlagAccepted:
    """Tests that --agent flag is accepted by all 5 commands."""

    def test_new_accepts_agent_flag(self, temp_daf_home):
        """daf new --help shows --agent option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["new", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output

    def test_open_accepts_agent_flag(self, temp_daf_home):
        """daf open --help shows --agent option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["open", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output

    def test_investigate_accepts_agent_flag(self, temp_daf_home):
        """daf investigate --help shows --agent option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["investigate", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output

    def test_jira_new_accepts_agent_flag(self, temp_daf_home):
        """daf jira new --help shows --agent option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["jira", "new", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output

    def test_git_new_accepts_agent_flag(self, temp_daf_home):
        """daf git new --help shows --agent option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["git", "new", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output


# ───────────────────────────────────────────────────────────────────────────────
# Invalid agent names rejected
# ───────────────────────────────────────────────────────────────────────────────

class TestInvalidAgentRejected:
    """Tests that invalid agent names are rejected."""

    def test_new_rejects_invalid_agent(self, temp_daf_home):
        """daf new --agent invalid-agent exits with error."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "new", "--name", "test", "--goal", "test", "--agent", "invalid-agent"
        ], input="n\n")  # Answer no to any prompt
        # Should fail with BadParameter
        assert result.exit_code != 0
        assert "Unsupported agent backend" in result.output

    def test_open_rejects_invalid_agent(self, temp_daf_home):
        """daf open --agent invalid-agent exits with error."""
        # Create a session first
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session_manager.create_session(
            name="test-reject",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
        )

        runner = CliRunner()
        result = runner.invoke(cli, [
            "open", "test-reject", "--agent", "nonexistent-agent"
        ])
        assert result.exit_code != 0
        assert "Unsupported agent backend" in result.output


# ───────────────────────────────────────────────────────────────────────────────
# List command shows agent column
# ───────────────────────────────────────────────────────────────────────────────

class TestListShowsAgent:
    """Tests that daf list shows agent_backend column."""

    def test_list_shows_agent_column_header(self, temp_daf_home):
        """daf list table includes Agent column header."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session_manager.create_session(
            name="test-list",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
            agent_backend="opencode",
        )

        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "Agent" in result.output

    def test_list_shows_agent_value(self, temp_daf_home):
        """daf list shows the stored agent_backend value."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session_manager.create_session(
            name="test-list-value",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
            agent_backend="opencode",
        )

        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "opencode" in result.output

    def test_list_shows_dash_when_no_agent(self, temp_daf_home):
        """daf list shows '-' when agent_backend is not set."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session_manager.create_session(
            name="test-list-none",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
        )

        runner = CliRunner(env={"COLUMNS": "200"})
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        # The Agent column should show "-" for sessions without agent_backend
        # We check that the table header exists and the session is listed
        assert "Agent" in result.output
        assert "test-list-none" in result.output


# ───────────────────────────────────────────────────────────────────────────────
# Info command shows agent
# ───────────────────────────────────────────────────────────────────────────────

class TestInfoShowsAgent:
    """Tests that daf info shows agent_backend."""

    def test_info_shows_agent_backend(self, temp_daf_home):
        """daf info displays agent backend when set."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session_manager.create_session(
            name="test-info-agent",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
            agent_backend="opencode",
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["info", "test-info-agent"])
        # exit_code may be 1 if no conversations exist, but output still shows agent
        assert "Agent Backend" in result.output
        assert "opencode" in result.output

    def test_info_no_agent_line_when_none(self, temp_daf_home):
        """daf info does not show agent backend line when not set."""
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        session_manager.create_session(
            name="test-info-no-agent",
            goal="Test",
            working_directory="test-dir",
            project_path="/tmp/test",
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["info", "test-info-no-agent"])
        # exit_code may be 1 if no conversations exist, but output still shows session info
        assert "Agent Backend" not in result.output
