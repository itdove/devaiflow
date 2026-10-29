"""Regression coverage for live-agent clone protection (issue #643)."""

import json
import subprocess
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest
from click.testing import CliRunner

from devflow.cli.main import cli
from devflow.config.loader import ConfigLoader
from devflow.config.models import (
    Config,
    ConversationContext,
    JiraConfig,
    RepoConfig,
    Session,
    WorkSession,
)
from devflow.session.manager import SessionManager
from devflow.utils.clone_lifecycle import (
    TemporaryDirectoryInUseError,
    assert_temp_directory_unused,
    get_temp_directory_root,
    temporary_directory_lock,
    unused_session_clones,
)
from devflow.utils.paths import get_cs_state_home
from devflow.utils.temp_directory import cleanup_temp_directory, get_clone_base_dir


@contextmanager
def _running_process(
    cwd: Path, code: str = "import sys; print('ready', flush=True); sys.stdin.read()"
) -> Iterator[subprocess.Popen[str]]:
    """Keep a real child alive until the test releases its input pipe."""
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", code],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "ready"
        yield process
    finally:
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.communicate(timeout=5)


@pytest.fixture
def clone_session(temp_daf_home):
    """Create an isolated pending-capture investigation and its nested clone."""
    loader = ConfigLoader()
    loader.save_config(
        Config(
            jira=JiraConfig(url="https://jira.example.com", user="test-user", transitions={}),
            repos=RepoConfig(),
        )
    )
    manager = SessionManager(loader)
    clone = get_clone_base_dir() / "daf-session-a" / "project-a"
    clone.mkdir(parents=True)
    (clone / "work.txt").write_text("preserve this work")
    session = manager.create_session(
        name="session-a",
        goal="Investigate clone lifecycle",
        working_directory="project-a",
        project_path=str(clone),
        ai_agent_session_id="pending-capture",
        agent_backend="opencode",
    )
    session.session_type = "investigation"
    session.active_conversation.temp_directory = str(clone)
    session.status = "in_progress"
    session.time_tracking_state = "paused"
    session.work_sessions = [WorkSession(start=datetime.now(timezone.utc).replace(tzinfo=None))]
    manager.update_session(session)
    return loader, manager, session, clone


def _complete(name: str = "session-a", *options: str):
    """Invoke completion without remote services or interactive prompts."""
    return CliRunner().invoke(
        cli,
        ["complete", name, "--yes", "--no-commit", "--no-pr", "--no-issue-update", *options],
    )


def test_get_temp_directory_root_nested_and_legacy(clone_session, tmp_path):
    """Only the recognized nested layout expands to a session parent."""
    _, _, _, clone = clone_session
    assert get_temp_directory_root(str(clone)) == clone.parent
    legacy = tmp_path / "daf-investigation-a"
    assert get_temp_directory_root(str(legacy)) == legacy
    unrelated = tmp_path / "daf-session-other" / "project-a"
    assert get_temp_directory_root(str(unrelated)) == unrelated


def test_get_temp_directory_root_system_temp(monkeypatch, tmp_path):
    """Legacy nested clones in the system temporary directory use the same root."""
    monkeypatch.setattr("devflow.utils.clone_lifecycle.tempfile.gettempdir", lambda: str(tmp_path))
    clone = tmp_path / "daf-session-a" / "project-a"
    assert get_temp_directory_root(str(clone)) == clone.parent


def test_temp_directory_lock_none_and_exception_release(clone_session):
    """No-clone sessions need no lock; exceptions always release an acquired lock."""
    _, _, _, clone = clone_session
    with temporary_directory_lock(None):
        pass
    with pytest.raises(ValueError), temporary_directory_lock(str(clone)):
        raise ValueError("interrupted startup")
    with temporary_directory_lock(str(clone)):
        pass


def test_temp_directory_lock_cross_process_and_post_exit_cleanup(clone_session):
    """A separate launcher protects the root even when its own cwd is elsewhere."""
    loader, _, _, clone = clone_session
    original_index = loader.sessions_file.read_bytes()
    code = (
        "import sys\n"
        "from devflow.utils.clone_lifecycle import temporary_directory_lock\n"
        f"with temporary_directory_lock({str(clone)!r}):\n"
        "    print('ready', flush=True)\n"
        "    sys.stdin.read()\n"
    )
    with _running_process(Path(__file__).resolve().parents[1], code):
        result = _complete()
        assert result.exit_code == 1, result.output
        assert "session-a" in result.output and "busy" in result.output
        assert loader.sessions_file.read_bytes() == original_index
        with pytest.raises(TemporaryDirectoryInUseError, match="busy"):
            cleanup_temp_directory(str(clone))
        assert (clone / "work.txt").exists()

    cleanup_temp_directory(str(clone))
    assert not clone.parent.exists()
    assert (get_cs_state_home() / "clone-locks").is_dir()


def test_temp_directory_lock_creation_failure_preserves_clone(clone_session, monkeypatch):
    """An inaccessible lock never falls through to unsafe cleanup."""
    _, _, _, clone = clone_session
    monkeypatch.setattr(Path, "open", Mock(side_effect=PermissionError("not writable")))
    with pytest.raises(TemporaryDirectoryInUseError, match="Cannot lock"):
        cleanup_temp_directory(str(clone))
    assert clone.exists()


def test_temp_directory_lock_windows_branch(clone_session, monkeypatch):
    """Windows locks the same byte nonblockingly and unlocks on exit."""
    _, _, _, clone = clone_session
    locking = Mock()
    monkeypatch.setitem(
        sys.modules, "msvcrt", SimpleNamespace(locking=locking, LK_NBLCK=2, LK_UNLCK=0)
    )
    monkeypatch.setattr("devflow.utils.clone_lifecycle.sys.platform", "win32")
    with temporary_directory_lock(str(clone)):
        pass
    assert [call.args[1:] for call in locking.call_args_list] == [(2, 1), (0, 1)]


