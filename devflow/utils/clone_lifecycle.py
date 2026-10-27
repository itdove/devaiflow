"""Coordinate agent startup and safe temporary-clone removal across processes."""

import hashlib
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psutil

from devflow.utils.paths import get_cs_cache_home, get_cs_state_home

if TYPE_CHECKING:
    from devflow.config.models import Session


class TemporaryDirectoryInUseError(RuntimeError):
    """A temporary directory is in use or cannot safely be checked."""

    def __init__(self, message: str, *, holder: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.holder = holder


def _directory_holder(process: psutil.Process, cwd: str) -> dict[str, Any]:
    """Describe a known holder without reading command arguments or credentials.

    A process may exit or become inaccessible between any two attribute reads.
    Keep the verified PID/cwd even when supplemental ownership details disappear.
    """
    holder: dict[str, Any] = {
        "pid": process.pid,
        "name": None,
        "cwd": cwd,
        "parent_pid": None,
        "parent_name": None,
        "parent_cwd": None,
    }
    for key, getter in (("name", process.name), ("parent_pid", process.ppid)):
        try:
            holder[key] = getter()
        except (psutil.Error, OSError):
            pass
    try:
        parent = process.parent()
    except (psutil.Error, OSError):
        parent = None
    if parent is not None:
        for key, getter in (("parent_name", parent.name), ("parent_cwd", parent.cwd)):
            try:
                holder[key] = getter()
            except (psutil.Error, OSError):
                pass
    return holder


def assert_session_clones_unused(session: "Session") -> None:
    """Preflight every conversation before offering or performing completion.

    This is not permission to delete later: removal must recheck under its lock.
    """
    for conversation in session.conversations.values():
        temp_directory = conversation.active_session.temp_directory
        if temp_directory:
            with temporary_directory_lock(temp_directory):
                assert_temp_directory_unused(temp_directory)


def completion_refusal_message(session_name: str, error: TemporaryDirectoryInUseError) -> str:
    """Explain live holders, including resources outliving a backend's UI."""
    return (
        f"Cannot complete session '{session_name}': {error}.\n"
        "Exit active AI agents and move terminals out of the clone.\n"
        "UI exit does not prove that backend workspace services exited.\n"
        "OpenCode v2's shared server can retain MCP processes.\n"
        "Check the reported parent/owner and other clients of this workspace before "
        "releasing its resources through supported backend lifecycle controls.\n"
        "DAF will not stop shared services or assume exclusive ownership.\n"
        f"Retry from outside the clone:\n  daf complete {session_name}\n"
        "Session status and time tracking were not changed.\n"
        "See docs/guides/troubleshooting.md#temporary-clone-still-in-use-after-agent-exit."
    )


def clone_cache_record_path(root: Path) -> Path:
    """Locate persistent ownership/recovery data outside a removable clone."""
    key = hashlib.sha256(os.path.normcase(str(root)).encode()).hexdigest()
    return get_cs_state_home() / "clone-cache" / f"{key}.json"


def get_temp_directory_root(temp_dir: str) -> Path:
    """Return the directory that cleanup will remove, including a nested clone's parent."""
    path = Path(temp_dir).expanduser().resolve()
    parent = path.parent
    if parent.name.startswith("daf-session-") and (
        parent.parent
        in (
            Path(tempfile.gettempdir()).resolve(),
            (get_cs_cache_home() / "clones").resolve(),
        )
        or clone_cache_record_path(parent).is_file()
    ):
        return parent
    return path


@contextmanager
def temporary_directory_lock(temp_dir: str | None) -> Iterator[None]:
    """Exclude clone startup and removal using a stable, cross-process lock.

    Lock files live in the user's DAF state directory, outside the removal root,
    and must not be unlinked: replacing one would let another process lock a
    different inode for the same clone. Per-user storage also avoids ownership
    conflicts when legacy clones live directly under a shared system temp dir.
    No session ID, session status, or time-tracking state is needed.
    """
    if not temp_dir:
        yield
        return

    root = get_temp_directory_root(temp_dir)
    key = hashlib.sha256(os.path.normcase(str(root)).encode()).hexdigest()
    try:
        lock_dir = get_cs_state_home() / "clone-locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_file = (lock_dir / f"{key}.lock").open("a+b")
    except OSError as error:
        raise TemporaryDirectoryInUseError(
            f"Cannot lock temporary directory {root}: {error}"
        ) from error

    with lock_file:
        try:
            if sys.platform == "win32":
                import msvcrt

                lock_file.seek(0, 2)
                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise TemporaryDirectoryInUseError(
                f"Temporary directory {root} is busy with agent startup or cleanup"
            ) from error

        try:
            yield
        finally:
            if sys.platform == "win32":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def assert_temp_directory_unused(temp_dir: str) -> None:
    """Refuse removal if a process uses the removal root or any descendant.

    Inspect actual working directories, including agents orphaned by an exited
    launcher and sessions whose native ID is still pending capture. Call while
    holding ``temporary_directory_lock`` to exclude concurrent managed startup.
    Terminals inside the clone also count as users of the directory.
    """
    root = get_temp_directory_root(temp_dir)
    if not root.exists():
        return

    try:
        for process in psutil.process_iter():
            try:
                cwd = process.cwd()
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            except psutil.AccessDenied:
                # Protected system processes can be inaccessible even for the
                # same user. Managed agents also hold the directory lock for
                # their lifetime, independently of process-inspection access.
                continue

            if cwd:
                process_path = Path(cwd).resolve()
                if process_path == root or root in process_path.parents:
                    holder = _directory_holder(process, cwd)
                    parent_pid = holder["parent_pid"]
                    raise TemporaryDirectoryInUseError(
                        f"Temporary directory {root} is in use by process {process.pid} "
                        f"({holder['name'] or 'name unavailable'}), cwd: {cwd}; "
                        f"parent PID: {parent_pid if parent_pid is not None else 'unavailable'}, "
                        f"name: {holder['parent_name'] or 'unavailable'}, "
                        f"cwd: {holder['parent_cwd'] or 'unavailable'}",
                        holder=holder,
                    )
    except (psutil.Error, OSError) as error:
        raise TemporaryDirectoryInUseError(
            f"Cannot verify whether temporary directory {root} is unused: {error}"
        ) from error
