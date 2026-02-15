"""Utilities for workspace management and auto-upgrade."""

from pathlib import Path
from typing import Tuple, Optional
from rich.console import Console

console = Console()


def ensure_workspace_skills_and_commands(
    workspace_path: str,
    quiet: bool = True
) -> Tuple[bool, Optional[str]]:
    """Ensure workspace has up-to-date skills and commands installed.

    This function checks if the workspace has bundled skills and commands installed,
    and installs/upgrades them if necessary. It's used to automatically maintain
    workspace skills/commands when:
    - Creating a new workspace (daf workspace add)
    - Setting default workspace (daf workspace set-default)
    - Using -w flag with session commands

    Args:
        workspace_path: Path to workspace directory
        quiet: If True, suppress console output (default: True for auto-operations)

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - (True, None) if skills/commands are up-to-date or were successfully installed
        - (False, error_message) if installation failed

    Example:
        >>> success, error = ensure_workspace_skills_and_commands("/path/to/workspace")
        >>> if not success:
        ...     console.print(f"[red]✗[/red] {error}")
    """
    from devflow.utils.claude_commands import install_or_upgrade_skills

    workspace = Path(workspace_path).expanduser().resolve()

    # Check if workspace exists
    if not workspace.exists():
        return False, f"Workspace directory does not exist: {workspace_path}"

    try:
        # Install/upgrade skills (commands and skills are now unified)
        changed_skills, _, failed_skills = install_or_upgrade_skills(
            str(workspace),
            dry_run=False,
            quiet=quiet
        )

        # Check for failures
        if failed_skills:
            return False, f"Failed to install/upgrade: {', '.join(failed_skills)}"

        # If anything was changed, report it (unless quiet)
        if not quiet and changed_skills:
            console.print(f"[green]✓[/green] Installed/upgraded {len(changed_skills)} skills")

        return True, None

    except Exception as e:
        return False, f"Error installing skills/commands: {e}"
