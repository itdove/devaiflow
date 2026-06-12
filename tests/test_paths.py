"""Tests for path utilities."""

import os
from pathlib import Path

import pytest

from devflow.utils.paths import (
    _is_valid_legacy_home,
    _is_unified_mode,
    get_cs_home,
    get_cs_config_home,
    get_cs_state_home,
    is_mock_mode,
    get_claude_config_dir,
)


def test_get_cs_home_default_xdg(monkeypatch, tmp_path):
    """Test get_cs_home returns XDG default when no env vars or legacy dir."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_cs_home()
    expected = tmp_path / ".local" / "share" / "devaiflow"

    assert result == expected
    assert isinstance(result, Path)


def test_get_cs_home_legacy_compat(monkeypatch, tmp_path):
    """Test get_cs_home uses legacy ~/.daf-sessions when it has config files."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    legacy_dir = tmp_path / ".daf-sessions"
    legacy_dir.mkdir()
    (legacy_dir / "config.json").write_text("{}")

    result = get_cs_home()

    assert result == legacy_dir


def test_get_cs_home_legacy_overrides_xdg(monkeypatch, tmp_path):
    """Test legacy ~/.daf-sessions takes priority over XDG_DATA_HOME."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    legacy_dir = tmp_path / ".daf-sessions"
    legacy_dir.mkdir()
    (legacy_dir / "config.json").write_text("{}")

    result = get_cs_home()

    assert result == legacy_dir


def test_get_cs_home_xdg_data_home(monkeypatch, tmp_path):
    """Test get_cs_home uses XDG_DATA_HOME when set (no legacy dir)."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    xdg_data = tmp_path / "xdg-data"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_cs_home()

    assert result == xdg_data / "devaiflow"


def test_get_cs_home_xdg_data_home_tilde(monkeypatch, tmp_path):
    """Test XDG_DATA_HOME with tilde expansion."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", "~/.data")
    # Use tmp_path as home to avoid real ~/.daf-sessions triggering legacy path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_cs_home()
    expected = Path("~/.data").expanduser().resolve() / "devaiflow"

    assert result == expected
    assert not str(result).startswith("~")


def test_get_cs_home_with_devaiflow_home(monkeypatch, tmp_path):
    """Test get_cs_home returns DEVAIFLOW_HOME value when set."""
    custom_path = tmp_path / "custom-sessions"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(custom_path))

    result = get_cs_home()

    assert result == custom_path
    assert isinstance(result, Path)


def test_get_cs_home_devaiflow_home_overrides_all(monkeypatch, tmp_path):
    """Test DEVAIFLOW_HOME takes precedence over legacy dir and XDG."""
    devaiflow_path = tmp_path / "devaiflow-sessions"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(devaiflow_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Create valid legacy dir — should still be ignored when DEVAIFLOW_HOME is set
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    (legacy / "config.json").write_text("{}")

    result = get_cs_home()

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
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
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


# Tests for get_cs_config_home()


def test_get_cs_config_home_xdg_default(monkeypatch, tmp_path):
    """Test get_cs_config_home returns XDG default for new installs."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_cs_config_home()

    assert result == tmp_path / ".config" / "devaiflow"


def test_get_cs_config_home_xdg_env(monkeypatch, tmp_path):
    """Test get_cs_config_home uses XDG_CONFIG_HOME when set."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    xdg_config = tmp_path / "custom-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_cs_config_home()

    assert result == xdg_config / "devaiflow"


def test_get_cs_config_home_unified_with_devaiflow_home(monkeypatch, tmp_path):
    """Test get_cs_config_home returns same as get_cs_home when DEVAIFLOW_HOME set."""
    custom = tmp_path / "unified"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(custom))

    assert get_cs_config_home() == get_cs_home()


def test_get_cs_config_home_unified_with_legacy(monkeypatch, tmp_path):
    """Test get_cs_config_home returns same as get_cs_home when legacy dir has config."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    (legacy / "config.json").write_text("{}")

    assert get_cs_config_home() == get_cs_home()


def test_get_cs_config_home_split_from_data(monkeypatch, tmp_path):
    """Test config and data return different paths for new installs."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert get_cs_config_home() != get_cs_home()
    assert get_cs_config_home() == tmp_path / ".config" / "devaiflow"
    assert get_cs_home() == tmp_path / ".local" / "share" / "devaiflow"


# Tests for get_cs_state_home()


def test_get_cs_state_home_xdg_default(monkeypatch, tmp_path):
    """Test get_cs_state_home returns XDG default for new installs."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_cs_state_home()

    assert result == tmp_path / ".local" / "state" / "devaiflow"


def test_get_cs_state_home_xdg_env(monkeypatch, tmp_path):
    """Test get_cs_state_home uses XDG_STATE_HOME when set."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    xdg_state = tmp_path / "custom-state"
    monkeypatch.setenv("XDG_STATE_HOME", str(xdg_state))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_cs_state_home()

    assert result == xdg_state / "devaiflow"


def test_get_cs_state_home_unified_with_devaiflow_home(monkeypatch, tmp_path):
    """Test get_cs_state_home returns same as get_cs_home when DEVAIFLOW_HOME set."""
    custom = tmp_path / "unified"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(custom))

    assert get_cs_state_home() == get_cs_home()


def test_get_cs_state_home_unified_with_legacy(monkeypatch, tmp_path):
    """Test get_cs_state_home returns same as get_cs_home when legacy dir has config."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    (legacy / "config.json").write_text("{}")

    assert get_cs_state_home() == get_cs_home()


def test_all_three_unified_when_devaiflow_home(monkeypatch, tmp_path):
    """Test all three functions return same path in unified mode."""
    custom = tmp_path / "unified"
    monkeypatch.setenv("DEVAIFLOW_HOME", str(custom))

    home = get_cs_home()
    config = get_cs_config_home()
    state = get_cs_state_home()

    assert home == config == state


