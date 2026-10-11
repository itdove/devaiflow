"""Tests for shared agent launch orchestration."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from devflow.agent.factory import (
    _get_opencode_session_title,
    launch_and_capture,
)
from devflow.agent.opencode_agent import OpenCodeAgent


def test_opencode_session_titles_are_distinct_across_repositories_and_replacements():
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

    title_a = _get_opencode_session_title("session-a", "/workspace/repo-a", repo_a)
    title_b = _get_opencode_session_title("session-a", "/workspace/repo-b", repo_b)
    replacement_title = _get_opencode_session_title(
        "session-a", "/workspace/repo-a", replacement, session
    )

    assert title_a == "session-a [repo-a]"
    assert title_b == "session-a [repo-b]"
    assert replacement_title == "session-a [repo-a] #2"
    assert len({title_a, title_b, replacement_title}) == 3


def test_launch_and_capture_passes_conversation_specific_opencode_title():
    """Shared launch orchestration forwards the derived title to OpenCode."""
    agent = OpenCodeAgent()
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
            "opencode",
            "/workspace/repo-a",
            active_conversation,
            initial_prompt="Read the project instructions",
            session_id="pending-capture",
            display_name="session-a",
        )

    assert launch.call_args.kwargs["display_name"] == "session-a [repo-a]"
