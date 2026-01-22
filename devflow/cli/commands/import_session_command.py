"""Implementation of 'daf import-session' command."""

import os
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt

from devflow.cli.utils import get_status_display, require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.discovery import SessionDiscovery
from devflow.session.manager import SessionManager

console = Console()


@require_outside_claude
def import_session(uuid: str, issue_key: str = None, goal: str = None) -> None:
    """Import an existing Claude Code session into daf tool.

    Args:
        uuid: Claude session UUID to import
        issue_key: issue tracker key (will prompt if not provided)
        goal: Session goal (will prompt if not provided)
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    discovery = SessionDiscovery()

    # Discover all sessions
    discovered = discovery.discover_sessions()

    # Find the session by UUID
    session_to_import = None
    for s in discovered:
        if s.uuid == uuid:
            session_to_import = s
            break

    if not session_to_import:
        console.print(f"[red]Session {uuid} not found[/red]")
        console.print("[dim]Use 'daf discover' to see available sessions[/dim]")
        return

    # Check if already managed
    existing = session_manager.list_sessions()
    for s in existing:
        # Check conversations for matching Claude session ID 
        is_managed = any(
            conv_ctx.ai_agent_session_id == uuid
            for conversation in s.conversations.values()
            for conv_ctx in conversation.get_all_sessions()
        )
        if is_managed:
            console.print(f"[yellow]Session {uuid} is already managed by daf tool[/yellow]")
            console.print(f"  JIRA: {s.issue_key}")
            console.print(f"  Goal: {s.goal}")
            return

    # Display session info
    console.print("\n[bold]Session to import:[/bold]\n")
    console.print(f"  UUID: [cyan]{session_to_import.uuid}[/cyan]")
    console.print(f"  Working Directory: {session_to_import.working_directory or 'unknown'}")
    console.print(f"  Project Path: {session_to_import.project_path or 'unknown'}")
    console.print(f"  Messages: {session_to_import.message_count}")
    console.print(f"  Created: {session_to_import.created.strftime('%Y-%m-%d %H:%M')}")
    console.print(f"  Last Active: {session_to_import.last_active.strftime('%Y-%m-%d %H:%M')}")

    if session_to_import.first_message:
        first_msg = session_to_import.first_message
        if len(first_msg) > 100:
            first_msg = first_msg[:100] + "..."
        console.print(f"  First Message: [dim]{first_msg}[/dim]")

    console.print()

    # Prompt for issue key if not provided
    if not issue_key:
        issue_key= Prompt.ask(
            "[bold]issue tracker key[/bold]",
            default="",
        )
        if not issue_key:
            console.print("[red]issue key is required[/red]")
            return

    # Prompt for goal if not provided
    if not goal:
        # Use first message as default goal
        default_goal = session_to_import.first_message or ""
        if len(default_goal) > 80:
            default_goal = default_goal[:80] + "..."

        goal = Prompt.ask(
            "[bold]Session goal/description[/bold]",
            default=default_goal,
        )
        if not goal:
            console.print("[red]Goal is required[/red]")
            return

    # Determine project path and working directory
    project_path = session_to_import.project_path
    working_directory = session_to_import.working_directory

    # If project path is not absolute or doesn't exist, prompt
    if not project_path or not Path(project_path).exists():
        current_dir = os.getcwd()
        use_current = Confirm.ask(
            f"Use current directory?\n  [dim]{current_dir}[/dim]",
            default=True,
        )

        if use_current:
            project_path = current_dir
            working_directory = Path(current_dir).name
        else:
            project_path = Prompt.ask("Project path")
            if not project_path or not project_path.strip():
                console.print("[red]✗[/red] Project path cannot be empty")
                return
            project_path = project_path.strip()
            working_directory = Path(project_path).name

    # Check for existing sessions with same issue key
    existing_sessions = session_manager.index.get_sessions(issue_key)
    if existing_sessions:
        console.print(f"\n[yellow]Found {len(existing_sessions)} existing session(s) for {issue_key}:[/yellow]\n")
        for s in existing_sessions:
            status_text, status_color = get_status_display(s.status)
            console.print(f"  [{status_color}]{s.working_directory}[/{status_color}] - {status_text}")
            console.print(f"      Goal: {s.goal}")
        console.print()

        if not Confirm.ask(f"Create new session for {issue_key}?", default=True):
            console.print("[dim]Import cancelled[/dim]")
            return

    # Create the session
    session = session_manager.create_session(
        name=issue_key,
        issue_key=issue_key,
        goal=goal,
        working_directory=working_directory,
        project_path=project_path,
        ai_agent_session_id=uuid,
    )

    # Update session metadata from discovered session
    # For new multi-conversation architecture, update the conversation's message_count
    if session.active_conversation:
        session.active_conversation.message_count = session_to_import.message_count
    session.created = session_to_import.created
    session.last_active = session_to_import.last_active
    session.status = "paused"  # Imported sessions are paused (not actively running)

    # Temporarily save last_active since update_session overwrites it
    preserved_last_active = session_to_import.last_active
    session_manager.update_session(session)
    # Restore the preserved last_active
    session.last_active = preserved_last_active
    # Update the session in the index with the restored value
    if session.name in session_manager.index.sessions:
        session_manager.index.sessions[session.name] = session
    # Mark as modified again so the restored value is saved
    session_manager._mark_modified(session)
    session_manager._save_index()
    session_manager._save_session_metadata(session)

    # Success message
    console.print(f"\n[green]✓[/green] Imported session for {issue_key}")
    console.print()
    console.print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    console.print(f"📋 Session: {issue_key}")
    console.print(f"🎯 Goal: {goal}")
    console.print(f"📁 Working Directory: {working_directory}")
    console.print(f"📂 Path: {project_path}")
    console.print(f"💬 Messages: {session.active_conversation.message_count if session.active_conversation else 0}")
    console.print(f"🆔 Claude Session ID: {uuid}")
    console.print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    console.print()
    console.print(f"[bold cyan]Resume with:[/bold cyan] daf open {issue_key}")
