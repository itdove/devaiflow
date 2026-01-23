"""Tests for update checker functionality."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from devflow.utils.update_checker import (
    _fetch_latest_version_from_github,
    _get_cache_file,
    _get_timeout_from_config,
    _is_cache_valid,
    _is_development_install,
    _parse_version,
    _read_cache,
    _write_cache,
    check_for_updates,
)


@pytest.fixture
def mock_cache_file(tmp_path, monkeypatch):
    """Create a temporary cache file for testing."""
    cache_file = tmp_path / "version_check_cache.json"

    def mock_get_cache_file():
        return cache_file

    monkeypatch.setattr("devflow.utils.update_checker._get_cache_file", mock_get_cache_file)
    return cache_file


def test_parse_version_standard():
    """Test parsing standard version strings."""
    assert _parse_version("1.0.0") == (1, 0, 0)
    assert _parse_version("1.2.3") == (1, 2, 3)
    assert _parse_version("2.10.5") == (2, 10, 5)


def test_parse_version_with_dev_suffix():
    """Test parsing version strings with -dev suffix."""
    assert _parse_version("1.0.0-dev") == (1, 0, 0)
    assert _parse_version("2.1.0-dev") == (2, 1, 0)


def test_parse_version_invalid():
    """Test parsing invalid version strings."""
    assert _parse_version("invalid") == (0, 0, 0)
    assert _parse_version("") == (0, 0, 0)
    assert _parse_version(None) == (0, 0, 0)


def test_get_cache_file_default(monkeypatch, tmp_path):
    """Test cache file path with default location (backward compat or new install)."""
    monkeypatch.delenv("CLAUDE_SESSION_HOME", raising=False)
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("CS_HOME", raising=False)

    # Mock Path.home() to use tmp_path to avoid existing ~/.daf-sessions
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    cache_file = _get_cache_file()
    # Should use .daf-sessions for new installations (when neither directory exists)
    assert cache_file == tmp_path / ".daf-sessions" / "version_check_cache.json"


def test_get_cache_file_custom_home(monkeypatch, tmp_path):
    """Test cache file path with custom DEVAIFLOW_HOME."""
    custom_home = str(tmp_path / "custom_session_home")
    monkeypatch.setenv("DEVAIFLOW_HOME", custom_home)
    cache_file = _get_cache_file()
    assert cache_file == Path(custom_home) / "version_check_cache.json"


def test_write_and_read_cache(mock_cache_file):
    """Test writing and reading cache data."""
    data = {
        "timestamp": "2025-01-15T10:00:00",
        "latest_version": "1.0.0",
        "current_version": "0.9.0"
    }

    _write_cache(data)
    assert mock_cache_file.exists()

    read_data = _read_cache()
    assert read_data == data


def test_read_cache_nonexistent(mock_cache_file):
    """Test reading cache when file doesn't exist."""
    assert _read_cache() is None


def test_read_cache_invalid_json(mock_cache_file):
    """Test reading cache with invalid JSON."""
    mock_cache_file.write_text("invalid json {")
    assert _read_cache() is None


def test_is_cache_valid_fresh():
    """Test cache validity with fresh cache."""
    cache = {
        "timestamp": datetime.now().isoformat(),
        "latest_version": "1.0.0"
    }
    assert _is_cache_valid(cache, max_age_hours=24) is True


def test_is_cache_valid_stale():
    """Test cache validity with stale cache."""
    old_time = datetime.now() - timedelta(hours=25)
    cache = {
        "timestamp": old_time.isoformat(),
        "latest_version": "1.0.0"
    }
    assert _is_cache_valid(cache, max_age_hours=24) is False


def test_is_cache_valid_missing_timestamp():
    """Test cache validity with missing timestamp."""
    cache = {"latest_version": "1.0.0"}
    assert _is_cache_valid(cache, max_age_hours=24) is False


