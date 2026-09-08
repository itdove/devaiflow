"""Implementation of 'daf note' and 'daf notes' commands."""

from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from devflow.cli.utils import get_session_with_prompt, add_jira_comment
from devflow.config.loader import ConfigLoader
from devflow.config.models import ConversationContext, Session
from devflow.session.manager import SessionManager

console = Console()


def _get_managed_active_conversation(
    session_manager: SessionManager,
    session_name: str,
) -> Optional[Tuple[Session, ConversationContext, str]]:
    """Return the active conversation for a managed session name.

    The managed session name is the authoritative identity inside an agent
    session.  The agent session ID can be stale or shared by placeholder
    sessions, so it must not be used to choose a different session here.

    Args:
        session_manager: Session manager containing the managed session.
        session_name: Session name from the managed environment.

    Returns:
        The session, active conversation, and working-directory key, or None
        when the managed session is not an active development session.
    """
    # Use the exact session-name index.  The public lookup also accepts issue
    # keys, which would weaken the identity supplied by DAF_SESSION_NAME.
    session = session_manager.index.sessions.get(session_name)
    if not session or session.status not in {"created", "in_progress"}:
        return None

    if (
        session.working_directory
        and session.working_directory in session.conversations
    ):
        working_dir = session.working_directory
    elif len(session.conversations) == 1:
        working_dir = next(iter(session.conversations))
    else:
        return None

    conversation_entry = session.conversations[working_dir]
    conversation = getattr(conversation_entry, "active_session", conversation_entry)
    if conversation is None or conversation.archived:
        return None

    return session, conversation, working_dir


