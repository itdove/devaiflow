"""Dependency checking utilities for external tools."""

import shutil
import subprocess
from typing import Optional, Dict

from devflow.exceptions import ToolNotFoundError


# Tool information mapping
TOOL_INFO: Dict[str, Dict[str, str]] = {
    "git": {
        "description": "Git version control",
        "install_url": "https://git-scm.com/downloads",
        "required": "true",
    },
    "claude": {
        "description": "Claude Code CLI",
        "install_url": "https://docs.claude.com/en/docs/claude-code/installation",
        "required": "true",
    },
    "gh": {
        "description": "GitHub CLI",
        "install_url": "https://cli.github.com/",
        "required": "false",
    },
    "glab": {
        "description": "GitLab CLI",
        "install_url": "https://gitlab.com/gitlab-org/cli",
        "required": "false",
    },
    "pytest": {
        "description": "Python testing framework",
        "install_url": "https://docs.pytest.org/",
        "required": "false",
    },
}


def check_tool_available(tool: str) -> bool:
    """Check if a command-line tool is available in PATH.

    Args:
        tool: Name of the tool to check (e.g., "git", "claude", "gh")

    Returns:
        True if tool is available, False otherwise
    """
    return shutil.which(tool) is not None


def get_tool_version(tool: str) -> Optional[str]:
    """Get version string for a tool if available.

    Args:
        tool: Name of the tool

    Returns:
        Version string if available, None otherwise
    """
    if not check_tool_available(tool):
        return None

    # Try common version flags
    version_flags = ["--version", "-v", "version"]

    for flag in version_flags:
        try:
            result = subprocess.run(
                [tool, flag],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Return first line of version output
                return result.stdout.strip().split('\n')[0]
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            continue

    return "installed"  # Tool exists but version unknown


def require_tool(tool: str, operation: str) -> None:
    """Check that a required tool is available, raise exception if not.

    Args:
        tool: Name of the tool to check
        operation: Description of the operation requiring the tool

    Raises:
        ToolNotFoundError: If the tool is not available in PATH
    """
    if not check_tool_available(tool):
        tool_info = TOOL_INFO.get(tool, {})
        install_url = tool_info.get("install_url", "")
        raise ToolNotFoundError(tool=tool, operation=operation, install_url=install_url)


def get_all_tools_status() -> Dict[str, Dict[str, str]]:
    """Get status of all known tools.

    Returns:
        Dictionary mapping tool names to their status information:
        {
            "git": {
                "available": "true",
                "version": "2.39.0",
                "description": "Git version control",
                "install_url": "https://git-scm.com/downloads",
                "required": "true"
            },
            ...
        }
    """
    status = {}

    for tool, info in TOOL_INFO.items():
        available = check_tool_available(tool)
        version = get_tool_version(tool) if available else None

        status[tool] = {
            "available": "true" if available else "false",
            "version": version or "",
            "description": info.get("description", ""),
            "install_url": info.get("install_url", ""),
            "required": info.get("required", "false"),
        }

    return status
