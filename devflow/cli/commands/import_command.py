"""Implementation of 'daf import' command."""

from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.export.manager import ExportManager

console = Console()


@require_outside_claude
def import_sessions(
    export_file: str,
    merge: bool = True,
    force: bool = False,
) -> None:
    """Import sessions from an export file.

    Args:
        export_file: Path to export file
        merge: If True, merge with existing sessions
        force: Skip confirmation prompt
    """
    export_path = Path(export_file)

    if not export_path.exists():
        console.print(f"[red]✗[/red] Export file not found: {export_path}")
        return

    config_loader = ConfigLoader()
    export_manager = ExportManager(config_loader)

    # Peek at export file to show what will be imported
    try:
        peek_data = export_manager.peek_export_file(export_path)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read export file: {e}")
        return

    session_count = peek_data["session_count"]
    session_keys = peek_data["session_keys"]

    # Check for conflicts with existing sessions
    existing_sessions = config_loader.load_sessions()
    conflicting_keys = [key for key in session_keys if key in existing_sessions.sessions]

    # Display export file contents
    console.print()
    console.print("[bold]Export file contains:[/bold]")
    console.print(f"  Sessions: [cyan]{session_count}[/cyan]")
    console.print(f"  Keys: [cyan]{', '.join(session_keys)}[/cyan]")
    console.print()

    # Display conflict information
    if conflicting_keys:
        console.print(f"[yellow]Existing sessions found:[/yellow] {', '.join(conflicting_keys)}")
        if merge:
            console.print("[dim]These will be skipped (existing sessions preserved)[/dim]")
        else:
            console.print("[bold red]These will be OVERWRITTEN[/bold red]")
        console.print()

    # Confirm import operation
    if not force:
        if merge:
            if conflicting_keys:
                message = "Proceed with import? (existing sessions will be preserved)"
            else:
                message = "Proceed with import?"
        else:
            if conflicting_keys:
                message = "[yellow]WARNING:[/yellow] Proceed with import? (conflicting sessions will be OVERWRITTEN)"
            else:
                message = "Proceed with import?"

        if not Confirm.ask(message):
            console.print("[dim]Import cancelled[/dim]")
            return

    console.print("[cyan]Importing sessions...[/cyan]")

    try:
        imported_keys = export_manager.import_sessions(export_path, merge=merge)

        console.print(f"[green]✓[/green] Import completed successfully")
        console.print(f"Imported {len(imported_keys)} session(s)")

        if imported_keys:
            console.print("\nImported sessions:")
            for key in imported_keys:
                console.print(f"  - {key}")

        if merge:
            console.print("\n[dim]Merged with existing sessions (duplicates skipped)[/dim]")
        else:
            console.print("\n[dim]Conflicting sessions replaced[/dim]")

        # Remind user about branch sync on open
        if imported_keys:
            console.print(f"\n[cyan]→ Next: Open the session to sync git branch[/cyan]")
            console.print(f"  daf open {imported_keys[0]}")
            console.print(f"[dim]  (Branch will be automatically fetched from remote)[/dim]")

    except Exception as e:
        console.print(f"[red]✗[/red] Import failed: {e}")
        raise
