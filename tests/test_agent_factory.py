"""Tests for shared agent launch orchestration."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from devflow.agent.factory import (
    launch_and_capture,
)


@pytest.mark.parametrize(
    ("backend", "expected_title"),
    [
        ("claude", "session-a"),
        ("opencode", "session-a"),
        ("opencode-ai", "session-a"),
        ("pi", "session-a"),
        ("pi-coding-agent", "session-a"),
        ("ollama", None),
        ("ollama-claude", None),
        ("github-copilot", None),
        ("copilot", None),
        ("cursor", None),
        ("windsurf", None),
        ("aider", None),
        ("continue", None),
        ("crush", None),
        ("codex", None),
    ],
)
def test_launch_and_capture_uses_native_title_support(backend, expected_title):
    """Only backends with native title support receive a generated title."""
    agent = Mock()
    active_conversation = SimpleNamespace(
        ai_agent_session_id="pending-capture",
        repo_name="repo-a",
        relative_path="repo-a",
        conversation_history=["ses_previous"],
    )
    session = SimpleNamespace(
        conversations={
            "repo-a": SimpleNamespace(
                active_session=active_conversation,
                archived_sessions=[SimpleNamespace(ai_agent_session_id="ses_archived")],
            )
        }
    )
    process = Mock(returncode=0)

    with (
        patch("devflow.agent.factory.snapshot_agent_sessions", return_value=set()),
        patch("devflow.agent.factory.capture_agent_session_id"),
        patch.object(agent, "launch_with_prompt", return_value=process) as launch,
        patch.object(agent, "wait_for_exit"),
    ):
        launch_and_capture(
            agent,
            backend,
            "/workspace/repo-a",
            active_conversation,
            initial_prompt="Read the project instructions",
            session_id="pending-capture",
            display_name="session-a",
            session=session,
        )

    assert launch.call_args.kwargs["display_name"] == expected_title


@pytest.mark.parametrize("wait_error", [None, RuntimeError("wait failed"), KeyboardInterrupt()])
def test_launch_and_capture_holds_clone_lock_until_exit(tmp_path, wait_error, temp_daf_home):
    """Protect startup and the entire wait, then release on exit or interruption."""
    from devflow.utils.clone_lifecycle import (
        TemporaryDirectoryInUseError,
        temporary_directory_lock,
    )

    clone = tmp_path / "project-a"
    clone.mkdir()
    active_conversation = SimpleNamespace(
        ai_agent_session_id="pending-capture", temp_directory=str(clone)
    )
    process = Mock(returncode=0)
    agent = Mock()

    def assert_locked(*args, **kwargs):
        with (
            pytest.raises(TemporaryDirectoryInUseError, match="busy"),
            temporary_directory_lock(str(clone)),
        ):
            pass
        return process

    def wait_for_exit(*args):
        assert_locked()
        if wait_error is not None:
            raise wait_error

    agent.launch_with_prompt.side_effect = assert_locked
    agent.wait_for_exit.side_effect = wait_for_exit
    with (
        patch("devflow.agent.factory.snapshot_agent_sessions", return_value=set()),
        patch("devflow.agent.factory.capture_agent_session_id"),
    ):
        if wait_error is None:
            launch_and_capture(
                agent,
                "opencode",
                str(clone),
                active_conversation,
                initial_prompt="Read project instructions",
                session_id="pending-capture",
            )
        else:
            with pytest.raises(type(wait_error)):
                launch_and_capture(
                    agent,
                    "opencode",
                    str(clone),
                    active_conversation,
                    initial_prompt="Read project instructions",
                    session_id="pending-capture",
                )

    with temporary_directory_lock(str(clone)):
        pass


def test_launch_and_capture_does_not_capture_another_agents_session_when_locked(
    tmp_path, temp_daf_home
):
    """A rejected startup must not capture an ID created by the running agent."""
    from devflow.utils.clone_lifecycle import (
        TemporaryDirectoryInUseError,
        temporary_directory_lock,
    )

    clone = tmp_path / "project-a"
    clone.mkdir()
    active_conversation = SimpleNamespace(
        ai_agent_session_id="pending-capture", temp_directory=str(clone)
    )
    agent = Mock()
    with (
        patch("devflow.agent.factory.snapshot_agent_sessions", return_value=set()),
        patch("devflow.agent.factory.capture_agent_session_id") as capture,
        temporary_directory_lock(str(clone)),
        pytest.raises(TemporaryDirectoryInUseError),
    ):
        launch_and_capture(
            agent,
            "opencode",
            str(clone),
            active_conversation,
            initial_prompt="Read project instructions",
            session_id="pending-capture",
        )

    agent.launch_with_prompt.assert_not_called()
    capture.assert_not_called()
    assert active_conversation.ai_agent_session_id == "pending-capture"