def test_all_three_split_for_new_install(monkeypatch, tmp_path):
    """Test all three functions return different paths for new installs."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    home = get_cs_home()
    config = get_cs_config_home()
    state = get_cs_state_home()

    assert home != config
    assert home != state
    assert config != state


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


# Tests for get_claude_config_dir()


def test_get_claude_config_dir_default(monkeypatch, tmp_path):
    """Test get_claude_config_dir returns ~/.claude by default."""
    # Ensure environment variable is not set
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)

    # Mock Path.home() to use tmp_path to avoid side effects
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = get_claude_config_dir()
    expected = tmp_path / ".claude"

    assert result == expected
    assert isinstance(result, Path)


def test_get_claude_config_dir_with_env_var(monkeypatch, tmp_path):
    """Test get_claude_config_dir returns CLAUDE_CONFIG_DIR value when set."""
    custom_path = tmp_path / "custom-claude-config"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_path))

    result = get_claude_config_dir()

    assert result == custom_path
    assert isinstance(result, Path)


def test_get_claude_config_dir_with_tilde_expansion(monkeypatch):
    """Test get_claude_config_dir expands tilde in CLAUDE_CONFIG_DIR."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "~/.config/claude")

    result = get_claude_config_dir()
    expected = Path.home() / ".config/claude"

    assert result == expected
    assert not str(result).startswith("~")


def test_get_claude_config_dir_with_relative_path(monkeypatch):
    """Test get_claude_config_dir resolves relative paths to absolute."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "relative/claude/path")

    result = get_claude_config_dir()

    assert result.is_absolute()
    assert str(result).endswith("relative/claude/path")


def test_get_claude_config_dir_with_absolute_path(monkeypatch, tmp_path):
    """Test get_claude_config_dir handles absolute paths."""
    custom_path = tmp_path / "absolute-claude-config"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_path))

    result = get_claude_config_dir()

    assert result == custom_path
    assert result.is_absolute()


def test_get_claude_config_dir_consistency(monkeypatch, tmp_path):
    """Test get_claude_config_dir returns same value on multiple calls."""
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)

    # Mock Path.home() to use tmp_path to avoid side effects
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result1 = get_claude_config_dir()
    result2 = get_claude_config_dir()

    assert result1 == result2


def test_get_claude_config_dir_with_complex_path(monkeypatch, tmp_path):
    """Test get_claude_config_dir handles paths with spaces and special chars."""
    complex_path = tmp_path / "my config" / "claude-data"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(complex_path))

    result = get_claude_config_dir()

    assert result == complex_path
    assert isinstance(result, Path)


def test_get_claude_config_dir_different_from_devaiflow_home(monkeypatch, tmp_path):
    """Test get_claude_config_dir and get_cs_home can have different values."""
    claude_path = tmp_path / "claude-config"
    devaiflow_path = tmp_path / "devaiflow-sessions"

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_path))
    monkeypatch.setenv("DEVAIFLOW_HOME", str(devaiflow_path))

    claude_result = get_claude_config_dir()
    devaiflow_result = get_cs_home()

    assert claude_result != devaiflow_result
    assert claude_result == claude_path
    assert devaiflow_result == devaiflow_path


# Tests for _is_valid_legacy_home() and stale legacy directory (#510)


def test_is_valid_legacy_home_empty_dir(tmp_path):
    """Empty directory is not a valid legacy home."""
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    assert _is_valid_legacy_home(legacy) is False


def test_is_valid_legacy_home_sessions_subdir_only(tmp_path):
    """Directory with only sessions/ subdir is not valid (stale dashboard scenario)."""
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    (legacy / "sessions").mkdir()
    assert _is_valid_legacy_home(legacy) is False


def test_is_valid_legacy_home_with_config_json(tmp_path):
    """Directory with config.json is a valid legacy home."""
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    (legacy / "config.json").write_text("{}")
    assert _is_valid_legacy_home(legacy) is True


def test_is_valid_legacy_home_with_sessions_json(tmp_path):
    """Directory with sessions.json is a valid legacy home."""
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    (legacy / "sessions.json").write_text("{}")
    assert _is_valid_legacy_home(legacy) is True


def test_stale_legacy_does_not_poison_config_resolution(monkeypatch, tmp_path):
    """Issue #510: Stale dashboard creating ~/.daf-sessions must not poison XDG resolution."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Simulate stale dashboard creating empty dirs
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    (legacy / "sessions").mkdir()
    (legacy / "state").mkdir()

    # All paths should use XDG, not the stale legacy dir
    assert get_cs_home() == tmp_path / ".local" / "share" / "devaiflow"
    assert get_cs_config_home() == tmp_path / ".config" / "devaiflow"
    assert get_cs_state_home() == tmp_path / ".local" / "state" / "devaiflow"
    assert _is_unified_mode() is False


def test_unified_mode_with_devaiflow_home_env(monkeypatch, tmp_path):
    """DEVAIFLOW_HOME env var always triggers unified mode."""
    monkeypatch.setenv("DEVAIFLOW_HOME", str(tmp_path / "custom"))
    assert _is_unified_mode() is True


def test_unified_mode_with_valid_legacy_home(monkeypatch, tmp_path):
    """Valid legacy home with config.json triggers unified mode."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    (legacy / "config.json").write_text("{}")
    assert _is_unified_mode() is True


def test_unified_mode_not_triggered_by_empty_legacy(monkeypatch, tmp_path):
    """Empty legacy directory does not trigger unified mode."""
    monkeypatch.delenv("DEVAIFLOW_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    legacy = tmp_path / ".daf-sessions"
    legacy.mkdir()
    assert _is_unified_mode() is False
