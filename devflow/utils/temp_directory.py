"""Temporary directory utilities for issue tracker ticket creation sessions.

This module provides shared functions for cloning repositories to temporary
directories for clean analysis during ticket creation sessions.

Extracted from jira_new_command.py to be reused by jira_open_command.py.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from rich.prompt import Confirm

from devflow.cli.utils import console_print
from devflow.git.utils import GitUtils


def should_clone_to_temp(path: Path) -> bool:
    """Check if the current directory is a git repository.

    Only prompt for cloning if we're in a git repository.

    Args:
        path: Directory path to check

    Returns:
        True if we should prompt to clone, False otherwise
    """
    return GitUtils.is_git_repository(path)


def prompt_and_clone_to_temp(current_path: Path) -> Optional[tuple[str, str]]:
    """Prompt user and clone repository to temporary directory.

    Args:
        current_path: Current project directory path

    Returns:
        Tuple of (temp_directory, original_project_path) if cloned,
        None if user declined or cloning failed
    """
    # Prompt user
    if not Confirm.ask(
        "Clone project in a temporary directory to ensure analysis is based on main branch?",
        default=True
    ):
        console_print("[dim]Using current directory[/dim]")
        return None

    # Get remote URL
    console_print("[dim]Detecting git remote URL...[/dim]")
    remote_url = GitUtils.get_remote_url(current_path)
    if not remote_url:
        console_print("[yellow]⚠[/yellow] Could not detect git remote URL")
        console_print("[yellow]Falling back to current directory[/yellow]")
        return None

    console_print(f"[dim]Remote URL: {remote_url}[/dim]")

    # Create temporary directory
    try:
        temp_dir = tempfile.mkdtemp(prefix="daf-jira-analysis-")
        console_print(f"[dim]Created temporary directory: {temp_dir}[/dim]")
    except Exception as e:
        console_print(f"[red]✗[/red] Failed to create temporary directory: {e}")
        console_print("[yellow]Falling back to current directory[/yellow]")
        return None

    # Clone repository
    console_print(f"[cyan]Cloning repository...[/cyan]")
    console_print(f"[dim]This may take a moment...[/dim]")

    if not GitUtils.clone_repository(remote_url, Path(temp_dir), branch=None):
        console_print(f"[red]✗[/red] Failed to clone repository")
        console_print("[yellow]Falling back to current directory[/yellow]")
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        return None

    # Checkout default branch
    default_branch = GitUtils.get_default_branch(Path(temp_dir))
    if default_branch:
        console_print(f"[dim]Checked out default branch: {default_branch}[/dim]")
        # Branch was already checked out during clone, but let's verify
        current_branch = GitUtils.get_current_branch(Path(temp_dir))
        if current_branch != default_branch:
            if not GitUtils.checkout_branch(Path(temp_dir), default_branch):
                console_print(f"[yellow]⚠[/yellow] Could not checkout {default_branch}")
    else:
        console_print(f"[yellow]⚠[/yellow] Could not determine default branch (trying main, master, develop)")
        # Try common default branches
        for branch in ["main", "master", "develop"]:
            if GitUtils.branch_exists(Path(temp_dir), branch):
                if GitUtils.checkout_branch(Path(temp_dir), branch):
                    console_print(f"[dim]Checked out branch: {branch}[/dim]")
                    break

    # Return temp directory and original path
    original_path = str(current_path.absolute())
    return (temp_dir, original_path)


def cleanup_temp_directory(temp_dir: Optional[str]) -> None:
    """Clean up a temporary directory.

    Args:
        temp_dir: Path to temporary directory (can be None)
    """
    if not temp_dir:
        return

    try:
        if Path(temp_dir).exists():
            console_print(f"[dim]Cleaning up temporary directory: {temp_dir}[/dim]")
            shutil.rmtree(temp_dir)
            console_print(f"[green]✓[/green] Temporary directory removed")
    except Exception as e:
        console_print(f"[yellow]⚠[/yellow] Could not remove temporary directory: {e}")
        console_print(f"[dim]You may need to manually delete: {temp_dir}[/dim]")
