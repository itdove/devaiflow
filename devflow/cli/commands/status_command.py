"""Implementation of 'daf status' command."""

from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from devflow.cli.utils import get_active_conversation, get_status_display, output_json as json_output, serialize_sessions
from devflow.config.loader import ConfigLoader
from devflow.config.models import Session
from devflow.session.manager import SessionManager

console = Console()


def show_status(output_json: bool = False) -> None:
    """Show sprint status dashboard.

    Displays sessions grouped by status with sprint progress summary.

    Args:
        output_json: Output in JSON format (default: False)
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Get all sessions
    all_sessions = session_manager.list_sessions()

    if not all_sessions:
        if output_json:
            json_output(
                success=True,
                data={
                    "sessions": [],
                    "sprints": {},
                    "summary": {
                        "total_sessions": 0,
                        "in_progress": 0,
                        "paused": 0,
                        "created": 0,
                        "complete": 0,
                        "total_time_seconds": 0
                    }
                }
            )
        else:
            console.print("[dim]No sessions found[/dim]")
            console.print("[dim]Use 'daf new' to create a session or 'daf sync' to import issue tracker tickets[/dim]")
        return

    # Group sessions by sprint (if JIRA integrated)
    sessions_by_sprint: Dict[str, List[Session]] = {}
    no_sprint_sessions = []

    for session in all_sessions:
        sprint = session.issue_metadata.get("sprint") if session.issue_metadata else None
        if sprint:
            if sprint not in sessions_by_sprint:
                sessions_by_sprint[sprint] = []
            sessions_by_sprint[sprint].append(session)
        else:
            no_sprint_sessions.append(session)

    # Calculate overall summary
    total_sessions = len(all_sessions)
    in_progress = len([s for s in all_sessions if s.status == "in_progress"])
    paused = len([s for s in all_sessions if s.status == "paused"])
    created = len([s for s in all_sessions if s.status == "created"])
    complete = len([s for s in all_sessions if s.status == "complete"])

    total_time = sum(
        sum((ws.end - ws.start).total_seconds() for ws in s.work_sessions if ws.end)
        for s in all_sessions
    )
    hours = int(total_time // 3600)
    minutes = int((total_time % 3600) // 60)

    # JSON output mode
    if output_json:
        # Check for active conversation
        active_result = get_active_conversation(session_manager)
        active_data = None
        if active_result:
            active_session, active_conversation, active_working_dir = active_result
            active_data = {
                "session_name": active_session.name,
                "issue_key": active_session.issue_key,
                "working_directory": active_working_dir,
                "goal": active_session.goal,
                "ai_agent_session_id": active_conversation.ai_agent_session_id
            }

        # Build sprint data
        sprints_data = {}
        for sprint_name, sprint_sessions in sessions_by_sprint.items():
            total_points = sum(
                s.issue_metadata.get("points") or 0
                for s in sprint_sessions
                if s.issue_metadata and s.issue_metadata.get("points")
            )
            in_progress_points = sum(
                s.issue_metadata.get("points") or 0
                for s in sprint_sessions
                if s.status == "in_progress" and s.issue_metadata and s.issue_metadata.get("points")
            )
            sprints_data[sprint_name] = {
                "sessions": serialize_sessions(sprint_sessions),
                "total_points": total_points,
                "in_progress_points": in_progress_points
            }

        json_output(
            success=True,
            data={
                "active_conversation": active_data,
                "sprints": sprints_data,
                "no_sprint_sessions": serialize_sessions(no_sprint_sessions),
                "summary": {
                    "total_sessions": total_sessions,
                    "in_progress": in_progress,
                    "paused": paused,
                    "created": created,
                    "complete": complete,
                    "total_time_seconds": int(total_time),
                    "total_time_hours": hours,
                    "total_time_minutes": minutes
                }
            }
        )
        return

    # Rich formatted output
    # Check for active conversation first
    active_result = get_active_conversation(session_manager)
    if active_result:
        _display_active_conversation_panel(active_result)
        console.print()  # Add spacing

    # Display sprint-based status
    if sessions_by_sprint:
        for sprint_name, sprint_sessions in sorted(sessions_by_sprint.items(), reverse=True):
            _display_sprint_status(sprint_name, sprint_sessions)
            console.print()

    # Display non-sprint sessions
    if no_sprint_sessions:
        console.print("[bold]Non-Sprint Sessions[/bold]\n")
        _display_session_table(no_sprint_sessions)
        console.print()

    # Overall summary
    console.print(f"[bold]Summary[/bold]")
    console.print(f"  Total sessions: {total_sessions}")
    console.print(f"  In progress: {in_progress}")
    console.print(f"  Paused: {paused}")
    console.print(f"  Created: {created}")
    console.print(f"  Complete: {complete}")
    console.print(f"  Total time tracked: {hours}h {minutes}m")


def _display_sprint_status(sprint_name: str, sessions: List[Session]) -> None:
    """Display status for a specific sprint.

    Args:
        sprint_name: Sprint name
        sessions: Sessions in this sprint
    """
    # Calculate story points (if available)
    total_points = sum(
        s.issue_metadata.get("points") or 0
        for s in sessions
        if s.issue_metadata and s.issue_metadata.get("points")
    )
    in_progress_points = sum(
        s.issue_metadata.get("points") or 0
        for s in sessions
        if s.status == "in_progress" and s.issue_metadata and s.issue_metadata.get("points")
    )

    console.print(f"[bold]Sprint: {sprint_name}[/bold]")
    if total_points > 0:
        console.print(f"[dim]Progress: {in_progress_points}/{total_points} points[/dim]")
    console.print()

    _display_session_table(sessions)


def _display_session_table(sessions: List[Session]) -> None:
    """Display sessions in a table.

    Args:
        sessions: List of sessions to display
    """
    # Group by status
    in_progress = [s for s in sessions if s.status == "in_progress"]
    paused = [s for s in sessions if s.status == "paused"]
    created = [s for s in sessions if s.status == "created"]
    complete = [s for s in sessions if s.status == "complete"]

    # Display in progress sessions
    if in_progress:
        display_text, color = get_status_display("in_progress")
        console.print(f"[{color}]{display_text}:[/{color}]")
        for session in in_progress:
            _display_session_summary(session)
        console.print()

    # Display paused sessions
    if paused:
        display_text, color = get_status_display("paused")
        console.print(f"[{color}]{display_text}:[/{color}]")
        for session in paused:
            _display_session_summary(session)
        console.print()

    # Display created sessions
    if created:
        display_text, color = get_status_display("created")
        console.print(f"[{color}]{display_text}:[/{color}]")
        for session in created:
            _display_session_summary(session)
        console.print()

    # Display complete sessions (limit to last 3)
    if complete:
        display_text, color = get_status_display("complete")
        console.print(f"[{color}]{display_text}:[/{color}]")
        for session in complete[:3]:  # Show only last 3
            _display_session_summary(session)
        if len(complete) > 3:
            console.print(f"  [dim]... and {len(complete) - 3} more[/dim]")
        console.print()


def _display_session_summary(session: Session) -> None:
    """Display a single session summary line.

    Args:
        session: Session to display
    """
    issue_display = f" ({session.issue_key})" if session.issue_key else ""
    points = session.issue_metadata.get("points") if session.issue_metadata else None
    points_display = f" | {points} pts" if points else ""

    # Calculate time spent
    total_seconds = sum(
        (ws.end - ws.start).total_seconds() for ws in session.work_sessions if ws.end
    )
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    time_display = f" | {hours}h {minutes}m" if total_seconds > 0 else ""

    # Truncate goal
    goal_display = session.goal or ""
    if len(goal_display) > 40:
        goal_display = goal_display[:37] + "..."

    issue_type = session.issue_metadata.get("type") if session.issue_metadata else None
    type_icon = "🐛" if issue_type == "Bug" else "📋"

    console.print(f"  {type_icon} {session.name}{issue_display}  {goal_display}{points_display}{time_display}")
    console.print(f"     [dim]└─ {session.working_directory or 'No directory'} | Last: {session.last_active.strftime('%Y-%m-%d %H:%M')}[/dim]")


def _display_active_conversation_panel(active_result) -> None:
    """Display currently active conversation in a prominent panel.

    Args:
        active_result: Tuple of (Session, ConversationContext, working_directory)
    """
    from datetime import datetime

    session, conversation, working_dir = active_result

    # Calculate current work session time
    current_work_time = "0h 0m"
    if session.time_tracking_state == "running" and session.work_sessions:
        last_work_session = session.work_sessions[-1]
        if last_work_session.end is None:
            seconds = (datetime.now() - last_work_session.start).total_seconds()
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            current_work_time = f"{hours}h {minutes}m"

    # Build panel content
    lines = [
        f"[bold]Session:[/bold] {session.name}",
        f"[bold]Conversation:[/bold] {working_dir}",
        f"[bold]Goal:[/bold] {session.goal or 'N/A'}",
        f"[bold]Time (this session):[/bold] {current_work_time}",
    ]

    if session.issue_key:
        lines.insert(1, f"[bold]JIRA:[/bold] {session.issue_key}")

    panel_content = "\n".join(lines)
    panel = Panel(
        panel_content,
        title="▶ Currently Active",
        border_style="green",
        padding=(0, 1),
    )

    console.print(panel)
