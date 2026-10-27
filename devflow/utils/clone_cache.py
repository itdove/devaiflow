"""Conservative retention for verified, reproducible DAF clone-cache entries.

Ownership, activity, process leases and eviction tombstones live in DAF state,
not in session/agent storage. A matching in-directory nonce prevents a replaced
or unrelated directory from becoming an eviction candidate. Locks are shared
with agent startup and explicit cleanup; process leases protect the interval
between allocation/reopen and the agent's lifetime lock.
"""

import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from contextlib import nullcontext
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

import psutil
from pydantic import BaseModel, Field, ValidationError

from devflow.cli.utils import console_print
from devflow.config.models import CloneRetentionConfig, Config
from devflow.utils.clone_lifecycle import (
    TemporaryDirectoryInUseError,
    assert_temp_directory_unused,
    clone_cache_record_path,
    get_temp_directory_root,
    temporary_directory_lock,
)

MARKER = ".daf-managed-clone"


class _Repository(BaseModel):
    remote_url: str | None = None
    branch: str | None = None
    local_files: dict[str, str] | None = None


class _Entry(BaseModel):
    version: Literal[1] = 1
    root: str
    base: str
    token: str
    repositories: dict[str, _Repository]
    last_used: float = Field(allow_inf_nan=False, ge=0)
    leases: dict[str, float] = Field(default_factory=dict)
    evicted_at: float | None = Field(default=None, allow_inf_nan=False, ge=0)
    restore_pending: bool = False


