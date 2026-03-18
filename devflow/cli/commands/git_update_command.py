"""Implementation of 'daf git update' command."""

import sys
from typing import Optional
from rich.console import Console

from devflow.cli.utils import output_json as json_output, console_print
from devflow.issue_tracker.factory import create_issue_tracker_client
from devflow.utils.git_remote import GitRemoteDetector
from devflow.issue_tracker.exceptions import (
    IssueTrackerError,
    IssueTrackerAuthError,
    IssueTrackerApiError,
    IssueTrackerNotFoundError,
)

console = Console()


def git_update(
    issue_key: str,
    state: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    labels: Optional[str] = None,
    assignee: Optional[str] = None,
    milestone: Optional[str] = None,
    parent: Optional[str] = None,
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
        parent: Link to parent issue (owner/repo#123 or #123)
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

    # Handle parent separately (not part of standard payload)
    parent_to_link = None
    if parent:
        parent_to_link = parent

    if not payload and not parent_to_link:
        console.print("[yellow]⚠[/yellow] No fields to update")
        console.print("[dim]Specify at least one option: --state, --title, --description, --labels, --assignee, --milestone, or --parent[/dim]")
        sys.exit(1)

    try:
        # Detect platform from repository or git remote
        detector = GitRemoteDetector()
        platform_info = detector.parse_repository_info()

        # Extract hostname for enterprise GitLab/GitHub instances
        hostname = detector.get_hostname()

        if platform_info:
            platform, owner, repo_name = platform_info
            backend = "gitlab" if platform == "gitlab" else "github"
            if not repository:
                repository = f"{owner}/{repo_name}"
        else:
            # Default to GitHub if can't detect
            backend = "github"

        # Create appropriate client (automatically returns mock in mock mode)
        client = create_issue_tracker_client(backend=backend, hostname=hostname)

        # Set repository if we have one
        if repository and hasattr(client, 'repository'):
            client.repository = repository

        # Validate parent issue exists if provided
        if parent_to_link:
            from devflow.issue_tracker.exceptions import IssueTrackerValidationError
            console_print(f"\n[cyan]Validating parent issue {parent_to_link}...[/cyan]")
            try:
                parent_issue = client.get_ticket(parent_to_link)
                if not parent_issue:
                    console.print(f"[red]✗[/red] Parent issue {parent_to_link} not found")
                    if output_json:
                        json_output(success=False, error={"message": f"Parent issue {parent_to_link} not found", "code": "PARENT_NOT_FOUND"})
                    sys.exit(1)
                console_print(f"[dim]Parent issue found: {parent_issue.get('summary', 'N/A')}[/dim]")
            except IssueTrackerValidationError as e:
                console.print(f"[red]✗[/red] Invalid parent issue key format: {parent_to_link}")
                console.print(f"[dim]Expected '#123' or 'owner/repo#123'[/dim]")
                if output_json:
                    json_output(success=False, error={"message": str(e), "code": "INVALID_PARENT_FORMAT"})
                sys.exit(1)
            except IssueTrackerNotFoundError:
                console.print(f"[red]✗[/red] Parent issue {parent_to_link} not found")
                if output_json:
                    json_output(success=False, error={"message": f"Parent issue {parent_to_link} not found", "code": "PARENT_NOT_FOUND"})
                sys.exit(1)

        # Update issue
        if not output_json:
            console_print(f"[cyan]Updating issue {issue_key}...[/cyan]")

        if payload:
            client.update_issue(issue_key, payload)

        # Link to parent if specified
        if parent_to_link:
            try:
                # Parse parent to get full repository info
                parent_repo, parent_number = client._parse_issue_number(parent_to_link)
                parent_repo = client._get_repository(parent_repo)

                # Add comment to child issue mentioning parent
                client.add_comment(
                    issue_key,
                    f"Child of {parent_repo}#{parent_number}",
                    public=True
                )

                # Add comment to parent issue mentioning child
                client.add_comment(
                    parent_to_link,
                    f"Sub-issue linked: {issue_key}",
                    public=True
                )
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Could not link to parent: {e}")

        # JSON output mode
        if output_json:
            result_data = {"issue_key": issue_key}
            if payload:
                result_data["updated_fields"] = payload
            if parent_to_link:
                result_data["parent"] = parent_to_link
            json_output(success=True, data=result_data)
            return

        # Console output mode
        console_print(f"[green]✓[/green] Updated issue {issue_key}")

        # Show what was updated
        if payload:
            console.print("\n[dim]Updated fields:[/dim]")
            for field, value in payload.items():
                if field == 'assignees':
                    value = ', '.join([f"@{u}" for u in value])
                elif field == 'labels':
                    value = ', '.join(value)
                console.print(f"  {field}: {value}")

        if parent_to_link:
            console.print(f"\n[dim]Linked to parent: {parent_to_link}[/dim]")

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
