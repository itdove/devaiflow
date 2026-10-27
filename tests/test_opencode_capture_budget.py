"""Bounded, launch-proven native session capture and safe reopen (issue #648)."""

import json
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from click.testing import CliRunner

from devflow.agent.factory import (
    OPENCODE_CAPTURE_TIMEOUT,
    PENDING_CAPTURE_PLACEHOLDER,
    capture_agent_session_id,
    launch_and_capture,
    snapshot_agent_sessions,
)
from devflow.agent.opencode_agent import OpenCodeAgent, OpenCodeSessionQueryError
from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.config.models import Config, JiraConfig, RepoConfig
from devflow.session.manager import SessionManager


@pytest.fixture
def clock(monkeypatch):
    """Model elapsed query and sleep time without waiting in unit tests."""
    state = SimpleNamespace(now=0.0)
    monkeypatch.setattr("time.monotonic", lambda: state.now)

    def advance(seconds):
        state.now += seconds

    monkeypatch.setattr("time.sleep", advance)
    return state


@pytest.fixture
def native_agent(monkeypatch):
    """Never start OpenCode or inspect the developer's native session database."""
    agent = OpenCodeAgent()
    agent._opencode_major_version = 2
    monkeypatch.setattr("devflow.agent.opencode_agent.require_tool", lambda *args: None)
    monkeypatch.setattr(agent, "get_session_model_id", lambda *args: None)
    return agent


def test_slow_queries_share_one_wall_clock_budget(native_agent, monkeypatch, clock, capsys):
    """Even a visible candidate is not accepted after a later query times out."""
    timeouts = []

    def query(command, **kwargs):
        remaining = kwargs["timeout"]
        timeouts.append(remaining)
        clock.now += min(1.1, remaining)
        if remaining < 1.1:
            raise subprocess.TimeoutExpired(command, remaining)
        return Mock(returncode=0, stdout='[{"id":"ses_new","directory":"/project"}]')

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", query)
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)
    assert not capture_agent_session_id(native_agent, "opencode", "/project", conversation, set())
    assert clock.now == pytest.approx(OPENCODE_CAPTURE_TIMEOUT)
    assert len(timeouts) == 2
    assert timeouts == sorted(timeouts, reverse=True)
    assert conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
    assert "timed out" in capsys.readouterr().out


def test_slow_successful_queries_cover_grace_without_ten_commands(native_agent, monkeypatch, clock):
    """Ordinary half-second CLI starts count as observation time, not extra latency."""
    calls = []

    def query(command, **kwargs):
        calls.append(kwargs["timeout"])
        assert kwargs["timeout"] >= 0.65
        clock.now += 0.65
        return Mock(returncode=0, stdout='[{"id":"ses_new","directory":"/project"}]')

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", query)
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)
    assert capture_agent_session_id(native_agent, "opencode", "/project", conversation, set())
    assert len(calls) == 2
    assert clock.now == pytest.approx(1.4)
    assert conversation.ai_agent_session_id == "ses_new"


def test_version_detection_is_inside_query_budget(native_agent, monkeypatch, clock):
    """Lazy version discovery cannot add another independent five-second wait."""
    native_agent._opencode_major_version = None
    timeouts = []

    def query(command, **kwargs):
        timeouts.append(kwargs["timeout"])
        if command == ["opencode", "--version"]:
            clock.now += 1.5
            return Mock(returncode=0, stdout="2.0.22", stderr="")
        clock.now += kwargs["timeout"]
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", query)
    with pytest.raises(OpenCodeSessionQueryError, match="timed out"):
        native_agent.get_existing_sessions("/project", timeout=2, strict=True)
    assert timeouts == [2, 0.5]
    assert clock.now == 2


def test_real_slow_subprocess_cannot_outlive_capture_budget(native_agent, monkeypatch, tmp_path):
    """Exercise subprocess's real timeout/kill path without launching native OpenCode."""
    real_run = subprocess.run

    def slow_query(command, **kwargs):
        return real_run([sys.executable, "-c", "import time; time.sleep(10)"], **kwargs)

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", slow_query)
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)
    start = time.monotonic()
    assert not capture_agent_session_id(
        native_agent, "opencode", str(tmp_path), conversation, set(), timeout=0.2
    )
    assert time.monotonic() - start < 1.5
    assert conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER


