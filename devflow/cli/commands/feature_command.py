"""Feature orchestration CLI commands.

Provides commands for managing multi-session feature workflows with
integrated verification.
"""

import os
import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.git.utils import GitUtils
from devflow.orchestration.feature import FeatureManager
from devflow.orchestration.storage import FeatureStorage
from devflow.session.manager import SessionManager

console = Console()


def require_experimental(f):
    """Decorator to check if experimental mode is enabled."""
    import functools

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if os.environ.get('DEVAIFLOW_EXPERIMENTAL') != '1':
            console.print("\n[red]✗ Experimental features are not enabled[/red]")
            console.print("\n[yellow]Feature orchestration is an experimental feature.[/yellow]")
            console.print("\nTo enable experimental features, use one of:")
            console.print("  • [cyan]daf -e feature <command>[/cyan]  (short form)")
            console.print("  • [cyan]daf --experimental feature <command>[/cyan]")
            console.print("  • [cyan]export DEVAIFLOW_EXPERIMENTAL=1[/cyan]")
            console.print("\n[dim]Note: The -e flag must come BEFORE 'feature' in the command.[/dim]")
            console.print("\nSee: [dim]docs/experimental/feature-orchestration.md[/dim]\n")
            sys.exit(1)
        return f(*args, **kwargs)

    return wrapper


@click.group()
def feature():
    """[EXPERIMENTAL] Manage multi-session feature orchestration.

    ⚠️  EXPERIMENTAL FEATURE - Subject to change in future releases.

    Feature orchestration allows you to execute multiple sessions sequentially
    on a shared branch with automated verification between sessions.

    This feature is under active development and may have rough edges.
    Please report issues at: https://github.com/itdove/devaiflow/issues

    Enable with:
      daf -e feature <command>          (short form)
      daf --experimental feature <command>
    Or set:
      export DEVAIFLOW_EXPERIMENTAL=1

    Note: The -e flag must come BEFORE the feature command.
    """
    # Display experimental warning
    console.print("\n[bold yellow]⚠️  EXPERIMENTAL FEATURE[/bold yellow]")
    console.print("[yellow]Feature orchestration is experimental and may change.[/yellow]")
    console.print("[dim]Report issues: https://github.com/itdove/devaiflow/issues[/dim]\n")


