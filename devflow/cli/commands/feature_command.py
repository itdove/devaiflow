"""Feature orchestration CLI commands.

Provides commands for managing multi-session feature workflows with
integrated verification.
"""

import os
import sys
from datetime import datetime
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


def _display_children_with_ownership(children, parent_key, current_user):
    """Display children with ownership (yours vs external) information.

    Args:
        children: List of child dicts with _ownership and _will_create_session added
        parent_key: Parent issue key
        current_user: Current user's assignee identifier
    """
    # Count by ownership
    yours_count = sum(1 for c in children if c.get('_ownership') == 'yours')
    external_count = len(children) - yours_count
    will_create_count = sum(1 for c in children if c.get('_will_create_session', False))

    console.print(f"\n[bold]Found {len(children)} children for {parent_key}:[/bold]")
    console.print(f"  • Yours: {yours_count} ({will_create_count} will create sessions)")
    console.print(f"  • External (teammates): {external_count} (tracked for dependencies)\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Assignee", style="blue", no_wrap=True)
    table.add_column("Ownership", style="magenta", no_wrap=True)
    table.add_column("Will Create", style="green", no_wrap=True)

    for i, child in enumerate(children, 1):
        key = child.get("key", "")
        title = child.get("summary") or ""
        assignee = child.get("assignee") or "unassigned"
        ownership = child.get('_ownership', 'unknown')
        will_create = child.get('_will_create_session', False)
        exclusion_reason = child.get('exclusion_reason')

        # Truncate long titles
        if title and len(title) > 40:
            title = title[:37] + "..."

        # Truncate long assignee
        if assignee and len(assignee) > 15:
            assignee = assignee[:12] + "..."

        # Ownership display
        if ownership == 'yours':
            ownership_display = "[green]Yours[/green]"
        else:
            ownership_display = "[dim]External[/dim]"

        # Will create display
        if will_create:
            will_create_display = "[green]✓ Session[/green]"
        elif ownership == 'yours' and not will_create:
            will_create_display = f"[red]✗ {exclusion_reason or 'No'}[/red]"
        else:
            will_create_display = "[dim]Track only[/dim]"

        table.add_row(str(i), key, title, assignee, ownership_display, will_create_display)

    console.print(table)
    console.print()

    # Show excluded reasons if any
    excluded = [c for c in children if c.get('_ownership') == 'yours' and not c.get('_will_create_session')]
    if excluded:
        console.print(f"[yellow]Your children that won't create sessions ({len(excluded)}):[/yellow]")
        for child in excluded:
            console.print(f"  • {child['key']}: {child.get('exclusion_reason', 'unknown reason')}")
        console.print()


def _ensure_feature_branch(project_path: str, feature_branch: str, base_branch: str) -> bool:
    """Ensure feature branch exists in the project.

    Creates the feature branch from base_branch if it doesn't exist.

    Args:
        project_path: Path to git repository
        feature_branch: Feature branch name (e.g., "feature/demo1")
        base_branch: Base branch to create from (e.g., "main")

    Returns:
        True if branch exists or was created successfully, False otherwise
    """
    from pathlib import Path

    project_path = Path(project_path)

    if not GitUtils.is_git_repository(project_path):
        return False

    # Check if feature branch already exists
    existing_branches = GitUtils.list_local_branches(project_path)
    if feature_branch in existing_branches:
        return True

    # Create feature branch from base_branch
    console.print(f"[dim]Creating feature branch '{feature_branch}' from '{base_branch}' in {project_path.name}[/dim]")
    success, error = GitUtils.create_branch(project_path, feature_branch, base_branch)

    if not success:
        console.print(f"[yellow]⚠[/yellow] Failed to create feature branch: {error}")
        return False

    console.print(f"[green]✓[/green] Created feature branch: {feature_branch}")
    return True