def test_exhausted_query_budget_does_not_start_process(native_agent, monkeypatch):
    run = Mock()
    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", run)
    with pytest.raises(OpenCodeSessionQueryError, match="no time budget"):
        native_agent.get_existing_sessions("/project", timeout=0, strict=True)
    run.assert_not_called()


@pytest.mark.parametrize("duration", [2.0, 2.1])
def test_one_expensive_observation_is_not_enough_to_accept_identity(
    native_agent, monkeypatch, clock, duration
):
    """A deadline cannot become permission to accept the first/newest candidate."""

    def query(*args, **kwargs):
        clock.now += duration
        return {"ses_new"}

    monkeypatch.setattr(native_agent, "get_existing_sessions", query)
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)
    assert not capture_agent_session_id(native_agent, "opencode", "/project", conversation, set())
    assert conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER


@pytest.mark.parametrize(
    ("result", "diagnostic"),
    [
        (Mock(returncode=1, stdout="", stderr="private session text"), "exit code 1"),
        (Mock(returncode=0, stdout="private session text"), "invalid JSON"),
        (Mock(returncode=0, stdout='{"unexpected":"private session text"}'), "JSON shape"),
        (FileNotFoundError("private session text"), "could not run"),
    ],
)
def test_query_failures_are_not_empty_results(native_agent, monkeypatch, result, diagnostic):
    """Strict capture diagnostics never include stdout/stderr or OS exception contents."""
    run = Mock(side_effect=result) if isinstance(result, Exception) else Mock(return_value=result)
    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", run)
    with pytest.raises(OpenCodeSessionQueryError, match=diagnostic) as caught:
        native_agent.get_existing_sessions("/project", strict=True)
    assert "private session text" not in str(caught.value)
    assert native_agent.get_existing_sessions("/project") == set()


def test_failed_baseline_cannot_capture_an_old_session(native_agent, monkeypatch, capsys):
    """A failed snapshot is not proof that a later-listed native session is new."""
    query = Mock(return_value=Mock(returncode=1, stdout="", stderr="private session text"))
    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", query)
    baseline = snapshot_agent_sessions(native_agent, "opencode", "/project")
    query.return_value = Mock(returncode=0, stdout='[{"id":"ses_old","directory":"/project"}]')
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)
    assert not capture_agent_session_id(
        native_agent, "opencode", "/project", conversation, baseline
    )
    assert query.call_count == 1
    assert conversation.ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
    output = " ".join(capsys.readouterr().out.split())
    assert "Pre-launch snapshot unavailable" in output
    assert "private session text" not in output


@pytest.mark.parametrize("ambiguous", [False, True])
def test_delayed_visibility_and_late_ambiguity(native_agent, monkeypatch, clock, ambiguous):
    """A unique delayed ID is capturable; a late same-project rival is not."""
    calls = []

    def query(*args, **kwargs):
        calls.append(kwargs["timeout"])
        sessions = []
        if len(calls) >= 3:
            sessions.append({"id": "ses_new", "directory": "/project"})
        if ambiguous and len(calls) >= 5:
            sessions.append({"id": "ses_other", "directory": "/project"})
        sessions.append({"id": "ses_cross_project", "directory": "/elsewhere"})
        return Mock(returncode=0, stdout=json.dumps(sessions))

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", query)
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)
    captured = capture_agent_session_id(native_agent, "opencode", "/project", conversation, set())
    assert captured is not ambiguous
    assert conversation.ai_agent_session_id == (
        PENDING_CAPTURE_PLACEHOLDER if ambiguous else "ses_new"
    )
    assert clock.now <= OPENCODE_CAPTURE_TIMEOUT
    assert len(calls) >= 5


