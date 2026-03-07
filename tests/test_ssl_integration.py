"""Integration tests for SSL verification in HTTP requests."""

import os
from unittest.mock import Mock, patch, call

import pytest
import requests


class TestHierarchicalSkillsSSL:
    """Test SSL verification in hierarchical_skills.py functions."""

    def test_download_skill_ssl_error_provides_helpful_message(self, monkeypatch):
        """Test that SSL errors provide helpful guidance."""
        monkeypatch.delenv('DAF_SSL_VERIFY', raising=False)

        from devflow.utils.hierarchical_skills import download_skill

        # Mock SSL error
        ssl_error = requests.exceptions.SSLError("certificate verify failed")

        with patch('devflow.utils.hierarchical_skills.requests.get', side_effect=ssl_error):
            with pytest.raises(ValueError) as exc_info:
                download_skill("https://gitlab.example.com/org/repo/skills/enterprise")

            error_msg = str(exc_info.value)
            # Verify helpful suggestions are included
            assert "SSL certificate verification failed" in error_msg
            assert "DAF_SSL_VERIFY=false" in error_msg
            assert "DAF_SSL_VERIFY=/path/to/ca-bundle.crt" in error_msg
            assert "organization.json" in error_msg

    def test_download_hierarchical_config_ssl_error_provides_helpful_message(self, monkeypatch):
        """Test that config download SSL errors provide helpful guidance."""
        monkeypatch.delenv('DAF_SSL_VERIFY', raising=False)

        from devflow.utils.hierarchical_skills import download_hierarchical_config_file

        # Mock SSL error
        ssl_error = requests.exceptions.SSLError("certificate verify failed")

        with patch('devflow.utils.hierarchical_skills.requests.get', side_effect=ssl_error):
            with pytest.raises(ValueError) as exc_info:
                download_hierarchical_config_file(
                    "https://gitlab.example.com/org/repo/configs",
                    "ENTERPRISE.md"
                )

            error_msg = str(exc_info.value)
            # Verify helpful suggestions are included
            assert "SSL certificate verification failed" in error_msg
            assert "DAF_SSL_VERIFY=false" in error_msg
            assert "DAF_SSL_VERIFY=/path/to/ca-bundle.crt" in error_msg
            assert "organization.json" in error_msg

    def test_download_skill_uses_ssl_verify_true(self, monkeypatch):
        """Test download_skill respects ssl_verify=True."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'true')
        monkeypatch.setenv('DAF_REQUEST_TIMEOUT', '15')

        from devflow.utils.hierarchical_skills import download_skill

        mock_response = Mock()
        mock_response.text = "# Skill content"
        mock_response.raise_for_status = Mock()

        with patch('devflow.utils.hierarchical_skills.requests.get', return_value=mock_response) as mock_get:
            result = download_skill("https://github.com/org/repo/skills/enterprise")

            # Verify requests.get was called with verify=True
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['verify'] is True
            assert call_kwargs['timeout'] == 15
            assert result == "# Skill content"

    def test_download_skill_uses_ssl_verify_false(self, monkeypatch):
        """Test download_skill respects ssl_verify=False."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'false')

        from devflow.utils.hierarchical_skills import download_skill

        mock_response = Mock()
        mock_response.text = "# Skill content"
        mock_response.raise_for_status = Mock()

        with patch('devflow.utils.hierarchical_skills.requests.get', return_value=mock_response) as mock_get:
            result = download_skill("https://github.com/org/repo/skills/enterprise")

            # Verify requests.get was called with verify=False
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['verify'] is False

    def test_download_skill_uses_ssl_verify_ca_bundle_path(self, monkeypatch):
        """Test download_skill respects custom CA bundle path."""
        ca_path = '/etc/pki/ca-trust/source/anchors/company-ca.crt'
        monkeypatch.setenv('DAF_SSL_VERIFY', ca_path)

        from devflow.utils.hierarchical_skills import download_skill

        mock_response = Mock()
        mock_response.text = "# Skill content"
        mock_response.raise_for_status = Mock()

        with patch('devflow.utils.hierarchical_skills.requests.get', return_value=mock_response) as mock_get:
            result = download_skill("https://github.com/org/repo/skills/enterprise")

            # Verify requests.get was called with custom CA bundle path
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['verify'] == ca_path

    def test_download_hierarchical_config_file_uses_ssl_verify(self, monkeypatch):
        """Test download_hierarchical_config_file respects SSL settings."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'false')

        from devflow.utils.hierarchical_skills import download_hierarchical_config_file

        mock_response = Mock()
        mock_response.text = "# Config content"
        mock_response.raise_for_status = Mock()

        with patch('devflow.utils.hierarchical_skills.requests.get', return_value=mock_response) as mock_get:
            result = download_hierarchical_config_file(
                "https://github.com/org/repo/configs",
                "ENTERPRISE.md"
            )

            # Verify requests.get was called with verify=False
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['verify'] is False
            assert result == "# Config content"


class TestUpdateCheckerSSL:
    """Test SSL verification in update_checker.py."""

    def test_fetch_latest_version_uses_ssl_verify_true(self, monkeypatch):
        """Test _fetch_latest_version_from_pypi respects ssl_verify=True."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'true')

        from devflow.utils.update_checker import _fetch_latest_version_from_pypi

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"info": {"version": "1.2.3"}}

        with patch('devflow.utils.update_checker.requests.get', return_value=mock_response) as mock_get:
            version, network_error = _fetch_latest_version_from_pypi(timeout=10)

            # Verify requests.get was called with verify=True
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['verify'] is True
            assert version == "1.2.3"
            assert network_error is False

    def test_fetch_latest_version_uses_ssl_verify_false(self, monkeypatch):
        """Test _fetch_latest_version_from_pypi respects ssl_verify=False."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'false')

        from devflow.utils.update_checker import _fetch_latest_version_from_pypi

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"info": {"version": "1.2.3"}}

        with patch('devflow.utils.update_checker.requests.get', return_value=mock_response) as mock_get:
            version, network_error = _fetch_latest_version_from_pypi(timeout=10)

            # Verify requests.get was called with verify=False
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['verify'] is False


class TestJiraClientSSL:
    """Test SSL verification in JIRA client."""

    def test_jira_api_request_uses_ssl_verify_true(self, monkeypatch, temp_daf_home):
        """Test JIRA _api_request respects ssl_verify=True."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'true')
        monkeypatch.setenv('JIRA_URL', 'https://jira.example.com')
        monkeypatch.setenv('JIRA_API_TOKEN', 'fake-token')

        from devflow.jira.client import JiraClient

        client = JiraClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "PROJ-123"}

        with patch('devflow.jira.client.requests.request', return_value=mock_response) as mock_request:
            response = client._api_request('GET', '/rest/api/2/issue/PROJ-123')

            # Verify requests.request was called with verify=True
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs['verify'] is True

    def test_jira_api_request_uses_ssl_verify_false(self, monkeypatch, temp_daf_home):
        """Test JIRA _api_request respects ssl_verify=False."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'false')
        monkeypatch.setenv('JIRA_URL', 'https://jira.example.com')
        monkeypatch.setenv('JIRA_API_TOKEN', 'fake-token')

        from devflow.jira.client import JiraClient

        client = JiraClient()

        mock_response = Mock()
        mock_response.status_code = 200

        with patch('devflow.jira.client.requests.request', return_value=mock_response) as mock_request:
            response = client._api_request('GET', '/rest/api/2/issue/PROJ-123')

            # Verify requests.request was called with verify=False
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs['verify'] is False

    def test_jira_api_request_uses_custom_ca_bundle(self, monkeypatch, temp_daf_home):
        """Test JIRA _api_request respects custom CA bundle path."""
        ca_path = '/etc/ssl/certs/custom-ca.crt'
        monkeypatch.setenv('DAF_SSL_VERIFY', ca_path)
        monkeypatch.setenv('JIRA_URL', 'https://jira.internal.example.com')
        monkeypatch.setenv('JIRA_API_TOKEN', 'fake-token')

        from devflow.jira.client import JiraClient

        client = JiraClient()

        mock_response = Mock()
        mock_response.status_code = 200

        with patch('devflow.jira.client.requests.request', return_value=mock_response) as mock_request:
            response = client._api_request('GET', '/rest/api/2/issue/PROJ-123')

            # Verify requests.request was called with custom CA bundle
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs['verify'] == ca_path

    def test_jira_attach_file_uses_ssl_verify(self, monkeypatch, temp_daf_home, tmp_path):
        """Test JIRA attach_file respects SSL settings."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'false')
        monkeypatch.setenv('JIRA_URL', 'https://jira.example.com')
        monkeypatch.setenv('JIRA_API_TOKEN', 'fake-token')

        # Create a temporary test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        from devflow.jira.client import JiraClient

        client = JiraClient()

        mock_response = Mock()
        mock_response.status_code = 200

        with patch('devflow.jira.client.requests.post', return_value=mock_response) as mock_post:
            client.attach_file('PROJ-123', str(test_file))

            # Verify requests.post was called with verify=False
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs['verify'] is False


