"""Implementation of 'daf sync' command."""

from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.table import Table

from devflow.cli.utils import output_json as json_output, require_outside_claude, serialize_session, console_print
from devflow.config.loader import ConfigLoader
from devflow.jira import JiraClient
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError
from devflow.session.manager import SessionManager

console = Console()


@require_outside_claude
def sync_jira(
    sprint: Optional[str] = None,
    ticket_type: Optional[str] = None,
    epic: Optional[str] = None,
    output_json: bool = False,
) -> None:
    """Sync with JIRA to import assigned tickets as sessions.

    Fetches issue tracker tickets assigned to you and creates session groups for tickets
    that don't already have sessions.

    Filter criteria (from config):
    - Status: New, To Do, or In Progress (configurable)
    - Sprint: Must be set
    - Story points: NOT required (Bugs don't have story points)

    Args:
        sprint: Filter by sprint (e.g., "2025-01" or "current")
        ticket_type: Filter by ticket type (Story, Bug, etc.)
        epic: Filter by epic
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Load config to get JIRA filters
    config = config_loader.load_config()
    if not config:
        console.print("[yellow]⚠[/yellow] No configuration found")
        console.print("[dim]Run 'daf init' to create default configuration[/dim]")
        return

    # Get JIRA sync filters from config
    sync_filters = config.jira.filters.get("sync")
    if not sync_filters:
        console.print("[yellow]⚠[/yellow] No sync filters configured")
        console.print("[dim]Check $DEVAIFLOW_HOME/config.json (or ~/.daf-sessions/config.json if DEVAIFLOW_HOME not set)[/dim]")
        return

    console_print("[cyan]Fetching issue tracker tickets...[/cyan]")

    # Initialize JIRA client
    try:
        jira_client = JiraClient()
    except FileNotFoundError as e:
        console_print(f"[red]✗[/red] {e}")
        return

    # Fetch tickets using JIRA REST API
    try:
        tickets = jira_client.list_tickets(
            assignee=sync_filters.assignee,
            status_list=sync_filters.status if sync_filters.status else None,
            sprint=sprint,
            ticket_type=ticket_type,
            field_mappings=config.jira.field_mappings,
        )
    except JiraAuthError as e:
        console_print(f"[red]✗[/red] Authentication failed: {e}")
        return
    except JiraApiError as e:
        console_print(f"[red]✗[/red] JIRA API error: {e}")
        return
    except JiraConnectionError as e:
        console_print(f"[red]✗[/red] Connection error: {e}")
        return

    console_print(f"[dim]Found {len(tickets)} tickets matching filters[/dim]")

    # Filter by required fields (from config)
    required_fields = sync_filters.required_fields if hasattr(sync_filters, 'required_fields') else []
    if required_fields:
        filtered_tickets = []
        for ticket in tickets:
            # Check if ticket has all required fields
            skip_ticket = False
            for field in required_fields:
                if field == "sprint" and not ticket.get("sprint"):
                    console_print(f"[dim]Skipping {ticket['key']}: No sprint assigned[/dim]")
                    skip_ticket = True
                    break
                elif field == "story-points" and not ticket.get("points"):
                    # Allow tickets without story points (Bugs don't have story points)
                    pass

            if not skip_ticket:
                filtered_tickets.append(ticket)

        tickets = filtered_tickets
        console_print(f"[dim]After filtering by required fields: {len(tickets)} tickets[/dim]")

    console_print()

    if not tickets:
        console_print("[bold]Sync complete[/bold]")
        console_print(f"[dim]No tickets found matching filters[/dim]")
        console_print(f"[dim]Filters: assignee={sync_filters.assignee}, status={sync_filters.status}[/dim]")
        return

    # Process tickets
    created_count = 0
    updated_count = 0
    created_sessions: List[Dict[str, Any]] = []
    updated_sessions: List[Dict[str, Any]] = []

    for ticket in tickets:
        issue_key = ticket["key"]

        # Check if development session already exists (ignore ticket_creation sessions)
        # ticket_creation sessions are for creating issue tracker tickets, not for working on them
        all_sessions = session_manager.index.get_sessions(issue_key)
        existing = [s for s in all_sessions if s.session_type == "development"] if all_sessions else []

        if not existing:
            # Create new session with concatenated goal format
            # Build concatenated goal: "{ISSUE_KEY}: {TITLE}"
            issue_summary = ticket.get("summary")
            if issue_summary:
                goal = f"{issue_key}: {issue_summary}"
            else:
                goal = issue_key

            session = session_manager.create_session(
                name=issue_key,  # Use issue key as session name
                issue_key=issue_key,
                goal=goal,
            )

            # Set session status to created (not in_progress yet)
            session.status = "created"

            # Populate issue tracker metadata
            session.issue_tracker = "jira"
            session.issue_key = issue_key
            session.issue_updated = ticket.get("updated")
            session.issue_metadata = {
                "summary": ticket.get("summary"),
                "type": ticket.get("type"),
                "status": ticket.get("status"),
                "sprint": ticket.get("sprint"),
                "points": ticket.get("points"),
                "assignee": ticket.get("assignee"),
                "epic": ticket.get("epic"),
            }
            # Remove None values from issue_metadata
            session.issue_metadata = {k: v for k, v in session.issue_metadata.items() if v is not None}

            session_manager.update_session(session)
            created_count += 1

            # Track for JSON output
            if output_json:
                created_sessions.append(serialize_session(session))

            console_print(f"[green]✓[/green] Created session: {issue_key} - {goal[:60]}")
        else:
            # Update existing session metadata only if ticket has been updated
            for session in existing:
                ticket_updated = ticket.get("updated")
                session_updated = session.issue_updated

                # Update if:
                # 1. Ticket has an updated timestamp AND session doesn't have one (first sync after this feature)
                # 2. Ticket's updated timestamp is newer than session's stored timestamp
                needs_update = False
                if ticket_updated:
                    if not session_updated:
                        needs_update = True  # First sync, populate the timestamp
                    elif ticket_updated != session_updated:
                        needs_update = True  # Ticket has been updated

                if needs_update:
                    # Update using issue_metadata structure
                    session.issue_tracker = "jira"
                    session.issue_key = issue_key
                    session.issue_updated = ticket_updated
                    session.issue_metadata = {
                        "summary": ticket.get("summary"),
                        "type": ticket.get("type"),
                        "status": ticket.get("status"),
                        "sprint": ticket.get("sprint"),
                        "points": ticket.get("points"),
                        "assignee": ticket.get("assignee"),
                        "epic": ticket.get("epic"),
                    }
                    # Remove None values from issue_metadata
                    session.issue_metadata = {k: v for k, v in session.issue_metadata.items() if v is not None}

                    session_manager.update_session(session)
                    updated_count += 1

                    # Track for JSON output
                    if output_json:
                        updated_sessions.append(serialize_session(session))

                    console_print(f"[cyan]↻[/cyan] Updated session: {issue_key}")
                else:
                    console_print(f"[dim]  Skipped (no changes): {issue_key}[/dim]")

    # JSON output mode
    if output_json:
        json_output(
            success=True,
            data={
                "created_sessions": created_sessions,
                "updated_sessions": updated_sessions,
                "created_count": created_count,
                "updated_count": updated_count,
            },
            metadata={
                "filters": {
                    "assignee": sync_filters.assignee,
                    "status": sync_filters.status if sync_filters.status else None,
                    "sprint": sprint,
                    "ticket_type": ticket_type,
                    "epic": epic,
                }
            }
        )
        return

    console_print()
    console_print("[bold]Sync complete[/bold]")
    console_print(f"[green]Created:[/green] {created_count} new sessions")
    console_print(f"[cyan]Updated:[/cyan] {updated_count} existing sessions")
    console_print()
    console_print(f"[dim]Use 'daf list' to see all sessions[/dim]")
    console_print(f"[dim]Use 'daf open <JIRA-KEY>' to start work[/dim]")
