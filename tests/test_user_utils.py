"""Tests for user detection utilities."""

import os

import pytest

from devflow.utils.user import get_current_user


def test_get_current_user_from_cs_user_env(monkeypatch):
    """Test getting user from CS_USER environment variable."""
    monkeypatch.setenv("CS_USER", "test-user")

    result = get_current_user()

    assert result == "test-user"


def test_get_current_user_from_user_env(monkeypatch):
    """Test getting user from USER environment variable."""
    monkeypatch.delenv("CS_USER", raising=False)
    monkeypatch.setenv("USER", "system-user")

    result = get_current_user()

    assert result == "system-user"


def test_get_current_user_fallback_to_getpass(monkeypatch):
    """Test fallback to getpass.getuser()."""
    monkeypatch.delenv("CS_USER", raising=False)
    monkeypatch.delenv("USER", raising=False)

    result = get_current_user()

    # Should fall back to getpass, which returns actual user
    assert result is not None
    assert len(result) > 0
    assert result != "unknown"


def test_get_current_user_getpass_exception(monkeypatch):
    """Test handling of getpass exception."""
    import getpass

    monkeypatch.delenv("CS_USER", raising=False)
    monkeypatch.delenv("USER", raising=False)

    def mock_getuser():
        raise Exception("Simulated getpass error")

    monkeypatch.setattr(getpass, "getuser", mock_getuser)

    result = get_current_user()

    assert result == "unknown"
