"""Implementation of 'daf restore' command."""

from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from devflow.backup.manager import BackupManager
from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader

console = Console()


@require_outside_claude
def restore_backup(backup_file: str, merge: bool = False, force: bool = False) -> None:
    """Restore from a complete backup.

    Args:
        backup_file: Path to backup file
        merge: If True, merge with existing sessions
        force: Skip confirmation prompt
    """
    backup_path = Path(backup_file)

    if not backup_path.exists():
        console.print(f"[red]✗[/red] Backup file not found: {backup_path}")
        return

    # Confirm restore operation
    if not force:
        if merge:
            message = "Restore and merge with existing sessions?"
        else:
            message = "[yellow]WARNING:[/yellow] This will replace ALL existing sessions. Continue?"

        if not Confirm.ask(message):
            console.print("[dim]Restore cancelled[/dim]")
            return

    config_loader = ConfigLoader()
    backup_manager = BackupManager(config_loader)

    console.print("[cyan]Restoring backup...[/cyan]")

    try:
        backup_manager.restore_backup(backup_path, merge=merge)
        console.print(f"[green]✓[/green] Backup restored successfully")

        if merge:
            console.print("[dim]Merged with existing sessions[/dim]")
        else:
            console.print("[dim]All sessions replaced[/dim]")

    except Exception as e:
        console.print(f"[red]✗[/red] Restore failed: {e}")
        raise
