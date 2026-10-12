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
