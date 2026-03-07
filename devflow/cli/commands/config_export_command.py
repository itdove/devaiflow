"""Implementation of 'daf config export' command."""

from pathlib import Path
from typing import Optional

from rich.console import Console

from devflow.cli.utils import require_outside_claude
from devflow.config.exporter import ConfigExporter
from devflow.utils.paths import get_cs_home

console = Console()


@require_outside_claude
def export_config(
    output: Optional[str] = None,
    force: bool = False,
) -> None:
    """Export configuration files for user onboarding.

    Args:
        output: Output file path (default: ~/config-export.tar.gz)
        force: Skip confirmation prompts
    """
    config_dir = get_cs_home()
    exporter = ConfigExporter(config_dir)

    output_path = Path(output) if output else None

    try:
        export_file = exporter.export_config(
            output_path=output_path,
            force=force,
        )

        console.print(f"[green]✓[/green] Configuration exported successfully")
        console.print(f"Location: {export_file}")

        # Show export size
        size_kb = export_file.stat().st_size / 1024
        if size_kb < 1024:
            console.print(f"Size: {size_kb:.2f} KB")
        else:
            size_mb = size_kb / 1024
            console.print(f"Size: {size_mb:.2f} MB")

        console.print()
        console.print("[cyan]→ Next: Share this file with your team for onboarding[/cyan]")
        console.print(f"  Recipients can import with: [dim]daf config import {export_file.name}[/dim]")

    except ValueError as e:
        console.print(f"[red]✗[/red] Export failed: {e}")
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        raise
