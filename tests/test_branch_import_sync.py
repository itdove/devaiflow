"""Tests for PROJ-61023: Branch sync on import workflow."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.cli.commands.open_command import (
    _checkout_and_sync_session_branch,
    _sync_branch_for_import,
)
from devflow.git.utils import GitUtils


@pytest.fixture
def mock_git_repo(tmp_path):
    """Create a mock git repository for testing."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True, check=True)

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True, check=True)

    return repo_path


def _create_remote_session_repo(
    tmp_path: Path,
    remote_update: bool = False,
    delete_local_session_branch: bool = False,
) -> Path:
    """Create a local repository and bare origin for reopen branch tests."""
    repo_path = tmp_path / "project-a"
    repo_path.mkdir()

    def run_git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            check=True,
            text=True,
        )

    run_git("init", "-b", "main")
    run_git("config", "user.name", "Test User")
    run_git("config", "user.email", "test@example.com")
    (repo_path / "README.md").write_text("# Project A\n")
    run_git("add", ".")
    run_git("commit", "-m", "Initial commit")

    remote_path = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote_path)],
        cwd=tmp_path,
        capture_output=True,
        check=True,
        text=True,
    )
    run_git("remote", "add", "origin", str(remote_path))
    run_git("push", "-u", "origin", "main")
    run_git("checkout", "-b", "feature-a")
    run_git("push", "-u", "origin", "feature-a")

    if remote_update:
        (repo_path / "remote-change.txt").write_text("Remote update\n")
        run_git("add", ".")
        run_git("commit", "-m", "Remote update")
        run_git("push", "origin", "feature-a")
        run_git("reset", "--hard", "HEAD^")

    run_git("checkout", "main")
    if delete_local_session_branch:
        run_git("branch", "-D", "feature-a")

    return repo_path


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
@pytest.mark.parametrize(
    ("remote_update", "expected_prompts"),
    [
        (
            True,
            [
                "Switch to branch 'feature-a'?",
                "Merge origin changes into local branch?",
            ],
        ),
        (False, ["Switch to branch 'feature-a'?"]),
    ],
)
def test_checkout_session_branch_before_remote_sync_prompt(
    tmp_path, monkeypatch, remote_update, expected_prompts
):
    """Reopen switches to the session branch before checking its remote state."""
    from rich.prompt import Confirm

    repo_path = _create_remote_session_repo(tmp_path, remote_update=remote_update)
    prompts = []

    def confirm(*args, **kwargs):
        prompt = next(arg for arg in args if isinstance(arg, str))
        prompts.append(prompt)
        if prompt.startswith("Merge "):
            assert GitUtils.get_current_branch(repo_path) == "feature-a"
        return True

    monkeypatch.setattr(Confirm, "ask", confirm)

    assert (
        _checkout_and_sync_session_branch(
            str(repo_path), "feature-a", base_branch="main"
        )
        is True
    )

    assert prompts == expected_prompts
    assert GitUtils.get_current_branch(repo_path) == "feature-a"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_checkout_and_sync_fetches_remote_only_session_branch(tmp_path, monkeypatch):
    """A remote-only imported branch is fetched before the checkout flow."""
    from rich.prompt import Confirm

    repo_path = _create_remote_session_repo(tmp_path, delete_local_session_branch=True)
    prompts = []

    def confirm(*args, **kwargs):
        prompt = next(arg for arg in args if isinstance(arg, str))
        prompts.append(prompt)
        return True

    monkeypatch.setattr(Confirm, "ask", confirm)

    assert (
        _checkout_and_sync_session_branch(
            str(repo_path), "feature-a", base_branch="main"
        )
        is True
    )

    assert prompts == ["Fetch branch 'feature-a' from origin?"]
    assert GitUtils.get_current_branch(repo_path) == "feature-a"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_checkout_and_sync_uses_local_session_branch_when_remote_query_times_out(
    tmp_path, monkeypatch, capsys
):
    """A remote query timeout doesn't prevent opening an existing local branch."""
    from rich.prompt import Confirm

    repo_path = _create_remote_session_repo(tmp_path)
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)

    real_run = subprocess.run
    commands = []

    def timeout_ls_remote(cmd, *args, **kwargs):
        commands.append(cmd)
        if cmd[:3] == ["git", "ls-remote", "--heads"]:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 10))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", timeout_ls_remote)

    assert (
        _checkout_and_sync_session_branch(
            str(repo_path), "feature-a", base_branch="main"
        )
        is True
    )

    assert GitUtils.get_current_branch(repo_path) == "feature-a"
    assert ["git", "fetch", "origin"] in commands
    output = " ".join(capsys.readouterr().out.split())
    assert "remote query timed out" in output
    assert "Continuing with the local branch" in output
    assert "up-to-date" not in output


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_checkout_and_sync_does_not_treat_remote_only_branch_as_missing_on_timeout(
    tmp_path, monkeypatch, capsys
):
    """An inconclusive remote query must not trigger a prompt to create a branch."""
    from rich.prompt import Confirm

    repo_path = _create_remote_session_repo(tmp_path, delete_local_session_branch=True)

    def unexpected_prompt(*args, **kwargs):
        pytest.fail("an inconclusive remote query must not prompt to create a branch")

    monkeypatch.setattr(Confirm, "ask", unexpected_prompt)

    real_run = subprocess.run

    def timeout_ls_remote(cmd, *args, **kwargs):
        if cmd[:3] == ["git", "ls-remote", "--heads"]:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 10))
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", timeout_ls_remote)

    assert (
        _checkout_and_sync_session_branch(
            str(repo_path), "feature-a", base_branch="main"
        )
        is False
    )

    assert GitUtils.get_current_branch(repo_path) == "main"
    output = " ".join(capsys.readouterr().out.split())
    assert "remote query timed out" in output
    assert "Remote state for branch 'feature-a' is unknown" in output
    assert "does not exist locally or on origin" not in output
    assert "Branch 'feature-a' does not exist" not in output


