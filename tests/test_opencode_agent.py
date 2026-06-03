"""Tests for OpenCode agent implementation."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from devflow.agent.opencode_agent import OpenCodeAgent
from devflow.agent import create_agent_client


class TestOpenCodeAgentInit:
    """Test OpenCodeAgent initialization."""

    def test_init_default_opencode_dir(self):
        """Test OpenCodeAgent uses default ~/.config/opencode directory."""
        agent = OpenCodeAgent()

        assert agent.opencode_dir == Path.home() / ".config" / "opencode"

    def test_init_custom_opencode_dir(self):
        """Test OpenCodeAgent accepts custom directory."""
        custom_dir = Path("/tmp/custom-opencode")
        agent = OpenCodeAgent(opencode_dir=custom_dir)

        assert agent.opencode_dir == custom_dir

    def test_init_xdg_config_home(self, monkeypatch):
        """Test OpenCodeAgent respects XDG_CONFIG_HOME."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        agent = OpenCodeAgent()

        assert agent.opencode_dir == Path("/custom/config/opencode")

    def test_get_agent_name(self):
        """Test get_agent_name returns 'opencode'."""
        agent = OpenCodeAgent()
        assert agent.get_agent_name() == "opencode"

    def test_get_agent_home_dir(self):
        """Test get_agent_home_dir returns opencode_dir."""
        custom_dir = Path("/tmp/test-opencode")
        agent = OpenCodeAgent(opencode_dir=custom_dir)
        assert agent.get_agent_home_dir() == custom_dir

    def test_encode_project_path(self):
        """Test encode_project_path returns path as-is."""
        agent = OpenCodeAgent()
        path = "/home/user/project"
        assert agent.encode_project_path(path) == path


