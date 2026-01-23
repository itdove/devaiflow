"""Implementation of 'daf info' command."""

import os
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from devflow.cli.utils import get_status_display, output_json as json_output, serialize_session
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.config.models import Session, ConversationContext

console = Console()


def session_info(
    identifier: Optional[str], uuid_only: bool, conversation_id: Optional[int], latest: bool = False, output_json: bool = False
) -> None:
    """Show detailed session information including Claude Code UUIDs.

    IDENTIFIER can be a session name, issue key, or omitted to show the most recent session.

    Examples:
        daf info                    # Show most recent session
        daf info --latest           # Show most recent session (explicit)
        daf info PROJ-60039          # Show by issue key
        daf info my-session         # Show by session name
        daf info PROJ-60039 --uuid-only  # Get UUID for scripting
        daf info PROJ-60039 --conversation-id 1  # Show specific conversation
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Get session
    if not identifier or latest:
        # Get most recent session
        sessions = session_manager.list_sessions()
        if not sessions:
            if output_json:
                json_output(
                    success=False,
                    error={"message": "No sessions found", "code": "NO_SESSIONS"}
                )
            else:
                console.print("[yellow]No sessions found[/yellow]")
                console.print("[dim]Use 'daf new' or 'daf sync' to create sessions[/dim]")
            import sys
            sys.exit(1)
        session = max(sessions, key=lambda s: s.last_active or s.created)
    else:
        session = session_manager.get_session(identifier)

    if not session:
        if output_json:
            json_output(
                success=False,
                error={"message": f"Session '{identifier}' not found", "code": "SESSION_NOT_FOUND"}
            )
        else:
            console.print(f"[red]Session '{identifier}' not found[/red]")
        import sys
        sys.exit(1)

    # JSON output mode
    if output_json:
        _output_json_session_info(session, conversation_id, uuid_only, config_loader)
        return

    # Handle --uuid-only flag
    if uuid_only:
        _print_uuid_only(session, conversation_id)
    else:
        _display_full_session_info(session, conversation_id, config_loader)


def _output_json_session_info(
    session: Session, conversation_id: Optional[int], uuid_only: bool, config_loader: ConfigLoader
) -> None:
    """Output session information in JSON format.

    Args:
        session: Session object
        conversation_id: Optional conversation number to display (1, 2, 3...)
        uuid_only: If True, output only the UUID
        config_loader: ConfigLoader instance
    """
    if uuid_only:
        # UUID-only mode
        if conversation_id is not None:
            if not session.conversations:
                json_output(
                    success=False,
                    error={"message": "No conversations found in this session", "code": "NO_CONVERSATIONS"}
                )
                import sys
                sys.exit(1)

            # Flatten all conversations into a single list
            all_conversations = []
            for conv_list in session.conversations.values():
                all_conversations.extend(conv_list)

            if conversation_id < 1 or conversation_id > len(all_conversations):
                json_output(
                    success=False,
                    error={
                        "message": f"Invalid conversation ID. Session has {len(all_conversations)} conversation(s)",
                        "code": "INVALID_CONVERSATION_ID"
                    }
                )
                import sys
                sys.exit(1)

            conv = all_conversations[conversation_id - 1]
            json_output(success=True, data={"uuid": conv.ai_agent_session_id})
        else:
            # Get active or first conversation UUID
            if session.active_conversation:
                json_output(success=True, data={"uuid": session.active_conversation.ai_agent_session_id})
            elif session.conversations:
                first_conv = list(session.conversations.values())[0]
                json_output(success=True, data={"uuid": first_conv.ai_agent_session_id})
            else:
                json_output(
                    success=False,
                    error={"message": "No conversations found in this session", "code": "NO_CONVERSATIONS"}
                )
                import sys
                sys.exit(1)
    else:
        # Full session info mode
        session_data = serialize_session(session)

        # Add conversation file paths 
        if session.conversations:
            conversations_with_paths = []
            conv_number = 1
            for working_dir, conversation in session.conversations.items():
                # Process all sessions (active + archived) in this Conversation
                for conv in conversation.get_all_sessions():
                    conv_data = conv.model_dump(mode="json")
                    conv_data["conversation_number"] = conv_number
                    conv_data["working_directory"] = working_dir
                    conv_data["conversation_file"] = _get_conversation_file_path(conv.project_path, conv.ai_agent_session_id)
                    # Check if this is the active conversation
                    is_active = (
                        session.active_conversation and
                        session.active_conversation.ai_agent_session_id == conv.ai_agent_session_id
                    )
                    conv_data["is_active"] = is_active
                    conversations_with_paths.append(conv_data)
                    conv_number += 1

            session_data["conversations_detail"] = conversations_with_paths

        # Add time tracking summary
        time_by_user = session.time_by_user()
        total_seconds = session.total_time_seconds()
        session_data["time_tracking"] = {
            "total_seconds": int(total_seconds),
            "total_hours": int(total_seconds // 3600),
            "total_minutes": int((total_seconds % 3600) // 60),
            "by_user": {
                user: {
                    "seconds": int(seconds),
                    "hours": int(seconds // 3600),
                    "minutes": int((seconds % 3600) // 60)
                }
                for user, seconds in time_by_user.items()
            }
        }

        # Add notes info
        session_dir = config_loader.get_session_dir(session.name)
        notes_file = session_dir / "notes.md"
        if notes_file.exists():
            with open(notes_file, "r") as f:
                content = f.read()
                note_count = content.count("\n## ")
            session_data["notes"] = {
                "count": note_count,
                "file_path": str(notes_file)
            }
        else:
            session_data["notes"] = None

        # Filter to specific conversation if requested
        if conversation_id is not None:
            # Count total conversations across all repositories
            total_convs = sum(len(conv_list) for conv_list in session.conversations.values())
            if conversation_id < 1 or conversation_id > total_convs:
                json_output(
                    success=False,
                    error={
                        "message": f"Invalid conversation ID. Session has {total_convs} conversation(s)",
                        "code": "INVALID_CONVERSATION_ID"
                    }
                )
                import sys
                sys.exit(1)
            # Filter conversations_detail to just the requested one
            session_data["conversations_detail"] = [session_data["conversations_detail"][conversation_id - 1]]

        json_output(success=True, data={"session": session_data})


def _print_uuid_only(session: Session, conversation_id: Optional[int]) -> None:
    """Print only the UUID for scripting purposes.

    Args:
        session: Session object
        conversation_id: Optional conversation number (1, 2, 3...)
    """
    if conversation_id is not None:
        # Get specific conversation by index
        if not session.conversations:
            console.print("[red]No conversations found in this session[/red]", err=True)
            import sys
            sys.exit(1)

        # Flatten all conversations into a single list
        all_conversations = []
        for conversation in session.conversations.values():
            all_conversations.extend(conversation.get_all_sessions())

        if conversation_id < 1 or conversation_id > len(all_conversations):
            console.print(
                f"[red]Invalid conversation ID. Session has {len(all_conversations)} conversation(s)[/red]",
                err=True,
            )
            import sys
            sys.exit(1)

        conv = all_conversations[conversation_id - 1]
        console.print(conv.ai_agent_session_id)
    else:
        # Print active conversation UUID (or first if only one)
        if session.active_conversation:
            console.print(session.active_conversation.ai_agent_session_id)
        elif session.conversations:
            # Fallback to first conversation
            first_conversation = list(session.conversations.values())[0]
            console.print(first_conversation.active_session.ai_agent_session_id)
        else:
            console.print("[red]No conversations found in this session[/red]", err=True)


def _display_full_session_info(
    session: Session, conversation_id: Optional[int], config_loader: ConfigLoader
) -> None:
    """Display full session information.

    Args:
        session: Session object
        conversation_id: Optional conversation number to display (1, 2, 3...)
        config_loader: ConfigLoader instance
    """
    # Header
    console.print(f"\n[bold cyan]Session Information[/bold cyan]\n")

    # Basic info
    console.print(f"[bold]Name:[/bold] {session.name}")
    if session.issue_key:
        console.print(f"[bold]JIRA:[/bold] {session.issue_key}")
        summary = session.issue_metadata.get("summary") if session.issue_metadata else None
        if summary:
            console.print(f"[bold]Summary:[/bold] {summary}")
        issue_status = session.issue_metadata.get("status") if session.issue_metadata else None
        if issue_status:
            console.print(f"[bold]JIRA Status:[/bold] {issue_status}")
    status_text, status_color = get_status_display(session.status)
    console.print(f"[bold]Status:[/bold] [{status_color}]{status_text}[/{status_color}]")
    # AAP-63377: Display workspace
    if session.workspace_name:
        console.print(f"[bold]Workspace:[/bold] [cyan]{session.workspace_name}[/cyan]")
    if session.goal:
        console.print(f"[bold]Goal:[/bold] {session.goal}")
    console.print()

    # Conversations section
    if not session.conversations:
        console.print("[yellow]No conversations found in this session[/yellow]")
        import sys
        sys.exit(1)

    # Filter conversations if conversation_id specified
    if conversation_id is not None:
        # Flatten all conversations into a single list with their working_dir
        all_conversations = []
        for working_dir, conversation in session.conversations.items():
            # Process all sessions (active + archived) in this Conversation
            for conv in conversation.get_all_sessions():
                all_conversations.append((working_dir, conv))

        if conversation_id < 1 or conversation_id > len(all_conversations):
            console.print(
                f"[red]Invalid conversation ID. Session has {len(all_conversations)} conversation(s)[/red]"
            )
            import sys
            sys.exit(1)
        working_dir, conv = all_conversations[conversation_id - 1]
        _display_conversation(working_dir, conv, conversation_id, session, config_loader)
    else:
        # Display all conversations 
        # Count total conversations across all repositories
        total_convs = sum(len(conversation.get_all_sessions()) for conversation in session.conversations.values())
        console.print(f"[bold]Conversations:[/bold] {len(session.conversations)} repositories ({total_convs} total conversations)\n")

        # Display conversations grouped by repository
        conv_number = 1
        for working_dir, conversation in session.conversations.items():
            # Process all sessions (active + archived) in this Conversation
            for conv in conversation.get_all_sessions():
                _display_conversation(working_dir, conv, conv_number, session, config_loader)
                conv_number += 1
                if conv_number <= total_convs:
                    console.print()

    # Time tracking info
    console.print()
    _display_time_tracking(session)

    # Notes info
    _display_notes_info(session, config_loader)


def _display_conversation(
    working_dir: str,
    conv: ConversationContext,
    conv_number: int,
    session: Session,
    config_loader: ConfigLoader,
) -> None:
    """Display a single conversation.

    Args:
        working_dir: Working directory name
        conv: ConversationContext object
        conv_number: Conversation number (1, 2, 3...)
        session: Parent Session object
        config_loader: ConfigLoader instance
    """
    # Mark active/archived status
    # A conversation is active if it's the active conversation for this working_dir
    is_active_for_dir = (
        session.working_directory == working_dir and
        session.active_conversation and
        session.active_conversation.ai_agent_session_id == conv.ai_agent_session_id
    )
    if is_active_for_dir:
        status_marker = " [green](active)[/green]"
    elif conv.archived:
        status_marker = " [yellow](archived)[/yellow]"
    else:
        status_marker = ""

    console.print(f"[bold]#{conv_number}{status_marker}[/bold]")
    console.print(f"  [dim]Working Directory:[/dim] {working_dir}")
    console.print(f"  [dim]Project Path:[/dim] {conv.project_path}")
    console.print(f"  [dim]Branch:[/dim] {conv.branch}")
    console.print(f"  [bold]Claude Session UUID:[/bold] [cyan]{conv.ai_agent_session_id}[/cyan]")

    # Get conversation file path
    conv_file_path = _get_conversation_file_path(conv.project_path, conv.ai_agent_session_id)
    console.print(f"  [dim]Conversation File:[/dim] {conv_file_path}")

    # Display timestamps
    console.print(f"  [dim]Created:[/dim] {conv.created.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"  [dim]Last Active:[/dim] {conv.last_active.strftime('%Y-%m-%d %H:%M:%S')}")

    # Display message count if available
    if conv.message_count > 0:
        console.print(f"  [dim]Messages:[/dim] {conv.message_count}")

    # Display summary if available
    if conv.summary:
        console.print(f"  [dim]Summary:[/dim] {conv.summary}")

    # Display PRs if any
    if conv.prs:
        console.print(f"  [dim]PRs:[/dim] {', '.join(conv.prs)}")


def _get_conversation_file_path(project_path: str, ai_agent_session_id: str) -> str:
    """Get the path to the Claude Code conversation file.

    Args:
        project_path: Full path to the project
        ai_agent_session_id: Claude session UUID

    Returns:
        Path to the conversation .jsonl file
    """
    # Claude Code encodes project paths for directory names
    # Replace / with - AND replace _ with -
    encoded_path = project_path.replace("/", "-").replace("_", "-")
    if encoded_path.startswith("-"):
        encoded_path = encoded_path[1:]

    # Claude Code stores sessions in ~/.claude/projects/{encoded-path}/
    claude_dir = Path.home() / ".claude" / "projects" / encoded_path
    conv_file = claude_dir / f"{ai_agent_session_id}.jsonl"

    # Check if file exists
    if conv_file.exists():
        return str(conv_file)
    else:
        # Return path with indicator that it doesn't exist
        return f"{conv_file} [dim](not found)[/dim]"


def _display_time_tracking(session: Session) -> None:
    """Display time tracking information.

    Args:
        session: Session object
    """
    # Display time tracking state
    if session.time_tracking_state == "running":
        console.print("[bold]Time Tracking:[/bold] [green]running[/green]")
    else:
        console.print("[bold]Time Tracking:[/bold] [yellow]paused[/yellow]")

    if not session.work_sessions:
        console.print("[dim]No time tracked yet[/dim]")
        return

    # Calculate total time by user
    time_by_user = session.time_by_user()
    total_seconds = session.total_time_seconds()

    if total_seconds == 0:
        console.print("[dim]No time tracked yet[/dim]")
        return

    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)

    console.print(f"[bold]Total Time:[/bold] {hours}h {minutes}m")

    # Show per-user breakdown if multiple users
    if len(time_by_user) > 1:
        console.print("[dim]  By user:[/dim]")
        for user, user_seconds in time_by_user.items():
            user_hours = int(user_seconds // 3600)
            user_minutes = int((user_seconds % 3600) // 60)
            console.print(f"    [dim]{user}:[/dim] {user_hours}h {user_minutes}m")


def _display_notes_info(session: Session, config_loader: ConfigLoader) -> None:
    """Display notes information.

    Args:
        session: Session object
        config_loader: ConfigLoader instance
    """
    # Check if notes file exists
    session_dir = config_loader.get_session_dir(session.name)
    notes_file = session_dir / "notes.md"

    if notes_file.exists():
        # Count note entries (lines starting with "## ")
        with open(notes_file, "r") as f:
            content = f.read()
            note_count = content.count("\n## ")

        console.print(f"[bold]Notes:[/bold] {note_count} entries")
        console.print(f"  [dim]Notes File:[/dim] {notes_file}")
    else:
        console.print("[dim]No notes[/dim]")
