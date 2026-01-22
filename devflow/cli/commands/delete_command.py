"""Implementation of 'daf delete' command."""

import shutil
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm, IntPrompt

from devflow.cli.utils import get_session_with_delete_all_option, get_status_display, require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager

console = Console()


@require_outside_claude
def delete_session(identifier: Optional[str] = None, delete_all: bool = False, force: bool = False, keep_metadata: bool = False, latest: bool = False) -> None:
    """Delete a session or all sessions.

    Args:
        identifier: Session group name or issue tracker key (required if not using --all or --latest)
        delete_all: Delete all sessions
        force: Skip confirmation prompt
        keep_metadata: Keep session files (notes, metadata) on disk
        latest: If True, delete the most recently active session
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Handle --all flag
    if delete_all:
        _delete_all_sessions(session_manager, config_loader, force, keep_metadata)
        return

    # Handle --latest flag
    if latest:
        sessions = session_manager.list_sessions()
        if not sessions:
            console.print("[red]No sessions found[/red]")
            return
        # Get most recent session
        most_recent = max(sessions, key=lambda s: s.last_active or s.created)
        identifier = most_recent.name
        issue_display = f" ({most_recent.issue_key})" if most_recent.issue_key else ""
        console.print(f"[dim]Using most recent session: {identifier}{issue_display}[/dim]\n")

    # Validate identifier is provided if not using --all or --latest
    if not identifier:
        console.print("[red]Error: Session identifier required (or use --all to delete all sessions)[/red]")
        console.print("[dim]Usage: daf delete <NAME-or-JIRA-KEY> or daf delete --all or daf delete --latest[/dim]")
        return

    # Get session using special delete utility (handles multi-session with "delete all" option)
    session, delete_all_in_group = get_session_with_delete_all_option(session_manager, identifier)

    if delete_all_in_group:
        # User chose to delete all sessions in the group
        sessions = session_manager.index.get_sessions(identifier)
        session_name = sessions[0].name

        if not force:
            if not Confirm.ask(f"\n[yellow]Delete ALL {len(sessions)} sessions in group '{session_name}'?[/yellow]", default=False):
                console.print("[dim]Cancelled[/dim]")
                return

        session_manager.delete_session(identifier)

        # Delete session directory by default unless --keep-metadata is specified
        session_dir = config_loader.get_session_dir(session_name)
        if session_dir.exists():
            if not keep_metadata:
                shutil.rmtree(session_dir)
                console.print(f"[green]✓[/green] Deleted session directory")
            else:
                console.print(f"[yellow]→[/yellow] Kept session files at: {session_dir}")

        console.print(f"[green]✓[/green] All sessions in group '{session_name}' deleted")
        console.print("[dim]Note: Claude Code session files are NOT deleted[/dim]")
        return

    if not session:
        return

    # Show session info
    console.print(f"\n[bold]Session to delete:[/bold]")
    issue_display = f" ({session.issue_key})" if session.issue_key else ""
    console.print(f"  Group: {session.name}{issue_display}")
    console.print(f"  Goal: {session.goal}")
    status_text, status_color = get_status_display(session.status)
    console.print(f"  Status: [{status_color}]{status_text}[/{status_color}]")
    if session.working_directory:
        console.print(f"  Working Directory: {session.working_directory}")

    # Show Claude session ID from active conversation
    active_conv = session.active_conversation
    if active_conv and active_conv.ai_agent_session_id:
        console.print(f"  Claude Session: {active_conv.ai_agent_session_id}")

    # Confirm deletion
    if not force:
        if not Confirm.ask(f"\n[yellow]Delete session '{session.name}'?[/yellow]", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

    # Delete specific session
    session_manager.delete_session(identifier)

    console.print(f"[green]✓[/green] Session '{session.name}' deleted")

    # Check if this was the last session in this group
    remaining = session_manager.index.get_sessions(identifier)
    if not remaining:
        # Delete session directory by default unless --keep-metadata is specified
        session_dir = config_loader.get_session_dir(session.name)
        if session_dir.exists():
            if not keep_metadata:
                shutil.rmtree(session_dir)
                console.print(f"[green]✓[/green] Deleted session directory")
            else:
                console.print(f"[yellow]→[/yellow] Kept session files at: {session_dir}")

    console.print("[dim]Note: Claude Code session files are NOT deleted[/dim]")


def _delete_all_sessions(session_manager: SessionManager, config_loader: ConfigLoader, force: bool, keep_metadata: bool = False) -> None:
    """Delete all sessions.

    Args:
        session_manager: SessionManager instance
        config_loader: ConfigLoader instance
        force: Skip confirmation prompt
        keep_metadata: Keep session files (notes, metadata) on disk
    """
    # Get all sessions
    all_sessions = session_manager.list_sessions()

    if not all_sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return

    # Count total sessions and session groups
    session_groups = set(s.name for s in all_sessions)
    issue_keys = set(s.issue_key for s in all_sessions if s.issue_key)
    session_count = len(all_sessions)

    # Show summary
    console.print(f"\n[bold yellow]⚠ WARNING: This will delete ALL sessions[/yellow][/bold]")
    console.print(f"\n  Total sessions: {session_count}")
    console.print(f"  Session groups: {len(session_groups)}")
    if issue_keys:
        console.print(f"  issue tracker tickets: {len(issue_keys)}")
        console.print(f"\n[dim]Groups: {', '.join(sorted(session_groups))}[/dim]")
        console.print(f"[dim]JIRA keys: {', '.join(sorted(issue_keys))}[/dim]")
    else:
        console.print(f"\n[dim]Groups: {', '.join(sorted(session_groups))}[/dim]")

    # Confirm deletion
    if not force:
        console.print()
        if not Confirm.ask(f"[red bold]Delete ALL {session_count} sessions?[/red bold]", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

    # Delete all session groups from index
    for group_name in session_groups:
        session_manager.delete_session(group_name)

    # Delete session directories by default unless --keep-metadata is specified
    sessions_root = config_loader.sessions_dir
    if sessions_root.exists():
        deleted_dirs = 0
        kept_dirs = 0
        for session_dir in sessions_root.iterdir():
            if session_dir.is_dir():
                if not keep_metadata:
                    shutil.rmtree(session_dir)
                    deleted_dirs += 1
                else:
                    kept_dirs += 1

        if deleted_dirs > 0:
            console.print(f"[green]✓[/green] Deleted {deleted_dirs} session directories")
        if kept_dirs > 0:
            console.print(f"[yellow]→[/yellow] Kept {kept_dirs} session directories at: {sessions_root}")

    console.print(f"[green]✓[/green] All {session_count} sessions deleted")
    console.print("[dim]Note: Claude Code session files (~/.claude/projects/) are NOT deleted[/dim]")
    console.print("[dim]Tip: Use 'daf init' to reinitialize if needed[/dim]")
