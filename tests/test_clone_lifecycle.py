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
from devflow.config.models import Config, JiraConfig, RepoConfig, WorkSession
from devflow.session.manager import SessionManager
from devflow.utils.clone_lifecycle import (
    TemporaryDirectoryInUseError,
    assert_temp_directory_unused,
    get_temp_directory_root,
    temporary_directory_lock,
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

    loader, manager, session, clone = clone_session
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


@pytest.mark.parametrize("session_id", ["ses_existing", "pending-capture", "pending-session"])
@pytest.mark.parametrize("failure_phase", [None, "spawn", "wait"])
def test_open_resume_protects_clone_until_exit_and_releases_on_errors(
    clone_session, monkeypatch, session_id, failure_phase
):
    """Native resume, fresh reopen, and resume fallback protect the clone before spawning."""
    _, manager, session, clone = clone_session
    session.active_conversation.ai_agent_session_id = session_id
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
    elif session_id == "pending-capture":
        agent.launch_with_prompt.assert_called_once()
    else:
        agent.launch_session.assert_called_once()
    if failure_phase != "spawn":
        agent.wait_for_exit.assert_called_once()
    if failure_phase is None:
        prompt.assert_called_once()
    with temporary_directory_lock(str(clone)):
        pass
    assert clone.exists()