@feature.command()
@click.argument("name")
@click.option(
    "--sessions",
    help="Comma-separated list of session names (in execution order)",
)
@click.option(
    "--parent",
    help="Parent ticket key (auto-discovers children). Mutually exclusive with --sessions.",
)
@click.option(
    "--branch",
    help="Shared git branch for all sessions (defaults to feature/<name>)",
)
@click.option(
    "--base-branch",
    help="Base branch to create feature branch from (auto-detected if not specified)",
)
@click.option(
    "--verify",
    type=click.Choice(["auto", "manual", "skip"]),
    default="auto",
    help="Verification mode: auto (run checks), manual (user approval), skip (no verification)",
)
@click.option(
    "--workspace",
    help="Workspace name for all sessions",
)
@click.option(
    "--auto-order",
    is_flag=True,
    help="Auto-order sessions by dependencies (blocks/is-blocked-by relationships)",
)
@click.option(
    "--filter-status",
    help="Filter children by status (comma-separated). Defaults to 'To Do,New'",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview session order without creating the feature",
)
@require_experimental
@require_outside_claude
def create(
    name: str,
    sessions: Optional[str],
    parent: Optional[str],
    branch: Optional[str],
    base_branch: Optional[str],
    verify: str,
    workspace: Optional[str],
    auto_order: bool,
    filter_status: Optional[str],
    dry_run: bool,
):
    """Create a new feature orchestration.

    Creates a feature that orchestrates multiple sessions on a single branch
    with verification checkpoints between sessions.

    Examples:

        # Manual session list
        daf -e feature create oauth-integration \\
          --sessions "PROJ-101,PROJ-102,PROJ-103" \\
          --branch "feature/oauth" \\
          --verify auto

        # Auto-discover from parent epic
        daf -e feature create oauth-integration \\
          --parent "PROJ-100" \\
          --auto-order \\
          --verify auto
    """
    try:
        # Validate: must have either --sessions or --parent
        if not sessions and not parent:
            console.print("[red]Error:[/red] Must provide either --sessions or --parent")
            sys.exit(1)

        if sessions and parent:
            console.print("[red]Error:[/red] Cannot use both --sessions and --parent")
            sys.exit(1)

        session_list = []

        # Parse sessions from --sessions flag
        if sessions:
            session_list = [s.strip() for s in sessions.split(",") if s.strip()]

            if len(session_list) < 2:
                console.print("[red]Error:[/red] Feature requires at least 2 sessions")
                sys.exit(1)

        # Discover sessions from --parent flag
        elif parent:
            console.print(f"[bold]Discovering children from parent:[/bold] {parent}\n")

            # Initialize managers
            config_loader = ConfigLoader()
            session_manager = SessionManager(config_loader=config_loader)

            # Detect backend from parent key format
            from devflow.issue_tracker.factory import create_issue_tracker_client
            from devflow.utils.backend_detection import detect_backend_from_key

            # Create appropriate client
            config = config_loader.load_config()
            backend = detect_backend_from_key(parent, config)
            issue_tracker_client = create_issue_tracker_client(backend=backend)

            # Get sync filters from config
            sync_filters = None
            if backend == "jira":
                # JIRA: Use configured sync filters, or default to currentUser()
                sync_filters_config = None
                if config.jira and config.jira.filters:
                    sync_filters_config = config.jira.filters.get("sync")

                if sync_filters_config:
                    # Use configured filters
                    assignee = sync_filters_config.assignee
                    required_fields = sync_filters_config.required_fields
                    status = sync_filters_config.status
                else:
                    # No filters configured - use safe defaults
                    console.print(f"[dim]No JIRA filters configured, using defaults (assignee: currentUser(), status: ['New', 'To Do', 'In Progress'])[/dim]")
                    assignee = "currentUser()"
                    required_fields = {}  # Empty dict for type-specific fields
                    status = ["New", "To Do", "In Progress"]

                console.print(f"[dim]Filtering by assignee: {assignee}[/dim]")
                sync_filters = {
                    "status": filter_status.split(",") if filter_status else status,
                    "assignee": assignee,
                    "required_fields": required_fields,
                }
            elif backend == "github":
                # GitHub: Use configured sync filters, or default to current user
                sync_filters_config = None
                if config.github and config.github.filters:
                    sync_filters_config = config.github.filters.get("sync")

                if sync_filters_config:
                    # Use configured filters
                    assignee = sync_filters_config.assignee
                    required_fields = sync_filters_config.required_fields
                    status = sync_filters_config.status
                else:
                    # No filters configured - use defaults (like daf sync does)
                    console.print(f"[dim]No GitHub filters configured, using defaults (assignee: current user, required_fields: ['assignee'])[/dim]")
                    assignee = "@me"
                    required_fields = ["assignee"]
                    status = ["open"]

                # Resolve @me to actual username
                if assignee == "@me":
                    import subprocess
                    try:
                        result = subprocess.run(
                            ['gh', 'api', 'user', '--jq', '.login'],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        assignee = result.stdout.strip()
                        if not assignee:
                            console.print(f"[yellow]Warning:[/yellow] Could not detect GitHub username")
                            assignee = "@me"
                    except Exception as e:
                        console.print(f"[yellow]Warning:[/yellow] Could not detect GitHub username: {e}")
                        assignee = "@me"

                console.print(f"[dim]Filtering by assignee: {assignee}[/dim]")
                sync_filters = {
                    "status": filter_status.split(",") if filter_status else status,
                    "assignee": assignee,
                    "required_fields": required_fields,
                }
            elif backend == "gitlab":
                # GitLab: Use configured sync filters, or default to current user
                sync_filters_config = None
                if config.gitlab and config.gitlab.filters:
                    sync_filters_config = config.gitlab.filters.get("sync")

                if sync_filters_config:
                    # Use configured filters
                    assignee = sync_filters_config.assignee
                    required_fields = sync_filters_config.required_fields
                    status = sync_filters_config.status
                else:
                    # No filters configured - use defaults
                    console.print(f"[dim]No GitLab filters configured, using defaults (assignee: current user, required_fields: ['assignee'])[/dim]")
                    assignee = "@me"
                    required_fields = ["assignee"]
                    status = ["open"]

                # Resolve @me to actual username
                if assignee == "@me":
                    import subprocess
                    try:
                        result = subprocess.run(
                            ['glab', 'api', 'user'],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        import json
                        user_data = json.loads(result.stdout.strip())
                        assignee = user_data.get('username', '')
                        if not assignee:
                            console.print(f"[yellow]Warning:[/yellow] Could not detect GitLab username")
                            assignee = "@me"
                    except Exception as e:
                        console.print(f"[yellow]Warning:[/yellow] Could not detect GitLab username: {e}")
                        assignee = "@me"

                console.print(f"[dim]Filtering by assignee: {assignee}[/dim]")
                sync_filters = {
                    "status": filter_status.split(",") if filter_status else status,
                    "assignee": assignee,
                    "required_fields": required_fields,
                }

            # Discover children using parent discovery
            from devflow.orchestration.parent_discovery import ParentTicketDiscovery

            discovery = ParentTicketDiscovery(issue_tracker_client)

            try:
                children = discovery.discover_children(parent, sync_filters)
            except ValueError as e:
                console.print(f"[red]Error:[/red] {e}")
                sys.exit(1)

            if not children:
                console.print("[yellow]No children found matching filters[/yellow]")
                sys.exit(1)

            # Order by dependencies if requested
            if auto_order:
                console.print("[dim]Ordering by dependencies...[/dim]")
                children, warnings = discovery.order_by_dependencies(children)

                if warnings:
                    for warning in warnings:
                        console.print(f"[yellow]Warning:[/yellow] {warning}")

            # Display children for confirmation
            discovery.display_children(children, parent)

            # DRY RUN MODE: Exit early if dry-run
            if dry_run:
                console.print("\n[bold cyan]DRY RUN:[/bold cyan] Feature preview\n")
                console.print(f"[dim]Feature name:[/dim] {name}")
                console.print(f"[dim]Branch:[/dim] {branch or f'feature/{name}'}")
                console.print(f"[dim]Sessions:[/dim] {len(children)}\n")

                console.print("[bold]Session order:[/bold]")
                for i, child in enumerate(children, 1):
                    console.print(f"  {i}. {child['key']} - {child.get('summary', 'N/A')}")

                console.print("\n[dim]No changes made (dry-run mode)[/dim]")
                console.print("[dim]Remove --dry-run to create the feature[/dim]")
                sys.exit(0)

            # Filter to only children that meet sync criteria
            valid_children = [c for c in children if c.get('meets_criteria', True)]
            excluded_children = [c for c in children if not c.get('meets_criteria', True)]

            if excluded_children:
                console.print(f"\n[yellow]Note:[/yellow] {len(excluded_children)} children excluded by sync criteria")
                console.print("[dim](See table above for details)[/dim]\n")

            # Check which valid children are missing sessions
            missing_sessions = []
            for child in valid_children:
                child_key = child["key"]
                existing_session = session_manager.get_session(child_key)
                if not existing_session:
                    missing_sessions.append(child)

            # If any children are missing sessions, prompt to sync
            if missing_sessions:
                console.print(f"\n[yellow]⚠ Warning:[/yellow] {len(missing_sessions)} children don't have sessions yet\n")

                # Show missing sessions
                from rich.table import Table
                table = Table(show_header=True, header_style="bold yellow")
                table.add_column("Key", style="yellow", no_wrap=True)
                table.add_column("Title", style="white")
                table.add_column("Status", style="magenta")

                for child in missing_sessions:
                    key = child.get("key", "")
                    title = child.get("summary", "")
                    status = child.get("status", "")

                    if len(title) > 50:
                        title = title[:47] + "..."

                    table.add_row(key, title, status)

                console.print(table)
                console.print()

                # Ask user what to do
                console.print("[bold]Options:[/bold]")
                console.print("  1. Auto-create sessions now (recommended)")
                console.print("  2. Exit and run 'daf sync' manually first")
                console.print("  3. Cancel\n")

                choice = click.prompt("Select option", type=int, default=1)

                if choice == 2:
                    console.print("\n[cyan]Please run:[/cyan] daf sync")
                    console.print("[dim]This will sync all children assigned to you[/dim]")
                    sys.exit(0)
                elif choice == 3:
                    console.print("Cancelled")
                    sys.exit(0)
                # choice == 1: continue to create sessions

            # Confirm with user
            if not click.confirm("\nCreate feature orchestration?", default=True):
                console.print("Cancelled")
                sys.exit(0)

            # Create sessions for valid children only (that meet sync criteria)
            created_sessions = []
            for child in valid_children:
                child_key = child["key"]

                # Check if session exists
                existing_session = session_manager.get_session(child_key)

                if not existing_session:
                    # Create session
                    child_summary = child.get("summary", "")
                    goal = f"{child_key}: {child_summary}" if child_summary else child_key

                    session = session_manager.create_session(
                        name=child_key,
                        issue_key=child_key,
                        goal=goal,
                    )

                    # Set session status
                    session.status = "created"

                    # Populate issue metadata
                    session.issue_tracker = config.issue_tracker_backend
                    session.issue_metadata = {
                        k: v for k, v in child.items() if k not in ("key", "updated", "meets_criteria", "exclusion_reason") and v is not None
                    }

                    session_manager.update_session(session)
                    created_sessions.append(child_key)
                    console.print(f"[green]✓[/green] Created session: {child_key}")
                else:
                    console.print(f"[dim]Session already exists: {child_key}[/dim]")

                session_list.append(child_key)

            if created_sessions:
                console.print(f"\n[green]Created {len(created_sessions)} sessions[/green]\n")

        if len(session_list) < 2:
            console.print("[red]Error:[/red] Feature requires at least 2 sessions")
            sys.exit(1)

        # Default branch name
        if not branch:
            branch = f"feature/{name}"

        # Auto-detect base branch if not specified
        if not base_branch:
            from pathlib import Path
            base_branch = GitUtils.get_default_branch(Path.cwd()) or "main"

        # DRY RUN MODE: Show preview and exit (for --sessions path)
        if dry_run and sessions:
            console.print("\n[bold cyan]DRY RUN:[/bold cyan] Feature preview\n")
            console.print(f"[dim]Feature name:[/dim] {name}")
            console.print(f"[dim]Branch:[/dim] {branch}")
            console.print(f"[dim]Base branch:[/dim] {base_branch}")
            console.print(f"[dim]Verification:[/dim] {verify}")
            console.print(f"[dim]Sessions:[/dim] {len(session_list)}\n")

            console.print("[bold]Session order:[/bold]")
            for i, session_name in enumerate(session_list, 1):
                console.print(f"  {i}. {session_name}")

            console.print("\n[dim]No changes made (dry-run mode)[/dim]")
            console.print("[dim]Remove --dry-run to create the feature[/dim]")
            sys.exit(0)

        # Initialize managers
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader=config_loader)
        feature_manager = FeatureManager(
            config_loader=config_loader,
            session_manager=session_manager,
        )

        # Create feature
        console.print(f"\n[bold]Creating feature orchestration:[/bold] {name}")
        console.print(f"[dim]Branch:[/dim] {branch}")
        console.print(f"[dim]Base branch:[/dim] {base_branch}")
        console.print(f"[dim]Sessions:[/dim] {len(session_list)}")
        console.print(f"[dim]Verification:[/dim] {verify}\n")

        feature = feature_manager.create_feature(
            name=name,
            sessions=session_list,
            branch=branch,
            base_branch=base_branch,
            verification_mode=verify,
            workspace_name=workspace,
        )

        console.print("[green]✓[/green] Feature created successfully\n")

        # Display feature details
        console.print(f"[bold]Feature:[/bold] {feature.name}")
        console.print(f"[dim]Status:[/dim] {feature.status}")
        console.print(f"[dim]Sessions ({len(feature.sessions)}):[/dim]")

        for i, session_name in enumerate(feature.sessions, 1):
            console.print(f"  {i}. {session_name}")

        if feature.linked_issues:
            console.print(f"\n[dim]Linked issues:[/dim]")
            for issue_key in feature.linked_issues:
                console.print(f"  • {issue_key}")

        console.print(f"\n[bold]Next steps:[/bold]")
        console.print(f"  1. Review feature state: [cyan]daf -e feature status {name}[/cyan]")
        console.print(f"  2. Start execution: [cyan]daf -e feature run {name}[/cyan]")

    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {str(e)}")
        sys.exit(1)


@feature.command()
@click.argument("name", required=False)
@click.option("--status", help="Filter by status (created, running, paused, complete, failed)")
@click.option("--workspace", help="Filter by workspace name")
@require_experimental
def list(name: Optional[str], status: Optional[str], workspace: Optional[str]):
    """List feature orchestrations.

    Shows all features or a specific feature by name.
    """
    try:
        config_loader = ConfigLoader()
        feature_manager = FeatureManager(config_loader=config_loader)

        if name:
            # Show specific feature
            feature = feature_manager.get_feature(name)
            if not feature:
                console.print(f"[red]Error:[/red] Feature '{name}' not found")
                sys.exit(1)

            _display_feature_details(feature)
        else:
            # List all features
            features = feature_manager.list_features(
                status=status,
                workspace_name=workspace,
            )

            if not features:
                console.print("[yellow]No features found[/yellow]")
                return

            # Create table
            table = Table(title="Feature Orchestrations")
            table.add_column("Name", style="cyan")
            table.add_column("Status", style="magenta")
            table.add_column("Progress", style="green")
            table.add_column("Branch", style="blue")
            table.add_column("Sessions", style="yellow")

            for feat in features:
                completed = len(feat.get_completed_sessions())
                total = len(feat.sessions)
                progress = f"{completed}/{total}"

                # Status with color
                status_color = {
                    "created": "white",
                    "running": "cyan",
                    "paused": "yellow",
                    "complete": "green",
                    "failed": "red",
                }.get(feat.status, "white")

                table.add_row(
                    feat.name,
                    f"[{status_color}]{feat.status}[/{status_color}]",
                    progress,
                    feat.branch,
                    str(total),
                )

            console.print()
            console.print(table)
            console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)