def _write(path: Path, text: str) -> None:
    """Atomically publish state without exposing partially written records."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _git(repo: Path, *args: str) -> str:
    """Run a bounded, non-interactive Git check; errors always protect the clone."""
    result = subprocess.run(
        ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"},
    )
    return result.stdout.strip()


def _local_files(repo: Path) -> dict[str, str]:
    """Fingerprint non-reproducible metadata established by the initial clone."""
    result = {}
    git_dir = repo / ".git"
    for item in (git_dir / "description", git_dir / "hooks", git_dir / "info"):
        paths = item.rglob("*") if item.is_dir() else [item]
        for path in paths:
            if path.is_symlink():
                raise OSError("Symlink in Git metadata")
            if path.is_file():
                result[str(path.relative_to(git_dir))] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
    return result


def _reproducible(repo: Path, baseline: _Repository) -> bool:
    """Prove all work and Git objects can be recovered from the recorded origin.

    Remote-tracking refs alone are not proof: confirm current advertised refs.
    Offline/auth failures, ignored files, stashes, dangling/reflog-only objects,
    local tags/config/hooks, worktrees, submodules and unknown metadata pin entries.
    """
    git_dir = repo / ".git"
    if git_dir.is_symlink() or not git_dir.is_dir() or baseline.local_files is None:
        return False
    allowed = {
        "HEAD",
        "config",
        "description",
        "hooks",
        "info",
        "objects",
        "refs",
        "logs",
        "index",
        "packed-refs",
        "FETCH_HEAD",
        "ORIG_HEAD",
        "COMMIT_EDITMSG",
    }
    if any(child.name not in allowed for child in git_dir.iterdir()):
        return False
    if any(path.is_symlink() for path in git_dir.rglob("*")):
        return False
    if (git_dir / "objects" / "info" / "alternates").exists():
        return False
    if (git_dir / "objects" / "info" / "http-alternates").exists():
        return False
    object_layout = re.compile(
        r"(?:[0-9a-f]{2}/[0-9a-f]{38}|pack/pack-[0-9a-f]{40}\.(?:pack|idx|rev|bitmap)"
        r"|info/(?:packs|commit-graph|commit-graphs/(?:commit-graph-chain|graph-[0-9a-f]{40}\.graph)))"
    )
    for path in (git_dir / "objects").rglob("*"):
        if path.is_file() and not object_layout.fullmatch(
            path.relative_to(git_dir / "objects").as_posix()
        ):
            return False  # Git fsck can ignore arbitrary non-object files here.
    if _local_files(repo) != baseline.local_files:
        return False
    # A custom init template may have installed local-only metadata on day one.
    # A clone-time fingerprint does not make active hooks or excludes reproducible.
    if any(
        path.is_file() and not path.name.endswith(".sample")
        for path in (git_dir / "hooks").rglob("*")
    ):
        return False
    exclude = git_dir / "info" / "exclude"
    if exclude.exists() and any(
        line.strip() and not line.lstrip().startswith("#")
        for line in exclude.read_text().splitlines()
    ):
        return False
    if any(path.is_file() and path.name != "exclude" for path in (git_dir / "info").rglob("*")):
        return False
    description = git_dir / "description"
    if description.exists() and description.read_text().strip() != (
        "Unnamed repository; edit this file 'description' to name the repository."
    ):
        return False
    if _git(repo, "rev-parse", "--show-toplevel") != str(repo):
        return False
    if _git(repo, "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching"):
        return False
    # Additional local configuration is not recreated by git clone.
    keys = _git(repo, "config", "--local", "--name-only", "--list").splitlines()
    if len(keys) != len(set(keys)):
        return False
    for key in keys:
        if key in {
            "core.repositoryformatversion",
            "core.filemode",
            "core.bare",
            "core.logallrefupdates",
            "core.ignorecase",
            "core.precomposeunicode",
            "remote.origin.url",
            "remote.origin.fetch",
        }:
            continue
        if (
            key.startswith("branch.")
            and key.endswith(".remote")
            and _git(repo, "config", "--get", key) == "origin"
        ):
            continue
        if (
            key.startswith("branch.")
            and key.endswith(".merge")
            and _git(repo, "config", "--get", key) == f"refs/heads/{key[7:-6]}"
        ):
            continue
        return False
    remote = _git(repo, "config", "--get", "remote.origin.url")
    if not remote or remote != baseline.remote_url:
        return False
    parsed = urlparse(remote)
    local_remote = None
    if parsed.scheme == "file" and parsed.netloc in {"", "localhost"}:
        local_remote = Path(unquote(parsed.path))
    elif Path(remote).is_absolute() or ":" not in remote:
        local_remote = Path(remote).expanduser()
    if local_remote is not None:
        resolved = (repo / local_remote).resolve()
        if resolved == repo.parent or repo.parent in resolved.parents:
            return False  # Two repositories in this removal root cannot back each other up.
    if (
        _git(repo, "config", "--get", "remote.origin.fetch")
        != "+refs/heads/*:refs/remotes/origin/*"
    ):
        return False
    advertised = {
        ref: oid
        for oid, ref in (
            line.split() for line in _git(repo, "ls-remote", "--refs", "origin").splitlines()
        )
    }
    remote_ids = set(advertised.values())
    recoverable = set()
    allowed_logs = {"HEAD"}
    for line in _git(repo, "for-each-ref", "--format=%(refname) %(objectname)").splitlines():
        ref, oid = line.split()
        allowed_logs.add(ref)
        if ref.startswith(("refs/heads/", "refs/tags/")):
            if advertised.get(ref) != oid:
                return False
        elif not ref.startswith("refs/remotes/origin/"):
            return False
        if oid in remote_ids:
            recoverable.add(oid)
    for path in (git_dir / "logs").rglob("*"):
        if path.is_file() and path.relative_to(git_dir / "logs").as_posix() not in allowed_logs:
            return False
    if not recoverable:
        return False
    if _git(
        repo, "rev-list", "--objects", "--all", "--reflog", "HEAD", "--not", *sorted(recoverable)
    ):
        return False
    # Includes unreachable loose objects not named by branches, tags or reflogs.
    return not _git(repo, "fsck", "--full", "--unreachable", "--no-progress")


def _size(path: Path) -> int:
    """Count apparent bytes, including .git, without following any symlinks."""
    size = path.lstat().st_size
    if path.is_symlink() or not path.is_dir():
        return size
    with os.scandir(path) as children:
        return size + sum(_size(Path(child.path)) for child in children)


def _live_leases(entry: _Entry) -> dict[str, float]:
    """Discard stale/reused PIDs while conservatively retaining uninspectable leases."""
    live = {}
    for pid, started in entry.leases.items():
        try:
            process = psutil.Process(int(pid))
            if process.is_running() and process.create_time() == started:
                live[pid] = started
        except (psutil.NoSuchProcess, psutil.ZombieProcess, ValueError):
            continue
        except psutil.AccessDenied:
            live[pid] = started
    return live


class CloneCache:
    """Apply one policy to allocation, reopen, recovery and post-clone accounting."""

    def __init__(self, config: Config | None = None) -> None:
        from devflow.utils.temp_directory import get_clone_base_dir

        self.base = get_clone_base_dir(config).resolve()
        policy = getattr(config, "clone_retention", None)
        self.policy = policy if isinstance(policy, CloneRetentionConfig) else CloneRetentionConfig()

    def _root(self, path: Path) -> Path | None:
        # Do not resolve a symlinked entry into another (potentially managed) entry.
        path = Path(os.path.abspath(path.expanduser()))
        root = (
            path.parent
            if path.parent.parent == self.base and path.parent.name.startswith("daf-session-")
            else path
        )
        if root.parent != self.base or not root.name.startswith(
            ("daf-session-", "daf-investigation-")
        ):
            return None
        if root.is_symlink() or path.is_symlink():
            return None
        return root

    def _read(self, root: Path, *, other_base: bool = False) -> _Entry | None:
        try:
            state_path = clone_cache_record_path(root)
            if state_path.is_symlink():
                return None
            entry = _Entry.model_validate_json(state_path.read_text())
            if entry.root != str(root) or entry.base != str(root.parent):
                return None
            if not other_base and entry.base != str(self.base):
                return None
            if any(
                name in {"", ".", ".."} or Path(name).name != name for name in entry.repositories
            ):
                return None
            if not math.isfinite(entry.last_used):
                return None
            if any(
                not pid.isdigit() or int(pid) <= 0 or not math.isfinite(started)
                for pid, started in entry.leases.items()
            ):
                return None
            return entry
        except (OSError, ValueError, ValidationError):
            return None

    def _recorded_root(self, path: Path) -> Path | None:
        """Keep recovery/activity working if clone_dir was changed after allocation."""
        root = path.parent if path.parent.name.startswith("daf-session-") else path
        if (
            not root.name.startswith(("daf-session-", "daf-investigation-"))
            or root.is_symlink()
            or path.is_symlink()
            or root != root.resolve()
        ):
            return None
        return root if self._read(root, other_base=True) else None

    def lock_path(self, path: Path) -> str:
        """Resolve the same enclosing lock before initial registration and after eviction."""
        path = Path(os.path.abspath(path.expanduser()))
        return str(
            self._root(path) or self._recorded_root(path) or get_temp_directory_root(str(path))
        )

    def use(
        self,
        path: Path,
        *,
        created: bool = False,
        remote_url: str | None = None,
        locked: bool = False,
    ) -> None:
        """Refresh actual activity and lease an entry through this CLI process's lifetime.

        Legacy session clones may be registered on reopen, but without an initial
        metadata baseline they remain protected from automatic eviction.
        ``locked`` is for callers already holding the matching lifecycle lock.
        """
        path = Path(os.path.abspath(path.expanduser()))
        root = self._root(path) or self._recorded_root(path)
        if root is None or not root.is_dir():
            return
        with nullcontext() if locked else temporary_directory_lock(str(root)):
            entry = self._read(root, other_base=True)
            marker = root / MARKER
            if entry is None:
                if marker.exists():
                    return  # Lost/corrupt ownership state: never adopt a replacement.
                entry = _Entry(
                    root=str(root),
                    base=str(self.base),
                    token=uuid.uuid4().hex,
                    repositories={},
                    last_used=time.time(),
                )
                _write(marker, entry.token)
            elif (
                not marker.exists()
                and (entry.evicted_at is not None or entry.restore_pending)
                and created
            ):
                _write(marker, entry.token)
            elif not marker.is_file() or marker.is_symlink() or marker.read_text() != entry.token:
                return
            if path != root:
                previous = entry.repositories.get(path.name, _Repository(remote_url=remote_url))
                if (path / ".git").is_dir():
                    try:
                        previous.remote_url = _git(path, "config", "--get", "remote.origin.url")
                        previous.branch = None
                        previous.branch = _git(path, "symbolic-ref", "--short", "HEAD")
                        if created:
                            previous.local_files = _local_files(path)
                    except (OSError, subprocess.SubprocessError):
                        pass  # Unknown Git state cannot become an eviction candidate.
                entry.repositories[path.name] = previous
            entry.leases = _live_leases(entry)
            entry.leases[str(os.getpid())] = psutil.Process().create_time()
            entry.last_used = time.time()
            entry.evicted_at = None
            entry.restore_pending = False
            _write(clone_cache_record_path(root), entry.model_dump_json())

    def begin_restore(self, path: Path, remote_url: str, branch: str | None) -> None:
        """Record an incomplete attempt under the caller's lifecycle lock, before Git runs."""
        root = self._root(path) or self._recorded_root(path)
        if root is None:
            return
        entry = self._read(root, other_base=True) or _Entry(
            root=str(root),
            base=str(root.parent),
            token=uuid.uuid4().hex,
            repositories={},
            last_used=time.time(),
        )
        repo = entry.repositories.setdefault(path.name, _Repository())
        repo.remote_url = remote_url
        repo.branch = branch
        entry.restore_pending = True
        entry.leases = _live_leases(entry)
        entry.leases[str(os.getpid())] = psutil.Process().create_time()
        _write(clone_cache_record_path(root), entry.model_dump_json())

    def pending_recovery(self, path: Path) -> bool:
        """Detect a partial clone/failed checkout instead of launching its default branch."""
        root = self._root(path) or self._recorded_root(path)
        entry = self._read(root, other_base=True) if root else None
        return bool(entry and entry.restore_pending)

    def recovery(self, path: Path) -> tuple[str | None, str | None, bool]:
        """Return saved origin, branch and known-retention cause without altering identity."""
        path = Path(os.path.abspath(path.expanduser()))
        root = self._root(path) or self._recorded_root(path)
        entry = self._read(root, other_base=True) if root else None
        if not entry:
            return None, None, False
        repo = entry.repositories.get(path.name, _Repository())
        return repo.remote_url, repo.branch, entry.evicted_at is not None

    def _evict(self, root: Path, *, now: float, size_pressure: bool) -> bool:
        with temporary_directory_lock(str(root)):
            entry = self._read(root)
            if entry is None or entry.restore_pending or _live_leases(entry):
                return False
            expired = (
                self.policy.max_idle_days
                and now - entry.last_used >= self.policy.max_idle_days * 86400
            )
            if not expired and not size_pressure:
                return False  # Activity may have refreshed since candidate discovery.
            marker = root / MARKER
            if self._root(root) != root or marker.is_symlink() or marker.read_text() != entry.token:
                return False
            expected = {MARKER, *entry.repositories}
            if {child.name for child in root.iterdir()} != expected:
                return False
            assert_temp_directory_unused(str(root))
            for name, repo in entry.repositories.items():
                project = root / name
                if project.is_symlink() or not _reproducible(project, repo):
                    return False
                repo.branch = _git(project, "symbolic-ref", "--short", "HEAD")
            # Tombstone first: failures preserve recovery information even if removal is partial.
            entry.evicted_at = now
            _write(clone_cache_record_path(root), entry.model_dump_json())
            assert_temp_directory_unused(str(root))
            shutil.rmtree(root)
            console_print(f"[dim]Clone cache retention removed: {root}[/dim]")
            return True

    def prune(self) -> None:
        """Expire idle entries, then remove reproducible LRU entries until within budget."""
        if not self.base.is_dir() or not (self.policy.max_idle_days or self.policy.max_size_mb):
            return
        try:
            with temporary_directory_lock(
                str(clone_cache_record_path(self.base).with_suffix(".maintenance"))
            ):
                now = time.time()
                total = 0
                unknown_size = False
                candidates = []
                for root in sorted(self.base.iterdir()):
                    try:
                        size = _size(root)
                        total += size
                        entry = self._read(root) if self._root(root) == root else None
                        if entry and root.is_dir() and not root.is_symlink():
                            candidates.append((entry.last_used, root.name, root, size))
                    except OSError:
                        unknown_size = True
                budget = self.policy.max_size_mb * 1024 * 1024
                for _, _, root, size in sorted(candidates):
                    over = bool(budget and total > budget)
                    try:
                        if self._evict(root, now=now, size_pressure=over):
                            total -= size
                    except (
                        OSError,
                        subprocess.SubprocessError,
                        TemporaryDirectoryInUseError,
                        ValueError,
                    ):
                        continue  # Permission errors, races and uncertain reproducibility pin clones.
                if unknown_size or (budget and total > budget):
                    console_print(
                        "[yellow]⚠[/yellow] Clone cache cannot meet its size budget: live, local-only, "
                        "unknown or inaccessible data is protected. Push/back up local work, exit agents, "
                        "then delete unneeded sessions explicitly, or increase clone_retention.max_size_mb."
                    )
        except (OSError, TemporaryDirectoryInUseError) as error:
            console_print(f"[yellow]⚠[/yellow] Clone cache retention deferred: {error}")
