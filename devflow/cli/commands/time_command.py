"""Implementation of 'daf time' command."""

from typing import Optional

from rich.console import Console
from rich.table import Table

from devflow.cli.utils import get_session_with_prompt
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager

console = Console()


def show_time(identifier: Optional[str] = None, latest: bool = False) -> None:
    """Show time tracking for a session.

    Args:
        identifier: Session group name or issue key (uses most recent active if not provided)
        latest: If True, use the most recently active session
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # If no identifier or --latest flag, use most recent active session
    if not identifier or latest:
        all_sessions = session_manager.list_sessions(status="in_progress")
        if not all_sessions:
            console.print("[dim]No active sessions[/dim]")
            return

        identifier = all_sessions[0].name
        issue_display = f" ({all_sessions[0].issue_key})" if all_sessions[0].issue_key else ""
        console.print(f"[dim]Showing time for: {identifier}{issue_display}[/dim]\n")

    # Get session using common utility (handles multi-session selection)
    session = get_session_with_prompt(session_manager, identifier)
    if not session:
        return

    if not session.work_sessions:
        issue_display = f" ({session.issue_key})" if session.issue_key else ""
        console.print(f"[dim]No work sessions recorded for '{session.name}'{issue_display}[/dim]")
        return

    # Create table
    title_jira = f" ({session.issue_key})" if session.issue_key else ""
    table = Table(title=f"Work Sessions for '{session.name}'{title_jira}", show_header=True, header_style="bold")
    table.add_column("Date", style="cyan")
    table.add_column("Start", style="green")
    table.add_column("End", style="red")
    table.add_column("Duration", justify="right")
    table.add_column("User", style="yellow")

    total_seconds = 0
    for ws in session.work_sessions:
        start_str = ws.start.strftime("%H:%M")
        end_str = ws.end.strftime("%H:%M") if ws.end else "active"
        date_str = ws.start.strftime("%Y-%m-%d")
        user_str = ws.user or "unknown"

        if ws.end:
            delta = ws.end - ws.start
            seconds = delta.total_seconds()
            total_seconds += seconds
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            duration_str = f"{hours}h {minutes}m"
        else:
            duration_str = "in progress"

        table.add_row(date_str, start_str, end_str, duration_str, user_str)

    console.print(table)

    # Show per-user breakdown
    time_by_user = session.time_by_user()
    if len(time_by_user) > 1:
        console.print("\n[bold]Time by User:[/bold]")
        for user, user_seconds in sorted(time_by_user.items(), key=lambda x: x[1], reverse=True):
            hours = int(user_seconds // 3600)
            minutes = int((user_seconds % 3600) // 60)
            percentage = (user_seconds / total_seconds * 100) if total_seconds > 0 else 0
            console.print(f"  {user}: {hours}h {minutes}m ({percentage:.0f}%)")

    # Show total
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    console.print(f"\n[bold]Total: {hours}h {minutes}m[/bold]")