def test_empty_capture_diagnostic_does_not_promise_recovery(
    native_agent, monkeypatch, clock, capsys
):
    monkeypatch.setattr(
        "devflow.agent.opencode_agent.subprocess.run",
        Mock(return_value=Mock(returncode=0, stdout="[]")),
    )
    conversation = SimpleNamespace(ai_agent_session_id=PENDING_CAPTURE_PLACEHOLDER)
    assert not capture_agent_session_id(native_agent, "opencode", "/project", conversation, set())
    output = " ".join(capsys.readouterr().out.split())
    assert "No new opencode sessions" in output
    assert "will be captured on next open" not in output


@pytest.mark.parametrize("backend", ["opencode", "opencode-ai"])
@pytest.mark.parametrize("known", [False, True])
@pytest.mark.parametrize("baseline_failed", [False, True])
def test_known_launch_id_skips_post_exit_discovery(
    native_agent, monkeypatch, capsys, backend, known, baseline_failed
):
    """Creation/resume IDs survive unrelated list candidates and are known before wait."""
    events = []
    conversation = SimpleNamespace(
        ai_agent_session_id="ses_known" if known else PENDING_CAPTURE_PLACEHOLDER
    )
    native_id = "ses_known" if known else "ses_created"
    query = Mock(return_value={"ses_old", "ses_unrelated"})
    if baseline_failed:
        query.side_effect = OpenCodeSessionQueryError("OpenCode session query timed out")
    monkeypatch.setattr(native_agent, "get_existing_sessions", query)
    create = Mock(return_value=native_id)
    monkeypatch.setattr(native_agent, "_create_session_with_title", create)

    def remember(sid):
        assert conversation.ai_agent_session_id == sid == native_id
        events.append("persist")

    def spawn(command, **kwargs):
        assert events == ["persist"]
        assert command[command.index("--session") + 1] == native_id
        assert kwargs["env"]["AI_AGENT_SESSION_ID"] == native_id
        events.append("spawn")
        return Mock(returncode=0)

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.Popen", spawn)
    monkeypatch.setattr(native_agent, "wait_for_exit", lambda *args: events.append("exit"))
    launch_and_capture(
        native_agent,
        backend,
        "/project",
        conversation,
        initial_prompt="Read instructions",
        session_id=conversation.ai_agent_session_id,
        display_name="session-a",
        on_session_id=remember,
    )
    assert events == ["persist", "spawn", "exit"]
    assert query.call_count == (0 if known else 1)
    assert create.call_count == (0 if known else 1)
    assert "Warning" not in capsys.readouterr().out


def test_version_failure_diagnostics_do_not_repeat_cli_contents(native_agent, monkeypatch):
    native_agent._opencode_major_version = None
    monkeypatch.setattr(
        "devflow.agent.opencode_agent.subprocess.run",
        Mock(return_value=Mock(returncode=1, stdout="private session text", stderr="")),
    )
    with pytest.raises(OpenCodeSessionQueryError, match="version detection failed") as caught:
        native_agent.get_existing_sessions("/project", strict=True)
    assert "private session text" not in str(caught.value)


@pytest.fixture
def open_session_case(temp_daf_home, tmp_path, native_agent, monkeypatch):
    """Real DAF persistence and CLI flow, with external side effects isolated."""
    monkeypatch.chdir(tmp_path)
    loader = ConfigLoader()
    loader.save_config(
        Config(
            jira=JiraConfig(url="https://jira.example.com", user="test-user", transitions={}),
            repos=RepoConfig(),
            agent_backend="opencode",
        )
    )
    manager = SessionManager(loader)
    project = tmp_path / "project-a"
    project.mkdir()
    session = manager.create_session(
        name="session-a",
        goal="Test native capture",
        working_directory="project-a",
        project_path=str(project),
        branch="feature-a",
        ai_agent_session_id="initial-id",
        agent_backend="opencode",
    )
    session.active_conversation.ai_agent_session_id = ""
    manager.update_session(session)
    prefix = "devflow.cli.commands.open_command."
    for name in (
        "_handle_branch_checkout",
        "_check_and_sync_with_base_branch",
        "_validate_context_files",
        "should_launch_claude_code",
    ):
        monkeypatch.setattr(prefix + name, lambda *args, **kwargs: True)
    monkeypatch.setattr(prefix + "_detect_working_directory_from_cwd", lambda *args: None)
    monkeypatch.setattr(prefix + "get_active_profile", lambda *args, **kwargs: None)
    monkeypatch.setattr(prefix + "setup_signal_handlers", lambda *args: None)
    monkeypatch.setattr(prefix + "is_cleanup_done", lambda: False)
    monkeypatch.setattr(
        prefix + "_generate_initial_prompt", lambda *args, **kwargs: "Read instructions"
    )
    monkeypatch.setattr("devflow.agent.create_agent_client", lambda *args: native_agent)
    monkeypatch.setattr(native_agent, "_get_db_path", lambda: tmp_path / "native.db")
    return loader, manager, session, native_agent


