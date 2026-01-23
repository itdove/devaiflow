"""Implementation of 'daf backup' command."""

from pathlib import Path
from typing import Optional

from rich.console import Console

from devflow.backup.manager import BackupManager
from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader

console = Console()


@require_outside_claude
def create_backup(output: Optional[str] = None) -> None:
    """Create a complete backup of all sessions.

    Args:
        output: Output file path
    """
    config_loader = ConfigLoader()
    backup_manager = BackupManager(config_loader)

    console.print("[cyan]Creating complete backup...[/cyan]")
    console.print()
    console.print("[yellow]Note:[/yellow] For team handoff, use [cyan]daf export[/cyan] instead:")
    console.print("  • daf export commits uncommitted changes")
    console.print("  • daf export pushes git branch to remote")
    console.print("  • daf export is designed for sharing with teammates")
    console.print()
    console.print("[dim]daf backup is for personal backups only (no git sync)[/dim]")
    console.print()

    output_path = Path(output) if output else None

    try:
        backup_file = backup_manager.create_backup(output_path)
        console.print(f"[green]✓[/green] Backup created successfully")
        console.print(f"Location: {backup_file}")

        # Show backup size
        size_mb = backup_file.stat().st_size / (1024 * 1024)
        console.print(f"Size: {size_mb:.2f} MB")

    except Exception as e:
        console.print(f"[red]✗[/red] Backup failed: {e}")
        raise
