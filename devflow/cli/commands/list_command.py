"""Implementation of 'daf list' command."""

import os
from datetime import datetime
from typing import Dict, Optional

from rich.console import Console
from rich.table import Table

from devflow.cli.utils import get_active_conversation, get_status_display, output_json as json_output, serialize_sessions
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.utils.time_parser import parse_time_expression

console = Console()


def _display_page(
    sessions_page,
    current_page: int,
    total_pages: int,
    total_sessions: int,
    limit: int,
    show_all: bool,
) -> None:
    """Display a single page of sessions.

    Args:
        sessions_page: List of sessions to display on this page
        current_page: Current page number
        total_pages: Total number of pages
        total_sessions: Total number of sessions across all pages
        limit: Number of sessions per page
        show_all: Whether showing all sessions
    """
    # Detect active conversation (if any)
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    active_result = get_active_conversation(session_manager)
    active_session_name = None
    active_session_id = None
    active_working_dir = None

    if active_result:
        active_session, active_conversation, active_working_dir = active_result
        active_session_name = active_session.name
            # Create table
    table = Table(title="Your Sessions", show_header=True, header_style="bold magenta")
    table.add_column("Status")
    table.add_column("Name", style="bold")
    table.add_column("Workspace", style="cyan")
    table.add_column("JIRA")
    table.add_column("Summary")
    table.add_column("Conversations", style="dim")
    table.add_column("Last Activity", style="dim", justify="right")
    table.add_column("Time", justify="right")

    for session in sessions_page:
        # Check if this session is currently active
        is_active = (
            active_session_name == session.name
            and active_session.name == session.name
        )

        # Status display with color
        status_text, status_color = get_status_display(session.status)
        # Add ▶ indicator for active session
        if is_active:
            status_display = f"[green]▶[/green] [{status_color}]{status_text}[/{status_color}]"
        else:
            status_display = f"  [{status_color}]{status_text}[/{status_color}]"

        # Calculate total time
        total_seconds = 0
        for ws in session.work_sessions:
            if ws.end:
                delta = ws.end - ws.start
                total_seconds += delta.total_seconds()

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        time_str = f"{hours}h {minutes}m" if total_seconds > 0 else "-"

        # Display session name with session ID
        name_display = f"{session.name}"

        # Display issue key or "-" if not linked
        issue_display = session.issue_key or "-"

        # Build conversations display (count + list of working directories)
        if session.conversations:
            conv_count = len(session.conversations)
            conv_dirs = sorted(session.conversations.keys())

            # Highlight active conversation if this session is active
            if is_active and active_working_dir:
                # Bold the active conversation
                highlighted_dirs = [
                    f"[bold]{d}[/bold]" if d == active_working_dir else d
                    for d in conv_dirs
                ]
                conv_list = ", ".join(highlighted_dirs)
            else:
                conv_list = ", ".join(conv_dirs)

            conversations_display = f"{conv_count}: {conv_list}"
        else:
            # Fallback for old sessions without conversations dict
            conversations_display = session.working_directory or "-"

        # AAP-63377: Display workspace name
        workspace_display = session.workspace_name or "-"

        # Get most recent conversation activity (last opened/closed time)
        last_session_display = "-"
        if session.conversations:
            # Find the most recent last_active across all conversations
            most_recent_activity = None
            for conv_data in session.conversations.values():
                # Handle both Conversation (new format) and ConversationContext (old format)
                conv = conv_data.active_session if hasattr(conv_data, 'active_session') else conv_data
                if conv and conv.last_active:
                    if most_recent_activity is None or conv.last_active > most_recent_activity:
                        most_recent_activity = conv.last_active

            if most_recent_activity:
                # Calculate time ago
                time_diff = datetime.now() - most_recent_activity
                hours_ago = int(time_diff.total_seconds() // 3600)
                days_ago = hours_ago // 24

                if days_ago > 0:
                    last_session_display = f"{days_ago}d ago"
                elif hours_ago > 0:
                    last_session_display = f"{hours_ago}h ago"
                else:
                    minutes_ago = int((time_diff.total_seconds() % 3600) // 60)
                    last_session_display = f"{minutes_ago}m ago" if minutes_ago > 0 else "just now"

        # Add row
        table.add_row(
            status_display,
            name_display,
            workspace_display,
            issue_display,
            session.issue_metadata.get("summary") if session.issue_metadata else session.goal or "",
            conversations_display,
            last_session_display,
            time_str,
        )

    console.print(table)

    # Calculate time for displayed sessions
    displayed_time = sum(
        sum((ws.end - ws.start).total_seconds() for ws in s.work_sessions if ws.end)
        for s in sessions_page
    )
    displayed_hours = int(displayed_time // 3600)
    displayed_minutes = int((displayed_time % 3600) // 60)

    # Show pagination info and summary
    if show_all or total_sessions <= limit:
        # Not paginated or showing all
        console.print(
            f"\n[dim]Total: {total_sessions} sessions | "
            f"{displayed_hours}h {displayed_minutes}m tracked[/dim]"
        )
    else:
        # Paginated view
        start_num = (current_page - 1) * limit + 1
        end_num = min(current_page * limit, total_sessions)
        console.print(
            f"\n[dim]Showing {start_num}-{end_num} of {total_sessions} sessions "
            f"(page {current_page}/{total_pages}) | "
            f"{displayed_hours}h {displayed_minutes}m on this page[/dim]"
        )


def list_sessions(
    status: Optional[str] = None,
    working_directory: Optional[str] = None,
    issue_metadata_filters: Optional[Dict[str, str]] = None,
    issue_status: Optional[str] = None,
    since: Optional[str] = None,
    before: Optional[str] = None,
    limit: int = 25,
    page: Optional[int] = None,
    show_all: bool = False,
    output_json: bool = False,
) -> None:
    """List all sessions with optional filters and pagination.

    Args:
        status: Filter by session status (comma-separated for multiple)
        working_directory: Filter by working directory
        issue_metadata_filters: Filter by custom fields (e.g., {"sprint": "Sprint 1", "severity": "Critical"})
        issue_status: Filter by issue tracker status (comma-separated for multiple)
        since: Filter by sessions active since this time (e.g., "last week", "3 days ago")
        before: Filter by sessions active before this time
        limit: Number of sessions to show per page (default: 25)
        page: Page number to display (1-indexed). If None, interactive mode is used.
        show_all: Show all sessions without pagination (default: False)
        output_json: Output in JSON format (default: False)
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Parse time expressions
    since_dt = None
    if since:
        since_dt = parse_time_expression(since)
        if since_dt is None:
            if output_json:
                json_output(
                    success=False,
                    error={"message": f"Could not parse time expression: {since}", "code": "INVALID_TIME_EXPRESSION"}
                )
            else:
                console.print(f"[red]✗[/red] Could not parse time expression: {since}")
                console.print("[dim]Examples: 'last week', '3 days ago', '2025-01-01'[/dim]")
            return

    before_dt = None
    if before:
        before_dt = parse_time_expression(before)
        if before_dt is None:
            if output_json:
                json_output(
                    success=False,
                    error={"message": f"Could not parse time expression: {before}", "code": "INVALID_TIME_EXPRESSION"}
                )
            else:
                console.print(f"[red]✗[/red] Could not parse time expression: {before}")
                console.print("[dim]Examples: 'last week', '3 days ago', '2025-01-01'[/dim]")
            return

    sessions = session_manager.list_sessions(
        status=status,
        working_directory=working_directory,
        issue_metadata_filters=issue_metadata_filters,
        issue_status=issue_status,
        since=since_dt,
        before=before_dt,
    )

    if not sessions:
        if output_json:
            json_output(
                success=True,
                data={"sessions": [], "total_count": 0},
                metadata={
                    "filters_applied": {
                        "status": status,
                        "working_directory": working_directory,
                        "issue_metadata_filters": issue_metadata_filters,
                        "issue_status": issue_status,
                        "since": since,
                        "before": before,
                    }
                }
            )
        else:
            console.print("[dim]No sessions found[/dim]")
            if status or working_directory or issue_metadata_filters or issue_status or since or before:
                console.print("[dim]Try removing filters or use 'daf sync' to fetch issue tracker tickets[/dim]")
        return

    # Store total count before pagination
    total_sessions = len(sessions)

    # JSON output mode
    if output_json:
        # Calculate pagination info
        if show_all:
            sessions_to_output = sessions
            current_page = 1
            total_pages = 1
        elif page is not None:
            # Validate limit
            if limit < 1:
                json_output(
                    success=False,
                    error={"message": "Limit must be 1 or greater", "code": "INVALID_LIMIT"}
                )
                return

            total_pages = (total_sessions + limit - 1) // limit
            if page < 1:
                json_output(
                    success=False,
                    error={"message": "Page number must be 1 or greater", "code": "INVALID_PAGE"}
                )
                return

            # Check if page is out of range
            if (page - 1) * limit >= total_sessions:
                json_output(
                    success=False,
                    error={"message": f"Page {page} is out of range (total pages: {total_pages})", "code": "PAGE_OUT_OF_RANGE"}
                )
                return

            current_page = page
            start_idx = (current_page - 1) * limit
            end_idx = start_idx + limit
            sessions_to_output = sessions[start_idx:end_idx]
        else:
            # Default to page 1 for JSON output (no interactive mode in JSON)
            total_pages = (total_sessions + limit - 1) // limit
            current_page = 1
            start_idx = 0
            end_idx = limit
            sessions_to_output = sessions[start_idx:end_idx]

        # Output JSON
        json_output(
            success=True,
            data={
                "sessions": serialize_sessions(sessions_to_output),
                "total_count": total_sessions,
            },
            metadata={
                "filters_applied": {
                    "status": status,
                    "working_directory": working_directory,
                    "issue_metadata_filters": issue_metadata_filters,
                    "issue_status": issue_status,
                    "since": since,
                    "before": before,
                },
                "pagination": {
                    "page": current_page,
                    "limit": limit,
                    "total_pages": total_pages,
                }
            }
        )
        return

    # Validate limit
    if limit < 1:
        console.print("[red]✗[/red] Limit must be 1 or greater")
        return

    # Determine mode: interactive, non-interactive single page, or show all
    is_interactive = page is None and not show_all

    if show_all:
        # Show all sessions at once (existing behavior)
        total_pages = 1
        current_page = 1
        _display_page(sessions, current_page, total_pages, total_sessions, limit, show_all=True)
    elif page is not None:
        # Non-interactive mode: show specific page only (existing behavior)
        if page < 1:
            console.print("[red]✗[/red] Page number must be 1 or greater")
            return

        total_pages = (total_sessions + limit - 1) // limit  # Ceiling division

        # Check if page is out of range
        if (page - 1) * limit >= total_sessions:
            console.print(f"[red]✗[/red] Page {page} is out of range (total pages: {total_pages})")
            console.print(f"[dim]Showing page 1 instead[/dim]")
            page = 1

        current_page = page
        start_idx = (current_page - 1) * limit
        end_idx = start_idx + limit
        sessions_page = sessions[start_idx:end_idx]

        _display_page(sessions_page, current_page, total_pages, total_sessions, limit, show_all=False)

        # Show hint for navigation
        if current_page < total_pages:
            console.print(f"[dim]Use --page {current_page + 1} to see more, or --all to show all sessions[/dim]")
        if current_page > 1:
            console.print(f"[dim]Use --page {current_page - 1} to go back[/dim]")
    else:
        # Interactive mode: display pages one by one
        total_pages = (total_sessions + limit - 1) // limit  # Ceiling division
        current_page = 1

        while current_page <= total_pages:
            # Calculate slice for current page
            start_idx = (current_page - 1) * limit
            end_idx = start_idx + limit
            sessions_page = sessions[start_idx:end_idx]

            # Display the current page
            _display_page(sessions_page, current_page, total_pages, total_sessions, limit, show_all=False)

            # If there are more pages, prompt user
            if current_page < total_pages:
                console.print()  # Blank line for readability
                try:
                    response = console.input("[dim]Press Enter to continue to next page, or 'q' to quit: [/dim]")
                    if response.lower().strip() == 'q':
                        break
                    console.print()  # Blank line before next page
                except (EOFError, KeyboardInterrupt):
                    # Handle EOF (e.g., in tests or non-interactive environments) or Ctrl+C
                    console.print()  # Newline for clean exit
                    break

            current_page += 1
