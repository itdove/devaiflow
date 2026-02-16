"""Extended tests for release/permissions.py to improve coverage."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import subprocess
from devflow.release.permissions import (
    parse_git_remote,
    get_git_remote_url,
    check_github_permission,
    check_gitlab_permission,
    check_release_permission,
    Platform,
    PermissionLevel
)


def test_parse_git_remote_github_ssh():
    """Test parse_git_remote with GitHub SSH URL."""
    url = "git@github.com:owner/repo.git"
    platform, owner, repo = parse_git_remote(url)

    assert platform == Platform.GITHUB
    assert owner == "owner"
    assert repo == "repo"


def test_parse_git_remote_github_https():
    """Test parse_git_remote with GitHub HTTPS URL."""
    url = "https://github.com/owner/repo.git"
    platform, owner, repo = parse_git_remote(url)

    assert platform == Platform.GITHUB
    assert owner == "owner"
    assert repo == "repo"


def test_parse_git_remote_gitlab_ssh():
    """Test parse_git_remote with GitLab SSH URL."""
    url = "git@gitlab.example.com:group/project.git"
    platform, owner, repo = parse_git_remote(url)

    assert platform == Platform.GITLAB
    assert owner == "group"
    assert repo == "project"


def test_parse_git_remote_gitlab_https():
    """Test parse_git_remote with GitLab HTTPS URL."""
    url = "https://gitlab.example.com/group/subgroup/project.git"
    platform, owner, repo = parse_git_remote(url)

    assert platform == Platform.GITLAB
    assert owner == "group/subgroup"
    assert repo == "project"


def test_parse_git_remote_unknown():
    """Test parse_git_remote with unknown URL format."""
    url = "unknown://example.com/repo.git"
    platform, owner, repo = parse_git_remote(url)

    assert platform == Platform.UNKNOWN
    assert owner is None
    assert repo is None


def test_get_git_remote_url_success(tmp_path):
    """Test get_git_remote_url successfully gets remote URL."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="git@github.com:owner/repo.git\n"
        )

        result = get_git_remote_url(tmp_path)

        assert result == "git@github.com:owner/repo.git"


def test_get_git_remote_url_timeout(tmp_path):
    """Test get_git_remote_url handles timeout."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)

        result = get_git_remote_url(tmp_path)

        assert result is None


def test_check_github_permission_admin():
    """Test check_github_permission with admin permission."""
    with patch('subprocess.run') as mock_run:
        # Mock user API call
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"login": "testuser"}'),
            Mock(returncode=0, stdout='{"permission": "admin", "role_name": "admin"}')
        ]

        has_perm, level, msg = check_github_permission("owner", "repo")

        assert has_perm is True
        assert level == PermissionLevel.OWNER
        assert "testuser" in msg


def test_check_github_permission_maintain():
    """Test check_github_permission with maintain permission."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"login": "testuser"}'),
            Mock(returncode=0, stdout='{"permission": "write", "role_name": "maintain"}')
        ]

        has_perm, level, msg = check_github_permission("owner", "repo")

        assert has_perm is True
        assert level == PermissionLevel.MAINTAINER


def test_check_github_permission_write():
    """Test check_github_permission with write permission."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"login": "testuser"}'),
            Mock(returncode=0, stdout='{"permission": "write", "role_name": ""}')
        ]

        has_perm, level, msg = check_github_permission("owner", "repo")

        assert has_perm is False
        assert level == PermissionLevel.DEVELOPER


def test_check_github_permission_read():
    """Test check_github_permission with read permission."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"login": "testuser"}'),
            Mock(returncode=0, stdout='{"permission": "read", "role_name": ""}')
        ]

        has_perm, level, msg = check_github_permission("owner", "repo")

        assert has_perm is False
        assert level == PermissionLevel.REPORTER


