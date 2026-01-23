"""Path utilities for DevAIFlow."""

import os
from pathlib import Path


def get_cs_home() -> Path:
    """Get the DevAIFlow home directory.

    Returns the directory specified by DEVAIFLOW_HOME environment variable,
    or defaults to ~/.daf-sessions.

    The DEVAIFLOW_HOME variable supports:
    - Tilde expansion (e.g., ~/custom/path)
    - Absolute paths (e.g., /var/lib/devaiflow-sessions)
    - Relative paths (resolved to absolute)

    Returns:
        Path to DevAIFlow home directory

    Examples:
        >>> # With DEVAIFLOW_HOME not set
        >>> get_cs_home()
        PosixPath('/home/user/.daf-sessions')

        >>> # With DEVAIFLOW_HOME set to custom path
        >>> os.environ['DEVAIFLOW_HOME'] = '~/my-sessions'
        >>> get_cs_home()
        PosixPath('/home/user/my-sessions')
    """
    # Check for environment variable
    devaiflow_home = os.getenv("DEVAIFLOW_HOME")
    if devaiflow_home:
        return Path(devaiflow_home).expanduser().resolve()

    # Default to ~/.daf-sessions
    return Path.home() / ".daf-sessions"


def is_mock_mode() -> bool:
    """Check if mock mode is enabled.

    Checks for DAF_MOCK_MODE environment variable.

    Returns:
        True if mock mode is enabled, False otherwise
    """
    return os.getenv("DAF_MOCK_MODE") == "1"
