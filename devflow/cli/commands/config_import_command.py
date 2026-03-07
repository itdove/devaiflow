"""Implementation of 'daf config import' command."""

from pathlib import Path

from rich.console import Console

from devflow.cli.utils import require_outside_claude
from devflow.config.importer import ConfigImporter
from devflow.utils.paths import get_cs_home

console = Console()


@require_outside_claude
def import_config(
    export_file: str,
    merge: bool = True,
    replace: bool = False,
    force: bool = False,
) -> None:
    """Import configuration from export file.

    Args:
        export_file: Path to config export file
        merge: Merge with existing config (default)
        replace: Replace existing config entirely
        force: Skip confirmation prompts
    """
    # Handle mutually exclusive flags
    if replace:
        merge = False

    export_path = Path(export_file)

    if not export_path.exists():
        console.print(f"[red]✗[/red] Export file not found: {export_path}")
        return

    config_dir = get_cs_home()
    importer = ConfigImporter(config_dir)

    try:
        imported_files = importer.import_config(
            export_path=export_path,
            merge=merge,
            force=force,
        )

        console.print(f"[green]✓[/green] Configuration imported successfully")
        console.print(f"Imported {len(imported_files)} file(s)")

        if imported_files:
            console.print("\nImported files:")
            for file in imported_files:
                console.print(f"  - {file}")

        if merge:
            console.print("\n[dim]Merged with existing configuration (your workspace paths preserved)[/dim]")
        else:
            console.print("\n[dim]Replaced existing configuration[/dim]")

        # Suggest running daf upgrade to install skills
        console.print("\n[cyan]→ Next: Install skills and hierarchical config[/cyan]")
        console.print("  [bold]daf upgrade[/bold]")
        console.print("  [dim](Installs organization skills and updates field mappings)[/dim]")

    except ValueError as e:
        console.print(f"[red]✗[/red] Import failed: {e}")
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        raise
