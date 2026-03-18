"""Implementation of 'daf sync' command."""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.table import Table

from devflow.cli.utils import output_json as json_output, require_outside_claude, serialize_session, console_print
from devflow.config.loader import ConfigLoader
from devflow.jira import JiraClient
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError
from devflow.issue_tracker.factory import create_issue_tracker_client
from devflow.issue_tracker.exceptions import IssueTrackerError, IssueTrackerAuthError, IssueTrackerApiError
from devflow.utils.git_remote import GitRemoteDetector
from devflow.session.manager import SessionManager

console = Console()


def render_sync_recap_table(synced_tickets: List[Dict[str, str]]) -> None:
    """Render a recap table showing all synced tickets.

    Args:
        synced_tickets: List of dictionaries with keys:
            - session_name: Session name (what users use with 'daf open')
            - title: Issue title/summary (will be truncated if too long)
            - action: "CREATED" or "UPDATED"
            - backend: "JIRA", "GitHub", or "GitLab"
    """
    if not synced_tickets:
        return

    # Create Rich Table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Session Name", style="cyan", no_wrap=True)
    table.add_column("Title", style="white", no_wrap=True)
    table.add_column("Action", style="green", no_wrap=True)
    table.add_column("Backend", style="blue", no_wrap=True)

    # Add rows
    for ticket in synced_tickets:
        session_name = ticket["session_name"]
        title = ticket["title"]
        action = ticket["action"]
        backend = ticket["backend"]

        # Truncate long titles to fit nicely in the table
        # Rich will apply ellipsis automatically due to overflow setting
        if len(title) > 60:
            title = title[:57] + "..."

        # Color action based on type
        if action == "CREATED":
            action_display = f"[green]{action}[/green]"
        else:  # UPDATED
            action_display = f"[cyan]{action}[/cyan]"

        table.add_row(session_name, title, action_display, backend)

    # Render the table
    console.print()
    console.print("[bold]Synced tickets:[/bold]")
    console.print(table)


def get_workspace_from_creation_session(
    session_manager: SessionManager,
    issue_key: str,
) -> Optional[str]:
    """Get workspace from creation session if it exists.

    Args:
        session_manager: SessionManager instance
        issue_key: Issue key (e.g., "PROJ-12345" for JIRA, "owner/repo#123" for GitHub)

    Returns:
        workspace_name from creation session if found, None otherwise

    This function looks for a creation session (session_type == "ticket_creation")
    that matches the pattern "creation-{issue_key}" or "creation-{session_name}"
    and returns its workspace_name if set.
    """
    # For JIRA: creation-PROJ-12345
    # For GitHub: creation-owner-repo-123 (convert issue key to session name first)
    creation_session_name = f"creation-{issue_key}"

    # Try direct lookup first (JIRA case)
    creation_session = session_manager.get_session(creation_session_name)

    # If not found and issue_key contains # or /, it's a GitHub/GitLab issue
    # Convert to session name format and try again
    if not creation_session and ("#" in issue_key or "/" in issue_key):
        # Convert GitHub issue key to session name format
        session_name = issue_key_to_session_name(issue_key)
        creation_session_name = f"creation-{session_name}"
        creation_session = session_manager.get_session(creation_session_name)

    # Validate: must be ticket_creation type and have workspace_name set
    if creation_session:
        if creation_session.session_type == "ticket_creation" and creation_session.workspace_name:
            return creation_session.workspace_name

    return None


def issue_key_to_session_name(issue_key: str, hostname: Optional[str] = None) -> str:
    """Convert GitHub/GitLab issue key to dash-separated session name.

    Removes bash-problematic characters (# and /) to ensure session names
    work safely in shell commands and scripts.

    Args:
        issue_key: Issue key in format "owner/repo#123" or "#123"
        hostname: Optional hostname (e.g., "github.com", "github.enterprise.com")
                  If github.com (default), hostname is omitted from session name.
                  For self-hosted instances, hostname is included for uniqueness.

    Returns:
        Dash-separated session name safe for bash usage

    Examples:
        >>> issue_key_to_session_name("itdove/devaiflow#60")
        'itdove-devaiflow-60'
        >>> issue_key_to_session_name("itdove/devaiflow#60", "github.com")
        'itdove-devaiflow-60'
        >>> issue_key_to_session_name("itdove/devaiflow#60", "github.enterprise.com")
        'github-enterprise-com-itdove-devaiflow-60'
    """
    # Replace bash-problematic characters: / and # with -
    base_name = issue_key.replace('/', '-').replace('#', '-').lstrip('-')

    if hostname and hostname != 'github.com':
        # Include hostname for non-default GitHub instances (GitHub Enterprise, etc.)
        hostname_part = hostname.replace('.', '-')
        return f"{hostname_part}-{base_name}"

    return base_name


