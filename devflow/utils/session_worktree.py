"""Create, recover, and safely remove per-session Git worktrees."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from devflow.config.models import Config
from devflow.git.utils import GitUtils
from devflow.utils.clone_lifecycle import (
    assert_temp_directory_unused,
    temporary_directory_lock,
)


class SessionWorktreeError(RuntimeError):
    """A session worktree could not be created or safely recovered."""


class SessionWorktreeCleanupError(SessionWorktreeError):
    """A worktree could not be removed without risking local work."""


def _run_git(
    path: Path,
    *args: str,
    timeout: int = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a credential-safe Git command in a repository."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise SessionWorktreeError(
            "Git worktree operation could not be completed"
        ) from error
    if check and result.returncode != 0:
        raise SessionWorktreeError(
            "Git worktree operation failed; verify the repository and branch"
        )
    return result


def _common_git_dir(path: Path) -> Path:
    """Resolve the shared Git directory for a main checkout or linked worktree."""
    result = _run_git(path, "rev-parse", "--git-common-dir")
    common = Path(result.stdout.strip())
    return (path / common).resolve() if not common.is_absolute() else common.resolve()


def worktree_source_fingerprint(source_path: Path) -> str:
    """Identify a source repository without storing its remote URL in metadata."""
    source = source_path.expanduser().resolve()
    if not source.is_dir() or not GitUtils.is_git_repository(source):
        raise SessionWorktreeError("The selected source path is not a Git repository")
    remotes = _run_git(
        source,
        "config",
        "--get-regexp",
        r"^remote\..*\.url$",
        check=False,
    ).stdout.splitlines()
    roots = _run_git(
        source,
        "rev-list",
        "--max-parents=0",
        "--all",
        timeout=60,
    ).stdout.splitlines()
    object_format = _run_git(source, "rev-parse", "--show-object-format").stdout.strip()
    payload = json.dumps(
        {
            "common_git_dir": str(_common_git_dir(source)),
            "object_format": object_format,
            "remote_urls": sorted(remotes),
            "root_commits": sorted(roots),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _managed_worktree_root(worktree_path: Path, config: Config | None = None) -> Path:
    """Require an exact worktree child in managed clone storage."""
    from devflow.utils.clone_cache import CloneCache, clone_cache_record_path

    path = Path(os.path.abspath(worktree_path.expanduser()))
    if path != path.resolve(strict=False):
        raise SessionWorktreeError(
            "The recorded worktree path is redirected by a symlink"
        )
    root = path.parent
    if not root.name.startswith("daf-session-") or path == root:
        raise SessionWorktreeError(
            "The recorded worktree is outside managed session storage"
        )
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise SessionWorktreeError("The recorded managed worktree directory is invalid")

    cache = CloneCache(config)
    record = clone_cache_record_path(root)
    if record.is_symlink() or (root.parent != cache.base and not record.is_file()):
        raise SessionWorktreeError(
            "The recorded worktree is outside managed clone storage"
        )
    return root


def _worktree_records(source_path: Path) -> dict[Path, str | None]:
    """Return canonical worktree paths and their attached branch names."""
    output = _run_git(source_path, "worktree", "list", "--porcelain").stdout
    records: dict[Path, str | None] = {}
    current_path: Path | None = None
    for line in output.splitlines() + [""]:
        if line.startswith("worktree "):
            current_path = Path(line[len("worktree ") :]).resolve()
            records[current_path] = None
        elif line.startswith("branch refs/heads/") and current_path is not None:
            records[current_path] = line[len("branch refs/heads/") :]
        elif not line:
            current_path = None
    return records


def _reference_exists(source_path: Path, branch: str) -> bool:
    result = _run_git(
        source_path,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/heads/{branch}",
        check=False,
    )
    if result.returncode == 0:
        return True
    remote = _run_git(
        source_path,
        "for-each-ref",
        "--format=%(refname)",
        "refs/remotes",
        check=False,
    )
    return any(line.endswith(f"/{branch}") for line in remote.stdout.splitlines())


def _valid_branch(source_path: Path, branch: str) -> bool:
    if not branch or branch.startswith("-"):
        return False
    return (
        _run_git(
            source_path,
            "check-ref-format",
            "--branch",
            branch,
            check=False,
        ).returncode
        == 0
    )


def _unique_worktree_branch(source_path: Path, branch: str, session_name: str) -> str:
    """Create a readable branch name that cannot collide with an existing ref."""
    session_slug = (
        re.sub(r"[^A-Za-z0-9._-]+", "-", session_name).strip("-._").lower()[:60]
    )
    suffix = f"-wt-{session_slug or 'session'}"
    stem = f"{branch[: 240 - len(suffix)]}{suffix}"
    candidate = stem
    number = 2
    while _reference_exists(source_path, candidate):
        numbered = f"-{number}"
        candidate = f"{stem[: 240 - len(numbered)]}{numbered}"
        number += 1
    return candidate


def _available_session_branch(source_path: Path, branch: str, session_name: str) -> str:
    """Use the proposed session branch unless it already exists."""
    if _valid_branch(source_path, branch) and not _reference_exists(
        source_path, branch
    ):
        return branch
    return _unique_worktree_branch(source_path, branch, session_name)


def _allocate_worktree_directory(
    source_path: Path, config: Config | None
) -> tuple[Path, Path]:
    from devflow.utils.temp_directory import extract_repo_name, get_clone_base_dir

    base = get_clone_base_dir(config)
    base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="daf-session-", dir=str(base)))
    remote = GitUtils.get_remote_url(source_path) or ""
    repo_name = extract_repo_name(remote) if remote else source_path.name
    if not repo_name or repo_name in {".", ".."}:
        repo_name = "repo"
    return root, root / repo_name


def create_session_worktree(
    source_path: Path,
    *,
    session_name: str,
    branch: str | None,
    base_branch: str | None,
    branch_prefix: str,
    config: Config | None = None,
) -> tuple[Path, str, str]:
    """Create an isolated worktree under the configured managed clone storage.

    If the saved branch is already checked out in another worktree, create a
    session-specific branch from that branch instead. The original checkout's
    HEAD and files are never switched or modified.
    """
    source = source_path.expanduser().resolve()
    if not source.is_dir() or not GitUtils.is_git_repository(source):
        raise SessionWorktreeError("The selected project path is not a Git repository")

    from devflow.utils.clone_cache import CloneCache

    cache = CloneCache(config)
    root: Path | None = None
    target: Path | None = None
    try:
        with temporary_directory_lock(cache.lock_path(source)):
            # Prevent retention from evicting a managed source checkout while
            # this worktree is being allocated.
            cache.use(source, locked=True)
            root, target = _allocate_worktree_directory(source, config)
            with temporary_directory_lock(cache.lock_path(target)):
                requested_branch = branch
                actual_base_branch = (
                    base_branch or GitUtils.get_default_branch(source) or "main"
                )
                if requested_branch:
                    if not _valid_branch(source, requested_branch):
                        raise SessionWorktreeError(
                            "The saved session branch is not a valid Git branch"
                        )
                    attached = requested_branch in _worktree_records(source).values()
                    actual_branch = (
                        _unique_worktree_branch(source, requested_branch, session_name)
                        if attached
                        else requested_branch
                    )
                    if actual_branch == requested_branch:
                        _run_git(
                            source,
                            "worktree",
                            "add",
                            str(target),
                            actual_branch,
                            timeout=120,
                        )
                    else:
                        _run_git(
                            source,
                            "worktree",
                            "add",
                            "-b",
                            actual_branch,
                            str(target),
                            requested_branch,
                            timeout=120,
                        )
                else:
                    default_branch = GitUtils.get_default_branch(source)
                    source_branch = base_branch
                    if not source_branch or (
                        source_branch == "main"
                        and default_branch
                        and default_branch != "main"
                    ):
                        source_branch = default_branch
                    if (
                        not source_branch
                        or not _valid_branch(source, source_branch)
                        or _run_git(
                            source,
                            "rev-parse",
                            "--verify",
                            "--quiet",
                            f"{source_branch}^{{commit}}",
                            check=False,
                        ).returncode
                        != 0
                    ):
                        source_branch = default_branch
                    if (
                        not source_branch
                        or not _valid_branch(source, source_branch)
                        or _run_git(
                            source,
                            "rev-parse",
                            "--verify",
                            "--quiet",
                            f"{source_branch}^{{commit}}",
                            check=False,
                        ).returncode
                        != 0
                    ):
                        raise SessionWorktreeError(
                            "Could not determine a valid base branch for the worktree"
                        )
                    actual_base_branch = source_branch
                    actual_branch = _available_session_branch(
                        source, branch_prefix, session_name
                    )
                    _run_git(
                        source,
                        "worktree",
                        "add",
                        "-b",
                        actual_branch,
                        str(target),
                        source_branch,
                        timeout=120,
                    )

                _verify_worktree(source, target, actual_branch)
                cache.use(
                    target,
                    created=True,
                    remote_url=GitUtils.get_remote_url(source),
                    locked=True,
                )
        # Prune only after releasing the source lock: retention takes its
        # maintenance lock before candidate locks, so reversing that order can
        # deadlock against another cache-prune process.
        cache.prune(exclude_paths={source})
        return target, actual_branch, actual_base_branch
    except Exception:
        # Remove only an empty, unregistered allocation. If Git began creating
        # a worktree, preserve it for inspection/recovery rather than guessing.
        if (
            target
            and target.is_dir()
            and not target.is_symlink()
            and not any(target.iterdir())
        ):
            try:
                registered = target.resolve() in _worktree_records(source)
            except SessionWorktreeError:
                registered = True
            if not registered:
                target.rmdir()
        if root and root.is_dir() and not root.is_symlink() and not any(root.iterdir()):
            root.rmdir()
        raise


def _verify_worktree(
    source_path: Path, worktree_path: Path, branch: str | None
) -> None:
    """Fail closed unless the exact path is a linked worktree of the source repo."""
    if not worktree_path.is_dir() or worktree_path.is_symlink():
        raise SessionWorktreeError(
            "The recorded worktree path is missing or redirected"
        )
    if not (worktree_path / ".git").is_file():
        raise SessionWorktreeError("The recorded path is not a linked Git worktree")
    top_level = Path(
        _run_git(worktree_path, "rev-parse", "--show-toplevel").stdout.strip()
    ).resolve()
    if top_level != worktree_path.resolve():
        raise SessionWorktreeError(
            "The recorded worktree resolves to a different project path"
        )
    if _common_git_dir(source_path) != _common_git_dir(worktree_path):
        raise SessionWorktreeError(
            "The worktree belongs to a different source repository"
        )
    if branch and GitUtils.get_current_branch(worktree_path) != branch:
        raise SessionWorktreeError("The worktree is not on the saved session branch")
    records = _worktree_records(source_path)
    if records.get(worktree_path.resolve()) != branch:
        raise SessionWorktreeError(
            "Git does not register the saved worktree and branch"
        )


def restore_session_worktree(
    source_path: Path,
    worktree_path: Path,
    branch: str | None,
    *,
    config: Config | None = None,
    expected_source_fingerprint: str | None = None,
) -> bool:
    """Validate or restore a session worktree at its recorded absolute path."""
    from devflow.utils.clone_cache import CloneCache

    source = source_path.expanduser().resolve()
    recorded = worktree_path.expanduser()
    root = _managed_worktree_root(recorded, config)
    if not branch or not source.is_dir() or not GitUtils.is_git_repository(source):
        raise SessionWorktreeError(
            "Saved source repository or session branch is unavailable"
        )
    actual_fingerprint = worktree_source_fingerprint(source)
    if (
        expected_source_fingerprint
        and actual_fingerprint != expected_source_fingerprint
    ):
        raise SessionWorktreeError(
            "The source repository no longer matches the repository recorded for this worktree"
        )
    if Path(os.path.abspath(recorded)) != recorded.resolve(strict=False):
        raise SessionWorktreeError(
            "The recorded worktree path is redirected by a symlink"
        )

    cache = CloneCache(config)
    lock_path = cache.lock_path(recorded)
    with temporary_directory_lock(lock_path):
        assert_temp_directory_unused(str(recorded))
        if recorded.exists():
            try:
                _verify_worktree(source, recorded, branch)
            except SessionWorktreeError:
                if (
                    not recorded.is_dir()
                    or recorded.is_symlink()
                    or any(recorded.iterdir())
                ):
                    raise
                # A failed worktree add can leave only its empty target
                # directory. It contains no user data and can be retried.
                recorded.rmdir()
            else:
                cache.use(
                    recorded,
                    created=cache.pending_recovery(recorded),
                    remote_url=GitUtils.get_remote_url(source),
                    locked=True,
                )
                return True

        if not _valid_branch(source, branch):
            raise SessionWorktreeError(
                "The saved session branch is no longer available"
            )
        if not expected_source_fingerprint:
            raise SessionWorktreeError(
                "Repository identity is missing; refusing to recreate a worktree from an unverified source"
            )
        attached = _worktree_records(source)
        stale_path = recorded.resolve(strict=False)
        if stale_path in attached and not stale_path.exists():
            # Pruning removes only stale Git registration metadata, not files.
            _run_git(source, "worktree", "prune", "--expire", "now")
            attached = _worktree_records(source)
        other_checkout = next(
            (
                path
                for path, attached_branch in attached.items()
                if attached_branch == branch
            ),
            None,
        )
        if other_checkout is not None and other_checkout != stale_path:
            raise SessionWorktreeError(
                "The saved session branch is checked out at another path; refusing to switch repositories"
            )

        root.mkdir(parents=True, exist_ok=True)
        if recorded.exists():
            if not recorded.is_dir() or any(recorded.iterdir()):
                raise SessionWorktreeError(
                    "Refusing to replace data at the recorded worktree path"
                )
            recorded.rmdir()
        cache.begin_restore(recorded, GitUtils.get_remote_url(source) or "", branch)
        _run_git(source, "worktree", "add", str(recorded), branch, timeout=120)
        _verify_worktree(source, recorded, branch)
        cache.use(
            recorded,
            created=True,
            remote_url=GitUtils.get_remote_url(source),
            locked=True,
        )
    cache.prune()
    return True


def cleanup_session_worktree(
    worktree_path: Path,
    source_path: Path,
    *,
    locked: bool = False,
    expected_source_fingerprint: str | None = None,
    config: Config | None = None,
) -> None:
    """Remove a clean, unused worktree without force or discarding local files."""
    path = worktree_path.expanduser()
    source = source_path.expanduser().resolve()
    root = _managed_worktree_root(path, config)
    lock = temporary_directory_lock(str(path))
    if locked:
        from contextlib import nullcontext

        lock = nullcontext()

    with lock:
        if not root.exists():
            return
        assert_temp_directory_unused(str(path))
        if not path.exists():
            _remove_empty_worktree_root(root)
            return
        try:
            if (
                expected_source_fingerprint
                and worktree_source_fingerprint(source) != expected_source_fingerprint
            ):
                raise SessionWorktreeError(
                    "The source repository no longer matches the repository recorded for this worktree"
                )
            _verify_worktree(source, path, GitUtils.get_current_branch(path))
        except (OSError, SessionWorktreeError) as error:
            raise SessionWorktreeCleanupError(
                "Cannot verify that the recorded worktree still belongs to its source repository; it was preserved"
            ) from error

        try:
            status = _run_git(
                path,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--ignored=matching",
                check=False,
            )
        except (OSError, SessionWorktreeError) as error:
            raise SessionWorktreeCleanupError(
                "Cannot inspect the worktree safely; it was preserved"
            ) from error
        if status.returncode != 0 or status.stdout:
            raise SessionWorktreeCleanupError(
                "The worktree contains local or ignored files and was preserved; commit or back up that work before deleting it"
            )

        try:
            result = _run_git(
                source,
                "worktree",
                "remove",
                str(path.resolve()),
                check=False,
            )
        except (OSError, SessionWorktreeError) as error:
            raise SessionWorktreeCleanupError(
                "Git worktree removal could not be verified; it was preserved"
            ) from error
        if result.returncode != 0 or path.exists():
            raise SessionWorktreeCleanupError(
                "Git refused to remove the worktree; it was preserved"
            )
        _remove_empty_worktree_root(root)


def _remove_empty_worktree_root(root: Path) -> None:
    """Remove only the managed container left after its worktree is gone."""
    if not root.is_dir() or root.is_symlink():
        return
    remaining = {child.name for child in root.iterdir()} - {".daf-managed-clone"}
    if not remaining:
        shutil.rmtree(root)
