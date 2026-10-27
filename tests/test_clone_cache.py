"""Retention/recovery regressions using real, isolated Git repositories."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from devflow.cli.commands.open_command import _restore_session_clone
from devflow.config.loader import ConfigLoader
from devflow.config.models import CloneRetentionConfig, Config, JiraConfig, RepoConfig
from devflow.session.manager import SessionManager
from devflow.utils import clone_cache
from devflow.utils.clone_cache import MARKER, CloneCache
from devflow.utils.clone_lifecycle import (
    clone_cache_record_path,
    temporary_directory_lock,
)
from devflow.utils.temp_directory import (
    clone_repository_at_path,
    clone_to_temp_directory,
    create_empty_temp_directory,
    extract_repo_name,
    get_clone_base_dir,
    prompt_and_clone_to_temp,
)

NOW = 2_000_000_000.0


def git(path: Path, *args: str, input: str | None = None) -> str:
    """Run local test Git commands without interactive prompts or signing."""
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-C", str(path), *args],
        input=input,
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    ).stdout.strip()


@pytest.fixture(scope="module")
def remote(tmp_path_factory):
    """A shared read-only local remote with a default branch and ignored-file rule."""
    base = tmp_path_factory.mktemp("clone-origin")
    source = base / "source"
    source.mkdir()
    git(source, "init", "--initial-branch=main")
    git(source, "config", "user.name", "Test User")
    git(source, "config", "user.email", "test@example.com")
    (source / "README.md").write_text("Tracked content\n")
    (source / ".gitignore").write_text("ignored.txt\n")
    git(source, "add", ".")
    git(source, "commit", "-m", "Initial content")
    origin = base / "origin.git"
    git(source, "clone", "--bare", str(source), str(origin))
    return origin


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVAIFLOW_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(clone_cache, "time", SimpleNamespace(time=lambda: NOW))
    config = Config(
        jira=JiraConfig(url="https://jira.example.com", user="test-user", transitions={}),
        repos=RepoConfig(),
        clone_dir=str(tmp_path / "clones"),
        clone_retention=CloneRetentionConfig(max_idle_days=30, max_size_mb=0),
    )
    return CloneCache(config), config


def managed(cache: CloneCache, remote: Path, name: str = "a") -> Path:
    """Allocate a marked, reproducible entry with the same layout as the CLI."""
    repo = cache.base / f"daf-session-{name}" / "project-a"
    repo.parent.mkdir(parents=True)
    git(remote, "clone", str(remote), str(repo))
    cache.use(repo, created=True)
    return repo


def idle(repo: Path, days: float = 31) -> None:
    """Simulate an exited CLI while preserving persistent ownership metadata."""
    state = clone_cache_record_path(repo.parent)
    record = json.loads(state.read_text())
    record.update(last_used=NOW - days * 86400, leases={})
    state.write_text(json.dumps(record))


@pytest.mark.parametrize("field", ["max_idle_days", "max_size_mb"])
@pytest.mark.parametrize("value", [-1, 1.5, "1", True, None, float("inf")])
def test_retention_rejects_invalid_limits(field, value):
    with pytest.raises(ValidationError):
        CloneRetentionConfig(**{field: value})


def test_finite_defaults_and_independent_disable():
    assert CloneRetentionConfig().model_dump() == {"max_idle_days": 30, "max_size_mb": 10240}
    assert CloneRetentionConfig(max_idle_days=0).max_size_mb == 10240
    assert CloneRetentionConfig(max_size_mb=0).max_idle_days == 30


@pytest.mark.parametrize("cleanup", [False, True])
def test_split_config_round_trip_preserves_policy_root_and_explicit_cleanup(cache, cleanup):
    _, config = cache
    config.clone_retention = CloneRetentionConfig(max_idle_days=7, max_size_mb=256)
    config.concurrency.cleanup_on_complete = cleanup
    loader = ConfigLoader()
    loader.save_config(config)
    loaded = ConfigLoader().load_config()
    assert loaded.clone_dir == config.clone_dir
    assert loaded.clone_retention == config.clone_retention
    assert loaded.concurrency.cleanup_on_complete is cleanup


@pytest.mark.parametrize("days,evicted", [(29.9999, False), (30, True), (31, True)])
def test_age_boundary_and_retention_tombstone(cache, remote, days, evicted):
    store, _ = cache
    repo = managed(store, remote)
    idle(repo, days)
    store.prune()
    assert repo.exists() is not evicted
    saved_remote, branch, known = store.recovery(repo)
    assert (saved_remote, branch, known) == (str(remote), "main", evicted)


def test_activity_refresh_does_not_use_directory_mtime(cache, remote):
    store, _ = cache
    repo = managed(store, remote)
    idle(repo, 31)
    os.utime(repo.parent, (1, 1))
    store.use(repo)
    idle(repo, 0)  # The newly recorded timestamp survives process exit.
    store.prune()
    assert repo.exists()
    assert json.loads(clone_cache_record_path(repo.parent).read_text())["last_used"] == NOW


def test_size_lru_and_equal_time_name_tiebreak(cache, remote, monkeypatch):
    store, _ = cache
    store.policy = CloneRetentionConfig(max_idle_days=0, max_size_mb=1)
    newest = managed(store, remote, "newest")
    b = managed(store, remote, "b")
    a = managed(store, remote, "a")
    idle(newest, 1)
    idle(b, 2)
    idle(a, 2)
    monkeypatch.setattr(clone_cache, "_size", lambda path: 512 * 1024)
    store.prune()
    assert not a.exists()
    assert b.exists() and newest.exists()  # Exactly the budget is allowed.


def test_age_expiry_precedes_size_only_candidates(cache, remote, monkeypatch):
    store, _ = cache
    store.policy = CloneRetentionConfig(max_idle_days=30, max_size_mb=1)
    expired = managed(store, remote, "expired")
    recent = managed(store, remote, "recent")
    idle(expired, 31)
    idle(recent, 1)
    monkeypatch.setattr(clone_cache, "_size", lambda path: 1024 * 1024)
    store.prune()
    assert not expired.exists()
    assert recent.exists()


def test_new_allocation_and_reopen_leases_pin_clones(cache, remote):
    store, _ = cache
    repo = managed(store, remote)
    state = clone_cache_record_path(repo.parent)
    record = json.loads(state.read_text())
    record["last_used"] = NOW - 100 * 86400
    state.write_text(json.dumps(record))  # Keep the current process lease.
    store.prune()
    assert repo.exists()


@pytest.mark.parametrize(
    "change",
    [
        "dirty",
        "untracked",
        "ignored",
        "unpushed",
        "branch",
        "tag",
        "stash",
        "dangling",
        "reflog",
        "hooks",
        "exclude",
        "config",
        "sibling",
        "metadata",
        "object-file",
        "log-file",
    ],
)
def test_local_only_work_is_never_evicted(cache, remote, change):
    store, _ = cache
    repo = managed(store, remote)
    if change == "dirty":
        (repo / "README.md").write_text("Modified content")
    elif change in {"untracked", "ignored"}:
        (repo / ("ignored.txt" if change == "ignored" else "new.txt")).write_text("Local work")
    elif change in {"unpushed", "reflog"}:
        if change == "reflog":
            git(repo, "checkout", "-b", "temporary")
        git(
            repo,
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--allow-empty",
            "-m",
            "Local-only commit",
        )
        if change == "reflog":
            git(repo, "checkout", "main")
            git(repo, "branch", "-D", "temporary")
    elif change == "stash":
        (repo / "README.md").write_text("Stashed work")
        git(repo, "-c", "user.name=Test User", "-c", "user.email=test@example.com", "stash")
    elif change == "branch":
        git(repo, "branch", "local-only")
    elif change == "tag":
        git(repo, "tag", "local-only")
    elif change == "dangling":
        git(repo, "hash-object", "-w", "--stdin", input="Local object content")
    elif change == "hooks":
        (repo / ".git" / "hooks" / "pre-commit").write_text("Local hook")
    elif change == "exclude":
        (repo / ".git" / "info" / "exclude").write_text("Local ignore patterns")
    elif change == "config":
        git(repo, "config", "custom.setting", "Local configuration")
    elif change == "sibling":
        (repo.parent / "other-project").mkdir()
    elif change in {"object-file", "log-file"}:
        directory = "objects" if change == "object-file" else "logs"
        (repo / ".git" / directory / "local-backup").write_text("Local-only Git data")
    else:
        (repo / ".git" / "local-backup").write_text("Unknown Git data")
    idle(repo)
    store.prune()
    assert repo.exists()


@pytest.mark.parametrize("metadata", ["hooks", "exclude", "description"])
def test_local_only_init_template_data_is_protected(cache, remote, metadata):
    store, _ = cache
    repo = managed(store, remote)
    if metadata == "hooks":
        (repo / ".git" / "hooks" / "pre-commit").write_text("Template hook")
    elif metadata == "exclude":
        (repo / ".git" / "info" / "exclude").write_text("Local patterns\n")
    else:
        (repo / ".git" / "description").write_text("Local repository description")
    store.use(repo, created=True)  # Simulate metadata installed by git clone's init template.
    idle(repo)
    store.prune()
    assert repo.exists()


def test_sibling_repositories_cannot_prove_each_others_recoverability(cache, remote):
    store, _ = cache
    a = managed(store, remote)
    b = a.parent / "project-b"
    git(remote, "clone", str(remote), str(b))
    store.use(b, created=True)
    git(a, "remote", "set-url", "origin", str(b))
    git(b, "remote", "set-url", "origin", str(a))
    store.use(a)
    store.use(b)
    idle(a)
    store.prune()
    assert a.exists() and b.exists()


def test_cached_remote_refs_are_not_proof_of_reproducibility(cache, remote, monkeypatch):
    store, _ = cache
    repo = managed(store, remote)
    idle(repo)
    original = clone_cache._git

    def missing_remote(path, *args):
        if args[0] == "ls-remote":
            return ""  # Branch was deleted remotely, despite a cached origin/main.
        return original(path, *args)

    monkeypatch.setattr(clone_cache, "_git", missing_remote)
    store.prune()
    assert repo.exists()


@pytest.mark.parametrize("kind", ["root", "repo", "git", "marker"])
def test_symlinks_cannot_redirect_automatic_removal(cache, remote, kind, tmp_path):
    store, _ = cache
    repo = managed(store, remote)
    idle(repo)
    path = {
        "root": repo.parent,
        "repo": repo,
        "git": repo / ".git",
        "marker": repo.parent / MARKER,
    }[kind]
    outside = tmp_path / f"outside-{kind}"
    path.rename(outside)
    path.symlink_to(outside, target_is_directory=outside.is_dir())
    store.prune()
    assert outside.exists()
    assert path.is_symlink()


def test_unknown_paths_and_legacy_metadata_are_protected(cache, remote):
    store, _ = cache
    repo = store.base / "daf-session-unknown" / "project-a"
    repo.mkdir(parents=True)
    # Registering an existing legacy session does not invent a clone-time Git baseline.
    git(remote, "clone", str(remote), str(repo))
    store.use(repo)
    idle(repo)
    unknown = store.base / "unrelated-data"
    unknown.mkdir()
    store.prune()
    assert repo.exists() and unknown.exists()


def test_size_includes_git_and_warns_instead_of_deleting_protected_work(cache, remote, monkeypatch):
    store, _ = cache
    store.policy = CloneRetentionConfig(max_idle_days=0, max_size_mb=1)
    repo = managed(store, remote)
    (repo / ".git" / "large-data").write_bytes(b"a" * (2 * 1024 * 1024))
    idle(repo)
    output = Mock()
    monkeypatch.setattr(clone_cache, "console_print", output)
    assert clone_cache._size(repo.parent) > 2 * 1024 * 1024
    store.prune()
    assert repo.exists()
    assert "clone_retention.max_size_mb" in str(output.call_args)


def test_empty_investigation_is_eligible_but_files_pin_it(cache):
    store, config = cache
    path = Path(create_empty_temp_directory(config=config))
    state = clone_cache_record_path(path)
    record = json.loads(state.read_text())
    record.update(leases={}, last_used=NOW - 31 * 86400)
    state.write_text(json.dumps(record))
    (path / "notes.txt").write_text("Local work")
    store.prune()
    assert path.exists()
    (path / "notes.txt").unlink()
    store.prune()
    assert not path.exists()


def test_lock_protects_concurrent_create_restore_launch_and_cleanup(cache, remote):
    store, _ = cache
    repo = managed(store, remote)
    idle(repo)
    with temporary_directory_lock(str(repo)):
        store.prune()
        assert repo.exists()
    store.prune()
    assert not repo.exists()


def test_orphan_process_cwd_protects_clone_without_a_lease(cache, remote):
    store, _ = cache
    repo = managed(store, remote)
    idle(repo)
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", "import sys; print('ready', flush=True); sys.stdin.read()"],
        cwd=repo,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout.readline().strip() == "ready"
        store.prune()
        assert repo.exists()
    finally:
        process.communicate(timeout=5)
    store.prune()
    assert not repo.exists()


def test_reopen_between_discovery_and_removal_refreshes_protection(cache, remote, monkeypatch):
    store, _ = cache
    repo = managed(store, remote)
    idle(repo)
    evict = store._evict

    def concurrent_reopen(root, **kwargs):
        store.use(repo)
        return evict(root, **kwargs)

    monkeypatch.setattr(store, "_evict", concurrent_reopen)
    store.prune()
    assert repo.exists()


@pytest.mark.parametrize("failure", ["permissions", "disappearance", "offline"])
def test_prune_failures_preserve_work_and_do_not_abort_allocation(
    cache, remote, monkeypatch, failure
):
    store, config = cache
    repo = managed(store, remote)
    idle(repo)
    if failure == "offline":
        original = clone_cache._git

        def offline(path, *args):
            if args[0] == "ls-remote":
                raise subprocess.CalledProcessError(128, "git")
            return original(path, *args)

        monkeypatch.setattr(clone_cache, "_git", offline)
    else:
        error = PermissionError if failure == "permissions" else FileNotFoundError
        monkeypatch.setattr(clone_cache.shutil, "rmtree", Mock(side_effect=error("unavailable")))
    store.prune()
    assert repo.exists()
    assert create_empty_temp_directory(config=config)


def test_allocation_and_recovery_apply_policy_before_and_after_clone(cache, remote, monkeypatch):
    store, config = cache
    source = managed(store, remote)
    prune = Mock()
    monkeypatch.setattr(CloneCache, "prune", prune)
    result = clone_to_temp_directory(source, config=config)
    assert result and Path(result[0]).is_relative_to(store.base)
    assert prune.call_count == 2
    prune.reset_mock()
    target = store.base / "daf-session-restored" / "project-a"
    assert clone_repository_at_path(str(remote), target, branch="main", config=config)
    assert prune.call_count == 2
    assert git(target, "branch", "--show-current") == "main"
    prune.reset_mock()
    monkeypatch.setattr("devflow.utils.temp_directory.Confirm.ask", lambda *a, **k: True)
    monkeypatch.setattr(
        "devflow.utils.temp_directory._prompt_for_branch_selection", lambda *a: None
    )
    assert prompt_and_clone_to_temp(source, config=config)
    assert prune.call_count == 2


@pytest.mark.parametrize("layout", ["custom", "legacy-alias", "unified", "xdg"])
def test_resolved_roots_apply_to_all_allocations(cache, tmp_path, monkeypatch, layout):
    _, config = cache
    if layout == "custom":
        expected = Path(config.clone_dir)
    elif layout == "legacy-alias":
        config.clone_dir = None
        config.concurrency.auto_clone_path = str(tmp_path / "alias")
        expected = tmp_path / "alias"
    elif layout == "unified":
        config.clone_dir = None
        expected = tmp_path / "home" / "clones"
    else:
        config.clone_dir = None
        monkeypatch.delenv("DEVAIFLOW_HOME")
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "no-legacy-home")
        expected = tmp_path / "cache" / "devaiflow" / "clones"
    assert get_clone_base_dir(config) == expected
    path = Path(create_empty_temp_directory(config=config))
    assert path.parent == expected
    assert clone_cache_record_path(path).exists()


def test_clone_dir_takes_precedence_over_legacy_alias(cache):
    store, config = cache
    config.concurrency.auto_clone_path = str(store.base / "legacy")
    assert get_clone_base_dir(config) == store.base


def session_for_clone(config, repo, source):
    """Persist a conversation whose source workspace may later disappear."""
    loader = ConfigLoader()
    loader.save_config(config)
    manager = SessionManager(loader)
    session = manager.create_session(
        name="session-a",
        goal="Clone retention",
        working_directory="project-a",
        project_path=str(repo),
        agent_backend="opencode",
        ai_agent_session_id="ses_saved",
    )
    session.active_conversation.temp_directory = str(repo)
    session.active_conversation.original_project_path = str(source)
    manager.update_session(session)
    return manager, session


def test_evicted_reopen_keeps_identity_branch_and_path_without_original_workspace(
    cache, remote, monkeypatch
):
    store, config = cache
    repo = managed(store, remote)
    manager, session = session_for_clone(config, repo, store.base.parent / "missing-workspace")
    idle(repo)
    store.prune()
    assert not repo.exists()
    output = Mock()
    monkeypatch.setattr("devflow.cli.commands.open_command.console.print", output)
    monkeypatch.setattr("devflow.cli.commands.open_command._copy_conversation_to_temp", Mock())
    assert _restore_session_clone(session, manager, config)
    assert repo.is_dir()
    assert git(repo, "branch", "--show-current") == "main"
    conv = manager.get_session(session.name).active_conversation
    assert conv.ai_agent_session_id == "ses_saved"
    assert conv.project_path == conv.temp_directory == str(repo)
    assert "evicted by clone cache retention" in str(output.call_args_list)


@pytest.mark.parametrize("failure", ["offline", "missing-remote", "branch-missing"])
def test_recovery_failure_preserves_metadata_and_conversation(cache, remote, monkeypatch, failure):
    store, config = cache
    repo = managed(store, remote)
    manager, session = session_for_clone(config, repo, store.base.parent / "missing-workspace")
    idle(repo)
    store.prune()
    if failure == "offline":
        monkeypatch.setattr(
            "devflow.utils.temp_directory.GitUtils.clone_repository", lambda *a, **k: False
        )
    elif failure == "missing-remote":
        clone_cache_record_path(repo.parent).unlink()
    else:
        session.active_conversation.branch = "missing-branch"
        manager.update_session(session)
    before = session.model_dump()
    assert _restore_session_clone(session, manager, config) is False
    assert session.model_dump() == before
    assert manager.get_session(session.name).model_dump() == before


def test_changed_clone_root_does_not_break_saved_recovery_metadata(cache, remote):
    store, config = cache
    repo = managed(store, remote)
    idle(repo)
    store.prune()
    config.clone_dir = str(store.base.parent / "different-clones")
    assert CloneCache(config).recovery(repo) == (str(remote), "main", True)


def test_nondefault_recorded_branch_is_restored(cache, remote, tmp_path, monkeypatch):
    store, config = cache
    origin = tmp_path / "branch-origin.git"
    git(remote, "clone", "--bare", str(remote), str(origin))
    git(origin, "update-ref", "refs/heads/release/test", git(origin, "rev-parse", "main"))
    repo = managed(store, origin)
    git(repo, "checkout", "release/test")
    store.use(repo)
    manager, session = session_for_clone(config, repo, tmp_path / "missing-workspace")
    session.active_conversation.branch = "release/test"
    manager.update_session(session)
    idle(repo)
    store.prune()
    assert not repo.exists()
    monkeypatch.setattr("devflow.cli.commands.open_command._copy_conversation_to_temp", Mock())
    assert _restore_session_clone(session, manager, config)
    assert git(repo, "branch", "--show-current") == "release/test"
    assert session.active_conversation.ai_agent_session_id == "ses_saved"


def test_failed_branch_recovery_cannot_reuse_wrong_branch_on_retry(cache, remote):
    store, config = cache
    repo = managed(store, remote)
    idle(repo)
    store.prune()
    assert not clone_repository_at_path(str(remote), repo, branch="missing-branch", config=config)
    assert store.pending_recovery(repo)
    assert git(repo, "branch", "--show-current") == "main"
    assert not clone_repository_at_path(str(remote), repo, branch="missing-branch", config=config)
    assert store.pending_recovery(repo)
    assert clone_repository_at_path(str(remote), repo, branch="main", config=config)
    assert not store.pending_recovery(repo)


def test_replaced_repository_does_not_silently_resume_a_different_origin(
    cache, remote, monkeypatch
):
    store, config = cache
    repo = managed(store, remote)
    manager, session = session_for_clone(config, repo, store.base.parent / "source")
    before = session.model_dump()
    git(repo, "remote", "set-url", "origin", str(store.base.parent / "different-origin.git"))
    copy = Mock()
    monkeypatch.setattr("devflow.cli.commands.open_command._copy_conversation_to_temp", copy)
    assert _restore_session_clone(session, manager, config) is False
    assert session.model_dump() == before
    copy.assert_not_called()


def test_all_conversation_references_survive_eviction_including_completed_sessions(
    cache, remote, tmp_path
):
    store, config = cache
    a = managed(store, remote, "a")
    b = managed(store, remote, "b")
    manager, session = session_for_clone(config, a, tmp_path / "missing-workspace")
    session.add_conversation(
        working_dir="project-b",
        ai_agent_session_id="ses_other",
        project_path=str(b),
        branch="main",
        temp_directory=str(b),
        original_project_path=str(tmp_path / "missing-b"),
    )
    session.working_directory = "project-a"
    session.status = "complete"
    manager.update_session(session)
    metadata = manager.config_loader.sessions_file
    before = metadata.read_bytes()
    conversation = tmp_path / "agent-storage" / "history.jsonl"
    conversation.parent.mkdir()
    conversation.write_text("Conversation history outside the cache")
    idle(a)
    idle(b)
    store.prune()
    assert not a.exists() and not b.exists()
    assert metadata.read_bytes() == before
    assert conversation.read_text() == "Conversation history outside the cache"


def test_new_oversized_clone_warns_without_evicting_it(cache, remote, monkeypatch):
    store, config = cache
    config.clone_retention.max_size_mb = 1
    monkeypatch.setattr(clone_cache, "_size", lambda path: 2 * 1024 * 1024)
    output = Mock()
    monkeypatch.setattr(clone_cache, "console_print", output)
    source = managed(store, remote)
    result = clone_to_temp_directory(source, config=config)
    assert result and Path(result[0]).exists()
    assert source.exists()
    assert "cannot meet its size budget" in str(output.call_args_list)


def test_cross_process_lifecycle_lock_protects_retention(cache, remote):
    store, _ = cache
    repo = managed(store, remote)
    idle(repo)
    code = (
        "import sys\n"
        "from devflow.utils.clone_lifecycle import temporary_directory_lock\n"
        "with temporary_directory_lock(sys.argv[1]):\n"
        "    print('ready', flush=True)\n"
        "    sys.stdin.read()\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", code, str(repo)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout.readline().strip() == "ready"
        store.prune()
        assert repo.exists()
    finally:
        process.communicate(timeout=5)
    store.prune()
    assert not repo.exists()


def test_atomic_record_failure_preserves_previous_state(cache, remote, monkeypatch):
    store, _ = cache
    repo = managed(store, remote)
    state = clone_cache_record_path(repo.parent)
    before = state.read_bytes()
    monkeypatch.setattr(clone_cache.os, "replace", Mock(side_effect=PermissionError("unavailable")))
    with pytest.raises(PermissionError):
        store.use(repo)
    assert state.read_bytes() == before
    assert list(state.parent.iterdir()) == [state]


@pytest.mark.parametrize("damage", ["invalid-json", "nonce", "path-traversal", "reused-pid"])
def test_invalid_ownership_is_protected_and_stale_pid_is_not_a_pin(cache, remote, damage):
    store, _ = cache
    repo = managed(store, remote)
    idle(repo)
    state = clone_cache_record_path(repo.parent)
    entry = json.loads(state.read_text())
    if damage == "invalid-json":
        state.write_text("not JSON")
    elif damage == "nonce":
        (repo.parent / MARKER).write_text("different ownership token")
    elif damage == "path-traversal":
        entry["repositories"]["../outside"] = entry["repositories"].pop(repo.name)
        state.write_text(json.dumps(entry))
    else:
        import psutil

        entry["leases"] = {str(os.getpid()): psutil.Process().create_time() - 1}
        state.write_text(json.dumps(entry))
    store.prune()
    assert repo.exists() is (damage != "reused-pid")


def test_failed_open_returns_clean_json_without_launch_or_identity_change(
    cache, remote, monkeypatch
):
    from click.testing import CliRunner

    from devflow.cli.main import cli

    store, config = cache
    repo = managed(store, remote)
    manager, session = session_for_clone(config, repo, store.base.parent / "missing-source")
    manager.config_loader.load_config()  # Finish any legacy migration before CLI output capture.
    idle(repo)
    store.prune()
    before = manager.config_loader.sessions_file.read_bytes()
    monkeypatch.chdir(store.base.parent)
    launch = Mock()
    monkeypatch.setattr("devflow.agent.factory.launch_and_capture", launch)
    monkeypatch.setattr(
        "devflow.utils.temp_directory.GitUtils.clone_repository", lambda *a, **k: False
    )
    result = CliRunner().invoke(cli, ["open", session.name, "--json"])
    assert result.exit_code == 1, result.output
    assert result.output.startswith("{"), (result.output, repr(result.exception))
    data = json.loads(result.output)
    assert data["success"] is False
    assert data["error"]["code"] == "CLONE_RECOVERY_FAILED"
    assert "recovery metadata was preserved" in data["error"]["message"]
    assert manager.config_loader.sessions_file.read_bytes() == before
    launch.assert_not_called()


@pytest.mark.parametrize("url", ["https://example.com/..", "https://example.com/."])
def test_repo_name_cannot_escape_the_managed_root(url):
    assert extract_repo_name(url) == "repo"