@require_outside_claude
def sync_jira(
    field_filters: Optional[Dict[str, str]] = None,
    ticket_type: Optional[str] = None,
    epic: Optional[str] = None,
    output_json: bool = False,
) -> None:
    """Sync with JIRA to import assigned tickets as sessions.

    Fetches issue tracker tickets assigned to you and creates session groups for tickets
    that don't already have sessions.

    Filter criteria (from config):
    - Status: New, To Do, or In Progress (configurable)
    - Required fields: Configurable in organization.json

    Args:
        field_filters: Filter by custom fields (e.g., {"sprint": "Sprint 1", "severity": "Critical"})
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
        console.print("[dim]Check $DEVAIFLOW_HOME/config.json for sync filter configuration[/dim]")
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
            ticket_type=ticket_type,
            field_mappings=config.jira.field_mappings,
            field_filters=field_filters,
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

    # Filter by type-specific required fields
    filtered_tickets = []
    for ticket in tickets:
        # Get issue type for this ticket
        # Note: JiraClient.list_tickets() returns issue type in "type" field
        issue_type = ticket.get("type")

        if not issue_type:
            console_print(f"[dim]Skipping {ticket['key']}: No issue type found[/dim]")
            continue

        # Get required fields for this issue type
        required_fields = sync_filters.get_required_fields_for_type(issue_type)

        # Check if ticket has all required fields for its type
        skip_ticket = False
        for field in required_fields:
            if not ticket.get(field):
                console_print(f"[dim]Skipping {ticket['key']} ({issue_type}): Missing required field '{field}'[/dim]")
                skip_ticket = True
                break

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
    synced_tickets: List[Dict[str, str]] = []  # Track all synced tickets for recap

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

            # Copy ALL fields from ticket to issue_metadata (generic approach)
            # Exclude the 'key' and 'updated' fields (already stored separately)
            session.issue_metadata = {k: v for k, v in ticket.items() if k not in ('key', 'updated') and v is not None}

            # Auto-inherit workspace from creation session (itdove/devaiflow#131)
            # If user created ticket with `daf jira new --workspace X`, inherit workspace X
            inherited_workspace = get_workspace_from_creation_session(session_manager, issue_key)
            if inherited_workspace:
                session.workspace_name = inherited_workspace

            session_manager.update_session(session)
            created_count += 1

            # Track for JSON output
            if output_json:
                created_sessions.append(serialize_session(session))

            # Track for recap table
            synced_tickets.append({
                "session_name": issue_key,  # For JIRA, session name == issue key
                "title": issue_summary or issue_key,
                "action": "CREATED",
                "backend": "JIRA"
            })

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

                    # Copy ALL fields from ticket to issue_metadata (generic approach)
                    # Exclude the 'key' and 'updated' fields (already stored separately)
                    session.issue_metadata = {k: v for k, v in ticket.items() if k not in ('key', 'updated') and v is not None}

                    session_manager.update_session(session)
                    updated_count += 1

                    # Track for JSON output
                    if output_json:
                        updated_sessions.append(serialize_session(session))

                    # Track for recap table
                    issue_summary = ticket.get("summary", issue_key)
                    synced_tickets.append({
                        "session_name": issue_key,  # For JIRA, session name == issue key
                        "title": issue_summary,
                        "action": "UPDATED",
                        "backend": "JIRA"
                    })

                    console_print(f"[cyan]↻[/cyan] Updated session: {issue_key}")
                else:
                    console_print(f"[dim]  Skipped (no changes): {issue_key}[/dim]")

    # JSON output mode
    if output_json:
        filters_metadata = {
            "assignee": sync_filters.assignee,
            "status": sync_filters.status if sync_filters.status else None,
            "ticket_type": ticket_type,
        }

        # Add field_filters if provided
        if field_filters:
            filters_metadata["field_filters"] = field_filters

        # Add epic if provided
        if epic:
            filters_metadata["epic"] = epic

        json_output(
            success=True,
            data={
                "created_sessions": created_sessions,
                "updated_sessions": updated_sessions,
                "created_count": created_count,
                "updated_count": updated_count,
            },
            metadata={
                "filters": filters_metadata
            }
        )
        return

    # Render recap table if there are synced tickets
    render_sync_recap_table(synced_tickets)

    console_print()
    console_print("[bold]Sync complete[/bold]")
    console_print(f"[green]Created:[/green] {created_count} new sessions")
    console_print(f"[cyan]Updated:[/cyan] {updated_count} existing sessions")
    console_print()
    console_print(f"[dim]Use 'daf list' to see all sessions[/dim]")
    console_print(f"[dim]Use 'daf open <JIRA-KEY>' to start work[/dim]")


def scan_workspace_for_repositories(workspace_path: str) -> List[Dict[str, str]]:
    """Scan workspace directory for git repositories.

    Args:
        workspace_path: Path to workspace directory

    Returns:
        List of repository info dictionaries with keys:
        - path: Absolute path to repository
        - remote: Remote name used (upstream or origin)
        - url: Git remote URL
        - backend: Platform (github, gitlab)
        - repository: owner/repo format
    """
    repositories = []
    workspace_path = Path(workspace_path).expanduser().resolve()

    if not workspace_path.exists():
        return repositories

    # Find all .git directories (repositories)
    for root, dirs, files in os.walk(workspace_path):
        if '.git' in dirs:
            repo_path = root
            detector = GitRemoteDetector(repo_path)

            # Try to parse repository info
            info = detector.parse_repository_info()
            if info:
                platform, owner, repo = info

                # Get which remote was used (upstream or origin)
                remote_url = detector.get_remote_url()
                remote_name = None
                if remote_url:
                    # Check which remote this URL came from
                    upstream_url = detector.get_remote_url('upstream')
                    if upstream_url == remote_url:
                        remote_name = 'upstream'
                    else:
                        remote_name = 'origin'

                repositories.append({
                    'path': repo_path,
                    'remote': remote_name or 'origin',
                    'url': remote_url or '',
                    'backend': platform,
                    'repository': f"{owner}/{repo}"
                })

            # Don't descend into .git or node_modules
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '.venv', 'venv', '__pycache__'}]

    return repositories


def sync_github_repository(
    repository: str,
    session_manager: SessionManager,
    config: Any,
    repository_url: Optional[str] = None,
    output_json: bool = False,
    synced_tickets: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, int]:
    """Sync issues from a GitHub repository.

    Args:
        repository: Repository in owner/repo format
        session_manager: Session manager instance
        config: Configuration object
        repository_url: Optional Git remote URL (to extract hostname for uniqueness)
        output_json: Whether to output JSON
        synced_tickets: Optional list to track synced tickets for recap table

    Returns:
        Dictionary with created_count and updated_count
    """
    created_count = 0
    updated_count = 0

    try:
        # Extract hostname from repository URL for uniqueness
        # Example: https://github.com/owner/repo.git → github.com
        # Example: https://github.enterprise.com/owner/repo.git → github.enterprise.com
        hostname = 'github.com'  # Default
        if repository_url:
            import re
            # Match both HTTPS and SSH URLs
            https_match = re.match(r'https?://([^/]+)/', repository_url)
            ssh_match = re.match(r'git@([^:]+):', repository_url)
            if https_match:
                hostname = https_match.group(1)
            elif ssh_match:
                hostname = ssh_match.group(1)

        # Create GitHub client
        from devflow.github.issues_client import GitHubClient
        client = GitHubClient(repository=repository)

        # Get current GitHub username
        import subprocess
        try:
            result = subprocess.run(
                ['gh', 'api', 'user', '--jq', '.login'],
                capture_output=True,
                text=True,
                timeout=10,
            )
            username = result.stdout.strip()
            if not username:
                raise ValueError("Empty username from gh api")

            # Debug: Show detected username (only once)
            if repository == 'itdove/devaiflow':
                console_print(f"[dim]  Detected GitHub user: {username}[/dim]")
        except Exception as e:
            username = '@me'  # Fallback to @me
            # Debug: Show fallback
            if repository == 'itdove/devaiflow':
                console_print(f"[dim]  Username detection failed ({e}), using @me[/dim]")

        # Fetch issues assigned to current user
        tickets = client.list_tickets(
            project=repository,
            assignee=username,  # Use actual username instead of @me
            status=['open'],  # Only open issues
            max_results=100,
        )

        if not tickets:
            console_print(f"[dim]  No issues found in {repository}[/dim]")
            return {'created_count': 0, 'updated_count': 0}

        console_print(f"[dim]  Found {len(tickets)} issues in {repository}[/dim]")

        for ticket in tickets:
            issue_key = ticket['key']  # Format: owner/repo#123

            # Convert issue key to dash-separated session name
            # Example: "itdove/devaiflow#60" → "itdove-devaiflow-60"
            # Example: "github.enterprise.com/owner/repo#60" → "github-enterprise-com-itdove-devaiflow-60"
            session_name = issue_key_to_session_name(issue_key, hostname=hostname)

            # Check if session already exists
            all_sessions = session_manager.index.get_sessions(issue_key)
            existing = [s for s in all_sessions if s.session_type == "development"] if all_sessions else []

            if not existing:
                # Create new session
                issue_summary = ticket.get('summary', '')
                goal = f"{issue_key}: {issue_summary}" if issue_summary else issue_key

                session = session_manager.create_session(
                    name=session_name,
                    issue_key=issue_key,
                    goal=goal,
                )

                session.status = 'created'
                session.issue_tracker = 'github'
                session.issue_key = issue_key
                session.issue_updated = ticket.get('updated')

                # Copy all fields to issue_metadata
                session.issue_metadata = {
                    k: v for k, v in ticket.items()
                    if k not in ('key', 'updated') and v is not None
                }

                # Auto-inherit workspace from creation session (itdove/devaiflow#131)
                # If user created ticket with `daf git new --workspace X`, inherit workspace X
                inherited_workspace = get_workspace_from_creation_session(session_manager, issue_key)
                if inherited_workspace:
                    session.workspace_name = inherited_workspace

                session_manager.update_session(session)
                created_count += 1

                # Track for recap table
                if synced_tickets is not None:
                    synced_tickets.append({
                        "session_name": session_name,  # Use converted session name, not issue key
                        "title": issue_summary or issue_key,
                        "action": "CREATED",
                        "backend": "GitHub"
                    })

                console_print(f"[green]  ✓[/green] Created session: {session_name} ({issue_key})")
            else:
                # Update existing session if needed
                for session in existing:
                    ticket_updated = ticket.get('updated')
                    session_updated = session.issue_updated

                    needs_update = False
                    if ticket_updated:
                        if not session_updated or ticket_updated != session_updated:
                            needs_update = True

                    if needs_update:
                        session.issue_tracker = 'github'
                        session.issue_updated = ticket_updated
                        session.issue_metadata = {
                            k: v for k, v in ticket.items()
                            if k not in ('key', 'updated') and v is not None
                        }

                        session_manager.update_session(session)
                        updated_count += 1

                        # Track for recap table
                        if synced_tickets is not None:
                            issue_summary = ticket.get('summary', issue_key)
                            synced_tickets.append({
                                "session_name": session.name,  # Use actual session name from session object
                                "title": issue_summary,
                                "action": "UPDATED",
                                "backend": "GitHub"
                            })

                        console_print(f"[cyan]  ↻[/cyan] Updated session: {issue_key}")

    except IssueTrackerAuthError as e:
        console_print(f"[yellow]  ⚠[/yellow] GitHub auth failed for {repository}: {e}")
    except IssueTrackerApiError as e:
        console_print(f"[yellow]  ⚠[/yellow] GitHub API error for {repository}: {e}")
    except Exception as e:
        console_print(f"[yellow]  ⚠[/yellow] Error syncing {repository}: {e}")

    return {'created_count': created_count, 'updated_count': updated_count}


def sync_gitlab_repository(
    repository: str,
    session_manager: SessionManager,
    config: Any,
    repository_url: Optional[str] = None,
    output_json: bool = False,
    synced_tickets: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, int]:
    """Sync issues from a GitLab repository.

    Args:
        repository: Repository in group/project format
        session_manager: Session manager instance
        config: Configuration object
        repository_url: Optional Git remote URL (to extract hostname for uniqueness)
        output_json: Whether to output JSON
        synced_tickets: Optional list to track synced tickets for recap table

    Returns:
        Dictionary with created_count and updated_count
    """
    created_count = 0
    updated_count = 0

    try:
        # Extract hostname from repository URL for uniqueness
        # Example: https://gitlab.com/group/project.git → gitlab.com
        # Example: https://gitlab.example.com/group/project.git → gitlab.example.com
        hostname = 'gitlab.com'  # Default
        if repository_url:
            import re
            # Match both HTTPS and SSH URLs
            https_match = re.match(r'https?://([^/]+)/', repository_url)
            ssh_match = re.match(r'git@([^:]+):', repository_url)
            if https_match:
                hostname = https_match.group(1)
            elif ssh_match:
                hostname = ssh_match.group(1)

        # Create GitLab client with hostname for enterprise instances
        from devflow.gitlab.issues_client import GitLabClient
        client = GitLabClient(repository=repository, hostname=hostname)

        # Get current GitLab username
        import subprocess
        try:
            # Build glab api command with hostname if needed
            glab_cmd = ['glab', 'api']

            # Add --hostname if not gitlab.com (for enterprise instances)
            if hostname and hostname != 'gitlab.com':
                glab_cmd.extend(['--hostname', hostname])

            glab_cmd.append('user')

            result = subprocess.run(
                glab_cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )

            if result.returncode == 0 and result.stdout.strip():
                # Parse JSON output from glab api (returns JSON by default)
                import json
                user_data = json.loads(result.stdout.strip())
                username = user_data.get('username', '@me')

                if not username or username == '@me':
                    raise ValueError("Empty username from glab api")

                # Debug: Show detected username
                console_print(f"[dim]  Detected GitLab user: {username}[/dim]")
            else:
                raise ValueError(f"glab api user failed: {result.stderr}")
        except Exception as e:
            username = '@me'  # Fallback to @me
            # Debug: Show fallback
            console_print(f"[dim]  Username detection failed ({e}), using @me[/dim]")

        # Fetch issues assigned to current user
        tickets = client.list_tickets(
            project=repository,
            assignee=username,  # Use actual username
            status=['open'],  # Only opened issues
            max_results=100,
        )

        if not tickets:
            console_print(f"[dim]  No issues found in {repository}[/dim]")
            return {'created_count': 0, 'updated_count': 0}

        console_print(f"[dim]  Found {len(tickets)} issues in {repository}[/dim]")

        for ticket in tickets:
            issue_key = ticket['key']  # Format: group/project#123

            # Convert issue key to dash-separated session name
            # Example: "group/project#60" → "group-project-60"
            # Example: "gitlab.example.com/group/project#60" → "gitlab-example-com-group-project-60"
            session_name = issue_key_to_session_name(issue_key, hostname=hostname)

            # Check if session already exists
            all_sessions = session_manager.index.get_sessions(issue_key)
            existing = [s for s in all_sessions if s.session_type == "development"] if all_sessions else []

            if not existing:
                # Create new session
                issue_summary = ticket.get('summary', '')
                goal = f"{issue_key}: {issue_summary}" if issue_summary else issue_key

                session = session_manager.create_session(
                    name=session_name,
                    issue_key=issue_key,
                    goal=goal,
                )

                session.status = 'created'
                session.issue_tracker = 'gitlab'
                session.issue_key = issue_key
                session.issue_updated = ticket.get('updated')

                # Copy all fields to issue_metadata
                session.issue_metadata = {
                    k: v for k, v in ticket.items()
                    if k not in ('key', 'updated') and v is not None
                }

                # Auto-inherit workspace from creation session
                # If user created ticket with `daf git new --workspace X`, inherit workspace X
                inherited_workspace = get_workspace_from_creation_session(session_manager, issue_key)
                if inherited_workspace:
                    session.workspace_name = inherited_workspace

                session_manager.update_session(session)
                created_count += 1

                # Track for recap table
                if synced_tickets is not None:
                    synced_tickets.append({
                        "session_name": session_name,  # Use converted session name, not issue key
                        "title": issue_summary or issue_key,
                        "action": "CREATED",
                        "backend": "GitLab"
                    })

                console_print(f"[green]  ✓[/green] Created session: {session_name} ({issue_key})")
            else:
                # Update existing session if needed
                for session in existing:
                    ticket_updated = ticket.get('updated')
                    session_updated = session.issue_updated

                    needs_update = False
                    if ticket_updated:
                        if not session_updated or ticket_updated != session_updated:
                            needs_update = True

                    if needs_update:
                        session.issue_tracker = 'gitlab'
                        session.issue_updated = ticket_updated
                        session.issue_metadata = {
                            k: v for k, v in ticket.items()
                            if k not in ('key', 'updated') and v is not None
                        }

                        session_manager.update_session(session)
                        updated_count += 1

                        # Track for recap table
                        if synced_tickets is not None:
                            issue_summary = ticket.get('summary', issue_key)
                            synced_tickets.append({
                                "session_name": session.name,  # Use actual session name from session object
                                "title": issue_summary,
                                "action": "UPDATED",
                                "backend": "GitLab"
                            })

                        console_print(f"[cyan]  ↻[/cyan] Updated session: {issue_key}")

    except IssueTrackerAuthError as e:
        console_print(f"[yellow]  ⚠[/yellow] GitLab auth failed for {repository}: {e}")
    except IssueTrackerApiError as e:
        console_print(f"[yellow]  ⚠[/yellow] GitLab API error for {repository}: {e}")
    except Exception as e:
        console_print(f"[yellow]  ⚠[/yellow] Error syncing {repository}: {e}")

    return {'created_count': created_count, 'updated_count': updated_count}


@require_outside_claude
def sync_multi_backend(
    field_filters: Optional[Dict[str, str]] = None,
    ticket_type: Optional[str] = None,
    epic: Optional[str] = None,
    workspace_filter: Optional[str] = None,
    repository_filter: Optional[str] = None,
    sync_jira: bool = True,
    sync_workspaces: bool = True,
    output_json: bool = False,
) -> None:
    """Sync issues from configured backends (JIRA + GitHub + GitLab).

    Smart sync automatically determines what to sync based on parameters:
    - sync_jira=True: Sync JIRA tickets
    - sync_workspaces=True: Scan workspaces and sync GitHub/GitLab issues

    Args:
        field_filters: JIRA-specific field filters
        ticket_type: JIRA ticket type filter
        epic: JIRA epic filter
        workspace_filter: Limit sync to specific workspace (name from config)
        repository_filter: Limit sync to specific repository (format: owner/repo)
        sync_jira: Whether to sync JIRA tickets (default: True)
        sync_workspaces: Whether to scan workspaces and sync GitHub/GitLab (default: True)
        output_json: Output results as JSON
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    if not config:
        console.print("[yellow]⚠[/yellow] No configuration found")
        console.print("[dim]Run 'daf init' to create default configuration[/dim]")
        return

    total_created = 0
    total_updated = 0
    backend_stats = {}
    synced_tickets: List[Dict[str, str]] = []  # Track all synced tickets for recap

    # Phase 1: Sync JIRA (if configured and sync_jira=True)
    if sync_jira and config.jira and config.jira.project and config.jira.url:
        console_print("[bold cyan]Syncing JIRA tickets...[/bold cyan]")

        # Get sync filters
        sync_filters = config.jira.filters.get("sync") if config.jira.filters else None
        if sync_filters:
            try:
                jira_client = JiraClient()
                tickets = jira_client.list_tickets(
                    assignee=sync_filters.assignee,
                    status_list=sync_filters.status if sync_filters.status else None,
                    ticket_type=ticket_type,
                    field_mappings=config.jira.field_mappings,
                    field_filters=field_filters,
                )

                # Filter by required fields (same logic as original sync_jira)
                filtered_tickets = []
                for ticket in tickets:
                    issue_type = ticket.get("type")
                    if not issue_type:
                        continue

                    required_fields = sync_filters.get_required_fields_for_type(issue_type)
                    skip_ticket = False
                    for field in required_fields:
                        if not ticket.get(field):
                            skip_ticket = True
                            break

                    if not skip_ticket:
                        filtered_tickets.append(ticket)

                console_print(f"[dim]Found {len(filtered_tickets)} JIRA tickets[/dim]")

                # Process JIRA tickets
                jira_created = 0
                jira_updated = 0
                for ticket in filtered_tickets:
                    issue_key = ticket["key"]
                    all_sessions = session_manager.index.get_sessions(issue_key)
                    existing = [s for s in all_sessions if s.session_type == "development"] if all_sessions else []

                    if not existing:
                        issue_summary = ticket.get("summary", "")
                        goal = f"{issue_key}: {issue_summary}" if issue_summary else issue_key

                        session = session_manager.create_session(
                            name=issue_key,
                            issue_key=issue_key,
                            goal=goal,
                        )

                        session.status = "created"
                        session.issue_tracker = "jira"
                        session.issue_key = issue_key
                        session.issue_updated = ticket.get("updated")
                        session.issue_metadata = {
                            k: v for k, v in ticket.items()
                            if k not in ('key', 'updated') and v is not None
                        }

                        # Auto-inherit workspace from creation session (itdove/devaiflow#131)
                        # If user created ticket with `daf jira new --workspace X`, inherit workspace X
                        inherited_workspace = get_workspace_from_creation_session(session_manager, issue_key)
                        if inherited_workspace:
                            session.workspace_name = inherited_workspace

                        session_manager.update_session(session)
                        jira_created += 1

                        # Track for recap table
                        synced_tickets.append({
                            "session_name": issue_key,  # For JIRA, session name == issue key
                            "title": issue_summary,
                            "action": "CREATED",
                            "backend": "JIRA"
                        })

                        console_print(f"[green]✓[/green] Created JIRA session: {issue_key}")
                    else:
                        # Update logic (same as original)
                        for session in existing:
                            ticket_updated = ticket.get("updated")
                            if ticket_updated and (not session.issue_updated or ticket_updated != session.issue_updated):
                                session.issue_tracker = "jira"
                                session.issue_updated = ticket_updated
                                session.issue_metadata = {
                                    k: v for k, v in ticket.items()
                                    if k not in ('key', 'updated') and v is not None
                                }
                                session_manager.update_session(session)
                                jira_updated += 1

                                # Track for recap table
                                issue_summary = ticket.get("summary", issue_key)
                                synced_tickets.append({
                                    "session_name": issue_key,  # For JIRA, session name == issue key
                                    "title": issue_summary,
                                    "action": "UPDATED",
                                    "backend": "JIRA"
                                })

                                console_print(f"[cyan]↻[/cyan] Updated JIRA session: {issue_key}")

                backend_stats['jira'] = {'created': jira_created, 'updated': jira_updated}
                total_created += jira_created
                total_updated += jira_updated

            except (JiraAuthError, JiraApiError, JiraConnectionError) as e:
                console_print(f"[yellow]⚠[/yellow] JIRA sync failed: {e}")
            except Exception as e:
                console_print(f"[yellow]⚠[/yellow] JIRA sync error: {e}")
        else:
            console_print("[dim]No JIRA sync filters configured, skipping JIRA sync[/dim]")
    else:
        # Only show JIRA messages when no workspace filters are used
        # If workspace filters present, user explicitly requested workspace-only mode (silent)
        has_workspace_filters = workspace_filter or repository_filter

        if not has_workspace_filters:
            # No workspace filters - user intended to sync JIRA, so show why we're not
            if config.jira and not config.jira.url:
                console_print("[dim]JIRA URL not configured, skipping JIRA sync[/dim]")
            elif config.jira and not config.jira.project:
                console_print("[dim]JIRA project not configured, skipping JIRA sync[/dim]")
            else:
                console_print("[dim]JIRA not configured, skipping JIRA sync[/dim]")

    # Phase 2: Scan workspaces for git repositories (if sync_workspaces=True)
    all_repositories = []
    seen_repos = set()  # Track unique repositories by owner/repo

    if sync_workspaces:
        console_print()
        console_print("[bold cyan]Scanning workspaces for git repositories...[/bold cyan]")

        if config.repos and config.repos.workspaces:
            workspaces_to_scan = config.repos.workspaces

            # Apply workspace filter if provided
            if workspace_filter:
                workspaces_to_scan = [w for w in config.repos.workspaces if w.name == workspace_filter]
                if not workspaces_to_scan:
                    console_print(f"[yellow]⚠[/yellow] Workspace '{workspace_filter}' not found in configuration")
                    console_print("[dim]Available workspaces:[/dim]")
                    for w in config.repos.workspaces:
                        console_print(f"  [dim]• {w.name}: {w.path}[/dim]")
                    # Continue with JIRA sync results (if any)
                    if not output_json:
                        console_print()
                        console_print("[dim]Use 'daf workspace list' to see all configured workspaces[/dim]")

            for workspace in workspaces_to_scan:
                workspace_path = workspace.path
                console_print(f"[dim]Scanning {workspace_path}...[/dim]")

                repos = scan_workspace_for_repositories(workspace_path)

                # Deduplicate repositories
                unique_repos = []
                for repo in repos:
                    repo_key = repo['repository']  # owner/repo format
                    if repo_key not in seen_repos:
                        seen_repos.add(repo_key)
                        unique_repos.append(repo)
                        remote_indicator = f"via {repo['remote']}" if repo['remote'] else ""
                        console_print(f"  [dim]• {repo['repository']} ({repo['backend']}) {remote_indicator}[/dim]")

                all_repositories.extend(unique_repos)

        if not all_repositories:
            console_print("[dim]No git repositories found in configured workspaces[/dim]")
        else:
            console_print(f"[dim]Found {len(all_repositories)} unique repositories[/dim]")

    # Phase 3: Sync GitHub/GitLab issues (if sync_workspaces=True)
    if sync_workspaces:
        github_repos = [r for r in all_repositories if r['backend'] == 'github']
        gitlab_repos = [r for r in all_repositories if r['backend'] == 'gitlab']

        # Apply repository filter if provided
        if repository_filter:
            github_repos = [r for r in github_repos if r['repository'] == repository_filter]
            gitlab_repos = [r for r in gitlab_repos if r['repository'] == repository_filter]

            # If no repositories match filter, add it directly (assume GitHub for now)
            if not github_repos and not gitlab_repos:
                if all_repositories:
                    # Repository wasn't found in scanned workspaces - show warning but continue
                    console_print()
                    console_print(f"[yellow]⚠[/yellow] Repository '{repository_filter}' not found in scanned workspaces")
                    console_print("[dim]Discovered repositories:[/dim]")
                    for r in all_repositories:
                        console_print(f"  [dim]• {r['repository']} ({r['backend']})[/dim]")
                    console_print(f"[dim]Adding '{repository_filter}' directly for sync (assuming GitHub)[/dim]")

                # Add the repository directly (assume GitHub, could enhance to detect GitLab)
                github_repos.append({
                    'repository': repository_filter,
                    'backend': 'github',
                    'url': None,  # No local git remote
                    'remote': None
                })

        if github_repos:
            console_print()
            console_print(f"[bold cyan]Syncing GitHub issues ({len(github_repos)} repositories)...[/bold cyan]")

            github_created = 0
            github_updated = 0
            for repo_info in github_repos:
                repository = repo_info['repository']
                repository_url = repo_info.get('url')  # Git remote URL for hostname extraction
                console_print(f"[cyan]• {repository}[/cyan]")

                result = sync_github_repository(
                    repository,
                    session_manager,
                    config,
                    repository_url=repository_url,
                    output_json=output_json,
                    synced_tickets=synced_tickets
                )
                github_created += result['created_count']
                github_updated += result['updated_count']

            backend_stats['github'] = {'created': github_created, 'updated': github_updated}
            total_created += github_created
            total_updated += github_updated

        if gitlab_repos:
            console_print()
            console_print(f"[bold cyan]Syncing GitLab issues ({len(gitlab_repos)} repositories)...[/bold cyan]")

            gitlab_created = 0
            gitlab_updated = 0

            for repo_info in gitlab_repos:
                repository = repo_info['repository']
                repository_url = repo_info.get('url')  # Git remote URL for hostname extraction
                console_print(f"[cyan]• {repository}[/cyan]")

                result = sync_gitlab_repository(
                    repository=repository,
                    session_manager=session_manager,
                    config=config,
                    repository_url=repository_url,
                    output_json=output_json,
                    synced_tickets=synced_tickets,
                )

                gitlab_created += result['created_count']
                gitlab_updated += result['updated_count']

            backend_stats['gitlab'] = {'created': gitlab_created, 'updated': gitlab_updated}
            total_created += gitlab_created
            total_updated += gitlab_updated

    # Render recap table if there are synced tickets
    render_sync_recap_table(synced_tickets)

    # Summary
    console_print()
    console_print("[bold]Sync complete[/bold]")
    console_print(f"[green]Total created:[/green] {total_created} sessions")
    console_print(f"[cyan]Total updated:[/cyan] {total_updated} sessions")

    if backend_stats:
        console_print()
        console_print("[dim]By backend:[/dim]")
        for backend, stats in backend_stats.items():
            console_print(f"  [dim]{backend.upper()}: {stats['created']} created, {stats['updated']} updated[/dim]")

    console_print()
    console_print(f"[dim]Use 'daf list' to see all sessions[/dim]")
    console_print(f"[dim]Use 'daf open <ISSUE-KEY>' to start work[/dim]")
