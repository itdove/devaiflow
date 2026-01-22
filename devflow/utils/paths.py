"""Path utilities for DevAIFlow."""

import os
import shutil
import sys
from pathlib import Path


def _migrate_claude_sessions_to_daf(old_dir: Path, new_dir: Path) -> bool:
    """Migrate data from .claude-sessions to .daf-sessions.

    This is a one-time migration that copies:
    - sessions/ directory (all session data)
    - backends/ directory (backend configurations)
    - config.json (main configuration)
    - organization.json (organization settings)
    - team.json (team settings)
    - templates.json (session templates)
    - mocks/ directory (mock data, if exists)

    Args:
        old_dir: Path to .claude-sessions
        new_dir: Path to .daf-sessions

    Returns:
        True if migration was performed, False if skipped
    """
    # Check if migration marker exists
    migration_marker = new_dir / ".migrated"
    if migration_marker.exists():
        return False

    # Check if old directory has sessions
    old_sessions_dir = old_dir / "sessions"
    if not old_sessions_dir.exists():
        return False

    # Check if new directory already has sessions (skip migration)
    new_sessions_dir = new_dir / "sessions"
    if new_sessions_dir.exists() and list(new_sessions_dir.iterdir()):
        return False

    # Perform migration
    try:
        # Ensure new directory exists
        new_dir.mkdir(parents=True, exist_ok=True)

        # Migrate sessions directory
        if old_sessions_dir.exists():
            if new_sessions_dir.exists():
                shutil.rmtree(new_sessions_dir)
            shutil.copytree(old_sessions_dir, new_sessions_dir)

        # Migrate backends directory
        old_backends = old_dir / "backends"
        new_backends = new_dir / "backends"
        if old_backends.exists():
            if new_backends.exists():
                shutil.rmtree(new_backends)
            shutil.copytree(old_backends, new_backends)

        # Migrate config.json
        old_config = old_dir / "config.json"
        new_config = new_dir / "config.json"
        if old_config.exists():
            shutil.copy2(old_config, new_config)

        # Migrate organization.json
        old_organization = old_dir / "organization.json"
        new_organization = new_dir / "organization.json"
        if old_organization.exists():
            shutil.copy2(old_organization, new_organization)

        # Migrate team.json
        old_team = old_dir / "team.json"
        new_team = new_dir / "team.json"
        if old_team.exists():
            shutil.copy2(old_team, new_team)

        # Migrate templates.json
        old_templates = old_dir / "templates.json"
        new_templates = new_dir / "templates.json"
        if old_templates.exists():
            shutil.copy2(old_templates, new_templates)

        # Migrate sessions.json (session metadata)
        old_sessions_json = old_dir / "sessions.json"
        new_sessions_json = new_dir / "sessions.json"
        if old_sessions_json.exists():
            shutil.copy2(old_sessions_json, new_sessions_json)

        # Migrate mocks directory (if exists)
        old_mocks = old_dir / "mocks"
        new_mocks = new_dir / "mocks"
        if old_mocks.exists():
            if new_mocks.exists():
                shutil.rmtree(new_mocks)
            shutil.copytree(old_mocks, new_mocks)

        # Create migration marker
        migration_marker.touch()

        # Print success message (suppress in JSON mode)
        if "--json" not in sys.argv:
            print(
                f"✓ Migrated sessions from {old_dir} to {new_dir}",
                file=sys.stderr
            )

        return True

    except Exception as e:
        # If migration fails, print error but don't crash
        if "--json" not in sys.argv:
            print(
                f"Warning: Failed to migrate sessions: {e}",
                file=sys.stderr
            )
        return False


def get_cs_home() -> Path:
    """Get the DevAIFlow home directory.

    Returns the directory specified by DEVAIFLOW_HOME environment variable,
    or defaults to ~/.daf-sessions for new installations (with backward
    compatibility for existing ~/.claude-sessions installations).

    The DEVAIFLOW_HOME variable supports:
    - Tilde expansion (e.g., ~/custom/path)
    - Absolute paths (e.g., /var/lib/devaiflow-sessions)
    - Relative paths (resolved to absolute)

    Returns:
        Path to DevAIFlow home directory

    Examples:
        >>> # With DEVAIFLOW_HOME not set (new installation)
        >>> get_cs_home()
        PosixPath('/home/user/.daf-sessions')

        >>> # With existing ~/.claude-sessions (backward compatibility)
        >>> get_cs_home()
        PosixPath('/home/user/.claude-sessions')

        >>> # With DEVAIFLOW_HOME set to custom path
        >>> os.environ['DEVAIFLOW_HOME'] = '~/my-sessions'
        >>> get_cs_home()
        PosixPath('/home/user/my-sessions')
    """
    # Check for environment variable
    devaiflow_home = os.getenv("DEVAIFLOW_HOME")
    if devaiflow_home:
        return Path(devaiflow_home).expanduser().resolve()

    # Default: Search for directories in priority order
    # 1. ~/.daf-sessions (new default)
    # 2. ~/.claude-sessions (backward compatibility)
    new_default = Path.home() / ".daf-sessions"
    old_default = Path.home() / ".claude-sessions"

    # Attempt one-time migration from .claude-sessions to .daf-sessions
    if new_default.exists() and old_default.exists():
        _migrate_claude_sessions_to_daf(old_default, new_default)

    # Use new default if it exists
    if new_default.exists():
        return new_default

    # Fall back to old default if it exists (backward compat)
    if old_default.exists():
        return old_default

    # Neither exists - use new default for new installations
    return new_default


def is_mock_mode() -> bool:
    """Check if mock mode is enabled.

    Checks for DAF_MOCK_MODE environment variable.

    Returns:
        True if mock mode is enabled, False otherwise
    """
    return os.getenv("DAF_MOCK_MODE") == "1"
