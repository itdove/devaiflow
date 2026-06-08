"""Tests for agent interface abstraction."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, ANY

import pytest

from devflow.agent import (
    AgentInterface,
    ClaudeAgent,
    OllamaClaudeAgent,
    GitHubCopilotAgent,
    CursorAgent,
    WindsurfAgent,
    AiderAgent,
    ContinueAgent,
    CrushAgent,
    OpenCodeAgent,
    create_agent_client,
    get_agent_display_name,
    AGENT_DISPLAY_NAMES,
)
from devflow.utils.dependencies import ToolNotFoundError


class TestAgentInterface:
    """Test AgentInterface abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that AgentInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AgentInterface()

    def test_abstract_methods_defined(self):
        """Test that all required abstract methods are defined."""
        required_methods = [
            "launch_session",
            "resume_session",
            "capture_session_id",
            "get_session_file_path",
            "session_exists",
            "get_existing_sessions",
            "get_session_message_count",
            "encode_project_path",
            "get_agent_home_dir",
            "get_agent_name",
        ]

        for method_name in required_methods:
            assert hasattr(AgentInterface, method_name)


class TestClaudeAgent:
    """Test ClaudeAgent implementation."""

    def test_init_default_claude_dir(self):
        """Test ClaudeAgent initialization with default claude_dir."""
        agent = ClaudeAgent()

        assert agent.claude_dir == Path.home() / ".claude"
        assert agent.projects_dir == Path.home() / ".claude" / "projects"

    def test_init_custom_claude_dir(self):
        """Test ClaudeAgent initialization with custom claude_dir."""
        custom_dir = Path("/tmp/custom-claude")
        agent = ClaudeAgent(claude_dir=custom_dir)

        assert agent.claude_dir == custom_dir
        assert agent.projects_dir == custom_dir / "projects"

    def test_get_agent_name(self):
        """Test get_agent_name returns 'claude'."""
        agent = ClaudeAgent()
        assert agent.get_agent_name() == "claude"

    def test_get_agent_home_dir(self):
        """Test get_agent_home_dir returns claude_dir."""
        custom_dir = Path("/tmp/claude")
        agent = ClaudeAgent(claude_dir=custom_dir)
        assert agent.get_agent_home_dir() == custom_dir

    def test_encode_project_path(self):
        """Test encode_project_path replaces / and _ with -."""
        agent = ClaudeAgent()

        # Test / replacement
        assert agent.encode_project_path("/home/user/project") == "-home-user-project"

        # Test _ replacement
        assert agent.encode_project_path("/home/my_project") == "-home-my-project"

        # Test both
        assert agent.encode_project_path("/home/user/my_project") == "-home-user-my-project"

    @patch("devflow.agent.claude_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_session(self, mock_popen, mock_require_tool):
        """Test launch_session calls claude code command."""
        agent = ClaudeAgent()
        project_path = "/home/user/project"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_session(
            project_path,
            model_provider_profile=None,
            session_name=None,
            profile_name=None,
            enforcement_source=None
        )

        mock_require_tool.assert_called_once_with("claude", "launch Claude Code session")
        mock_popen.assert_called_once_with(
            ["claude", "code"],
            cwd=project_path,
            env=ANY,
        )
        assert result == mock_process

    @patch("devflow.agent.claude_agent.require_tool")
    @patch("subprocess.Popen")
    def test_resume_session(self, mock_popen, mock_require_tool):
        """Test resume_session calls claude --resume command."""
        agent = ClaudeAgent()
        project_path = "/home/user/project"
        session_id = "test-session-uuid"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.resume_session(session_id, project_path)

        mock_require_tool.assert_called_once_with("claude", "resume Claude Code session")
        mock_popen.assert_called_once_with(
            ["claude", "--resume", session_id],
            cwd=project_path,
            env=ANY,
        )
        assert result == mock_process

    def test_get_session_file_path(self):
        """Test get_session_file_path returns correct path."""
        agent = ClaudeAgent(claude_dir=Path("/tmp/claude"))
        project_path = "/home/user/project"
        session_id = "test-uuid"

        result = agent.get_session_file_path(session_id, project_path)

        expected = Path("/tmp/claude/projects/-home-user-project/test-uuid.jsonl")
        assert result == expected

    def test_session_exists_true(self, tmp_path):
        """Test session_exists returns True when file exists."""
        claude_dir = tmp_path / "claude"
        agent = ClaudeAgent(claude_dir=claude_dir)

        project_path = "/home/user/project"
        session_id = "test-uuid"

        # Create session file
        session_file = agent.get_session_file_path(session_id, project_path)
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.touch()

        assert agent.session_exists(session_id, project_path) is True

    def test_session_exists_false(self, tmp_path):
        """Test session_exists returns False when file doesn't exist."""
        claude_dir = tmp_path / "claude"
        agent = ClaudeAgent(claude_dir=claude_dir)

        project_path = "/home/user/project"
        session_id = "nonexistent-uuid"

        assert agent.session_exists(session_id, project_path) is False

    def test_get_existing_sessions(self, tmp_path):
        """Test get_existing_sessions returns set of session UUIDs."""
        claude_dir = tmp_path / "claude"
        agent = ClaudeAgent(claude_dir=claude_dir)

        project_path = "/home/user/project"

        # Create session directory
        session_dir = claude_dir / "projects" / "-home-user-project"
        session_dir.mkdir(parents=True)

        # Create session files
        (session_dir / "session-1.jsonl").touch()
        (session_dir / "session-2.jsonl").touch()
        (session_dir / "session-3.jsonl").touch()

        sessions = agent.get_existing_sessions(project_path)

        assert sessions == {"session-1", "session-2", "session-3"}

    def test_get_existing_sessions_empty(self, tmp_path):
        """Test get_existing_sessions returns empty set when no sessions."""
        claude_dir = tmp_path / "claude"
        agent = ClaudeAgent(claude_dir=claude_dir)

        project_path = "/home/user/project"

        sessions = agent.get_existing_sessions(project_path)

        assert sessions == set()

    def test_get_session_message_count(self, tmp_path):
        """Test get_session_message_count returns line count."""
        claude_dir = tmp_path / "claude"
        agent = ClaudeAgent(claude_dir=claude_dir)

        project_path = "/home/user/project"
        session_id = "test-uuid"

        # Create session file with 5 lines
        session_file = agent.get_session_file_path(session_id, project_path)
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text("line1\nline2\nline3\nline4\nline5\n")

        count = agent.get_session_message_count(session_id, project_path)

        assert count == 5

    def test_get_session_message_count_nonexistent(self, tmp_path):
        """Test get_session_message_count returns 0 for nonexistent file."""
        claude_dir = tmp_path / "claude"
        agent = ClaudeAgent(claude_dir=claude_dir)

        project_path = "/home/user/project"
        session_id = "nonexistent-uuid"

        count = agent.get_session_message_count(session_id, project_path)

        assert count == 0

    @patch("devflow.agent.claude_agent.time.sleep")
    @patch.object(ClaudeAgent, "launch_session")
    @patch.object(ClaudeAgent, "get_existing_sessions")
    def test_capture_session_id_success(self, mock_get_sessions, mock_launch, mock_sleep):
        """Test capture_session_id successfully detects new session."""
        agent = ClaudeAgent()
        project_path = "/home/user/project"

        # Mock initial sessions (before launch)
        # Then mock new sessions (after launch)
        mock_get_sessions.side_effect = [
            {"old-session"},
            {"old-session"},
            {"old-session", "new-session"},
        ]

        mock_launch.return_value = Mock()

        session_id = agent.capture_session_id(project_path, timeout=10, poll_interval=0.5)

        assert session_id == "new-session"
        mock_launch.assert_called_once_with(project_path)

    @patch("devflow.agent.claude_agent.time.sleep")
    @patch.object(ClaudeAgent, "launch_session")
    @patch.object(ClaudeAgent, "get_existing_sessions")
    def test_capture_session_id_timeout(self, mock_get_sessions, mock_launch, mock_sleep):
        """Test capture_session_id raises TimeoutError when no new session detected."""
        agent = ClaudeAgent()
        project_path = "/home/user/project"

        # Mock no new sessions detected
        mock_get_sessions.return_value = {"old-session"}
        mock_launch.return_value = Mock()

        with pytest.raises(TimeoutError) as exc_info:
            agent.capture_session_id(project_path, timeout=1, poll_interval=0.5)

        assert "Failed to detect new Claude Code session" in str(exc_info.value)


class TestClaudeAgentHeadless:
    """Test ClaudeAgent headless and auto-approve modes."""

    @patch("devflow.agent.claude_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_headless(self, mock_popen, mock_require_tool):
        """Test headless mode adds --print flag."""
        agent = ClaudeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="test-uuid",
            headless=True,
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--print" in cmd
        assert "--session-id" in cmd
        assert "Fix bug" in cmd

    @patch("devflow.agent.claude_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_auto_approve(self, mock_popen, mock_require_tool):
        """Test auto-approve mode adds --dangerously-skip-permissions flag."""
        agent = ClaudeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="test-uuid",
            auto_approve=True,
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--dangerously-skip-permissions" in cmd
        assert "--print" not in cmd  # not headless

    @patch("devflow.agent.claude_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_headless_and_auto_approve(self, mock_popen, mock_require_tool):
        """Test both headless and auto-approve flags together."""
        agent = ClaudeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="test-uuid",
            headless=True,
            auto_approve=True,
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--print" in cmd
        assert "--dangerously-skip-permissions" in cmd

    @patch("devflow.agent.claude_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt_default_no_flags(self, mock_popen, mock_require_tool):
        """Test default launch has neither --print nor --dangerously-skip-permissions."""
        agent = ClaudeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="Fix bug",
            session_id="test-uuid",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "--print" not in cmd
        assert "--dangerously-skip-permissions" not in cmd

    @patch("devflow.agent.claude_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_empty_prompt_omits_prompt_arg(self, mock_popen, mock_require_tool):
        """Test that empty prompt is NOT appended to the command (#421)."""
        agent = ClaudeAgent()
        mock_popen.return_value = Mock()

        agent.launch_with_prompt(
            project_path="/home/user/project",
            initial_prompt="",
            session_id="test-uuid",
        )

        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "claude"
        assert "--session-id" in cmd
        assert "test-uuid" in cmd
        assert "" not in cmd[cmd.index("test-uuid") + 1:]


class TestAgentFactory:
    """Test create_agent_client factory function."""

    def test_create_claude_agent(self):
        """Test factory creates ClaudeAgent for 'claude' backend."""
        agent = create_agent_client("claude")

        assert isinstance(agent, ClaudeAgent)
        assert agent.get_agent_name() == "claude"

    def test_create_claude_agent_case_insensitive(self):
        """Test factory handles case-insensitive backend names."""
        agent = create_agent_client("CLAUDE")

        assert isinstance(agent, ClaudeAgent)

    def test_create_claude_agent_custom_home(self):
        """Test factory passes custom agent_home to ClaudeAgent."""
        custom_home = Path("/tmp/custom-claude")
        agent = create_agent_client("claude", agent_home=custom_home)

        assert isinstance(agent, ClaudeAgent)
        assert agent.claude_dir == custom_home

    def test_create_ollama_agent(self):
        """Test factory creates OllamaClaudeAgent for 'ollama' backend."""
        agent = create_agent_client("ollama")

        assert isinstance(agent, OllamaClaudeAgent)
        assert agent.get_agent_name() == "ollama"

    def test_create_ollama_claude_agent_alias(self):
        """Test factory accepts 'ollama-claude' as alias for 'ollama'."""
        agent = create_agent_client("ollama-claude")

        assert isinstance(agent, OllamaClaudeAgent)
        assert agent.get_agent_name() == "ollama"

    def test_create_ollama_agent_custom_home(self):
        """Test factory passes custom agent_home to OllamaClaudeAgent."""
        custom_home = Path("/tmp/custom-ollama")
        agent = create_agent_client("ollama", agent_home=custom_home)

        assert isinstance(agent, OllamaClaudeAgent)
        assert agent.ollama_dir == custom_home

    def test_create_github_copilot_agent(self):
        """Test factory creates GitHubCopilotAgent for 'github-copilot' backend."""
        agent = create_agent_client("github-copilot")

        assert isinstance(agent, GitHubCopilotAgent)
        assert agent.get_agent_name() == "github-copilot"

    def test_create_copilot_agent_alias(self):
        """Test factory accepts 'copilot' as alias for 'github-copilot'."""
        agent = create_agent_client("copilot")

        assert isinstance(agent, GitHubCopilotAgent)
        assert agent.get_agent_name() == "github-copilot"

    def test_create_cursor_agent(self):
        """Test factory creates CursorAgent for 'cursor' backend."""
        agent = create_agent_client("cursor")

        assert isinstance(agent, CursorAgent)
        assert agent.get_agent_name() == "cursor"

    def test_create_windsurf_agent(self):
        """Test factory creates WindsurfAgent for 'windsurf' backend."""
        agent = create_agent_client("windsurf")

        assert isinstance(agent, WindsurfAgent)
        assert agent.get_agent_name() == "windsurf"

    def test_create_github_copilot_custom_home(self):
        """Test factory passes custom agent_home to GitHubCopilotAgent."""
        custom_home = Path("/tmp/custom-copilot")
        agent = create_agent_client("github-copilot", agent_home=custom_home)

        assert isinstance(agent, GitHubCopilotAgent)
        assert agent.copilot_dir == custom_home

    def test_create_cursor_custom_home(self):
        """Test factory passes custom agent_home to CursorAgent."""
        custom_home = Path("/tmp/custom-cursor")
        agent = create_agent_client("cursor", agent_home=custom_home)

        assert isinstance(agent, CursorAgent)
        assert agent.cursor_dir == custom_home

    def test_create_windsurf_custom_home(self):
        """Test factory passes custom agent_home to WindsurfAgent."""
        custom_home = Path("/tmp/custom-windsurf")
        agent = create_agent_client("windsurf", agent_home=custom_home)

        assert isinstance(agent, WindsurfAgent)
        assert agent.windsurf_dir == custom_home

    def test_create_aider_agent(self):
        """Test factory creates AiderAgent for 'aider' backend."""
        agent = create_agent_client("aider")

        assert isinstance(agent, AiderAgent)
        assert agent.get_agent_name() == "aider"

    def test_create_aider_custom_home(self):
        """Test factory passes custom agent_home to AiderAgent."""
        custom_home = Path("/tmp/custom-aider")
        agent = create_agent_client("aider", agent_home=custom_home)

        assert isinstance(agent, AiderAgent)
        assert agent.aider_dir == custom_home

    def test_create_continue_agent(self):
        """Test factory creates ContinueAgent for 'continue' backend."""
        agent = create_agent_client("continue")

        assert isinstance(agent, ContinueAgent)
        assert agent.get_agent_name() == "continue"

    def test_create_continue_custom_home(self):
        """Test factory passes custom agent_home to ContinueAgent."""
        custom_home = Path("/tmp/custom-continue")
        agent = create_agent_client("continue", agent_home=custom_home)

        assert isinstance(agent, ContinueAgent)
        assert agent.continue_dir == custom_home

    def test_create_crush_agent(self):
        """Test factory creates CrushAgent for 'crush' backend."""
        agent = create_agent_client("crush")

        assert isinstance(agent, CrushAgent)
        assert agent.get_agent_name() == "crush"

    def test_create_opencode_agent(self):
        """Test factory creates OpenCodeAgent for 'opencode' backend."""
        agent = create_agent_client("opencode")

        assert isinstance(agent, OpenCodeAgent)
        assert agent.get_agent_name() == "opencode"

    def test_create_opencode_ai_alias(self):
        """Test factory accepts 'opencode-ai' as alias for 'opencode'."""
        agent = create_agent_client("opencode-ai")

        assert isinstance(agent, OpenCodeAgent)
        assert agent.get_agent_name() == "opencode"

    def test_create_crush_custom_home(self):
        """Test factory passes custom agent_home to CrushAgent."""
        custom_home = Path("/tmp/custom-crush")
        agent = create_agent_client("crush", agent_home=custom_home)

        assert isinstance(agent, CrushAgent)
        assert agent.crush_dir == custom_home

    def test_unsupported_backend_raises_error(self):
        """Test factory raises ValueError for unsupported backend."""
        with pytest.raises(ValueError) as exc_info:
            create_agent_client("unsupported-backend")

        assert "Unsupported agent backend: unsupported-backend" in str(exc_info.value)
        assert "Supported backends:" in str(exc_info.value)
        # Check that the message contains the main backends (don't check exact list to avoid test brittleness)
        assert "claude" in str(exc_info.value)
        assert "ollama" in str(exc_info.value)


class TestGitHubCopilotAgent:
    """Test GitHubCopilotAgent implementation."""

    def test_init_default_copilot_dir(self):
        """Test GitHubCopilotAgent initialization with default copilot_dir."""
        agent = GitHubCopilotAgent()

        assert agent.copilot_dir == Path.home() / ".vscode"

    def test_init_custom_copilot_dir(self):
        """Test GitHubCopilotAgent initialization with custom copilot_dir."""
        custom_dir = Path("/tmp/custom-copilot")
        agent = GitHubCopilotAgent(copilot_dir=custom_dir)

        assert agent.copilot_dir == custom_dir

    def test_get_agent_name(self):
        """Test get_agent_name returns 'github-copilot'."""
        agent = GitHubCopilotAgent()
        assert agent.get_agent_name() == "github-copilot"

    def test_get_agent_home_dir(self):
        """Test get_agent_home_dir returns copilot_dir."""
        custom_dir = Path("/tmp/copilot")
        agent = GitHubCopilotAgent(copilot_dir=custom_dir)
        assert agent.get_agent_home_dir() == custom_dir

    def test_encode_project_path(self):
        """Test encode_project_path replaces / and _ with -."""
        agent = GitHubCopilotAgent()

        assert agent.encode_project_path("/home/user/project") == "-home-user-project"
        assert agent.encode_project_path("/home/my_project") == "-home-my-project"

    @patch("devflow.agent.github_copilot_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_session(self, mock_popen, mock_require_tool):
        """Test launch_session calls code command."""
        agent = GitHubCopilotAgent()
        project_path = "/home/user/project"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_session(project_path)

        mock_require_tool.assert_called_once_with("code", "launch VS Code with GitHub Copilot")
        mock_popen.assert_called_once_with(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.github_copilot_agent.time.time")
    def test_capture_session_id(self, mock_time):
        """Test capture_session_id generates workspace-based ID."""
        mock_time.return_value = 1234567890
        agent = GitHubCopilotAgent()
        project_path = "/home/user/project"

        session_id = agent.capture_session_id(project_path)

        assert session_id.startswith("copilot--home-user-project-")
        assert "1234567890" in session_id

    @patch("devflow.agent.github_copilot_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt(self, mock_popen, mock_require_tool):
        """Test launch_with_prompt calls launch_session (initial prompt ignored)."""
        agent = GitHubCopilotAgent()
        project_path = "/home/user/project"
        initial_prompt = "Test prompt"
        session_id = "test-session-id"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_with_prompt(project_path, initial_prompt, session_id)

        # Should call launch_session (initial_prompt and session_id are ignored)
        mock_require_tool.assert_called_once_with("code", "launch VS Code with GitHub Copilot")
        mock_popen.assert_called_once_with(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.github_copilot_agent.require_tool")
    @patch("subprocess.Popen")
    def test_resume_session(self, mock_popen, mock_require_tool):
        """Test resume_session calls code command."""
        agent = GitHubCopilotAgent()
        project_path = "/home/user/project"
        session_id = "test-session-id"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.resume_session(session_id, project_path)

        mock_require_tool.assert_called_once_with("code", "resume VS Code with GitHub Copilot")
        mock_popen.assert_called_once_with(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    def test_get_session_file_path(self):
        """Test get_session_file_path returns workspace storage path."""
        custom_dir = Path("/tmp/vscode")
        agent = GitHubCopilotAgent(copilot_dir=custom_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        result = agent.get_session_file_path(session_id, project_path)

        expected = custom_dir / "User" / "workspaceStorage" / "-home-user-project" / "state.vscdb"
        assert result == expected

    def test_session_exists_when_directory_exists(self, tmp_path):
        """Test session_exists returns True when workspace storage directory exists."""
        copilot_dir = tmp_path / "vscode"
        agent = GitHubCopilotAgent(copilot_dir=copilot_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Create workspace storage directory
        workspace_dir = copilot_dir / "User" / "workspaceStorage" / "-home-user-project"
        workspace_dir.mkdir(parents=True)

        assert agent.session_exists(session_id, project_path) is True

    def test_session_exists_returns_false_when_not_exists(self, tmp_path):
        """Test session_exists returns False when workspace storage doesn't exist."""
        copilot_dir = tmp_path / "vscode"
        agent = GitHubCopilotAgent(copilot_dir=copilot_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        assert agent.session_exists(session_id, project_path) is False

    def test_get_existing_sessions_returns_empty_set(self):
        """Test get_existing_sessions returns empty set (VS Code manages sessions)."""
        agent = GitHubCopilotAgent()
        project_path = "/home/user/project"

        sessions = agent.get_existing_sessions(project_path)

        assert sessions == set()

    def test_get_session_message_count_returns_zero(self):
        """Test get_session_message_count returns 0 (not supported)."""
        agent = GitHubCopilotAgent()
        project_path = "/home/user/project"
        session_id = "test-session-id"

        count = agent.get_session_message_count(session_id, project_path)

        assert count == 0


class TestCursorAgent:
    """Test CursorAgent implementation."""

    def test_init_default_cursor_dir(self):
        """Test CursorAgent initialization with default cursor_dir."""
        agent = CursorAgent()

        assert agent.cursor_dir == Path.home() / ".cursor"

    def test_init_custom_cursor_dir(self):
        """Test CursorAgent initialization with custom cursor_dir."""
        custom_dir = Path("/tmp/custom-cursor")
        agent = CursorAgent(cursor_dir=custom_dir)

        assert agent.cursor_dir == custom_dir

    def test_get_agent_name(self):
        """Test get_agent_name returns 'cursor'."""
        agent = CursorAgent()
        assert agent.get_agent_name() == "cursor"

    def test_get_agent_home_dir(self):
        """Test get_agent_home_dir returns cursor_dir."""
        custom_dir = Path("/tmp/cursor")
        agent = CursorAgent(cursor_dir=custom_dir)
        assert agent.get_agent_home_dir() == custom_dir

    @patch("devflow.agent.cursor_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_session(self, mock_popen, mock_require_tool):
        """Test launch_session calls cursor command."""
        agent = CursorAgent()
        project_path = "/home/user/project"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_session(project_path)

        mock_require_tool.assert_called_once_with("cursor", "launch Cursor editor")
        mock_popen.assert_called_once_with(
            ["cursor", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.cursor_agent.time.time")
    def test_capture_session_id(self, mock_time):
        """Test capture_session_id generates workspace-based ID."""
        mock_time.return_value = 1234567890
        agent = CursorAgent()
        project_path = "/home/user/project"

        session_id = agent.capture_session_id(project_path)

        assert session_id.startswith("cursor--home-user-project-")
        assert "1234567890" in session_id

    @patch("devflow.agent.cursor_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt(self, mock_popen, mock_require_tool):
        """Test launch_with_prompt calls launch_session (initial prompt ignored)."""
        agent = CursorAgent()
        project_path = "/home/user/project"
        initial_prompt = "Test prompt"
        session_id = "test-session-id"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_with_prompt(project_path, initial_prompt, session_id)

        # Should call launch_session (initial_prompt and session_id are ignored)
        mock_require_tool.assert_called_once_with("cursor", "launch Cursor editor")
        mock_popen.assert_called_once_with(
            ["cursor", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.cursor_agent.require_tool")
    @patch("subprocess.Popen")
    def test_resume_session(self, mock_popen, mock_require_tool):
        """Test resume_session calls cursor command."""
        agent = CursorAgent()
        project_path = "/home/user/project"
        session_id = "test-session-id"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.resume_session(session_id, project_path)

        mock_require_tool.assert_called_once_with("cursor", "resume Cursor editor")
        mock_popen.assert_called_once_with(
            ["cursor", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    def test_get_session_file_path_fallback(self):
        """Test get_session_file_path returns fallback path when workspace storage doesn't exist."""
        custom_dir = Path("/tmp/cursor")
        agent = CursorAgent(cursor_dir=custom_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        result = agent.get_session_file_path(session_id, project_path)

        expected = custom_dir / "User" / "workspaceStorage" / "-home-user-project" / "state.vscdb"
        assert result == expected

    def test_get_session_file_path_with_existing_workspace(self, tmp_path):
        """Test get_session_file_path finds existing workspace state file."""
        cursor_dir = tmp_path / "cursor"
        agent = CursorAgent(cursor_dir=cursor_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Create workspace storage with state file
        workspace_dir = cursor_dir / "User" / "workspaceStorage" / "workspace-id-123"
        workspace_dir.mkdir(parents=True)
        workspace_json = workspace_dir / "workspace.json"
        workspace_json.write_text('{"folder": "/home/user/project"}')
        state_file = workspace_dir / "state.vscdb"
        state_file.touch()

        result = agent.get_session_file_path(session_id, project_path)

        # Should find the existing state file
        assert result.exists()
        assert result.name == "state.vscdb"

    def test_session_exists_when_directory_exists(self, tmp_path):
        """Test session_exists returns True when workspace storage exists."""
        cursor_dir = tmp_path / "cursor"
        agent = CursorAgent(cursor_dir=cursor_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Create workspace storage directory
        workspace_dir = cursor_dir / "User" / "workspaceStorage" / "-home-user-project"
        workspace_dir.mkdir(parents=True)

        assert agent.session_exists(session_id, project_path) is True

    def test_session_exists_returns_false_when_not_exists(self, tmp_path):
        """Test session_exists returns False when workspace storage doesn't exist."""
        cursor_dir = tmp_path / "cursor"
        agent = CursorAgent(cursor_dir=cursor_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        assert agent.session_exists(session_id, project_path) is False

    def test_get_existing_sessions_returns_empty_set(self):
        """Test get_existing_sessions returns empty set (Cursor manages sessions internally)."""
        agent = CursorAgent()
        project_path = "/home/user/project"

        sessions = agent.get_existing_sessions(project_path)

        assert sessions == set()

    def test_get_session_message_count_returns_zero(self):
        """Test get_session_message_count returns 0 (not supported)."""
        agent = CursorAgent()
        project_path = "/home/user/project"
        session_id = "test-session-id"

        count = agent.get_session_message_count(session_id, project_path)

        assert count == 0


class TestWindsurfAgent:
    """Test WindsurfAgent implementation."""

    def test_init_default_windsurf_dir(self):
        """Test WindsurfAgent initialization with default windsurf_dir."""
        agent = WindsurfAgent()

        assert agent.windsurf_dir == Path.home() / ".windsurf"

    def test_init_custom_windsurf_dir(self):
        """Test WindsurfAgent initialization with custom windsurf_dir."""
        custom_dir = Path("/tmp/custom-windsurf")
        agent = WindsurfAgent(windsurf_dir=custom_dir)

        assert agent.windsurf_dir == custom_dir

    def test_get_agent_name(self):
        """Test get_agent_name returns 'windsurf'."""
        agent = WindsurfAgent()
        assert agent.get_agent_name() == "windsurf"

    def test_get_agent_home_dir(self):
        """Test get_agent_home_dir returns windsurf_dir."""
        custom_dir = Path("/tmp/windsurf")
        agent = WindsurfAgent(windsurf_dir=custom_dir)
        assert agent.get_agent_home_dir() == custom_dir

    @patch("devflow.agent.windsurf_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_session(self, mock_popen, mock_require_tool):
        """Test launch_session calls windsurf command."""
        agent = WindsurfAgent()
        project_path = "/home/user/project"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_session(project_path)

        mock_require_tool.assert_called_once_with("windsurf", "launch Windsurf editor")
        mock_popen.assert_called_once_with(
            ["windsurf", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.windsurf_agent.time.time")
    def test_capture_session_id(self, mock_time):
        """Test capture_session_id generates workspace-based ID."""
        mock_time.return_value = 1234567890
        agent = WindsurfAgent()
        project_path = "/home/user/project"

        session_id = agent.capture_session_id(project_path)

        assert session_id.startswith("windsurf--home-user-project-")
        assert "1234567890" in session_id

    @patch("devflow.agent.windsurf_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt(self, mock_popen, mock_require_tool):
        """Test launch_with_prompt calls launch_session (initial prompt ignored)."""
        agent = WindsurfAgent()
        project_path = "/home/user/project"
        initial_prompt = "Test prompt"
        session_id = "test-session-id"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_with_prompt(project_path, initial_prompt, session_id)

        # Should call launch_session (initial_prompt and session_id are ignored)
        mock_require_tool.assert_called_once_with("windsurf", "launch Windsurf editor")
        mock_popen.assert_called_once_with(
            ["windsurf", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.windsurf_agent.require_tool")
    @patch("subprocess.Popen")
    def test_resume_session(self, mock_popen, mock_require_tool):
        """Test resume_session calls windsurf command."""
        agent = WindsurfAgent()
        project_path = "/home/user/project"
        session_id = "test-session-id"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.resume_session(session_id, project_path)

        mock_require_tool.assert_called_once_with("windsurf", "resume Windsurf editor")
        mock_popen.assert_called_once_with(
            ["windsurf", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    def test_get_session_file_path_fallback(self):
        """Test get_session_file_path returns fallback path when workspace storage doesn't exist."""
        custom_dir = Path("/tmp/windsurf")
        agent = WindsurfAgent(windsurf_dir=custom_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        result = agent.get_session_file_path(session_id, project_path)

        expected = custom_dir / "User" / "workspaceStorage" / "-home-user-project" / "state.vscdb"
        assert result == expected

    def test_get_session_file_path_with_existing_workspace(self, tmp_path):
        """Test get_session_file_path finds existing workspace state file."""
        windsurf_dir = tmp_path / "windsurf"
        agent = WindsurfAgent(windsurf_dir=windsurf_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Create workspace storage with state file
        workspace_dir = windsurf_dir / "User" / "workspaceStorage" / "workspace-id-456"
        workspace_dir.mkdir(parents=True)
        workspace_json = workspace_dir / "workspace.json"
        workspace_json.write_text('{"folder": "/home/user/project"}')
        state_file = workspace_dir / "state.vscdb"
        state_file.touch()

        result = agent.get_session_file_path(session_id, project_path)

        # Should find the existing state file
        assert result.exists()
        assert result.name == "state.vscdb"

    def test_session_exists_when_directory_exists(self, tmp_path):
        """Test session_exists returns True when workspace storage exists."""
        windsurf_dir = tmp_path / "windsurf"
        agent = WindsurfAgent(windsurf_dir=windsurf_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Create workspace storage directory
        workspace_dir = windsurf_dir / "User" / "workspaceStorage" / "-home-user-project"
        workspace_dir.mkdir(parents=True)

        assert agent.session_exists(session_id, project_path) is True

    def test_session_exists_returns_false_when_not_exists(self, tmp_path):
        """Test session_exists returns False when workspace storage doesn't exist."""
        windsurf_dir = tmp_path / "windsurf"
        agent = WindsurfAgent(windsurf_dir=windsurf_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        assert agent.session_exists(session_id, project_path) is False

    def test_get_existing_sessions_returns_empty_set(self):
        """Test get_existing_sessions returns empty set (Windsurf manages sessions internally)."""
        agent = WindsurfAgent()
        project_path = "/home/user/project"

        sessions = agent.get_existing_sessions(project_path)

        assert sessions == set()

    def test_get_session_message_count_returns_zero(self):
        """Test get_session_message_count returns 0 (not supported)."""
        agent = WindsurfAgent()
        project_path = "/home/user/project"
        session_id = "test-session-id"

        count = agent.get_session_message_count(session_id, project_path)

        assert count == 0


class TestAiderAgent:
    """Test AiderAgent implementation."""

    def test_init_default_aider_dir(self):
        """Test AiderAgent initialization with default aider_dir."""
        agent = AiderAgent()

        assert agent.aider_dir == Path.home() / ".aider"
        assert agent.chat_history_dir == Path.home() / ".aider" / "chat_history"

    def test_init_custom_aider_dir(self):
        """Test AiderAgent initialization with custom aider_dir."""
        custom_dir = Path("/tmp/custom-aider")
        agent = AiderAgent(aider_dir=custom_dir)

        assert agent.aider_dir == custom_dir
        assert agent.chat_history_dir == custom_dir / "chat_history"

    def test_get_agent_name(self):
        """Test get_agent_name returns 'aider'."""
        agent = AiderAgent()
        assert agent.get_agent_name() == "aider"

    def test_get_agent_home_dir(self):
        """Test get_agent_home_dir returns aider_dir."""
        custom_dir = Path("/tmp/aider")
        agent = AiderAgent(aider_dir=custom_dir)
        assert agent.get_agent_home_dir() == custom_dir

    def test_encode_project_path(self):
        """Test encode_project_path replaces / and _ with -."""
        agent = AiderAgent()

        # Test / replacement
        assert agent.encode_project_path("/home/user/project") == "-home-user-project"

        # Test _ replacement
        assert agent.encode_project_path("/home/my_project") == "-home-my-project"

        # Test both
        assert agent.encode_project_path("/home/user/my_project") == "-home-user-my-project"

    @patch("devflow.agent.aider_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_session(self, mock_popen, mock_require_tool):
        """Test launch_session calls aider command."""
        agent = AiderAgent()
        project_path = "/home/user/project"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_session(project_path)

        mock_require_tool.assert_called_once_with("aider", "launch Aider AI assistant")
        mock_popen.assert_called_once_with(
            ["aider"],
            cwd=project_path,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.aider_agent.time.time")
    def test_capture_session_id(self, mock_time):
        """Test capture_session_id generates timestamp-based ID."""
        mock_time.return_value = 1234567890
        agent = AiderAgent()
        project_path = "/home/user/project"

        session_id = agent.capture_session_id(project_path)

        assert session_id.startswith("aider--home-user-project-")
        assert "1234567890" in session_id

    @patch("devflow.agent.aider_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt(self, mock_popen, mock_require_tool, tmp_path):
        """Test launch_with_prompt saves prompt and launches aider."""
        agent = AiderAgent(aider_dir=tmp_path / "aider")
        project_path = "/home/user/project"
        initial_prompt = "Test prompt for Aider"
        session_id = "test-session-123"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_with_prompt(project_path, initial_prompt, session_id)

        # Check prompt file was created
        prompt_file = agent.chat_history_dir / f"{session_id}_initial_prompt.txt"
        assert prompt_file.exists()
        assert prompt_file.read_text() == initial_prompt

        # Check aider was launched with chat history file
        mock_require_tool.assert_called_once_with("aider", "launch Aider AI assistant")
        expected_chat_file = agent.chat_history_dir / f"{session_id}_chat.txt"
        mock_popen.assert_called_once_with(
            ["aider", "--chat-history-file", str(expected_chat_file)],
            cwd=project_path,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.aider_agent.require_tool")
    @patch("subprocess.Popen")
    def test_resume_session(self, mock_popen, mock_require_tool, tmp_path):
        """Test resume_session loads chat history file."""
        agent = AiderAgent(aider_dir=tmp_path / "aider")
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Create chat history file
        chat_file = agent.chat_history_dir / f"{session_id}_chat.txt"
        chat_file.parent.mkdir(parents=True, exist_ok=True)
        chat_file.write_text("Previous chat content")

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.resume_session(session_id, project_path)

        mock_require_tool.assert_called_once_with("aider", "resume Aider AI assistant")
        mock_popen.assert_called_once_with(
            ["aider", "--chat-history-file", str(chat_file)],
            cwd=project_path,
            env=None,
        )
        assert result == mock_process

    def test_get_session_file_path(self):
        """Test get_session_file_path returns correct path."""
        agent = AiderAgent(aider_dir=Path("/tmp/aider"))
        project_path = "/home/user/project"
        session_id = "test-session-id"

        result = agent.get_session_file_path(session_id, project_path)

        expected = Path("/tmp/aider/chat_history/test-session-id_chat.txt")
        assert result == expected

    def test_session_exists_true(self, tmp_path):
        """Test session_exists returns True when chat file exists."""
        agent = AiderAgent(aider_dir=tmp_path / "aider")
        project_path = "/home/user/project"
        session_id = "test-uuid"

        # Create chat history file
        chat_file = agent.get_session_file_path(session_id, project_path)
        chat_file.parent.mkdir(parents=True, exist_ok=True)
        chat_file.touch()

        assert agent.session_exists(session_id, project_path) is True

    def test_session_exists_false(self, tmp_path):
        """Test session_exists returns False when chat file doesn't exist."""
        agent = AiderAgent(aider_dir=tmp_path / "aider")
        project_path = "/home/user/project"
        session_id = "nonexistent-uuid"

        assert agent.session_exists(session_id, project_path) is False

    def test_get_existing_sessions(self, tmp_path):
        """Test get_existing_sessions returns set of session IDs."""
        agent = AiderAgent(aider_dir=tmp_path / "aider")
        project_path = "/home/user/project"
        encoded_path = agent.encode_project_path(project_path)

        # Create chat history directory
        agent.chat_history_dir.mkdir(parents=True, exist_ok=True)

        # Create chat files
        (agent.chat_history_dir / f"aider-{encoded_path}-1234567890_chat.txt").touch()
        (agent.chat_history_dir / f"aider-{encoded_path}-1234567891_chat.txt").touch()
        (agent.chat_history_dir / f"aider-other-project-1234567892_chat.txt").touch()

        sessions = agent.get_existing_sessions(project_path)

        assert sessions == {
            f"aider-{encoded_path}-1234567890",
            f"aider-{encoded_path}-1234567891"
        }

    def test_get_existing_sessions_empty(self, tmp_path):
        """Test get_existing_sessions returns empty set when no sessions."""
        agent = AiderAgent(aider_dir=tmp_path / "aider")
        project_path = "/home/user/project"

        sessions = agent.get_existing_sessions(project_path)

        assert sessions == set()

    def test_get_session_message_count(self, tmp_path):
        """Test get_session_message_count counts non-empty lines."""
        agent = AiderAgent(aider_dir=tmp_path / "aider")
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Create chat file with some content
        chat_file = agent.get_session_file_path(session_id, project_path)
        chat_file.parent.mkdir(parents=True, exist_ok=True)
        chat_file.write_text("Message 1\nMessage 2\n\nMessage 3\n")

        count = agent.get_session_message_count(session_id, project_path)

        assert count == 3  # 3 non-empty lines

    def test_get_session_message_count_zero_when_file_not_exists(self, tmp_path):
        """Test get_session_message_count returns 0 when file doesn't exist."""
        agent = AiderAgent(aider_dir=tmp_path / "aider")
        project_path = "/home/user/project"
        session_id = "nonexistent-session"

        count = agent.get_session_message_count(session_id, project_path)

        assert count == 0


class TestContinueAgent:
    """Test ContinueAgent implementation."""

    def test_init_default_continue_dir(self):
        """Test ContinueAgent initialization with default continue_dir."""
        agent = ContinueAgent()

        assert agent.continue_dir == Path.home() / ".continue"
        assert agent.vscode_dir == Path.home() / ".vscode"
        assert agent.workspace_storage == Path.home() / ".vscode" / "User" / "workspaceStorage"

    def test_init_custom_continue_dir(self):
        """Test ContinueAgent initialization with custom continue_dir."""
        custom_dir = Path("/tmp/custom-continue")
        agent = ContinueAgent(continue_dir=custom_dir)

        assert agent.continue_dir == custom_dir
        # VS Code dir is always ~/.vscode
        assert agent.vscode_dir == Path.home() / ".vscode"

    def test_get_agent_name(self):
        """Test get_agent_name returns 'continue'."""
        agent = ContinueAgent()
        assert agent.get_agent_name() == "continue"

    def test_get_agent_home_dir(self):
        """Test get_agent_home_dir returns continue_dir."""
        custom_dir = Path("/tmp/continue")
        agent = ContinueAgent(continue_dir=custom_dir)
        assert agent.get_agent_home_dir() == custom_dir

    def test_encode_project_path(self):
        """Test encode_project_path replaces / and _ with -."""
        agent = ContinueAgent()

        # Test / replacement
        assert agent.encode_project_path("/home/user/project") == "-home-user-project"

        # Test _ replacement
        assert agent.encode_project_path("/home/my_project") == "-home-my-project"

        # Test both
        assert agent.encode_project_path("/home/user/my_project") == "-home-user-my-project"

    @patch("devflow.agent.continue_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_session(self, mock_popen, mock_require_tool):
        """Test launch_session calls code command."""
        agent = ContinueAgent()
        project_path = "/home/user/project"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_session(project_path)

        mock_require_tool.assert_called_once_with("code", "launch VS Code with Continue extension")
        mock_popen.assert_called_once_with(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.continue_agent.time.time")
    def test_capture_session_id(self, mock_time):
        """Test capture_session_id generates workspace-based ID."""
        mock_time.return_value = 1234567890
        agent = ContinueAgent()
        project_path = "/home/user/project"

        session_id = agent.capture_session_id(project_path)

        assert session_id.startswith("continue--home-user-project-")
        assert "1234567890" in session_id

    @patch("devflow.agent.continue_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt(self, mock_popen, mock_require_tool, tmp_path):
        """Test launch_with_prompt saves prompt and launches VS Code."""
        agent = ContinueAgent(continue_dir=tmp_path / "continue")
        project_path = "/home/user/project"
        initial_prompt = "Test prompt for Continue"
        session_id = "test-session-456"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_with_prompt(project_path, initial_prompt, session_id)

        # Check prompt file was created
        prompt_file = agent.continue_dir / f"{session_id}_initial_prompt.txt"
        assert prompt_file.exists()
        assert prompt_file.read_text() == initial_prompt

        # Check VS Code was launched
        mock_require_tool.assert_called_once_with("code", "launch VS Code with Continue extension")
        mock_popen.assert_called_once_with(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    @patch("devflow.agent.continue_agent.require_tool")
    @patch("subprocess.Popen")
    def test_resume_session(self, mock_popen, mock_require_tool):
        """Test resume_session calls code command."""
        agent = ContinueAgent()
        project_path = "/home/user/project"
        session_id = "test-session-id"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.resume_session(session_id, project_path)

        mock_require_tool.assert_called_once_with("code", "resume VS Code with Continue extension")
        mock_popen.assert_called_once_with(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
        )
        assert result == mock_process

    def test_get_session_file_path(self):
        """Test get_session_file_path returns workspace storage path."""
        custom_dir = Path("/tmp/continue")
        agent = ContinueAgent(continue_dir=custom_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        result = agent.get_session_file_path(session_id, project_path)

        # Note: VS Code dir is always ~/.vscode, not custom_dir
        expected = Path.home() / ".vscode" / "User" / "workspaceStorage" / "-home-user-project"
        assert result == expected

    def test_session_exists_when_storage_exists(self, tmp_path):
        """Test session_exists returns True when workspace storage exists."""
        agent = ContinueAgent(continue_dir=tmp_path / "continue")
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Create workspace storage directory
        workspace_dir = agent.workspace_storage / "-home-user-project"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        assert agent.session_exists(session_id, project_path) is True

    def test_session_exists_returns_false_when_not_exists(self, tmp_path):
        """Test session_exists returns False when workspace storage doesn't exist."""
        # Use a different vscode_dir to avoid conflicts with real VS Code
        agent = ContinueAgent(continue_dir=tmp_path / "continue")
        # Override workspace_storage to use tmp_path
        agent.workspace_storage = tmp_path / "vscode" / "User" / "workspaceStorage"

        project_path = "/home/user/project"
        session_id = "test-session-id"

        assert agent.session_exists(session_id, project_path) is False

    def test_get_existing_sessions_returns_empty_set(self):
        """Test get_existing_sessions returns empty set (Continue manages sessions via VS Code)."""
        agent = ContinueAgent()
        project_path = "/home/user/project"

        sessions = agent.get_existing_sessions(project_path)

        assert sessions == set()

    def test_get_session_message_count_returns_zero(self):
        """Test get_session_message_count returns 0 (not supported)."""
        agent = ContinueAgent()
        project_path = "/home/user/project"
        session_id = "test-session-id"

        count = agent.get_session_message_count(session_id, project_path)

        assert count == 0


class TestCrushAgent:
    """Test CrushAgent implementation."""

    def test_init_default_crush_dir(self):
        """Test CrushAgent initialization with default directory (~/.local/share/crush)."""
        agent = CrushAgent()

        assert agent.crush_dir == Path.home() / ".local" / "share" / "crush"
        assert agent.db_path == Path.home() / ".local" / "share" / "crush" / "crush.db"

    def test_init_custom_crush_dir(self):
        """Test CrushAgent initialization with custom directory."""
        custom_dir = Path("/tmp/custom-crush")
        agent = CrushAgent(crush_dir=custom_dir)

        assert agent.crush_dir == custom_dir
        assert agent.db_path == custom_dir / "crush.db"

    def test_get_agent_name(self):
        """Test get_agent_name returns 'crush'."""
        agent = CrushAgent()
        assert agent.get_agent_name() == "crush"

    def test_get_agent_home_dir(self):
        """Test get_agent_home_dir returns crush_dir."""
        custom_dir = Path("/tmp/crush")
        agent = CrushAgent(crush_dir=custom_dir)
        assert agent.get_agent_home_dir() == custom_dir

    def test_encode_project_path(self):
        """Test encode_project_path returns original path (no encoding for Crush)."""
        agent = CrushAgent()

        # Crush doesn't encode paths since it uses a global SQLite database
        assert agent.encode_project_path("/home/user/project") == "/home/user/project"
        assert agent.encode_project_path("/home/my_project") == "/home/my_project"

    @patch("devflow.agent.crush_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_session(self, mock_popen, mock_require_tool):
        """Test launch_session calls crush command with env=None."""
        agent = CrushAgent()
        project_path = "/home/user/project"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_session(project_path)

        mock_require_tool.assert_called_once_with("crush", "launch Crush AI assistant")
        mock_popen.assert_called_once_with(
            ["crush"],
            cwd=project_path,
            env=ANY,
        )
        assert result == mock_process

    @patch("devflow.agent.crush_agent.require_tool")
    @patch("subprocess.Popen")
    def test_launch_with_prompt(self, mock_popen, mock_require_tool):
        """Test launch_with_prompt calls 'crush --session {session_id}'."""
        agent = CrushAgent()
        project_path = "/home/user/project"
        initial_prompt = "Test prompt for Crush"
        session_id = "test-session-789"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.launch_with_prompt(project_path, initial_prompt, session_id)

        # Crush doesn't support initial prompts via CLI, but uses --session flag
        mock_require_tool.assert_called_once_with("crush", "launch Crush AI assistant")
        mock_popen.assert_called_once_with(
            ["crush", "--session", session_id],
            cwd=project_path,
            env=ANY,
        )
        assert result == mock_process

    @patch("devflow.agent.crush_agent.require_tool")
    @patch("subprocess.Popen")
    def test_resume_session(self, mock_popen, mock_require_tool):
        """Test resume_session calls 'crush --session {session_id}'."""
        agent = CrushAgent()
        project_path = "/home/user/project"
        session_id = "test-session-id"

        mock_process = Mock()
        mock_popen.return_value = mock_process

        result = agent.resume_session(session_id, project_path)

        mock_require_tool.assert_called_once_with("crush", "resume Crush AI assistant")
        mock_popen.assert_called_once_with(
            ["crush", "--session", session_id],
            cwd=project_path,
            env=ANY,
        )
        assert result == mock_process

    def test_get_session_file_path(self):
        """Test returns the db_path (~/.local/share/crush/crush.db)."""
        agent = CrushAgent(crush_dir=Path("/tmp/crush"))
        project_path = "/home/user/project"
        session_id = "test-session-id"

        result = agent.get_session_file_path(session_id, project_path)

        # All sessions are stored in the same database
        expected = Path("/tmp/crush/crush.db")
        assert result == expected

    @patch("devflow.agent.crush_agent.sqlite3.connect")
    def test_session_exists_when_db_exists_and_has_session(self, mock_connect, tmp_path):
        """Test with mocked SQLite connection."""
        crush_dir = tmp_path / "crush"
        agent = CrushAgent(crush_dir=crush_dir)
        project_path = "/home/user/project"
        session_id = "test-session-uuid"

        # Create the database file
        db_path = crush_dir / "crush.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.touch()

        # Mock SQLite connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("test-session-uuid",)  # Session exists
        mock_connect.return_value = mock_conn

        assert agent.session_exists(session_id, project_path) is True

        # Verify SQL query
        mock_cursor.execute.assert_called_once_with(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        )
        mock_conn.close.assert_called_once()

    def test_session_exists_returns_false_when_db_not_exists(self, tmp_path):
        """Test when database doesn't exist."""
        crush_dir = tmp_path / "crush"
        agent = CrushAgent(crush_dir=crush_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Database doesn't exist
        assert agent.session_exists(session_id, project_path) is False

    @patch("devflow.agent.crush_agent.sqlite3.connect")
    def test_get_existing_sessions_returns_session_ids(self, mock_connect, tmp_path):
        """Test with mocked SQLite query."""
        crush_dir = tmp_path / "crush"
        agent = CrushAgent(crush_dir=crush_dir)
        project_path = "/home/user/project"

        # Create the database file
        db_path = crush_dir / "crush.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.touch()

        # Mock SQLite connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("session-1",),
            ("session-2",),
            ("session-3",),
        ]
        mock_connect.return_value = mock_conn

        sessions = agent.get_existing_sessions(project_path)

        assert sessions == {"session-1", "session-2", "session-3"}

        # Verify SQL query
        mock_cursor.execute.assert_called_once_with("SELECT id FROM sessions")
        mock_conn.close.assert_called_once()

    def test_get_existing_sessions_returns_empty_when_db_not_exists(self, tmp_path):
        """Test empty set."""
        crush_dir = tmp_path / "crush"
        agent = CrushAgent(crush_dir=crush_dir)
        project_path = "/home/user/project"

        # Database doesn't exist
        sessions = agent.get_existing_sessions(project_path)

        assert sessions == set()

    @patch("devflow.agent.crush_agent.sqlite3.connect")
    def test_get_session_message_count(self, mock_connect, tmp_path):
        """Test with mocked SQLite query."""
        crush_dir = tmp_path / "crush"
        agent = CrushAgent(crush_dir=crush_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Create the database file
        db_path = crush_dir / "crush.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.touch()

        # Mock SQLite connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (42,)  # 42 messages
        mock_connect.return_value = mock_conn

        count = agent.get_session_message_count(session_id, project_path)

        assert count == 42

        # Verify SQL query
        mock_cursor.execute.assert_called_once_with(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            (session_id,)
        )
        mock_conn.close.assert_called_once()

    def test_get_session_message_count_zero_when_db_not_exists(self, tmp_path):
        """Test returns 0."""
        crush_dir = tmp_path / "crush"
        agent = CrushAgent(crush_dir=crush_dir)
        project_path = "/home/user/project"
        session_id = "test-session-id"

        # Database doesn't exist
        count = agent.get_session_message_count(session_id, project_path)

        assert count == 0


class TestSupportsPermissionPrompts:
    """Test supports_permission_prompts() across all agent implementations."""

    def test_claude_supports_permissions(self):
        """Claude Code has a built-in permission system."""
        agent = ClaudeAgent()
        assert agent.supports_permission_prompts() is True

    def test_ollama_supports_permissions(self):
        """Ollama uses Claude Code, so it inherits permission support."""
        agent = OllamaClaudeAgent()
        assert agent.supports_permission_prompts() is True

    def test_copilot_supports_permissions(self):
        """GitHub Copilot uses default (True) — IDE manages permissions."""
        agent = GitHubCopilotAgent()
        assert agent.supports_permission_prompts() is True

    def test_cursor_supports_permissions(self):
        """Cursor uses default (True) — IDE manages permissions."""
        agent = CursorAgent()
        assert agent.supports_permission_prompts() is True

    def test_windsurf_supports_permissions(self):
        """Windsurf uses default (True) — IDE manages permissions."""
        agent = WindsurfAgent()
        assert agent.supports_permission_prompts() is True

    def test_aider_supports_permissions(self):
        """Aider uses default (True)."""
        agent = AiderAgent()
        assert agent.supports_permission_prompts() is True

    def test_continue_supports_permissions(self):
        """Continue uses default (True)."""
        agent = ContinueAgent()
        assert agent.supports_permission_prompts() is True

    def test_crush_supports_permissions(self):
        """Crush uses default (True)."""
        agent = CrushAgent()
        assert agent.supports_permission_prompts() is True

    def test_opencode_supports_permissions(self):
        """OpenCode supports permissions when launched without --prompt (#430)."""
        agent = OpenCodeAgent()
        assert agent.supports_permission_prompts() is True


class TestUsesTui:
    """Test uses_tui() across all agent implementations (#461)."""

    def test_opencode_uses_tui(self):
        """OpenCode uses a full-screen TUI (Bubble Tea)."""
        agent = OpenCodeAgent()
        assert agent.uses_tui() is True

    def test_crush_uses_tui(self):
        """Crush uses a full-screen TUI (Bubble Tea)."""
        agent = CrushAgent()
        assert agent.uses_tui() is True

    def test_claude_does_not_use_tui(self):
        """Claude Code uses a standard terminal REPL, not a TUI."""
        agent = ClaudeAgent()
        assert agent.uses_tui() is False

    def test_ollama_does_not_use_tui(self):
        """OllamaClaude uses a standard terminal REPL."""
        agent = OllamaClaudeAgent()
        assert agent.uses_tui() is False

    def test_aider_does_not_use_tui(self):
        """Aider uses a standard terminal REPL."""
        agent = AiderAgent()
        assert agent.uses_tui() is False

    def test_copilot_does_not_use_tui(self):
        """GitHub Copilot is a GUI/IDE, not a TUI."""
        agent = GitHubCopilotAgent()
        assert agent.uses_tui() is False

    def test_cursor_does_not_use_tui(self):
        """Cursor is a GUI/IDE, not a TUI."""
        agent = CursorAgent()
        assert agent.uses_tui() is False

    def test_windsurf_does_not_use_tui(self):
        """Windsurf is a GUI/IDE, not a TUI."""
        agent = WindsurfAgent()
        assert agent.uses_tui() is False

    def test_continue_does_not_use_tui(self):
        """Continue is a GUI/IDE extension, not a TUI."""
        agent = ContinueAgent()
        assert agent.uses_tui() is False


class TestWaitForExit:
    """Test wait_for_exit() and cleanup_after_exit() (#461)."""

    def test_wait_for_exit_calls_process_wait_then_cleanup(self):
        """wait_for_exit() calls process.wait() then cleanup."""
        agent = ClaudeAgent()
        mock_process = Mock()
        with patch.object(agent, "cleanup_after_exit") as mock_cleanup:
            agent.wait_for_exit(mock_process, headless=False)
        mock_process.wait.assert_called_once()
        mock_cleanup.assert_called_once_with(False)

    def test_wait_for_exit_headless_skips_cleanup(self):
        """In headless mode, cleanup_after_exit is still called but returns early."""
        agent = ClaudeAgent()
        mock_process = Mock()
        with patch.object(agent, "cleanup_after_exit") as mock_cleanup:
            agent.wait_for_exit(mock_process, headless=True)
        mock_process.wait.assert_called_once()
        mock_cleanup.assert_called_once_with(True)

    @patch("devflow.cli.utils.clear_screen_after_tui")
    @patch("devflow.cli.utils.reset_terminal_after_tui")
    def test_cleanup_tui_agent_clears_screen(self, mock_reset, mock_clear):
        """TUI agents reset terminal AND clear screen."""
        agent = OpenCodeAgent()
        agent.cleanup_after_exit(headless=False)
        mock_reset.assert_called_once()
        mock_clear.assert_called_once()

    @patch("devflow.cli.utils.clear_screen_after_tui")
    @patch("devflow.cli.utils.reset_terminal_after_tui")
    def test_cleanup_non_tui_agent_resets_but_no_clear(self, mock_reset, mock_clear):
        """Non-TUI agents reset terminal but do NOT clear screen."""
        agent = ClaudeAgent()
        agent.cleanup_after_exit(headless=False)
        mock_reset.assert_called_once()
        mock_clear.assert_not_called()

    @patch("devflow.cli.utils.clear_screen_after_tui")
    @patch("devflow.cli.utils.reset_terminal_after_tui")
    def test_cleanup_headless_does_nothing(self, mock_reset, mock_clear):
        """Headless mode skips all terminal cleanup."""
        agent = OpenCodeAgent()
        agent.cleanup_after_exit(headless=True)
        mock_reset.assert_not_called()
        mock_clear.assert_not_called()


class TestGetAgentDisplayName:
    """Tests for get_agent_display_name helper function (#448)."""

    def test_claude_display_name(self):
        """Claude backend returns 'Claude Code' display name."""
        assert get_agent_display_name("claude") == "Claude Code"

    def test_opencode_display_name(self):
        """OpenCode backend returns 'OpenCode' display name."""
        assert get_agent_display_name("opencode") == "OpenCode"

    def test_github_copilot_display_name(self):
        """GitHub Copilot backend returns correct display name."""
        assert get_agent_display_name("github-copilot") == "GitHub Copilot"

    def test_copilot_alias_display_name(self):
        """Copilot alias returns 'GitHub Copilot' display name."""
        assert get_agent_display_name("copilot") == "GitHub Copilot"

    def test_ollama_display_name(self):
        """Ollama backend returns correct display name."""
        assert get_agent_display_name("ollama") == "Ollama + Claude Code"

    def test_cursor_display_name(self):
        """Cursor backend returns 'Cursor' display name."""
        assert get_agent_display_name("cursor") == "Cursor"

    def test_windsurf_display_name(self):
        """Windsurf backend returns 'Windsurf' display name."""
        assert get_agent_display_name("windsurf") == "Windsurf"

    def test_crush_display_name(self):
        """Crush backend returns 'Crush' display name."""
        assert get_agent_display_name("crush") == "Crush"

    def test_aider_display_name(self):
        """Aider backend returns 'Aider' display name."""
        assert get_agent_display_name("aider") == "Aider"

    def test_continue_display_name(self):
        """Continue backend returns 'Continue' display name."""
        assert get_agent_display_name("continue") == "Continue"

    def test_none_defaults_to_claude(self):
        """None backend defaults to Claude Code."""
        assert get_agent_display_name(None) == "Claude Code"

    def test_case_insensitive(self):
        """Backend names are case-insensitive."""
        assert get_agent_display_name("Claude") == "Claude Code"
        assert get_agent_display_name("OPENCODE") == "OpenCode"

    def test_unknown_backend_returns_raw_name(self):
        """Unknown backend returns the raw backend string."""
        assert get_agent_display_name("unknown-agent") == "unknown-agent"

    def test_all_supported_backends_have_display_names(self):
        """Every supported backend has a display name entry."""
        from devflow.agent import SUPPORTED_BACKENDS
        for backend in SUPPORTED_BACKENDS:
            name = get_agent_display_name(backend)
            assert name != backend or backend in ("cursor", "windsurf", "aider", "continue", "crush"), \
                f"Backend '{backend}' should have a human-readable display name"


class TestGetManualResumeCommand:
    """Test get_manual_resume_command() across all agent implementations (#486)."""

    def test_claude_resume_command(self):
        agent = ClaudeAgent()
        cmd = agent.get_manual_resume_command("sess-123", "/home/user/project")
        assert cmd == "claude --resume sess-123"

    def test_ollama_resume_command(self):
        agent = OllamaClaudeAgent()
        cmd = agent.get_manual_resume_command("sess-123", "/home/user/project")
        assert cmd == "claude --resume sess-123"

    def test_opencode_resume_command(self):
        agent = OpenCodeAgent()
        cmd = agent.get_manual_resume_command("ses_abc", "/home/user/project")
        assert cmd == "opencode --session ses_abc"

    def test_crush_resume_command(self):
        agent = CrushAgent()
        cmd = agent.get_manual_resume_command("sess-123", "/home/user/project")
        assert cmd == "crush --session sess-123"

    def test_aider_resume_command(self):
        agent = AiderAgent()
        cmd = agent.get_manual_resume_command("sess-123", "/home/user/project")
        assert "aider --chat-history-file" in cmd
        assert "sess-123" in cmd

    def test_cursor_resume_command(self):
        agent = CursorAgent()
        cmd = agent.get_manual_resume_command("sess-123", "/home/user/project")
        assert cmd == 'cursor "/home/user/project"'

    def test_windsurf_resume_command(self):
        agent = WindsurfAgent()
        cmd = agent.get_manual_resume_command("sess-123", "/home/user/project")
        assert cmd == 'windsurf "/home/user/project"'

    def test_copilot_resume_command(self):
        agent = GitHubCopilotAgent()
        cmd = agent.get_manual_resume_command("sess-123", "/home/user/project")
        assert cmd == 'code "/home/user/project"'

    def test_continue_resume_command(self):
        agent = ContinueAgent()
        cmd = agent.get_manual_resume_command("sess-123", "/home/user/project")
        assert cmd == 'code "/home/user/project"'


class TestGenerateText:
    """Test generate_text() on AgentInterface (#486)."""

    @patch("subprocess.run")
    def test_claude_generate_text_success(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="Generated text\n")
        agent = ClaudeAgent()
        result = agent.generate_text("test prompt")
        assert result == "Generated text"
        mock_run.assert_called_once_with(
            ["claude", "-p"],
            input="test prompt",
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch("subprocess.run")
    def test_generate_text_returns_none_on_failure(self, mock_run):
        mock_run.return_value = Mock(returncode=1, stdout="")
        agent = ClaudeAgent()
        result = agent.generate_text("test prompt")
        assert result is None

    @patch("subprocess.run")
    def test_generate_text_returns_none_on_empty_output(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="   \n")
        agent = ClaudeAgent()
        result = agent.generate_text("test prompt")
        assert result is None

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_generate_text_returns_none_when_cli_missing(self, mock_run):
        agent = ClaudeAgent()
        result = agent.generate_text("test prompt")
        assert result is None

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=30))
    def test_generate_text_returns_none_on_timeout(self, mock_run):
        agent = ClaudeAgent()
        result = agent.generate_text("test prompt")
        assert result is None

    @patch("subprocess.run")
    def test_generate_text_custom_timeout(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="result\n")
        agent = ClaudeAgent()
        result = agent.generate_text("prompt", timeout=60)
        assert result == "result"
        mock_run.assert_called_once_with(
            ["claude", "-p"],
            input="prompt",
            capture_output=True,
            text=True,
            timeout=60,
        )

    @patch("subprocess.run")
    def test_opencode_generate_text_uses_opencode_binary(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="opencode result\n")
        agent = OpenCodeAgent()
        result = agent.generate_text("test prompt")
        assert result == "opencode result"
        mock_run.assert_called_once_with(
            ["opencode", "-p"],
            input="test prompt",
            capture_output=True,
            text=True,
            timeout=30,
        )


class TestUsesFileBasedSessions:
    """Test uses_file_based_sessions() across all agent implementations (#486)."""

    def test_claude_uses_file_sessions(self):
        assert ClaudeAgent().uses_file_based_sessions() is True

    def test_ollama_uses_file_sessions(self):
        assert OllamaClaudeAgent().uses_file_based_sessions() is True

    def test_opencode_uses_database_sessions(self):
        assert OpenCodeAgent().uses_file_based_sessions() is False

    def test_crush_uses_database_sessions(self):
        assert CrushAgent().uses_file_based_sessions() is False

    def test_aider_uses_file_sessions(self):
        assert AiderAgent().uses_file_based_sessions() is True

    def test_cursor_uses_file_sessions(self):
        assert CursorAgent().uses_file_based_sessions() is True

    def test_windsurf_uses_file_sessions(self):
        assert WindsurfAgent().uses_file_based_sessions() is True

    def test_copilot_uses_file_sessions(self):
        assert GitHubCopilotAgent().uses_file_based_sessions() is True

    def test_continue_uses_file_sessions(self):
        assert ContinueAgent().uses_file_based_sessions() is True