def test_open_persists_precreated_id_before_child_and_resumes_it(open_session_case, monkeypatch):
    loader, _, session, agent = open_session_case
    events = []
    monkeypatch.setattr(agent, "get_existing_sessions", Mock(return_value={"ses_created"}))
    monkeypatch.setattr(agent, "_create_session_with_title", Mock(return_value="ses_created"))
    original_popen = subprocess.Popen

    def spawn(command, **kwargs):
        if command[0] != "opencode":
            return original_popen(command, **kwargs)
        saved = SessionManager(loader).get_session(session.name)
        assert saved.active_conversation.ai_agent_session_id == "ses_created"
        assert command[command.index("--session") + 1] == "ses_created"
        events.append("spawn")
        return Mock(returncode=0)

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.Popen", spawn)
    monkeypatch.setattr(agent, "wait_for_exit", lambda *args: events.append("exit"))
    monkeypatch.setattr(agent, "update_session_title", Mock(return_value=True))
    prompt = Mock(side_effect=lambda *args: events.append("prompt"))
    monkeypatch.setattr("devflow.cli.commands.open_command._prompt_for_complete_on_exit", prompt)

    first = CliRunner().invoke(cli, ["open", session.name])
    assert first.exit_code == 0, first.output
    assert events == ["spawn", "exit", "prompt"]
    assert agent.get_existing_sessions.call_count == 1
    assert "Could not capture" not in first.output
    second = CliRunner().invoke(cli, ["open", session.name])
    assert second.exit_code == 0, second.output
    assert events == ["spawn", "exit", "prompt", "spawn", "exit", "prompt"]
    agent._create_session_with_title.assert_called_once()
    assert agent.get_existing_sessions.call_count == 2


def test_fallback_capture_finishes_before_completion_prompt(open_session_case, monkeypatch, clock):
    """Actual CLI query duration counts toward the bounded post-exit observation window."""
    loader, _, session, agent = open_session_case
    events = []
    exited = []
    real_run = subprocess.run
    real_popen = subprocess.Popen
    monkeypatch.setattr(agent, "_create_session_with_title", Mock(return_value=None))

    def query(command, **kwargs):
        if command[0] != "opencode":
            return real_run(command, **kwargs)
        events.append("query")
        clock.now += 0.65
        sessions = (
            []
            if not exited
            else [{"id": "ses_captured", "directory": session.active_conversation.project_path}]
        )
        return Mock(returncode=0, stdout=json.dumps(sessions))

    def spawn(command, **kwargs):
        if command[0] != "opencode":
            return real_popen(command, **kwargs)
        events.append("spawn")
        return Mock(returncode=0)

    def wait(*args):
        events.append("exit")
        exited.append(clock.now)

    def complete_prompt(*args):
        events.append("prompt")
        assert clock.now - exited[0] <= OPENCODE_CAPTURE_TIMEOUT
        assert (
            SessionManager(loader).get_session(session.name).active_conversation.ai_agent_session_id
            == "ses_captured"
        )

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.run", query)
    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.Popen", spawn)
    monkeypatch.setattr(agent, "wait_for_exit", wait)
    monkeypatch.setattr(
        "devflow.cli.commands.open_command._prompt_for_complete_on_exit", complete_prompt
    )
    result = CliRunner().invoke(cli, ["open", session.name])
    assert result.exit_code == 0, result.output
    assert events == ["query", "spawn", "exit", "query", "query", "prompt"]
    assert "Warning" not in result.output


