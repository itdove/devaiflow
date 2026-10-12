"""Tests for Claude Code session title behavior."""

from unittest.mock import Mock, patch

from devflow.agent.claude_agent import ClaudeAgent


@patch("devflow.agent.claude_agent.require_tool")
@patch("devflow.agent.claude_agent.subprocess.Popen")
def test_launch_with_prompt_uses_daf_derived_session_title(
    mock_popen, mock_require_tool
):
    mock_popen.return_value = Mock()
    title = "session-a"

    ClaudeAgent().launch_with_prompt(
        project_path="/tmp/project-a",
        initial_prompt="Read the project instructions",
        session_id="new-session-id",
        skills_dirs=[],
        display_name=title,
    )

    command = mock_popen.call_args.args[0]
    assert command[command.index("--name") + 1] == title
    assert command[command.index("--session-id") + 1] == "new-session-id"
    mock_require_tool.assert_called_once_with("claude", "launch Claude Code session")


@patch("devflow.agent.claude_agent.require_tool")
@patch("devflow.agent.claude_agent.subprocess.Popen")
def test_resume_session_does_not_override_existing_title(mock_popen, mock_require_tool):
    mock_popen.return_value = Mock()
    session_id = "existing-session-id"

    ClaudeAgent().resume_session(session_id, "/tmp/project-a")

    command = mock_popen.call_args.args[0]
    assert command == ["claude", "--resume", session_id]
    assert "--name" not in command
    mock_require_tool.assert_called_once_with("claude", "resume Claude Code session")
