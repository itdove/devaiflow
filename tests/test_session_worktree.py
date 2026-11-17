"""Regression tests for isolated per-session Git worktrees."""

import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from devflow.config.models import CloneRetentionConfig
from devflow.utils.clone_cache import CloneCache
from devflow.utils.clone_lifecycle import TemporaryDirectoryInUseError
from devflow.utils.session_worktree import (
    SessionWorktreeCleanupError,
    SessionWorktreeError,
    cleanup_session_worktree,
    create_session_worktree,
    restore_session_worktree,
    worktree_source_fingerprint,
)


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=path, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _repository(path: Path, content: str = "fixture repository\n") -> Path:
    path.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    _git(path, "config", "user.name", "Test User")
    _git(path, "config", "user.email", "test@example.invalid")
    (path / "README.md").write_text(content)
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "Initial commit")
    return path


@pytest.fixture
def worktree_config(tmp_path, monkeypatch):
    managed_root = tmp_path / "managed-clones"
    monkeypatch.setattr(
        "devflow.utils.temp_directory.get_clone_base_dir",
        lambda _config=None: managed_root,
    )
    return SimpleNamespace(clone_dir=str(managed_root))


def test_multiple_worktrees_keep_source_checkout_and_branches_independent(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    _git(source, "branch", "feature-b")

    first_path, first_branch, _first_base = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    second_path, second_branch, _second_base = create_session_worktree(
        source,
        session_name="session-b",
        branch="feature-b",
        base_branch="main",
        branch_prefix="session-b",
        config=worktree_config,
    )

    assert first_path != second_path
    assert first_path.parent != second_path.parent
    assert first_branch == "feature-a"
    assert second_branch == "feature-b"
    assert _git(source, "branch", "--show-current") == "main"
    assert _git(first_path, "branch", "--show-current") == first_branch
    assert _git(second_path, "branch", "--show-current") == second_branch


def test_worktree_allocation_does_not_prune_a_managed_source_under_its_lock(
    tmp_path, worktree_config
):
    base = Path(worktree_config.clone_dir)
    base.mkdir(parents=True)
    worktree_config.clone_retention = CloneRetentionConfig(
        max_idle_days=0, max_size_mb=1
    )
    source_root = base / "daf-session-source"
    source_root.mkdir()
    source = _repository(source_root / "project-a")
    cache = CloneCache(worktree_config)
    cache.use(source, created=True)
    (source_root / "cache-pressure.bin").write_bytes(b"x" * (2 * 1024 * 1024))

    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch=None,
        base_branch="main",
        branch_prefix="feature-a",
        config=worktree_config,
    )

    assert worktree_path.is_dir()
    assert _git(worktree_path, "branch", "--show-current") == branch
    assert source_root.exists()


