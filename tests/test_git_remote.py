"""Tests for git remote detection utilities."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devflow.utils.git_remote import (
    GitRemoteDetector,
    get_github_repository,
    get_gitlab_repository,
    get_project_remote_url,
)


class TestGitRemoteDetector:
    """Tests for GitRemoteDetector class."""

    def test_init_with_path(self):
        """Test initialization with explicit path."""
        detector = GitRemoteDetector('/path/to/repo')
        assert detector.repo_path == Path('/path/to/repo')

    def test_init_without_path(self):
        """Test initialization with default path."""
        detector = GitRemoteDetector()
        assert detector.repo_path == Path.cwd()

    @patch('subprocess.run')
    def test_get_remote_url_by_name_success(self, mock_run):
        """Test getting remote URL by name."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='https://github.com/owner/repo.git\n'
        )

        detector = GitRemoteDetector()
        url = detector._get_remote_url_by_name('origin')

        assert url == 'https://github.com/owner/repo.git'
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ['git', 'remote', 'get-url', 'origin']

    @patch('subprocess.run')
    def test_get_remote_url_by_name_not_found(self, mock_run):
        """Test getting remote URL when remote doesn't exist."""
        mock_run.return_value = MagicMock(returncode=128)

        detector = GitRemoteDetector()
        url = detector._get_remote_url_by_name('nonexistent')

        assert url is None

    @patch('subprocess.run')
    def test_get_remote_url_by_name_timeout(self, mock_run):
        """Test timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired('git', 5)

        detector = GitRemoteDetector()
        url = detector._get_remote_url_by_name('origin')

        assert url is None

    @patch('subprocess.run')
    def test_get_remote_url_priority_upstream_exists(self, mock_run):
        """Test that upstream is preferred when it exists."""
        def side_effect(*args, **kwargs):
            remote_name = args[0][3]
            if remote_name == 'upstream':
                return MagicMock(
                    returncode=0,
                    stdout='https://github.com/main/repo.git\n'
                )
            elif remote_name == 'origin':
                return MagicMock(
                    returncode=0,
                    stdout='https://github.com/fork/repo.git\n'
                )
            return MagicMock(returncode=128)

        mock_run.side_effect = side_effect

        detector = GitRemoteDetector()
        url = detector.get_remote_url()

        # Should get upstream, not origin
        assert url == 'https://github.com/main/repo.git'

    @patch('subprocess.run')
    def test_get_remote_url_priority_origin_fallback(self, mock_run):
        """Test that origin is used when upstream doesn't exist."""
        def side_effect(*args, **kwargs):
            remote_name = args[0][3]
            if remote_name == 'upstream':
                return MagicMock(returncode=128)
            elif remote_name == 'origin':
                return MagicMock(
                    returncode=0,
                    stdout='https://github.com/owner/repo.git\n'
                )
            return MagicMock(returncode=128)

        mock_run.side_effect = side_effect

        detector = GitRemoteDetector()
        url = detector.get_remote_url()

        assert url == 'https://github.com/owner/repo.git'

    @patch('subprocess.run')
    def test_get_remote_url_specific_remote(self, mock_run):
        """Test getting URL for specific remote name."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='https://github.com/custom/repo.git\n'
        )

        detector = GitRemoteDetector()
        url = detector.get_remote_url('custom')

        assert url == 'https://github.com/custom/repo.git'
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0][3] == 'custom'

    def test_parse_repository_info_github_https(self):
        """Test parsing GitHub HTTPS URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('https://github.com/owner/repo.git')

        assert result == ('github', 'owner', 'repo')

    def test_parse_repository_info_github_https_no_git(self):
        """Test parsing GitHub HTTPS URL without .git suffix."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('https://github.com/owner/repo')

        assert result == ('github', 'owner', 'repo')

    def test_parse_repository_info_github_ssh(self):
        """Test parsing GitHub SSH URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('git@github.com:owner/repo.git')

        assert result == ('github', 'owner', 'repo')

    def test_parse_repository_info_github_ssh_no_git(self):
        """Test parsing GitHub SSH URL without .git suffix."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('git@github.com:owner/repo')

        assert result == ('github', 'owner', 'repo')

    def test_parse_repository_info_gitlab_https(self):
        """Test parsing GitLab HTTPS URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('https://gitlab.com/group/project.git')

        assert result == ('gitlab', 'group', 'project')

    def test_parse_repository_info_gitlab_ssh(self):
        """Test parsing GitLab SSH URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('git@gitlab.com:group/project.git')

        assert result == ('gitlab', 'group', 'project')

    def test_parse_repository_info_unsupported_host(self):
        """Test parsing URL from unsupported host."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('https://bitbucket.org/owner/repo.git')

        assert result is None

    def test_parse_repository_info_github_enterprise_https(self):
        """Test parsing GitHub Enterprise HTTPS URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('https://github.enterprise.com/owner/repo.git')

        assert result == ('github', 'owner', 'repo')

    def test_parse_repository_info_github_enterprise_ssh(self):
        """Test parsing GitHub Enterprise SSH URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('git@github.enterprise.com:owner/repo.git')

        assert result == ('github', 'owner', 'repo')

    def test_parse_repository_info_gitlab_enterprise_https(self):
        """Test parsing GitLab Enterprise HTTPS URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('https://gitlab.cee.redhat.com/group/project.git')

        assert result == ('gitlab', 'group', 'project')

    def test_parse_repository_info_gitlab_enterprise_ssh(self):
        """Test parsing GitLab Enterprise SSH URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('git@gitlab.cee.redhat.com:group/project.git')

        assert result == ('gitlab', 'group', 'project')

    def test_parse_repository_info_github_self_hosted(self):
        """Test parsing self-hosted GitHub instance URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('https://github.company.internal/owner/repo.git')

        assert result == ('github', 'owner', 'repo')

    def test_parse_repository_info_gitlab_self_hosted(self):
        """Test parsing self-hosted GitLab instance URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('https://gitlab.company.internal/group/project.git')

        assert result == ('gitlab', 'group', 'project')

    def test_parse_repository_info_invalid_url(self):
        """Test parsing invalid URL."""
        detector = GitRemoteDetector()
        result = detector.parse_repository_info('not-a-url')

        assert result is None

    def test_parse_repository_info_none_url(self):
        """Test parsing with None URL."""
        detector = GitRemoteDetector()
        with patch.object(detector, 'get_remote_url', return_value=None):
            result = detector.parse_repository_info(None)
            assert result is None

    @patch.object(GitRemoteDetector, 'parse_repository_info')
    def test_get_github_repository_success(self, mock_parse):
        """Test getting GitHub repository string."""
        mock_parse.return_value = ('github', 'owner', 'repo')

        detector = GitRemoteDetector()
        result = detector.get_github_repository()

        assert result == 'owner/repo'

    @patch.object(GitRemoteDetector, 'parse_repository_info')
    def test_get_github_repository_not_github(self, mock_parse):
        """Test getting GitHub repository when it's not GitHub."""
        mock_parse.return_value = ('gitlab', 'owner', 'repo')

        detector = GitRemoteDetector()
        result = detector.get_github_repository()

        assert result is None

    @patch.object(GitRemoteDetector, 'parse_repository_info')
    def test_get_github_repository_parse_failed(self, mock_parse):
        """Test getting GitHub repository when parsing fails."""
        mock_parse.return_value = None

        detector = GitRemoteDetector()
        result = detector.get_github_repository()

        assert result is None

    @patch.object(GitRemoteDetector, 'parse_repository_info')
    def test_get_gitlab_repository_success(self, mock_parse):
        """Test getting GitLab repository string."""
        mock_parse.return_value = ('gitlab', 'group', 'project')

        detector = GitRemoteDetector()
        result = detector.get_gitlab_repository()

        assert result == 'group/project'

    @patch.object(GitRemoteDetector, 'parse_repository_info')
    def test_get_gitlab_repository_not_gitlab(self, mock_parse):
        """Test getting GitLab repository when it's not GitLab."""
        mock_parse.return_value = ('github', 'owner', 'repo')

        detector = GitRemoteDetector()
        result = detector.get_gitlab_repository()

        assert result is None

    @patch('subprocess.run')
    def test_list_all_remotes_success(self, mock_run):
        """Test listing all remotes."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='''origin\thttps://github.com/owner/repo.git (fetch)
origin\thttps://github.com/owner/repo.git (push)
upstream\thttps://github.com/main/repo.git (fetch)
upstream\thttps://github.com/main/repo.git (push)
'''
        )

        detector = GitRemoteDetector()
        remotes = detector.list_all_remotes()

        assert remotes == {
            'origin': 'https://github.com/owner/repo.git',
            'upstream': 'https://github.com/main/repo.git',
        }

    @patch('subprocess.run')
    def test_list_all_remotes_empty(self, mock_run):
        """Test listing remotes when none exist."""
        mock_run.return_value = MagicMock(returncode=0, stdout='')

        detector = GitRemoteDetector()
        remotes = detector.list_all_remotes()

        assert remotes == {}

    @patch('subprocess.run')
    def test_list_all_remotes_error(self, mock_run):
        """Test listing remotes when command fails."""
        mock_run.return_value = MagicMock(returncode=128)

        detector = GitRemoteDetector()
        remotes = detector.list_all_remotes()

        assert remotes == {}

    def test_host_to_platform_github(self):
        """Test mapping GitHub host."""
        detector = GitRemoteDetector()
        assert detector._host_to_platform('github.com') == 'github'

    def test_host_to_platform_gitlab(self):
        """Test mapping GitLab host."""
        detector = GitRemoteDetector()
        assert detector._host_to_platform('gitlab.com') == 'gitlab'

    def test_host_to_platform_unsupported(self):
        """Test mapping unsupported host."""
        detector = GitRemoteDetector()
        assert detector._host_to_platform('bitbucket.org') is None

    def test_host_to_platform_github_enterprise(self):
        """Test mapping GitHub Enterprise host."""
        detector = GitRemoteDetector()
        assert detector._host_to_platform('github.enterprise.com') == 'github'

    def test_host_to_platform_gitlab_enterprise(self):
        """Test mapping GitLab Enterprise host."""
        detector = GitRemoteDetector()
        assert detector._host_to_platform('gitlab.cee.redhat.com') == 'gitlab'

    def test_host_to_platform_github_self_hosted(self):
        """Test mapping self-hosted GitHub instance."""
        detector = GitRemoteDetector()
        assert detector._host_to_platform('github.company.internal') == 'github'

    def test_host_to_platform_gitlab_self_hosted(self):
        """Test mapping self-hosted GitLab instance."""
        detector = GitRemoteDetector()
        assert detector._host_to_platform('gitlab.company.internal') == 'gitlab'

    def test_host_to_platform_case_insensitive(self):
        """Test that platform detection is case-insensitive."""
        detector = GitRemoteDetector()
        assert detector._host_to_platform('GitHub.Enterprise.COM') == 'github'
        assert detector._host_to_platform('GitLab.CEE.RedHat.COM') == 'gitlab'


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @patch.object(GitRemoteDetector, 'get_remote_url')
    def test_get_project_remote_url(self, mock_get_remote):
        """Test convenience function for getting remote URL."""
        mock_get_remote.return_value = 'https://github.com/owner/repo.git'

        url = get_project_remote_url('/path/to/repo')

        assert url == 'https://github.com/owner/repo.git'
        mock_get_remote.assert_called_once()

    @patch.object(GitRemoteDetector, 'get_github_repository')
    def test_get_github_repository(self, mock_get_repo):
        """Test convenience function for getting GitHub repository."""
        mock_get_repo.return_value = 'owner/repo'

        repo = get_github_repository('/path/to/repo')

        assert repo == 'owner/repo'
        mock_get_repo.assert_called_once()

    @patch.object(GitRemoteDetector, 'get_gitlab_repository')
    def test_get_gitlab_repository(self, mock_get_repo):
        """Test convenience function for getting GitLab repository."""
        mock_get_repo.return_value = 'group/project'

        repo = get_gitlab_repository('/path/to/repo')

        assert repo == 'group/project'
        mock_get_repo.assert_called_once()
