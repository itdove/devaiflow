"""Tests for path utilities."""

import os
from pathlib import Path

import pytest

from devflow.utils.paths import get_cs_home, is_mock_mode, _migrate_claude_sessions_to_daf


def test_get_cs_home_default_new_installation(monkeypatch, tmp_path):
    """Test get_cs_home returns ~/.daf-sessions for new installations."""
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


def test_get_cs_home_default_backward_compat(monkeypatch, tmp_path):
    """Test get_cs_home returns ~/.claude-sessions if it exists (backward compat)."""
    # Ensure environment variable is not set
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)

    # Mock Path.home() to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Create old directory (existing installation)
    old_dir = tmp_path / ".claude-sessions"
    old_dir.mkdir()

    result = get_cs_home()

    # Should use old directory for backward compatibility
    assert result == old_dir
    assert isinstance(result, Path)


def test_get_cs_home_priority_daf_over_claude(monkeypatch, tmp_path):
    """Test that ~/.daf-sessions takes priority over ~/.claude-sessions when both exist."""
    # Ensure environment variable is not set
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)

    # Mock Path.home() to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Create both directories
    new_dir = tmp_path / ".daf-sessions"
    old_dir = tmp_path / ".claude-sessions"
    new_dir.mkdir()
    old_dir.mkdir()

    result = get_cs_home()

    # Should use new directory (takes priority)
    assert result == new_dir
    assert result != old_dir
    assert isinstance(result, Path)


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
    monkeypatch.delenv("CLAUDE_SESSION_HOME", raising=False)
    monkeypatch.delenv("CS_HOME", raising=False)

    # Mock Path.home() to use tmp_path to avoid side effects
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result1 = get_cs_home()
    result2 = get_cs_home()

    assert result1 == result2


def test_get_cs_home_with_complex_path(monkeypatch, tmp_path):
    """Test get_cs_home handles complex paths with spaces and special chars."""
    complex_path = tmp_path / "my sessions" / "test-env"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(complex_path))
    monkeypatch.delenv("CLAUDE_SESSION_HOME", raising=False)
    monkeypatch.delenv("CS_HOME", raising=False)

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


# Tests for _migrate_claude_sessions_to_daf()


def test_migrate_claude_sessions_to_daf_success(tmp_path, capsys):
    """Test migration from .claude-sessions to .daf-sessions copies all files."""
    old_dir = tmp_path / ".claude-sessions"
    new_dir = tmp_path / ".daf-sessions"

    # Create old directory structure
    old_dir.mkdir()
    (old_dir / "sessions").mkdir()
    (old_dir / "backends").mkdir()
    (old_dir / "config.json").write_text('{"repos": {"workspace": "~/dev"}}')
    (old_dir / "organization.json").write_text('{"jira_project": "PROJ", "sync_filters": {"sync": {}}}')
    (old_dir / "team.json").write_text('{"jira_workstream": "Platform"}')
    (old_dir / "templates.json").write_text('{}')
    (old_dir / "sessions.json").write_text('{"sessions": {}}')
    (old_dir / "mocks").mkdir()

    # Create new directory (to trigger migration check)
    new_dir.mkdir()

    # Perform migration
    result = _migrate_claude_sessions_to_daf(old_dir, new_dir)

    # Verify migration was performed
    assert result is True

    # Verify all files were copied
    assert (new_dir / "sessions").exists()
    assert (new_dir / "backends").exists()
    assert (new_dir / "config.json").exists()
    assert (new_dir / "organization.json").exists()
    assert (new_dir / "team.json").exists()
    assert (new_dir / "templates.json").exists()
    assert (new_dir / "sessions.json").exists()
    assert (new_dir / "mocks").exists()
    assert (new_dir / ".migrated").exists()

    # Verify file contents
    assert (new_dir / "organization.json").read_text() == '{"jira_project": "PROJ", "sync_filters": {"sync": {}}}'
    assert (new_dir / "team.json").read_text() == '{"jira_workstream": "Platform"}'

    # Verify success message
    captured = capsys.readouterr()
    assert "Migrated sessions" in captured.err


def test_migrate_claude_sessions_already_migrated(tmp_path):
    """Test migration skips if .migrated marker exists."""
    old_dir = tmp_path / ".claude-sessions"
    new_dir = tmp_path / ".daf-sessions"

    # Create directories
    old_dir.mkdir()
    new_dir.mkdir()
    (new_dir / ".migrated").touch()

    # Perform migration
    result = _migrate_claude_sessions_to_daf(old_dir, new_dir)

    # Verify migration was skipped
    assert result is False


def test_migrate_claude_sessions_no_old_sessions(tmp_path):
    """Test migration skips if old sessions directory doesn't exist."""
    old_dir = tmp_path / ".claude-sessions"
    new_dir = tmp_path / ".daf-sessions"

    # Create old directory but no sessions
    old_dir.mkdir()
    new_dir.mkdir()

    # Perform migration
    result = _migrate_claude_sessions_to_daf(old_dir, new_dir)

    # Verify migration was skipped
    assert result is False


def test_migrate_claude_sessions_new_sessions_exist(tmp_path):
    """Test migration skips if new directory already has sessions."""
    old_dir = tmp_path / ".claude-sessions"
    new_dir = tmp_path / ".daf-sessions"

    # Create directories with sessions
    old_dir.mkdir()
    (old_dir / "sessions").mkdir()
    new_dir.mkdir()
    (new_dir / "sessions").mkdir()
    (new_dir / "sessions" / "existing-session").mkdir()

    # Perform migration
    result = _migrate_claude_sessions_to_daf(old_dir, new_dir)

    # Verify migration was skipped
    assert result is False


def test_migrate_claude_sessions_partial_files(tmp_path, capsys):
    """Test migration handles missing optional files gracefully."""
    old_dir = tmp_path / ".claude-sessions"
    new_dir = tmp_path / ".daf-sessions"

    # Create old directory with only some files
    old_dir.mkdir()
    (old_dir / "sessions").mkdir()
    (old_dir / "config.json").write_text('{}')
    # organization.json and team.json are missing (optional)

    # Create new directory
    new_dir.mkdir()

    # Perform migration
    result = _migrate_claude_sessions_to_daf(old_dir, new_dir)

    # Verify migration was performed
    assert result is True

    # Verify required files were copied
    assert (new_dir / "sessions").exists()
    assert (new_dir / "config.json").exists()
    assert (new_dir / ".migrated").exists()

    # Verify optional files are not present (as expected)
    assert not (new_dir / "organization.json").exists()
    assert not (new_dir / "team.json").exists()


def test_migrate_claude_sessions_json_mode_no_output(tmp_path, capsys, monkeypatch):
    """Test migration suppresses output in JSON mode."""
    import sys
    monkeypatch.setattr(sys, "argv", ["daf", "sync", "--json"])

    old_dir = tmp_path / ".claude-sessions"
    new_dir = tmp_path / ".daf-sessions"

    # Create old directory structure
    old_dir.mkdir()
    (old_dir / "sessions").mkdir()
    (old_dir / "config.json").write_text('{}')

    # Create new directory
    new_dir.mkdir()

    # Perform migration
    result = _migrate_claude_sessions_to_daf(old_dir, new_dir)

    # Verify migration was performed
    assert result is True

    # Verify no output in JSON mode
    captured = capsys.readouterr()
    assert "Migrated sessions" not in captured.err
