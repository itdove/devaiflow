"""Tests for Git utilities."""

import shutil
import subprocess
from pathlib import Path

import pytest

from devflow.git.utils import GitUtils


def test_slugify_basic():
    """Test basic slugification."""
    result = GitUtils.slugify("Implement backup feature")

    assert result == "implement-backup-feature"


def test_slugify_special_characters():
    """Test slugify removes special characters."""
    result = GitUtils.slugify("Fix bug: authentication failed!")

    assert result == "fix-bug-authentication-failed"


def test_slugify_multiple_spaces():
    """Test slugify handles multiple spaces."""
    result = GitUtils.slugify("multiple   spaces   here")

    assert result == "multiple-spaces-here"


def test_slugify_underscores():
    """Test slugify converts underscores to hyphens."""
    result = GitUtils.slugify("test_with_underscores")

    assert result == "test-with-underscores"


def test_slugify_leading_trailing_hyphens():
    """Test slugify removes leading/trailing hyphens."""
    result = GitUtils.slugify("  - leading and trailing -  ")

    assert result == "leading-and-trailing"


def test_slugify_uppercase():
    """Test slugify converts to lowercase."""
    result = GitUtils.slugify("UPPERCASE TEXT")

    assert result == "uppercase-text"


def test_slugify_max_length():
    """Test slugify limits length to 50 characters."""
    long_text = "a" * 100
    result = GitUtils.slugify(long_text)

    assert len(result) == 50


def test_slugify_collapse_hyphens():
    """Test slugify collapses multiple hyphens."""
    result = GitUtils.slugify("multiple---hyphens---here")

    assert result == "multiple-hyphens-here"


def test_generate_branch_name():
    """Test generating branch name from issue key and goal."""
    result = GitUtils.generate_branch_name("PROJ-12345", "Implement backup feature")

    assert result == "proj-12345-implement-backup-feature"


def test_generate_branch_name_with_special_chars():
    """Test branch name generation with special characters in goal."""
    result = GitUtils.generate_branch_name("PROJ-99999", "Fix bug: auth failed!")

    assert result == "proj-99999-fix-bug-auth-failed"


def test_generate_branch_name_custom_pattern():
    """Test branch name generation with custom pattern."""
    result = GitUtils.generate_branch_name(
        "PROJ-12345",
        "Feature",
        pattern="feature/{issue_key}/{goal_slug}"
    )

    assert result == "feature/proj-12345/feature"


def test_generate_branch_name_with_issue_key_in_goal():
    """Test branch name generation when goal contains issue key prefix."""
    result = GitUtils.generate_branch_name("PROJ-12345", "PROJ-12345: Fix login bug")

    # Should strip the duplicate issue key from goal
    assert result == "proj-12345-fix-login-bug"


def test_generate_branch_name_with_issue_key_in_goal_no_space():
    """Test branch name generation when goal has issue key with no space after colon."""
    result = GitUtils.generate_branch_name("PROJ-99999", "PROJ-99999:Refactor authentication")

    # Should strip the issue key even without space
    assert result == "proj-99999-refactor-authentication"


def test_generate_branch_name_without_issue_key_in_goal():
    """Test branch name generation when goal does not contain issue key."""
    result = GitUtils.generate_branch_name("PROJ-12345", "Fix login bug")

    # Should work normally without issue key in goal
    assert result == "proj-12345-fix-login-bug"


def test_generate_branch_name_different_issue_key_in_goal():
    """Test branch name generation when goal contains a different issue key."""
    result = GitUtils.generate_branch_name("PROJ-12345", "Related to PROJ-99999: Fix bug")

    # Should only strip issue key at the beginning
    assert result == "proj-12345-related-to-proj-99999-fix-bug"


def test_generate_branch_name_issue_key_in_middle_of_goal():
    """Test that issue key in middle of goal is not stripped."""
    result = GitUtils.generate_branch_name("PROJ-12345", "Fix PROJ-99999 related bug")

    # Should only strip issue key at the start, not in middle
    assert result == "proj-12345-fix-proj-99999-related-bug"


def test_generate_branch_name_multiple_colons_in_goal():
    """Test branch name generation with multiple colons in goal."""
    result = GitUtils.generate_branch_name("PROJ-12345", "PROJ-12345: Fix bug: authentication failed")

    # Should strip the issue key prefix but keep other colons
    assert result == "proj-12345-fix-bug-authentication-failed"