class TestOpenCodeAgentLaunch:
    """Test OpenCodeAgent launch and resume operations."""

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_session(self, mock_popen, mock_require):
        """Test launching a new OpenCode session."""
        agent = OpenCodeAgent()
        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_session("/home/user/project")

        mock_require.assert_called_once_with("opencode", "launch OpenCode AI assistant")
        mock_popen.assert_called_once_with(
            ["opencode"],
            cwd="/home/user/project",
            env=mock_popen.call_args[1]["env"],
        )
        assert result == mock_process

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_interactive_default(self, mock_popen, mock_require):
        """Test launching OpenCode with prompt defaults to interactive mode."""
        agent = OpenCodeAgent()
        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix the login bug",
            session_id="ses_abc123",
        )

        mock_require.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "opencode"
        assert "--prompt" in cmd
        assert "Fix the login bug" in cmd
        assert "--session" in cmd
        assert "ses_abc123" in cmd
        assert "run" not in cmd
        assert call_args[1]["cwd"] == "/home/user/project"
        assert result == mock_process

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_headless(self, mock_popen, mock_require):
        """Test launching OpenCode in headless mode uses 'opencode run'."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix the login bug",
            session_id="ses_headless123",
            headless=True,
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "opencode"
        assert cmd[1] == "run"
        assert "Fix the login bug" in cmd
        assert "--prompt" not in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_auto_approve(self, mock_popen, mock_require):
        """Test launching OpenCode with auto-approve adds --dangerously-skip-permissions."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="test-id",
            auto_approve=True,
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--dangerously-skip-permissions" in cmd
        assert "--prompt" in cmd  # still interactive

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_headless_and_auto_approve(self, mock_popen, mock_require):
        """Test launching OpenCode with both headless and auto-approve."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="test-id",
            headless=True,
            auto_approve=True,
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd[1] == "run"
        assert "--dangerously-skip-permissions" in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_skips_uuid_session_id(self, mock_popen, mock_require):
        """Test that DevAIFlow UUID session IDs are NOT passed to --session."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="29798353-1758-43a9-b95a-05bac425c3f3",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--session" not in cmd
        assert "--prompt" in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_passes_ses_prefixed_session_id(self, mock_popen, mock_require):
        """Test that OpenCode session IDs (ses-prefixed) ARE passed to --session."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="ses_real_opencode_id",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--session" in cmd
        assert "ses_real_opencode_id" in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_empty_session_id(self, mock_popen, mock_require):
        """Test that empty session ID does not add --session flag."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--session" not in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_and_model(self, mock_popen, mock_require):
        """Test launching OpenCode with model provider profile."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="test-id",
            model_provider_profile={"model_name": "anthropic/claude-sonnet"},
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--model" in cmd
        assert "anthropic/claude-sonnet" in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_resume_session(self, mock_popen, mock_require):
        """Test resuming an existing OpenCode session."""
        agent = OpenCodeAgent()
        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.resume_session("test-session-uuid", "/home/user/project")

        mock_require.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["opencode", "--session", "test-session-uuid"]
        assert result == mock_process


class TestOpenCodeAgentSessions:
    """Test OpenCodeAgent session management."""

    @patch("subprocess.run")
    def test_get_existing_sessions(self, mock_run):
        """Test getting existing sessions from CLI."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([
                {"id": "session-1", "name": "Test 1"},
                {"id": "session-2", "name": "Test 2"},
            ]),
        )

        sessions = agent.get_existing_sessions("/home/user/project")

        assert sessions == {"session-1", "session-2"}
        mock_run.assert_called_once_with(
            ["opencode", "session", "list", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd="/home/user/project",
        )

    @patch("subprocess.run")
    def test_get_existing_sessions_empty(self, mock_run):
        """Test getting sessions when none exist."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(returncode=0, stdout="[]")

        sessions = agent.get_existing_sessions("/home/user/project")
        assert sessions == set()

    @patch("subprocess.run")
    def test_get_existing_sessions_cli_failure(self, mock_run):
        """Test graceful handling when CLI fails."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(returncode=1, stdout="")

        sessions = agent.get_existing_sessions("/home/user/project")
        assert sessions == set()

    @patch("subprocess.run")
    def test_get_existing_sessions_not_installed(self, mock_run):
        """Test graceful handling when opencode is not installed."""
        agent = OpenCodeAgent()
        mock_run.side_effect = FileNotFoundError("opencode not found")

        sessions = agent.get_existing_sessions("/home/user/project")
        assert sessions == set()

    @patch("subprocess.run")
    def test_session_exists_true(self, mock_run):
        """Test session_exists returns True when session found."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([{"id": "test-uuid"}]),
        )

        assert agent.session_exists("test-uuid", "/home/user/project") is True

    @patch("subprocess.run")
    def test_session_exists_false(self, mock_run):
        """Test session_exists returns False when session not found."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([{"id": "other-uuid"}]),
        )

        assert agent.session_exists("test-uuid", "/home/user/project") is False

    @patch("subprocess.run")
    def test_get_session_message_count(self, mock_run):
        """Test getting message count from export."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                    {"role": "user", "content": "bye"},
                ]
            }),
        )

        count = agent.get_session_message_count("test-uuid", "/home/user/project")
        assert count == 3

    @patch("subprocess.run")
    def test_get_session_message_count_failure(self, mock_run):
        """Test message count returns 0 on failure."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(returncode=1, stdout="")

        count = agent.get_session_message_count("test-uuid", "/home/user/project")
        assert count == 0

    @patch("subprocess.run")
    def test_get_session_message_count_list_format(self, mock_run):
        """Test message count when export returns a list."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([{"role": "user"}, {"role": "assistant"}]),
        )

        count = agent.get_session_message_count("test-uuid", "/home/user/project")
        assert count == 2


class TestOpenCodeAgentTokenUsage:
    """Test OpenCodeAgent token usage extraction."""

    @patch("subprocess.run")
    def test_extract_token_usage(self, mock_run):
        """Test extracting token usage from stats."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({
                "input_tokens": 1000,
                "output_tokens": 500,
                "total_tokens": 1500,
                "total_cost": 0.025,
            }),
        )

        usage = agent.extract_token_usage("test-uuid", "/home/user/project")

        assert usage is not None
        assert usage["input_tokens"] == 1000
        assert usage["output_tokens"] == 500
        assert usage["total_tokens"] == 1500
        assert usage["total_cost"] == 0.025

    @patch("subprocess.run")
    def test_extract_token_usage_failure(self, mock_run):
        """Test token usage returns None on failure."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(returncode=1, stdout="")

        usage = agent.extract_token_usage("test-uuid", "/home/user/project")
        assert usage is None

    @patch("subprocess.run")
    def test_extract_token_usage_not_installed(self, mock_run):
        """Test token usage returns None when opencode not installed."""
        agent = OpenCodeAgent()
        mock_run.side_effect = FileNotFoundError("opencode not found")

        usage = agent.extract_token_usage("test-uuid", "/home/user/project")
        assert usage is None


class TestOpenCodeAgentDbPath:
    """Test OpenCodeAgent database path resolution."""

    @patch("subprocess.run")
    def test_get_db_path_from_cli(self, mock_run):
        """Test getting db path from opencode db path command."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(
            returncode=0,
            stdout="/home/user/.local/share/opencode/opencode.db\n",
        )

        path = agent._get_db_path()
        assert path == Path("/home/user/.local/share/opencode/opencode.db")

    @patch("subprocess.run")
    def test_get_db_path_fallback(self, mock_run):
        """Test db path falls back to config dir when CLI fails."""
        agent = OpenCodeAgent(opencode_dir=Path("/tmp/test-opencode"))
        mock_run.return_value = Mock(returncode=1, stdout="")

        path = agent._get_db_path()
        assert path == Path("/tmp/test-opencode")

    @patch("subprocess.run")
    def test_get_session_file_path(self, mock_run):
        """Test get_session_file_path returns db path."""
        agent = OpenCodeAgent(opencode_dir=Path("/tmp/test-opencode"))
        mock_run.return_value = Mock(returncode=1, stdout="")

        path = agent.get_session_file_path("test-uuid", "/home/user/project")
        assert path == Path("/tmp/test-opencode")


