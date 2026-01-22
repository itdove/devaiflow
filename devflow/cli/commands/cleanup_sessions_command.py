"""Implementation of 'daf cleanup-sessions' command."""

from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from devflow.cli.utils import get_status_display, require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.capture import SessionCapture
from devflow.session.manager import SessionManager

console = Console()


@require_outside_claude
def cleanup_sessions(dry_run: bool = False, force: bool = False) -> None:
    """Find and fix orphaned sessions (sessions with missing conversation files).

    This command scans all sessions and identifies ones where:
    - Session has a ai_agent_session_id set
    - But the corresponding conversation file doesn't exist

    Args:
        dry_run: Show what would be cleaned without actually cleaning
        force: Skip confirmation prompt
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    capture = SessionCapture()

    console.print("\n[bold]Scanning for orphaned sessions...[/bold]\n")

    # Get all sessions
    all_sessions = session_manager.list_sessions()
    if not all_sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return

    # Find orphaned sessions
    orphaned: List[Tuple] = []
    total_checked = 0

    for session in all_sessions:
        total_checked += 1

        # Skip sessions without active conversation
        active_conv = session.active_conversation
        if not active_conv:
            continue

        # Skip sessions without ai_agent_session_id
        if not active_conv.ai_agent_session_id:
            continue

        # Skip sessions without project_path
        if not active_conv.project_path:
            continue

        # Check if conversation file exists
        if not capture.session_exists(active_conv.ai_agent_session_id, active_conv.project_path):
            orphaned.append((session, active_conv.ai_agent_session_id))

    console.print(f"[dim]Checked {total_checked} sessions[/dim]\n")

    if not orphaned:
        console.print("[green]✓[/green] No orphaned sessions found")
        console.print("[dim]All sessions have valid conversation files[/dim]")
        return

    # Display orphaned sessions
    console.print(f"[yellow]Found {len(orphaned)} orphaned session(s):[/yellow]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Session", style="cyan")
    table.add_column("JIRA", style="yellow")
    table.add_column("Missing UUID", style="red")
    table.add_column("Status", style="dim")

    for session, old_uuid in orphaned:
        issue_display = session.issue_key if session.issue_key else "-"
        status_text, status_color = get_status_display(session.status)
        table.add_row(
            f"{session.name}",
            issue_display,
            old_uuid[:8] + "...",
            f"[{status_color}]{status_text}[/{status_color}]",
        )

    console.print(table)
    console.print()

    if dry_run:
        console.print("[yellow]DRY RUN - No changes will be made[/yellow]\n")
        console.print("[bold]What would be cleaned:[/bold]")
        console.print("  • Clear ai_agent_session_id from orphaned sessions")
        console.print("  • Sessions will be treated as first-time launch on next 'daf open'")
        console.print("  • New UUIDs will be generated when opened")
        return

    # Confirm cleanup
    if not force:
        console.print("[bold]This will:[/bold]")
        console.print("  • Clear ai_agent_session_id from these sessions")
        console.print("  • Next 'daf open' will generate new UUIDs")
        console.print("  • No data will be lost (sessions remain in database)")
        console.print()

        if not Confirm.ask("[yellow]Proceed with cleanup?[/yellow]", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

    # Clean up orphaned sessions
    console.print("\n[cyan]Cleaning up orphaned sessions...[/cyan]\n")

    cleaned_count = 0
    for session, old_uuid in orphaned:
        try:
            # Clear the orphaned ai_agent_session_id from active conversation
            if session.active_conversation:
                session.active_conversation.ai_agent_session_id = None
            session_manager.update_session(session)

            console.print(
                f"[green]✓[/green] Cleaned: {session.name}"
            )
            cleaned_count += 1

        except Exception as e:
            console.print(
                f"[red]✗[/red] Failed to clean {session.name}: {e}"
            )

    console.print(f"\n[green]✓[/green] Cleaned {cleaned_count} orphaned session(s)")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print("  • Use 'daf open <NAME>' to launch cleaned sessions")
    console.print("  • New conversation files will be created automatically")
