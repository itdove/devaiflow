"""Implementation of 'daf git update' command."""

import sys
from typing import Optional
from rich.console import Console

from devflow.cli.utils import output_json as json_output, console_print, require_outside_claude
from devflow.github.issues_client import GitHubClient
from devflow.issue_tracker.exceptions import (
    IssueTrackerError,
    IssueTrackerAuthError,
    IssueTrackerApiError,
    IssueTrackerNotFoundError,
)

console = Console()


@require_outside_claude
def git_update(
    issue_key: str,
    state: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    labels: Optional[str] = None,
    assignee: Optional[str] = None,
    milestone: Optional[str] = None,
    repository: Optional[str] = None,
    output_json: bool = False,
) -> None:
    """Update a GitHub/GitLab issue.

    Args:
        issue_key: Issue key (#123 or owner/repo#123)
        state: New state (open, closed)
        title: New title
        description: New description
        labels: New labels (comma-separated, replaces all labels)
        assignee: Assign to username
        milestone: Set milestone
        repository: Repository in owner/repo format (optional, will auto-detect)
        output_json: Output in JSON format
    """
    # Build update payload
    payload = {}

    if state:
        state_lower = state.lower()
        if state_lower not in ['open', 'closed']:
            console.print(f"[red]✗[/red] Invalid state: {state}")
            console.print(f"[dim]Valid states: open, closed[/dim]")
            sys.exit(1)
        payload['state'] = state_lower

    if title:
        payload['title'] = title

    if description:
        payload['body'] = description

    if labels is not None:
        label_list = [label.strip() for label in labels.split(',') if label.strip()]
        payload['labels'] = label_list

    if assignee:
        payload['assignees'] = [assignee]

    if milestone:
        payload['milestone'] = milestone

    if not payload:
        console.print("[yellow]⚠[/yellow] No fields to update")
        console.print("[dim]Specify at least one option: --state, --title, --description, --labels, --assignee, or --milestone[/dim]")
        sys.exit(1)

    try:
        # Create client (automatically returns mock in mock mode)
        client = GitHubClient(repository=repository)

        # Update issue
        if not output_json:
            console_print(f"[cyan]Updating issue {issue_key}...[/cyan]")

        client.update_issue(issue_key, payload)

        # JSON output mode
        if output_json:
            json_output(success=True, data={"issue_key": issue_key, "updated_fields": payload})
            return

        # Console output mode
        console_print(f"[green]✓[/green] Updated issue {issue_key}")

        # Show what was updated
        console.print("\n[dim]Updated fields:[/dim]")
        for field, value in payload.items():
            if field == 'assignees':
                value = ', '.join([f"@{u}" for u in value])
            elif field == 'labels':
                value = ', '.join(value)
            console.print(f"  {field}: {value}")

    except IssueTrackerNotFoundError as e:
        console.print(f"[red]✗[/red] Issue not found: {issue_key}")
        if output_json:
            json_output(success=False, error=str(e))
        sys.exit(1)
    except IssueTrackerAuthError as e:
        console.print(f"[red]✗[/red] Authentication failed")
        console.print(f"[dim]Run 'gh auth login' or 'glab auth login' to authenticate[/dim]")
        if output_json:
            json_output(success=False, error=str(e))
        sys.exit(1)
    except IssueTrackerApiError as e:
        console.print(f"[red]✗[/red] API error: {e}")
        if output_json:
            json_output(success=False, error=str(e))
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        if output_json:
            json_output(success=False, error=str(e))
        sys.exit(1)
