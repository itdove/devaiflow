"""Implementation of 'daf workspace' commands (AAP-63377)."""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkspaceDefinition

console = Console()


def list_workspaces() -> None:
    """List all configured workspaces."""
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.repos.workspaces:
        console.print("\n[yellow]⚠[/yellow] No workspaces configured")
        console.print("[dim]Add a workspace with: daf workspace add <name> <path>[/dim]")
        return

    # Create table
    table = Table(title="\nConfigured Workspaces", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="white")
    table.add_column("Default", style="green")

    for workspace in config.repos.workspaces:
        default_marker = "✓" if workspace.is_default else ""
        table.add_row(workspace.name, workspace.path, default_marker)

    console.print(table)
    console.print()


@require_outside_claude
def add_workspace(name: str, path: str, set_default: bool = False) -> None:
    """Add a workspace to the configuration.

    Args:
        name: Unique workspace name (e.g., 'primary', 'product-a', 'feat-caching').
              If not provided and path looks like a path, name will be auto-derived from path.
        path: Absolute or home-relative path to workspace directory
        set_default: If True, set this workspace as the default
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    # Handle single argument: if name provided but not path, check if name looks like a path
    if name and not path:
        # Check if name looks like a path (contains /, starts with ~, or is absolute path)
        if "/" in name or name.startswith("~") or Path(name).is_absolute():
            # Treat name as path and derive workspace name from it
            path = name
            # Derive name from path: use the last directory component
            try:
                expanded_path = Path(path).expanduser()
                # Get the directory name (last component of path)
                name = expanded_path.name
                console.print(f"[dim]Auto-derived workspace name from path: {name}[/dim]")
            except Exception:
                # If path expansion fails, fallback to prompting
                name = None
                path = None

    # Prompt for name if not provided
    if not name:
        console.print("\n[bold]Add Workspace[/bold]")
        console.print("[dim]Enter a unique name for this workspace[/dim]\n")
        console.print("[dim]Examples:[/dim]")
        console.print("[dim]  primary[/dim]")
        console.print("[dim]  product-a[/dim]")
        console.print("[dim]  feat-caching[/dim]")
        console.print()
        name = Prompt.ask("Workspace name")

    if not name or not name.strip():
        console.print("[yellow]⚠[/yellow] Name cannot be empty")
        return

    name = name.strip()

    # Check if name already exists
    if config.repos.get_workspace_by_name(name):
        console.print(f"[yellow]⚠[/yellow] Workspace already exists: {name}")
        return

    # Prompt for path if not provided
    if not path:
        console.print()
        console.print("[dim]Enter the directory path for this workspace[/dim]")
        console.print("[dim]Examples: ~/development, ~/repos/product-a, /Users/john/workspaces/feat-caching[/dim]")
        console.print()
        path = Prompt.ask("Workspace path")

    if not path or not path.strip():
        console.print("[yellow]⚠[/yellow] Path cannot be empty")
        return

    path = path.strip()

    # Expand and validate path
    try:
        expanded_path = Path(path).expanduser().resolve()
    except Exception as e:
        console.print(f"[red]✗[/red] Invalid path: {e}")
        return

    # Check if path exists
    if not expanded_path.exists():
        console.print(f"[yellow]⚠[/yellow] Path does not exist: {expanded_path}")
        create_dir = Confirm.ask("Create directory?", default=True)
        if create_dir:
            try:
                expanded_path.mkdir(parents=True, exist_ok=True)
                console.print(f"[green]✓[/green] Created directory: {expanded_path}")
            except Exception as e:
                console.print(f"[red]✗[/red] Failed to create directory: {e}")
                return
        else:
            console.print("[dim]Cancelled[/dim]")
            return

    # Check if this should be the default (only if no default exists and not explicitly set)
    if not set_default and not config.repos.get_default_workspace():
        set_default = Confirm.ask("\nSet as default workspace?", default=True)

    # Create workspace definition
    workspace = WorkspaceDefinition(
        name=name,
        path=str(expanded_path),
        is_default=set_default
    )

    # If setting as default, unset other defaults
    if set_default:
        for w in config.repos.workspaces:
            w.is_default = False

    # Add to config
    config.repos.workspaces.append(workspace)

    # Save config
    config_loader.save_config(config)

    console.print(f"\n[green]✓[/green] Added workspace: {name}")
    console.print(f"[dim]Path: {expanded_path}[/dim]")
    if set_default:
        console.print(f"[dim]Default: Yes[/dim]")


@require_outside_claude
def remove_workspace(name: str) -> None:
    """Remove a workspace from the configuration.

    Args:
        name: Workspace name to remove
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.repos.workspaces:
        console.print("[yellow]⚠[/yellow] No workspaces configured to remove")
        return

    # If name not provided, show list and prompt for selection
    if not name:
        console.print("\n[bold]Remove Workspace[/bold]\n")

        # Show configured workspaces
        console.print("[cyan]Configured workspaces:[/cyan]")
        for i, workspace in enumerate(config.repos.workspaces, 1):
            default_marker = " [default]" if workspace.is_default else ""
            console.print(f"  {i}. {workspace.name} ({workspace.path}){default_marker}")

        console.print()
        choice = Prompt.ask(
            "Enter number or name to remove (or 'cancel' to exit)",
            default="cancel"
        )

        if choice.lower() == "cancel":
            console.print("[dim]Cancelled[/dim]")
            return

        # Check if choice is a number
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(config.repos.workspaces):
                name = config.repos.workspaces[index].name
            else:
                console.print(f"[red]✗[/red] Invalid selection. Choose 1-{len(config.repos.workspaces)}")
                return
        else:
            name = choice.strip()

    # Find workspace
    workspace = config.repos.get_workspace_by_name(name)
    if not workspace:
        console.print(f"[red]✗[/red] Workspace not found: {name}")
        return

    # Confirm removal
    console.print(f"\n[yellow]Remove workspace '{name}' ({workspace.path})?[/yellow]")
    if not Confirm.ask("Continue?", default=False):
        console.print("[dim]Cancelled[/dim]")
        return

    # Check if any sessions are using this workspace
    from devflow.session.manager import SessionManager
    session_manager = SessionManager(config_loader)
    sessions_using_workspace = [
        s for s in session_manager.index.sessions.values()
        if s.workspace_name == name
    ]

    if sessions_using_workspace:
        console.print(f"\n[yellow]⚠[/yellow] Warning: {len(sessions_using_workspace)} session(s) are using this workspace:")
        for session in sessions_using_workspace[:5]:  # Show first 5
            console.print(f"  • {session.name}")
        if len(sessions_using_workspace) > 5:
            console.print(f"  ... and {len(sessions_using_workspace) - 5} more")
        console.print()
        console.print("[dim]Sessions will continue to work, but workspace selection won't show this workspace[/dim]")
        if not Confirm.ask("Continue anyway?", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

    # Remove workspace
    was_default = workspace.is_default
    config.repos.workspaces = [
        w for w in config.repos.workspaces if w.name != name
    ]

    # If removed workspace was default, set first remaining as default
    if was_default and config.repos.workspaces:
        config.repos.workspaces[0].is_default = True
        console.print(f"[dim]Set '{config.repos.workspaces[0].name}' as new default[/dim]")

    # Save config
    config_loader.save_config(config)

    console.print(f"\n[green]✓[/green] Removed workspace: {name}")


@require_outside_claude
def set_default_workspace(name: str) -> None:
    """Set a workspace as the default.

    Args:
        name: Workspace name to set as default
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.repos.workspaces:
        console.print("[yellow]⚠[/yellow] No workspaces configured")
        console.print("[dim]Add a workspace with: daf workspace add <name> <path>[/dim]")
        return

    # If name not provided, show list and prompt for selection
    if not name:
        console.print("\n[bold]Set Default Workspace[/bold]\n")

        # Show configured workspaces
        console.print("[cyan]Configured workspaces:[/cyan]")
        for i, workspace in enumerate(config.repos.workspaces, 1):
            default_marker = " [current default]" if workspace.is_default else ""
            console.print(f"  {i}. {workspace.name} ({workspace.path}){default_marker}")

        console.print()
        choice = Prompt.ask(
            "Enter number or name to set as default (or 'cancel' to exit)",
            default="cancel"
        )

        if choice.lower() == "cancel":
            console.print("[dim]Cancelled[/dim]")
            return

        # Check if choice is a number
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(config.repos.workspaces):
                name = config.repos.workspaces[index].name
            else:
                console.print(f"[red]✗[/red] Invalid selection. Choose 1-{len(config.repos.workspaces)}")
                return
        else:
            name = choice.strip()

    # Find workspace
    workspace = config.repos.get_workspace_by_name(name)
    if not workspace:
        console.print(f"[red]✗[/red] Workspace not found: {name}")
        return

    # Already default?
    if workspace.is_default:
        console.print(f"[yellow]⚠[/yellow] Workspace '{name}' is already the default")
        return

    # Unset all defaults
    for w in config.repos.workspaces:
        w.is_default = False

    # Set new default
    workspace.is_default = True

    # Save config
    config_loader.save_config(config)

    console.print(f"\n[green]✓[/green] Set '{name}' as default workspace")


@require_outside_claude
def rename_workspace(old_name: str, new_name: str) -> None:
    """Rename a workspace.

    Args:
        old_name: Current workspace name
        new_name: New workspace name
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.repos.workspaces:
        console.print("[yellow]⚠[/yellow] No workspaces configured")
        console.print("[dim]Add a workspace with: daf workspace add <path>[/dim]")
        return

    # If old_name not provided, show list and prompt for selection
    if not old_name:
        console.print("\n[bold]Rename Workspace[/bold]\n")

        # Show configured workspaces
        console.print("[cyan]Configured workspaces:[/cyan]")
        for i, workspace in enumerate(config.repos.workspaces, 1):
            default_marker = " [default]" if workspace.is_default else ""
            console.print(f"  {i}. {workspace.name} ({workspace.path}){default_marker}")

        console.print()
        choice = Prompt.ask(
            "Enter number or name to rename (or 'cancel' to exit)",
            default="cancel"
        )

        if choice.lower() == "cancel":
            console.print("[dim]Cancelled[/dim]")
            return

        # Check if choice is a number
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(config.repos.workspaces):
                old_name = config.repos.workspaces[index].name
            else:
                console.print(f"[red]✗[/red] Invalid selection. Choose 1-{len(config.repos.workspaces)}")
                return
        else:
            old_name = choice.strip()

    # Find workspace
    workspace = config.repos.get_workspace_by_name(old_name)
    if not workspace:
        console.print(f"[red]✗[/red] Workspace not found: {old_name}")
        return

    # Prompt for new name if not provided
    if not new_name:
        console.print(f"\n[bold]Renaming workspace '{old_name}'[/bold]")
        console.print(f"[dim]Current path: {workspace.path}[/dim]\n")
        new_name = Prompt.ask("New workspace name", default=old_name)

    if not new_name or not new_name.strip():
        console.print("[yellow]⚠[/yellow] New name cannot be empty")
        return

    new_name = new_name.strip()

    # Check if same as old name
    if new_name == old_name:
        console.print(f"[yellow]⚠[/yellow] New name is same as current name: {old_name}")
        return

    # Check if new name already exists
    if config.repos.get_workspace_by_name(new_name):
        console.print(f"[red]✗[/red] Workspace already exists with name: {new_name}")
        return

    # Update workspace name
    workspace.name = new_name

    # Update all sessions that use this workspace
    from devflow.session.manager import SessionManager
    session_manager = SessionManager(config_loader)
    sessions_updated = 0

    for session in session_manager.index.sessions.values():
        if session.workspace_name == old_name:
            session.workspace_name = new_name
            session_manager.save_session(session)
            sessions_updated += 1

    # Save config
    config_loader.save_config(config)

    console.print(f"\n[green]✓[/green] Renamed workspace: {old_name} → {new_name}")
    if sessions_updated > 0:
        console.print(f"[dim]Updated {sessions_updated} session(s) to use new workspace name[/dim]")