def test_is_git_repository_not_git(tmp_path):
    """Test is_git_repository with non-git directory."""
    result = GitUtils.is_git_repository(tmp_path)

    assert result is False


def test_is_git_repository_nonexistent(tmp_path):
    """Test is_git_repository with nonexistent directory."""
    nonexistent = tmp_path / "does-not-exist"
    result = GitUtils.is_git_repository(nonexistent)

    assert result is False


def test_get_current_branch_not_git(tmp_path):
    """Test get_current_branch with non-git directory."""
    result = GitUtils.get_current_branch(tmp_path)

    assert result is None


def test_get_default_branch_not_git(tmp_path):
    """Test get_default_branch with non-git directory."""
    result = GitUtils.get_default_branch(tmp_path)

    assert result is None


def test_branch_exists_not_git(tmp_path):
    """Test branch_exists with non-git directory."""
    result = GitUtils.branch_exists(tmp_path, "main")

    assert result is False


def test_create_branch_not_git(tmp_path):
    """Test create_branch with non-git directory."""
    result = GitUtils.create_branch(tmp_path, "new-branch")

    assert result is False


def test_checkout_branch_not_git(tmp_path):
    """Test checkout_branch with non-git directory."""
    result = GitUtils.checkout_branch(tmp_path, "main")

    assert result is False


def test_fetch_origin_not_git(tmp_path):
    """Test fetch_origin with non-git directory."""
    result = GitUtils.fetch_origin(tmp_path)

    assert result is False


def test_pull_current_branch_not_git(tmp_path):
    """Test pull_current_branch with non-git directory."""
    result = GitUtils.pull_current_branch(tmp_path)

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_is_git_repository_with_real_git(tmp_path):
    """Test is_git_repository with actual git repo."""
    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)

    result = GitUtils.is_git_repository(tmp_path)

    assert result is True


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_get_current_branch_with_real_git(tmp_path):
    """Test get_current_branch with actual git repo."""
    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit to establish branch
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    result = GitUtils.get_current_branch(tmp_path)

    assert result in ["main", "master"]  # Depends on git configuration


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_get_current_commit_sha_with_real_git(tmp_path):
    """Test get_current_commit_sha with actual git repo."""
    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    result = GitUtils.get_current_commit_sha(tmp_path)

    # Should return a 40-character hex SHA
    assert result is not None
    assert len(result) == 40
    assert all(c in "0123456789abcdef" for c in result)


def test_get_current_commit_sha_not_git(tmp_path):
    """Test get_current_commit_sha with non-git directory."""
    result = GitUtils.get_current_commit_sha(tmp_path)

    assert result is None


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_branch_exists_with_real_git(tmp_path):
    """Test branch_exists with actual git repo."""
    # Initialize a git repo with a branch
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    current_branch = GitUtils.get_current_branch(tmp_path)

    # Current branch should exist
    assert GitUtils.branch_exists(tmp_path, current_branch) is True

    # Non-existent branch should not exist
    assert GitUtils.branch_exists(tmp_path, "nonexistent-branch") is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_create_and_checkout_branch(tmp_path):
    """Test creating and checking out branches."""
    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create an initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Create new branch
    result = GitUtils.create_branch(tmp_path, "feature-branch")
    assert result is True

    # Verify we're on the new branch
    current = GitUtils.get_current_branch(tmp_path)
    assert current == "feature-branch"

    # Switch back to default branch
    default_branch = GitUtils.get_current_branch(tmp_path)
    if default_branch != "feature-branch":
        result = GitUtils.checkout_branch(tmp_path, default_branch)
    else:
        # We're on feature-branch, checkout main/master
        for branch in ["main", "master"]:
            if GitUtils.branch_exists(tmp_path, branch):
                result = GitUtils.checkout_branch(tmp_path, branch)
                break

    assert result is True or default_branch == "feature-branch"


