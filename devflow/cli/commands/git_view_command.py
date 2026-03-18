"""Implementation of 'daf git view' command."""

import sys
from typing import Dict, Optional
from rich.console import Console

from devflow.cli.utils import output_json as json_output
from devflow.issue_tracker.factory import create_issue_tracker_client
from devflow.issue_tracker.exceptions import (
    IssueTrackerError,
    IssueTrackerAuthError,
    IssueTrackerApiError,
    IssueTrackerNotFoundError,
)
from devflow.utils.git_remote import GitRemoteDetector

console = Console()


def format_issue_for_claude(issue_data: dict) -> str:
    """Format GitHub issue data in a Claude-friendly text format.

    Args:
        issue_data: Dictionary with issue data from GitHubClient.get_ticket()

    Returns:
        Formatted string suitable for Claude to read
    """
    lines = []

    # Header - required fields
    lines.append(f"Issue: {issue_data['key']}")
    lines.append(f"Title: {issue_data['summary']}")
    lines.append(f"State: {issue_data['status']}")

    # Type, priority, points from labels
    if issue_data.get('type'):
        lines.append(f"Type: {issue_data['type']} (from labels)")

    if issue_data.get('priority'):
        lines.append(f"Priority: {issue_data['priority']} (from labels)")

    if issue_data.get('points'):
        lines.append(f"Points: {issue_data['points']} (from labels)")

    # Optional metadata
    if issue_data.get('assignee'):
        lines.append(f"Assignee: @{issue_data['assignee']}")

    if issue_data.get('milestone'):
        lines.append(f"Milestone: {issue_data['milestone']}")

    if issue_data.get('sprint'):
        lines.append(f"Sprint: {issue_data['sprint']}")

    # Description
    if issue_data.get('description'):
        lines.append("")
        lines.append("Description:")
        lines.append(issue_data['description'])

    # Acceptance criteria (if present)
    if issue_data.get('acceptance_criteria'):
        lines.append("")
        lines.append("Acceptance Criteria:")
        for criterion in issue_data['acceptance_criteria']:
            lines.append(f"- {criterion}")

    # Labels
    if issue_data.get('labels'):
        labels = issue_data['labels']
        if labels:
            lines.append("")
            lines.append(f"Labels: {', '.join(labels)}")

    # PR links
    if issue_data.get('pr_links'):
        lines.append("")
        lines.append("Pull Requests:")
        lines.append(issue_data['pr_links'])

    return "\n".join(lines)


def format_comments_for_claude(comments: list) -> str:
    """Format GitHub issue comments in a Claude-friendly text format.

    Args:
        comments: List of comment dicts with 'author', 'body', 'created' keys

    Returns:
        Formatted string
    """
    if not comments:
        return "No comments."

    lines = []
    for comment in comments:
        author = comment.get('author', 'Unknown')
        created = comment.get('created', '')
        body = comment.get('body', '')

        lines.append(f"\n--- Comment by {author} ({created}) ---")
        lines.append(body)

    return "\n".join(lines)


def git_view(
    issue_key: Optional[str] = None,
    comments: bool = False,
    repository: Optional[str] = None,
    output_json: bool = False,
) -> None:
    """View a GitHub/GitLab issue in Claude-friendly format.

    Args:
        issue_key: GitHub issue key (#123 or owner/repo#123). If None, uses current session.
        comments: If True, include comments
        repository: Repository in owner/repo format (optional, will auto-detect)
        output_json: If True, output in JSON format
    """
    # Auto-detect issue key from current session if not provided
    if not issue_key:
        from devflow.config.loader import ConfigLoader
        from devflow.session.manager import SessionManager
        from devflow.session.capture import SessionCapture

        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader)
        capture = SessionCapture()

        # Get current session from environment
        current_session_id = capture.get_current_session_id()
        if not current_session_id:
            console.print("[red]✗[/red] Not in a DevAIFlow session")
            console.print("[dim]Run this command from within a Claude Code session opened via 'daf open'[/dim]")
            console.print("[dim]Or provide an issue key: daf git view 123[/dim]")
            sys.exit(1)

        # Get session from ID
        sessions = session_manager.index.list_sessions()
        session = next((s for s in sessions if str(s.session_id) == current_session_id), None)

        if not session or not session.issue_key:
            console.print("[red]✗[/red] Current session has no GitHub/GitLab issue associated")
            console.print("[dim]Provide an issue key: daf git view 123[/dim]")
            sys.exit(1)

        issue_key = session.issue_key
        console.print(f"[dim]Using issue from current session: {issue_key}[/dim]\n")

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

        # Fetch issue
        if comments:
            issue_data = client.get_ticket_detailed(issue_key, include_changelog=True)
        else:
            issue_data = client.get_ticket(issue_key)

        # JSON output mode
        if output_json:
            json_output(success=True, data=issue_data)
            return

        # Format for Claude
        formatted = format_issue_for_claude(issue_data)
        console.print(formatted)

        # Show comments if requested
        if comments and issue_data.get('comments'):
            console.print("\n" + "=" * 60)
            console.print("COMMENTS")
            console.print("=" * 60)
            formatted_comments = format_comments_for_claude(issue_data['comments'])
            console.print(formatted_comments)

    except IssueTrackerNotFoundError as e:
        console.print(f"[red]✗[/red] Issue not found: {issue_key}")
        if output_json:
            json_output(success=False, error=str(e))
        sys.exit(1)
    except IssueTrackerAuthError as e:
        console.print(f"[red]✗[/red] Authentication failed")
        console.print(f"[dim]Run 'gh auth login' (GitHub) or 'glab auth login' (GitLab) to authenticate[/dim]")
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
