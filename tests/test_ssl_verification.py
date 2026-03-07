"""Tests for SSL verification configuration and helper functions."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devflow.utils.ssl_helper import get_ssl_verify_setting, get_request_timeout


class TestGetSslVerifySetting:
    """Tests for get_ssl_verify_setting function."""

    def test_default_returns_true(self, monkeypatch):
        """Test that default behavior is to verify SSL (secure)."""
        # Clear environment variable
        monkeypatch.delenv('DAF_SSL_VERIFY', raising=False)

        # Mock config loading to fail (no config available)
        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.side_effect = Exception("No config")

            result = get_ssl_verify_setting()
            assert result is True

    def test_env_var_true_string(self, monkeypatch):
        """Test environment variable with 'true' value."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'true')

        result = get_ssl_verify_setting()
        assert result is True

    def test_env_var_true_number(self, monkeypatch):
        """Test environment variable with '1' value."""
        monkeypatch.setenv('DAF_SSL_VERIFY', '1')

        result = get_ssl_verify_setting()
        assert result is True

    def test_env_var_true_yes(self, monkeypatch):
        """Test environment variable with 'yes' value."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'yes')

        result = get_ssl_verify_setting()
        assert result is True

    def test_env_var_false_string(self, monkeypatch):
        """Test environment variable with 'false' value."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'false')

        result = get_ssl_verify_setting()
        assert result is False

    def test_env_var_false_number(self, monkeypatch):
        """Test environment variable with '0' value."""
        monkeypatch.setenv('DAF_SSL_VERIFY', '0')

        result = get_ssl_verify_setting()
        assert result is False

    def test_env_var_false_no(self, monkeypatch):
        """Test environment variable with 'no' value."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'no')

        result = get_ssl_verify_setting()
        assert result is False

    def test_env_var_path_to_ca_bundle(self, monkeypatch):
        """Test environment variable with path to CA bundle."""
        ca_path = '/etc/pki/ca-trust/source/anchors/company-ca.crt'
        monkeypatch.setenv('DAF_SSL_VERIFY', ca_path)

        result = get_ssl_verify_setting()
        assert result == ca_path

    def test_env_var_case_insensitive(self, monkeypatch):
        """Test environment variable is case-insensitive."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'TRUE')

        result = get_ssl_verify_setting()
        assert result is True

        monkeypatch.setenv('DAF_SSL_VERIFY', 'FALSE')

        result = get_ssl_verify_setting()
        assert result is False

    def test_config_ssl_verify_true(self, monkeypatch):
        """Test reading ssl_verify=True from config."""
        monkeypatch.delenv('DAF_SSL_VERIFY', raising=False)

        # Mock config with ssl_verify=True
        mock_config = Mock()
        mock_config.http_client = Mock()
        mock_config.http_client.ssl_verify = True

        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = mock_config

            result = get_ssl_verify_setting()
            assert result is True

    def test_config_ssl_verify_false(self, monkeypatch):
        """Test reading ssl_verify=False from config."""
        monkeypatch.delenv('DAF_SSL_VERIFY', raising=False)

        # Mock config with ssl_verify=False
        mock_config = Mock()
        mock_config.http_client = Mock()
        mock_config.http_client.ssl_verify = False

        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = mock_config

            result = get_ssl_verify_setting()
            assert result is False

    def test_config_ssl_verify_path(self, monkeypatch):
        """Test reading ssl_verify with path from config."""
        monkeypatch.delenv('DAF_SSL_VERIFY', raising=False)

        ca_path = '/path/to/ca-bundle.crt'

        # Mock config with ssl_verify=path
        mock_config = Mock()
        mock_config.http_client = Mock()
        mock_config.http_client.ssl_verify = ca_path

        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = mock_config

            result = get_ssl_verify_setting()
            assert result == ca_path

    def test_env_var_overrides_config(self, monkeypatch):
        """Test that environment variable takes precedence over config."""
        monkeypatch.setenv('DAF_SSL_VERIFY', 'false')

        # Mock config with ssl_verify=True
        mock_config = Mock()
        mock_config.http_client = Mock()
        mock_config.http_client.ssl_verify = True

        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = mock_config

            result = get_ssl_verify_setting()
            # Environment variable should override config
            assert result is False

    def test_config_without_http_client(self, monkeypatch):
        """Test config without http_client attribute defaults to True."""
        monkeypatch.delenv('DAF_SSL_VERIFY', raising=False)

        # Mock config without http_client
        mock_config = Mock(spec=[])  # Empty spec, no http_client attribute

        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = mock_config

            result = get_ssl_verify_setting()
            assert result is True

    def test_config_with_none_http_client(self, monkeypatch):
        """Test config with http_client=None defaults to True."""
        monkeypatch.delenv('DAF_SSL_VERIFY', raising=False)

        # Mock config with http_client=None
        mock_config = Mock()
        mock_config.http_client = None

        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = mock_config

            result = get_ssl_verify_setting()
            assert result is True


class TestGetRequestTimeout:
    """Tests for get_request_timeout function."""

    def test_default_returns_10(self, monkeypatch):
        """Test that default timeout is 10 seconds."""
        # Clear environment variable
        monkeypatch.delenv('DAF_REQUEST_TIMEOUT', raising=False)

        # Mock config loading to fail (no config available)
        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.side_effect = Exception("No config")

            result = get_request_timeout()
            assert result == 10

    def test_env_var_timeout(self, monkeypatch):
        """Test environment variable sets timeout."""
        monkeypatch.setenv('DAF_REQUEST_TIMEOUT', '30')

        result = get_request_timeout()
        assert result == 30

    def test_env_var_invalid_falls_back_to_default(self, monkeypatch):
        """Test invalid environment variable falls back to default."""
        monkeypatch.setenv('DAF_REQUEST_TIMEOUT', 'invalid')

        # Mock config loading to fail
        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.side_effect = Exception("No config")

            result = get_request_timeout()
            assert result == 10

    def test_config_timeout(self, monkeypatch):
        """Test reading timeout from config."""
        monkeypatch.delenv('DAF_REQUEST_TIMEOUT', raising=False)

        # Mock config with timeout=20
        mock_config = Mock()
        mock_config.http_client = Mock()
        mock_config.http_client.timeout = 20

        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = mock_config

            result = get_request_timeout()
            assert result == 20

    def test_env_var_overrides_config_timeout(self, monkeypatch):
        """Test that environment variable overrides config timeout."""
        monkeypatch.setenv('DAF_REQUEST_TIMEOUT', '60')

        # Mock config with timeout=20
        mock_config = Mock()
        mock_config.http_client = Mock()
        mock_config.http_client.timeout = 20

        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = mock_config

            result = get_request_timeout()
            # Environment variable should override config
            assert result == 60

    def test_config_without_http_client(self, monkeypatch):
        """Test config without http_client returns default."""
        monkeypatch.delenv('DAF_REQUEST_TIMEOUT', raising=False)

        # Mock config without http_client
        mock_config = Mock(spec=[])

        with patch('devflow.config.loader.ConfigLoader') as mock_loader:
            mock_loader.return_value.load_config.return_value = mock_config

            result = get_request_timeout()
            assert result == 10