@pytest.mark.parametrize("location", ["project-a", "project-a/src", "project-b"])
def test_cleanup_protects_live_process_anywhere_in_session_root(clone_session, location):
    """Deleting a nested parent must also protect sibling repositories and descendants."""
    _, _, _, clone = clone_session
    cwd = clone.parent / location
    cwd.mkdir(parents=True, exist_ok=True)
    with _running_process(cwd) as process:
        with pytest.raises(TemporaryDirectoryInUseError, match=str(process.pid)):
            cleanup_temp_directory(str(clone))
        assert (clone / "work.txt").read_text() == "preserve this work"
    cleanup_temp_directory(str(clone))
    assert not clone.parent.exists()


def test_cleanup_protects_symlink_alias(clone_session, tmp_path):
    """Canonical paths prevent symlink aliases from bypassing process detection."""
    _, _, _, clone = clone_session
    alias = tmp_path / "clone-alias"
    try:
        alias.symlink_to(clone, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with _running_process(clone), pytest.raises(TemporaryDirectoryInUseError, match="in use"):
        cleanup_temp_directory(str(alias))
    assert clone.exists()


def test_usage_check_handles_exited_and_protected_processes(clone_session, monkeypatch):
    """Unrelated protected OS processes do not block cleanup of every clone."""
    _, _, _, clone = clone_session
    exited = Mock(pid=1)
    exited.cwd.side_effect = psutil.NoSuchProcess(1)
    protected = Mock(pid=2)
    protected.cwd.side_effect = psutil.AccessDenied(2)
    monkeypatch.setattr("psutil.process_iter", lambda: iter([exited, protected]))
    assert_temp_directory_unused(str(clone))
    assert_temp_directory_unused(str(clone / "missing"))


def test_usage_check_fails_closed_when_process_listing_fails(clone_session, monkeypatch):
    """A broken process listing must not be interpreted as an unused directory."""
    _, _, _, clone = clone_session
    monkeypatch.setattr("psutil.process_iter", Mock(side_effect=OSError("listing failed")))
    with pytest.raises(TemporaryDirectoryInUseError, match="Cannot verify"):
        cleanup_temp_directory(str(clone))
    assert clone.exists()


@pytest.mark.parametrize("session_type", ["investigation", "ticket_creation", "development"])
@pytest.mark.parametrize("tracking_state", ["paused", "active"])
@pytest.mark.parametrize("status", ["in_progress", "paused"])
def test_complete_rejects_live_pending_capture_without_mutation(
    clone_session, session_type, tracking_state, status
):
    """Pending IDs and paused tracking never prove that a live clone is unused."""
    loader, manager, session, clone = clone_session
    session.session_type = session_type
    session.time_tracking_state = tracking_state
    session.status = status
    manager.update_session(session)
    original_index = loader.sessions_file.read_bytes()

    with _running_process(clone) as process:
        result = _complete()
        assert result.exit_code == 1, result.output
        assert "session-a" in result.output
        assert str(process.pid) in result.output
        assert "daf complete session-a" in result.output
        assert "not changed" in result.output
        assert (clone / "work.txt").exists()
        assert loader.sessions_file.read_bytes() == original_index


@pytest.mark.parametrize("latest", [False, True])
def test_complete_in_use_json_is_clean_and_nonzero(clone_session, latest):
    """Both named and --latest rejection produce a single structured error."""
    loader, _, _, clone = clone_session
    original_index = loader.sessions_file.read_bytes()
    with _running_process(clone):
        result = _complete("--latest" if latest else "session-a", "--json")
    assert result.exit_code == 1, result.output
    data = json.loads(result.output)
    assert data["success"] is False
    assert data["error"]["code"] == "SESSION_IN_USE"
    assert data["error"]["session"] == "session-a"
    assert loader.sessions_file.read_bytes() == original_index


def test_complete_from_another_terminal_rejects_live_clone(clone_session):
    """Real completion and agent processes share no in-memory session state."""
    loader, _, _, clone = clone_session
    original_index = loader.sessions_file.read_bytes()
    with _running_process(clone):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from devflow.cli.main import cli; cli()",
                "complete",
                "session-a",
                "--yes",
                "--json",
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads(result.stdout)["error"]["code"] == "SESSION_IN_USE"
    assert loader.sessions_file.read_bytes() == original_index
    assert clone.exists()


def test_complete_preserves_clones_by_default_and_explicit_delete_cleans_up(clone_session):
    """Completion keeps a resumable clone; explicit session deletion still removes it."""
    from devflow.cli.commands.delete_command import delete_session

    loader, _, session, clone = clone_session
    assert loader.load_config().concurrency.cleanup_on_complete is False
    result = _complete()
    assert result.exit_code == 0, result.output
    assert clone.exists()
    assert SessionManager(loader).get_session(session.name).status == "complete"
    delete_session(identifier=session.name, force=True)
    assert not clone.exists()
    assert not clone.parent.exists()


@pytest.mark.parametrize("cleanup_enabled", [False, True])
def test_complete_after_exit_respects_config_and_independent_clones(clone_session, cleanup_enabled):
    """Only the completed clone is removed; paused and other live clones survive."""
    loader, manager, session, clone = clone_session
    config = loader.load_config()
    config.concurrency.cleanup_on_complete = cleanup_enabled
    loader.save_config(config)
    other = clone.parent.parent / "daf-session-ab" / "project-b"
    other.mkdir(parents=True)
    paused = clone.parent.parent / "daf-session-paused" / "project-c"
    paused.mkdir(parents=True)
    other_sessions = []
    for name, path, status in [
        ("session-b", other, "in_progress"),
        ("session-c", paused, "paused"),
    ]:
        other_session = manager.create_session(
            name=name,
            goal="Independent clone lifecycle",
            working_directory=path.name,
            project_path=str(path),
            ai_agent_session_id="pending-capture",
            agent_backend="opencode",
        )
        other_session.active_conversation.temp_directory = str(path)
        other_session.session_type = "investigation"
        other_session.status = status
        manager.update_session(other_session)
        other_sessions.append(other_session.model_dump())
    with _running_process(clone):
        pass
    with _running_process(other) as other_process:
        result = _complete()
        assert result.exit_code == 0, result.output
        assert other_process.poll() is None
        assert other.exists()
        assert paused.exists()
    assert clone.exists() is not cleanup_enabled
    assert clone.parent.exists() is not cleanup_enabled
    completed = SessionManager(loader).get_session(session.name)
    assert completed.status == "complete"
    assert completed.work_sessions[-1].end is not None
    for expected in other_sessions:
        assert SessionManager(loader).get_session(expected["name"]).model_dump() == expected


def test_complete_checks_other_conversations_before_mutation(clone_session):
    """Switching the active conversation cannot hide a live clone in the session."""
    loader, manager, session, clone = clone_session
    other = clone.parent.parent / "daf-session-b" / "project-b"
    other.mkdir(parents=True)
    session.add_conversation(
        working_dir="project-b",
        ai_agent_session_id="pending-capture",
        project_path=str(other),
        branch="main",
        temp_directory=str(other),
    )
    session.working_directory = "project-a"
    manager.update_session(session)
    original_index = loader.sessions_file.read_bytes()
    with _running_process(other):
        result = _complete()
    assert result.exit_code == 1, result.output
    assert clone.exists() and other.exists()
    assert loader.sessions_file.read_bytes() == original_index


def test_complete_defers_cleanup_if_agent_starts_after_preflight(clone_session, monkeypatch):
    """The final locked check closes the race after the initial liveness check."""
    loader, _, _, clone = clone_session
    config = loader.load_config()
    config.concurrency.cleanup_on_complete = True
    loader.save_config(config)
    with ExitStack() as processes:

        def start_late_agent(*args):
            processes.enter_context(_running_process(clone))

        monkeypatch.setattr(
            "devflow.orchestration.feature.FeatureManager.get_session_context", start_late_agent
        )
        result = _complete()
        assert result.exit_code == 0, result.output
        assert "cleanup was deferred" in result.output
        assert "daf complete session-a" in result.output
        assert clone.exists()

    monkeypatch.setattr(
        "devflow.orchestration.feature.FeatureManager.get_session_context", lambda *args: None
    )
    result = _complete()
    assert result.exit_code == 0, result.output
    assert not clone.parent.exists()


@pytest.mark.parametrize("session_id", ["ses_existing", "", "pending-session"])
@pytest.mark.parametrize("failure_phase", [None, "spawn", "wait"])
def test_open_resume_protects_clone_until_exit_and_releases_on_errors(
    clone_session, monkeypatch, session_id, failure_phase
):
    """Native resume, fresh reopen, and resume fallback protect the clone before spawning."""
    _, manager, session, clone = clone_session
    session.active_conversation.ai_agent_session_id = session_id
    session.active_conversation.agent_launch_started = False if session_id == "" else None
    manager.update_session(session)
    prefix = "devflow.cli.commands.open_command."
    monkeypatch.setattr(prefix + "_detect_working_directory_from_cwd", lambda *args: None)
    monkeypatch.setattr(prefix + "_handle_temp_directory_for_ticket_creation", lambda *args: None)
    monkeypatch.setattr(prefix + "_handle_branch_checkout", lambda *args, **kwargs: True)
    monkeypatch.setattr(prefix + "_check_and_sync_with_base_branch", lambda *args, **kwargs: True)
    monkeypatch.setattr(prefix + "should_launch_claude_code", lambda *args, **kwargs: True)
    monkeypatch.setattr(prefix + "resolve_agent_backend", lambda **kwargs: "opencode")
    monkeypatch.setattr(prefix + "get_active_profile", lambda *args, **kwargs: None)
    monkeypatch.setattr(prefix + "_copy_conversation_from_temp", lambda *args: None)
    monkeypatch.setattr(prefix + "Confirm.ask", lambda *args, **kwargs: True)
    monkeypatch.setattr("devflow.agent.factory.capture_agent_session_id", lambda *args, **kw: False)

    def assert_locked():
        with (
            pytest.raises(TemporaryDirectoryInUseError, match="busy"),
            temporary_directory_lock(str(clone)),
        ):
            pass

    process = Mock(returncode=0)

    def spawn(*args, **kwargs):
        assert_locked()
        if failure_phase == "spawn":
            raise RuntimeError("startup failed")
        return process

    def wait(*args):
        assert_locked()
        if failure_phase == "wait":
            raise RuntimeError("wait failed")

    agent = Mock()
    agent.get_agent_name.return_value = "opencode"
    agent.get_existing_sessions.return_value = set()
    agent.get_session_model_id.return_value = None
    agent.session_exists.return_value = True
    agent.resume_session.side_effect = spawn
    agent.launch_session.side_effect = spawn
    agent.launch_with_prompt.side_effect = spawn
    agent.wait_for_exit.side_effect = wait
    monkeypatch.setattr("devflow.agent.create_agent_client", lambda *args: agent)

    def check_post_exit_lock(*args):
        with temporary_directory_lock(str(clone)):
            pass

    prompt = Mock(side_effect=check_post_exit_lock)
    monkeypatch.setattr(prefix + "_prompt_for_complete_on_exit", prompt)
    result = CliRunner().invoke(cli, ["open", "session-a"])
    assert result.exit_code == 0, result.output
    if session_id == "ses_existing":
        agent.resume_session.assert_called_once()
        assert agent.resume_session.call_args.kwargs["isolated_workspace"] is True
    elif not session_id:
        agent.launch_with_prompt.assert_called_once()
        assert agent.launch_with_prompt.call_args.kwargs["isolated_workspace"] is True
    else:
        agent.launch_session.assert_called_once()
        assert agent.launch_session.call_args.kwargs["isolated_workspace"] is True
    if failure_phase != "spawn":
        agent.wait_for_exit.assert_called_once()
    if failure_phase is None:
        prompt.assert_called_once()
    with temporary_directory_lock(str(clone)):
        pass
    assert clone.exists()


@pytest.mark.parametrize("detail_error", [psutil.AccessDenied(1), psutil.NoSuchProcess(1)])
def test_holder_diagnostics_preserve_verified_pid_and_cwd_on_detail_errors(
    clone_session, monkeypatch, detail_error
):
    """Exit/permission races during extra detail reads never hide a verified holder."""
    _, _, _, clone = clone_session
    holder = Mock(pid=123)
    holder.cwd.return_value = str(clone)
    holder.name.side_effect = detail_error
    holder.ppid.side_effect = detail_error
    holder.parent.side_effect = detail_error
    monkeypatch.setattr("psutil.process_iter", lambda: iter([holder]))

    with pytest.raises(TemporaryDirectoryInUseError) as caught:
        assert_temp_directory_unused(str(clone))

    assert caught.value.holder == {
        "pid": 123,
        "name": None,
        "cwd": str(clone),
        "parent_pid": None,
        "parent_name": None,
        "parent_cwd": None,
    }
    assert "unavailable" in str(caught.value)
    holder.cmdline.assert_not_called()
    holder.environ.assert_not_called()


def test_holder_diagnostics_include_parent_and_escape_rich_markup(clone_session, monkeypatch):
    """Text/JSON retain process ownership details without interpreting process names as markup."""
    loader, _, _, clone = clone_session
    holder = Mock(pid=123)
    holder.cwd.return_value = str(clone)
    holder.name.return_value = "worker[red]"
    holder.ppid.return_value = 456
    parent = holder.parent.return_value
    parent.name.return_value = "backend-service"
    parent.cwd.return_value = str(clone.parent.parent)
    monkeypatch.setattr("psutil.process_iter", lambda: iter([holder]))
    original_index = loader.sessions_file.read_bytes()

    result = _complete()
    assert result.exit_code == 1, result.output
    assert "worker[red]" in result.output
    assert "parent PID: 456" in result.output
    assert "backend-service" in result.output
    data = json.loads(_complete("session-a", "--json").output)
    assert data["error"]["holder"] == {
        "pid": 123,
        "name": "worker[red]",
        "cwd": str(clone),
        "parent_pid": 456,
        "parent_name": "backend-service",
        "parent_cwd": str(clone.parent.parent),
    }
    assert loader.sessions_file.read_bytes() == original_index


@pytest.mark.parametrize("detail_error", [psutil.AccessDenied(1), psutil.NoSuchProcess(1)])
def test_holder_diagnostics_keep_parent_pid_when_parent_details_disappear(
    clone_session, monkeypatch, detail_error
):
    """A parent exiting between lookup and detail reads must not hide its child."""
    _, _, _, clone = clone_session
    holder = Mock(pid=123)
    holder.cwd.return_value = str(clone)
    holder.name.return_value = "worker"
    holder.ppid.return_value = 456
    parent = holder.parent.return_value
    parent.name.side_effect = detail_error
    parent.cwd.side_effect = detail_error
    monkeypatch.setattr("psutil.process_iter", lambda: iter([holder]))
    with pytest.raises(TemporaryDirectoryInUseError) as caught:
        assert_temp_directory_unused(str(clone))
    assert caught.value.holder["parent_pid"] == 456
    assert caught.value.holder["parent_name"] is None
    assert caught.value.holder["parent_cwd"] is None
    assert caught.value.holder["name"] == "worker"


@pytest.mark.parametrize("auto_complete", [None, True])
@pytest.mark.parametrize("cleanup_enabled", [False, True])
def test_exited_ui_with_shared_service_worker_refuses_until_resources_released(
    clone_session, monkeypatch, tmp_path, capsys, auto_complete, cleanup_enabled
):
    """Reproduce the UI/service lifetime split using real processes, not stale PIDs.

    A service outside the clone owns a worker inside it. An independent UI exits;
    neither DAF's prompted nor automatic path may stop/evict the shared service.
    The fixture's owner later releases the worker normally, allowing completion.
    """
    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit

    loader, manager, session, clone = clone_session
    config = loader.load_config()
    config.prompts.auto_complete_on_exit = auto_complete
    config.concurrency.cleanup_on_complete = cleanup_enabled
    loader.save_config(config)
    session.active_conversation.ai_agent_session_id = "ses_existing"
    manager.update_session(session)
    original_index = loader.sessions_file.read_bytes()
    code = (
        "import subprocess, sys\n"
        "worker = subprocess.Popen([sys.executable, '-u', '-c', "
        '"import sys; sys.stdin.read()"], '
        f"cwd={str(clone)!r}, stdin=subprocess.PIPE)\n"
        "print('ready', flush=True)\n"
        "try:\n"
        "    sys.stdin.read()\n"
        "finally:\n"
        "    worker.communicate(timeout=5)\n"
    )
    other = tmp_path / "project-b"
    other.mkdir()
    with _running_process(other) as other_backend:
        with _running_process(tmp_path, code) as service:
            ui = subprocess.run([sys.executable, "-c", "pass"], cwd=clone, timeout=5, check=True)
            assert ui.returncode == 0 and service.poll() is None
            confirm = Mock(side_effect=AssertionError("Do not offer completion while held"))
            monkeypatch.setattr("devflow.cli.commands.open_command.Confirm.ask", confirm)
            _prompt_for_complete_on_exit(session, config)
            output = capsys.readouterr().out
            assert "Cannot complete session" in output
            assert "shared server" in output
            assert "Failed to complete session: 1" not in output
            confirm.assert_not_called()
            result = _complete("session-a", "--json")
            assert result.exit_code == 1, result.output
            holder = json.loads(result.output)["error"]["holder"]
            assert holder["cwd"] == str(clone)
            assert holder["parent_pid"] == service.pid
            assert holder["parent_cwd"] == str(tmp_path)
            assert holder["name"] and holder["parent_name"]
            assert loader.sessions_file.read_bytes() == original_index
            with pytest.raises(TemporaryDirectoryInUseError):
                cleanup_temp_directory(str(clone))
            assert service.poll() is None
            assert clone.exists()

        # Only the test fixture's verified owner releases its service/worker.
        # DAF must leave a different active project's backend alone.
        result = _complete()
        assert result.exit_code == 0, result.output
        assert other_backend.poll() is None and other.exists()
    completed = SessionManager(loader).get_session(session.name)
    assert completed.status == "complete"
    assert completed.active_conversation.ai_agent_session_id == "ses_existing"
    assert clone.exists() is not cleanup_enabled


@pytest.mark.parametrize("auto_complete", [None, True])
@pytest.mark.parametrize("exit_code", [0, 1])
def test_post_exit_expected_completion_exit_has_no_opaque_secondary_error(
    clone_session, monkeypatch, capsys, auto_complete, exit_code
):
    """A late refusal after preflight is already reported, and env is restored."""
    import os

    import click

    from devflow.cli.commands.open_command import _prompt_for_complete_on_exit

    loader, _, session, _ = clone_session
    config = loader.load_config()
    config.prompts.auto_complete_on_exit = auto_complete
    monkeypatch.setenv("DEVAIFLOW_IN_SESSION", "1")
    monkeypatch.setenv("AI_AGENT_SESSION_ID", "ses_existing")
    monkeypatch.setattr("devflow.cli.commands.open_command.Confirm.ask", lambda *a, **kw: True)
    monkeypatch.setattr(
        "devflow.cli.commands.complete_command.complete_session",
        Mock(side_effect=click.exceptions.Exit(exit_code)),
    )
    _prompt_for_complete_on_exit(session, config)
    output = capsys.readouterr().out
    assert "Failed to complete session" not in output
    assert ("retry with" in output) is bool(exit_code)
    assert os.environ["DEVAIFLOW_IN_SESSION"] == "1"
    assert os.environ["AI_AGENT_SESSION_ID"] == "ses_existing"


def test_unused_session_clones_deduplicates_and_locks_archived_roots(clone_session):
    """Transitions protect all history and acquire each shared removal root once."""
    _, _, session, clone = clone_session
    sibling = clone.parent / "project-b"
    sibling.mkdir()
    session.add_conversation(
        working_dir="project-b",
        project_path=str(sibling),
        ai_agent_session_id="ses_sibling",
        branch="feature-b",
        temp_directory=str(sibling),
    )
    archived = clone.parent.parent / "daf-session-z" / "project-old"
    archived.mkdir(parents=True)
    session.conversations["project-a"].archived_sessions.append(
        ConversationContext(
            ai_agent_session_id="ses_archived",
            project_path=str(archived),
            temp_directory=str(archived),
            archived=True,
        )
    )
    before = session.model_dump()
    with unused_session_clones(session) as roots:
        assert roots == sorted([str(clone.parent), str(archived.parent)])
        for path in (clone, sibling, archived):
            with pytest.raises(TemporaryDirectoryInUseError), temporary_directory_lock(str(path)):
                pass
    assert session.model_dump() == before
    for root in roots:
        with temporary_directory_lock(root):
            pass


def test_unused_session_clones_releases_earlier_locks_when_archived_clone_is_busy(clone_session):
    """A cross-process refusal on a later root releases every earlier acquisition."""
    _, _, session, clone = clone_session
    archived = clone.parent.parent / "daf-session-z" / "project-old"
    archived.mkdir(parents=True)
    session.conversations["project-a"].archived_sessions.append(
        ConversationContext(
            ai_agent_session_id="pending-capture",
            project_path=str(archived),
            temp_directory=str(archived),
            archived=True,
        )
    )
    code = (
        "import sys\n"
        "from devflow.utils.clone_lifecycle import temporary_directory_lock\n"
        f"with temporary_directory_lock({str(archived)!r}):\n"
        "    print('ready', flush=True)\n"
        "    sys.stdin.read()\n"
    )
    with _running_process(Path(__file__).resolve().parents[1], code):
        with pytest.raises(TemporaryDirectoryInUseError), unused_session_clones(session):
            pytest.fail("A busy archived clone must block the transition")
        with temporary_directory_lock(str(clone)):
            pass
        assert clone.exists() and archived.exists()


def test_unused_session_clones_without_clones():
    """A not-yet-opened development session needs no filesystem locks."""
    with unused_session_clones(Session(name="session-a")) as roots:
        assert roots == []


def test_cleanup_under_session_guard_keeps_lock_after_removal(clone_session):
    """Metadata persistence remains protected after the physical clone is removed."""
    _, _, session, clone = clone_session
    with unused_session_clones(session):
        cleanup_temp_directory(str(clone), locked=True)
        assert not clone.parent.exists()
        with pytest.raises(TemporaryDirectoryInUseError), temporary_directory_lock(str(clone)):
            pass
    with temporary_directory_lock(str(clone)):
        pass


def test_contended_lock_includes_available_directory_holder(clone_session):
    """A failed lock reports a real cwd holder without weakening the refusal."""
    _, _, _, clone = clone_session
    source = str(Path(__file__).resolve().parents[1])
    code = (
        f"import sys; sys.path.insert(0, {source!r})\n"
        "from devflow.utils.clone_lifecycle import temporary_directory_lock\n"
        f"with temporary_directory_lock({str(clone)!r}):\n"
        "    print('ready', flush=True)\n"
        "    sys.stdin.read()\n"
    )
    with _running_process(clone, code) as process:
        with pytest.raises(TemporaryDirectoryInUseError) as caught:
            with temporary_directory_lock(str(clone)):
                pytest.fail("Never proceed after lock contention")
        assert caught.value.holder["pid"] == process.pid
        assert caught.value.holder["cwd"] == str(clone)
        assert process.poll() is None
        assert clone.exists()


@pytest.fixture(params=["jira-legacy", "jira-unified", "github", "gitlab"])
def creation_sync(clone_session, monkeypatch, request):
    """Exercise every sync conversion path with real persisted creation history."""
    from devflow.cli.commands import sync_command
    from devflow.config.models import JiraFiltersConfig

    loader, manager, session, clone = clone_session
    backend = request.param.split("-")[0]
    key = "PROJ-12345" if backend == "jira" else "owner/project-a#42"
    name = "creation-PROJ-12345" if backend == "jira" else "owner-project-a-42"
    manager.rename_session(session.name, name)
    session.session_type = "ticket_creation"
    session.issue_key = key
    session.workspace_name = "workspace-1"
    session.active_conversation.ai_agent_session_id = "ses_creation"
    session.active_conversation.branch = "creation-source"
    session.active_conversation.conversation_history = ["ses_previous", "ses_creation"]
    session.conversations["project-a"].archived_sessions.append(
        ConversationContext(
            ai_agent_session_id="ses_previous",
            project_path=str(clone),
            temp_directory=str(clone),
            archived=True,
            branch="previous-source",
        )
    )
    manager.update_session(session)
    (loader.get_session_dir(name) / "notes.md").write_text("Preserve creation notes")
    config = loader.load_config()
    config.jira.project = "PROJ"
    config.jira.filters = {"sync": JiraFiltersConfig(required_fields=[])}
    config.jira.field_cache_auto_refresh = False
    loader.save_config(config)
    ticket = {
        "key": key,
        "summary": "Implement a generic feature",
        "type": "Story",
        "updated": "2026-10-29T12:00:00Z",
    }
    client = Mock()
    client.list_tickets.return_value = [ticket]
    monkeypatch.setattr(sync_command, "JiraClient", Mock(return_value=client))
    monkeypatch.setattr("devflow.github.issues_client.GitHubClient", Mock(return_value=client))
    monkeypatch.setattr("devflow.gitlab.issues_client.GitLabClient", Mock(return_value=client))
    real_run = subprocess.run

    def fake_username(command, *args, **kwargs):
        if command and command[0] in ("gh", "glab"):
            stdout = '{"username": "test-user"}' if command[0] == "glab" else "test-user\n"
            return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_username)

    def sync():
        if request.param == "jira-legacy":
            return sync_command.sync_jira()
        if request.param == "jira-unified":
            return sync_command.sync_multi_backend(sync_workspaces=False)
        function = getattr(sync_command, f"sync_{backend}_repository")
        return function("owner/project-a", SessionManager(loader), loader.load_config())

    return loader, manager, session, clone, sync, ticket