def test_recovery_rejects_paths_outside_managed_clone_storage(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    fingerprint = worktree_source_fingerprint(source)
    recorded = tmp_path / "unmanaged" / "project-a"

    with pytest.raises(SessionWorktreeError, match="outside managed"):
        restore_session_worktree(
            source,
            recorded,
            "feature-a",
            config=worktree_config,
            expected_source_fingerprint=fingerprint,
        )

    assert not recorded.parent.exists()


def test_worktree_uses_a_session_branch_when_saved_branch_is_already_checked_out(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    _git(source, "checkout", "-b", "feature-a")

    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )

    assert branch.startswith("feature-a-wt-session-a")
    assert _git(source, "branch", "--show-current") == "feature-a"
    assert _git(worktree_path, "branch", "--show-current") == branch


def test_worktree_without_saved_branch_creates_branch_from_base(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")

    worktree_path, branch, base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch=None,
        base_branch="main",
        branch_prefix="feature-a",
        config=worktree_config,
    )

    assert branch == "feature-a"
    assert base_branch == "main"
    assert _git(worktree_path, "branch", "--show-current") == branch
    assert _git(source, "branch", "--show-current") == "main"


def test_worktree_uses_remote_default_when_saved_base_is_default_placeholder(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    _git(source, "checkout", "-b", "develop")
    (source / "develop.txt").write_text("develop base\n")
    _git(source, "add", "develop.txt")
    _git(source, "commit", "-m", "Add develop base")
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=develop", str(bare)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(source, "remote", "add", "origin", str(bare))
    _git(source, "push", "--all", "origin")
    _git(source, "remote", "set-head", "origin", "develop")

    worktree_path, branch, actual_base = create_session_worktree(
        source,
        session_name="session-a",
        branch=None,
        base_branch="main",
        branch_prefix="feature-a",
        config=worktree_config,
    )

    assert actual_base == "develop"
    assert (worktree_path / "develop.txt").exists()
    assert branch == "feature-a"


def test_recovery_restores_missing_worktree_at_exact_path_and_branch(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    shutil.rmtree(worktree_path)

    assert restore_session_worktree(
        source,
        worktree_path,
        branch,
        config=worktree_config,
        expected_source_fingerprint=worktree_source_fingerprint(source),
    )
    assert worktree_path.is_dir()
    assert _git(worktree_path, "branch", "--show-current") == branch
    assert _git(source, "branch", "--show-current") == "main"


def test_recovery_retries_an_empty_path_left_by_failed_worktree_add(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    shutil.rmtree(worktree_path)
    worktree_path.mkdir()

    assert restore_session_worktree(
        source,
        worktree_path,
        branch,
        config=worktree_config,
        expected_source_fingerprint=worktree_source_fingerprint(source),
    )
    assert _git(worktree_path, "branch", "--show-current") == branch


def test_recovery_refuses_a_different_repository_at_the_recorded_path(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    other = _repository(tmp_path / "other")
    _git(source, "branch", "feature-a")
    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    shutil.rmtree(worktree_path)
    shutil.copytree(other, worktree_path)

    with pytest.raises(SessionWorktreeError):
        restore_session_worktree(source, worktree_path, branch, config=worktree_config)

    assert (worktree_path / "README.md").read_text() == "fixture repository\n"


def test_recovery_refuses_recreated_source_repository(tmp_path, worktree_config):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    fingerprint = worktree_source_fingerprint(source)
    shutil.rmtree(worktree_path)
    source_backup = tmp_path / "source-backup"
    source.rename(source_backup)
    replacement = _repository(source, "replacement repository\n")
    _git(replacement, "branch", "feature-a")

    with pytest.raises(SessionWorktreeError, match="no longer matches"):
        restore_session_worktree(
            replacement,
            worktree_path,
            branch,
            config=worktree_config,
            expected_source_fingerprint=fingerprint,
        )


def test_cleanup_preserves_worktree_with_uncommitted_files(tmp_path, worktree_config):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    worktree_path, _branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    local_file = worktree_path / "local-work.txt"
    local_file.write_text("keep this work\n")

    with pytest.raises(SessionWorktreeCleanupError):
        cleanup_session_worktree(worktree_path, source)

    assert local_file.read_text() == "keep this work\n"
    assert worktree_path.is_dir()


def test_cleanup_reports_tracked_untracked_and_ignored_worktree_data(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    (source / ".gitignore").write_text("generated/\n")
    _git(source, "add", ".gitignore")
    _git(source, "commit", "-m", "Ignore generated files")
    _git(source, "branch", "feature-a")
    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    (worktree_path / "README.md").write_text("modified tracked data\n")
    (worktree_path / "local-work.txt").write_text("untracked data\n")
    ignored_file = worktree_path / "generated" / "output.txt"
    ignored_file.parent.mkdir()
    ignored_file.write_text("ignored data\n")

    with pytest.raises(SessionWorktreeCleanupError) as caught:
        cleanup_session_worktree(
            worktree_path,
            source,
            expected_branch=branch,
        )

    changes = caught.value.changes
    assert changes is not None
    assert changes.path == worktree_path
    assert (changes.tracked, changes.untracked, changes.ignored) == (1, 1, 1)
    assert "tracked changes: 1" in str(caught.value)
    assert str(worktree_path) in str(caught.value)
    assert worktree_path.is_dir()
    assert ignored_file.read_text() == "ignored data\n"


def test_cleanup_deletes_dirty_worktree_only_with_reviewed_status_snapshot(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    local_file = worktree_path / "local-work.txt"
    local_file.write_text("reviewed local data\n")

    with pytest.raises(SessionWorktreeCleanupError) as caught:
        cleanup_session_worktree(worktree_path, source, expected_branch=branch)
    changes = caught.value.changes
    assert changes is not None

    with pytest.raises(SessionWorktreeCleanupError, match="reviewed status snapshot"):
        cleanup_session_worktree(
            worktree_path,
            source,
            expected_branch=branch,
            delete_local_files=True,
        )
    assert local_file.exists()

    cleanup_session_worktree(
        worktree_path,
        source,
        expected_branch=branch,
        delete_local_files=True,
        expected_changes=changes,
    )

    assert not worktree_path.exists()


def test_cleanup_refuses_dirty_worktree_changed_after_review(tmp_path, worktree_config):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    reviewed_file = worktree_path / "reviewed.txt"
    reviewed_file.write_text("reviewed\n")

    with pytest.raises(SessionWorktreeCleanupError) as caught:
        cleanup_session_worktree(worktree_path, source, expected_branch=branch)
    changes = caught.value.changes
    assert changes is not None
    added_after_review = worktree_path / "added-after-review.txt"
    added_after_review.write_text("new data\n")

    with pytest.raises(
        SessionWorktreeCleanupError, match="changed after its contents were reviewed"
    ):
        cleanup_session_worktree(
            worktree_path,
            source,
            expected_branch=branch,
            delete_local_files=True,
            expected_changes=changes,
        )

    assert reviewed_file.exists()
    assert added_after_review.exists()


def test_cleanup_refuses_ignored_file_changes_after_review(tmp_path, worktree_config):
    source = _repository(tmp_path / "source")
    (source / ".gitignore").write_text("generated/\n")
    _git(source, "add", ".gitignore")
    _git(source, "commit", "-m", "Ignore generated files")
    _git(source, "branch", "feature-a")
    worktree_path, branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    ignored_file = worktree_path / "generated" / "output.txt"
    ignored_file.parent.mkdir()
    ignored_file.write_text("reviewed data\n")

    with pytest.raises(SessionWorktreeCleanupError) as caught:
        cleanup_session_worktree(worktree_path, source, expected_branch=branch)
    changes = caught.value.changes
    assert changes is not None
    original_status = _git(
        worktree_path,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignored=matching",
    )

    ignored_file.write_text("changed after review\n")
    changed_status = _git(
        worktree_path,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignored=matching",
    )
    assert changed_status == original_status

    with pytest.raises(
        SessionWorktreeCleanupError, match="changed after its contents were reviewed"
    ):
        cleanup_session_worktree(
            worktree_path,
            source,
            expected_branch=branch,
            delete_local_files=True,
            expected_changes=changes,
        )

    assert ignored_file.read_text() == "changed after review\n"


def test_cleanup_refuses_worktree_on_branch_different_from_session_record(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    worktree_path, _branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )

    with pytest.raises(SessionWorktreeCleanupError, match="Cannot verify"):
        cleanup_session_worktree(
            worktree_path,
            source,
            expected_branch="different-branch",
        )

    assert worktree_path.is_dir()


def test_cleanup_preserves_ignored_worktree_files(tmp_path, worktree_config):
    source = _repository(tmp_path / "source")
    (source / ".gitignore").write_text("generated/\n")
    _git(source, "add", ".gitignore")
    _git(source, "commit", "-m", "Ignore generated files")
    _git(source, "branch", "feature-a")
    worktree_path, _branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    ignored_file = worktree_path / "generated" / "output.txt"
    ignored_file.parent.mkdir()
    ignored_file.write_text("local generated data\n")

    with pytest.raises(SessionWorktreeCleanupError):
        cleanup_session_worktree(worktree_path, source)

    assert ignored_file.read_text() == "local generated data\n"


def test_cleanup_removes_a_clean_worktree_without_switching_source(
    tmp_path, worktree_config
):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    worktree_path, _branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )

    cleanup_session_worktree(worktree_path, source)

    assert not worktree_path.exists()
    assert _git(source, "branch", "--show-current") == "main"


def test_cleanup_refuses_worktree_held_by_a_process(tmp_path, worktree_config):
    source = _repository(tmp_path / "source")
    _git(source, "branch", "feature-a")
    worktree_path, _branch, _base_branch = create_session_worktree(
        source,
        session_name="session-a",
        branch="feature-a",
        base_branch="main",
        branch_prefix="session-a",
        config=worktree_config,
    )
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=worktree_path,
    )
    try:
        with pytest.raises(TemporaryDirectoryInUseError):
            cleanup_session_worktree(worktree_path, source)
    finally:
        process.terminate()
        process.wait(timeout=5)

    assert worktree_path.is_dir()
