"""Implementation of 'daf summary' command."""

from rich.console import Console

from devflow.cli.utils import get_session_with_prompt, display_session_header
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.session.summary import generate_session_summary, generate_prose_summary

console = Console()


def show_summary(identifier: str = None, detail: bool = False, ai_summary: bool = False, latest: bool = False) -> None:
    """Display session summary without opening Claude Code.

    Args:
        identifier: Session group name or issue key
        detail: If True, show full file lists and commands. Default: False (condensed view)
        ai_summary: If True, use AI to generate summary. Default: False (use config)
        latest: If True, use the most recently active session
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # If --latest flag or no identifier, use most recent active session
    if latest or not identifier:
        all_sessions = session_manager.list_sessions()
        if not all_sessions:
            console.print("[red]No sessions found[/red]")
            return
        identifier = all_sessions[0].name
        issue_display = f" ({all_sessions[0].issue_key})" if all_sessions[0].issue_key else ""
        console.print(f"[dim]Using session: {identifier}{issue_display}[/dim]\n")

    # Get session using common utility (handles multi-session selection)
    session = get_session_with_prompt(session_manager, identifier)
    if not session:
        return

    # Display session metadata header using common utility
    display_session_header(session)

    # Generate and display session summary from conversation
    # Check if session has an active conversation with a ai_agent_session_id
    has_conversation = session.active_conversation and session.active_conversation.ai_agent_session_id
    if has_conversation:
        try:
            summary = generate_session_summary(session)

            # Only display if we have some summary data
            if (summary.files_created or summary.files_modified or
                summary.commands_run or summary.last_assistant_message):

                console.print()  # Blank line before summary

                if detail:
                    # Detailed view: show all files and commands
                    # Files created
                    if summary.files_created:
                        console.print(f"[bold]Files Created ({len(summary.files_created)}):[/bold]")
                        for file in summary.files_created:
                            console.print(f"  ✏️  {file}")
                        console.print()

                    # Files modified
                    if summary.files_modified:
                        console.print(f"[bold]Files Modified ({len(summary.files_modified)}):[/bold]")
                        for file in summary.files_modified:
                            console.print(f"  ✏️  {file}")
                        console.print()

                    # Files read
                    if summary.files_read:
                        console.print(f"[bold]Files Read ({len(summary.files_read)}):[/bold]")
                        for file in summary.files_read:
                            console.print(f"  📖 {file}")
                        console.print()

                    # Commands run
                    if summary.commands_run:
                        console.print(f"[bold]Commands Run ({len(summary.commands_run)}):[/bold]")
                        for cmd in summary.commands_run:
                            console.print(f"  $ {cmd.command}")
                        console.print()

                    # Last activity
                    if summary.last_assistant_message:
                        console.print("[bold]Last Activity:[/bold]")
                        console.print(f"  \"{summary.last_assistant_message}\"")
                        console.print()

                    # Tool call statistics
                    if summary.tool_call_stats:
                        console.print("[bold]Tool Usage:[/bold]")
                        for tool_name, count in sorted(summary.tool_call_stats.items(), key=lambda x: x[1], reverse=True):
                            console.print(f"  {tool_name}: {count} calls")
                        console.print()
                else:
                    # Condensed view: prose summary + key details
                    # Determine summary mode
                    summary_mode = "local"  # Default
                    if ai_summary:
                        summary_mode = "ai"
                    elif hasattr(config_loader, 'config') and hasattr(config_loader.config, 'session_summary'):
                        summary_mode = config_loader.config.session_summary.mode

                    # Generate and display prose summary
                    # Pass agent_backend for graceful degradation (non-Claude agents use local mode)
                    config = config_loader.load_config()
                    prose = generate_prose_summary(
                        summary,
                        mode=summary_mode,
                        agent_backend=config.agent_backend if config else None
                    )

                    # Show indicator if using AI
                    if summary_mode in ("ai", "both"):
                        console.print("[bold cyan]## Summary of Changes[/bold cyan] [dim](AI-powered)[/dim]\n")
                    else:
                        console.print("[bold cyan]## Summary of Changes[/bold cyan]\n")

                    console.print(prose)
                    console.print()

                    # Files created (show first 5)
                    if summary.files_created:
                        console.print(f"[bold]Files Created ({len(summary.files_created)}):[/bold]")
                        for file in summary.files_created[:5]:
                            console.print(f"  ✏️  {file}")
                        if len(summary.files_created) > 5:
                            console.print(f"  [dim]... and {len(summary.files_created) - 5} more[/dim]")
                        console.print()

                    # Files modified (show first 5)
                    if summary.files_modified:
                        console.print(f"[bold]Files Modified ({len(summary.files_modified)}):[/bold]")
                        for file in summary.files_modified[:5]:
                            console.print(f"  ✏️  {file}")
                        if len(summary.files_modified) > 5:
                            console.print(f"  [dim]... and {len(summary.files_modified) - 5} more[/dim]")
                        console.print()

                    # Tool call statistics
                    console.print("[bold cyan]## Tool Usage[/bold cyan]\n")
                    if summary.tool_call_stats:
                        for tool_name, count in sorted(summary.tool_call_stats.items(), key=lambda x: x[1], reverse=True):
                            console.print(f"  {tool_name}: {count} calls")
                        console.print()

                    # Hint about detail view
                    if (len(summary.files_created) > 5 or len(summary.files_modified) > 5 or
                        summary.files_read or summary.commands_run):
                        console.print("[dim]Use --detail to see all files, commands, and files read[/dim]")

            else:
                console.print("\n[dim]No activity summary available yet (session may be empty)[/dim]")

        except Exception as e:
            console.print(f"\n[yellow]Warning: Could not generate session summary: {e}[/yellow]")
    else:
        console.print("\n[yellow]No Claude session ID - session summary not available[/yellow]")

    # Show recent notes if available
    session_dir = config_loader.get_session_dir(session.name)
    notes_file = session_dir / "notes.md"
    if notes_file.exists():
        console.print("\n[bold]Recent notes:[/bold]")
        with open(notes_file, "r") as f:
            lines = f.readlines()
            # Show last 10 lines
            console.print("".join(lines[-10:]))
