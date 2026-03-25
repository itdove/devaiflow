"""Tests for Ollama Claude agent."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock, ANY
import subprocess
import os

from devflow.agent.ollama_claude_agent import OllamaClaudeAgent


def test_ollama_agent_init_default():
    """Test OllamaClaudeAgent initialization with default directory."""
    agent = OllamaClaudeAgent()

    assert agent.ollama_dir == Path.home() / ".ollama"
    # Sessions stored in ~/.claude regardless of launcher
    assert agent.claude_dir == Path.home() / ".claude"
    assert agent.projects_dir == agent.claude_dir / "projects"


def test_ollama_agent_init_custom_dir():
    """Test OllamaClaudeAgent initialization with custom directory."""
    custom_dir = Path("/custom/ollama")
    agent = OllamaClaudeAgent(ollama_dir=custom_dir)

    assert agent.ollama_dir == custom_dir
    # Sessions still stored in ~/.claude even with custom ollama_dir
    assert agent.claude_dir == Path.home() / ".claude"
    assert agent.projects_dir == agent.claude_dir / "projects"


def test_get_agent_name():
    """Test get_agent_name returns 'ollama'."""
    agent = OllamaClaudeAgent()
    assert agent.get_agent_name() == "ollama"


def test_get_agent_home_dir():
    """Test get_agent_home_dir returns ollama_dir."""
    custom_dir = Path("/tmp/ollama")
    agent = OllamaClaudeAgent(ollama_dir=custom_dir)
    assert agent.get_agent_home_dir() == custom_dir


def test_encode_project_path():
    """Test encode_project_path replaces / and _ with -."""
    agent = OllamaClaudeAgent()

    # Test / replacement
    assert agent.encode_project_path("/home/user/project") == "-home-user-project"

    # Test _ replacement
    assert agent.encode_project_path("/home/my_project") == "-home-my-project"

    # Test both
    assert agent.encode_project_path("/home/user/my_project") == "-home-user-my-project"


@patch("devflow.agent.ollama_claude_agent.require_tool")
@patch("subprocess.Popen")
def test_launch_session(mock_popen, mock_require_tool):
    """Test launch_session calls ollama launch claude command."""
    agent = OllamaClaudeAgent()
    project_path = "/home/user/project"

    mock_process = Mock()
    mock_popen.return_value = mock_process

    result = agent.launch_session(project_path)

    mock_require_tool.assert_called_once_with("ollama", "launch Claude Code with Ollama")
    mock_popen.assert_called_once_with(
        ["ollama", "launch", "claude"],
        cwd=project_path,
        env=ANY,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    assert result == mock_process


@patch("devflow.agent.ollama_claude_agent.require_tool")
@patch("subprocess.Popen")
def test_launch_session_with_model(mock_popen, mock_require_tool):
    """Test launch_session with OLLAMA_MODEL environment variable."""
    agent = OllamaClaudeAgent()
    project_path = "/home/user/project"

    mock_process = Mock()
    mock_popen.return_value = mock_process

    # Set OLLAMA_MODEL environment variable
    with patch.dict(os.environ, {"OLLAMA_MODEL": "qwen3-coder"}):
        result = agent.launch_session(project_path)

    mock_require_tool.assert_called_once_with("ollama", "launch Claude Code with Ollama")

    # Should include --model flag
    call_args = mock_popen.call_args
    assert call_args[0][0] == ["ollama", "launch", "claude", "--model", "qwen3-coder"]
    assert call_args[1]["cwd"] == project_path


@patch("devflow.agent.ollama_claude_agent.require_tool")
@patch("subprocess.Popen")
def test_resume_session(mock_popen, mock_require_tool):
    """Test resume_session calls ollama launch claude command.

    Note: ollama doesn't support --resume yet (TODO in implementation).
    """
    agent = OllamaClaudeAgent()
    project_path = "/home/user/project"
    session_id = "test-session-uuid"

    mock_process = Mock()
    mock_popen.return_value = mock_process

    result = agent.resume_session(session_id, project_path)

    mock_require_tool.assert_called_once_with("ollama", "resume Claude Code session with Ollama")
    # Ollama doesn't support --resume yet, so it just launches Claude Code
    mock_popen.assert_called_once_with(
        ["ollama", "launch", "claude"],
        cwd=project_path,
        env=ANY,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    assert result == mock_process


@patch("devflow.agent.ollama_claude_agent.require_tool")
@patch("subprocess.Popen")
def test_resume_session_with_model(mock_popen, mock_require_tool):
    """Test resume_session with OLLAMA_MODEL environment variable."""
    agent = OllamaClaudeAgent()
    project_path = "/home/user/project"
    session_id = "test-session-uuid"

    mock_process = Mock()
    mock_popen.return_value = mock_process

    with patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.3"}):
        result = agent.resume_session(session_id, project_path)

    call_args = mock_popen.call_args
    # Ollama doesn't support --resume yet
    assert call_args[0][0] == ["ollama", "launch", "claude", "--model", "llama3.3"]


def test_get_session_file_path():
    """Test get_session_file_path returns correct path.

    Note: Sessions are stored in ~/.claude regardless of ollama_dir.
    """
    agent = OllamaClaudeAgent(ollama_dir=Path("/tmp/ollama"))
    project_path = "/home/user/project"
    session_id = "test-uuid"

    result = agent.get_session_file_path(session_id, project_path)

    # Sessions stored in ~/.claude/projects not /tmp/ollama/projects
    expected = Path.home() / ".claude" / "projects" / "-home-user-project" / "test-uuid.jsonl"
    assert result == expected


def test_session_exists_true(tmp_path):
    """Test session_exists returns True when file exists."""
    ollama_dir = tmp_path / "ollama"
    agent = OllamaClaudeAgent(ollama_dir=ollama_dir)

    project_path = "/home/user/project"
    session_id = "test-uuid"

    # Create session file
    session_file = agent.get_session_file_path(session_id, project_path)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.touch()

    assert agent.session_exists(session_id, project_path) is True


def test_session_exists_false(tmp_path):
    """Test session_exists returns False when file doesn't exist."""
    ollama_dir = tmp_path / "ollama"
    agent = OllamaClaudeAgent(ollama_dir=ollama_dir)

    project_path = "/home/user/project"
    session_id = "nonexistent-uuid"

    assert agent.session_exists(session_id, project_path) is False