def _display_feature_details(feature):
    """Display detailed feature information."""
    console.print(f"\n[bold]Feature:[/bold] {feature.name}")
    console.print(f"[dim]Status:[/dim] {feature.status}")
    console.print(f"[dim]Branch:[/dim] {feature.branch}")
    console.print(f"[dim]Base branch:[/dim] {feature.base_branch}")
    console.print(f"[dim]Verification:[/dim] {feature.verification_mode}")

    if feature.workspace_name:
        console.print(f"[dim]Workspace:[/dim] {feature.workspace_name}")

    # Progress
    completed = len(feature.get_completed_sessions())
    total = len(feature.sessions)
    console.print(f"\n[bold]Progress:[/bold] {completed}/{total} sessions\n")

    # Completed sessions
    completed_sessions = feature.get_completed_sessions()
    if completed_sessions:
        console.print("[green]Completed:[/green]")
        for session_name in completed_sessions:
            console.print(f"  ✓ {session_name}")
            if session_name in feature.verification_results:
                result = feature.verification_results[session_name]
                console.print(f"    [dim]Verification: {result.status} ({result.verified_criteria}/{result.total_criteria} criteria)[/dim]")

    # Current session
    current = feature.get_current_session()
    if current:
        status = feature.session_statuses.get(current, "pending")
        status_symbol = {
            "pending": "○",
            "running": "⧗",
            "paused": "⏸",
            "completed": "✓",
            "failed": "✗",
        }.get(status, "?")

        console.print(f"\n[yellow]Current:[/yellow]")
        console.print(f"  {status_symbol} {current} ({status})")

        if status == "paused" and current in feature.verification_results:
            result = feature.verification_results[current]
            console.print(f"    [red]Verification failed:[/red] {len(result.unverified_criteria)} criteria not met")

    # Pending sessions
    pending = feature.get_pending_sessions()
    if pending:
        console.print(f"\n[dim]Pending:[/dim]")
        for session_name in pending:
            console.print(f"  ○ {session_name}")

    # Linked issues
    if feature.linked_issues:
        console.print(f"\n[dim]Linked issues:[/dim]")
        for issue_key in feature.linked_issues:
            console.print(f"  • {issue_key}")

    # PR info
    if feature.pr_url:
        console.print(f"\n[dim]Pull Request:[/dim] {feature.pr_url}")

    console.print()


