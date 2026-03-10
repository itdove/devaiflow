"""Temporary directory utilities for issue tracker ticket creation sessions.

This module provides shared functions for cloning repositories to temporary
directories for clean analysis during ticket creation sessions.

Extracted from jira_new_command.py to be reused by jira_open_command.py.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from rich.prompt import Confirm, Prompt

from devflow.cli.utils import console_print, is_json_mode
from devflow.git.utils import GitUtils
from devflow.utils.paths import is_mock_mode


def should_clone_to_temp(path: Path) -> bool:
    """Check if the current directory is a git repository.

    Only prompt for cloning if we're in a git repository.

    Args:
        path: Directory path to check

    Returns:
        True if we should prompt to clone, False otherwise
    """
    return GitUtils.is_git_repository(path)


def _prompt_for_branch_selection(repo_path: Path) -> Optional[str]:
    """Prompt user to select a branch after cloning to temp directory.

    Args:
        repo_path: Path to the cloned repository

    Returns:
        Selected branch name, or None if selection should be skipped or failed
    """
    # Skip prompting in non-interactive modes (mock or JSON output)
    if is_mock_mode() or is_json_mode():
        return None

    # Get list of remotes
    remotes = GitUtils.get_remote_names(repo_path)
    if not remotes:
        console_print("[yellow]⚠[/yellow] No remotes found in repository")
        return None

    # Determine which remote to use (prefer upstream over origin)
    remote = "upstream" if "upstream" in remotes else "origin"
    if remote not in remotes:
        console_print(f"[yellow]⚠[/yellow] Remote '{remote}' not found")
        return None

    # List available branches from the remote
    console_print(f"[dim]Fetching branches from {remote}...[/dim]")
    branches = GitUtils.list_remote_branches(repo_path, remote)
    if not branches:
        console_print(f"[yellow]⚠[/yellow] No branches found on remote '{remote}'")
        return None

    # Determine default branch with priority: upstream/main > upstream/master > origin/main > origin/master
    default_branch = None
    default_candidates = ["main", "master"]
    for candidate in default_candidates:
        if candidate in branches:
            default_branch = candidate
            break

    if not default_branch and branches:
        # If no main/master, use first available branch
        default_branch = branches[0]

    # Build branch selection menu
    console_print("\nSelect branch to checkout:")
    for idx, branch in enumerate(branches, start=1):
        if branch == default_branch:
            console_print(f"  {idx}. {branch} [cyan](default - from {remote})[/cyan]")
        else:
            console_print(f"  {idx}. {branch}")

    # Prompt user for selection with validation loop
    try:
        while True:
            choice = Prompt.ask(
                "\nEnter selection",
                default="1" if default_branch else None,
                show_default=True
            )

            # Allow cancel
            if choice.lower() in ['cancel', 'q']:
                console_print(f"[dim]Using default branch: {default_branch}[/dim]")
                return default_branch

            # Parse selection (can be number or branch name)
            selected_branch = None

            # Try to parse as number first
            try:
                selection_num = int(choice)
                if 1 <= selection_num <= len(branches):
                    selected_branch = branches[selection_num - 1]
                else:
                    console_print(f"[red]✗[/red] Invalid selection: {choice}")
                    console_print("[dim]Please try again or type 'cancel' to use default[/dim]")
                    continue
            except ValueError:
                # Not a number, treat as branch name
                if choice in branches:
                    selected_branch = choice
                else:
                    console_print(f"[red]✗[/red] Branch '{choice}' not found in available branches")
                    console_print("[dim]Please try again or type 'cancel' to use default[/dim]")
                    continue

            # Valid selection made
            if selected_branch:
                console_print(f"[green]✓[/green] Selected branch: {selected_branch}")
                return selected_branch

    except (KeyboardInterrupt, EOFError):
        console_print("\n[dim]Branch selection cancelled, using default[/dim]")
        return default_branch


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

    console_print(f"[green]✓[/green] Repository cloned")

    # Prompt user to select branch (unless in non-interactive mode)
    selected_branch = _prompt_for_branch_selection(Path(temp_dir))

    if selected_branch:
        # Checkout the selected branch
        console_print(f"[dim]Checking out branch: {selected_branch}...[/dim]")
        if GitUtils.checkout_branch(Path(temp_dir), selected_branch):
            console_print(f"[green]✓[/green] Checked out branch: {selected_branch}")
        else:
            console_print(f"[yellow]⚠[/yellow] Could not checkout {selected_branch}")
            console_print("[dim]Falling back to auto-detection[/dim]")
            selected_branch = None

    # If no branch was selected or checkout failed, fall back to auto-detection
    if not selected_branch:
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