def test_live_creation_sync_open_delete_and_retry_preserve_history(creation_sync, capsys):
    """A live launcher outside the clone blocks transitions until normal owner exit."""
    loader, _, session, clone, sync, _ = creation_sync
    before = session.model_dump()
    original_index = loader.sessions_file.read_bytes()
    session_dir = loader.get_session_dir(session.name)
    original_files = {p.name: p.read_bytes() for p in session_dir.iterdir() if p.is_file()}
    code = (
        "import sys\n"
        "from devflow.utils.clone_lifecycle import temporary_directory_lock\n"
        f"with temporary_directory_lock({str(clone)!r}):\n"
        "    print('ready', flush=True)\n"
        "    sys.stdin.read()\n"
    )
    with _running_process(Path(__file__).resolve().parents[1], code) as owner:
        sync()
        output = capsys.readouterr().out
        assert "Deferred conversion" in output
        assert "retry 'daf sync'" in output
        assert "Converting ticket_creation" not in output
        assert loader.sessions_file.read_bytes() == original_index
        for command in (
            ["open", session.name, "--json"],
            ["delete", session.name, "--force", "--json"],
        ):
            result = CliRunner().invoke(cli, command)
            assert result.exit_code == 1, result.output
            assert isinstance(result.exception, SystemExit), repr(result.exception)
            assert result.output.lstrip().startswith("{"), (command, result.output)
            data = json.loads(result.output)
            assert data["success"] is False
            assert data["error"]["code"] == "SESSION_IN_USE"
            assert "Traceback" not in result.output
            assert "CLONE_RECOVERY_FAILED" not in result.output
            assert loader.sessions_file.read_bytes() == original_index
        assert owner.poll() is None
        assert (clone / "work.txt").read_text() == "preserve this work"
        assert SessionManager(loader).get_session(session.name).model_dump() == before
        saved_files = {p.name: p.read_bytes() for p in session_dir.iterdir() if p.is_file()}
        assert saved_files == original_files

    sync()
    converted = SessionManager(loader).get_session(session.name)
    assert converted.session_type == "development"
    assert converted.workspace_name == "workspace-1"
    assert converted.conversations == session.conversations
    assert converted.work_sessions == session.work_sessions
    assert converted.time_tracking_state == session.time_tracking_state
    assert (session_dir / "notes.md").read_text() == "Preserve creation notes"
    assert clone.exists()
    result = CliRunner().invoke(cli, ["delete", session.name, "--force", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["data"]["deleted_sessions"] == [session.name]
    assert SessionManager(loader).get_session(session.name) is None
    assert not clone.parent.exists()


def test_conversion_never_recovers_an_unverified_pending_identity(creation_sync, monkeypatch):
    """Releasing a clone lock is not proof of ownership of a missing native ID."""
    loader, manager, session, _, sync, _ = creation_sync
    session.active_conversation.ai_agent_session_id = "pending-capture"
    session.active_conversation.agent_launch_started = None
    manager.update_session(session)
    sync()
    converted = SessionManager(loader).get_session(session.name)
    assert converted.session_type == "development"
    monkeypatch.setattr("devflow.cli.utils.select_workspace", lambda *a, **kw: None)
    monkeypatch.setattr(
        "devflow.cli.commands.open_command._detect_working_directory_from_cwd", lambda *a: None
    )
    monkeypatch.setattr("devflow.cli.commands.open_command._copy_conversation_to_temp", Mock())
    agent_factory = Mock(side_effect=AssertionError("Never guess or replace native identity"))
    monkeypatch.setattr("devflow.agent.create_agent_client", agent_factory)
    result = CliRunner().invoke(cli, ["open", session.name, "--json"])
    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert result.output.lstrip().startswith("{"), result.output
    assert json.loads(result.output)["error"]["code"] == "AGENT_SESSION_UNVERIFIED"
    agent_factory.assert_not_called()
    saved = SessionManager(loader).get_session(session.name)
    assert saved.conversations == converted.conversations
    assert saved.active_conversation.agent_launch_started is None


@pytest.mark.parametrize("json_mode", [False, True])
@pytest.mark.parametrize("extra", [[], ["--new-conversation"], ["--workspace", "workspace-2"]])
def test_open_live_clone_refuses_before_metadata_options(clone_session, json_mode, extra):
    """Open reports a real holder before workspace or native-identity replacement."""
    loader, _, session, clone = clone_session
    original_index = loader.sessions_file.read_bytes()
    with _running_process(clone) as owner:
        result = CliRunner().invoke(
            cli, ["open", session.name, *extra, *(["--json"] if json_mode else [])]
        )
        assert result.exit_code == 1, result.output
        if json_mode:
            data = json.loads(result.output)
            assert data["error"]["code"] == "SESSION_IN_USE"
            assert data["error"]["holder"]["pid"] == owner.pid
            assert data["error"]["holder"]["cwd"] == str(clone)
        else:
            assert "Cannot open session" in result.output
            assert str(owner.pid) in result.output
        assert "CLONE_RECOVERY_FAILED" not in result.output
        assert loader.sessions_file.read_bytes() == original_index
        assert (clone / "work.txt").exists()


@pytest.mark.parametrize("mode", ["single", "group", "all"])
@pytest.mark.parametrize("force", [False, True])
def test_delete_live_clone_is_a_concise_refusal(clone_session, monkeypatch, mode, force):
    """Every deletion route preserves busy data; force changes confirmation only."""
    loader, _, session, clone = clone_session
    original_index = loader.sessions_file.read_bytes()
    session_dir = loader.get_session_dir(session.name)
    (session_dir / "notes.md").write_text("Preserve notes")
    metadata = (session_dir / "metadata.json").read_bytes()
    if mode == "group":
        monkeypatch.setattr(
            "devflow.cli.commands.delete_command.get_session_with_delete_all_option",
            lambda *args: (session, True),
        )
    arguments = ["delete", "--all" if mode == "all" else session.name]
    if force:
        arguments.append("--force")
    with _running_process(clone):
        result = CliRunner().invoke(cli, arguments, input="y\n")
    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit)
    assert "Cannot delete session" in result.output
    assert "--force skips confirmation only" in " ".join(result.output.split())
    assert "Traceback" not in result.output
    assert "✓" not in result.output
    assert loader.sessions_file.read_bytes() == original_index
    assert (session_dir / "metadata.json").read_bytes() == metadata
    assert (session_dir / "notes.md").read_text() == "Preserve notes"
    assert (clone / "work.txt").exists()


@pytest.mark.parametrize("json_mode", [False, True])
def test_delete_all_reports_partial_results_and_preserves_busy_metadata(clone_session, json_mode):
    """A safe batch member can be removed without orphaning a refused member."""
    loader, manager, session, clone = clone_session
    safe = manager.create_session(name="session-b", goal="Inactive independent session")
    safe_dir = loader.get_session_dir(safe.name)
    (safe_dir / "notes.md").write_text("Safe notes")
    busy_dir = loader.get_session_dir(session.name)
    (busy_dir / "notes.md").write_text("Busy notes")
    before = session.model_dump()
    metadata = (busy_dir / "metadata.json").read_bytes()
    unrelated = loader.sessions_dir / "unindexed-user-work"
    unrelated.mkdir()
    (unrelated / "work.txt").write_text("Do not sweep unrelated metadata")
    arguments = ["delete", "--all", "--force", *(["--json"] if json_mode else [])]
    with _running_process(clone):
        result = CliRunner().invoke(cli, arguments)
    assert result.exit_code == 1, result.output
    if json_mode:
        data = json.loads(result.output)
        assert data["success"] is False
        assert data["data"]["deleted_count"] == data["data"]["refused_count"] == 1
        assert data["data"]["deleted_sessions"] == [safe.name]
        assert data["data"]["refused_sessions"][0]["session"] == session.name
    else:
        assert "Deleted 1 sessions; preserved 1 refused sessions" in result.output
        assert "All 2 sessions deleted" not in result.output
    saved = SessionManager(loader)
    assert saved.get_session(safe.name) is None
    assert not safe_dir.exists()
    assert saved.get_session(session.name).model_dump() == before
    assert (busy_dir / "metadata.json").read_bytes() == metadata
    assert (busy_dir / "notes.md").read_text() == "Busy notes"
    assert (clone / "work.txt").exists()
    assert (unrelated / "work.txt").exists()
    retry = CliRunner().invoke(cli, ["delete", "--all", "--force", "--json"])
    assert retry.exit_code == 0, retry.output
    assert json.loads(retry.output)["data"]["deleted_sessions"] == [session.name]
    assert (unrelated / "work.txt").exists()


def test_sync_json_reports_deferred_creation_without_false_updates(
    creation_sync, monkeypatch, request
):
    """Unified JSON counts distinguish a protected creation session from an update."""
    from devflow.config.models import WorkspaceDefinition

    loader, _, session, clone, _, ticket = creation_sync
    if ticket["key"].startswith("PROJ-"):
        arguments = ["sync", "--jira", "--json"]
    else:
        config = loader.load_config()
        config.repos.workspaces = [
            WorkspaceDefinition(name="workspace-1", path=str(clone.parent.parent))
        ]
        loader.save_config(config)
        backend = request.node.callspec.params["creation_sync"]
        monkeypatch.setattr(
            "devflow.cli.commands.sync_command.scan_workspace_for_repositories",
            lambda *a: [{
                "repository": "owner/project-a", "backend": backend,
                "path": str(clone), "remote": "origin", "url": None,
            }],
        )
        arguments = ["sync", "--repository", "owner/project-a", "--json"]
    before = loader.sessions_file.read_bytes()
    code = (
        "import sys\n"
        "from devflow.utils.clone_lifecycle import temporary_directory_lock\n"
        f"with temporary_directory_lock({str(clone)!r}):\n"
        "    print('ready', flush=True)\n"
        "    sys.stdin.read()\n"
    )
    with _running_process(Path(__file__).resolve().parents[1], code):
        result = CliRunner().invoke(cli, arguments)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["success"] is True
    assert data["data"]["created_count"] == data["data"]["updated_count"] == 0
    assert data["data"]["deferred_count"] == 1
    assert data["data"]["deferred_sessions"][0]["session"] == session.name
    assert data["data"]["deferred_sessions"][0]["code"] == "SESSION_IN_USE"
    assert loader.sessions_file.read_bytes() == before


@pytest.mark.parametrize("creation_sync", ["jira-legacy"], indirect=True)
def test_conversion_preserves_native_metadata_saved_after_sync_snapshot(creation_sync):
    """An owner finishing between snapshot and lock acquisition cannot lose its ID."""
    from devflow.cli.commands.sync_command import _convert_creation_session

    loader, manager, session, _, _, ticket = creation_sync
    stale = session.model_copy(deep=True)
    session.active_conversation.ai_agent_session_id = "ses_final_capture"
    session.active_conversation.conversation_history.append("ses_final_capture")
    manager.update_session(session)
    before = loader.sessions_file.read_bytes()
    deferred = []
    assert _convert_creation_session(stale, manager, ticket, "jira", deferred) is None
    assert "changed during sync" in deferred[0]["message"]
    assert loader.sessions_file.read_bytes() == before
    latest = SessionManager(loader).get_session(session.name)
    converted = _convert_creation_session(latest, manager, ticket, "jira")
    assert converted.active_conversation.ai_agent_session_id == "ses_final_capture"
    assert converted.conversations == latest.conversations


@pytest.mark.parametrize("creation_sync", ["jira-legacy"], indirect=True)
def test_conversion_keeps_clone_lock_while_persisting(creation_sync, monkeypatch):
    """A successful preflight never releases protection before metadata is saved."""
    from devflow.cli.commands.sync_command import _convert_creation_session

    _, manager, session, clone, _, ticket = creation_sync
    update = manager.update_session

    def guarded_update(current):
        with pytest.raises(TemporaryDirectoryInUseError), temporary_directory_lock(str(clone)):
            pytest.fail("The transition must still hold the clone lock")
        update(current)

    monkeypatch.setattr(manager, "update_session", guarded_update)
    assert _convert_creation_session(session, manager, ticket, "jira").session_type == "development"


@pytest.mark.parametrize("creation_sync", ["jira-unified"], indirect=True)
@pytest.mark.parametrize("status", ["paused", "complete"])
@pytest.mark.parametrize("has_conversation", [False, True])
def test_inactive_conversion_uses_development_branch_setup(
    creation_sync, monkeypatch, status, has_conversation
):
    """Fresh development uses normal setup; existing history keeps its saved branch."""
    from devflow.cli.commands.open_command import open_session

    loader, manager, session, clone, sync, _ = creation_sync
    session.status = status
    if not has_conversation:
        session.conversations = {}
        session.working_directory = None
    manager.update_session(session)
    sync()
    converted = SessionManager(loader).get_session(session.name)
    assert converted.session_type == "development"
    assert converted.workspace_name == "workspace-1"
    prefix = "devflow.cli.commands.open_command."
    monkeypatch.setattr("devflow.cli.utils.select_workspace", lambda *a, **kw: None)
    monkeypatch.setattr(prefix + "_detect_working_directory_from_cwd", lambda *a: None)
    monkeypatch.setattr(prefix + "_copy_conversation_to_temp", Mock())
    monkeypatch.setattr(prefix + "_display_session_summary", Mock())
    monkeypatch.setattr(prefix + "_sync_branch_for_import", Mock())
    monkeypatch.setattr(prefix + "_check_and_sync_with_base_branch", lambda *a, **kw: True)
    monkeypatch.setattr(prefix + "GitUtils.has_merge_conflicts", lambda *a: False)
    monkeypatch.setattr(prefix + "should_launch_claude_code", lambda *a, **kw: False)
    monkeypatch.setattr(
        prefix + "check_concurrent_session",
        lambda *a, **kw: SimpleNamespace(safe_to_proceed=True, clone_path=None),
    )
    checkout = Mock(return_value=True)
    monkeypatch.setattr(prefix + "_handle_branch_checkout", checkout)
    create_branch = Mock(return_value=("feature-a", "origin/trunk"))
    monkeypatch.setattr("devflow.cli.commands.new_command._handle_branch_creation", create_branch)
    agent = Mock()
    agent.get_agent_name.return_value = "OpenCode"
    agent.session_exists.return_value = True
    agent.get_session_model_id.return_value = None
    monkeypatch.setattr("devflow.agent.create_agent_client", lambda *a: agent)

    def select_project(current, config_loader, session_manager, *args, **kwargs):
        current.working_directory = "project-a"
        conv = current.add_conversation(
            working_dir="project-a", project_path=str(clone),
            ai_agent_session_id="pending-capture", branch=None,
        )
        conv.agent_launch_started = False
        session_manager.update_session(current)
        return True

    select = Mock(side_effect=select_project)
    monkeypatch.setattr(prefix + "_prompt_for_working_directory", select)
    open_session(session.name, skip_jira_transition=True)
    saved = SessionManager(loader).get_session(session.name)
    if has_conversation:
        select.assert_not_called()
        create_branch.assert_not_called()
        assert saved.conversations == converted.conversations
        assert checkout.call_args.args[:2] == (str(clone), "creation-source")
    else:
        select.assert_called_once()
        create_branch.assert_called_once()
        assert saved.active_conversation.branch == "feature-a"
        assert saved.active_conversation.base_branch == "origin/trunk"
    assert (loader.get_session_dir(session.name) / "notes.md").exists()


def test_delete_busy_archived_clone_preserves_all_active_clone_contents(clone_session):
    """Preflight every history root before removing even the first inactive clone."""
    loader, manager, session, clone = clone_session
    archived = clone.parent.parent / "daf-session-z" / "project-old"
    archived.mkdir(parents=True)
    (archived / "work.txt").write_text("Preserve archived work")
    session.conversations["project-a"].archived_sessions.append(
        ConversationContext(
            ai_agent_session_id="ses_archived", project_path=str(archived),
            temp_directory=str(archived), archived=True,
        )
    )
    manager.update_session(session)
    before = loader.sessions_file.read_bytes()
    with _running_process(archived):
        result = CliRunner().invoke(cli, ["delete", session.name, "--force", "--json"])
    assert result.exit_code == 1, result.output
    data = json.loads(result.output)
    assert data["error"]["code"] == "SESSION_IN_USE"
    assert data["error"]["removed_clones"] == []
    assert loader.sessions_file.read_bytes() == before
    assert (clone / "work.txt").exists()
    assert (archived / "work.txt").read_text() == "Preserve archived work"


def test_delete_cleanup_failure_keeps_metadata_and_reports_actual_reason(
    clone_session, monkeypatch
):
    """A non-removal must not be reported as a successful session deletion."""
    loader, _, session, clone = clone_session
    before = loader.sessions_file.read_bytes()
    monkeypatch.setattr("devflow.cli.commands.delete_command.cleanup_temp_directory", Mock())
    result = CliRunner().invoke(cli, ["delete", session.name, "--force", "--json"])
    assert result.exit_code == 1, result.output
    data = json.loads(result.output)
    assert data["error"]["code"] == "CLONE_CLEANUP_FAILED"
    assert data["data"]["deleted_count"] == 0
    assert loader.sessions_file.read_bytes() == before
    assert clone.exists()