def test_check_github_permission_auth_failed():
    """Test check_github_permission when auth fails."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=1, stdout='')

        has_perm, level, msg = check_github_permission("owner", "repo")

        assert has_perm is False
        assert level == PermissionLevel.NONE
        assert "authenticate" in msg.lower()


def test_check_github_permission_gh_not_found():
    """Test check_github_permission when gh CLI not found."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError()

        has_perm, level, msg = check_github_permission("owner", "repo")

        assert has_perm is False
        assert "GitHub CLI (gh) not found" in msg


def test_check_gitlab_permission_owner():
    """Test check_gitlab_permission with owner access."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"username": "testuser"}'),
            Mock(returncode=0, stdout='{"permissions": {"project_access": {"access_level": 50}}}')
        ]

        has_perm, level, msg = check_gitlab_permission("group", "repo")

        assert has_perm is True
        assert level == PermissionLevel.OWNER


def test_check_gitlab_permission_maintainer():
    """Test check_gitlab_permission with maintainer access."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"username": "testuser"}'),
            Mock(returncode=0, stdout='{"permissions": {"project_access": {"access_level": 40}}}')
        ]

        has_perm, level, msg = check_gitlab_permission("group", "repo")

        assert has_perm is True
        assert level == PermissionLevel.MAINTAINER


def test_check_gitlab_permission_developer():
    """Test check_gitlab_permission with developer access."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"username": "testuser"}'),
            Mock(returncode=0, stdout='{"permissions": {"project_access": {"access_level": 30}}}')
        ]

        has_perm, level, msg = check_gitlab_permission("group", "repo")

        assert has_perm is False
        assert level == PermissionLevel.DEVELOPER


def test_check_gitlab_permission_group_access():
    """Test check_gitlab_permission uses highest of project/group access."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = [
            Mock(returncode=0, stdout='{"username": "testuser"}'),
            Mock(returncode=0, stdout='{"permissions": {"project_access": {"access_level": 30}, "group_access": {"access_level": 40}}}')
        ]

        has_perm, level, msg = check_gitlab_permission("group", "repo")

        assert has_perm is True
        assert level == PermissionLevel.MAINTAINER


def test_check_gitlab_permission_glab_not_found():
    """Test check_gitlab_permission when glab CLI not found."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError()

        has_perm, level, msg = check_gitlab_permission("group", "repo")

        assert has_perm is False
        assert "GitLab CLI (glab) not found" in msg


def test_check_release_permission_no_remote(tmp_path):
    """Test check_release_permission when no git remote found."""
    with patch('devflow.release.permissions.get_git_remote_url', return_value=None):
        with pytest.raises(ValueError, match="Could not determine git remote URL"):
            check_release_permission(tmp_path)


def test_check_release_permission_unknown_platform(tmp_path):
    """Test check_release_permission with unknown platform."""
    with patch('devflow.release.permissions.get_git_remote_url', return_value="unknown://example.com/repo.git"):
        with pytest.raises(ValueError, match="Could not determine git platform"):
            check_release_permission(tmp_path)


def test_check_release_permission_github(tmp_path):
    """Test check_release_permission with GitHub repository."""
    with patch('devflow.release.permissions.get_git_remote_url', return_value="git@github.com:owner/repo.git"):
        with patch('devflow.release.permissions.check_github_permission') as mock_check:
            mock_check.return_value = (True, PermissionLevel.MAINTAINER, "Has access")

            has_perm, msg = check_release_permission(tmp_path)

            assert has_perm is True
            assert "Has access" in msg


def test_check_release_permission_gitlab(tmp_path):
    """Test check_release_permission with GitLab repository."""
    with patch('devflow.release.permissions.get_git_remote_url', return_value="git@gitlab.com:group/repo.git"):
        with patch('devflow.release.permissions.check_gitlab_permission') as mock_check:
            mock_check.return_value = (True, PermissionLevel.OWNER, "Has access")

            has_perm, msg = check_release_permission(tmp_path)

            assert has_perm is True
            assert "Has access" in msg
