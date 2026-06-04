"""Tests for OpenCode agent implementation."""

import json
import os
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
    def test_launch_with_prompt_interactive_no_prompt_flag(self, mock_popen, mock_require, tmp_path):
        """Test interactive launch does NOT pass --prompt; uses AGENTS.md trigger (#430)."""
        agent = OpenCodeAgent()
        mock_process = Mock()
        mock_popen.return_value = mock_process

        # Create a project directory with an existing AGENTS.md
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "AGENTS.md").write_text("# Agent instructions\n")

        result = agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="Fix the login bug",
            session_id="ses_abc123",
        )

        mock_require.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "opencode"
        assert "--prompt" not in cmd
        assert "Fix the login bug" not in cmd
        assert "--session" in cmd
        assert "ses_abc123" in cmd
        assert "run" not in cmd
        assert call_args[1]["cwd"] == str(project_dir)
        assert result == mock_process

        # Verify AGENTS.md was updated with trigger
        content = (project_dir / "AGENTS.md").read_text()
        assert agent.AGENTS_MD_TRIGGER in content

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
    def test_launch_with_prompt_auto_approve(self, mock_popen, mock_require, tmp_path):
        """Test launching OpenCode with auto-approve adds --dangerously-skip-permissions."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="Fix bug",
            session_id="test-id",
            auto_approve=True,
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--dangerously-skip-permissions" in cmd
        # Interactive mode: no --prompt (#430)
        assert "--prompt" not in cmd

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
    def test_launch_with_prompt_skips_uuid_session_id(self, mock_popen, mock_require, tmp_path):
        """Test that DevAIFlow UUID session IDs are NOT passed to --session."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="Fix bug",
            session_id="29798353-1758-43a9-b95a-05bac425c3f3",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--session" not in cmd
        # Interactive mode: no --prompt (#430)
        assert "--prompt" not in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_passes_ses_prefixed_session_id(self, mock_popen, mock_require, tmp_path):
        """Test that OpenCode session IDs (ses-prefixed) ARE passed to --session."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="Fix bug",
            session_id="ses_real_opencode_id",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--session" in cmd
        assert "ses_real_opencode_id" in cmd
        # Interactive mode: no --prompt (#430)
        assert "--prompt" not in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_empty_session_id(self, mock_popen, mock_require, tmp_path):
        """Test that empty session ID does not add --session flag."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="Fix bug",
            session_id="",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--session" not in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_empty_prompt_no_prompt_flag(self, mock_popen, mock_require, tmp_path):
        """Test interactive launch with empty prompt omits --prompt (#421, #430)."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="",
            session_id="ses_abc123",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd == ["opencode", "--session", "ses_abc123"]
        assert "--prompt" not in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_empty_prompt_no_session(self, mock_popen, mock_require, tmp_path):
        """Test interactive launch with empty prompt and UUID session ID."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="",
            session_id="29798353-1758-43a9-b95a-05bac425c3f3",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd == ["opencode"]
        assert "--prompt" not in cmd
        assert "--session" not in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_and_model(self, mock_popen, mock_require, tmp_path):
        """Test launching OpenCode with model provider profile."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="Fix bug",
            session_id="test-id",
            model_provider_profile={"model_name": "anthropic/claude-sonnet"},
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--model" in cmd
        assert "anthropic/claude-sonnet" in cmd
        # Interactive mode: no --prompt (#430)
        assert "--prompt" not in cmd

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


class TestOpenCodeAgentPermissions:
    """Test OpenCodeAgent permission prompt support."""

    def test_supports_permission_prompts_returns_true(self):
        """OpenCode supports permission prompts when launched without --prompt (#430)."""
        agent = OpenCodeAgent()
        assert agent.supports_permission_prompts() is True

    def test_supports_permission_prompts_is_consistent(self):
        """Multiple calls return same value."""
        agent = OpenCodeAgent()
        assert agent.supports_permission_prompts() is True
        assert agent.supports_permission_prompts() is True


class TestOpenCodeAgentAgentsMdTrigger:
    """Test AGENTS.md trigger for daf-workflow skill (#430, #433)."""

    def test_ensure_trigger_prepends_to_existing_agents_md(self, tmp_path):
        """Test trigger is prepended to an existing AGENTS.md (#433)."""
        agent = OpenCodeAgent()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        agents_md = project_dir / "AGENTS.md"
        agents_md.write_text("# Existing agent instructions\n\nSome content.\n")

        result = agent.ensure_agents_md_trigger(str(project_dir))

        assert result is True
        content = agents_md.read_text()
        assert "# Existing agent instructions" in content
        assert "Some content." in content
        assert agent.AGENTS_MD_TRIGGER in content
        # Trigger must be at the TOP of the file
        assert content.startswith(agent.AGENTS_MD_TRIGGER)

    def test_ensure_trigger_creates_agents_md_if_missing(self, tmp_path):
        """Test AGENTS.md is created with trigger when file does not exist."""
        agent = OpenCodeAgent()
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = agent.ensure_agents_md_trigger(str(project_dir))

        assert result is True
        agents_md = project_dir / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert content == f"{agent.AGENTS_MD_TRIGGER}\n"

    def test_ensure_trigger_idempotent(self, tmp_path):
        """Test calling ensure_agents_md_trigger twice does not duplicate."""
        agent = OpenCodeAgent()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "AGENTS.md").write_text("# Instructions\n")

        # First call adds trigger
        assert agent.ensure_agents_md_trigger(str(project_dir)) is True
        content_after_first = (project_dir / "AGENTS.md").read_text()

        # Second call is a no-op
        assert agent.ensure_agents_md_trigger(str(project_dir)) is False
        content_after_second = (project_dir / "AGENTS.md").read_text()

        assert content_after_first == content_after_second
        assert content_after_second.count(agent.AGENTS_MD_TRIGGER) == 1

    def test_ensure_trigger_preserves_existing_content(self, tmp_path):
        """Test existing AGENTS.md content is preserved below trigger (#433)."""
        agent = OpenCodeAgent()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        original = "# My Project\n\n## Guidelines\n\n- Follow PEP 8\n- Write tests\n"
        (project_dir / "AGENTS.md").write_text(original)

        agent.ensure_agents_md_trigger(str(project_dir))

        content = (project_dir / "AGENTS.md").read_text()
        # Trigger at top, existing content preserved below
        assert content.startswith(agent.AGENTS_MD_TRIGGER)
        assert original.strip() in content

    def test_ensure_trigger_already_present(self, tmp_path):
        """Test no modification when trigger block already exists."""
        agent = OpenCodeAgent()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        existing = f"{agent.AGENTS_MD_TRIGGER}\n\n# Instructions\n"
        (project_dir / "AGENTS.md").write_text(existing)

        result = agent.ensure_agents_md_trigger(str(project_dir))

        assert result is False
        assert (project_dir / "AGENTS.md").read_text() == existing

    def test_ensure_trigger_migrates_legacy_trigger(self, tmp_path):
        """Test legacy trigger at end is replaced with new block at top (#433)."""
        agent = OpenCodeAgent()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        agents_md = project_dir / "AGENTS.md"
        legacy_content = (
            "# My Project Instructions\n\n"
            "Follow the coding standards.\n\n"
            f"{agent._LEGACY_TRIGGER}\n"
        )
        agents_md.write_text(legacy_content)

        result = agent.ensure_agents_md_trigger(str(project_dir))

        assert result is True
        content = agents_md.read_text()
        # New trigger at the top
        assert content.startswith(agent.AGENTS_MD_TRIGGER)
        # Legacy trigger removed
        assert agent._LEGACY_TRIGGER not in content
        # Original content preserved
        assert "# My Project Instructions" in content
        assert "Follow the coding standards." in content

    def test_ensure_trigger_migrates_legacy_trigger_appended_with_newlines(self, tmp_path):
        """Test legacy trigger appended with \\n\\n prefix is cleaned up (#433)."""
        agent = OpenCodeAgent()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        agents_md = project_dir / "AGENTS.md"
        # Simulate the old append behavior: original content + \n\n + trigger + \n
        legacy_content = (
            "# Instructions\n\nSome content.\n"
            f"\n\n{agent._LEGACY_TRIGGER}\n"
        )
        agents_md.write_text(legacy_content)

        result = agent.ensure_agents_md_trigger(str(project_dir))

        assert result is True
        content = agents_md.read_text()
        assert content.startswith(agent.AGENTS_MD_TRIGGER)
        assert agent._LEGACY_TRIGGER not in content
        assert "# Instructions" in content
        assert "Some content." in content

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_interactive_updates_agents_md(self, mock_popen, mock_require, tmp_path):
        """Test interactive launch calls ensure_agents_md_trigger (#430)."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="Work on feature",
            session_id="test-id",
        )

        # AGENTS.md should have been created with trigger
        agents_md = project_dir / "AGENTS.md"
        assert agents_md.exists()
        assert agent.AGENTS_MD_TRIGGER in agents_md.read_text()

        # Command should NOT have --prompt
        cmd = mock_popen.call_args[0][0]
        assert "--prompt" not in cmd

    @patch("devflow.agent.opencode_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_headless_does_not_update_agents_md(self, mock_popen, mock_require, tmp_path):
        """Test headless launch does NOT modify AGENTS.md (#430)."""
        agent = OpenCodeAgent()
        mock_popen.return_value = Mock()

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        agent.launch_with_prompt(
            project_path=str(project_dir),
            initial_prompt="Work on feature",
            session_id="test-id",
            headless=True,
        )

        # AGENTS.md should NOT have been created
        agents_md = project_dir / "AGENTS.md"
        assert not agents_md.exists()

        # Command should have prompt via 'run'
        cmd = mock_popen.call_args[0][0]
        assert cmd[1] == "run"
        assert "Work on feature" in cmd


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
