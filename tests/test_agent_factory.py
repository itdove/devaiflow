"""Tests for shared agent launch orchestration."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from devflow.agent.factory import (
    _get_agent_conversation_title,
    launch_and_capture,
)


def test_agent_session_titles_are_distinct_across_repositories_and_replacements():
    """Titles retain the DAF name and distinguish repository/history contexts."""
    repo_a = SimpleNamespace(
        repo_name="repo-a",
        relative_path="repo-a",
        conversation_history=["pending-capture"],
    )
    repo_b = SimpleNamespace(
        repo_name="repo-b",
        relative_path="repo-b",
        conversation_history=[],
    )
    replacement = SimpleNamespace(
        repo_name="repo-a",
        relative_path="repo-a",
        conversation_history=["pending-capture"],
    )
    prior_conversation = SimpleNamespace(ai_agent_session_id="ses_previous")
    archived = SimpleNamespace(
        active_session=replacement,
        archived_sessions=[prior_conversation],
    )
    session = SimpleNamespace(
        working_directory="repo-a",
        conversations={"repo-a": archived},
    )

    title_a = _get_agent_conversation_title("session-a", "/workspace/repo-a", repo_a)
    title_b = _get_agent_conversation_title("session-a", "/workspace/repo-b", repo_b)
    replacement_title = _get_agent_conversation_title(
        "session-a", "/workspace/repo-a", replacement, session
    )

    assert title_a == "session-a [repo-a]"
    assert title_b == "session-a [repo-b]"
    assert replacement_title == "session-a [repo-a] #2"
    assert len({title_a, title_b, replacement_title}) == 3


@pytest.mark.parametrize(
    ("backend", "expected_title"),
    [
        ("claude", "session-a [repo-a]"),
        ("opencode", "session-a [repo-a]"),
        ("opencode-ai", "session-a [repo-a]"),
        ("pi", "session-a [repo-a]"),
        ("pi-coding-agent", "session-a [repo-a]"),
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
        conversation_history=[],
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
        )

    assert launch.call_args.kwargs["display_name"] == expected_title