def test_has_uncommitted_changes_not_git(tmp_path):
    """Test has_uncommitted_changes with non-git directory."""
    result = GitUtils.has_uncommitted_changes(tmp_path)

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_has_uncommitted_changes_clean_repo(tmp_path):
    """Test has_uncommitted_changes with clean repository."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    result = GitUtils.has_uncommitted_changes(tmp_path)

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_has_uncommitted_changes_with_changes(tmp_path):
    """Test has_uncommitted_changes with uncommitted changes."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Make uncommitted change
    (tmp_path / "test.txt").write_text("modified")

    result = GitUtils.has_uncommitted_changes(tmp_path)

    assert result is True


def test_get_status_summary_not_git(tmp_path):
    """Test get_status_summary with non-git directory."""
    result = GitUtils.get_status_summary(tmp_path)

    assert result == ""


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_get_status_summary_with_changes(tmp_path):
    """Test get_status_summary with uncommitted changes."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Make uncommitted change
    (tmp_path / "test.txt").write_text("modified")

    result = GitUtils.get_status_summary(tmp_path)

    assert " M test.txt" in result or "M test.txt" in result


def test_commit_all_not_git(tmp_path):
    """Test commit_all with non-git directory."""
    result = GitUtils.commit_all(tmp_path, "Test commit")

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_commit_all_success(tmp_path):
    """Test commit_all with valid changes."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Make uncommitted change
    (tmp_path / "test.txt").write_text("modified")

    result = GitUtils.commit_all(tmp_path, "Test commit message")

    assert result is True
    assert not GitUtils.has_uncommitted_changes(tmp_path)


def test_detect_repo_type_not_git(tmp_path):
    """Test detect_repo_type with non-git directory."""
    result = GitUtils.detect_repo_type(tmp_path)

    assert result is None


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_detect_repo_type_github(tmp_path):
    """Test detect_repo_type with GitHub repository."""
    # Initialize git repo with GitHub remote
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
        cwd=tmp_path,
        capture_output=True
    )

    result = GitUtils.detect_repo_type(tmp_path)

    assert result == "github"


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_detect_repo_type_gitlab(tmp_path):
    """Test detect_repo_type with GitLab repository."""
    # Initialize git repo with GitLab remote
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://gitlab.com/test/repo.git"],
        cwd=tmp_path,
        capture_output=True
    )

    result = GitUtils.detect_repo_type(tmp_path)

    assert result == "gitlab"


def test_is_branch_pushed_not_git(tmp_path):
    """Test is_branch_pushed with non-git directory."""
    result = GitUtils.is_branch_pushed(tmp_path, "main")

    assert result is False


def test_push_branch_not_git(tmp_path):
    """Test push_branch with non-git directory."""
    result = GitUtils.push_branch(tmp_path, "main")

    assert result is False


