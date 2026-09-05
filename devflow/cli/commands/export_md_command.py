"""Implementation of 'daf export-md' command."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Console

from devflow.cli.utils import output_json as json_output
from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.export.markdown import MarkdownExporter
from devflow.utils.time_parser import parse_time_expression

console = Console()


@require_outside_claude
def export_markdown(
    identifiers: List[str],
    output_dir: Optional[str] = None,
    include_activity: bool = True,
    include_statistics: bool = True,
    ai_summary: bool = False,
    combined: bool = False,
    since: Optional[str] = None,
    before: Optional[str] = None,
    output_json: bool = False,
) -> None:
    """Export one or more sessions to Markdown documentation format.

    Args:
        identifiers: List of session identifiers (names or JIRA keys) to export.
            May be empty when since or before is provided.
        output_dir: Output directory path (defaults to current directory)
        include_activity: Include session activity summary
        include_statistics: Include detailed statistics
        ai_summary: Use AI-powered summary (requires ANTHROPIC_API_KEY)
        combined: Export all sessions to a single combined file
        since: Only export sessions active at or after this time expression
        before: Only export sessions active at or before this time expression
        output_json: Output results in JSON format
    """
    if not identifiers and not since and not before:
        message = "Must specify at least one session identifier or a --since/--before filter"
        if output_json:
            json_output(success=False, error={"message": message, "code": "MISSING_EXPORT_FILTER"})
        else:
            console.print(f"[red]✗[/red] {message}")
        return

    since_dt: Optional[datetime] = None
    if since:
        since_dt = parse_time_expression(since)
        if since_dt is None:
            message = f"Could not parse time expression for --since: {since}"
            if output_json:
                json_output(
                    success=False,
                    error={"message": message, "code": "INVALID_TIME_EXPRESSION"},
                )
            else:
                console.print(f"[red]✗[/red] {message}")
                console.print("[dim]Examples: 'last week', '3 days ago', '2025-01-01'[/dim]")
            return

    before_dt: Optional[datetime] = None
    if before:
        before_dt = parse_time_expression(before)
        if before_dt is None:
            message = f"Could not parse time expression for --before: {before}"
            if output_json:
                json_output(
                    success=False,
                    error={"message": message, "code": "INVALID_TIME_EXPRESSION"},
                )
            else:
                console.print(f"[red]✗[/red] {message}")
                console.print("[dim]Examples: 'last week', '3 days ago', '2025-01-01'[/dim]")
            return

    if since_dt and before_dt and since_dt > before_dt:
        message = "The --since filter must be earlier than or equal to --before"
        if output_json:
            json_output(success=False, error={"message": message, "code": "INVALID_TIME_RANGE"})
        else:
            console.print(f"[red]✗[/red] {message}")
        return

    config_loader = ConfigLoader()
    exporter = MarkdownExporter(config_loader)

    # Determine output directory
    output_path = Path(output_dir) if output_dir else Path.cwd()

    # Show what will be exported in text mode only.
    if not output_json:
        if len(identifiers) == 1:
            console.print(f"[cyan]Exporting session: {identifiers[0]}[/cyan]")
        elif identifiers:
            console.print(f"[cyan]Exporting {len(identifiers)} session(s)[/cyan]")
        else:
            console.print("[cyan]Exporting sessions matching the date filter(s)[/cyan]")

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
            since=since_dt,
            before=before_dt,
        )

        if output_json:
            json_output(
                success=True,
                data={
                    "files": [str(file_path) for file_path in created_files],
                    "count": len(created_files),
                    "output_directory": str(output_path.absolute()),
                },
                metadata={
                    "filters": {
                        "identifiers": identifiers,
                        "since": since,
                        "before": before,
                    }
                },
            )
        else:
            console.print("\n[green]✓[/green] Export completed successfully")

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
        if output_json:
            code = "NO_SESSIONS_FOUND" if str(e) == "No sessions found to export" else "EXPORT_FAILED"
            json_output(success=False, error={"message": str(e), "code": code})
        else:
            console.print(f"[red]✗[/red] Export failed: {e}")
    except Exception as e:
        if output_json:
            json_output(success=False, error={"message": str(e), "code": "UNEXPECTED_ERROR"})
        else:
            console.print(f"[red]✗[/red] Unexpected error: {e}")
            raise
