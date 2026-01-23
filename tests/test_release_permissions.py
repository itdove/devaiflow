"""Tests for release permission checking."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock

from devflow.release.permissions import (
    Platform,
    PermissionLevel,
    parse_git_remote,
    get_git_remote_url,
    check_github_permission,
    check_gitlab_permission,
    check_release_permission,
)


class TestParseGitRemote:
    """Test parsing git remote URLs."""

    def test_parse_github_ssh(self):
        """Test parsing GitHub SSH URL."""
        platform, owner, repo = parse_git_remote("git@github.com:owner/repo.git")
        assert platform == Platform.GITHUB
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_github_ssh_without_git_suffix(self):
        """Test parsing GitHub SSH URL without .git suffix."""
        platform, owner, repo = parse_git_remote("git@github.com:owner/repo")
        assert platform == Platform.GITHUB
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_github_https(self):
        """Test parsing GitHub HTTPS URL."""
        platform, owner, repo = parse_git_remote("https://github.com/owner/repo.git")
        assert platform == Platform.GITHUB
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_github_https_without_git_suffix(self):
        """Test parsing GitHub HTTPS URL without .git suffix."""
        platform, owner, repo = parse_git_remote("https://github.com/owner/repo")
        assert platform == Platform.GITHUB
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_gitlab_ssh(self):
        """Test parsing GitLab SSH URL."""
        platform, owner, repo = parse_git_remote("git@gitlab.com:group/project.git")
        assert platform == Platform.GITLAB
        assert owner == "group"
        assert repo == "project"

    def test_parse_gitlab_ssh_with_subgroup(self):
        """Test parsing GitLab SSH URL with subgroups."""
        platform, owner, repo = parse_git_remote("git@gitlab.com:group/subgroup/project.git")
        assert platform == Platform.GITLAB
        assert owner == "group/subgroup"
        assert repo == "project"

    def test_parse_gitlab_custom_hostname(self):
        """Test parsing GitLab URL with custom hostname."""
        platform, owner, repo = parse_git_remote("git@gitlab.example.com:workspace/devflow.git")
        assert platform == Platform.GITLAB
        assert owner == "workspace"
        assert repo == "devflow"

    def test_parse_gitlab_https(self):
        """Test parsing GitLab HTTPS URL."""
        platform, owner, repo = parse_git_remote("https://gitlab.com/group/project.git")
        assert platform == Platform.GITLAB
        assert owner == "group"
        assert repo == "project"

    def test_parse_unknown_url(self):
        """Test parsing unknown URL format."""
        platform, owner, repo = parse_git_remote("https://example.com/repo")
        assert platform == Platform.UNKNOWN
        assert owner is None
        assert repo is None


class TestGetGitRemoteUrl:
    """Test getting git remote URL."""

    def test_get_remote_url_success(self, monkeypatch, tmp_path):
        """Test successfully getting remote URL."""
        # Mock subprocess to return a URL
        def mock_run(*args, **kwargs):
            result = Mock()
            result.returncode = 0
            result.stdout = "git@github.com:owner/repo.git\n"
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        url = get_git_remote_url(tmp_path)
        assert url == "git@github.com:owner/repo.git"

    def test_get_remote_url_not_git_repo(self, monkeypatch, tmp_path):
        """Test getting remote URL when not a git repo."""
        def mock_run(*args, **kwargs):
            result = Mock()
            result.returncode = 1
            result.stdout = ""
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        url = get_git_remote_url(tmp_path)
        assert url is None

    def test_get_remote_url_timeout(self, monkeypatch, tmp_path):
        """Test timeout when getting remote URL."""
        def mock_run(*args, **kwargs):
            import subprocess
            raise subprocess.TimeoutExpired("git", 5)

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        url = get_git_remote_url(tmp_path)
        assert url is None


class TestCheckGitHubPermission:
    """Test GitHub permission checking."""

    def test_github_admin_permission(self, monkeypatch):
        """Test user with admin permission."""
        calls = []

        def mock_run(cmd, *args, **kwargs):
            calls.append(cmd)
            result = Mock()
            result.returncode = 0

            if "/user" in cmd:
                result.stdout = json.dumps({"login": "testuser"})
            else:  # permission check
                result.stdout = json.dumps({
                    "permission": "admin",
                    "role_name": "admin"
                })
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_github_permission("owner", "repo")
        assert has_perm is True
        assert level == PermissionLevel.OWNER
        assert "testuser" in msg
        assert "owner" in msg.lower()

    def test_github_maintain_permission(self, monkeypatch):
        """Test user with maintain permission."""
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.returncode = 0

            if "/user" in cmd:
                result.stdout = json.dumps({"login": "testuser"})
            else:  # permission check
                result.stdout = json.dumps({
                    "permission": "write",
                    "role_name": "maintain"
                })
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_github_permission("owner", "repo")
        assert has_perm is True
        assert level == PermissionLevel.MAINTAINER
        assert "testuser" in msg

    def test_github_write_permission(self, monkeypatch):
        """Test user with write permission (insufficient)."""
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.returncode = 0

            if "/user" in cmd:
                result.stdout = json.dumps({"login": "testuser"})
            else:  # permission check
                result.stdout = json.dumps({
                    "permission": "write",
                    "role_name": "write"
                })
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_github_permission("owner", "repo")
        assert has_perm is False
        assert level == PermissionLevel.DEVELOPER
        assert "required" in msg.lower()

    def test_github_read_permission(self, monkeypatch):
        """Test user with read permission (insufficient)."""
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.returncode = 0

            if "/user" in cmd:
                result.stdout = json.dumps({"login": "testuser"})
            else:  # permission check
                result.stdout = json.dumps({
                    "permission": "read",
                    "role_name": "read"
                })
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_github_permission("owner", "repo")
        assert has_perm is False
        assert level == PermissionLevel.REPORTER

    def test_github_cli_not_found(self, monkeypatch):
        """Test when GitHub CLI is not installed."""
        def mock_run(*args, **kwargs):
            raise FileNotFoundError("gh not found")

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_github_permission("owner", "repo")
        assert has_perm is False
        assert level == PermissionLevel.NONE
        assert "not found" in msg.lower()


class TestCheckGitLabPermission:
    """Test GitLab permission checking."""

    def test_gitlab_owner_permission(self, monkeypatch):
        """Test user with owner permission (access level 50)."""
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.returncode = 0

            if "user" in cmd:
                result.stdout = json.dumps({"username": "testuser"})
            else:  # project check
                result.stdout = json.dumps({
                    "permissions": {
                        "project_access": {"access_level": 50},
                        "group_access": None
                    }
                })
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_gitlab_permission("group", "project")
        assert has_perm is True
        assert level == PermissionLevel.OWNER
        assert "testuser" in msg
        assert "50" in msg

    def test_gitlab_maintainer_permission(self, monkeypatch):
        """Test user with maintainer permission (access level 40)."""
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.returncode = 0

            if "user" in cmd:
                result.stdout = json.dumps({"username": "testuser"})
            else:  # project check
                result.stdout = json.dumps({
                    "permissions": {
                        "project_access": {"access_level": 40},
                        "group_access": None
                    }
                })
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_gitlab_permission("group", "project")
        assert has_perm is True
        assert level == PermissionLevel.MAINTAINER
        assert "40" in msg

    def test_gitlab_developer_permission(self, monkeypatch):
        """Test user with developer permission (insufficient)."""
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.returncode = 0

            if "user" in cmd:
                result.stdout = json.dumps({"username": "testuser"})
            else:  # project check
                result.stdout = json.dumps({
                    "permissions": {
                        "project_access": {"access_level": 30},
                        "group_access": None
                    }
                })
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_gitlab_permission("group", "project")
        assert has_perm is False
        assert level == PermissionLevel.DEVELOPER
        assert "required" in msg.lower()

    def test_gitlab_group_access(self, monkeypatch):
        """Test GitLab with group-level access."""
        def mock_run(cmd, *args, **kwargs):
            result = Mock()
            result.returncode = 0

            if "user" in cmd:
                result.stdout = json.dumps({"username": "testuser"})
            else:  # project check - group access is higher
                result.stdout = json.dumps({
                    "permissions": {
                        "project_access": {"access_level": 30},
                        "group_access": {"access_level": 40}
                    }
                })
            return result

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_gitlab_permission("group", "project")
        assert has_perm is True
        assert level == PermissionLevel.MAINTAINER

    def test_gitlab_cli_not_found(self, monkeypatch):
        """Test when GitLab CLI is not installed."""
        def mock_run(*args, **kwargs):
            raise FileNotFoundError("glab not found")

        import subprocess
        monkeypatch.setattr(subprocess, "run", mock_run)

        has_perm, level, msg = check_gitlab_permission("group", "project")
        assert has_perm is False
        assert level == PermissionLevel.NONE
        assert "not found" in msg.lower()


class TestCheckReleasePermission:
    """Test end-to-end release permission checking."""

    def test_release_permission_github_allowed(self, monkeypatch, tmp_path):
        """Test release permission check for GitHub with sufficient access."""
        # Mock get_git_remote_url
        def mock_get_remote(path):
            return "git@github.com:owner/repo.git"

        # Mock GitHub permission check
        def mock_github_check(owner, repo):
            return True, PermissionLevel.OWNER, "User has admin access"

        import devflow.release.permissions as perms
        monkeypatch.setattr(perms, "get_git_remote_url", mock_get_remote)
        monkeypatch.setattr(perms, "check_github_permission", mock_github_check)

        has_perm, msg = check_release_permission(tmp_path)
        assert has_perm is True
        assert "admin" in msg.lower()

    def test_release_permission_gitlab_allowed(self, monkeypatch, tmp_path):
        """Test release permission check for GitLab with sufficient access."""
        def mock_get_remote(path):
            return "git@gitlab.com:group/project.git"

        def mock_gitlab_check(owner, repo):
            return True, PermissionLevel.MAINTAINER, "User has maintainer access"

        import devflow.release.permissions as perms
        monkeypatch.setattr(perms, "get_git_remote_url", mock_get_remote)
        monkeypatch.setattr(perms, "check_gitlab_permission", mock_gitlab_check)

        has_perm, msg = check_release_permission(tmp_path)
        assert has_perm is True
        assert "maintainer" in msg.lower()

    def test_release_permission_denied(self, monkeypatch, tmp_path):
        """Test release permission check with insufficient access."""
        def mock_get_remote(path):
            return "git@github.com:owner/repo.git"

        def mock_github_check(owner, repo):
            return False, PermissionLevel.DEVELOPER, "User has write access (maintainer required)"

        import devflow.release.permissions as perms
        monkeypatch.setattr(perms, "get_git_remote_url", mock_get_remote)
        monkeypatch.setattr(perms, "check_github_permission", mock_github_check)

        has_perm, msg = check_release_permission(tmp_path)
        assert has_perm is False
        assert "required" in msg.lower()

    def test_release_permission_no_remote(self, monkeypatch, tmp_path):
        """Test release permission check when no remote is configured."""
        def mock_get_remote(path):
            return None

        import devflow.release.permissions as perms
        monkeypatch.setattr(perms, "get_git_remote_url", mock_get_remote)

        with pytest.raises(ValueError, match="Could not determine git remote URL"):
            check_release_permission(tmp_path)

    def test_release_permission_unknown_platform(self, monkeypatch, tmp_path):
        """Test release permission check with unknown platform."""
        def mock_get_remote(path):
            return "https://example.com/repo.git"

        import devflow.release.permissions as perms
        monkeypatch.setattr(perms, "get_git_remote_url", mock_get_remote)

        with pytest.raises(ValueError, match="Could not determine git platform"):
            check_release_permission(tmp_path)
