"""Permission checking for release operations."""

import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from enum import Enum


class Platform(Enum):
    """Git hosting platform."""
    GITHUB = "github"
    GITLAB = "gitlab"
    UNKNOWN = "unknown"


class PermissionLevel(Enum):
    """Normalized permission levels across platforms."""
    OWNER = "owner"
    MAINTAINER = "maintainer"
    DEVELOPER = "developer"
    REPORTER = "reporter"
    GUEST = "guest"
    NONE = "none"


def parse_git_remote(remote_url: str) -> Tuple[Platform, Optional[str], Optional[str]]:
    """Parse git remote URL to extract platform and project path.

    Args:
        remote_url: Git remote URL (SSH or HTTPS)

    Returns:
        Tuple of (platform, owner, repo)

    Examples:
        git@github.com:owner/repo.git -> (GITHUB, "owner", "repo")
        git@gitlab.example.com:group/project.git -> (GITLAB, "group", "project")
        https://github.com/owner/repo.git -> (GITHUB, "owner", "repo")
    """
    # GitHub patterns
    github_ssh = r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$"
    github_https = r"https://github\.com/([^/]+)/(.+?)(?:\.git)?$"

    # GitLab patterns (supports any gitlab hostname)
    gitlab_ssh = r"git@(?:gitlab[^:]*):([^/]+(?:/[^/]+)*)/(.+?)(?:\.git)?$"
    gitlab_https = r"https://(?:gitlab[^/]*)/([^/]+(?:/[^/]+)*)/(.+?)(?:\.git)?$"

    # Try GitHub patterns
    for pattern in [github_ssh, github_https]:
        match = re.match(pattern, remote_url)
        if match:
            owner, repo = match.groups()
            return Platform.GITHUB, owner, repo

    # Try GitLab patterns
    for pattern in [gitlab_ssh, gitlab_https]:
        match = re.match(pattern, remote_url)
        if match:
            path, repo = match.groups()
            return Platform.GITLAB, path, repo

    return Platform.UNKNOWN, None, None