def test_sync_branch_not_git_repo(tmp_path):
    """Test _sync_branch_for_import when path is not a git repo."""
    non_git_path = tmp_path / "not-a-repo"
    non_git_path.mkdir()

    # Should return True (no error) for non-git repos
    result = _sync_branch_for_import(str(non_git_path), "test-branch")
    assert result is True


def test_sync_branch_exists_remotely_but_not_locally(mock_git_repo, monkeypatch):
    """Test fetching branch that exists on remote but not locally (PROJ-61023 AC1)."""
    # Mock the prompts to auto-confirm
    from rich.prompt import Confirm
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)

    # Store real subprocess.run
    real_run = subprocess.run

    # Mock git commands to simulate remote branch existence
    def mock_run(cmd, *args, **kwargs):
        # Mock git fetch - success
        if isinstance(cmd, list) and "fetch" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            return mock_result

        # Mock git ls-remote to show branch exists on remote
        if isinstance(cmd, list) and "ls-remote" in cmd and "--heads" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "abc123def456  refs/heads/test-branch"
            return mock_result

        # Mock git checkout - success
        if isinstance(cmd, list) and "checkout" in cmd and "-b" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        # Default - call real subprocess
        return real_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=mock_run):
        # Branch doesn't exist locally
        with patch.object(GitUtils, "branch_exists", return_value=False):
            result = _sync_branch_for_import(str(mock_git_repo), "test-branch")

            # Should successfully fetch and checkout
            assert result is True


def test_sync_branch_exists_locally_but_behind_remote(mock_git_repo, monkeypatch):
    """Test merging when local branch is behind remote (PROJ-61023 AC2)."""
    # Create a local branch
    real_run = subprocess.run
    # Get current branch name (could be main or master)
    result = real_run(["git", "branch", "--show-current"], cwd=mock_git_repo, capture_output=True, check=True, text=True)
    default_branch = result.stdout.strip()

    real_run(["git", "checkout", "-b", "test-branch"], cwd=mock_git_repo, capture_output=True, check=True)
    real_run(["git", "checkout", default_branch], cwd=mock_git_repo, capture_output=True, check=True)

    # Mock prompts to auto-confirm
    from rich.prompt import Confirm
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)

    # Mock git commands to simulate branch being behind
    rev_list_commands = []

    def mock_run(cmd, *args, **kwargs):
        # Mock git fetch - success
        if isinstance(cmd, list) and "fetch" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        # Mock git ls-remote to show branch exists on remote
        if isinstance(cmd, list) and "ls-remote" in cmd and "--heads" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "abc123def456  refs/heads/test-branch"
            return mock_result

        # Mock git rev-list to show 3 commits behind
        if isinstance(cmd, list) and "rev-list" in cmd and "--count" in cmd:
            rev_list_commands.append(cmd)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "3"
            return mock_result

        # Mock git merge - success (no conflicts)
        if isinstance(cmd, list) and "merge" in cmd and "origin/test-branch" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        # Default - call real subprocess
        return real_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=mock_run):
        # Branch exists locally
        with patch.object(GitUtils, "branch_exists", return_value=True):
            result = _sync_branch_for_import(str(mock_git_repo), "test-branch")

            # Should successfully merge
            assert result is True

    assert rev_list_commands == [
        [
            "git",
            "rev-list",
            "--count",
            "refs/heads/test-branch..refs/remotes/origin/test-branch",
        ]
    ]


