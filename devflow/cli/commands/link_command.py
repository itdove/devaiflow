"""Implementation of 'daf link' command."""

import subprocess
import sys
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm

from devflow.cli.utils import require_outside_claude, is_json_mode, console_print, output_json
from devflow.config.loader import ConfigLoader
from devflow.issue_tracker.factory import create_issue_tracker_client
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError
from devflow.session.manager import SessionManager

console = Console()


def _fetch_issue_metadata_dict(issue_key: str) -> Optional[dict]:
    """Fetch issue tracker ticket metadata using issue tracker client.

    Args:
        issue_key: issue tracker key (e.g., PROJ-52470)

    Returns:
        issue tracker ticket metadata dictionary if successful, None if not found

    Raises:
        RuntimeError: If ticket validation fails
        FileNotFoundError: If issue tracker client is not available
    """
    try:
        issue_tracker_client = create_issue_tracker_client(timeout=10)
        ticket = issue_tracker_client.get_ticket(issue_key)
        return ticket

    except JiraNotFoundError as e:
        raise RuntimeError(f"issue tracker ticket {issue_key} not found")
    except JiraAuthError as e:
        raise RuntimeError(f"Authentication failed: {e}")
    except JiraApiError as e:
        raise RuntimeError(f"JIRA API error: {e}")
    except JiraConnectionError as e:
        raise RuntimeError(f"Connection error: {e}")
    except FileNotFoundError:
        raise
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Timeout validating issue tracker ticket {issue_key}")


@require_outside_claude
def link_jira(
    name: str,
    issue_key: str,
    force: bool = False,
) -> None:
    """Link a issue tracker ticket to a session group.

    Args:
        name: Session group name
        issue_key: issue tracker key to link
        force: Skip confirmation prompts
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Fetch JIRA metadata (validates ticket exists)
    try:
        console_print(f"\n[cyan]Fetching issue tracker ticket {issue_key}...[/cyan]")
        issue_metadata_dict = _fetch_issue_metadata_dict(issue_key)
        console_print(f"[green]✓[/green] issue tracker ticket {issue_key} exists")
        console_print(f"[dim]Status: {issue_metadata_dict.get('status')}, Type: {issue_metadata_dict.get('type')}[/dim]")
    except RuntimeError as e:
        if is_json_mode():
            output_json(success=False, error={"code": "VALIDATION_ERROR", "message": str(e)})
        else:
            console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    # Get all sessions in the group
    sessions = session_manager.index.get_sessions(name)

    if not sessions:
        if is_json_mode():
            output_json(success=False, error={"code": "NOT_FOUND", "message": f"Session group '{name}' not found"})
        else:
            console.print(f"[red]✗[/red] Session group '{name}' not found")
        sys.exit(1)

    # Check if any session already has a issue key
    existing_jira = None
    for session in sessions:
        if session.issue_key and session.issue_key != issue_key:
            existing_jira = session.issue_key
            break

    if existing_jira:
        # In JSON mode or with --force, automatically replace without prompting
        if not force and not is_json_mode():
            console.print(f"[yellow]⚠[/yellow] Session group '{name}' is already linked to {existing_jira}")
            if not Confirm.ask(f"Replace {existing_jira} with {issue_key}?", default=False):
                console.print("[dim]Link operation cancelled[/dim]")
                if is_json_mode():
                    output_json(success=False, error={"code": "CANCELLED", "message": "Link operation cancelled by user"})
                sys.exit(0)
        else:
            console_print(f"[yellow]⚠[/yellow] Replacing existing link {existing_jira} with {issue_key}")


    # Update all sessions in the group
    for session in sessions:
        session.issue_key = issue_key

        # Copy ALL fields from issue_metadata_dict to issue_metadata (generic approach)
        # Exclude the 'key' and 'updated' fields (already stored separately)
        session.issue_metadata = {k: v for k, v in issue_metadata_dict.items() if k not in ('key', 'updated') and v is not None}

        # Update goal to concatenated format: "{ISSUE_KEY}: {JIRA_TITLE}"
        issue_summary = issue_metadata_dict.get("summary")
        if issue_summary:
            session.goal = f"{issue_key}: {issue_summary}"
        else:
            # If no summary, just use the issue key
            session.goal = issue_key

        session_manager.update_session(session)

    if is_json_mode():
        output_json(
            success=True,
            data={
                "session_group": name,
                "issue_key": issue_key,
                "sessions_updated": len(sessions),
                "replaced": existing_jira,
                "metadata": issue_metadata_dict
            }
        )
    else:
        console.print(f"[green]✓[/green] Linked session group '{name}' to {issue_key}")
        console.print(f"[dim]All {len(sessions)} session(s) in group now associated with {issue_key}[/dim]")
        console.print()
        console.print(f"[dim]You can now use either identifier:[/dim]")
        console.print(f"  daf open {name}")
        console.print(f"  daf open {issue_key}")


@require_outside_claude
def unlink_jira(name: str, force: bool = False) -> None:
    """Remove JIRA association from a session group.

    Args:
        name: Session group name or issue key
        force: Skip confirmation prompts
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Get all sessions (could be by name or issue key)
    sessions = session_manager.index.get_sessions(name)

    if not sessions:
        if is_json_mode():
            output_json(success=False, error={"code": "NOT_FOUND", "message": f"Session group '{name}' not found"})
        else:
            console.print(f"[red]✗[/red] Session group '{name}' not found")
        sys.exit(1)

    # Check if any session has a issue key
    has_jira = any(session.issue_key for session in sessions)

    if not has_jira:
        if is_json_mode():
            output_json(success=False, error={"code": "NO_JIRA", "message": f"Session group '{sessions[0].name}' has no JIRA association"})
        else:
            console.print(f"[yellow]⚠[/yellow] Session group '{sessions[0].name}' has no JIRA association")
        sys.exit(0)

    issue_key= sessions[0].issue_key
    group_name = sessions[0].name

    # Confirm removal (skip if force or JSON mode)
    if not force and not is_json_mode():
        if not Confirm.ask(f"Remove JIRA association ({issue_key}) from '{group_name}'?", default=True):
            if is_json_mode():
                output_json(success=False, error={"code": "CANCELLED", "message": "Unlink operation cancelled by user"})
            else:
                console.print("[dim]Unlink operation cancelled[/dim]")
            sys.exit(0)

    # Update all sessions in the group
    for session in sessions:
        session.issue_key = None
        # Clear JIRA metadata
        session.issue_metadata = {}
        session_manager.update_session(session)

    if is_json_mode():
        output_json(
            success=True,
            data={
                "session_group": group_name,
                "previous_issue_key": issue_key,
                "sessions_updated": len(sessions)
            }
        )
    else:
        console.print(f"[green]✓[/green] Removed JIRA association from session group '{group_name}'")
        console.print(f"[dim]All {len(sessions)} session(s) in group are now JIRA-free[/dim]")
        console.print()
        console.print(f"[dim]Access with:[/dim]")
        console.print(f"  daf open {group_name}")
