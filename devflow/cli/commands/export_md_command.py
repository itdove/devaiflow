"""Implementation of 'daf export-md' command."""

from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.table import Table

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.export.markdown import MarkdownExporter

console = Console()


@require_outside_claude
def export_markdown(
    identifiers: List[str],
    output_dir: Optional[str] = None,
    include_activity: bool = True,
    include_statistics: bool = True,
    ai_summary: bool = False,
    combined: bool = False,
) -> None:
    """Export one or more sessions to Markdown documentation format.

    Args:
        identifiers: List of session identifiers (names or JIRA keys) to export
        output_dir: Output directory path (defaults to current directory)
        include_activity: Include session activity summary
        include_statistics: Include detailed statistics
        ai_summary: Use AI-powered summary (requires ANTHROPIC_API_KEY)
        combined: Export all sessions to a single combined file
    """
    if not identifiers:
        console.print("[red]✗[/red] Must specify at least one session identifier")
        return

    config_loader = ConfigLoader()
    exporter = MarkdownExporter(config_loader)

    # Determine output directory
    output_path = Path(output_dir) if output_dir else Path.cwd()

    # Show what will be exported
    if len(identifiers) == 1:
        console.print(f"[cyan]Exporting session: {identifiers[0]}[/cyan]")
    else:
        console.print(f"[cyan]Exporting {len(identifiers)} session(s)[/cyan]")

    if combined:
        console.print("[dim]Exporting to single combined file[/dim]")
    else:
        console.print("[dim]Exporting each session to separate file[/dim]")

    if ai_summary:
        console.print("[dim]Using AI-powered summary (requires ANTHROPIC_API_KEY)[/dim]")

    try:
        created_files = exporter.export_sessions_to_markdown(
            identifiers=identifiers,
            output_dir=output_path,
            include_activity=include_activity,
            include_statistics=include_statistics,
            ai_summary=ai_summary,
            combined=combined,
        )

        console.print(f"\n[green]✓[/green] Export completed successfully")

        # Show created files
        if len(created_files) == 1:
            console.print(f"Created file: {created_files[0]}")
        else:
            console.print(f"\nCreated {len(created_files)} file(s):")
            for file_path in created_files:
                console.print(f"  - {file_path.name}")

        console.print(f"\nOutput directory: {output_path.absolute()}")

        # Calculate total size
        total_size = sum(f.stat().st_size for f in created_files)
        size_kb = total_size / 1024
        if size_kb < 1024:
            console.print(f"Total size: {size_kb:.2f} KB")
        else:
            size_mb = size_kb / 1024
            console.print(f"Total size: {size_mb:.2f} MB")

    except ValueError as e:
        console.print(f"[red]✗[/red] Export failed: {e}")
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        raise