def get_git_remote_url(path: Path) -> Optional[str]:
    """Get the git remote URL for origin.

    Args:
        path: Repository path

    Returns:
        Remote URL or None if not found
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def check_github_permission(owner: str, repo: str) -> Tuple[bool, PermissionLevel, str]:
    """Check GitHub repository permission for current user.

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        Tuple of (has_permission, permission_level, message)
    """
    try:
        # Get current user
        result = subprocess.run(
            ["gh", "api", "/user"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return False, PermissionLevel.NONE, "Failed to authenticate with GitHub CLI"

        import json
        user_data = json.loads(result.stdout)
        username = user_data.get("login")

        if not username:
            return False, PermissionLevel.NONE, "Could not determine GitHub username"

        # Check user's permission on repository
        result = subprocess.run(
            ["gh", "api", f"/repos/{owner}/{repo}/collaborators/{username}/permission"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return False, PermissionLevel.NONE, f"Failed to check permissions: {result.stderr}"

        perm_data = json.loads(result.stdout)
        permission = perm_data.get("permission", "none")
        role_name = perm_data.get("role_name", "")

        # Map GitHub permissions to our enum
        # Note: "maintain" role shows as "write" in permission field but has role_name="maintain"
        if permission == "admin":
            level = PermissionLevel.OWNER
        elif role_name == "maintain" or permission == "maintain":
            level = PermissionLevel.MAINTAINER
        elif permission == "write":
            level = PermissionLevel.DEVELOPER
        elif permission == "read":
            level = PermissionLevel.REPORTER
        else:
            level = PermissionLevel.NONE

        # Require maintainer or owner for releases
        has_perm = level in [PermissionLevel.OWNER, PermissionLevel.MAINTAINER]

        if has_perm:
            msg = f"User '{username}' has {level.value} access"
        else:
            msg = f"User '{username}' has {level.value} access (maintainer or admin required)"

        return has_perm, level, msg

    except subprocess.TimeoutExpired:
        return False, PermissionLevel.NONE, "GitHub API request timed out"
    except FileNotFoundError:
        return False, PermissionLevel.NONE, "GitHub CLI (gh) not found. Install from https://cli.github.com/"
    except json.JSONDecodeError as e:
        return False, PermissionLevel.NONE, f"Failed to parse GitHub API response: {e}"
    except Exception as e:
        return False, PermissionLevel.NONE, f"Unexpected error checking GitHub permissions: {e}"


def check_gitlab_permission(project_path: str, repo: str) -> Tuple[bool, PermissionLevel, str]:
    """Check GitLab repository permission for current user.

    Args:
        project_path: Project path (e.g., "myorg/myproject" or "group/subgroup")
        repo: Repository name

    Returns:
        Tuple of (has_permission, permission_level, message)
    """
    try:
        # Construct full project path
        full_path = f"{project_path}/{repo}"
        # URL encode the path (/ becomes %2F)
        encoded_path = full_path.replace("/", "%2F")

        # Get current user
        result = subprocess.run(
            ["glab", "api", "user"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return False, PermissionLevel.NONE, "Failed to authenticate with GitLab CLI"

        import json
        user_data = json.loads(result.stdout)
        username = user_data.get("username")

        if not username:
            return False, PermissionLevel.NONE, "Could not determine GitLab username"

        # Get project permissions
        result = subprocess.run(
            ["glab", "api", f"projects/{encoded_path}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return False, PermissionLevel.NONE, f"Failed to access project: {result.stderr}"

        project_data = json.loads(result.stdout)
        permissions = project_data.get("permissions", {})

        # Check both project_access and group_access
        project_access = permissions.get("project_access") or {}
        group_access = permissions.get("group_access") or {}

        # Get highest access level
        project_level = project_access.get("access_level", 0)
        group_level = group_access.get("access_level", 0)
        access_level = max(project_level, group_level)

        # Map GitLab access levels to our enum
        # 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer, 50=Owner
        if access_level >= 50:
            level = PermissionLevel.OWNER
        elif access_level >= 40:
            level = PermissionLevel.MAINTAINER
        elif access_level >= 30:
            level = PermissionLevel.DEVELOPER
        elif access_level >= 20:
            level = PermissionLevel.REPORTER
        elif access_level >= 10:
            level = PermissionLevel.GUEST
        else:
            level = PermissionLevel.NONE

        # Require maintainer or owner for releases
        has_perm = level in [PermissionLevel.OWNER, PermissionLevel.MAINTAINER]

        if has_perm:
            msg = f"User '{username}' has {level.value} access (level {access_level})"
        else:
            msg = f"User '{username}' has {level.value} access (level {access_level}). Maintainer (40) or Owner (50) required."

        return has_perm, level, msg

    except subprocess.TimeoutExpired:
        return False, PermissionLevel.NONE, "GitLab API request timed out"
    except FileNotFoundError:
        return False, PermissionLevel.NONE, "GitLab CLI (glab) not found. Install from https://gitlab.com/gitlab-org/cli"
    except json.JSONDecodeError as e:
        return False, PermissionLevel.NONE, f"Failed to parse GitLab API response: {e}"
    except Exception as e:
        return False, PermissionLevel.NONE, f"Unexpected error checking GitLab permissions: {e}"


def check_release_permission(repo_path: Path) -> Tuple[bool, str]:
    """Check if current user has permission to create releases.

    This function checks repository permissions across GitHub and GitLab,
    requiring Maintainer or Owner access to proceed with releases.

    Args:
        repo_path: Path to git repository

    Returns:
        Tuple of (has_permission, message)

    Raises:
        ValueError: If repository platform cannot be determined
    """
    # Get git remote URL
    remote_url = get_git_remote_url(repo_path)
    if not remote_url:
        raise ValueError(
            "Could not determine git remote URL. "
            "Ensure you are in a git repository with an 'origin' remote."
        )

    # Parse platform and project info
    platform, owner, repo = parse_git_remote(remote_url)

    if platform == Platform.UNKNOWN:
        raise ValueError(
            f"Could not determine git platform from remote URL: {remote_url}. "
            "Supported platforms: GitHub, GitLab"
        )

    # Check permissions based on platform
    if platform == Platform.GITHUB:
        has_perm, level, msg = check_github_permission(owner, repo)
    elif platform == Platform.GITLAB:
        has_perm, level, msg = check_gitlab_permission(owner, repo)
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    return has_perm, msg
