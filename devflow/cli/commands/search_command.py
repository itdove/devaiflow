"""Implementation of 'daf search' command."""

from typing import Optional

from rich.console import Console
from rich.table import Table

from devflow.cli.utils import get_status_display
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager

console = Console()


def search_sessions(
    query: Optional[str] = None,
    tag: Optional[str] = None,
    working_directory: Optional[str] = None,
) -> None:
    """Search sessions by query, tag, or working directory.

    Args:
        query: Search query (searches in name, goal, JIRA summary, notes)
        tag: Filter by tag
        working_directory: Filter by working directory
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Get all sessions
    all_sessions = session_manager.list_sessions()

    if not all_sessions:
        console.print("[dim]No sessions found[/dim]")
        return

    # Filter by working directory
    if working_directory:
        all_sessions = [s for s in all_sessions if s.working_directory == working_directory]

    # Filter by tag
    if tag:
        all_sessions = [s for s in all_sessions if tag in s.tags]

    # Filter by query (search in name, goal, JIRA summary)
    if query:
        query_lower = query.lower()
        filtered = []
        for session in all_sessions:
            # Search in name, goal, issue summary
            issue_summary = session.issue_metadata.get("summary") if session.issue_metadata else None
            if (query_lower in session.name.lower() or
                (session.goal and query_lower in session.goal.lower()) or
                (issue_summary and query_lower in issue_summary.lower())):
                filtered.append(session)
                continue

            # Search in notes
            session_dir = config_loader.get_session_dir(session.name)
            notes_file = session_dir / "notes.md"
            if notes_file.exists():
                with open(notes_file, "r") as f:
                    if query_lower in f.read().lower():
                        filtered.append(session)

        all_sessions = filtered

    if not all_sessions:
        console.print(f"[dim]No sessions found matching criteria[/dim]")
        return

    # Display results
    console.print(f"\n[bold]Found {len(all_sessions)} session(s)[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Session", style="cyan")
    table.add_column("JIRA", style="yellow")
    table.add_column("Goal", style="white")
    table.add_column("Status", style="green")
    table.add_column("Working Dir", style="dim")

    for session in all_sessions:
        issue_display = session.issue_key or "-"
        status_text, status_color = get_status_display(session.status)
        status = f"[{status_color}]{status_text}[/{status_color}]"

        # Truncate goal if too long
        goal_display = session.goal or "-"
        if len(goal_display) > 50:
            goal_display = goal_display[:47] + "..."

        table.add_row(
            f"{session.name}",
            issue_display,
            goal_display,
            status,
            session.working_directory or "-",
        )

    console.print(table)
    console.print()
    console.print(f"[dim]Use 'daf open <name>' to resume a session[/dim]")
