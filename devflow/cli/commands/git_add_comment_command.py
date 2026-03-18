"""Implementation of 'daf git add-comment' command."""

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


def git_add_comment(
    issue_key: str,
    comment: str,
    repository: Optional[str] = None,
    output_json: bool = False,
) -> None:
    """Add a comment to a GitHub/GitLab issue.

    Args:
        issue_key: Issue key (#123 or owner/repo#123)
        comment: Comment text
        repository: Repository in owner/repo format (optional, will auto-detect)
        output_json: Output in JSON format
    """
    if not comment or not comment.strip():
        console.print("[red]✗[/red] Comment text is required")
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

        # Add comment
        console_print(f"[cyan]Adding comment to {issue_key}...[/cyan]")
        client.add_comment(issue_key, comment, public=True)

        console_print(f"[green]✓[/green] Comment added to {issue_key}")

        # JSON output mode
        if output_json:
            json_output(success=True, data={"issue_key": issue_key})
            return

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
