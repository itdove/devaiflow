"""Tests for path utilities."""

import os
from pathlib import Path

import pytest

from devflow.utils.paths import get_cs_home, is_mock_mode


def test_get_cs_home_default(monkeypatch, tmp_path):
    """Test get_cs_home returns ~/.daf-sessions by default."""
    # Ensure environment variable is not set
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)

    # Mock Path.home() to use tmp_path to avoid side effects
    import devflow.utils.paths
    original_home = Path.home
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_cs_home()
    expected = tmp_path / ".daf-sessions"

    assert result == expected
    assert isinstance(result, Path)

    # Restore original
    monkeypatch.setattr(Path, "home", original_home)


def test_get_cs_home_with_devaiflow_home(monkeypatch, tmp_path):
    """Test get_cs_home returns DEVAIFLOW_HOME value when set."""
    custom_path = tmp_path / "custom-sessions"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(custom_path))

    result = get_cs_home()

    assert result == custom_path
    assert isinstance(result, Path)


def test_get_cs_home_precedence_devaiflow_home_wins(monkeypatch, tmp_path):
    """Test that DEVAIFLOW_HOME takes precedence over default paths."""
    devaiflow_path = tmp_path / "devaiflow-sessions"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(devaiflow_path))

    result = get_cs_home()

    # Should use DEVAIFLOW_HOME
    assert result == devaiflow_path


def test_get_cs_home_with_tilde_expansion(monkeypatch):
    """Test get_cs_home expands tilde in DEVAIFLOW_HOME."""
    monkeypatch.setenv("DEVAIFLOW_HOME", "~/my-sessions")
    monkeypatch.delenv("CLAUDE_SESSION_HOME", raising=False)
    monkeypatch.delenv("CS_HOME", raising=False)

    result = get_cs_home()
    expected = Path.home() / "my-sessions"

    assert result == expected
    assert not str(result).startswith("~")


def test_get_cs_home_with_relative_path(monkeypatch):
    """Test get_cs_home resolves relative paths to absolute."""
    monkeypatch.setenv("DEVAIFLOW_HOME", "relative/path")
    monkeypatch.delenv("CLAUDE_SESSION_HOME", raising=False)
    monkeypatch.delenv("CS_HOME", raising=False)

    result = get_cs_home()

    assert result.is_absolute()
    assert str(result).endswith("relative/path")


def test_get_cs_home_with_absolute_path(monkeypatch, tmp_path):
    """Test get_cs_home handles absolute paths."""
    custom_path = tmp_path / "absolute-sessions"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(custom_path))
    monkeypatch.delenv("CLAUDE_SESSION_HOME", raising=False)
    monkeypatch.delenv("CS_HOME", raising=False)

    result = get_cs_home()

    assert result == custom_path
    assert result.is_absolute()


def test_get_cs_home_consistency(monkeypatch, tmp_path):
    """Test get_cs_home returns same value on multiple calls."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)

    # Mock Path.home() to use tmp_path to avoid side effects
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result1 = get_cs_home()
    result2 = get_cs_home()

    assert result1 == result2


def test_get_cs_home_with_complex_path(monkeypatch, tmp_path):
    """Test get_cs_home handles complex paths with spaces and special chars."""
    complex_path = tmp_path / "my sessions" / "test-env"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(complex_path))

    result = get_cs_home()

    assert result == complex_path
    assert isinstance(result, Path)


# Tests for is_mock_mode()


def test_is_mock_mode_with_daf_mock_mode(monkeypatch):
    """Test is_mock_mode returns True when DAF_MOCK_MODE=1."""
    monkeypatch.setenv("DAF_MOCK_MODE", "1")

    assert is_mock_mode() is True


def test_is_mock_mode_neither_set(monkeypatch):
    """Test is_mock_mode returns False when DAF_MOCK_MODE is not set."""
    monkeypatch.delenv("DAF_MOCK_MODE", raising=False)

    assert is_mock_mode() is False


def test_is_mock_mode_with_daf_set_to_zero(monkeypatch):
    """Test is_mock_mode returns False when DAF_MOCK_MODE=0."""
    monkeypatch.setenv("DAF_MOCK_MODE", "0")

    assert is_mock_mode() is False