@pytest.mark.parametrize("invalid_id", ["ses_different", "not-a-native-id"])
def test_launch_callback_cannot_replace_known_native_identity(
    native_agent, monkeypatch, invalid_id
):
    """Even a bad adapter callback cannot mutate an already-associated native ID."""
    conversation = SimpleNamespace(ai_agent_session_id="ses_known")

    def bad_launch(**kwargs):
        kwargs["on_session_id"](invalid_id)

    monkeypatch.setattr(native_agent, "launch_with_prompt", bad_launch)
    with pytest.raises(ValueError, match="Refusing"):
        launch_and_capture(
            native_agent,
            "opencode",
            "/project",
            conversation,
            initial_prompt="Read instructions",
            session_id="ses_known",
        )
    assert conversation.ai_agent_session_id == "ses_known"


@pytest.mark.parametrize("json_mode", [False, True])
@pytest.mark.parametrize("state", ["pending", "missing", "query-failure"])
def test_unverified_reopen_never_replaces_identity(
    open_session_case, monkeypatch, json_mode, state
):
    loader, manager, session, agent = open_session_case
    session.active_conversation.ai_agent_session_id = (
        PENDING_CAPTURE_PLACEHOLDER if state == "pending" else "ses_existing"
    )
    manager.update_session(session)
    query = Mock(return_value=set())
    if state == "query-failure":
        query.side_effect = OpenCodeSessionQueryError("OpenCode session list returned invalid JSON")
    monkeypatch.setattr(agent, "get_existing_sessions", query)
    spawn = Mock()
    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.Popen", spawn)
    original = SessionManager(loader).get_session(session.name).model_dump()
    result = CliRunner().invoke(cli, ["open", session.name, *(["--json"] if json_mode else [])])
    assert result.exit_code == 1, result.output
    assert "No replacement conversation was launched" in " ".join(result.output.split())
    assert "--new-conversation" in result.output
    if json_mode:
        assert json.loads(result.output)["error"]["code"] == "AGENT_SESSION_UNVERIFIED"
    spawn.assert_not_called()
    assert SessionManager(loader).get_session(session.name).model_dump() == original
    if state == "pending":
        query.assert_not_called()


def test_explicit_new_conversation_archives_pending_identity(open_session_case, monkeypatch):
    """Starting over is an explicit user choice, not automatic capture recovery."""
    loader, manager, session, agent = open_session_case
    session.active_conversation.ai_agent_session_id = PENDING_CAPTURE_PLACEHOLDER
    manager.update_session(session)
    monkeypatch.setattr(agent, "get_existing_sessions", Mock(return_value=set()))
    monkeypatch.setattr(agent, "_create_session_with_title", Mock(return_value="ses_replacement"))
    original_popen = subprocess.Popen

    def spawn(command, **kwargs):
        if command[0] != "opencode":
            return original_popen(command, **kwargs)
        saved = SessionManager(loader).get_session(session.name)
        assert saved.active_conversation.ai_agent_session_id == "ses_replacement"
        return Mock(returncode=0)

    monkeypatch.setattr("devflow.agent.opencode_agent.subprocess.Popen", spawn)
    monkeypatch.setattr(agent, "wait_for_exit", Mock())
    monkeypatch.setattr("devflow.cli.commands.open_command._prompt_for_complete_on_exit", Mock())
    result = CliRunner().invoke(cli, ["open", session.name, "--new-conversation"])
    assert result.exit_code == 0, result.output
    agent._create_session_with_title.assert_called_once()
    saved = SessionManager(loader).get_session(session.name)
    assert saved.active_conversation.ai_agent_session_id == "ses_replacement"
    archived = saved.conversations["project-a"].archived_sessions
    assert len(archived) == 1
    assert archived[0].ai_agent_session_id == PENDING_CAPTURE_PLACEHOLDER
