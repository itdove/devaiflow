"""Implementation of 'daf delete' command."""

import shutil
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm

from devflow.agent import get_agent_display_name
from devflow.agent.factory import resolve_agent_backend
from devflow.cli.utils import (
    console_print,
    get_session_with_delete_all_option,
    get_status_display,
    is_json_mode,
    output_json,
    require_outside_claude,
)
from devflow.config.loader import ConfigLoader
from devflow.config.models import Session
from devflow.session.manager import SessionManager
from devflow.utils.clone_lifecycle import TemporaryDirectoryInUseError, unused_session_clones
from devflow.utils.temp_directory import cleanup_temp_directory

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
    config = config_loader.load_config()
    agent_name = get_agent_display_name(resolve_agent_backend(config=config))
    session_manager = SessionManager(config_loader)

    if is_json_mode() and not force:
        output_json(success=False, error={
            "code": "CONFIRMATION_REQUIRED",
            "message": "Use --force to confirm deletion in JSON mode; clone safety still applies.",
        })
        raise click.exceptions.Exit(1)

    # Handle --all flag
    if delete_all:
        _delete_all_sessions(session_manager, config_loader, force, keep_metadata)
        return

    # Handle --latest flag
    if latest:
        sessions = session_manager.list_sessions()
        if not sessions:
            console_print("[red]No sessions found[/red]")
            if is_json_mode():
                output_json(success=False, error={
                    "code": "SESSION_NOT_FOUND", "message": "No sessions found",
                })
            import sys
            sys.exit(1)
        # Get most recent session
        most_recent = max(sessions, key=lambda s: s.last_active or s.created)
        identifier = most_recent.name
        issue_display = f" ({most_recent.issue_key})" if most_recent.issue_key else ""
        console_print(f"[dim]Using most recent session: {identifier}{issue_display}[/dim]\n")

    # Validate identifier is provided if not using --all or --latest
    if not identifier:
        console_print(
            "[red]Error: Session identifier required (or use --all to delete all sessions)[/red]"
        )
        console_print(
            "[dim]Usage: daf delete <NAME-or-JIRA-KEY> or daf delete --all "
            "or daf delete --latest[/dim]"
        )
        if is_json_mode():
            output_json(success=False, error={
                "code": "MISSING_IDENTIFIER", "message": "Session identifier required",
            })
        import sys
        sys.exit(1)

    # The legacy selection helper prints on missing sessions; keep JSON clean.
    if is_json_mode() and session_manager.get_session(identifier) is None:
        output_json(success=False, error={
            "code": "SESSION_NOT_FOUND", "message": f"No session found for '{identifier}'",
        })
        raise click.exceptions.Exit(1)

    # Get session using special delete utility (handles multi-session with "delete all" option)
    session, delete_all_in_group = get_session_with_delete_all_option(session_manager, identifier)

    if delete_all_in_group:
        # User chose to delete all sessions in the group
        sessions = session_manager.index.get_sessions(identifier)
        session_name = sessions[0].name

        if not force:
            if not Confirm.ask(f"\n[yellow]Delete ALL {len(sessions)} sessions in group '{session_name}'?[/yellow]", default=False):
                console_print("[dim]Cancelled[/dim]")
                return

        _delete_selected_sessions(sessions, session_manager, config_loader, keep_metadata)
        console_print(f"[green]✓[/green] All sessions in group '{session_name}' deleted")
        console_print(f"[dim]Note: {agent_name} session files are NOT deleted[/dim]")
        return

    if not session:
        import sys
        sys.exit(1)

    # Show session info
    console_print("\n[bold]Session to delete:[/bold]")
    issue_display = f" ({session.issue_key})" if session.issue_key else ""
    console_print(f"  Group: {session.name}{issue_display}")
    console_print(f"  Goal: {session.goal}")
    status_text, status_color = get_status_display(session.status)
    console_print(f"  Status: [{status_color}]{status_text}[/{status_color}]")
    if session.working_directory:
        console_print(f"  Working Directory: {session.working_directory}")

    # Show Claude session ID from active conversation
    active_conv = session.active_conversation
    if active_conv and active_conv.ai_agent_session_id:
        console_print(f"  {agent_name} Session: {active_conv.ai_agent_session_id}")

    # Confirm deletion
    if not force:
        if not Confirm.ask(f"\n[yellow]Delete session '{session.name}'?[/yellow]", default=False):
            console_print("[dim]Cancelled[/dim]")
            return

    _delete_selected_sessions([session], session_manager, config_loader, keep_metadata)
    console_print(f"[dim]Note: {agent_name} session files are NOT deleted[/dim]")


