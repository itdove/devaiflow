"""Tests for GitHub authentication and pre-flight checks."""

import os
import subprocess
import sys
from unittest.mock import patch, MagicMock, Mock
import pytest

from devflow.github.auth import (
    is_interactive_environment,
    check_gh_auth_for_repo,
    handle_auth_error,
)
from devflow.issue_tracker.exceptions import IssueTrackerAuthError


class TestIsInteractiveEnvironment:
    """Tests for environment detection."""

    def test_interactive_when_tty_and_no_ci(self, monkeypatch):
        """Test detection of interactive environment."""
        # Clear CI env vars
        for var in ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_HOME', 'CIRCLECI', 'TRAVIS']:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.delenv('DAF_NO_PROMPT', raising=False)

        # Mock stdin.isatty() to return True
        with patch.object(sys.stdin, 'isatty', return_value=True):
            assert is_interactive_environment() is True

    def test_non_interactive_when_ci_env_var(self, monkeypatch):
        """Test detection of CI environment."""
        monkeypatch.setenv('CI', '1')

        with patch.object(sys.stdin, 'isatty', return_value=True):
            assert is_interactive_environment() is False

    def test_non_interactive_when_github_actions(self, monkeypatch):
        """Test detection of GitHub Actions."""
        monkeypatch.setenv('GITHUB_ACTIONS', 'true')

        with patch.object(sys.stdin, 'isatty', return_value=True):
            assert is_interactive_environment() is False

    def test_non_interactive_when_gitlab_ci(self, monkeypatch):
        """Test detection of GitLab CI."""
        monkeypatch.setenv('GITLAB_CI', '1')

        with patch.object(sys.stdin, 'isatty', return_value=True):
            assert is_interactive_environment() is False

    def test_non_interactive_when_jenkins(self, monkeypatch):
        """Test detection of Jenkins."""
        monkeypatch.setenv('JENKINS_HOME', '/var/jenkins')

        with patch.object(sys.stdin, 'isatty', return_value=True):
            assert is_interactive_environment() is False

    def test_non_interactive_when_no_tty(self, monkeypatch):
        """Test detection of non-TTY environment."""
        # Clear CI env vars
        for var in ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_HOME']:
            monkeypatch.delenv(var, raising=False)

        with patch.object(sys.stdin, 'isatty', return_value=False):
            assert is_interactive_environment() is False

    def test_non_interactive_when_daf_no_prompt(self, monkeypatch):
        """Test detection of DAF_NO_PROMPT environment variable."""
        monkeypatch.setenv('DAF_NO_PROMPT', '1')

        # Clear CI env vars
        for var in ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_HOME']:
            monkeypatch.delenv(var, raising=False)

        with patch.object(sys.stdin, 'isatty', return_value=True):
            assert is_interactive_environment() is False

    def test_interactive_when_daf_no_prompt_is_zero(self, monkeypatch):
        """Test that DAF_NO_PROMPT=0 doesn't disable prompts."""
        monkeypatch.setenv('DAF_NO_PROMPT', '0')

        # Clear CI env vars
        for var in ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_HOME']:
            monkeypatch.delenv(var, raising=False)

        with patch.object(sys.stdin, 'isatty', return_value=True):
            assert is_interactive_environment() is True


class TestCheckGhAuthForRepo:
    """Tests for pre-flight authentication checks."""

    @patch('subprocess.run')
    def test_auth_check_success(self, mock_run):
        """Test successful authentication and repository access."""
        # Mock gh auth status (success)
        auth_result = Mock()
        auth_result.returncode = 0
        auth_result.stderr = ""

        # Mock gh api /repos/owner/repo (success)
        api_result = Mock()
        api_result.returncode = 0
        api_result.stdout = "repo-name"
        api_result.stderr = ""

        mock_run.side_effect = [auth_result, api_result]

        authenticated, error_type, error_msg = check_gh_auth_for_repo("owner/repo")

        assert authenticated is True
        assert error_type == 'ok'
        assert error_msg == ''

    @patch('subprocess.run')
    def test_not_authenticated(self, mock_run):
        """Test detection of not authenticated state."""
        # Mock gh auth status (failure)
        auth_result = Mock()
        auth_result.returncode = 1
        auth_result.stderr = "Not logged in"

        mock_run.return_value = auth_result

        authenticated, error_type, error_msg = check_gh_auth_for_repo("owner/repo")

        assert authenticated is False
        assert error_type == 'not_authenticated'
        assert error_msg == 'Not logged in to GitHub'

    @patch('subprocess.run')
    def test_fine_grained_token_required(self, mock_run):
        """Test detection of fine-grained token requirement."""
        # Mock gh auth status (success)
        auth_result = Mock()
        auth_result.returncode = 0

        # Mock gh api (fine-grained token error)
        api_result = Mock()
        api_result.returncode = 1
        api_result.stderr = "forbids access via a personal access token (classic)"

        mock_run.side_effect = [auth_result, api_result]

        authenticated, error_type, error_msg = check_gh_auth_for_repo("ansible-automation-platform/repo")

        assert authenticated is False
        assert error_type == 'fine_grained_required'
        assert error_msg == 'Repository requires fine-grained token'

    @patch('subprocess.run')
    def test_not_found_or_no_access(self, mock_run):
        """Test detection of not found or no access."""
        # Mock gh auth status (success)
        auth_result = Mock()
        auth_result.returncode = 0

        # Mock gh api (not found)
        api_result = Mock()
        api_result.returncode = 1
        api_result.stderr = "Not Found (HTTP 404)"

        mock_run.side_effect = [auth_result, api_result]

        authenticated, error_type, error_msg = check_gh_auth_for_repo("owner/repo")

        assert authenticated is False
        assert error_type == 'not_found'
        assert error_msg == 'Repository not found or no access'

    @patch('subprocess.run')
    def test_bad_credentials(self, mock_run):
        """Test detection of bad credentials."""
        # Mock gh auth status (success)
        auth_result = Mock()
        auth_result.returncode = 0

        # Mock gh api (bad credentials)
        api_result = Mock()
        api_result.returncode = 1
        api_result.stderr = "Bad credentials (HTTP 401)"

        mock_run.side_effect = [auth_result, api_result]

        authenticated, error_type, error_msg = check_gh_auth_for_repo("owner/repo")

        assert authenticated is False
        assert error_type == 'insufficient_permissions'
        assert error_msg == 'Authentication invalid or expired'

    @patch('subprocess.run')
    def test_forbidden_403(self, mock_run):
        """Test detection of forbidden access."""
        # Mock gh auth status (success)
        auth_result = Mock()
        auth_result.returncode = 0

        # Mock gh api (forbidden)
        api_result = Mock()
        api_result.returncode = 1
        api_result.stderr = "Forbidden (HTTP 403)"

        mock_run.side_effect = [auth_result, api_result]

        authenticated, error_type, error_msg = check_gh_auth_for_repo("owner/repo")

        assert authenticated is False
        assert error_type == 'insufficient_permissions'
        assert error_msg == 'Insufficient permissions'

    @patch('subprocess.run')
    def test_unknown_error(self, mock_run):
        """Test handling of unknown error."""
        # Mock gh auth status (success)
        auth_result = Mock()
        auth_result.returncode = 0

        # Mock gh api (unknown error)
        api_result = Mock()
        api_result.returncode = 1
        api_result.stderr = "Some unexpected error"

        mock_run.side_effect = [auth_result, api_result]

        authenticated, error_type, error_msg = check_gh_auth_for_repo("owner/repo")

        assert authenticated is False
        assert error_type == 'unknown'
        assert error_msg == 'Some unexpected error'


