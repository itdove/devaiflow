"""Utilities for workspace management and auto-upgrade."""

from pathlib import Path
from typing import Tuple, Optional
from rich.console import Console

console = Console()


def ensure_workspace_skills_and_commands(
    workspace_path: str,
    quiet: bool = True
) -> Tuple[bool, Optional[str]]:
    """Ensure global skills are up-to-date.

    This function installs/upgrades bundled skills globally to ~/.claude/skills/.
    Skills are now installed globally (not per-workspace) since Claude Code 2.1.3+
    unified slash commands and skills into a single system.

    Note: The workspace_path parameter is kept for backwards compatibility but is
    only used to verify the workspace exists. Skills are installed globally.

    Args:
        workspace_path: Path to workspace directory (for validation only)
        quiet: If True, suppress console output (default: True for auto-operations)

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - (True, None) if skills are up-to-date or were successfully installed
        - (False, error_message) if installation failed

    Example:
        >>> success, error = ensure_workspace_skills_and_commands("/path/to/workspace")
        >>> if not success:
        ...     console.print(f"[red]✗[/red] {error}")
    """
    from devflow.utils.claude_commands import (
        install_or_upgrade_slash_commands,
        install_or_upgrade_reference_skills
    )

    workspace = Path(workspace_path).expanduser().resolve()

    # Check if workspace exists
    if not workspace.exists():
        return False, f"Workspace directory does not exist: {workspace_path}"

    try:
        # Install/upgrade slash commands globally to ~/.claude/skills/
        changed_slash, _, failed_slash = install_or_upgrade_slash_commands(
            dry_run=False,
            quiet=quiet
        )

        # Install/upgrade reference skills globally to ~/.claude/skills/
        changed_ref, _, failed_ref = install_or_upgrade_reference_skills(
            dry_run=False,
            quiet=quiet
        )

        # Combine results
        changed_skills = changed_slash + changed_ref
        failed_skills = failed_slash + failed_ref

        # Check for failures
        if failed_skills:
            return False, f"Failed to install/upgrade: {', '.join(failed_skills)}"

        # If anything was changed, report it (unless quiet)
        if not quiet and changed_skills:
            console.print(f"[green]✓[/green] Installed/upgraded {len(changed_skills)} skills globally to ~/.claude/skills/")

        return True, None

    except Exception as e:
        return False, f"Error installing skills: {e}"