def _delete_selected_sessions(
    sessions: list[Session],
    session_manager: SessionManager,
    config_loader: ConfigLoader,
    keep_metadata: bool,
) -> None:
    """Delete each unused session and accurately report refusals in a batch.

    All of a session's clone roots are preflighted before removing any of them.
    Their locks remain held through cleanup and metadata deletion. A busy session
    keeps its index entry, notes, native identity, and conversation history.
    """
    deleted: list[str] = []
    refused: list[dict[str, Any]] = []
    for session in sessions:
        removed_clones: list[str] = []
        with ExitStack() as locks:
            try:
                roots = locks.enter_context(unused_session_clones(session))
                current = session_manager.storage.load_index().get_session(session.name)
                if current is None or current.conversations != session.conversations:
                    raise TemporaryDirectoryInUseError(
                        "Session conversations changed during deletion; "
                        "retry with the latest metadata"
                    )
                for root in roots:
                    existed = Path(root).exists()
                    cleanup_temp_directory(root, locked=True)
                    if Path(root).exists():
                        raise OSError(f"Temporary directory was not removed: {root}")
                    if existed:
                        removed_clones.append(root)
            except (TemporaryDirectoryInUseError, OSError) as error:
                message = (
                    f"Cannot delete session '{session.name}': {error}. "
                    "Exit the owning agent and move terminals outside the clone, then retry "
                    f"'daf delete {session.name}'. --force skips confirmation only. "
                    "Session metadata, notes, native identity, and history were preserved."
                )
                if removed_clones:
                    message += f" Clone roots already removed: {', '.join(removed_clones)}."
                details: dict[str, Any] = {
                    "code": (
                        "SESSION_IN_USE" if isinstance(error, TemporaryDirectoryInUseError)
                        else "CLONE_CLEANUP_FAILED"
                    ),
                    "session": session.name,
                    "message": message,
                    "removed_clones": removed_clones,
                }
                if isinstance(error, TemporaryDirectoryInUseError) and error.holder is not None:
                    details["holder"] = error.holder
                refused.append(details)
                console_print(f"[red]✗[/red] {escape(message)}")
                continue

            # Keep the clone locks through persistence. Do not describe a later
            # metadata-write error as a safe clone refusal with unchanged state.
            session_manager.delete_session(session.name)
            session_dir = config_loader.get_session_dir(session.name)
            if session_dir.exists():
                if not keep_metadata:
                    shutil.rmtree(session_dir)
                    console_print("[green]✓[/green] Deleted session directory")
                else:
                    console_print(f"[yellow]→[/yellow] Kept session files at: {session_dir}")

        deleted.append(session.name)
        console_print(f"[green]✓[/green] Session '{escape(session.name)}' deleted")

    if is_json_mode():
        output_json(
            success=not refused,
            data={
                "deleted_sessions": deleted,
                "deleted_count": len(deleted),
                "refused_sessions": refused,
                "refused_count": len(refused),
            },
            error=refused[0] if refused else None,
        )
    if refused:
        if len(sessions) > 1:
            console_print(
                f"[yellow]Deleted {len(deleted)} sessions; "
                f"preserved {len(refused)} refused sessions.[/yellow]"
            )
        raise click.exceptions.Exit(1)


def _delete_all_sessions(session_manager: SessionManager, config_loader: ConfigLoader, force: bool, keep_metadata: bool = False) -> None:
    """Delete all sessions.

    Args:
        session_manager: SessionManager instance
        config_loader: ConfigLoader instance
        force: Skip confirmation prompt
        keep_metadata: Keep session files (notes, metadata) on disk
    """
    config = config_loader.load_config()
    agent_name = get_agent_display_name(resolve_agent_backend(config=config))

    # Get all sessions
    all_sessions = session_manager.list_sessions()

    if not all_sessions:
        console_print("[yellow]No sessions found[/yellow]")
        if is_json_mode():
            output_json(success=True, data={
                "deleted_sessions": [], "deleted_count": 0,
                "refused_sessions": [], "refused_count": 0,
            })
        return

    # Count total sessions and session groups
    session_groups = set(s.name for s in all_sessions)
    issue_keys = set(s.issue_key for s in all_sessions if s.issue_key)
    session_count = len(all_sessions)

    # Show summary
    console_print("\n[bold yellow]⚠ WARNING: This will delete ALL sessions[/bold yellow]")
    console_print(f"\n  Total sessions: {session_count}")
    console_print(f"  Session groups: {len(session_groups)}")
    if issue_keys:
        console_print(f"  issue tracker tickets: {len(issue_keys)}")
        console_print(f"\n[dim]Groups: {', '.join(sorted(session_groups))}[/dim]")
        console_print(f"[dim]JIRA keys: {', '.join(sorted(issue_keys))}[/dim]")
    else:
        console_print(f"\n[dim]Groups: {', '.join(sorted(session_groups))}[/dim]")

    # Confirm deletion
    if not force:
        console_print()
        if not Confirm.ask(f"[red bold]Delete ALL {session_count} sessions?[/red bold]", default=False):
            console_print("[dim]Cancelled[/dim]")
            return

    _delete_selected_sessions(all_sessions, session_manager, config_loader, keep_metadata)
    console_print(f"[green]✓[/green] All {session_count} sessions deleted")
    console_print(f"[dim]Note: {agent_name} session files are NOT deleted[/dim]")
    console_print("[dim]Tip: Use 'daf init' to reinitialize if needed[/dim]")
