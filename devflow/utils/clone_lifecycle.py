"""Coordinate agent startup and safe temporary-clone removal across processes."""

import hashlib
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psutil

from devflow.utils.paths import get_cs_cache_home, get_cs_state_home


class TemporaryDirectoryInUseError(RuntimeError):
    """A temporary directory is in use or cannot safely be checked."""


def clone_cache_record_path(root: Path) -> Path:
    """Locate persistent ownership/recovery data outside a removable clone."""
    key = hashlib.sha256(os.path.normcase(str(root)).encode()).hexdigest()
    return get_cs_state_home() / "clone-cache" / f"{key}.json"


def get_temp_directory_root(temp_dir: str) -> Path:
    """Return the directory that cleanup will remove, including a nested clone's parent."""
    path = Path(temp_dir).expanduser().resolve()
    parent = path.parent
    if parent.name.startswith("daf-session-") and (
        parent.parent in (
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
                    raise TemporaryDirectoryInUseError(
                        f"Temporary directory {root} is in use by process {process.pid}"
                    )
    except (psutil.Error, OSError) as error:
        raise TemporaryDirectoryInUseError(
            f"Cannot verify whether temporary directory {root} is unused: {error}"
        ) from error
