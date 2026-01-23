"""Implementation of 'daf note' and 'daf notes' commands."""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from devflow.cli.utils import get_session_with_prompt, add_jira_comment, require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager

console = Console()


@require_outside_claude
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

    # If no identifier or --latest flag, use most recent active session
    if not identifier or latest:
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
    session = get_session_with_prompt(session_manager, identifier)
    if not session:
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

    # If no identifier or --latest flag, use most recent active session
    if not identifier or latest:
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
        console.print(f"[dim]Add notes using: daf note '{session.name}' 'Your note text'[/dim]")
        return

    # Read and display notes
    with open(notes_file, "r") as f:
        notes_content = f.read()

    # Display as formatted markdown
    console.print()
    console.print(Markdown(notes_content))
    console.print()
