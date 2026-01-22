"""User detection utilities."""

import getpass
import os


def get_current_user() -> str:
    """Get current system username.

    Checks environment variables first (for CI/automation), then falls back
    to system user detection.

    Returns:
        Current username as a string
    """
    # Check for explicit override (useful for testing or CI)
    user = os.getenv("CS_USER")
    if user:
        return user

    # Try standard USER environment variable
    user = os.getenv("USER")
    if user:
        return user

    # Fall back to getpass (works on all platforms)
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"