class TestOpenCodeAgentCaptureSession:
    """Test OpenCodeAgent session capture."""

    @patch("devflow.agent.opencode_agent.time.sleep")
    @patch("subprocess.run")
    def test_capture_session_id_success(self, mock_run, mock_sleep):
        """Test capturing a new session ID."""
        agent = OpenCodeAgent()

        # First call: no sessions, second call: one new session
        mock_run.side_effect = [
            Mock(returncode=0, stdout=json.dumps([])),
            Mock(returncode=0, stdout=json.dumps([{"id": "new-session-123"}])),
        ]

        session_id = agent.capture_session_id("/home/user/project")
        assert session_id == "new-session-123"

    @patch("devflow.agent.opencode_agent.time.sleep")
    @patch("subprocess.run")
    def test_capture_session_id_timeout(self, mock_run, mock_sleep):
        """Test session capture raises TimeoutError."""
        agent = OpenCodeAgent()
        mock_run.return_value = Mock(returncode=0, stdout=json.dumps([]))

        with pytest.raises(TimeoutError, match="Failed to detect new OpenCode session"):
            agent.capture_session_id("/home/user/project", timeout=1, poll_interval=0.5)


class TestOpenCodeAgentFactory:
    """Test factory integration for OpenCodeAgent."""

    def test_factory_creates_opencode_agent(self):
        """Test factory creates OpenCodeAgent for 'opencode' backend."""
        agent = create_agent_client("opencode")
        assert isinstance(agent, OpenCodeAgent)
        assert agent.get_agent_name() == "opencode"

    def test_factory_opencode_ai_alias(self):
        """Test factory accepts 'opencode-ai' alias."""
        agent = create_agent_client("opencode-ai")
        assert isinstance(agent, OpenCodeAgent)

    def test_factory_custom_home(self):
        """Test factory passes custom agent_home to OpenCodeAgent."""
        custom_home = Path("/tmp/custom-opencode")
        agent = create_agent_client("opencode", agent_home=custom_home)
        assert isinstance(agent, OpenCodeAgent)
        assert agent.opencode_dir == custom_home

    def test_crush_still_works(self):
        """Test 'crush' backend still creates CrushAgent."""
        from devflow.agent.crush_agent import CrushAgent
        agent = create_agent_client("crush")
        assert isinstance(agent, CrushAgent)
        assert agent.get_agent_name() == "crush"