def _create_story_branch(project_path: str, story_branch: str, feature_branch: str) -> tuple[bool, str]:
    """Create story-specific branch from feature branch with user choice.

    Args:
        project_path: Path to git repository
        story_branch: Story branch name (e.g., "feature/demo1-aap-70184")
        feature_branch: Feature branch to create from

    Returns:
        Tuple of (success: bool, branch_name: str)
        - (True, branch_name) if branch was selected/created successfully
        - (False, feature_branch) if failed, falls back to feature branch
    """
    from pathlib import Path
    from rich.prompt import Prompt, Confirm

    project_path = Path(project_path)

    if not GitUtils.is_git_repository(project_path):
        return (False, feature_branch)

    # Get current branch and list of existing branches
    current_branch = GitUtils.get_current_branch(project_path)
    existing_branches = GitUtils.list_local_branches(project_path)
    story_branch_exists = story_branch in existing_branches

    # Prompt user for branch choice
    console.print(f"\n[cyan]Story branch strategy for this session:[/cyan]")
    console.print(f"  Current branch: [yellow]{current_branch}[/yellow]")
    console.print(f"  Suggested story branch: [green]{story_branch}[/green] {'(exists)' if story_branch_exists else '(new)'}")
    console.print(f"  Feature branch: [blue]{feature_branch}[/blue]")

    choices = []
    if story_branch_exists:
        choices.append("1. Use existing story branch")
        default_choice = "1"
    else:
        choices.append("1. Create new story branch")
        default_choice = "1"

    choices.append("2. Use current branch")
    choices.append("3. Use feature branch (no story branch)")
    choices.append("4. Select different existing branch")

    console.print("\nOptions:")
    for choice in choices:
        console.print(f"  {choice}")

    choice = Prompt.ask(
        "\nSelect option",
        choices=["1", "2", "3", "4"],
        default=default_choice
    )

    # Handle user choice
    if choice == "1":
        # Use or create story branch
        if story_branch_exists:
            # Checkout existing story branch
            success, error = GitUtils.checkout_branch(project_path, story_branch)
            if success:
                console.print(f"[green]✓[/green] Checked out existing story branch: {story_branch}")
                return (True, story_branch)
            else:
                console.print(f"[yellow]⚠[/yellow] Failed to checkout story branch: {error}")
                return (False, feature_branch)
        else:
            # Create new story branch from feature branch
            console.print(f"[dim]Creating story branch '{story_branch}' from '{feature_branch}'[/dim]")
            success, error = GitUtils.create_branch(project_path, story_branch, feature_branch)
            if not success:
                console.print(f"[yellow]⚠[/yellow] Failed to create story branch: {error}")
                return (False, feature_branch)

            console.print(f"[green]✓[/green] Created and checked out story branch: {story_branch}")
            return (True, story_branch)

    elif choice == "2":
        # Use current branch
        console.print(f"[green]✓[/green] Using current branch: {current_branch}")
        return (True, current_branch)

    elif choice == "3":
        # Use feature branch
        success, error = GitUtils.checkout_branch(project_path, feature_branch)
        if success:
            console.print(f"[green]✓[/green] Using feature branch: {feature_branch}")
            return (True, feature_branch)
        else:
            console.print(f"[yellow]⚠[/yellow] Failed to checkout feature branch: {error}")
            return (False, feature_branch)

    elif choice == "4":
        # Select different existing branch
        console.print("\nAvailable branches:")
        for i, branch in enumerate(existing_branches, 1):
            marker = " (current)" if branch == current_branch else ""
            console.print(f"  {i}. {branch}{marker}")

        branch_choice = Prompt.ask(
            "\nSelect branch number",
            choices=[str(i) for i in range(1, len(existing_branches) + 1)]
        )
        selected_branch = existing_branches[int(branch_choice) - 1]

        success, error = GitUtils.checkout_branch(project_path, selected_branch)
        if success:
            console.print(f"[green]✓[/green] Checked out branch: {selected_branch}")
            return (True, selected_branch)
        else:
            console.print(f"[yellow]⚠[/yellow] Failed to checkout branch: {error}")
            return (False, feature_branch)

    return (False, feature_branch)


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
    type=click.Choice(["auto", "auto-ai", "manual", "skip"]),
    default="auto-ai",
    help="Verification mode: auto (evidence-based), auto-ai (AI agent), manual (user approval), skip (no verification)",
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

            # Discover ALL children (no assignee filter for team collaboration)
            # Remove assignee from sync_filters to get everyone's stories
            sync_filters_no_assignee = sync_filters.copy() if sync_filters else {}
            current_user_assignee = sync_filters_no_assignee.pop('assignee', None) if sync_filters_no_assignee else None

            # Also remove assignee from required_fields since we're using it for separation, not validation
            if 'required_fields' in sync_filters_no_assignee:
                required_fields = sync_filters_no_assignee['required_fields']
                try:
                    # Check type by name to avoid isinstance issues with typing module
                    type_name = type(required_fields).__name__
                    if type_name in ('list', 'tuple'):
                        # GitHub/GitLab format: ['assignee'] → []
                        sync_filters_no_assignee['required_fields'] = [f for f in required_fields if f != 'assignee']
                    elif type_name == 'dict':
                        # JIRA format: {Story: [sprint, assignee]} → {Story: [sprint]}
                        sync_filters_no_assignee['required_fields'] = {
                            issue_type: [f for f in fields if f != 'assignee']
                            for issue_type, fields in required_fields.items()
                        }
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Could not process required_fields: {e}")
                    console.print(f"[dim]Type: {type(required_fields)}, Value: {required_fields}[/dim]")
                    # Keep original value if we can't process it
                    pass

            console.print(f"[dim]Discovering all children (team collaboration mode)...[/dim]")

            try:
                children = discovery.discover_children(parent, sync_filters_no_assignee)
            except ValueError as e:
                console.print(f"[red]Error:[/red] {e}")
                sys.exit(1)

            if not children:
                console.print("[yellow]No children found[/yellow]")
                sys.exit(1)

            # Order by dependencies if requested
            if auto_order:
                console.print("[dim]Ordering by dependencies...[/dim]")
                children, warnings = discovery.order_by_dependencies(children)

                if warnings:
                    for warning in warnings:
                        console.print(f"[yellow]Warning:[/yellow] {warning}")

            # Resolve currentUser() for display purposes
            resolved_assignee = None
            if current_user_assignee:
                if hasattr(issue_tracker_client, 'resolve_assignee_for_comparison'):
                    resolved_assignee = issue_tracker_client.resolve_assignee_for_comparison(current_user_assignee)
                    if resolved_assignee and resolved_assignee != current_user_assignee:
                        console.print(f"[dim]Filtering by assignee: {resolved_assignee}[/dim]")
                else:
                    resolved_assignee = current_user_assignee

            # Separate children into "mine" (assigned to me) and "external" (assigned to others) FIRST
            # This allows us to display ownership in the table
            my_children = []
            external_children = []

            for child in children:
                child_assignee = child.get('assignee', '')

                # Check if meets criteria (other than assignee)
                meets_criteria = child.get('meets_criteria', True)

                # Check if assigned to current user
                is_mine = False
                if current_user_assignee:
                    if hasattr(issue_tracker_client, 'is_assigned_to'):
                        # Use JIRA client method for proper currentUser() handling
                        is_mine = issue_tracker_client.is_assigned_to(child_assignee, current_user_assignee)
                    elif child_assignee and resolved_assignee:
                        # Fallback for non-JIRA backends
                        is_mine = (resolved_assignee.lower() in child_assignee.lower())

                # Store ownership in child for display
                child['_ownership'] = 'yours' if is_mine else 'external'
                child['_will_create_session'] = is_mine and meets_criteria

                if is_mine and meets_criteria:
                    my_children.append(child)
                else:
                    external_children.append(child)

            # Display children with ownership information
            _display_children_with_ownership(children, parent, current_user_assignee)

            # DRY RUN MODE: Exit early if dry-run
            if dry_run:
                console.print("\n[bold cyan]DRY RUN:[/bold cyan] Feature preview\n")
                console.print(f"[dim]Feature name:[/dim] {name}")
                console.print(f"[dim]Branch:[/dim] {branch or f'feature/{name}'}")
                console.print(f"[dim]Your sessions:[/dim] {len(my_children)}")
                console.print(f"[dim]External sessions (tracked):[/dim] {len(external_children)}\n")

                console.print("\n[dim]No changes made (dry-run mode)[/dim]")
                console.print("[dim]Remove --dry-run to create the feature[/dim]")
                sys.exit(0)

            # Display summary
            console.print(f"\n[bold]Team Collaboration:[/bold]")
            console.print(f"  • Your sessions: {len(my_children)}")
            console.print(f"  • External sessions (tracked for dependencies): {len(external_children)}")

            if not my_children and not external_children:
                console.print(f"\n[red]Error:[/red] No children found after filtering")
                sys.exit(1)

            if not my_children:
                console.print(f"\n[yellow]⚠ Warning:[/yellow] No children assigned to you ({current_user_assignee})")
                console.print(f"[dim]All {len(children)} children are assigned to others or unassigned[/dim]\n")

                # Offer to assign unassigned children to yourself
                unassigned_children = [c for c in external_children if not c.get('assignee')]
                if unassigned_children:
                    console.print(f"[bold]Found {len(unassigned_children)} unassigned children:[/bold]")
                    for child in unassigned_children[:5]:  # Show first 5
                        console.print(f"  • {child['key']}: {child.get('summary', 'N/A')}")
                    if len(unassigned_children) > 5:
                        console.print(f"  ... and {len(unassigned_children) - 5} more")

                    console.print("\n[bold]Options:[/bold]")
                    console.print("  1. Assign all unassigned children to yourself (creates sessions)")
                    console.print("  2. Continue with external-only feature (just track them)")
                    console.print("  3. Cancel\n")

                    choice = click.prompt("Select option", type=int, default=1)

                    if choice == 1:
                        # Move unassigned children to my_children
                        my_children = unassigned_children
                        external_children = [c for c in external_children if c.get('assignee')]
                        console.print(f"\n[green]✓[/green] Assigned {len(my_children)} children to yourself")
                    elif choice == 2:
                        # Continue with empty my_children - feature will have no internal sessions
                        console.print(f"\n[cyan]Creating external-only feature (for tracking)[/cyan]")
                        session_list = []  # No internal sessions
                    elif choice == 3:
                        console.print("Cancelled")
                        sys.exit(0)
                else:
                    # All external children have other assignees
                    console.print("\n[bold]Options:[/bold]")
                    console.print("  1. Continue with external-only feature (just track them)")
                    console.print("  2. Cancel\n")

                    if not click.confirm("Continue with external-only feature?", default=False):
                        console.print("Cancelled")
                        sys.exit(0)

                    session_list = []  # No internal sessions

            # Check which of my children are missing sessions
            missing_sessions = []
            for child in my_children:
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

            # Initialize session_list (may already be [] for external-only features)
            if 'session_list' not in locals():
                session_list = []

            # Create sessions for my children only (assigned to current user)
            # Also collect blocking relationships for my sessions
            blocking_relationships = {}
            created_sessions = []

            # Skip session creation if external-only feature (no my_children)
            if not my_children:
                console.print(f"[dim]Creating external-only feature (no sessions to create)[/dim]\n")

            for child in my_children:
                child_key = child["key"]

                # Store blocking relationships
                blocking_relationships[child_key] = {
                    'blocks': child.get('blocks', []),
                    'blocked_by': child.get('blocked_by', []),
                }

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

                    # Populate issue metadata (including assignee and blocking relationships)
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

        # Check minimum sessions (allow 0 for external-only features)
        if len(session_list) == 0 and len(external_children) == 0:
            console.print("[red]Error:[/red] Feature must have at least 1 session or external dependency")
            sys.exit(1)
        elif len(session_list) == 1 and len(external_children) == 0:
            console.print("[red]Error:[/red] Feature with 1 session should use regular workflow, not feature orchestration")
            console.print("[dim]Feature orchestration is for multi-session workflows[/dim]")
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

        # Prepare metadata with blocking relationships
        metadata = {}
        if parent:
            metadata['blocking_relationships'] = blocking_relationships

        feature = feature_manager.create_feature(
            name=name,
            sessions=session_list,
            branch=branch,
            base_branch=base_branch,
            verification_mode=verify,
            workspace_name=workspace,
            parent_issue_key=parent if parent else None,
            external_sessions=external_children if parent else [],
            metadata=metadata,
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
                complete = len(feat.get_complete_sessions())
                total = len(feat.sessions)
                progress = f"{complete}/{total}"

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
    complete = len(feature.get_complete_sessions())
    total = len(feature.sessions)
    console.print(f"\n[bold]Progress:[/bold] {complete}/{total} sessions\n")

    # Completed sessions
    complete_sessions = feature.get_complete_sessions()
    if complete_sessions:
        console.print("[green]Completed:[/green]")
        for session_name in complete_sessions:
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
            "complete": "✓",
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

        # Use parent from feature metadata if not provided
        if not parent:
            if hasattr(feature, 'parent_issue_key') and feature.parent_issue_key:
                parent = feature.parent_issue_key
                console.print(f"[dim]Using parent from feature: {parent}[/dim]\n")
            else:
                console.print(f"[red]Error:[/red] --parent is required (feature has no stored parent)")
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

        # Get sync filters (without assignee for team collaboration)
        sync_filters = None
        current_user_assignee = None

        if backend == "jira" and config.jira and config.jira.filters:
            sync_filters_config = config.jira.filters.get("sync")
            if sync_filters_config:
                sync_filters = {
                    "status": sync_filters_config.status,
                    "required_fields": sync_filters_config.required_fields,
                }
                current_user_assignee = sync_filters_config.assignee
        elif backend == "github" and config.github and config.github.filters:
            sync_filters_config = config.github.filters.get("sync")
            if sync_filters_config:
                sync_filters = {
                    "status": sync_filters_config.status,
                    "required_fields": sync_filters_config.required_fields,
                }
                current_user_assignee = sync_filters_config.assignee
        elif backend == "gitlab" and config.gitlab and config.gitlab.filters:
            sync_filters_config = config.gitlab.filters.get("sync")
            if sync_filters_config:
                sync_filters = {
                    "status": sync_filters_config.status,
                    "required_fields": sync_filters_config.required_fields,
                }
                current_user_assignee = sync_filters_config.assignee

        console.print(f"[dim]Team collaboration mode: Discovering all children...[/dim]")

        # Remove assignee from sync_filters for team collaboration
        # Also remove assignee from required_fields since we're using it for separation
        sync_filters_no_assignee = sync_filters.copy() if sync_filters else {}
        if 'required_fields' in sync_filters_no_assignee:
            required_fields = sync_filters_no_assignee['required_fields']
            try:
                # Check type by name to avoid isinstance issues with typing module
                type_name = type(required_fields).__name__
                if type_name in ('list', 'tuple'):
                    # GitHub/GitLab format: ['assignee'] → []
                    sync_filters_no_assignee['required_fields'] = [f for f in required_fields if f != 'assignee']
                elif type_name == 'dict':
                    # JIRA format: {Story: [sprint, assignee]} → {Story: [sprint]}
                    sync_filters_no_assignee['required_fields'] = {
                        issue_type: [f for f in fields if f != 'assignee']
                        for issue_type, fields in required_fields.items()
                    }
            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Could not process required_fields: {e}")
                console.print(f"[dim]Type: {type(required_fields)}, Value: {required_fields}[/dim]")
                # Keep original value if we can't process it
                pass

        # Discover children (all, not filtered by assignee)
        from devflow.orchestration.parent_discovery import ParentTicketDiscovery
        discovery = ParentTicketDiscovery(issue_tracker_client)

        try:
            all_children = discovery.discover_children(parent, sync_filters_no_assignee)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)

        # Separate into my_children and external_children
        my_children = []
        external_children = []
        current_session_keys = set(feature.sessions)
        current_external_keys = set(ext['key'] for ext in feature.external_sessions)

        for child in all_children:
            child_key = child['key']
            child_assignee = child.get('assignee', '')
            meets_criteria = child.get('meets_criteria', True)

            # Check if assigned to current user
            is_mine = False
            if current_user_assignee:
                if hasattr(issue_tracker_client, 'is_assigned_to'):
                    # Use JIRA client method for proper currentUser() handling
                    is_mine = issue_tracker_client.is_assigned_to(child_assignee, current_user_assignee)
                elif child_assignee:
                    # Fallback for non-JIRA backends
                    is_mine = (current_user_assignee.lower() in child_assignee.lower())

            if is_mine and meets_criteria:
                # Mine and not already in feature.sessions
                if child_key not in current_session_keys:
                    my_children.append(child)
            else:
                # External - update existing or add new
                external_children.append(child)

        # Find new children (assigned to me, not already in feature.sessions)
        new_children = my_children

        if not new_children:
            console.print("[green]✓[/green] No new children to add")
            console.print("[dim]All children assigned to you are already in the feature[/dim]")

            # Still update external sessions even if no new children
            console.print(f"\n[dim]Updating external session statuses...[/dim]")
            feature.external_sessions = external_children
            feature_manager.update_feature(feature)
            console.print(f"[green]✓[/green] Updated {len(external_children)} external sessions")
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

        # Get or create blocking_relationships in metadata
        if not hasattr(feature, 'metadata') or not feature.metadata:
            feature.metadata = {}
        if 'blocking_relationships' not in feature.metadata:
            feature.metadata['blocking_relationships'] = {}

        # Create sessions for new children
        created_count = 0
        for child in new_children:
            child_key = child["key"]

            # Store blocking relationships for new child
            feature.metadata['blocking_relationships'][child_key] = {
                'blocks': child.get('blocks', []),
                'blocked_by': child.get('blocked_by', []),
            }

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

        # Update external_sessions with latest status
        console.print(f"\n[dim]Updating external session statuses...[/dim]")
        feature.external_sessions = external_children
        console.print(f"[green]✓[/green] Updated {len(external_children)} external sessions")

        # Save feature
        feature_manager.update_feature(feature)

        # Summary
        console.print(f"\n[green]✓[/green] Feature '{name}' updated")
        if created_count:
            console.print(f"[green]✓[/green] Created {created_count} new sessions")
        console.print(f"[dim]Total sessions:[/dim] {len(feature.sessions)}")
        console.print(f"[dim]External sessions (tracked):[/dim] {len(feature.external_sessions)}")

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
@click.option("--auto-advance", is_flag=True, help="Automatically open next session after each completion (no prompts)")
@require_experimental
@require_outside_claude
def run(name: str, auto_advance: bool):
    """Execute feature sessions sequentially.

    Automatically opens the first pending session and starts the workflow.
    After each session completion, either prompts or auto-advances to the next session.

    With --auto-advance: Skips prompts between sessions for continuous workflow.
    Without --auto-advance: Prompts "Open next session?" after each completion.
    """
    try:
        config_loader = ConfigLoader()
        feature_manager = FeatureManager(config_loader=config_loader)

        feature = feature_manager.get_feature(name)
        if not feature:
            console.print(f"[red]Error:[/red] Feature '{name}' not found")
            sys.exit(1)

        console.print(f"[bold]Feature:[/bold] {feature.name}")
        console.print(f"[dim]Sessions:[/dim] {len(feature.sessions)}")

        if auto_advance:
            console.print(f"[cyan]Mode:[/cyan] Auto-advance enabled (continuous workflow)\n")
        else:
            console.print(f"[cyan]Mode:[/cyan] Manual (prompts between sessions)\n")

        # Update status to running and store auto-advance preference
        feature.status = "running"
        if not hasattr(feature, 'metadata'):
            feature.metadata = {}
        feature.metadata['auto_advance'] = auto_advance
        feature_manager.update_feature(feature)

        # Show session execution order
        console.print("[bold]Execution order:[/bold]")
        for i, session_name in enumerate(feature.sessions, 1):
            status = feature.session_statuses.get(session_name, "pending")
            symbol = {
                "pending": "○",
                "running": "⧗",
                "complete": "✓",
                "paused": "⏸",
                "failed": "✗",
            }.get(status, "?")

            console.print(f"  {i}. {symbol} {session_name} ({status})")

        # Get first unblocked session (respects team dependencies)
        current = feature.get_first_unblocked_session()
        if current:
            console.print(f"\n[bold]Starting with:[/bold] {current}")
            console.print(f"\n[cyan]Opening first session...[/cyan]")
            from devflow.cli.commands.open_command import open_session
            open_session(identifier=current, skip_feature_warning=True)
        else:
            # Check if blocked by external sessions
            pending_sessions = [s for s in feature.sessions if feature.session_statuses.get(s) != "complete"]
            if pending_sessions:
                console.print(f"\n[yellow]⚠ All remaining sessions are blocked by external dependencies[/yellow]")
                console.print(f"\n[dim]Blocked sessions:[/dim]")
                for session_key in pending_sessions:
                    blocking_issues = feature.get_blocking_issues(session_key)
                    console.print(f"  • {session_key}")
                    console.print(f"    [dim]Blocked by:[/dim] {', '.join(blocking_issues)}")
                console.print(f"\n[cyan]Tip:[/cyan] Run 'daf -e feature sync {name}' to update external session statuses")
            else:
                console.print(f"\n[green]All sessions complete![/green]")
                console.print(f"\n[cyan]Next:[/cyan] daf -e feature complete {name}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        sys.exit(1)


@feature.command()
@click.argument("name")
@require_experimental
@require_outside_claude
def resume(name: str):
    """Resume feature workflow from where you left off.

    Smart resume that handles different scenarios:
    - Paused/failed session: Re-runs verification, then opens session
    - Running session: Opens the session to continue working
    - Completed session: Advances to next session and opens it
    - All complete: Shows feature complete message
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

        # Check if feature is complete
        if feature.status == "complete":
            console.print(f"[green]Feature '{name}' is already complete[/green]")
            if feature.pr_url:
                console.print(f"[dim]PR:[/dim] {feature.pr_url}")
            return

        console.print(f"[bold]Resuming feature:[/bold] {feature.name}\n")

        # Get first unblocked session (respects team dependencies)
        current_session = feature.get_first_unblocked_session()
        if not current_session:
            # Check if blocked by external sessions
            pending_sessions = [s for s in feature.sessions if feature.session_statuses.get(s) != "complete"]
            if pending_sessions:
                console.print(f"[yellow]⚠ All remaining sessions are blocked by external dependencies[/yellow]")
                console.print(f"\n[dim]Blocked sessions:[/dim]")
                for session_key in pending_sessions:
                    blocking_issues = feature.get_blocking_issues(session_key)
                    console.print(f"  • {session_key}")
                    console.print(f"    [dim]Blocked by:[/dim] {', '.join(blocking_issues)}")
                console.print(f"\n[cyan]Tip:[/cyan] Run 'daf -e feature sync {name}' to update external session statuses")
                sys.exit(1)
            else:
                console.print("[green]All sessions complete![/green]")
                console.print(f"\n[cyan]Next:[/cyan] daf -e feature complete {name}")
                sys.exit(0)

        # Get current session status
        session_status = feature.session_statuses.get(current_session, "pending")
        console.print(f"[dim]Current session:[/dim] {current_session}")
        console.print(f"[dim]Session status:[/dim] {session_status}\n")

        # Handle based on session status
        if session_status in ["paused", "failed"]:
            # Session paused due to verification failure - re-run verification
            console.print(f"[yellow]Session paused/failed[/yellow] - Re-running verification...\n")

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

            # If verification passed, advance and open next session
            if result.status == "passed":
                console.print(f"\n[green]✓ Verification passed![/green]")

                # Update session status
                feature.session_statuses[current_session] = "complete"

                # Move to next session or mark complete
                if not feature.advance_to_next_session():
                    console.print(f"\n[green]All sessions complete![/green]")
                    feature.status = "complete"
                    feature_manager.update_feature(feature)
                    console.print(f"\n[cyan]Next:[/cyan] daf -e feature complete {name}")
                else:
                    feature.status = "running"
                    feature_manager.update_feature(feature)
                    next_session = feature.get_first_unblocked_session()
                    if next_session:
                        console.print(f"\n[bold]Opening next session:[/bold] {next_session}")
                        from devflow.cli.commands.open_command import open_session
                        open_session(identifier=next_session, skip_feature_warning=True)
                    else:
                        console.print(f"\n[yellow]⚠ Next session is blocked by external dependencies[/yellow]")
                        console.print(f"\n[cyan]Tip:[/cyan] Run 'daf -e feature sync {name}' to update external session statuses")
            else:
                # Verification still has gaps - open session to fix
                console.print(f"\n[yellow]⚠ Verification still has gaps[/yellow]")

                if result.unverified_criteria:
                    console.print(f"\nUnverified criteria ({len(result.unverified_criteria)}):")
                    for criterion in result.unverified_criteria[:3]:
                        console.print(f"  • {criterion}")
                    if len(result.unverified_criteria) > 3:
                        console.print(f"  ... and {len(result.unverified_criteria) - 3} more")

                if result.suggestions:
                    console.print(f"\n[bold]Suggestions:[/bold]")
                    for suggestion in result.suggestions:
                        console.print(f"  • {suggestion}")

                console.print(f"\n[cyan]Opening session to fix issues:[/cyan] {current_session}")
                from devflow.cli.commands.open_command import open_session
                open_session(identifier=current_session, skip_feature_warning=True)

        elif session_status == "complete":
            # Session already complete - advance to next
            console.print(f"[green]Session already complete[/green] - Advancing to next...\n")

            if not feature.advance_to_next_session():
                console.print(f"[green]All sessions complete![/green]")
                feature.status = "complete"
                feature_manager.update_feature(feature)
                console.print(f"\n[cyan]Next:[/cyan] daf -e feature complete {name}")
            else:
                feature.status = "running"
                feature_manager.update_feature(feature)
                next_session = feature.get_first_unblocked_session()
                if next_session:
                    console.print(f"[bold]Opening next session:[/bold] {next_session}")
                    from devflow.cli.commands.open_command import open_session
                    open_session(identifier=next_session, skip_feature_warning=True)
                else:
                    console.print(f"\n[yellow]⚠ Next session is blocked by external dependencies[/yellow]")
                    console.print(f"\n[cyan]Tip:[/cyan] Run 'daf -e feature sync {name}' to update external session statuses")

        else:
            # Session is pending or running - just open it
            console.print(f"[cyan]Opening session:[/cyan] {current_session}")
            feature.status = "running"
            feature_manager.update_feature(feature)
            from devflow.cli.commands.open_command import open_session
            open_session(identifier=current_session, skip_feature_warning=True)

    except Exception as e:
        # Escape markup in error message to prevent Rich rendering issues
        from rich.markup import escape
        console.print(f"[red]Error:[/red] {escape(str(e))}")
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
        console.print(f"   • All {len(feature.sessions)} sessions complete")
        console.print(f"   • {verified_criteria}/{total_criteria} acceptance criteria verified")

        if feature.linked_issues:
            console.print(f"   • Linked issues: {', '.join(feature.linked_issues)}")

        console.print(f"\n3. Mark feature as complete:")

        # Mark feature as complete
        feature.status = "complete"
        feature.completed = datetime.now()
        feature_manager.update_feature(feature)

        console.print(f"   [green]✓ Feature marked as complete[/green]")

        # Transition parent epic if exists
        if feature.parent_issue_key:
            config = config_loader.load_config()

            # Only transition if JIRA is configured
            if config and config.jira:
                console.print(f"\n4. Transition parent epic:")
                console.print(f"   Parent: {feature.parent_issue_key}")

                from devflow.jira.transitions import transition_issue_interactive
                transition_issue_interactive(
                    issue_key=feature.parent_issue_key,
                    config=config
                )

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
                "complete": "✓",
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
                    "complete": "✓",
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
                    "complete": "✓",
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
                        "complete": "✓",
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
                        "complete": "✓",
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
