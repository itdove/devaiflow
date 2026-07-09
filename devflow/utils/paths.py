"""Path utilities for DevAIFlow."""

import os
from pathlib import Path


def _is_valid_legacy_home(path: Path) -> bool:
    """Check if a legacy ~/.daf-sessions directory is a genuine installation.

    An empty ~/.daf-sessions/ (or one with only sessions/) can be created
    accidentally by stale processes (e.g., an old dashboard). Only treat it
    as a valid legacy home if it contains config files that indicate a real
    installation.
    """
    return (path / "config.json").exists() or (path / "sessions.json").exists()


def get_cs_home() -> Path:
    """Get the DevAIFlow home directory.

    Resolution priority:
        1. DEVAIFLOW_HOME env var (explicit override, highest priority)
        2. ~/.daf-sessions with config files (legacy compatibility)
        3. XDG_DATA_HOME/devaiflow (XDG Base Directory Specification)
        4. ~/.local/share/devaiflow (XDG default)

    The DEVAIFLOW_HOME variable supports:
    - Tilde expansion (e.g., ~/custom/path)
    - Absolute paths (e.g., /var/lib/devaiflow-sessions)
    - Relative paths (resolved to absolute)

    Migration from legacy path:
        1. Move ~/.daf-sessions/* to ~/.local/share/devaiflow/
        2. Remove ~/.daf-sessions/
        3. DevAIFlow picks up the XDG path automatically

    Returns:
        Path to DevAIFlow home directory

    Examples:
        >>> # New install (no legacy dir, no env vars)
        >>> get_cs_home()
        PosixPath('/home/user/.local/share/devaiflow')

        >>> # With DEVAIFLOW_HOME set
        >>> os.environ['DEVAIFLOW_HOME'] = '~/my-sessions'
        >>> get_cs_home()
        PosixPath('/home/user/my-sessions')

        >>> # With XDG_DATA_HOME set (no legacy dir)
        >>> os.environ['XDG_DATA_HOME'] = '/home/user/.data'
        >>> get_cs_home()
        PosixPath('/home/user/.data/devaiflow')
    """
    # 1. Explicit env var (highest priority)
    devaiflow_home = os.getenv("DEVAIFLOW_HOME")
    if devaiflow_home:
        return Path(devaiflow_home).expanduser().resolve()

    # 2. Legacy path with valid config (migration compat — don't silently move data)
    legacy_path = Path.home() / ".daf-sessions"
    if legacy_path.exists() and _is_valid_legacy_home(legacy_path):
        return legacy_path

    # 3. XDG compliant
    xdg_data = os.getenv("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data).expanduser().resolve() / "devaiflow"

    # 4. XDG default
    return Path.home() / ".local" / "share" / "devaiflow"


def _is_unified_mode() -> bool:
    """Check if DevAIFlow should use a single unified directory.

    Returns True when DEVAIFLOW_HOME is set or the legacy ~/.daf-sessions
    directory contains valid config files. An empty ~/.daf-sessions/ created
    by a stale process does not trigger unified mode.
    """
    if bool(os.getenv("DEVAIFLOW_HOME")):
        return True
    legacy_path = Path.home() / ".daf-sessions"
    return legacy_path.exists() and _is_valid_legacy_home(legacy_path)


def get_cs_config_home() -> Path:
    """Get the DevAIFlow configuration directory.

    In unified mode (DEVAIFLOW_HOME set or legacy ~/.daf-sessions exists),
    returns the same path as get_cs_home() for backward compatibility.

    In XDG mode (new installs):
        1. XDG_CONFIG_HOME/devaiflow (if XDG_CONFIG_HOME is set)
        2. ~/.config/devaiflow (XDG default)

    Stores: config.json, enterprise.json, organization.json, team.json,
    backends/, templates/, .claude/skills/, context .md files.

    Returns:
        Path to DevAIFlow configuration directory
    """
    if _is_unified_mode():
        return get_cs_home()

    xdg_config = os.getenv("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config).expanduser().resolve() / "devaiflow"

    return Path.home() / ".config" / "devaiflow"


def get_cs_state_home() -> Path:
    """Get the DevAIFlow state directory.

    In unified mode (DEVAIFLOW_HOME set or legacy ~/.daf-sessions exists),
    returns the same path as get_cs_home() for backward compatibility.

    In XDG mode (new installs):
        1. XDG_STATE_HOME/devaiflow (if XDG_STATE_HOME is set)
        2. ~/.local/state/devaiflow (XDG default)

    Stores: audit.log, version_check_cache.json, suggestions.json,
    state/ (dashboard pid/port).

    Returns:
        Path to DevAIFlow state directory
    """
    if _is_unified_mode():
        return get_cs_home()

    xdg_state = os.getenv("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state).expanduser().resolve() / "devaiflow"

    return Path.home() / ".local" / "state" / "devaiflow"


def get_cs_cache_home() -> Path:
    """Get the DevAIFlow cache directory.

    In unified mode (DEVAIFLOW_HOME set or legacy ~/.daf-sessions exists),
    returns the same path as get_cs_home() for backward compatibility.

    In XDG mode (new installs):
        1. XDG_CACHE_HOME/devaiflow (if XDG_CACHE_HOME is set)
        2. ~/.cache/devaiflow (XDG default)

    On Windows (non-unified, no XDG_CACHE_HOME):
        %LOCALAPPDATA%/devaiflow/cache

    Stores: session clones (clones/), other reproducible cached artifacts.

    Returns:
        Path to DevAIFlow cache directory
    """
    if _is_unified_mode():
        return get_cs_home()

    xdg_cache = os.getenv("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser().resolve() / "devaiflow"

    if os.name == "nt":
        local_app = os.getenv("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "devaiflow" / "cache"

    return Path.home() / ".cache" / "devaiflow"


def get_claude_config_dir() -> Path:
    """Get Claude Code config directory, respecting CLAUDE_CONFIG_DIR.

    This function respects the official Claude Code environment variable
    CLAUDE_CONFIG_DIR, which allows users to customize where Claude Code
    stores its configuration and data files.

    Returns:
        Path to Claude config directory:
        - $CLAUDE_CONFIG_DIR if set (official Claude Code variable)
        - ~/.claude otherwise (backward compatible)

    Examples:
        >>> # With CLAUDE_CONFIG_DIR not set
        >>> get_claude_config_dir()
        PosixPath('/home/user/.claude')

        >>> # With CLAUDE_CONFIG_DIR set to custom path
        >>> os.environ['CLAUDE_CONFIG_DIR'] = '~/.config/claude'
        >>> get_claude_config_dir()
        PosixPath('/home/user/.config/claude')
    """
    claude_config_dir = os.getenv("CLAUDE_CONFIG_DIR")
    if claude_config_dir:
        return Path(claude_config_dir).expanduser().resolve()
    return Path.home() / ".claude"


def is_mock_mode() -> bool:
    """Check if mock mode is enabled.

    Checks for DAF_MOCK_MODE environment variable.

    Returns:
        True if mock mode is enabled, False otherwise
    """
    return os.getenv("DAF_MOCK_MODE") == "1"