@feature.command()
@click.argument("name")
@click.option("--delete-sessions", is_flag=True, help="Also delete all sessions in this feature")
@click.option("--delete-branch", is_flag=True, help="Also delete the git branch")
@require_experimental
def delete(name: str, delete_sessions: bool, delete_branch: bool):
    """Delete a feature orchestration.

    By default, only removes the feature metadata. Sessions and branches are preserved.
    Use --delete-sessions and/or --delete-branch to clean up completely.

    Examples:

        # Delete feature only (sessions and branch preserved)
        daf -e feature delete my-feature

        # Delete feature and all sessions
        daf -e feature delete my-feature --delete-sessions

        # Delete everything (feature, sessions, and branch)
        daf -e feature delete my-feature --delete-sessions --delete-branch
    """
    try:
        config_loader = ConfigLoader()
        storage = FeatureStorage()

        # Load index
        index = storage.load_index()

        # Check if feature exists
        feature = index.get_feature(name)
        if not feature:
            console.print(f"[red]Error:[/red] Feature '{name}' not found")
            sys.exit(1)

        # Show what will be deleted
        console.print(f"\n[yellow]Warning:[/yellow] This will delete:")
        console.print(f"  • Feature orchestration: {name}")

        if delete_sessions:
            console.print(f"  • All {len(feature.sessions)} sessions: {', '.join(feature.sessions)}")
        else:
            console.print(f"[dim]  • Sessions will be preserved ({len(feature.sessions)} sessions)[/dim]")

        if delete_branch:
            console.print(f"  • Git branch: {feature.branch}")
        else:
            console.print(f"[dim]  • Branch will be preserved ({feature.branch})[/dim]")

        console.print()

        if not click.confirm("Continue?"):
            console.print("Cancelled")
            return

        # Delete sessions if requested
        deleted_sessions = []
        if delete_sessions:
            from devflow.session.manager import SessionManager
            session_manager = SessionManager(config_loader)

            for session_name in feature.sessions:
                session = session_manager.get_session(session_name)
                if session:
                    session_manager.delete_session(session_name)  # Pass session_name, not session object
                    deleted_sessions.append(session_name)
                    console.print(f"  [dim]Deleted session: {session_name}[/dim]")

        # Delete branch if requested
        if delete_branch:
            from pathlib import Path
            try:
                # Check if branch exists
                result = GitUtils.run_git_command(
                    ["git", "rev-parse", "--verify", feature.branch],
                    cwd=Path.cwd(),
                    check=False
                )

                if result.returncode == 0:
                    # Check if we're on the branch
                    current_branch_result = GitUtils.run_git_command(
                        ["git", "branch", "--show-current"],
                        cwd=Path.cwd()
                    )
                    current_branch = current_branch_result.stdout.strip()

                    if current_branch == feature.branch:
                        console.print(f"\n[yellow]Warning:[/yellow] Cannot delete current branch '{feature.branch}'")
                        console.print(f"[dim]Please checkout a different branch first[/dim]")
                    else:
                        # Delete branch
                        GitUtils.run_git_command(
                            ["git", "branch", "-D", feature.branch],
                            cwd=Path.cwd()
                        )
                        console.print(f"  [dim]Deleted branch: {feature.branch}[/dim]")
                else:
                    console.print(f"  [dim]Branch {feature.branch} does not exist[/dim]")
            except Exception as e:
                console.print(f"  [yellow]Warning:[/yellow] Could not delete branch: {e}")

        # Delete feature metadata
        index.remove_feature(name)
        storage.save_index(index)
        storage.delete_feature_data(name)

        # Summary
        console.print(f"\n[green]✓[/green] Feature '{name}' deleted")
        if deleted_sessions:
            console.print(f"[green]✓[/green] Deleted {len(deleted_sessions)} sessions")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)