class TestHandleAuthError:
    """Tests for error handling."""

    def test_not_authenticated_interactive(self, monkeypatch, capsys):
        """Test error message for not authenticated in interactive mode."""
        monkeypatch.delenv('CI', raising=False)
        monkeypatch.delenv('DAF_NO_PROMPT', raising=False)

        with patch.object(sys.stdin, 'isatty', return_value=True):
            with pytest.raises(IssueTrackerAuthError):
                handle_auth_error("owner/repo", "not_authenticated", "Not logged in to GitHub")

        captured = capsys.readouterr()
        assert "✗ GitHub authentication failed" in captured.out
        assert "gh auth login" in captured.out
        assert "Tip:" in captured.out  # Interactive tip shown

    def test_not_authenticated_non_interactive(self, monkeypatch, capsys):
        """Test error message for not authenticated in non-interactive mode."""
        monkeypatch.setenv('CI', '1')

        with pytest.raises(IssueTrackerAuthError):
            handle_auth_error("owner/repo", "not_authenticated", "Not logged in to GitHub")

        captured = capsys.readouterr()
        assert "✗ GitHub authentication failed" in captured.out
        assert "gh auth login" in captured.out
        assert "non-interactive mode" in captured.out
        assert "Tip:" not in captured.out  # No interactive tip

    def test_fine_grained_required(self, monkeypatch, capsys):
        """Test error message for fine-grained token requirement."""
        monkeypatch.delenv('CI', raising=False)

        with patch.object(sys.stdin, 'isatty', return_value=True):
            with pytest.raises(IssueTrackerAuthError):
                handle_auth_error("owner/repo", "fine_grained_required", "Repository requires fine-grained token")

        captured = capsys.readouterr()
        assert "fine-grained personal access token" in captured.out
        assert "personal-access-tokens/new" in captured.out
        assert "Grant access to repository" in captured.out

    def test_not_found(self, monkeypatch, capsys):
        """Test error message for not found."""
        monkeypatch.delenv('CI', raising=False)

        with patch.object(sys.stdin, 'isatty', return_value=True):
            with pytest.raises(IssueTrackerAuthError):
                handle_auth_error("owner/repo", "not_found", "Repository not found or no access")

        captured = capsys.readouterr()
        assert "Verify repository exists" in captured.out
        assert "gh auth status" in captured.out

    def test_insufficient_permissions(self, monkeypatch, capsys):
        """Test error message for insufficient permissions."""
        monkeypatch.delenv('CI', raising=False)

        with patch.object(sys.stdin, 'isatty', return_value=True):
            with pytest.raises(IssueTrackerAuthError):
                handle_auth_error("owner/repo", "insufficient_permissions", "Authentication invalid")

        captured = capsys.readouterr()
        assert "Re-authenticate with sufficient permissions" in captured.out
        assert "gh auth refresh" in captured.out

    def test_unknown_error(self, monkeypatch, capsys):
        """Test error message for unknown error."""
        monkeypatch.delenv('CI', raising=False)

        with patch.object(sys.stdin, 'isatty', return_value=True):
            with pytest.raises(IssueTrackerAuthError):
                handle_auth_error("owner/repo", "unknown", "Some unexpected error")

        captured = capsys.readouterr()
        assert "Error details:" in captured.out
        assert "Some unexpected error" in captured.out
        assert "gh auth status" in captured.out
