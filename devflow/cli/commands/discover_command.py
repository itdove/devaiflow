"""Implementation of 'daf discover' command."""

from rich.console import Console
from rich.table import Table

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.discovery import SessionDiscovery
from devflow.session.manager import SessionManager

console = Console()


@require_outside_claude
def discover_sessions() -> None:
    """Discover existing Claude Code sessions not managed by daf tool."""
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    discovery = SessionDiscovery()

    console.print("\n[bold]Discovering Claude Code sessions...[/bold]\n")

    # Discover all Claude sessions
    discovered = discovery.discover_sessions()

    if not discovered:
        console.print("[yellow]No Claude Code sessions found[/yellow]")
        console.print("[dim]Claude sessions are stored in ~/.claude/projects/[/dim]")
        return

    # Get list of UUIDs already managed by daf tool
    managed_sessions = session_manager.list_sessions()
    managed_uuids = {s.ai_agent_session_id for s in managed_sessions if s.ai_agent_session_id}

    # Separate managed and unmanaged sessions
    unmanaged = [s for s in discovered if s.uuid not in managed_uuids]
    managed = [s for s in discovered if s.uuid in managed_uuids]

    # Display unmanaged sessions (importable)
    if unmanaged:
        console.print(f"[bold green]Found {len(unmanaged)} unmanaged session(s)[/bold green]")
        console.print("[dim]These sessions can be imported with 'daf import-session'[/dim]\n")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("UUID", style="cyan", width=36)
        table.add_column("Working Dir", style="yellow", width=30)
        table.add_column("Messages", justify="right", style="white")
        table.add_column("Last Active", style="dim white", width=20)
        table.add_column("First Message", style="dim white", width=50)

        for session in unmanaged:
            # Format last active
            last_active = session.last_active.strftime("%Y-%m-%d %H:%M")

            # Truncate first message
            first_msg = session.first_message or "(no message)"
            if len(first_msg) > 47:
                first_msg = first_msg[:47] + "..."

            # Truncate working directory
            working_dir = session.working_directory or "unknown"
            if len(working_dir) > 27:
                working_dir = "..." + working_dir[-24:]

            table.add_row(
                session.uuid,
                working_dir,
                str(session.message_count),
                last_active,
                first_msg,
            )

        console.print(table)
        console.print()

    # Display managed sessions
    if managed:
        console.print(f"\n[bold]Found {len(managed)} managed session(s)[/bold]")
        console.print("[dim]These sessions are already tracked by daf tool[/dim]\n")

        table = Table(show_header=True, header_style="bold green")
        table.add_column("UUID", style="green", width=36)
        table.add_column("JIRA Key", style="yellow", width=15)
        table.add_column("Working Dir", style="white", width=30)
        table.add_column("Messages", justify="right", style="white")
        table.add_column("Last Active", style="dim white", width=20)

        # Find JIRA keys for managed sessions
        uuid_to_jira = {}
        for s in managed_sessions:
            if s.ai_agent_session_id:
                uuid_to_jira[s.ai_agent_session_id] = (s.issue_key, s.session_id)

        for session in managed:
            last_active = session.last_active.strftime("%Y-%m-%d %H:%M")
            working_dir = session.working_directory or "unknown"
            if len(working_dir) > 27:
                working_dir = "..." + working_dir[-24:]

            issue_key= "unknown"
            if session.uuid in uuid_to_jira:
                key, sid = uuid_to_jira[session.uuid]
                issue_key= f"{key} (#{sid})"

            table.add_row(
                session.uuid,
                issue_key,
                working_dir,
                str(session.message_count),
                last_active,
            )

        console.print(table)
        console.print()

    # Summary
    console.print(f"[bold]Total:[/bold] {len(discovered)} session(s) | "
                  f"[green]{len(unmanaged)} unmanaged[/green] | "
                  f"[yellow]{len(managed)} managed[/yellow]")

    if unmanaged:
        console.print("\n[bold cyan]Next steps:[/bold cyan]")
        console.print("  [cyan]daf import-session <UUID>[/cyan] - Import a specific session")
        console.print("  [dim]You'll be prompted for issue key and goal[/dim]")
