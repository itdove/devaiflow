"""Command for daf git open - open or create session from GitHub/GitLab issue."""

from pathlib import Path
from typing import Optional
from rich.console import Console

from devflow.cli.utils import console_print, require_outside_claude, is_json_mode, output_json
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.issue_tracker.factory import create_issue_tracker_client
from devflow.utils.git_remote import GitRemoteDetector
from devflow.issue_tracker.exceptions import IssueTrackerNotFoundError, IssueTrackerAuthError, IssueTrackerApiError

console = Console()


@require_outside_claude
def git_open_session(
    issue_key: str,
    repository: Optional[str] = None,
) -> None:
    """Open session for GitHub/GitLab issue, creating it if needed.

    This command validates that the issue exists, then either:
    1. Opens the existing session if one exists for this issue
    2. Creates a new session if no session exists

    Args:
        issue_key: Issue key (#123 or owner/repo#123)
        repository: Repository in owner/repo format (optional, will auto-detect)
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console_print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        if is_json_mode():
            output_json(success=False, error={"message": "No configuration found", "code": "NO_CONFIG"})
        return

    session_manager = SessionManager(config_loader=config_loader)

    # Check if session already exists
    # For GitHub/GitLab, issue_key format is #123 or owner/repo#123
    # Normalize to just the number for session name matching
    import re
    number_match = re.search(r'#?(\d+)$', issue_key)
    if not number_match:
        console_print(f"[red]✗[/red] Invalid issue key format: {issue_key}")
        console_print(f"[dim]Expected: #123 or owner/repo#123[/dim]")
        return

    issue_number = number_match.group(1)

    # Search for existing sessions with this issue key
    all_sessions = session_manager.index.list_sessions()
    matching_sessions = [
        s for s in all_sessions
        if s.issue_key and issue_number in s.issue_key
    ]

    if matching_sessions:
        # Found existing session - open it
        session = matching_sessions[0]
        console_print(f"[green]✓[/green] Found existing session: [cyan]{session.name}[/cyan]")
        console_print(f"[dim]Session type: {session.session_type}, status: {session.status}[/dim]")

        from devflow.cli.commands.open_command import open_session
        open_session(session.name)
        return

    # No session found - validate issue exists
    console_print(f"[dim]No existing session found, validating issue...[/dim]")

    try:
        # Detect platform from repository or git remote
        detector = GitRemoteDetector()
        platform_info = detector.parse_repository_info()

        if platform_info:
            platform, owner, repo_name = platform_info
            backend = "gitlab" if platform == "gitlab" else "github"
            if not repository:
                repository = f"{owner}/{repo_name}"
        else:
            # Default to GitHub if can't detect
            backend = "github"

        # Create appropriate client (automatically returns mock in mock mode)
        client = create_issue_tracker_client(backend=backend)

        # Set repository if we have one
        if repository and hasattr(client, 'repository'):
            client.repository = repository

        issue = client.get_ticket(issue_key)
    except IssueTrackerNotFoundError:
        console_print(f"[red]✗[/red] Issue not found: {issue_key}")
        if is_json_mode():
            output_json(success=False, error={"message": f"Issue {issue_key} not found", "code": "ISSUE_NOT_FOUND"})
        return
    except IssueTrackerAuthError as e:
        console_print(f"[red]✗[/red] Authentication failed")
        console_print(f"[dim]Run 'gh auth login' or 'glab auth login' to authenticate[/dim]")
        if is_json_mode():
            output_json(success=False, error={"message": str(e), "code": "AUTH_ERROR"})
        return
    except IssueTrackerApiError as e:
        console_print(f"[red]✗[/red] API error: {e}")
        if is_json_mode():
            output_json(success=False, error={"message": str(e), "code": "API_ERROR"})
        return
    except Exception as e:
        console_print(f"[red]✗[/red] Unexpected error: {e}")
        if is_json_mode():
            output_json(success=False, error={"message": str(e), "code": "UNEXPECTED_ERROR"})
        return

    # Create session from issue
    # Use normalized issue key from the fetched issue
    normalized_key = issue['key']

    # Convert to dash-separated session name (remove # and / for bash compatibility)
    # Example: "owner/repo#123" -> "owner-repo-123"
    from devflow.cli.commands.sync_command import issue_key_to_session_name
    session_name = issue_key_to_session_name(normalized_key)

    goal = f"{normalized_key}: {issue['summary']}"

    console_print(f"[green]✓[/green] Issue validated: [bold]{normalized_key}[/bold]")
    console_print(f"[dim]Creating session: {session_name}[/dim]")

    # Determine project path
    project_path = str(Path.cwd())
    working_directory = Path(project_path).name

    # Create session with issue metadata
    session = session_manager.create_session(
        name=session_name,
        goal=goal,
        working_directory=working_directory,
        project_path=project_path,
        branch=None,  # Will be set when user starts working
    )

    # Set session_type to "development"
    session.session_type = "development"

    # Set issue tracker backend and metadata
    # Auto-detect backend from repository
    from devflow.utils.git_remote import GitRemoteDetector
    detector = GitRemoteDetector(project_path)
    repo_info = detector.parse_repository_info()

    if repo_info:
        backend = repo_info[0]  # 'github' or 'gitlab'
        session.issue_tracker = backend
    else:
        # Fallback to github if can't detect
        session.issue_tracker = "github"

    session.issue_key = normalized_key

    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["summary"] = issue.get('summary')
    session.issue_metadata["type"] = issue.get('type')
    session.issue_metadata["status"] = issue.get('status')

    # Add conversation metadata
    from devflow.git.utils import GitUtils

    current_branch = GitUtils.get_current_branch(Path(project_path)) if GitUtils.is_git_repository(Path(project_path)) else None

    session.add_conversation(
        working_dir=working_directory,
        project_path=project_path,
        ai_agent_session_id="",  # Will be generated on first launch
        branch=current_branch,
    )

    # Save session
    session_manager.update_session(session)

    console_print(f"[green]✓[/green] Session created: [cyan]{session.name}[/cyan]")
    console_print(f"[dim]Opening session...[/dim]\n")

    # Open the session
    from devflow.cli.commands.open_command import open_session
    open_session(session.name)
