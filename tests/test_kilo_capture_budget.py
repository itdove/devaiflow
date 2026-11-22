"""Bounded, project-scoped native Kilo session capture regressions."""

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from devflow.agent.factory import (
    KILO_CAPTURE_TIMEOUT,
    OPENCODE_CAPTURE_TIMEOUT,
    PENDING_CAPTURE_PLACEHOLDER,
    capture_agent_session_id,
    launch_and_capture,
    snapshot_agent_sessions,
)
from devflow.agent.kilo_agent import KiloAgent, KiloSessionQueryError


@pytest.fixture
def clock(monkeypatch):
    """Model query and polling time without waiting in the test process."""
    state = SimpleNamespace(now=0.0)
    monkeypatch.setattr("time.monotonic", lambda: state.now)

    def advance(seconds):
        state.now += seconds

    monkeypatch.setattr("time.sleep", advance)
    return state


def test_slow_kilo_queries_capture_project_session_with_backend_budget(
    monkeypatch, clock
):
    """Version detection and slow listing stay within Kilo's bounded budget."""
    agent = KiloAgent()
    list_calls = 0
    list_timeouts = []

    def run(command, **kwargs):
        nonlocal list_calls
        if command == ["kilo", "--version"]:
            clock.now += 4
            return subprocess.CompletedProcess(command, 0, "7.8.27\n", "")
        if command == ["kilo", "session", "list", "--format", "json", "--all"]:
            list_calls += 1
            list_timeouts.append(kwargs["timeout"])
            clock.now += min(2, kwargs["timeout"])
            rows = (
                []
                if list_calls == 1
                else [
                    {"id": "ses_other", "directory": "/other"},
                    {"id": "ses_created", "directory": "/project"},
                ]
            )
            return subprocess.CompletedProcess(command, 0, json.dumps(rows), "")
        raise AssertionError(f"unexpected Kilo command: {command}")

    monkeypatch.setattr("devflow.agent.kilo_agent.subprocess.run", run)
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)
    process = Mock(returncode=0)
    agent.wait_for_exit = Mock()
    agent.update_session_title = Mock(return_value=True)
    persisted_ids = []

    def launch(**kwargs):
        kwargs["on_launch"]()
        return process

    agent.launch_with_prompt = launch

    launch_and_capture(
        agent,
        "kilo",
        "/project",
        conversation,
        initial_prompt="initial context",
        session_id=PENDING_CAPTURE_PLACEHOLDER,
        display_name="daf-session",
        env={"EXISTING": "yes"},
        on_session_id=persisted_ids.append,
    )

    assert conversation.ai_agent_session_id == "ses_created"
    assert persisted_ids == ["ses_created"]
    agent.update_session_title.assert_called_once_with(
        "ses_created", "daf-session", "/project", {"EXISTING": "yes"}
    )
    assert list_calls == 3
    assert list_timeouts[1] == pytest.approx(KILO_CAPTURE_TIMEOUT)
    assert KILO_CAPTURE_TIMEOUT == 10.0
    assert KILO_CAPTURE_TIMEOUT >= OPENCODE_CAPTURE_TIMEOUT
    assert clock.now < KILO_CAPTURE_TIMEOUT + 1


def test_kilo_capture_timeout_keeps_pending_identity(capsys):
    """A failed Kilo query never turns an unavailable baseline into a guess."""
    kilo = KiloAgent()
    kilo._kilo_version = (7, 8, 27)
    kilo.get_existing_sessions = Mock(
        side_effect=KiloSessionQueryError(
            "Kilo session query timed out within its time budget"
        )
    )
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)

    assert not capture_agent_session_id(kilo, "kilo", "/project", conversation, set())
    assert conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
    output = " ".join(capsys.readouterr().out.split())
    assert "timed out" in output
    assert "Native identity was not changed" in output


def test_failed_kilo_baseline_never_captures_an_existing_session(capsys):
    """An unavailable baseline is not evidence that a later-listed ID is new."""
    kilo = KiloAgent()
    kilo._kilo_version = (7, 8, 27)
    query = Mock(
        side_effect=KiloSessionQueryError(
            "Kilo session query timed out within its time budget"
        )
    )
    kilo.get_existing_sessions = query
    baseline = snapshot_agent_sessions(kilo, "kilo", "/project")
    assert query.call_args.kwargs["timeout"] == KILO_CAPTURE_TIMEOUT
    assert query.call_args.kwargs["strict"] is True
    query.side_effect = None
    query.return_value = {"ses_old"}
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)

    assert not capture_agent_session_id(
        kilo, "kilo", "/project", conversation, baseline
    )
    assert query.call_count == 1
    assert conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
    output = " ".join(capsys.readouterr().out.split())
    assert "Pre-launch snapshot unavailable" in output
