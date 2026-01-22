"""Implementation of 'daf active' command."""

from datetime import datetime
from rich.console import Console
from rich.panel import Panel

from devflow.cli.utils import get_active_conversation, output_json as json_output, serialize_session
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager

console = Console()


def show_active(output_json: bool = False) -> None:
    """Show currently active AI agent conversation.

    Detects the active conversation via AI_AGENT_SESSION_ID environment variable
    and displays session and conversation details.

    Args:
        output_json: Output in JSON format (default: False)
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    session_manager = SessionManager(config_loader)

    # Get active conversation
    active_result = get_active_conversation(session_manager)

    if active_result is None:
        if output_json:
            # Get recent conversations for JSON output
            recent_data = _get_recent_conversations_data(session_manager)
            json_output(
                success=True,
                data={
                    "active_conversation": None,
                    "recent_conversations": recent_data
                }
            )
        else:
            # No active conversation - show recent conversations
            console.print("\n[yellow]No active conversation[/yellow]\n")
            _show_recent_conversations(session_manager)
        return

    session, conversation, working_dir = active_result

    # Calculate current work session time
    current_work_seconds = 0
    if session.time_tracking_state == "running" and session.work_sessions:
        last_work_session = session.work_sessions[-1]
        if last_work_session.end is None:
            current_work_seconds = (datetime.now() - last_work_session.start).total_seconds()

    hours = int(current_work_seconds // 3600)
    minutes = int((current_work_seconds % 3600) // 60)
    current_work_time = f"{hours}h {minutes}m"

    # Format project path display
    workspace = config.repos.workspace if config else None
    project_path = conversation.get_project_path(workspace)

    # JSON output mode
    if output_json:
        other_conversations = []
        if len(session.conversations) > 1:
            for wd, conv in session.conversations.items():
                if wd != working_dir:
                    # Access active_session
                    active = conv.active_session
                    other_conversations.append({
                        "working_directory": wd,
                        "branch": active.branch,
                        "project_path": active.project_path,
                        "ai_agent_session_id": active.ai_agent_session_id
                    })

        json_output(
            success=True,
            data={
                "active_conversation": {
                    "session_name": session.name,
                    "issue_key": session.issue_key,
                    "working_directory": working_dir,
                    "project_path": project_path,
                    "goal": session.goal,
                    "branch": conversation.branch,
                    "status": session.status,
                    "ai_agent_session_id": conversation.ai_agent_session_id,
                    "current_work_time_seconds": int(current_work_seconds),
                    "current_work_time_hours": hours,
                    "current_work_time_minutes": minutes,
                    "time_tracking_state": session.time_tracking_state,
                    "other_conversations": other_conversations
                }
            }
        )
        return

    # Rich formatted output
    # Build the active conversation display
    lines = [
        f"[bold]DAF Session:[/bold] {session.name}",
        f"[bold]Conversation:[/bold] ({working_dir})",
        f"[bold]Project:[/bold] {project_path}",
        f"[bold]Goal:[/bold] {session.goal or 'N/A'}",
        f"[bold]Branch:[/bold] {conversation.branch}",
        f"[bold]Time (this work session):[/bold] {current_work_time}",
        f"[bold]Status:[/bold] {session.status}",
    ]

    # Add issue key if present
    if session.issue_key:
        lines.insert(1, f"[bold]JIRA:[/bold] {session.issue_key}")

    # Show other conversations if this is a multi-project session
    if len(session.conversations) > 1:
        other_convos = [
            (wd, conv) for wd, conv in session.conversations.items()
            if wd != working_dir
        ]
        lines.append("")
        lines.append(f"[bold]Other conversations in this session:[/bold]")
        for other_wd, other_conv in other_convos:
            lines.append(f"  • {other_wd} (branch: {other_conv.branch})")

    panel_content = "\n".join(lines)
    panel = Panel(
        panel_content,
        title="▶ Currently Active Conversation",
        border_style="green",
        padding=(1, 2),
    )

    console.print()
    console.print(panel)
    console.print()
    console.print("[dim]To pause: Exit Claude Code[/dim]")
    console.print(f"[dim]To switch: daf open {session.name} (and select different conversation)[/dim]")
    console.print()


def _get_recent_conversations_data(session_manager: SessionManager) -> list:
    """Get recent conversations data for JSON output.

    Args:
        session_manager: SessionManager instance

    Returns:
        List of recent conversation dictionaries
    """
    all_sessions = session_manager.list_sessions()
    recent_conversations = []
    for session in all_sessions[:5]:
        for working_dir, conversation in session.conversations.items():
            recent_conversations.append((session, conversation, working_dir))

    recent_conversations.sort(key=lambda x: x[1].active_session.last_active, reverse=True)

    result = []
    for session, conversation, working_dir in recent_conversations[:5]:
        time_diff = datetime.now() - conversation.active_session.last_active
        seconds_ago = int(time_diff.total_seconds())

        result.append({
            "session_name": session.name,
            "issue_key": session.issue_key,
            "working_directory": working_dir,
            "branch": conversation.active_session.branch,
            "last_active": conversation.active_session.last_active.isoformat(),
            "seconds_ago": seconds_ago
        })

    return result


def _show_recent_conversations(session_manager: SessionManager) -> None:
    """Show recent conversations when no active conversation.

    Args:
        session_manager: SessionManager instance
    """
    # Get all sessions sorted by last_active
    all_sessions = session_manager.list_sessions()

    # Get recent conversations from last 3 sessions
    recent_conversations = []
    for session in all_sessions[:5]:  # Check last 5 sessions
        for working_dir, conversation in session.conversations.items():
            recent_conversations.append((session, conversation, working_dir))

    # Sort by conversation.active_session.last_active
    recent_conversations.sort(key=lambda x: x[1].active_session.last_active, reverse=True)

    if not recent_conversations:
        console.print("[dim]No recent conversations[/dim]")
        console.print("[dim]Use 'daf new' or 'daf open' to start a session[/dim]")
        return

    console.print("[bold]Recent conversations:[/bold]\n")

    # Show up to 5 recent conversations
    for session, conversation, working_dir in recent_conversations[:5]:
        # Calculate time since last active
        time_diff = datetime.now() - conversation.active_session.last_active
        hours_ago = int(time_diff.total_seconds() // 3600)
        minutes_ago = int((time_diff.total_seconds() % 3600) // 60)

        if hours_ago > 0:
            time_ago = f"{hours_ago}h ago"
        elif minutes_ago > 0:
            time_ago = f"{minutes_ago}m ago"
        else:
            time_ago = "just now"

        issue_display = f" ({session.issue_key})" if session.issue_key else ""
        console.print(
            f"  {session.name}{issue_display} ({working_dir}) - paused {time_ago}"
        )

    console.print()
    console.print("[dim]To resume: daf open <name>[/dim]")
