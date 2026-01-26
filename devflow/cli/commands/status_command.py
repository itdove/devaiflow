"""Implementation of 'daf status' command."""

from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from devflow.cli.utils import get_active_conversation, get_status_display, output_json as json_output, serialize_sessions
from devflow.config.loader import ConfigLoader
from devflow.config.models import Session
from devflow.session.manager import SessionManager

console = Console()


def show_status(output_json: bool = False) -> None:
    """Show status dashboard.

    Displays sessions grouped by configured field (default: sprint) with totals summary.

    Args:
        output_json: Output in JSON format (default: False)
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Load organization config to get grouping and totals field names
    org_config = config_loader._load_organization_config()
    grouping_field = None  # Default: no grouping
    totals_field = None    # Default: no totals
    if org_config:
        grouping_field = org_config.status_grouping_field
        totals_field = org_config.status_totals_field

    # Get all sessions
    all_sessions = session_manager.list_sessions()

    if not all_sessions:
        if output_json:
            json_output(
                success=True,
                data={
                    "sessions": [],
                    "groups": {},
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

    # Group sessions by configured field (e.g., sprint, iteration, release)
    sessions_by_group: Dict[str, List[Session]] = {}
    ungrouped_sessions = []

    # Only group if a grouping field is configured
    if grouping_field:
        for session in all_sessions:
            group_value = session.issue_metadata.get(grouping_field) if session.issue_metadata else None
            if group_value:
                if group_value not in sessions_by_group:
                    sessions_by_group[group_value] = []
                sessions_by_group[group_value].append(session)
            else:
                ungrouped_sessions.append(session)
    else:
        # No grouping configured - all sessions are ungrouped
        ungrouped_sessions = all_sessions

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

        # Build groups data (generic - works with any field)
        groups_data = {}
        for group_name, group_sessions in sessions_by_group.items():
            group_data = {
                "sessions": serialize_sessions(group_sessions)
            }

            # Only include totals if totals_field is configured
            if totals_field:
                total_value = sum(
                    s.issue_metadata.get(totals_field) or 0
                    for s in group_sessions
                    if s.issue_metadata and s.issue_metadata.get(totals_field)
                )
                in_progress_value = sum(
                    s.issue_metadata.get(totals_field) or 0
                    for s in group_sessions
                    if s.status == "in_progress" and s.issue_metadata and s.issue_metadata.get(totals_field)
                )
                group_data["total"] = total_value
                group_data["in_progress"] = in_progress_value

            groups_data[group_name] = group_data

        json_output(
            success=True,
            data={
                "active_conversation": active_data,
                "groups": groups_data,
                "ungrouped_sessions": serialize_sessions(ungrouped_sessions),
                "grouping_field": grouping_field,
                "totals_field": totals_field,
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

    # Display grouped status (by sprint, iteration, release, etc.)
    if sessions_by_group:
        for group_name, group_sessions in sorted(sessions_by_group.items(), reverse=True):
            _display_group_status(group_name, group_sessions, grouping_field, totals_field)
            console.print()

    # Display ungrouped sessions
    if ungrouped_sessions:
        if grouping_field:
            # Show "No {field} Sessions" header when grouping is configured
            grouping_field_display = grouping_field.replace('_', ' ').title()
            console.print(f"[bold]No {grouping_field_display} Sessions[/bold]\n")
        else:
            # Show "All Sessions" header when no grouping is configured
            console.print(f"[bold]All Sessions[/bold]\n")
        _display_session_table(ungrouped_sessions, totals_field)
        console.print()

    # Overall summary
    console.print(f"[bold]Summary[/bold]")
    console.print(f"  Total sessions: {total_sessions}")
    console.print(f"  In progress: {in_progress}")
    console.print(f"  Paused: {paused}")
    console.print(f"  Created: {created}")
    console.print(f"  Complete: {complete}")
    console.print(f"  Total time tracked: {hours}h {minutes}m")


def _display_group_status(group_name: str, sessions: List[Session], grouping_field: str, totals_field: Optional[str]) -> None:
    """Display status for a specific group (sprint, iteration, release, etc.).

    Args:
        group_name: Group name (e.g., "Sprint 42", "Release 1.0")
        sessions: Sessions in this group
        grouping_field: Name of the field used for grouping (e.g., "sprint", "release")
        totals_field: Name of the field to sum for totals (e.g., "points", "effort"), or None to skip totals
    """
    grouping_field_display = grouping_field.replace('_', ' ').title()
    console.print(f"[bold]{grouping_field_display}: {group_name}[/bold]")

    # Calculate and display totals only if totals_field is configured
    if totals_field:
        total_value = sum(
            s.issue_metadata.get(totals_field) or 0
            for s in sessions
            if s.issue_metadata and s.issue_metadata.get(totals_field)
        )
        in_progress_value = sum(
            s.issue_metadata.get(totals_field) or 0
            for s in sessions
            if s.status == "in_progress" and s.issue_metadata and s.issue_metadata.get(totals_field)
        )

        if total_value > 0:
            totals_field_display = totals_field.replace('_', ' ')
            console.print(f"[dim]Progress: {in_progress_value}/{total_value} {totals_field_display}[/dim]")

    console.print()
    _display_session_table(sessions, totals_field)


def _display_session_table(sessions: List[Session], totals_field: Optional[str] = None) -> None:
    """Display sessions in a table.

    Args:
        sessions: List of sessions to display
        totals_field: Name of the field to display for totals (e.g., "points", "effort"), or None to skip totals
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
            _display_session_summary(session, totals_field)
        console.print()

    # Display paused sessions
    if paused:
        display_text, color = get_status_display("paused")
        console.print(f"[{color}]{display_text}:[/{color}]")
        for session in paused:
            _display_session_summary(session, totals_field)
        console.print()

    # Display created sessions
    if created:
        display_text, color = get_status_display("created")
        console.print(f"[{color}]{display_text}:[/{color}]")
        for session in created:
            _display_session_summary(session, totals_field)
        console.print()

    # Display complete sessions (limit to last 3)
    if complete:
        display_text, color = get_status_display("complete")
        console.print(f"[{color}]{display_text}:[/{color}]")
        for session in complete[:3]:  # Show only last 3
            _display_session_summary(session, totals_field)
        if len(complete) > 3:
            console.print(f"  [dim]... and {len(complete) - 3} more[/dim]")
        console.print()


def _display_session_summary(session: Session, totals_field: Optional[str] = None) -> None:
    """Display a single session summary line.

    Args:
        session: Session to display
        totals_field: Name of the field to display for totals (e.g., "points", "effort"), or None to skip totals
    """
    issue_display = f" ({session.issue_key})" if session.issue_key else ""

    # Only display value if totals_field is configured
    value_display = ""
    if totals_field:
        value = session.issue_metadata.get(totals_field) if session.issue_metadata else None

        # Create display suffix based on field name
        if value is not None:
            if totals_field == "points":
                value_display = f" | {value} pts"
            else:
                # Generic display for other fields
                field_abbrev = totals_field.replace('_', ' ')
                value_display = f" | {value} {field_abbrev}"

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

    console.print(f"  {type_icon} {session.name}{issue_display}  {goal_display}{value_display}{time_display}")
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