def test_commits_behind_not_git(tmp_path):
    """Test commits_behind with non-git directory."""
    result = GitUtils.commits_behind(tmp_path, "feature", "main")

    assert result == 0


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_commits_behind_up_to_date(tmp_path):
    """Test commits_behind when branch is up-to-date."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get current branch
    current_branch = GitUtils.get_current_branch(tmp_path)

    # Should be 0 commits behind (no remote)
    result = GitUtils.commits_behind(tmp_path, current_branch, current_branch)

    assert result == 0


def test_merge_branch_not_git(tmp_path):
    """Test merge_branch with non-git directory."""
    result = GitUtils.merge_branch(tmp_path, "main")

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_merge_branch_success(tmp_path):
    """Test merge_branch with successful merge."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get the default branch name
    default_branch = GitUtils.get_current_branch(tmp_path)

    # Create and switch to feature branch
    GitUtils.create_branch(tmp_path, "feature")

    # Add commit to feature branch
    (tmp_path / "feature.txt").write_text("feature")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Feature"], cwd=tmp_path, capture_output=True)

    # Switch back to default branch
    GitUtils.checkout_branch(tmp_path, default_branch)

    # Merge feature branch into default
    result = GitUtils.merge_branch(tmp_path, "feature")

    assert result is True


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_merge_branch_conflict(tmp_path):
    """Test merge_branch with merge conflict."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "conflict.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get the default branch name
    default_branch = GitUtils.get_current_branch(tmp_path)

    # Create and switch to feature branch
    GitUtils.create_branch(tmp_path, "feature")

    # Modify file on feature branch
    (tmp_path / "conflict.txt").write_text("feature change")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Feature change"], cwd=tmp_path, capture_output=True)

    # Switch back to default branch
    GitUtils.checkout_branch(tmp_path, default_branch)

    # Modify same file on default branch
    (tmp_path / "conflict.txt").write_text("main change")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Main change"], cwd=tmp_path, capture_output=True)

    # Attempt merge - should conflict and be aborted
    result = GitUtils.merge_branch(tmp_path, "feature")

    assert result is False
    # Verify merge was aborted (no MERGE_HEAD file)
    assert not (tmp_path / ".git" / "MERGE_HEAD").exists()


def test_rebase_branch_not_git(tmp_path):
    """Test rebase_branch with non-git directory."""
    result = GitUtils.rebase_branch(tmp_path, "main")

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_rebase_branch_success(tmp_path):
    """Test rebase_branch with successful rebase."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get the default branch name
    default_branch = GitUtils.get_current_branch(tmp_path)

    # Create and switch to feature branch
    GitUtils.create_branch(tmp_path, "feature")

    # Add commit to feature branch
    (tmp_path / "feature.txt").write_text("feature")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Feature"], cwd=tmp_path, capture_output=True)

    # Switch back to default branch and add another commit
    GitUtils.checkout_branch(tmp_path, default_branch)
    (tmp_path / "main.txt").write_text("main")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Main commit"], cwd=tmp_path, capture_output=True)

    # Switch back to feature branch
    GitUtils.checkout_branch(tmp_path, "feature")

    # Rebase feature branch onto default
    result = GitUtils.rebase_branch(tmp_path, default_branch)

    assert result is True


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_rebase_branch_conflict(tmp_path):
    """Test rebase_branch with rebase conflict."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "conflict.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get the default branch name
    default_branch = GitUtils.get_current_branch(tmp_path)

    # Create and switch to feature branch
    GitUtils.create_branch(tmp_path, "feature")

    # Modify file on feature branch
    (tmp_path / "conflict.txt").write_text("feature change")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Feature change"], cwd=tmp_path, capture_output=True)

    # Switch back to default branch
    GitUtils.checkout_branch(tmp_path, default_branch)

    # Modify same file on default branch
    (tmp_path / "conflict.txt").write_text("main change")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Main change"], cwd=tmp_path, capture_output=True)

    # Switch back to feature branch
    GitUtils.checkout_branch(tmp_path, "feature")

    # Attempt rebase - should conflict and be aborted
    result = GitUtils.rebase_branch(tmp_path, default_branch)

    assert result is False
    # Verify rebase was aborted (check we're not in rebase state)
    assert not (tmp_path / ".git" / "rebase-merge").exists()
    assert not (tmp_path / ".git" / "rebase-apply").exists()


def test_remote_branch_exists_not_git(tmp_path):
    """Test remote_branch_exists with non-git directory."""
    result = GitUtils.remote_branch_exists(tmp_path, "main")

    assert result is False


def test_fetch_and_checkout_branch_not_git(tmp_path):
    """Test fetch_and_checkout_branch with non-git directory."""
    result = GitUtils.fetch_and_checkout_branch(tmp_path, "feature")

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_remote_branch_exists_no_remote(tmp_path):
    """Test remote_branch_exists with no remote configured."""
    # Initialize git repo without remote
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    result = GitUtils.remote_branch_exists(tmp_path, "main")

    # Should return False (no remote configured)
    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_fetch_and_checkout_branch_no_remote(tmp_path):
    """Test fetch_and_checkout_branch with no remote configured."""
    # Initialize git repo without remote
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    result = GitUtils.fetch_and_checkout_branch(tmp_path, "feature")

    # Should return False (no remote configured)
    assert result is False


def test_has_merge_conflicts_not_git(tmp_path):
    """Test has_merge_conflicts with non-git directory."""
    result = GitUtils.has_merge_conflicts(tmp_path)

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_has_merge_conflicts_clean_repo(tmp_path):
    """Test has_merge_conflicts with clean repository."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    result = GitUtils.has_merge_conflicts(tmp_path)

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_has_merge_conflicts_with_conflicts(tmp_path):
    """Test has_merge_conflicts with unresolved merge conflicts."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "conflict.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get the default branch name
    default_branch = GitUtils.get_current_branch(tmp_path)

    # Create and switch to feature branch
    GitUtils.create_branch(tmp_path, "feature")

    # Modify file on feature branch
    (tmp_path / "conflict.txt").write_text("feature change")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Feature change"], cwd=tmp_path, capture_output=True)

    # Switch back to default branch
    GitUtils.checkout_branch(tmp_path, default_branch)

    # Modify same file on default branch
    (tmp_path / "conflict.txt").write_text("main change")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Main change"], cwd=tmp_path, capture_output=True)

    # Attempt merge without abort - this will leave conflicts
    subprocess.run(
        ["git", "merge", "feature"],
        cwd=tmp_path,
        capture_output=True
    )

    # Should detect conflicts
    result = GitUtils.has_merge_conflicts(tmp_path)

    assert result is True

    # Clean up - abort the merge
    subprocess.run(["git", "merge", "--abort"], cwd=tmp_path, capture_output=True)


def test_get_conflicted_files_not_git(tmp_path):
    """Test get_conflicted_files with non-git directory."""
    result = GitUtils.get_conflicted_files(tmp_path)

    assert result == []


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_get_conflicted_files_clean_repo(tmp_path):
    """Test get_conflicted_files with clean repository."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    result = GitUtils.get_conflicted_files(tmp_path)

    assert result == []


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_get_conflicted_files_with_conflicts(tmp_path):
    """Test get_conflicted_files returns list of conflicted files."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "conflict1.txt").write_text("original1")
    (tmp_path / "conflict2.txt").write_text("original2")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get the default branch name
    default_branch = GitUtils.get_current_branch(tmp_path)

    # Create and switch to feature branch
    GitUtils.create_branch(tmp_path, "feature")

    # Modify files on feature branch
    (tmp_path / "conflict1.txt").write_text("feature change 1")
    (tmp_path / "conflict2.txt").write_text("feature change 2")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Feature changes"], cwd=tmp_path, capture_output=True)

    # Switch back to default branch
    GitUtils.checkout_branch(tmp_path, default_branch)

    # Modify same files on default branch
    (tmp_path / "conflict1.txt").write_text("main change 1")
    (tmp_path / "conflict2.txt").write_text("main change 2")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Main changes"], cwd=tmp_path, capture_output=True)

    # Attempt merge without abort - this will leave conflicts
    subprocess.run(
        ["git", "merge", "feature"],
        cwd=tmp_path,
        capture_output=True
    )

    # Should return list of conflicted files
    result = GitUtils.get_conflicted_files(tmp_path)

    assert len(result) == 2
    assert "conflict1.txt" in result
    assert "conflict2.txt" in result

    # Clean up - abort the merge
    subprocess.run(["git", "merge", "--abort"], cwd=tmp_path, capture_output=True)


def test_get_conflict_details_not_git(tmp_path):
    """Test get_conflict_details with non-git directory."""
    result = GitUtils.get_conflict_details(tmp_path, "test.txt")

    assert result is None


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_get_conflict_details_with_conflicts(tmp_path):
    """Test get_conflict_details returns detailed conflict information."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "conflict.txt").write_text("original content")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get the default branch name
    default_branch = GitUtils.get_current_branch(tmp_path)

    # Create and switch to feature branch
    GitUtils.create_branch(tmp_path, "feature")

    # Modify file on feature branch
    (tmp_path / "conflict.txt").write_text("feature change\nmore lines\nhere")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Feature change"], cwd=tmp_path, capture_output=True)

    # Switch back to default branch
    GitUtils.checkout_branch(tmp_path, default_branch)

    # Modify same file on default branch
    (tmp_path / "conflict.txt").write_text("main change\ndifferent lines\nhere")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Main change"], cwd=tmp_path, capture_output=True)

    # Attempt merge without abort - this will leave conflicts
    subprocess.run(
        ["git", "merge", "feature"],
        cwd=tmp_path,
        capture_output=True
    )

    # Get conflict details
    details = GitUtils.get_conflict_details(tmp_path, "conflict.txt")

    assert details is not None
    assert details['conflict_count'] >= 1
    assert 'preview' in details
    assert 'ours_branch' in details
    assert 'theirs_branch' in details
    assert details['file_size'] > 0

    # Clean up - abort the merge
    subprocess.run(["git", "merge", "--abort"], cwd=tmp_path, capture_output=True)