def test_get_existing_sessions(tmp_path):
    """Test get_existing_sessions returns set of session UUIDs.

    Note: Sessions are stored in ~/.claude regardless of ollama_dir.
    """
    # Mock the claude_dir to use tmp_path for testing
    agent = OllamaClaudeAgent()
    agent.claude_dir = tmp_path / "claude"
    agent.projects_dir = agent.claude_dir / "projects"

    project_path = "/home/user/project"

    # Create session directory in claude_dir not ollama_dir
    session_dir = agent.projects_dir / "-home-user-project"
    session_dir.mkdir(parents=True)

    # Create session files
    (session_dir / "session-1.jsonl").touch()
    (session_dir / "session-2.jsonl").touch()
    (session_dir / "session-3.jsonl").touch()

    sessions = agent.get_existing_sessions(project_path)

    assert sessions == {"session-1", "session-2", "session-3"}


def test_get_existing_sessions_empty(tmp_path):
    """Test get_existing_sessions returns empty set when no sessions."""
    # Mock the claude_dir to use tmp_path for testing
    agent = OllamaClaudeAgent()
    agent.claude_dir = tmp_path / "claude"
    agent.projects_dir = agent.claude_dir / "projects"

    project_path = "/home/user/project"

    sessions = agent.get_existing_sessions(project_path)

    assert sessions == set()


def test_get_session_message_count(tmp_path):
    """Test get_session_message_count returns line count."""
    ollama_dir = tmp_path / "ollama"
    agent = OllamaClaudeAgent(ollama_dir=ollama_dir)

    project_path = "/home/user/project"
    session_id = "test-uuid"

    # Create session file with 5 lines
    session_file = agent.get_session_file_path(session_id, project_path)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text("line1\nline2\nline3\nline4\nline5\n")

    count = agent.get_session_message_count(session_id, project_path)

    assert count == 5


def test_get_session_message_count_nonexistent(tmp_path):
    """Test get_session_message_count returns 0 for nonexistent file."""
    ollama_dir = tmp_path / "ollama"
    agent = OllamaClaudeAgent(ollama_dir=ollama_dir)

    project_path = "/home/user/project"
    session_id = "nonexistent-uuid"

    count = agent.get_session_message_count(session_id, project_path)

    assert count == 0


@patch("devflow.agent.ollama_claude_agent.time.sleep")
@patch.object(OllamaClaudeAgent, "launch_session")
@patch.object(OllamaClaudeAgent, "get_existing_sessions")
def test_capture_session_id_success(mock_get_sessions, mock_launch, mock_sleep):
    """Test capture_session_id successfully detects new session."""
    agent = OllamaClaudeAgent()
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