def add_note(identifier: Optional[str] = None, note: Optional[str] = None, sync_to_jira: bool = False, latest: bool = False) -> None:
    """Add a note to a session.

    Args:
        identifier: Session group name or issue key (uses last active if not provided)
        note: Note text
        sync_to_jira: If True, also add note as JIRA comment (requires issue key)
        latest: If True, use the most recently active session
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Import auto-detection helpers lazily to avoid unnecessary CLI imports.
    from devflow.cli.utils import get_active_conversation
    import os

    # Auto-detect active session if in Claude Code session
    # When identifier is provided but note is None, check if we're in an active session
    # If yes, treat identifier as note content (fix for issue #198)
    if identifier and not note and not latest:
        # The managed session name is authoritative.  Falling back to the
        # agent session ID first can select a stale or paused session when
        # multiple sessions still contain the same placeholder ID.
        managed_session_name = (
            os.environ.get("DAF_SESSION_NAME")
            or os.environ.get("CS_SESSION_NAME")
        )
        if managed_session_name:
            active_result = _get_managed_active_conversation(
                session_manager,
                managed_session_name,
            )
            if active_result is None:
                console.print(
                    f"[red]No active session found for '{managed_session_name}'[/red]"
                )
                import sys
                sys.exit(1)
        else:
            active_result = get_active_conversation(session_manager)

        if active_result:
            # We're in an active session - treat identifier as note content
            session, conversation, working_dir = active_result
            note = identifier
            identifier = session.name
            issue_display = f" ({session.issue_key})" if session.issue_key else ""
            console.print(f"[dim]Using active session: {identifier}{issue_display}[/dim]")
        # else: not in active session, keep identifier as session name (old behavior)

    # Priority: explicit identifier > DAF_SESSION_NAME env var > --latest > most recent
    if not identifier:
        if not latest:
            # Check DAF_SESSION_NAME env var when no identifier given
            from devflow.cli.utils import get_active_session_name
            active_name = get_active_session_name()
            if active_name:
                identifier = active_name

        if not identifier:
            # Fall back to most recent session
            all_sessions = session_manager.list_sessions()
            if not all_sessions:
                console.print("[red]No sessions found[/red]")
                import sys
                sys.exit(1)

            # Use the name of the most recent session
            identifier = all_sessions[0].name
            issue_display = f" ({all_sessions[0].issue_key})" if all_sessions[0].issue_key else ""
            console.print(f"[dim]Using session: {identifier}{issue_display}[/dim]")

    # Get session using common utility (handles multi-session selection)
    session = get_session_with_prompt(session_manager, identifier, error_if_not_found=False)
    if not session:
        console.print(f"[red]No session found for '{identifier}'[/red]")
        # Provide helpful guidance based on context
        if os.environ.get("AI_AGENT_SESSION_ID"):
            console.print(f"[dim]Tip: When in an AI agent session, use:[/dim]")
            console.print("[dim]  daf note \"your note text\"[/dim]")
        else:
            console.print("[dim]Usage:[/dim]")
            console.print("[dim]  daf note SESSION_ID \"note text\"          # Add note to specific session[/dim]")
            console.print("[dim]  daf note \"note text\"                      # Add note to active session[/dim]")
            console.print("[dim]  daf note --latest \"note text\"            # Add note to most recent session[/dim]")
        import sys
        sys.exit(1)

    # Get note text if not provided
    if not note:
        note = Prompt.ask("Enter note")
        if not note or not note.strip():
            console.print("[red]✗[/red] Note cannot be empty")
            import sys
            sys.exit(1)
        note = note.strip()

    # Add note locally (always)
    try:
        session_manager.add_note(identifier, note)
        issue_display = f" ({session.issue_key})" if session.issue_key else ""
        console.print(f"[green]✓[/green] Note added to '{session.name}'{issue_display}")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        import sys
        sys.exit(1)

    # Optionally sync to JIRA (only if session has issue key)
    if sync_to_jira:
        if session.issue_key:
            # Format comment with session context
            comment = f"📝 Session ({session.working_directory}): {note}"
            success = add_jira_comment(session.issue_key, comment)
            if not success:
                console.print(f"[dim]Note saved locally[/dim]")
        else:
            console.print(f"[yellow]⚠[/yellow] Session has no issue key - cannot sync to JIRA")
            console.print(f"[dim]Use 'daf link {session.name} --jira <KEY>' to add a JIRA association[/dim]")


def view_notes(identifier: Optional[str] = None, latest: bool = False) -> None:
    """View notes for a session.

    Args:
        identifier: Session group name or issue key (uses last active if not provided)
        latest: If True, use the most recently active session
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Priority: explicit identifier > DAF_SESSION_NAME env var > --latest > most recent
    if not identifier:
        if not latest:
            # Check DAF_SESSION_NAME env var when no identifier given
            from devflow.cli.utils import get_active_session_name
            active_name = get_active_session_name()
            if active_name:
                identifier = active_name

        if not identifier:
            # Fall back to most recent session
            all_sessions = session_manager.list_sessions()
            if not all_sessions:
                console.print("[red]No sessions found[/red]")
                import sys
                sys.exit(1)

            # Use the name of the most recent session
            identifier = all_sessions[0].name
            issue_display = f" ({all_sessions[0].issue_key})" if all_sessions[0].issue_key else ""
            console.print(f"[dim]Viewing notes for: {identifier}{issue_display}[/dim]")

    # Get session using common utility (handles multi-session selection)
    session = get_session_with_prompt(session_manager, identifier)
    if not session:
        import sys
        sys.exit(1)

    # Use session name for directory (not issue key, which might be None)
    session_dir = config_loader.get_session_dir(session.name)
    notes_file = session_dir / "notes.md"

    # Check if notes file exists
    if not notes_file.exists():
        console.print(f"[yellow]No notes found for session '{session.name}'[/yellow]")
        console.print(f"[dim]Add notes using: daf note 'Your note text' (when in active session)[/dim]")
        console.print(f"[dim]                 or daf note '{session.name}' 'Your note text'[/dim]")
        return

    # Read and display notes
    with open(notes_file, "r") as f:
        notes_content = f.read()

    # Display as formatted markdown
    console.print()
    console.print(Markdown(notes_content))
    console.print()