class TestCliUtilsSSL:
    """Test SSL verification in CLI utility functions."""

    def test_fetch_goal_from_url_uses_ssl_verify(self, monkeypatch):
        """Test _fetch_goal_from_url respects SSL settings."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'false')

        from devflow.cli.utils import _fetch_goal_from_url

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Goal content"

        with patch('devflow.cli.utils.requests.get', return_value=mock_response) as mock_get:
            result = _fetch_goal_from_url("https://example.com/goal.txt")

            # Verify requests.get was called with verify=False
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['verify'] is False
            assert result == "Goal content"


class TestCompleteCommandSSL:
    """Test SSL verification in complete_command.py functions."""

    def test_fetch_github_with_api_uses_ssl_verify(self, monkeypatch):
        """Test GitHub API fetch respects SSL settings."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'false')

        from devflow.cli.commands.complete_command import _fetch_github_with_api

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'content': 'VGVtcGxhdGUgY29udGVudA=='  # base64 encoded "Template content"
        }

        with patch('requests.get', return_value=mock_response) as mock_get:
            result = _fetch_github_with_api('owner', 'repo', '.github/PULL_REQUEST_TEMPLATE.md', 'main')

            # Verify requests.get was called with verify=False
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['verify'] is False

    def test_fetch_github_raw_uses_ssl_verify(self, monkeypatch):
        """Test raw GitHub file fetch respects SSL settings."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'true')

        from devflow.cli.commands.complete_command import _fetch_github_raw

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Template content"

        with patch('requests.get', return_value=mock_response) as mock_get:
            result = _fetch_github_raw('owner', 'repo', 'PULL_REQUEST_TEMPLATE.md', 'main')

            # Verify requests.get was called with verify=True
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['verify'] is True
            assert result == "Template content"