@patch("devflow.agent.ollama_claude_agent.time.sleep")
@patch.object(OllamaClaudeAgent, "launch_session")
@patch.object(OllamaClaudeAgent, "get_existing_sessions")
def test_capture_session_id_timeout(mock_get_sessions, mock_launch, mock_sleep):
    """Test capture_session_id raises TimeoutError when no new session detected."""
    agent = OllamaClaudeAgent()
    project_path = "/home/user/project"

    # Mock no new sessions detected
    mock_get_sessions.return_value = {"old-session"}
    mock_launch.return_value = Mock()

    with pytest.raises(TimeoutError) as exc_info:
        agent.capture_session_id(project_path, timeout=1, poll_interval=0.5)

    # Error message should say "Claude Code" not "Ollama Claude"
    assert "Failed to detect new Claude Code session" in str(exc_info.value)


def test_get_model_name_from_profile():
    """Test _get_model_name extracts model from profile."""
    agent = OllamaClaudeAgent()

    profile = {"model_name": "qwen3-coder"}
    assert agent._get_model_name(profile) == "qwen3-coder"


def test_get_model_name_from_env():
    """Test _get_model_name uses OLLAMA_MODEL env var."""
    agent = OllamaClaudeAgent()

    with patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.3"}):
        assert agent._get_model_name(None) == "llama3.3"


def test_get_model_name_default():
    """Test _get_model_name returns None for default."""
    agent = OllamaClaudeAgent()

    # Clear env var if present
    with patch.dict(os.environ, {}, clear=True):
        assert agent._get_model_name(None) is None


def test_get_model_name_priority():
    """Test _get_model_name prioritizes profile over env var."""
    agent = OllamaClaudeAgent()

    profile = {"model_name": "qwen3-coder"}

    with patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.3"}):
        # Profile should take priority
        assert agent._get_model_name(profile) == "qwen3-coder"


@patch("devflow.agent.ollama_claude_agent.require_tool")
@patch("subprocess.Popen")
def test_launch_with_prompt_basic(mock_popen, mock_require_tool):
    """Test launch_with_prompt with basic parameters.

    Note: ollama doesn't support --session-id or initial prompts yet (TODO).
    """
    agent = OllamaClaudeAgent()
    project_path = "/home/user/project"
    initial_prompt = "Start working on the feature"
    session_id = "test-session-123"

    mock_process = Mock()
    mock_popen.return_value = mock_process

    result = agent.launch_with_prompt(
        project_path=project_path,
        initial_prompt=initial_prompt,
        session_id=session_id,
    )

    mock_require_tool.assert_called_once_with("ollama", "launch Claude Code with Ollama")

    call_args = mock_popen.call_args
    # Ollama doesn't support --session-id or initial prompts yet
    assert call_args[0][0] == ["ollama", "launch", "claude"]
    assert call_args[1]["cwd"] == project_path
    assert result == mock_process


@patch("devflow.agent.ollama_claude_agent.require_tool")
@patch("subprocess.Popen")
def test_launch_with_prompt_with_model_profile(mock_popen, mock_require_tool):
    """Test launch_with_prompt with model provider profile."""
    agent = OllamaClaudeAgent()
    project_path = "/home/user/project"
    initial_prompt = "Start working"
    session_id = "test-session-123"
    model_profile = {"model_name": "qwen3-coder"}

    mock_process = Mock()
    mock_popen.return_value = mock_process

    result = agent.launch_with_prompt(
        project_path=project_path,
        initial_prompt=initial_prompt,
        session_id=session_id,
        model_provider_profile=model_profile,
    )

    call_args = mock_popen.call_args
    assert "--model" in call_args[0][0]
    assert "qwen3-coder" in call_args[0][0]


@patch("devflow.agent.ollama_claude_agent.require_tool")
@patch("subprocess.Popen")
def test_launch_with_prompt_with_skills_dirs(mock_popen, mock_require_tool):
    """Test launch_with_prompt with skills directories.

    Note: ollama doesn't support --add-dir yet (TODO), so skills_dirs are ignored.
    """
    agent = OllamaClaudeAgent()
    project_path = "/home/user/project"
    initial_prompt = "Start working"
    session_id = "test-session-123"
    skills_dirs = ["/home/user/.claude/skills", "/home/user/project/.claude/skills"]

    mock_process = Mock()
    mock_popen.return_value = mock_process

    result = agent.launch_with_prompt(
        project_path=project_path,
        initial_prompt=initial_prompt,
        session_id=session_id,
        skills_dirs=skills_dirs,
    )

    call_args = mock_popen.call_args
    cmd = call_args[0][0]

    # Ollama doesn't support --add-dir yet, so it's not in the command
    assert cmd == ["ollama", "launch", "claude"]
    assert result == mock_process
