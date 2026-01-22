"""Tests for agent interface abstraction."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devflow.agent import (
    AgentInterface,
    ClaudeAgent,
    GitHubCopilotAgent,
    CursorAgent,
    WindsurfAgent,
    create_agent_client,
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

        result = agent.launch_session(project_path)

        mock_require_tool.assert_called_once_with("claude", "launch Claude Code session")
        mock_popen.assert_called_once_with(
            ["claude", "code"],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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

    def test_unsupported_backend_raises_error(self):
        """Test factory raises ValueError for unsupported backend."""
        with pytest.raises(ValueError) as exc_info:
            create_agent_client("unsupported-backend")

        assert "Unsupported agent backend: unsupported-backend" in str(exc_info.value)
        assert "Supported backends: claude, github-copilot, cursor, windsurf" in str(exc_info.value)


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