@feature.command()
@click.argument("name")
@click.option("--parent", help="Parent ticket key to re-discover children from")
@click.option("--auto-order", is_flag=True, help="Auto-order new sessions by dependencies")
@click.option("--dry-run", is_flag=True, help="Preview changes without updating the feature")
@require_experimental
@require_outside_claude
def sync(name: str, parent: Optional[str], auto_order: bool, dry_run: bool):
    """Sync a feature with its parent ticket to add new children.

    Re-discovers children from the parent ticket and adds any that now meet
    sync criteria (previously excluded due to missing assignee, required fields, etc.).

    This is useful when you:
    - Created a feature but some children didn't meet criteria
    - Later updated those tickets to meet criteria
    - Want to add them to the existing feature

    Examples:

        # Re-discover and add new children
        daf -e feature sync my-feature --parent "PROJ-100"

        # Preview what would be added
        daf -e feature sync my-feature --parent "PROJ-100" --dry-run

        # Add and reorder by dependencies
        daf -e feature sync my-feature --parent "PROJ-100" --auto-order
    """
    try:
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader=config_loader)
        feature_manager = FeatureManager(config_loader=config_loader, session_manager=session_manager)

        # Load feature
        feature = feature_manager.get_feature(name)
        if not feature:
            console.print(f"[red]Error:[/red] Feature '{name}' not found")
            sys.exit(1)

        if not parent:
            console.print(f"[red]Error:[/red] --parent is required for sync")
            console.print(f"[dim]Usage: daf -e feature sync {name} --parent <parent-key>[/dim]")
            sys.exit(1)

        console.print(f"[bold]Syncing feature '{name}' with parent {parent}[/bold]\n")
        console.print(f"[dim]Current sessions:[/dim] {len(feature.sessions)}")
        console.print(f"[dim]Current: {', '.join(feature.sessions)}[/dim]\n")

        # Detect backend and create client
        from devflow.issue_tracker.factory import create_issue_tracker_client
        from devflow.utils.backend_detection import detect_backend_from_key

        config = config_loader.load_config()
        backend = detect_backend_from_key(parent, config)
        issue_tracker_client = create_issue_tracker_client(backend=backend)

        # Get sync filters (JIRA-only)
        sync_filters = None
        if backend == "jira" and config.jira and config.jira.filters:
            sync_filters_config = config.jira.filters.get("sync")
            if sync_filters_config:
                sync_filters = {
                    "status": sync_filters_config.status,
                    "assignee": sync_filters_config.assignee,
                    "required_fields": sync_filters_config.required_fields,
                }

        # Discover children
        from devflow.orchestration.parent_discovery import ParentTicketDiscovery
        discovery = ParentTicketDiscovery(issue_tracker_client)

        try:
            all_children = discovery.discover_children(parent, sync_filters)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)

        # Filter to valid children (that meet criteria)
        valid_children = [c for c in all_children if c.get('meets_criteria', True)]

        # Find new children (not already in feature)
        current_session_keys = set(feature.sessions)
        new_children = [c for c in valid_children if c['key'] not in current_session_keys]

        if not new_children:
            console.print("[green]✓[/green] No new children found")
            console.print("[dim]All children that meet criteria are already in the feature[/dim]")
            return

        # Show new children
        console.print(f"[bold]Found {len(new_children)} new children:[/bold]\n")

        from rich.table import Table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Type", style="blue")

        for i, child in enumerate(new_children, 1):
            key = child.get("key", "")
            title = child.get("summary", "")
            status = child.get("status", "")
            issue_type = child.get("type", "")

            if len(title) > 50:
                title = title[:47] + "..."

            table.add_row(str(i), key, title, status, issue_type)

        console.print(table)
        console.print()

        if dry_run:
            console.print("[bold cyan]DRY RUN:[/bold cyan] Would add these children to the feature\n")
            console.print(f"[dim]New session count:[/dim] {len(feature.sessions)} → {len(feature.sessions) + len(new_children)}")
            console.print(f"[dim]Remove --dry-run to apply changes[/dim]")
            return

        # Confirm
        if not click.confirm(f"Add {len(new_children)} new children to feature '{name}'?", default=True):
            console.print("Cancelled")
            return

        # Create sessions for new children
        created_count = 0
        for child in new_children:
            child_key = child["key"]

            # Check if session exists
            existing_session = session_manager.get_session(child_key)

            if not existing_session:
                # Create session
                child_summary = child.get("summary", "")
                goal = f"{child_key}: {child_summary}" if child_summary else child_key

                session = session_manager.create_session(
                    name=child_key,
                    issue_key=child_key,
                    goal=goal,
                )

                session.status = "created"
                session.issue_tracker = config.issue_tracker_backend
                session.issue_metadata = {
                    k: v for k, v in child.items()
                    if k not in ("key", "updated", "meets_criteria", "exclusion_reason") and v is not None
                }

                session_manager.update_session(session)
                created_count += 1
                console.print(f"[green]✓[/green] Created session: {child_key}")
            else:
                console.print(f"[dim]Session already exists: {child_key}[/dim]")

            # Add to feature
            feature.sessions.append(child_key)
            feature.session_statuses[child_key] = "pending"

        # Reorder if requested
        if auto_order and backend == "jira":
            console.print("\n[dim]Reordering by dependencies...[/dim]")
            # Get all children with blocking relationships
            all_session_children = []
            for session_name in feature.sessions:
                all_session_children.append({"key": session_name})

            # Fetch blocking relationships for all
            try:
                relationships = issue_tracker_client.get_blocking_relationships(feature.sessions)
                for child in all_session_children:
                    rel = relationships.get(child["key"], {"blocks": [], "blocked_by": []})
                    child["blocks"] = rel["blocks"]
                    child["blocked_by"] = rel["blocked_by"]

                ordered_children, warnings = discovery.order_by_dependencies(all_session_children)
                feature.sessions = [c["key"] for c in ordered_children]

                if warnings:
                    for warning in warnings:
                        console.print(f"[yellow]Warning:[/yellow] {warning}")

                console.print("[green]✓[/green] Reordered by dependencies")
            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Could not reorder: {e}")

        # Save feature
        feature_manager.update_feature(feature)

        # Summary
        console.print(f"\n[green]✓[/green] Feature '{name}' updated")
        if created_count:
            console.print(f"[green]✓[/green] Created {created_count} new sessions")
        console.print(f"[dim]Total sessions:[/dim] {len(feature.sessions)}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)


@feature.command()
@click.argument("name")
@require_experimental
def status(name: str):
    """Show detailed status for a feature.

    Displays progress, verification results, and next steps.
    """
    try:
        config_loader = ConfigLoader()
        feature_manager = FeatureManager(config_loader=config_loader)

        feature = feature_manager.get_feature(name)
        if not feature:
            console.print(f"[red]Error:[/red] Feature '{name}' not found")
            sys.exit(1)

        _display_feature_details(feature)

        # Show next steps based on status
        console.print("[bold]Next steps:[/bold]")

        if feature.status == "created":
            console.print(f"  • Start execution: [cyan]daf -e feature run {name}[/cyan]")

        elif feature.status == "running":
            current = feature.get_current_session()
            console.print(f"  • Wait for session '{current}' to complete")
            console.print(f"  • Verification will run automatically")

        elif feature.status == "paused":
            current = feature.get_current_session()
            console.print(f"  • Fix verification issues in '{current}'")

            if current and current in feature.verification_results:
                result = feature.verification_results[current]
                if result.report_path:
                    console.print(f"  • View report: [cyan]{result.report_path}[/cyan]")

            console.print(f"  • Resume: [cyan]daf -e feature resume {name}[/cyan]")

        elif feature.status == "complete":
            console.print(f"  • Feature complete!")
            if feature.pr_url:
                console.print(f"  • Review PR: {feature.pr_url}")
            else:
                console.print(f"  • Create PR: [cyan]daf -e feature complete {name}[/cyan]")

        elif feature.status == "failed":
            console.print(f"  • Review failure reason")
            console.print(f"  • Fix issues and retry: [cyan]daf -e feature resume {name}[/cyan]")

        console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)


