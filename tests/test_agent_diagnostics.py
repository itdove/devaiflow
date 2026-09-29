"""Tests for safe AI agent launch diagnostics."""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from devflow.agent.diagnostics import (
    AgentLaunchError,
    failure_from_exception,
    failure_from_process,
)
from devflow.agent.factory import launch_and_capture
from devflow.exceptions import ToolNotFoundError


def test_failure_from_process_includes_sanitized_stderr():
    process = SimpleNamespace(
        returncode=2,
        stderr=StringIO(
            "Provider rejected the request: api_key=secret-api-key "
            "https://provider.example.test/error?token=secret-query"
        ),
        stdout=None,
    )

    failure = failure_from_process(
        process,
        backend="opencode",
        display_name="OpenCode",
        phase="launch",
        executable="opencode",
        env={"TEST_API_KEY": "secret-api-key"},
    )

    assert failure.exit_code == 2
    assert failure.code == "AGENT_PROCESS_EXITED"
    assert "Provider rejected the request" in failure.diagnostics
    assert "secret-api-key" not in failure.diagnostics
    assert "secret-query" not in failure.diagnostics
    assert failure.as_error()["backend"] == "opencode"
    assert failure.as_error()["phase"] == "launch"


def test_failure_from_process_reports_empty_diagnostics():
    process = SimpleNamespace(returncode=1, stderr=StringIO(""), stdout=StringIO(""))

    failure = failure_from_process(
        process,
        backend="codex",
        display_name="Codex",
        phase="resume",
        executable="codex",
    )

    assert failure.exit_code == 1
    assert failure.diagnostics == ""
    assert failure.as_error()["diagnostics"] == "(none provided)"
    assert "exit code 1" in failure.display_message


def test_failure_from_exception_explains_missing_executable():
    error = ToolNotFoundError(
        tool="opencode",
        operation="launch OpenCode AI assistant",
        install_url="https://opencode.example.test/install",
    )

    failure = failure_from_exception(
        error,
        backend="opencode",
        display_name="OpenCode",
        phase="launch",
        executable="opencode",
    )

    assert failure.code == "AGENT_EXECUTABLE_NOT_FOUND"
    assert failure.missing_executable is True
    assert "opencode" in failure.summary
    assert "PATH" in failure.summary
    assert failure.as_error()["install_url"] == "https://opencode.example.test/install"


@patch("devflow.agent.factory.capture_agent_session_id")
@patch("devflow.agent.factory.snapshot_agent_sessions", return_value=set())
def test_launch_and_capture_raises_structured_failure(
    mock_snapshot, mock_capture
):
    process = SimpleNamespace(
        returncode=3,
        stderr=StringIO("model configuration rejected"),
        stdout=None,
    )
    agent = Mock()
    agent.get_agent_name.return_value = "opencode"
    agent.launch_with_prompt.return_value = process
    active_conversation = SimpleNamespace(ai_agent_session_id="pending-capture")

    with pytest.raises(AgentLaunchError) as raised:
        launch_and_capture(
            agent,
            "opencode",
            "/tmp/project-a",
            active_conversation,
            initial_prompt="Read the project instructions",
            session_id="pending-capture",
        )

    assert raised.value.failure.backend == "opencode"
    assert raised.value.failure.phase == "launch"
    assert raised.value.failure.exit_code == 3
    mock_snapshot.assert_called_once()
    mock_capture.assert_called_once()
    assert mock_capture.call_args.kwargs["quiet"] is True