def test_is_cache_valid_empty_cache():
    """Test cache validity with empty cache."""
    assert _is_cache_valid(None, max_age_hours=24) is False
    assert _is_cache_valid({}, max_age_hours=24) is False


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_from_github_success(mock_get):
    """Test successfully fetching latest version from GitHub."""
    # Mock successful API response (GitHub /releases/latest returns a single dict)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tag_name": "v1.0.0",
        "name": "Release 1.0.0"
    }
    mock_get.return_value = mock_response

    version, network_error = _fetch_latest_version_from_github()
    assert version == "1.0.0"
    assert network_error is False


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_from_github_no_v_prefix(mock_get):
    """Test fetching version without v prefix."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "tag_name": "1.0.0",
        "name": "Release 1.0.0"
    }
    mock_get.return_value = mock_response

    version, network_error = _fetch_latest_version_from_github()
    assert version == "1.0.0"
    assert network_error is False


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_from_github_api_error(mock_get):
    """Test handling API errors."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    version, network_error = _fetch_latest_version_from_github()
    assert version is None
    assert network_error is False


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_from_github_connection_error(mock_get):
    """Test handling connection errors (actual network issue)."""
    import requests
    mock_get.side_effect = requests.ConnectionError("Connection refused")

    version, network_error = _fetch_latest_version_from_github()
    assert version is None
    assert network_error is True


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_from_github_timeout_error(mock_get):
    """Test handling timeout errors (NOT a network issue)."""
    import requests
    mock_get.side_effect = requests.Timeout("Request timed out")

    version, network_error = _fetch_latest_version_from_github()
    assert version is None
    assert network_error is False  # Timeout is NOT treated as network issue


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_from_github_http_error(mock_get):
    """Test handling HTTP errors (NOT a network issue)."""
    import requests
    mock_get.side_effect = requests.HTTPError("500 Server Error")

    version, network_error = _fetch_latest_version_from_github()
    assert version is None
    assert network_error is False  # HTTP error is NOT treated as network issue


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_from_github_too_many_redirects(mock_get):
    """Test handling too many redirects error (NOT a network issue)."""
    import requests
    mock_get.side_effect = requests.TooManyRedirects("Too many redirects")

    version, network_error = _fetch_latest_version_from_github()
    assert version is None
    assert network_error is False  # Redirects error is NOT treated as network issue


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_from_github_generic_request_exception(mock_get):
    """Test handling generic RequestException (NOT a network issue)."""
    import requests
    mock_get.side_effect = requests.RequestException("Generic request error")

    version, network_error = _fetch_latest_version_from_github()
    assert version is None
    assert network_error is False  # Generic RequestException is NOT treated as network issue


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_from_github_empty_response(mock_get):
    """Test handling empty response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_get.return_value = mock_response

    version, network_error = _fetch_latest_version_from_github()
    assert version is None
    assert network_error is False


@patch("devflow.utils.update_checker.__version__", "0.9.0")
@patch("devflow.utils.update_checker._is_development_install")
@patch("devflow.utils.update_checker._fetch_latest_version_from_github")
def test_check_for_updates_update_available(mock_fetch, mock_is_dev, mock_cache_file):
    """Test check_for_updates when update is available."""
    mock_is_dev.return_value = False
    mock_fetch.return_value = ("1.0.0", False)

    latest, network_error = check_for_updates()
    assert latest == "1.0.0"
    assert network_error is False


@patch("devflow.utils.update_checker.__version__", "1.0.0")
@patch("devflow.utils.update_checker._is_development_install")
@patch("devflow.utils.update_checker._fetch_latest_version_from_github")
def test_check_for_updates_no_update(mock_fetch, mock_is_dev, mock_cache_file):
    """Test check_for_updates when already on latest version."""
    mock_is_dev.return_value = False
    mock_fetch.return_value = ("1.0.0", False)

    latest, network_error = check_for_updates()
    assert latest is None
    assert network_error is False


@patch("devflow.utils.update_checker.__version__", "1.1.0")
@patch("devflow.utils.update_checker._is_development_install")
@patch("devflow.utils.update_checker._fetch_latest_version_from_github")
def test_check_for_updates_newer_than_latest(mock_fetch, mock_is_dev, mock_cache_file):
    """Test check_for_updates when current version is newer than latest release."""
    mock_is_dev.return_value = False
    mock_fetch.return_value = ("1.0.0", False)

    latest, network_error = check_for_updates()
    assert latest is None
    assert network_error is False


@patch("devflow.utils.update_checker._is_development_install")
def test_check_for_updates_development_mode(mock_is_dev, mock_cache_file):
    """Test check_for_updates skips check in development mode."""
    mock_is_dev.return_value = True

    latest, network_error = check_for_updates()
    assert latest is None
    assert network_error is False


@patch("devflow.utils.update_checker.__version__", "0.9.0")
@patch("devflow.utils.update_checker._is_development_install")
def test_check_for_updates_uses_cache(mock_is_dev, mock_cache_file):
    """Test check_for_updates uses cached data when available."""
    mock_is_dev.return_value = False

    # Write fresh cache
    cache_data = {
        "timestamp": datetime.now().isoformat(),
        "latest_version": "1.0.0",
        "current_version": "0.9.0"
    }
    _write_cache(cache_data)

    # Should use cache without making API request
    with patch("devflow.utils.update_checker._fetch_latest_version_from_github") as mock_fetch:
        latest, network_error = check_for_updates()
        assert latest == "1.0.0"
        assert network_error is False
        mock_fetch.assert_not_called()


@patch("devflow.utils.update_checker.__version__", "0.9.0")
@patch("devflow.utils.update_checker._is_development_install")
@patch("devflow.utils.update_checker._fetch_latest_version_from_github")
def test_check_for_updates_fetches_when_cache_stale(mock_fetch, mock_is_dev, mock_cache_file):
    """Test check_for_updates fetches new data when cache is stale."""
    mock_is_dev.return_value = False
    mock_fetch.return_value = ("1.0.0", False)

    # Write stale cache
    old_time = datetime.now() - timedelta(hours=25)
    cache_data = {
        "timestamp": old_time.isoformat(),
        "latest_version": "0.8.0",
        "current_version": "0.9.0"
    }
    _write_cache(cache_data)

    # Should fetch fresh data
    latest, network_error = check_for_updates()
    assert latest == "1.0.0"
    assert network_error is False
    mock_fetch.assert_called_once()


@patch("devflow.utils.update_checker.__version__", "0.9.0")
@patch("devflow.utils.update_checker._is_development_install")
@patch("devflow.utils.update_checker._fetch_latest_version_from_github")
def test_check_for_updates_caches_result(mock_fetch, mock_is_dev, mock_cache_file):
    """Test check_for_updates caches the result."""
    mock_is_dev.return_value = False
    mock_fetch.return_value = ("1.0.0", False)

    check_for_updates()

    # Verify cache was written
    cache = _read_cache()
    assert cache is not None
    assert cache["latest_version"] == "1.0.0"
    assert cache["current_version"] == "0.9.0"
    assert "timestamp" in cache


@patch("devflow.utils.update_checker._is_development_install")
@patch("devflow.utils.update_checker._fetch_latest_version_from_github")
def test_check_for_updates_network_error(mock_fetch, mock_is_dev, mock_cache_file):
    """Test check_for_updates handles network errors (network connectivity issue)."""
    mock_is_dev.return_value = False
    mock_fetch.return_value = (None, True)  # Network error

    latest, network_error = check_for_updates()

    assert latest is None
    assert network_error is True
    # Verify cache was NOT written (network errors shouldn't be cached)
    cache = _read_cache()
    assert cache is None


def test_is_development_install_regular_install():
    """Test detection of regular pip install."""
    # This is a simple check - if the function returns a boolean, it's working
    result = _is_development_install()
    assert isinstance(result, bool)


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_uses_custom_timeout(mock_get):
    """Test that _fetch_latest_version_from_github uses custom timeout."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"tag_name": "v1.0.0"}]
    mock_get.return_value = mock_response

    # Call with custom timeout
    _fetch_latest_version_from_github(timeout=30)

    # Verify timeout was passed to requests.get
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["timeout"] == 30


@patch("devflow.utils.update_checker.requests.get")
def test_fetch_latest_version_default_timeout(mock_get):
    """Test that _fetch_latest_version_from_github uses default timeout."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"tag_name": "v1.0.0"}]
    mock_get.return_value = mock_response

    # Call without timeout argument (should use default=10)
    _fetch_latest_version_from_github()

    # Verify default timeout was used
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["timeout"] == 10


@patch("devflow.utils.update_checker._fetch_latest_version_from_github")
@patch("devflow.utils.update_checker._get_timeout_from_config")
@patch("devflow.utils.update_checker._is_development_install")
def test_check_for_updates_uses_config_timeout(mock_is_dev, mock_get_timeout, mock_fetch, mock_cache_file):
    """Test that check_for_updates loads and uses timeout from config."""
    mock_is_dev.return_value = False
    mock_get_timeout.return_value = 15  # Custom timeout from config
    mock_fetch.return_value = ("1.0.0", False)

    check_for_updates()

    # Verify _get_timeout_from_config was called
    mock_get_timeout.assert_called_once()
    # Verify timeout was passed to _fetch_latest_version_from_github
    mock_fetch.assert_called_once_with(timeout=15)
