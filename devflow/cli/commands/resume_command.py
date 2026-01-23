"""Implementation of 'daf resume' command."""

from datetime import datetime
from typing import Optional

from rich.console import Console

from devflow.cli.utils import get_session_with_prompt
from devflow.config.loader import ConfigLoader
from devflow.config.models import WorkSession
from devflow.session.manager import SessionManager

console = Console()


def resume_time_tracking(identifier: Optional[str] = None, latest: bool = False) -> None:
    """Resume time tracking for a session.

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
        console.print(f"[dim]Resuming time for: {identifier}{issue_display}[/dim]\n")

    # Get session using common utility (handles multi-session selection)
    session = get_session_with_prompt(session_manager, identifier)
    if not session:
        return

    # Check if time tracking is already running
    if session.time_tracking_state == "running":
        issue_display = f" ({session.issue_key})" if session.issue_key else ""
        console.print(f"[yellow]Time tracking is already running for '{session.name}'{issue_display}[/yellow]")
        return

    # Start a new work session
    session.work_sessions.append(WorkSession(start=datetime.now()))
    session.time_tracking_state = "running"
    session_manager.update_session(session)

    issue_display = f" ({session.issue_key})" if session.issue_key else ""
    console.print(f"[green]✓[/green] Time tracking resumed for '{session.name}'{issue_display}")
