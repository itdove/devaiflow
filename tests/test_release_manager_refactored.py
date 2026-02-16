"""Tests for refactored release/manager.py with improved exception handling."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess


def test_get_current_branch_success(tmp_path):
    """Test getting current branch successfully."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="main\n")

        result = manager.get_current_branch()

        assert result == "main"
        mock_run.assert_called_once()


def test_get_current_branch_not_git_repo(tmp_path):
    """Test get_current_branch returns None for non-git repo."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=128, stdout="")

        result = manager.get_current_branch()

        assert result is None


def test_get_current_branch_timeout(tmp_path):
    """Test get_current_branch raises on timeout."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

        with pytest.raises(subprocess.TimeoutExpired):
            manager.get_current_branch()


def test_get_current_branch_git_not_installed(tmp_path):
    """Test get_current_branch raises when git not installed."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError("git not found")

        with pytest.raises(FileNotFoundError):
            manager.get_current_branch()


def test_has_uncommitted_changes_true(tmp_path):
    """Test has_uncommitted_changes returns True when changes exist."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="M file.py\n")

        result = manager.has_uncommitted_changes()

        assert result is True


def test_has_uncommitted_changes_false(tmp_path):
    """Test has_uncommitted_changes returns False when clean."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="")

        result = manager.has_uncommitted_changes()

        assert result is False


def test_has_uncommitted_changes_timeout(tmp_path):
    """Test has_uncommitted_changes raises on timeout."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

        with pytest.raises(subprocess.TimeoutExpired):
            manager.has_uncommitted_changes()


def test_has_uncommitted_changes_git_fails(tmp_path):
    """Test has_uncommitted_changes raises on git failure."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with pytest.raises(subprocess.CalledProcessError):
            manager.has_uncommitted_changes()


def test_get_latest_tag_success(tmp_path):
    """Test getting latest tag successfully."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="v1.2.3\n")

        result = manager.get_latest_tag()

        assert result == "v1.2.3"


def test_get_latest_tag_no_tags(tmp_path):
    """Test get_latest_tag returns None when no tags exist."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=128, stdout="")

        result = manager.get_latest_tag()

        assert result is None


def test_get_latest_tag_timeout(tmp_path):
    """Test get_latest_tag raises on timeout."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

        with pytest.raises(subprocess.TimeoutExpired):
            manager.get_latest_tag()


def test_analyze_commits_since_tag_success(tmp_path):
    """Test analyzing commits since tag."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123 feat: add new feature\ndef456 fix: bug fix\n"
        )

        result = manager.analyze_commits_since_tag("v1.0.0")

        assert len(result['features']) == 1
        assert len(result['fixes']) == 1
        assert "feat: add new feature" in result['features'][0]
        assert "fix: bug fix" in result['fixes'][0]


def test_analyze_commits_since_tag_breaking_changes(tmp_path):
    """Test analyzing commits with breaking changes."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123 feat!: BREAKING CHANGE: remove API\n"
        )

        result = manager.analyze_commits_since_tag("v1.0.0")

        assert len(result['breaking']) == 1


def test_analyze_commits_since_tag_timeout(tmp_path):
    """Test analyze_commits_since_tag raises on timeout."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)

        with pytest.raises(subprocess.TimeoutExpired):
            manager.analyze_commits_since_tag("v1.0.0")


def test_get_commits_with_prs_success(tmp_path):
    """Test getting commits with PR information."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123|||Merge pull request #42 from user/branch|||PR body|||COMMIT_DELIMITER|||"
        )

        result = manager.get_commits_with_prs("v1.0.0")

        assert len(result) == 1
        assert result[0]['hash'] == "abc123"
        assert result[0]['pr_mr'] is not None
        assert result[0]['pr_mr']['type'] == 'github_pr'
        assert result[0]['pr_mr']['number'] == '42'


def test_get_commits_with_prs_gitlab_mr(tmp_path):
    """Test getting commits with GitLab MR information."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123|||Merge branch 'feature'|||See merge request !123|||COMMIT_DELIMITER|||"
        )

        result = manager.get_commits_with_prs("v1.0.0")

        assert len(result) == 1
        assert result[0]['pr_mr'] is not None
        assert result[0]['pr_mr']['type'] == 'gitlab_mr'
        assert result[0]['pr_mr']['number'] == '123'


def test_get_commits_with_prs_timeout(tmp_path):
    """Test get_commits_with_prs raises on timeout."""
    from devflow.release.manager import ReleaseManager

    manager = ReleaseManager(repo_path=tmp_path)

    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("git", 30)

        with pytest.raises(subprocess.TimeoutExpired):
            manager.get_commits_with_prs("v1.0.0")


def test_extract_changelog_for_version_success(tmp_path):
    """Test extracting changelog for a version."""
    from devflow.release.manager import ReleaseManager
    from devflow.release.version import Version

    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("""
# Changelog

## [1.2.0] - 2024-01-15
### Added
- New feature A
- New feature B

## [1.1.0] - 2024-01-01
### Fixed
- Bug fix
    """)

    manager = ReleaseManager(repo_path=tmp_path)
    manager.changelog_file = changelog_file

    result = manager.extract_changelog_for_version(Version(1, 2, 0))

    assert result is not None
    assert "New feature A" in result
    assert "New feature B" in result


def test_extract_changelog_for_version_not_found(tmp_path):
    """Test extracting changelog for non-existent version."""
    from devflow.release.manager import ReleaseManager
    from devflow.release.version import Version

    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("# Changelog\n")

    manager = ReleaseManager(repo_path=tmp_path)
    manager.changelog_file = changelog_file

    result = manager.extract_changelog_for_version(Version(99, 99, 99))

    assert result is None


def test_extract_changelog_for_version_file_not_found(tmp_path):
    """Test extracting changelog when file doesn't exist."""
    from devflow.release.manager import ReleaseManager
    from devflow.release.version import Version

    manager = ReleaseManager(repo_path=tmp_path)
    manager.changelog_file = tmp_path / "nonexistent.md"

    result = manager.extract_changelog_for_version(Version(1, 0, 0))

    assert result is None


def test_extract_changelog_for_version_permission_error(tmp_path):
    """Test extracting changelog raises on permission error."""
    from devflow.release.manager import ReleaseManager
    from devflow.release.version import Version

    changelog_file = tmp_path / "CHANGELOG.md"
    changelog_file.write_text("# Changelog\n")

    manager = ReleaseManager(repo_path=tmp_path)
    manager.changelog_file = changelog_file

    with patch.object(Path, 'read_text') as mock_read:
        mock_read.side_effect = OSError("Permission denied")

        with pytest.raises(OSError):
            manager.extract_changelog_for_version(Version(1, 0, 0))