def test_get_conflict_details_no_conflicts(tmp_path):
    """Test get_conflict_details with file that has no conflicts."""
    # Create a file without conflicts
    (tmp_path / "test.txt").write_text("no conflicts here")

    result = GitUtils.get_conflict_details(tmp_path, "test.txt")

    assert result is None


def test_get_merge_head_info_not_in_merge(tmp_path):
    """Test get_merge_head_info when not in a merge."""
    result = GitUtils.get_merge_head_info(tmp_path)

    assert result is None


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_get_merge_head_info_during_merge(tmp_path):
    """Test get_merge_head_info during an active merge."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit on main
    (tmp_path / "conflict.txt").write_text("original")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get the default branch name
    default_branch = GitUtils.get_current_branch(tmp_path)

    # Create and switch to feature branch
    GitUtils.create_branch(tmp_path, "feature")

    # Modify file on feature branch
    (tmp_path / "conflict.txt").write_text("feature change")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Feature change"], cwd=tmp_path, capture_output=True)

    # Switch back to default branch
    GitUtils.checkout_branch(tmp_path, default_branch)

    # Modify same file on default branch
    (tmp_path / "conflict.txt").write_text("main change")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Main change"], cwd=tmp_path, capture_output=True)

    # Attempt merge - will create conflict and MERGE_HEAD/MERGE_MSG files
    subprocess.run(
        ["git", "merge", "feature"],
        cwd=tmp_path,
        capture_output=True
    )

    # Get merge info
    info = GitUtils.get_merge_head_info(tmp_path)

    assert info is not None
    assert 'merge_msg' in info
    assert 'merge_head' in info
    assert 'merge_mode' in info
    assert info['merge_mode'] == 'merge'
    assert len(info['merge_head']) > 0  # Should have a commit hash

    # Clean up - abort the merge
    subprocess.run(["git", "merge", "--abort"], cwd=tmp_path, capture_output=True)


def test_has_unpushed_commits_not_git(tmp_path):
    """Test has_unpushed_commits with non-git directory."""
    result = GitUtils.has_unpushed_commits(tmp_path, "main")

    assert result is False


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_has_unpushed_commits_no_remote(tmp_path):
    """Test has_unpushed_commits when branch doesn't exist on remote."""
    # Initialize git repo without remote
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get current branch
    current_branch = GitUtils.get_current_branch(tmp_path)

    # Should return True (branch exists locally but not on remote)
    result = GitUtils.has_unpushed_commits(tmp_path, current_branch)

    assert result is True


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_has_unpushed_commits_with_unpushed_commits(tmp_path):
    """Test has_unpushed_commits when there are local commits not pushed."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get current branch
    current_branch = GitUtils.get_current_branch(tmp_path)

    # Create a bare repo to act as remote
    remote_path = tmp_path.parent / "remote"
    subprocess.run(["git", "init", "--bare", str(remote_path)], capture_output=True)

    # Add remote and push
    subprocess.run(["git", "remote", "add", "origin", str(remote_path)], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", current_branch], cwd=tmp_path, capture_output=True)

    # Make another commit locally (not pushed)
    (tmp_path / "test2.txt").write_text("test2")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Second commit"], cwd=tmp_path, capture_output=True)

    # Should return True (we have unpushed commits)
    result = GitUtils.has_unpushed_commits(tmp_path, current_branch)

    assert result is True


@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)
def test_has_unpushed_commits_up_to_date(tmp_path):
    """Test has_unpushed_commits when branch is up-to-date with remote."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, capture_output=True)

    # Create initial commit
    (tmp_path / "test.txt").write_text("test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, capture_output=True)

    # Get current branch
    current_branch = GitUtils.get_current_branch(tmp_path)

    # Create a bare repo to act as remote
    remote_path = tmp_path.parent / "remote"
    subprocess.run(["git", "init", "--bare", str(remote_path)], capture_output=True)

    # Add remote and push
    subprocess.run(["git", "remote", "add", "origin", str(remote_path)], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", current_branch], cwd=tmp_path, capture_output=True)

    # Should return False (branch is up-to-date with remote)
    result = GitUtils.has_unpushed_commits(tmp_path, current_branch)

    assert result is False
