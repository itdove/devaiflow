"""Git remote detection utilities for issue tracker integration.

This module provides utilities to detect and extract issue tracker information
from git remotes, prioritizing upstream over origin for fork workflows.
"""

import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse


class GitRemoteDetector:
    """Detects and extracts issue tracker information from git remotes."""

    # Supported hosting platforms
    GITHUB_HOSTS = {'github.com'}
    GITLAB_HOSTS = {'gitlab.com'}

    # Remote priority for fork workflows
    REMOTE_PRIORITY = ['upstream', 'origin']

    def __init__(self, repo_path: Optional[str] = None):
        """Initialize detector for a repository.

        Args:
            repo_path: Path to git repository. Defaults to current directory.
        """
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()

    def get_remote_url(self, remote_name: Optional[str] = None) -> Optional[str]:
        """Get URL for a specific remote or best available remote.

        Args:
            remote_name: Specific remote to query (e.g., 'origin', 'upstream').
                        If None, uses priority order: upstream → origin

        Returns:
            Remote URL if found, None otherwise
        """
        if remote_name:
            return self._get_remote_url_by_name(remote_name)

        # Try remotes in priority order
        for remote in self.REMOTE_PRIORITY:
            url = self._get_remote_url_by_name(remote)
            if url:
                return url

        return None

    def _get_remote_url_by_name(self, remote_name: str) -> Optional[str]:
        """Get URL for a specific remote name.

        Args:
            remote_name: Remote name (e.g., 'origin')

        Returns:
            Remote URL if found, None otherwise
        """
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', remote_name],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def parse_repository_info(self, url: Optional[str] = None) -> Optional[Tuple[str, str, str]]:
        """Parse repository information from remote URL.

        Args:
            url: Remote URL to parse. If None, uses get_remote_url()

        Returns:
            Tuple of (platform, owner, repo) if parsed successfully
            - platform: 'github', 'gitlab', etc.
            - owner: Repository owner/organization
            - repo: Repository name

            Returns None if URL cannot be parsed or platform is unsupported.

        Examples:
            >>> detector = GitRemoteDetector()
            >>> detector.parse_repository_info('https://github.com/owner/repo.git')
            ('github', 'owner', 'repo')
            >>> detector.parse_repository_info('git@github.com:owner/repo.git')
            ('github', 'owner', 'repo')
        """
        if url is None:
            url = self.get_remote_url()

        if not url:
            return None

        # Handle SSH URLs (git@host:owner/repo.git)
        ssh_match = re.match(r'^git@([^:]+):(.+)/(.+?)(?:\.git)?$', url)
        if ssh_match:
            host, owner, repo = ssh_match.groups()
            platform = self._host_to_platform(host)
            if platform:
                return (platform, owner, repo)

        # Handle HTTPS URLs
        try:
            parsed = urlparse(url)
            host = parsed.netloc
            platform = self._host_to_platform(host)

            if platform and parsed.path:
                # Remove leading slash and .git suffix
                path = parsed.path.lstrip('/')
                if path.endswith('.git'):
                    path = path[:-4]

                # Split into owner/repo
                parts = path.split('/')
                if len(parts) >= 2:
                    owner, repo = parts[0], parts[1]
                    return (platform, owner, repo)
        except Exception:
            pass

        return None

    def _host_to_platform(self, host: str) -> Optional[str]:
        """Map hostname to platform name.

        Supports both public instances (github.com, gitlab.com) and
        enterprise/self-hosted instances (github.enterprise.com, gitlab.cee.redhat.com, etc.).

        Args:
            host: Hostname (e.g., 'github.com', 'gitlab.cee.redhat.com')

        Returns:
            Platform name ('github', 'gitlab') or None if unsupported

        Examples:
            >>> detector._host_to_platform('github.com')
            'github'
            >>> detector._host_to_platform('github.enterprise.com')
            'github'
            >>> detector._host_to_platform('gitlab.cee.redhat.com')
            'gitlab'
        """
        host_lower = host.lower()
        if 'github' in host_lower:
            return 'github'
        elif 'gitlab' in host_lower:
            return 'gitlab'
        return None

    def get_github_repository(self) -> Optional[str]:
        """Get GitHub repository in owner/repo format.

        Returns:
            Repository string like 'owner/repo' if this is a GitHub repository,
            None otherwise
        """
        info = self.parse_repository_info()
        if info and info[0] == 'github':
            _, owner, repo = info
            return f"{owner}/{repo}"
        return None

    def get_gitlab_repository(self) -> Optional[str]:
        """Get GitLab repository in owner/repo format.

        Returns:
            Repository string like 'owner/repo' if this is a GitLab repository,
            None otherwise
        """
        info = self.parse_repository_info()
        if info and info[0] == 'gitlab':
            _, owner, repo = info
            return f"{owner}/{repo}"
        return None

    def list_all_remotes(self) -> dict[str, str]:
        """List all remotes and their URLs.

        Returns:
            Dictionary mapping remote names to URLs
        """
        remotes = {}
        try:
            result = subprocess.run(
                ['git', 'remote', '-v'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    # Format: "origin  https://... (fetch)"
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        url = parts[1]
                        # Only store fetch URLs (avoid duplicates)
                        if parts[-1] == '(fetch)':
                            remotes[name] = url
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return remotes


def get_project_remote_url(repo_path: Optional[str] = None) -> Optional[str]:
    """Get remote URL for issue tracking.

    Convenience function that prioritizes upstream over origin for fork workflows.

    Args:
        repo_path: Path to git repository. Defaults to current directory.

    Returns:
        Remote URL if found, None otherwise

    Priority:
        1. upstream - for forked repos (main project where issues live)
        2. origin - for non-forked repos
    """
    detector = GitRemoteDetector(repo_path)
    return detector.get_remote_url()


def get_github_repository(repo_path: Optional[str] = None) -> Optional[str]:
    """Get GitHub repository in owner/repo format.

    Convenience function for GitHub repository detection.

    Args:
        repo_path: Path to git repository. Defaults to current directory.

    Returns:
        Repository string like 'owner/repo' if this is a GitHub repository,
        None otherwise
    """
    detector = GitRemoteDetector(repo_path)
    return detector.get_github_repository()


def get_gitlab_repository(repo_path: Optional[str] = None) -> Optional[str]:
    """Get GitLab repository in owner/repo format.

    Convenience function for GitLab repository detection.

    Args:
        repo_path: Path to git repository. Defaults to current directory.

    Returns:
        Repository string like 'owner/repo' if this is a GitLab repository,
        None otherwise
    """
    detector = GitRemoteDetector(repo_path)
    return detector.get_gitlab_repository()
