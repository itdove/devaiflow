"""Implementation of 'daf update' command."""

from rich.console import Console
from rich.prompt import Prompt

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager

console = Console()


@require_outside_claude
def update_session(identifier: str, ai_agent_session_id: str = None) -> None:
    """Update session with Claude session ID.

    Args:
        identifier: Session group name or issue key
        ai_agent_session_id: Claude session UUID (prompts if not provided)
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Get session (uses first session if multiple exist)
    session = session_manager.get_session(identifier)
    if not session:
        console.print(f"[red]Session '{identifier}' not found[/red]")
        return

    # Show current session info
    issue_display = f" ({session.issue_key})" if session.issue_key else ""
    console.print(f"\n[bold]Session: {session.name}{issue_display}[/bold]")
    console.print(f"  Goal: {session.goal}")

    # Get current session ID from active conversation
    current_session_id = None
    if session.active_conversation:
        current_session_id = session.active_conversation.ai_agent_session_id
    console.print(f"  Current session ID: {current_session_id or '[dim]None[/dim]'}")

    # Get session ID if not provided
    if not ai_agent_session_id:
        console.print("\n[cyan]Tip: Run 'claude --resume' to see available sessions[/cyan]")
        ai_agent_session_id = Prompt.ask("Enter Claude session ID")

    if not ai_agent_session_id:
        console.print("[yellow]No session ID provided[/yellow]")
        return

    # Update session - update the active conversation's ai_agent_session_id
    if session.active_conversation:
        session.active_conversation.ai_agent_session_id = ai_agent_session_id
    else:
        console.print("[yellow]Warning: No active conversation found. Session ID not updated.[/yellow]")
        return

    session.status = "in_progress"
    session_manager.update_session(session)

    console.print(f"[green]✓[/green] Updated session '{session.name}'{issue_display}")
    console.print(f"  Claude session ID: {ai_agent_session_id}")