def test_sync_branch_merge_conflicts(mock_git_repo, monkeypatch):
    """Test handling merge conflicts during branch sync (PROJ-61023 AC4)."""
    # Create a local branch
    real_run = subprocess.run
    # Get current branch name (could be main or master)
    result = real_run(["git", "branch", "--show-current"], cwd=mock_git_repo, capture_output=True, check=True, text=True)
    default_branch = result.stdout.strip()

    real_run(["git", "checkout", "-b", "test-branch"], cwd=mock_git_repo, capture_output=True, check=True)
    real_run(["git", "checkout", default_branch], cwd=mock_git_repo, capture_output=True, check=True)

    # Mock prompts to auto-confirm
    from rich.prompt import Confirm
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)

    # Mock git commands to simulate merge conflicts
    def mock_run(cmd, *args, **kwargs):
        # Mock git fetch - success
        if isinstance(cmd, list) and "fetch" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        # Mock git ls-remote to show branch exists on remote
        if isinstance(cmd, list) and "ls-remote" in cmd and "--heads" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "abc123def456  refs/heads/test-branch"
            return mock_result

        # Mock git rev-list to show commits behind
        if isinstance(cmd, list) and "rev-list" in cmd and "--count" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "1"
            return mock_result

        # Mock git merge - conflicts!
        if isinstance(cmd, list) and "merge" in cmd and "origin/test-branch" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 1  # Merge failed
            return mock_result

        # Mock git merge --abort - cleanup
        if isinstance(cmd, list) and "merge" in cmd and "--abort" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        # Default - call real subprocess
        return real_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=mock_run):
        # Branch exists locally
        with patch.object(GitUtils, "branch_exists", return_value=True):
            with patch.object(GitUtils, "merge_branch", return_value=(False, "merge error")):
                result = _sync_branch_for_import(str(mock_git_repo), "test-branch")

                # Should return False (merge failed)
                assert result is False


def test_sync_branch_doesnt_exist_anywhere(mock_git_repo, monkeypatch):
    """Test when branch doesn't exist locally or remotely (PROJ-61023 AC3)."""
    # Mock prompts
    from rich.prompt import Confirm
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)

    # Store real subprocess.run
    real_run = subprocess.run

    # Mock git commands to show branch doesn't exist anywhere
    def mock_run(cmd, *args, **kwargs):
        # Mock git fetch - success
        if isinstance(cmd, list) and "fetch" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        # Mock git ls-remote to show branch doesn't exist on remote
        if isinstance(cmd, list) and "ls-remote" in cmd and "--heads" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""  # Empty - no branch found
            return mock_result

        # Default - call real subprocess
        return real_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=mock_run):
        # Branch doesn't exist locally either
        with patch.object(GitUtils, "branch_exists", return_value=False):
            result = _sync_branch_for_import(str(mock_git_repo), "nonexistent-branch")

            # Should return True (not critical - user will be prompted to create)
            assert result is True


def test_sync_branch_fork_support(mock_git_repo, monkeypatch):
    """Test fork support with different remote URL (PROJ-61023 AC5)."""
    # Mock prompts to auto-confirm
    from rich.prompt import Confirm, Prompt
    monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "teammate")

    # Store real subprocess.run
    real_run = subprocess.run

    # Setup - add origin remote
    real_run(
        ["git", "remote", "add", "origin", "https://github.com/myorg/repo.git"],
        cwd=mock_git_repo,
        capture_output=True,
        check=True
    )

    # Different fork URL
    fork_url = "https://github.com/teammate/repo.git"

    # Mock git commands
    def mock_run(cmd, *args, **kwargs):
        # Mock git fetch - success
        if isinstance(cmd, list) and "fetch" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        # Mock git ls-remote to show branch exists on teammate's fork
        if isinstance(cmd, list) and "ls-remote" in cmd and "--heads" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "abc123def456  refs/heads/feature-branch"
            return mock_result

        # Mock git remote add - success
        if isinstance(cmd, list) and "remote" in cmd and "add" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        # Mock git checkout - success
        if isinstance(cmd, list) and "checkout" in cmd and "-b" in cmd:
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        # Default - call real subprocess
        return real_run(cmd, *args, **kwargs)

    with patch("subprocess.run", side_effect=mock_run):
        with patch.object(GitUtils, "branch_exists", return_value=False):
            with patch.object(GitUtils, "get_remote_name_for_url", return_value=None):
                result = _sync_branch_for_import(str(mock_git_repo), "feature-branch", remote_url=fork_url)

                # Should handle fork workflow and return True
                assert result is True