@feature.command()
@click.argument("name")
@require_experimental
@require_outside_claude
def run(name: str):
    """Execute feature sessions sequentially.

    Runs sessions in order with automated verification between each session.
    Pauses automatically if verification fails.

    This is a long-running command that orchestrates the entire feature workflow.
    """
    console.print(f"[yellow]Note:[/yellow] This is Phase 1 MVP - manual session execution")
    console.print(f"[dim]Automated execution loop will be implemented in Phase 2[/dim]\n")

    try:
        config_loader = ConfigLoader()
        feature_manager = FeatureManager(config_loader=config_loader)

        feature = feature_manager.get_feature(name)
        if not feature:
            console.print(f"[red]Error:[/red] Feature '{name}' not found")
            sys.exit(1)

        console.print(f"[bold]Feature:[/bold] {feature.name}")
        console.print(f"[dim]Sessions:[/dim] {len(feature.sessions)}\n")

        # Update status to running
        feature.status = "running"
        feature_manager.update_feature(feature)

        console.print("[bold]Manual execution workflow:[/bold]")
        console.print(f"1. Open each session: [cyan]daf open <session-name>[/cyan]")
        console.print(f"2. Complete the session: [cyan]daf complete <session-name>[/cyan]")
        console.print(f"3. Verification runs automatically")
        console.print(f"4. If verification passes, proceed to next session")
        console.print(f"5. If verification fails, feature pauses for fixes\n")

        # Show session execution order
        console.print("[bold]Execution order:[/bold]")
        for i, session_name in enumerate(feature.sessions, 1):
            status = feature.session_statuses.get(session_name, "pending")
            symbol = {
                "pending": "○",
                "running": "⧗",
                "completed": "✓",
                "paused": "⏸",
                "failed": "✗",
            }.get(status, "?")

            console.print(f"  {i}. {symbol} {session_name} ({status})")

        console.print(f"\n[bold]Current session:[/bold]")
        current = feature.get_current_session()
        if current:
            console.print(f"  → {current}")
            console.print(f"\n[cyan]Next:[/cyan] daf open {current}")
        else:
            console.print(f"  [green]All sessions complete![/green]")
            console.print(f"\n[cyan]Next:[/cyan] daf -e feature complete {name}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)


@feature.command()
@click.argument("name")
@require_experimental
@require_outside_claude
def resume(name: str):
    """Resume a paused feature.

    Re-runs verification for the current session and continues if it passes.
    """
    try:
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader=config_loader)
        feature_manager = FeatureManager(
            config_loader=config_loader,
            session_manager=session_manager,
        )

        feature = feature_manager.get_feature(name)
        if not feature:
            console.print(f"[red]Error:[/red] Feature '{name}' not found")
            sys.exit(1)

        if feature.status != "paused":
            console.print(f"[yellow]Warning:[/yellow] Feature is not paused (status: {feature.status})")
            if feature.status == "complete":
                console.print(f"Feature is already complete")
                return

        console.print(f"[bold]Resuming feature:[/bold] {feature.name}\n")

        # Get current session
        current_session = feature.get_current_session()
        if not current_session:
            console.print("[red]Error:[/red] No current session to resume")
            sys.exit(1)

        console.print(f"Re-running verification for: {current_session}\n")

        # Run verification
        result = feature_manager.verify_session(feature, current_session)

        # Display result
        console.print(f"[bold]Verification result:[/bold] {result.status.upper()}")

        if result.total_criteria > 0:
            console.print(f"Acceptance criteria: {result.verified_criteria}/{result.total_criteria} verified")

        if result.test_command:
            test_status = "✓ PASSED" if result.tests_passed else "✗ FAILED"
            console.print(f"Tests: {test_status}")

        if result.report_path:
            console.print(f"\n[dim]Report:[/dim] {result.report_path}")

        # Update feature status
        if result.status == "passed":
            console.print(f"\n[green]✓ Verification passed![/green]")

            # Update session status
            feature.session_statuses[current_session] = "completed"

            # Move to next session or mark complete
            if not feature.advance_to_next_session():
                console.print(f"\n[green]All sessions complete![/green]")
                feature.status = "complete"
                console.print(f"\n[cyan]Next:[/cyan] daf -e feature complete {name}")
            else:
                feature.status = "running"
                next_session = feature.get_current_session()
                console.print(f"\n[bold]Next session:[/bold] {next_session}")
                console.print(f"[cyan]Command:[/cyan] daf open {next_session}")

            feature_manager.update_feature(feature)

        else:
            console.print(f"\n[yellow]⚠ Verification still has gaps[/yellow]")

            if result.unverified_criteria:
                console.print(f"\nUnverified criteria ({len(result.unverified_criteria)}):")
                for criterion in result.unverified_criteria[:3]:  # Show first 3
                    console.print(f"  • {criterion}")
                if len(result.unverified_criteria) > 3:
                    console.print(f"  ... and {len(result.unverified_criteria) - 3} more")

            if result.suggestions:
                console.print(f"\n[bold]Suggestions:[/bold]")
                for suggestion in result.suggestions:
                    console.print(f"  • {suggestion}")

            console.print(f"\n[dim]Fix issues and run:[/dim] daf -e feature resume {name}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)


@feature.command()
@click.argument("name")
@require_experimental
@require_outside_claude
def complete(name: str):
    """Complete a feature and create pull request.

    Verifies all sessions are complete, runs final checks, and creates
    a single PR with aggregated context from all sessions.
    """
    console.print(f"[yellow]Note:[/yellow] This is Phase 1 MVP - manual PR creation")
    console.print(f"[dim]Automated PR creation will be implemented in Phase 2[/dim]\n")

    try:
        config_loader = ConfigLoader()
        feature_manager = FeatureManager(config_loader=config_loader)

        feature = feature_manager.get_feature(name)
        if not feature:
            console.print(f"[red]Error:[/red] Feature '{name}' not found")
            sys.exit(1)

        console.print(f"[bold]Completing feature:[/bold] {feature.name}\n")

        # Verify all sessions complete
        if not feature.is_complete():
            pending = feature.get_pending_sessions()
            console.print(f"[yellow]Warning:[/yellow] {len(pending)} sessions still pending:")
            for session_name in pending[:5]:
                console.print(f"  • {session_name}")

            console.print(f"\nCannot complete feature with pending sessions")
            sys.exit(1)

        # Display completion summary
        console.print("[green]✓ All sessions complete![/green]\n")

        console.print("[bold]Verification summary:[/bold]")
        total_criteria = 0
        verified_criteria = 0

        for session_name in feature.sessions:
            if session_name in feature.verification_results:
                result = feature.verification_results[session_name]
                total_criteria += result.total_criteria
                verified_criteria += result.verified_criteria

                status_symbol = "✓" if result.status == "passed" else "⚠"
                console.print(
                    f"  {status_symbol} {session_name}: "
                    f"{result.verified_criteria}/{result.total_criteria} criteria"
                )

        console.print(f"\n[bold]Total:[/bold] {verified_criteria}/{total_criteria} criteria verified\n")

        # Manual PR creation instructions
        console.print("[bold]Next steps:[/bold]")
        console.print(f"1. Create PR manually:")
        console.print(f"   [cyan]gh pr create --base {feature.base_branch} --head {feature.branch}[/cyan]")
        console.print(f"\n2. Include in PR description:")
        console.print(f"   • All {len(feature.sessions)} sessions completed")
        console.print(f"   • {verified_criteria}/{total_criteria} acceptance criteria verified")

        if feature.linked_issues:
            console.print(f"   • Linked issues: {', '.join(feature.linked_issues)}")

        console.print(f"\n3. Mark feature as complete:")

        # Mark feature as complete
        feature.status = "complete"
        feature.completed = datetime.now()
        feature_manager.update_feature(feature)

        console.print(f"   [green]✓ Feature marked as complete[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)


@feature.command()
@click.argument("name")
@click.argument("session", required=False)
@click.argument("position", type=int, required=False)
@click.option(
    "--order",
    help="Comma-separated list of session names in new order",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview new order without updating the feature",
)
@require_experimental
@require_outside_claude
def reorder(name: str, session: Optional[str], position: Optional[int], order: Optional[str], dry_run: bool):
    """Reorder sessions in a feature.

    Interactive mode (default): Shows current order and prompts for changes
    Direct mode (--order): Specify new order directly
    Move mode: Move a specific session to a position

    Note: To reorder based on JIRA blocking relationships, use:
          daf -e feature sync <name> --parent <parent> --auto-order

    Examples:

        # Interactive mode
        daf -e feature reorder oauth-integration

        # Move mode - by session name
        daf -e feature reorder oauth-integration PROJ-102 1

        # Move mode - by session number
        daf -e feature reorder oauth-integration 3 1

        # Direct mode (full order)
        daf -e feature reorder oauth-integration \\
          --order "PROJ-102,PROJ-101,PROJ-103"

        # Dry-run preview
        daf -e feature reorder oauth-integration PROJ-102 1 --dry-run
    """
    try:
        config_loader = ConfigLoader()
        feature_manager = FeatureManager(config_loader=config_loader)

        feature = feature_manager.get_feature(name)
        if not feature:
            console.print(f"[red]Error:[/red] Feature '{name}' not found")
            sys.exit(1)

        # Show current order
        console.print(f"\n[bold]Feature:[/bold] {name}")
        console.print(f"[bold]Current order:[/bold]\n")

        for i, session_name in enumerate(feature.sessions, 1):
            status = feature.session_statuses.get(session_name, "pending")
            symbol = {
                "pending": "○",
                "running": "⧗",
                "completed": "✓",
                "paused": "⏸",
                "failed": "✗",
            }.get(status, "?")

            console.print(f"  {i}. {symbol} {session_name} ({status})")

        console.print()

        # Validate argument combinations
        if order and (session is not None or position is not None):
            console.print("[red]Error:[/red] Cannot use both --order and move arguments")
            console.print("[dim]Use either: --order \"s1,s2,s3\" OR <session> <position>[/dim]")
            sys.exit(1)

        if (session is not None) != (position is not None):
            console.print("[red]Error:[/red] Both session and position are required for move mode")
            console.print("[dim]Usage: daf -e feature reorder <name> <session> <position>[/dim]")
            sys.exit(1)

        # Move mode: move specific session to position
        if session is not None and position is not None:
            # Determine if session is a name or number
            session_to_move = None
            current_position = None

            # Try as session number first (1-based)
            try:
                session_num = int(session)
                if 1 <= session_num <= len(feature.sessions):
                    session_to_move = feature.sessions[session_num - 1]
                    current_position = session_num
            except ValueError:
                # It's a session name
                if session in feature.sessions:
                    session_to_move = session
                    current_position = feature.sessions.index(session) + 1

            if not session_to_move:
                console.print(f"[red]Error:[/red] Session '{session}' not found")
                console.print(f"[dim]Available sessions:[/dim]")
                for i, s in enumerate(feature.sessions, 1):
                    console.print(f"  {i}. {s}")
                sys.exit(1)

            # Validate target position
            if position < 1 or position > len(feature.sessions):
                console.print(f"[red]Error:[/red] Position must be between 1 and {len(feature.sessions)}")
                sys.exit(1)

            # Create new order by moving session
            new_sessions = feature.sessions.copy()
            new_sessions.remove(session_to_move)
            new_sessions.insert(position - 1, session_to_move)

            # Show move operation
            console.print(f"[bold]Moving:[/bold] {session_to_move}")
            console.print(f"[dim]From position {current_position} → to position {position}[/dim]\n")

            # Show new order
            console.print("[bold]New order:[/bold]\n")
            for i, session_name in enumerate(new_sessions, 1):
                status = feature.session_statuses.get(session_name, "pending")
                symbol = {
                    "pending": "○",
                    "running": "⧗",
                    "completed": "✓",
                    "paused": "⏸",
                    "failed": "✗",
                }.get(status, "?")
                # Highlight the moved session
                if session_name == session_to_move:
                    console.print(f"  {i}. {symbol} [bold cyan]{session_name}[/bold cyan] ({status}) [cyan]← moved[/cyan]")
                else:
                    console.print(f"  {i}. {symbol} {session_name} ({status})")

            console.print()

            # DRY RUN MODE: Exit early
            if dry_run:
                console.print("[dim]No changes made (dry-run mode)[/dim]")
                console.print("[dim]Remove --dry-run to update the feature[/dim]")
                sys.exit(0)

            # Update order
            feature.sessions = new_sessions
            feature_manager.update_feature(feature)

            console.print("[green]✓[/green] Feature order updated\n")
            return

        # Direct mode: use provided order
        if order:
            new_order = [s.strip() for s in order.split(",") if s.strip()]

            # Validate: must include all sessions
            current_set = set(feature.sessions)
            new_set = set(new_order)

            if current_set != new_set:
                missing = current_set - new_set
                extra = new_set - current_set

                if missing:
                    console.print(f"[red]Error:[/red] Missing sessions: {', '.join(missing)}")
                if extra:
                    console.print(f"[red]Error:[/red] Unknown sessions: {', '.join(extra)}")

                sys.exit(1)

            # Show new order
            console.print("[bold]New order:[/bold]\n")
            for i, session_name in enumerate(new_order, 1):
                status = feature.session_statuses.get(session_name, "pending")
                symbol = {
                    "pending": "○",
                    "running": "⧗",
                    "completed": "✓",
                    "paused": "⏸",
                    "failed": "✗",
                }.get(status, "?")
                console.print(f"  {i}. {symbol} {session_name} ({status})")

            console.print()

            # DRY RUN MODE: Exit early
            if dry_run:
                console.print("[dim]No changes made (dry-run mode)[/dim]")
                console.print("[dim]Remove --dry-run to update the feature[/dim]")
                sys.exit(0)

            # Update order
            feature.sessions = new_order
            feature_manager.update_feature(feature)

            console.print("[green]✓[/green] Feature order updated\n")

        # Interactive mode: prompt for changes
        else:
            console.print("[bold]Reorder options:[/bold]")
            console.print("  1. Move session up/down")
            console.print("  2. Specify new order manually")
            console.print("  3. Cancel\n")

            choice = click.prompt("Select option", type=int, default=3)

            if choice == 1:
                # Move session up/down
                session_num = click.prompt(
                    "Session number to move",
                    type=int,
                    default=1,
                )

                if session_num < 1 or session_num > len(feature.sessions):
                    console.print(f"[red]Error:[/red] Invalid session number")
                    sys.exit(1)

                direction = click.prompt(
                    "Move up or down?",
                    type=click.Choice(["up", "down"]),
                    default="down",
                )

                session_idx = session_num - 1
                new_sessions = feature.sessions.copy()

                if direction == "up" and session_idx > 0:
                    # Swap with previous
                    new_sessions[session_idx], new_sessions[session_idx - 1] = (
                        new_sessions[session_idx - 1],
                        new_sessions[session_idx],
                    )
                elif direction == "down" and session_idx < len(new_sessions) - 1:
                    # Swap with next
                    new_sessions[session_idx], new_sessions[session_idx + 1] = (
                        new_sessions[session_idx + 1],
                        new_sessions[session_idx],
                    )
                else:
                    console.print(f"[yellow]Cannot move {direction}[/yellow]")
                    sys.exit(0)

                # Show new order
                console.print("\n[bold]New order:[/bold]\n")
                for i, session_name in enumerate(new_sessions, 1):
                    status = feature.session_statuses.get(session_name, "pending")
                    symbol = {
                        "pending": "○",
                        "running": "⧗",
                        "completed": "✓",
                        "paused": "⏸",
                        "failed": "✗",
                    }.get(status, "?")
                    console.print(f"  {i}. {symbol} {session_name} ({status})")

                # DRY RUN MODE: Exit early
                if dry_run:
                    console.print("\n[dim]No changes made (dry-run mode)[/dim]")
                    console.print("[dim]Remove --dry-run to update the feature[/dim]")
                    sys.exit(0)

                if click.confirm("\nApply this order?", default=True):
                    feature.sessions = new_sessions
                    feature_manager.update_feature(feature)
                    console.print("[green]✓[/green] Feature order updated")

            elif choice == 2:
                # Manual order
                console.print("\n[dim]Enter session names in order (comma-separated):[/dim]")
                new_order_str = click.prompt("New order")

                new_order = [s.strip() for s in new_order_str.split(",") if s.strip()]

                # Validate
                current_set = set(feature.sessions)
                new_set = set(new_order)

                if current_set != new_set:
                    missing = current_set - new_set
                    extra = new_set - current_set

                    if missing:
                        console.print(f"[red]Error:[/red] Missing sessions: {', '.join(missing)}")
                    if extra:
                        console.print(f"[red]Error:[/red] Unknown sessions: {', '.join(extra)}")

                    sys.exit(1)

                # Show new order
                console.print("\n[bold]New order:[/bold]\n")
                for i, session_name in enumerate(new_order, 1):
                    status = feature.session_statuses.get(session_name, "pending")
                    symbol = {
                        "pending": "○",
                        "running": "⧗",
                        "completed": "✓",
                        "paused": "⏸",
                        "failed": "✗",
                    }.get(status, "?")
                    console.print(f"  {i}. {symbol} {session_name} ({status})")

                # DRY RUN MODE: Exit early
                if dry_run:
                    console.print("\n[dim]No changes made (dry-run mode)[/dim]")
                    console.print("[dim]Remove --dry-run to update the feature[/dim]")
                    sys.exit(0)

                if click.confirm("\nApply this order?", default=True):
                    feature.sessions = new_order
                    feature_manager.update_feature(feature)
                    console.print("[green]✓[/green] Feature order updated")

            else:
                console.print("Cancelled")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)
