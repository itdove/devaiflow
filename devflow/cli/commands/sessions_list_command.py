"""Implementation of 'daf sessions list' command."""

from typing import Optional

from rich.console import Console
from rich.table import Table

from devflow.cli.utils import output_json as json_output
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager

console = Console()


def sessions_list(identifier: str, output_json: bool = False) -> None:
    """List all Claude Code sessions (conversations) for a DevAIFlow session.

    This command shows all conversations across all repositories, including
    both active and archived conversations.

    Args:
        identifier: Session name or issue tracker key
        output_json: If True, output results in JSON format

    Example:
        daf sessions list PROJ-12345
        daf sessions list my-session --json
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Get session
    session = session_manager.get_session(identifier)

    if not session:
        if output_json:
            json_output(
                success=False,
                error={"message": f"Session '{identifier}' not found", "code": "SESSION_NOT_FOUND"}
            )
        else:
            console.print(f"[red]Session '{identifier}' not found[/red]")
        return

    # JSON output mode
    if output_json:
        _output_json_sessions_list(session)
        return

    # Display in human-readable format
    _display_sessions_list(session)


def _output_json_sessions_list(session) -> None:
    """Output sessions list in JSON format.

    Args:
        session: Session object
    """
    repositories = []

    for working_dir, conversation in session.conversations.items():
        conversations = []
        # Process all sessions (active + archived) in this Conversation
        for idx, conv in enumerate(conversation.get_all_sessions(), start=1):
            conversations.append({
                "number": idx,
                "uuid": conv.ai_agent_session_id,
                "status": "archived" if conv.archived else "active",
                "created": conv.created.isoformat(),
                "last_active": conv.last_active.isoformat(),
                "message_count": conv.message_count,
                "branch": conv.branch,
                "prs": conv.prs,
                "summary": conv.summary,  # Display summary for archived sessions
            })

        repositories.append({
            "working_dir": working_dir,
            "conversations": conversations,
        })

    json_output(
        success=True,
        data={
            "session_name": session.name,
            "issue_key": session.issue_key,
            "repositories": repositories,
        }
    )


def _display_sessions_list(session) -> None:
    """Display sessions list in human-readable format.

    Args:
        session: Session object
    """
    # Header
    issue_display = f" ({session.issue_key})" if session.issue_key else ""
    console.print(f"\n[bold cyan]Conversations for Session: {session.name}{issue_display}[/bold cyan]\n")

    if not session.conversations:
        console.print("[yellow]No conversations found in this session[/yellow]")
        return

    # Count total conversations
    total_convs = sum(len(conversation.get_all_sessions()) for conversation in session.conversations.values())
    console.print(f"[bold]Total:[/bold] {len(session.conversations)} repositories, {total_convs} conversations\n")

    # Display conversations grouped by repository
    for working_dir, conversation in session.conversations.items():
        console.print(f"[bold]Repository: {working_dir}[/bold]")

        # Create table for this repository's conversations
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="dim")
        table.add_column("Status", style="")
        table.add_column("UUID", style="cyan")
        table.add_column("Created", style="dim")
        table.add_column("Messages", justify="right")
        table.add_column("Summary", style="dim", max_width=50)  # Show summaries

        # Process all sessions (active + archived) in this Conversation
        for idx, conv in enumerate(conversation.get_all_sessions(), start=1):
            status = "[green]active[/green]" if not conv.archived else "[yellow]archived[/yellow]"
            created_str = conv.created.strftime("%Y-%m-%d %H:%M")
            uuid_short = conv.ai_agent_session_id[:8] + "..."

            # Truncate summary for table display
            summary_display = ""
            if conv.summary:
                # Show first 80 characters + ellipsis if longer
                summary_display = conv.summary[:80]
                if len(conv.summary) > 80:
                    summary_display += "..."

            table.add_row(
                str(idx),
                status,
                uuid_short,
                created_str,
                str(conv.message_count),
                summary_display or "N/A",
            )

        console.print(table)
        console.print()  # Add spacing between repositories
