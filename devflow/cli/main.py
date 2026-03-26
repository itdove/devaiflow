"""Main CLI entry point for DevAIFlow."""

import functools
import sys
from typing import Optional
import click
from rich.console import Console

from devflow import __version__
from devflow.cli.completion import (
    complete_session_identifiers,
    complete_working_directories,
    complete_tags,
    complete_file_paths,
    complete_workspace_names,
)

console = Console()


# Common decorator for --json flag that can be used across all commands
def json_option(f):
    """Add --json option to a command.

    This decorator adds the --json flag and makes it available via the Click context.
    The flag can be placed anywhere in the command line.
    """
    @click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
    @click.pass_context
    @functools.wraps(f)
    def wrapper(ctx, output_json, **kwargs):
        # Store in context for nested access
        if not ctx.obj:
            ctx.obj = {}
        ctx.obj['output_json'] = output_json
        # Call the wrapped function directly with ctx as first parameter
        return f(ctx, **kwargs)
    return wrapper


# Common decorator for -w/--workspace flag (AAP-64296)
def workspace_option(help_text="Workspace name to use (overrides session default and config default)"):
    """Add -w/--workspace option to a command.

    This decorator adds the -w/--workspace flag to session creation commands.
    The workspace parameter is added to the function's kwargs.

    Args:
        help_text: Custom help text for the workspace option (default provided)

    Usage:
        @workspace_option()
        def my_command(ctx, workspace, **kwargs):
            # workspace is now available as a parameter
            pass
    """
    def decorator(f):
        return click.option("-w", "--workspace", help=help_text)(f)
    return decorator


def _check_mock_mode() -> None:
    """Check if mock mode is enabled and display a warning banner.

    This runs automatically before each command to alert users that they
    are working with mock data instead of real services.
    """
    import os
    import sys

    # Suppress output if --json flag is present
    if "--json" in sys.argv:
        return

    # Check if mock mode environment variable is set
    from devflow.utils import is_mock_mode
    from devflow.utils.paths import get_cs_home
    if is_mock_mode():
        cs_home = get_cs_home()
        console.print()
        console.print("[bold yellow]⚠️  MOCK MODE ENABLED ⚠️[/bold yellow]")
        console.print("[yellow]Using mock services - data is isolated from production[/yellow]")
        console.print(f"[dim]Mock data location: {cs_home}/mocks/[/dim]")
        console.print()


def _show_no_config_error() -> None:
    """Show comprehensive error message when no configuration is found.

    Provides guidance on:
    - Using daf init for personal/user configuration
    - Using workspace configuration for team collaboration
    - Where to find templates for all users
    """
    import os
    from pathlib import Path

    console.print("""[red]✗[/red] No configuration found.

[bold]Configuration Options:[/bold]

  [cyan]1. User Configuration[/cyan] (Personal setup)
     Run: [yellow]daf init[/yellow]
     Creates configuration in: $DEVAIFLOW_HOME (defaults to ~/.daf-sessions)

  [cyan]2. Workspace Configuration[/cyan] (Recommended for teams)
     Create config files in your workspace root:
       • backends/jira.json      - JIRA backend settings
       • organization.json        - Organization settings
       • team.json               - Team settings

     [bold]Templates:[/bold]
       Configuration templates: docs/config-templates/
       Or see: https://github.com/itdove/devaiflow/tree/main/docs/config-templates

     [dim]Workspace config files are automatically discovered when you
     run daf commands from within your workspace.[/dim]
""")


def _check_and_refresh_jira_fields() -> None:
    """Check if JIRA field cache is stale and refresh if needed.

    This runs automatically before each command to ensure field mappings
    are up-to-date. Runs only if:
    - Auto-refresh is enabled in config (default: True)
    - Cache is older than configured max age (default: 24 hours)
    - JIRA is configured with project key

    Failures are handled gracefully with warnings, allowing commands to continue.
    """
    from devflow.config.loader import ConfigLoader
    from devflow.jira.client import JiraClient
    from devflow.jira.field_mapper import JiraFieldMapper
    from datetime import datetime
    import os
    import sys

    # Suppress output if --json flag is present
    is_json_mode = "--json" in sys.argv

    # Skip in mock mode (mock tickets don't need field discovery)
    if os.getenv("DAF_MOCK_MODE") == "1":
        return

    # Only run if JIRA_API_TOKEN is set (avoid errors for non-JIRA usage)
    if not os.getenv("JIRA_API_TOKEN"):
        return

    try:
        config_loader = ConfigLoader()

        # Load config (silently return if no config exists)
        if not config_loader.config_file.exists():
            return

        config = config_loader.load_config()
        if not config or not config.jira or not config.jira.project:
            return

        # Check if auto-refresh is disabled
        if not config.jira.field_cache_auto_refresh:
            return

        # Check if cache is stale
        jira_client = JiraClient()
        field_mapper = JiraFieldMapper(jira_client, config.jira.field_mappings)

        max_age_hours = config.jira.field_cache_max_age_hours
        is_stale = field_mapper.is_cache_stale(
            config.jira.field_cache_timestamp,
            max_age_hours=max_age_hours
        )

        if not is_stale:
            return

        # Cache is stale - refresh it
        if not is_json_mode:
            console.print("[dim]Refreshing JIRA field mappings...[/dim]")

        field_mappings = field_mapper.discover_fields(config.jira.project)

        # Update config with fresh mappings and timestamp
        config.jira.field_mappings = field_mappings
        config.jira.field_cache_timestamp = datetime.now().isoformat()

        # Save WITHOUT patches to persist the discovered field IDs
        config_loader.save_config(config)

        # Reload config WITH patches to reapply patch-provided metadata like required_for
        # This ensures that patch-provided field metadata is not lost after auto-refresh
        config = config_loader.load_config()

        # Save again with patches applied to merge discovered fields + patch metadata
        config_loader.save_config(config)

        if not is_json_mode:
            console.print("[dim]✓ Field mappings refreshed[/dim]")

    except Exception as e:
        # Gracefully handle errors - warn but don't block the command
        if not is_json_mode:
            console.print(f"[yellow]⚠[/yellow] [dim]Could not auto-refresh JIRA fields: {e}[/dim]")
            console.print("[dim]  Continuing with cached mappings...[/dim]")


def _check_for_updates() -> None:
    """Check for available updates and show notification if found.

    This runs automatically before each command to notify users of new versions.
    Only runs when:
    - Installed via pip (not in development/editable mode)
    - Cache is stale (last check > 24 hours ago)
    - Not in JSON output mode

    Shows warning if GitLab is unreachable (VPN not connected).
    Other failures are handled silently - never blocks command execution.
    """
    import sys

    # Suppress output if --json flag is present
    if "--json" in sys.argv:
        return

    try:
        from devflow.utils.update_checker import check_for_updates, show_update_notification, show_network_warning

        # Check for updates (uses cache, only fetches if stale)
        latest_version, network_error = check_for_updates()

        if network_error:
            # PyPI unreachable - network connectivity issue
            show_network_warning()
        elif latest_version:
            # Update available
            show_update_notification(latest_version)

    except Exception:
        # Silently handle any other errors - never block the command
        pass


def _version_callback(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Handle --version flag with optional JSON output support."""
    if not value or ctx.resilient_parsing:
        return

    # Check if --json flag is present using sys.argv
    # This works in real CLI usage.  For tests, we'll need to mock sys.argv.
    import sys
    import json as json_module

    output_json = '--json' in sys.argv

    if output_json:
        # JSON output mode
        print(json_module.dumps({"version": __version__}))
    else:
        # Plain text output (Click's default format)
        print(f"cli, version {__version__}")
    ctx.exit(0)


@click.group(context_settings={'ignore_unknown_options': True, 'allow_extra_args': True})
@click.option('--version', is_flag=True, callback=_version_callback, expose_value=False, is_eager=True, help='Show version and exit')
@click.option('--non-interactive', is_flag=True, help='Non-interactive mode: error if required parameters missing (no prompts)')
@click.pass_context
def cli(ctx: click.Context, non_interactive: bool) -> None:
    """DevAIFlow - Manage Claude Code sessions with JIRA integration."""
    import sys

    ctx.ensure_object(dict)

    # Store non-interactive flag in context for all commands to access
    ctx.obj['non_interactive'] = non_interactive

    # Also set environment variable for child processes and utility functions
    if non_interactive:
        import os
        os.environ['DAF_NON_INTERACTIVE'] = '1'

    # Check and display mock mode warning if enabled
    _check_mock_mode()

    # Check for available updates (non-intrusive notification)
    # _check_for_updates()  # TODO: Re-enable after fixing

    # Auto-refresh JIRA field mappings if stale
    # Skip auto-refresh for 'init' command to avoid conflicts with init's own field discovery logic
    # Use click's invoked_subcommand to check which command is being run
    # Note: invoked_subcommand is None until after this function returns, so we check sys.argv
    if len(sys.argv) > 1:
        # Check if the first argument after the script name is 'init'
        # This works both in direct invocation and in test environments
        command = sys.argv[1]
        if command == 'init' or (command.startswith('-') and 'init' in sys.argv):
            # Don't auto-refresh during init command - init handles its own field discovery
            return

    _check_and_refresh_jira_fields()


@cli.command()
@click.option("--name", help="Session name (will prompt if not provided)")
@click.option("--goal", help="Session goal/description (supports auto-detection of file:// paths and http(s):// URLs)")
@click.option("--goal-file", help="Explicit file path or URL for goal input (mutually exclusive with --goal)")
@click.option("--jira", help="issue tracker key (optional, e.g., PROJ-12345)")
@click.option("--working-directory", help="Working directory name (defaults to directory name)")
@click.option("--path", help="Project path (defaults to current directory)")
@click.option("--branch", help="Git branch name (optional)")
@click.option("--template", help="Template name to use for session configuration")
@workspace_option()
@click.option("--projects", help="Comma-separated list of repository names for multi-project sessions (requires --workspace)")
@click.option("--new-session", is_flag=True, help="Force creation of new session instead of adding conversation to existing session")
@click.option("--model-profile", help="Model provider profile to use (e.g., 'vertex', 'llama-cpp')")
@click.option("--create-branch/--no-create-branch", default=None, help="Control branch creation (default: prompt)")
@click.option("--source-branch", help="Source branch to create new branch from (default: base branch)")
@click.option("--on-branch-exists", type=click.Choice(['error', 'use-existing', 'add-suffix', 'skip'], case_sensitive=False), help="Action when branch already exists")
@click.option("--allow-uncommitted", is_flag=True, help="Allow uncommitted changes when switching branches")
@click.option("--sync-upstream/--no-sync-upstream", default=None, help="Sync with upstream before creating branch (default: prompt)")
@click.option("--auto-workspace", is_flag=True, help="Auto-select workspace without prompting")
@click.option("--session-index", type=int, help="Select existing session by index (for multi-session selection)")
@json_option
def new(ctx: click.Context, name: str, goal: str, goal_file: str, jira: str, working_directory: str, path: str, branch: str, template: str, workspace: str, projects: str, new_session: bool, model_profile: str, create_branch: bool, source_branch: str, on_branch_exists: str, allow_uncommitted: bool, sync_upstream: bool, auto_workspace: bool, session_index: int) -> None:
    """Create a new session or add conversation to existing session.

    By default, if a session already exists with the same name, this command will
    add a new conversation to that session (multi-conversation architecture).

    Use --new-session to create a separate session in the same group instead.
    This is useful for different approaches, phases, or experiments.

    Use --projects with --workspace to work across multiple repositories simultaneously.
    Example: daf new PROJ-123 -w primary --projects backend-api,frontend-app,shared-lib

    Issue tracker integration is optional. Use 'daf link' to associate a issue tracker ticket later.

    Use --template to create a session from a saved template configuration.
    """
    from devflow.cli.commands.new_command import create_new_session
    from devflow.cli.utils import process_goal_options
    from rich.prompt import Prompt
    from rich.console import Console

    console = Console()

    # Validate name if provided (distinguish between None and empty string)
    # None = not provided (prompt user), '' = explicitly empty (error)
    if name is not None and not name.strip():
        console.print("[red]✗[/red] Session name cannot be empty")
        sys.exit(1)

    # Validate goal if provided (distinguish between None and empty string)
    # None = not provided (OK, goal is optional), '' = explicitly empty (error)
    # Exception: empty goal is OK if JIRA is provided (goal will come from JIRA title)
    if goal is not None and not goal.strip() and not jira:
        console.print("[red]✗[/red] Goal cannot be empty (omit --goal flag if not needed)")
        sys.exit(1)

    # Validate goal_file if provided (distinguish between None and empty string)
    if goal_file is not None and not goal_file.strip():
        console.print("[red]✗[/red] Goal file cannot be empty (omit --goal-file flag if not needed)")
        sys.exit(1)

    # Prompt for name if not provided
    if name is None:
        if jira:
            # Suggest issue key as name
            name = Prompt.ask("Session group name", default=jira)
        else:
            name = Prompt.ask("Session group name")

        # Validate prompted name is not empty
        if not name or not name.strip():
            console.print("[red]✗[/red] Session name cannot be empty")
            sys.exit(1)

    # Prompt for goal if not provided (allow empty input since goal is optional for daf new)
    if not goal and not goal_file and not jira:
        goal = click.prompt("Enter session goal/description (optional, press Enter to skip)", default="", show_default=False)
        if not goal:  # Convert empty string to None
            goal = None

    # Process --goal and --goal-file options (mutual exclusion and resolution)
    goal = process_goal_options(goal, goal_file)

    # Validate --projects requires --workspace
    if projects and not workspace:
        console.print("[red]✗[/red] --projects requires --workspace to be specified")
        console.print("[dim]Example: daf new PROJ-123 -w primary --projects backend-api,frontend-app[/dim]")
        sys.exit(1)

    # Get output_json flag from context
    output_json = ctx.obj.get('output_json', False) if ctx.obj else False

    create_new_session(
        name,
        goal,
        working_directory,
        path,
        branch,
        jira,
        template,
        workspace,
        projects,
        new_session,
        model_profile,
        output_json,
        create_branch=create_branch,
        source_branch=source_branch,
        on_branch_exists=on_branch_exists,
        allow_uncommitted=allow_uncommitted,
        sync_upstream=sync_upstream,
        auto_workspace=auto_workspace,
        session_index=session_index,
    )


@cli.command()
@click.argument("identifier", shell_complete=complete_session_identifiers)
@click.option("--edit", is_flag=True, help="Edit session metadata via TUI instead of opening")
@click.option("--path", help="Project path (auto-detects conversation in multi-conversation sessions)")
@workspace_option("Workspace name to use (overrides session stored workspace)")
@click.option("--projects", help="Add multiple projects to session (comma-separated, requires --workspace)")
@click.option("--new-conversation", is_flag=True, help="Create a new conversation (archive current and start fresh)")
@click.option("--conversation-id", help="Resume a specific archived conversation by its UUID")
@click.option("--model-profile", help="Model provider profile to use (overrides session default)")
@click.option("--create-branch/--no-create-branch", default=None, help="Control branch creation when adding projects (default: prompt)")
@click.option("--source-branch", help="Source branch for new branches when adding projects")
@click.option("--on-branch-exists", type=click.Choice(['error', 'use-existing', 'add-suffix', 'skip'], case_sensitive=False), help="Action when branch exists when adding projects")
@click.option("--allow-uncommitted", is_flag=True, help="Allow uncommitted changes when switching branches")
@click.option("--sync-upstream/--no-sync-upstream", default=None, help="Sync with upstream when opening session (default: prompt)")
@click.option("--auto-workspace", is_flag=True, help="Auto-select workspace without prompting")
@click.option("--sync-strategy", type=click.Choice(['merge', 'rebase', 'skip'], case_sensitive=False), help="Strategy for syncing with upstream (merge/rebase/skip)")
@json_option
def open(ctx: click.Context, identifier: str, edit: bool, path: str, workspace: str, projects: str, new_conversation: bool, conversation_id: str, model_profile: str, create_branch: bool, source_branch: str, on_branch_exists: str, allow_uncommitted: bool, sync_upstream: bool, auto_workspace: bool, sync_strategy: str) -> None:
    """Open/resume an existing session.

    IDENTIFIER can be either a session group name or issue tracker key.

    Use --path to specify which project to work on when the session has
    multiple conversations (multi-repository work). The path can be:
    - An absolute path to a repository
    - A repository name from workspace
    - Current directory (if not specified)

    Use --projects to add multiple projects to the session at once (batch mode).
    This requires --workspace and will prompt for branch creation for each project.

    Use --new-conversation to start a fresh Claude session when context becomes too long.
    This archives the current conversation and creates a new one.

    Use --conversation-id to resume a specific archived conversation by its UUID.
    Find conversation UUIDs with: daf info <session-name>

    Examples:
        # Open existing single-project session
        daf open PROJ-123

        # Switch to specific project in multi-project session
        daf open PROJ-123 --path backend

        # Add multiple projects to existing session
        daf open PROJ-123 -w primary --projects backend,frontend,shared
    """
    # Handle --edit flag (edit session metadata via TUI)
    if edit:
        from devflow.ui.session_editor_tui import run_session_editor_tui
        run_session_editor_tui(identifier)
        return

    from devflow.cli.commands.open_command import open_session

    # Validate --projects and --path are mutually exclusive
    if path and projects:
        console.print("[red]✗[/red] Cannot use both --path and --projects at the same time")
        console.print("[dim]Use --path to select one project, or --projects to add multiple[/dim]")
        sys.exit(1)

    # Validate --projects requires --workspace
    if projects and not workspace:
        console.print("[red]✗[/red] --projects requires --workspace to be specified")
        console.print("[dim]Example: daf open PROJ-123 -w primary --projects backend,frontend[/dim]")
        sys.exit(1)

    open_session(
        identifier,
        output_json=ctx.obj.get('output_json', False),
        path=path,
        workspace=workspace,
        projects=projects,
        new_conversation=new_conversation,
        conversation_id=conversation_id,
        model_profile=model_profile,
        create_branch=create_branch,
        source_branch=source_branch,
        on_branch_exists=on_branch_exists,
        allow_uncommitted=allow_uncommitted,
        sync_upstream=sync_upstream,
        auto_workspace=auto_workspace,
        sync_strategy=sync_strategy,
    )


@cli.group()
@json_option
def session(ctx: click.Context) -> None:
    """Manage sessions and their projects/conversations."""
    pass


@session.command(name="list-conversations")
@click.argument("identifier", shell_complete=complete_session_identifiers)
@json_option
def session_list_conversations_cmd(ctx: click.Context, identifier: str) -> None:
    """List all conversations for a session.

    Shows all Claude Code conversations (active and archived) across all repositories
    in the session.

    IDENTIFIER can be either a session name or issue tracker key.

    Example:
        daf session list-conversations PROJ-12345
        daf session list-conversations my-session --json
    """
    from devflow.cli.commands.sessions_list_command import sessions_list

    sessions_list(identifier, output_json=ctx.obj.get('output_json', False))


@session.command(name="add-project")
@click.argument("session_name", shell_complete=complete_session_identifiers)
@click.argument("project_name", required=False)
@workspace_option()
@click.option("--projects", help="Add multiple projects (comma-separated)")
@click.option("--branch", help="Shared branch name for all projects (optional)")
def session_add_project(session_name: str, project_name: Optional[str], workspace: str, projects: Optional[str], branch: Optional[str]) -> None:
    """Add project(s) to an existing session.

    Add one or more projects/repositories to a multi-project session. Each project
    will get its own conversation with separate git branch.

    Examples:
        # Add one project
        daf session add-project PROJ-123 backend-api -w primary

        # Add multiple projects at once
        daf session add-project PROJ-123 --projects backend,frontend,shared -w primary

        # Add with specific branch name
        daf session add-project PROJ-123 backend-api -w primary --branch feature/api
    """
    from devflow.cli.commands.session_project_command import add_project_to_session

    # Validation
    if not project_name and not projects:
        console.print("[red]✗[/red] Must specify either PROJECT_NAME or --projects")
        console.print("[dim]Examples:[/dim]")
        console.print("[dim]  daf session add-project PROJ-123 backend-api -w primary[/dim]")
        console.print("[dim]  daf session add-project PROJ-123 --projects backend,frontend -w primary[/dim]")
        sys.exit(1)

    if project_name and projects:
        console.print("[red]✗[/red] Cannot use both PROJECT_NAME and --projects")
        sys.exit(1)

    if not workspace:
        console.print("[red]✗[/red] --workspace is required")
        console.print("[dim]Example: daf session add-project PROJ-123 backend-api -w primary[/dim]")
        sys.exit(1)

    # Build project list
    project_list = [project_name] if project_name else projects.split(',')
    project_list = [p.strip() for p in project_list]

    add_project_to_session(session_name, project_list, workspace, branch)


@session.command(name="remove-project")
@click.argument("session_name", shell_complete=complete_session_identifiers)
@click.argument("project_name")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def session_remove_project(session_name: str, project_name: str, force: bool) -> None:
    """Remove a project from a session.

    Removes a project/conversation from a multi-project session. The project's
    conversation history will be deleted.

    Example:
        daf session remove-project PROJ-123 old-service
        daf session remove-project PROJ-123 backend-api --force
    """
    from devflow.cli.commands.session_project_command import remove_project_from_session

    remove_project_from_session(session_name, project_name, force)


@session.command(name="set-workspace")
@click.argument("session_name", shell_complete=complete_session_identifiers)
@click.argument("workspace_name", shell_complete=complete_workspace_names)
def session_set_workspace(session_name: str, workspace_name: str) -> None:
    """Set the workspace for a session.

    Changes which workspace a session uses. This persists and will be used
    when the session is reopened with 'daf open'.

    Example:
        daf session set-workspace PROJ-123 production
        daf session set-workspace my-session experiments
    """
    from devflow.cli.commands.session_project_command import set_workspace_for_session

    set_workspace_for_session(session_name, workspace_name)


# ============================================================================
# Maintenance Command Group (Hidden)
# ============================================================================


@cli.group(hidden=True)
@json_option
def maintenance(ctx: click.Context) -> None:
    """Maintenance and repair commands (hidden utilities)."""
    pass


@maintenance.command(name="cleanup-sessions")
@click.option("--dry-run", is_flag=True, help="Show what would be cleaned without actually cleaning")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@json_option
def maintenance_cleanup_sessions_cmd(ctx: click.Context, dry_run: bool, force: bool) -> None:
    """Find and fix orphaned sessions (sessions with missing conversation files)."""
    from devflow.cli.commands.cleanup_sessions_command import cleanup_sessions

    cleanup_sessions(dry_run=dry_run, force=force)


@maintenance.command(name="rebuild-index")
@click.option("--dry-run", is_flag=True, help="Show what would be rebuilt without actually rebuilding")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@json_option
def maintenance_rebuild_index_cmd(ctx: click.Context, dry_run: bool, force: bool) -> None:
    """Rebuild sessions.json index from session directories."""
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    rebuild_index(dry_run=dry_run, force=force)


@maintenance.command(name="repair-conversation")
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--conversation-id", type=int, help="Repair specific conversation by number (1, 2, 3...)")
@click.option("--max-size", type=int, default=10000, help="Maximum size for content truncation (default: 10000 chars)")
@click.option("--check-all", is_flag=True, help="Check all sessions for corruption (dry run)")
@click.option("--all", "repair_all", is_flag=True, help="Repair all corrupted sessions found")
@click.option("--dry-run", is_flag=True, help="Report issues without making changes")
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def maintenance_repair_conversation_cmd(ctx: click.Context, identifier: str, conversation_id: int, max_size: int, check_all: bool, repair_all: bool, dry_run: bool, latest: bool) -> None:
    """Repair corrupted Claude Code conversation files."""
    from devflow.cli.commands.repair_conversation_command import repair_conversation

    repair_conversation(
        identifier=identifier,
        conversation_id=conversation_id,
        max_size=max_size,
        check_all=check_all,
        repair_all=repair_all,
        dry_run=dry_run,
        latest=latest,
    )


@maintenance.command(name="cleanup-conversation")
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--older-than", help="Remove messages older than duration (e.g., '2h', '1d', '30m')")
@click.option("--keep-last", type=int, help="Keep only the last N messages")
@click.option("--dry-run", is_flag=True, help="Show what would be removed without actually removing")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.option("--list-backups", is_flag=True, help="List available backups for this session")
@click.option("--restore-backup", help="Restore from a specific backup (timestamp)")
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def maintenance_cleanup_conversation_cmd(ctx: click.Context, identifier: str, older_than: str, keep_last: int, dry_run: bool, force: bool, list_backups: bool, restore_backup: str, latest: bool) -> None:
    """Clean up Claude Code conversation history to reduce context size."""
    from devflow.cli.commands.cleanup_conversation_command import cleanup_conversation

    cleanup_conversation(
        identifier=identifier,
        older_than=older_than,
        keep_last=keep_last,
        dry_run=dry_run,
        force=force,
        list_backups=list_backups,
        restore_backup=restore_backup,
        latest=latest,
    )


@maintenance.command(name="discover")
@json_option
def maintenance_discover_cmd(ctx: click.Context) -> None:
    """Discover existing Claude Code sessions not managed by daf tool."""
    from devflow.cli.commands.discover_command import discover_sessions

    discover_sessions()


@cli.command()
@click.option("--active", is_flag=True, help="Show only active sessions")
@click.option("--status", help="Filter by session status: created, in_progress, paused, complete (comma-separated for multiple)")
@click.option("--working-directory", shell_complete=complete_working_directories, help="Filter by working directory")
@click.option("--field", multiple=True, help="Filter by custom field (format: field_name=value, can be specified multiple times)")
@click.option("--issue-status", help="Filter by issue tracker status (comma-separated for multiple)")
@click.option("--since", help="Filter by sessions active since this time (e.g., 'last week', '3 days ago', '2025-01-01')")
@click.option("--before", help="Filter by sessions active before this time")
@click.option("--limit", type=int, default=25, help="Number of sessions to show per page (default: 25)")
@click.option("--page", type=int, default=None, help="Page number to display (non-interactive mode)")
@click.option("--all", "show_all", is_flag=True, help="Show all sessions without pagination")
@json_option
def list(
    ctx: click.Context,
    active: bool,
    status: str,
    working_directory: str,
    field: tuple,
    issue_status: str,
    since: str,
    before: str,
    limit: int,
    page: int,
    show_all: bool,
) -> None:
    """List all sessions with enhanced filtering and pagination.

    \b
    Valid status values:
        created, in_progress, paused, complete

    \b
    Filter by multiple statuses:
        daf list --status in_progress,complete

    \b
    Filter by time range:
        daf list --since "last week"
        daf list --since "3 days ago" --before "yesterday"
        daf list --since "2025-01-01"

    \b
    Filter by issue status:
        daf list --issue-status "Code Review,In Progress"

    \b
    Pagination (Interactive by default):
        daf list                     # Interactive mode: browse pages with Enter/'q'
        daf list --limit 10          # Interactive mode with 10 sessions per page
        daf list --page 2            # Non-interactive: show only page 2
        daf list --limit 10 --page 2 # Non-interactive: show 10 sessions on page 2
        daf list --all               # Show all sessions without pagination

    \b
    Combine multiple filters:
        daf list --status in_progress --since "last week" --working-directory backend-api
    """
    from devflow.cli.commands.list_command import list_sessions

    # --active flag takes precedence over --status
    if active and not status:
        status = "in_progress"

    # Parse field filters from tuple of "field_name=value" strings
    issue_metadata_filters = {}
    for field_filter in field:
        if '=' in field_filter:
            field_name, field_value = field_filter.split('=', 1)
            issue_metadata_filters[field_name.strip()] = field_value.strip()

    list_sessions(
        status=status,
        working_directory=working_directory,
        issue_metadata_filters=issue_metadata_filters,
        issue_status=issue_status,
        since=since,
        before=before,
        limit=limit,
        page=page,
        show_all=show_all,
        output_json=ctx.obj.get('output_json', False),
    )


@cli.command()
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.argument("note", required=False)
@click.option("--jira", "sync_to_jira", is_flag=True, help="Also add note as JIRA comment")
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def note(ctx: click.Context, identifier: str, note: str, sync_to_jira: bool, latest: bool) -> None:
    """Add a note to a session.

    IDENTIFIER can be either a session group name or issue tracker key.
    If not provided and --latest is not specified, uses the most recent active session.
    Use --latest to explicitly use the most recently active session.

    Notes are always saved locally. Use --jira flag to also add as JIRA comment
    (requires session to have a issue key).
    """
    from devflow.cli.commands.note_command import add_note

    add_note(identifier, note, sync_to_jira=sync_to_jira, latest=latest)


@cli.command()
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--latest", is_flag=True, help="View notes for the most recently active session")
@json_option
def notes(ctx: click.Context, identifier: str, latest: bool) -> None:
    """View notes for a session.

    IDENTIFIER can be either a session group name or issue tracker key.
    If not provided and --latest is not specified, uses the most recent active session.
    Use --latest to explicitly view notes for the most recently active session.

    Notes are displayed in chronological order.
    """
    from devflow.cli.commands.note_command import view_notes

    view_notes(identifier, latest=latest)


@cli.command()
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--status", help="Target issue status")
@click.option("--attach-to-issue", is_flag=True, help="Export session group and attach to issue tracker ticket")
@click.option("--latest", is_flag=True, help="Complete the most recently active session")
@click.option("--no-commit", is_flag=True, help="Skip git commit (don't commit changes)")
@click.option("--no-pr", is_flag=True, help="Skip PR/MR creation (don't create pull request)")
@click.option("--no-issue-update", is_flag=True, help="Skip issue tracker updates (don't add summary or update fields)")
@json_option
def complete(ctx: click.Context, identifier: str, status: str, attach_to_issue: bool, latest: bool, no_commit: bool, no_pr: bool, no_issue_update: bool) -> None:
    """Mark a session as complete.

    IDENTIFIER can be either a session group name or issue tracker key.
    If --latest is specified, completes the most recently active session without requiring an identifier.

    Use --attach-to-issue to export the session group and attach it to the issue tracker ticket
    for team handoff or documentation. The export includes conversation history.

    The --no-commit, --no-pr, and --no-issue-update flags skip interactive prompts for automated workflows.
    """
    from devflow.cli.commands.complete_command import complete_session

    complete_session(identifier, status, attach_to_issue, latest, no_commit, no_pr, no_issue_update)


@cli.command()
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--all", "delete_all", is_flag=True, help="Delete all sessions")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.option("--keep-metadata", is_flag=True, help="Keep session files (notes, metadata) on disk")
@click.option("--latest", is_flag=True, help="Delete the most recently active session")
@json_option
def delete(ctx: click.Context, identifier: str, delete_all: bool, force: bool, keep_metadata: bool, latest: bool) -> None:
    """Delete a session or all sessions.

    IDENTIFIER can be either a session group name or issue tracker key.
    Use --latest to delete the most recently active session.

    By default, both the session index entry and session files are deleted.
    Use --keep-metadata to preserve session files (notes.md, metadata.json, etc.).
    """
    from devflow.cli.commands.delete_command import delete_session

    delete_session(identifier, delete_all=delete_all, force=force, keep_metadata=keep_metadata, latest=latest)


@cli.command()
@click.argument("identifier", shell_complete=complete_session_identifiers)
@click.option("--session-id", "ai_agent_session_id", help="Claude session UUID")
@json_option
def update(ctx: click.Context, identifier: str, ai_agent_session_id: str) -> None:
    """Update session with Claude session ID.

    IDENTIFIER can be either a session group name or issue tracker key.
    """
    from devflow.cli.commands.update_command import update_session

    update_session(identifier, ai_agent_session_id)


@cli.command()
@click.argument("query", required=False)
@click.option("--tag", shell_complete=complete_tags, help="Filter by tag")
@click.option("--working-directory", shell_complete=complete_working_directories, help="Filter by working directory")
@json_option
def search(ctx: click.Context, query: str, tag: str, working_directory: str) -> None:
    """Search sessions."""
    from devflow.cli.commands.search_command import search_sessions

    search_sessions(query=query, tag=tag, working_directory=working_directory)


@cli.command()
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def time(ctx: click.Context, identifier: str, latest: bool) -> None:
    """Show time tracking for a session.

    IDENTIFIER can be either a session group name or issue tracker key.
    If not provided or --latest is specified, uses the most recently active session.
    """
    from devflow.cli.commands.time_command import show_time

    show_time(identifier, latest=latest)


@cli.command()
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def pause(ctx: click.Context, identifier: str, latest: bool) -> None:
    """Pause time tracking for a session.

    IDENTIFIER can be either a session group name or issue tracker key.
    If not provided or --latest is specified, uses the most recently active session.
    """
    from devflow.cli.commands.pause_command import pause_time_tracking

    pause_time_tracking(identifier, latest=latest)


@cli.command()
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def resume(ctx: click.Context, identifier: str, latest: bool) -> None:
    """Resume time tracking for a session.

    IDENTIFIER can be either a session group name or issue tracker key.
    If not provided or --latest is specified, uses the most recently active session.
    """
    from devflow.cli.commands.resume_command import resume_time_tracking

    resume_time_tracking(identifier, latest=latest)


@cli.command()
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--detail", is_flag=True, help="Show full file lists and commands")
@click.option("--ai-summary", is_flag=True, help="Use AI to generate intelligent summary (requires API key)")
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def summary(ctx: click.Context, identifier: str, detail: bool, ai_summary: bool, latest: bool) -> None:
    """Display session summary without opening Claude Code.

    IDENTIFIER can be either a session group name or issue tracker key.
    If --latest is specified, uses the most recently active session.

    Shows what happened in the session (condensed by default):
    - File change counts
    - Tool usage statistics
    - Last activity message

    Use --detail to see full lists of files and commands.
    Use --ai-summary to generate an intelligent AI-powered summary.
    """
    from devflow.cli.commands.summary_command import show_summary

    show_summary(identifier, detail=detail, ai_summary=ai_summary, latest=latest)


@cli.command(name="info")
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--uuid-only", is_flag=True, help="Output only the Claude session UUID (for scripting)")
@click.option("--conversation-id", type=int, help="Show specific conversation by number (1, 2, 3...)")
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def info_cmd(ctx: click.Context, identifier: str, uuid_only: bool, conversation_id: int, latest: bool) -> None:
    """Show detailed session information including Claude Code UUIDs.

    IDENTIFIER can be a session name, issue key, or omitted to show the most recent session.
    Use --latest to explicitly use the most recently active session.

    \b
    Examples:
        daf info                    # Show most recent session
        daf info --latest           # Show most recent session (explicit)
        daf info PROJ-60039          # Show by issue key
        daf info my-session         # Show by session name
        daf info PROJ-60039 --uuid-only  # Get UUID for scripting
        daf info PROJ-60039 --conversation-id 1  # Show specific conversation
    """
    from devflow.cli.commands.info_command import session_info

    session_info(identifier, uuid_only, conversation_id, latest=latest, output_json=ctx.obj.get('output_json', False))


@cli.command(hidden=True)
@click.argument("identifier", required=True, shell_complete=complete_session_identifiers)
def edit(identifier: str) -> None:
    """[Hidden] Edit session metadata interactively via TUI.

    Use 'daf open <identifier> --edit' instead.

    IDENTIFIER can be a session name or issue key.

    \b
    Examples:
        daf edit PROJ-60989          # Edit by issue key (old)
        daf open PROJ-60989 --edit   # Edit by issue key (new)
        daf edit my-session          # Edit by session name (old)
        daf open my-session --edit   # Edit by session name (new)
    """
    from devflow.ui.session_editor_tui import run_session_editor_tui

    run_session_editor_tui(identifier)


@cli.command()
@json_option
def status(ctx: click.Context) -> None:
    """Show sprint status."""
    from devflow.cli.commands.status_command import show_status

    show_status(output_json=ctx.obj.get('output_json', False))


@cli.command()
@json_option
def active(ctx: click.Context) -> None:
    """Show currently active Claude Code conversation."""
    from devflow.cli.commands.active_command import show_active

    show_active(output_json=ctx.obj.get('output_json', False))


@cli.command()
@click.option("--field", multiple=True, help="Filter by custom field (format: field_name=value, can be specified multiple times)")
@click.option("--type", "ticket_type", help="Filter by ticket type")
@click.option("--epic", help="Filter by epic")
@click.option("-w", "--workspace", help="Limit sync to specific workspace (name from config)")
@click.option("--repository", "--repo", help="Limit sync to specific repository (format: owner/repo)")
@click.option("--jira", is_flag=True, help="Force JIRA sync (can be combined with workspace/repository filters)")
@json_option
def sync(ctx: click.Context, field: tuple, ticket_type: str, epic: str, workspace: str, repository: str, jira: bool) -> None:
    """Sync with configured issue trackers (JIRA, GitHub, GitLab).

    Smart sync automatically determines what to sync based on parameters:

    - daf sync (with JIRA configured) → Sync JIRA tickets only
    - daf sync -w <workspace> → Sync workspace repositories only
    - daf sync --field/--type/--epic → Sync JIRA tickets only
    - daf sync --repository → Sync specific repository only
    - daf sync (no JIRA configured) → Sync all workspaces
    - daf sync --jira → Force JIRA sync (requires JIRA URL)
    - daf sync --jira -w <workspace> → Sync both JIRA and workspace

    Creates sessions for issues that don't already have them.
    """
    from devflow.cli.commands.sync_command import sync_multi_backend
    from devflow.config.loader import ConfigLoader

    # Parse field filters from tuple of "field_name=value" strings
    field_filters = {}
    for field_filter in field:
        if '=' in field_filter:
            field_name, field_value = field_filter.split('=', 1)
            field_filters[field_name.strip()] = field_value.strip()

    # Determine sync mode based on parameters
    has_jira_filters = bool(field_filters or ticket_type or epic)
    has_workspace_filters = bool(workspace or repository)

    # Load config to check JIRA configuration
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    jira_configured = bool(config and config.jira and config.jira.url)

    # Determine what to sync
    if jira:
        # --jira flag: Force JIRA sync (can be combined with workspace filters)
        if not jira_configured:
            click.echo("Error: --jira flag requires JIRA to be configured", err=True)
            click.echo("Please set JIRA_URL environment variable or configure JIRA in your organization.json", err=True)
            raise click.Abort()
        sync_jira = True
        # Also sync workspaces if workspace/repository filters present
        sync_workspaces = has_workspace_filters
    elif has_jira_filters:
        # JIRA-specific filters → sync JIRA only
        if not jira_configured:
            click.echo("Error: JIRA filters (--field, --type, --epic) require JIRA to be configured", err=True)
            click.echo("Please set JIRA_URL environment variable or configure JIRA in your organization.json", err=True)
            raise click.Abort()
        sync_jira = True
        sync_workspaces = False
    elif has_workspace_filters:
        # Workspace/repository filters → sync workspaces only (unless --jira also specified, handled above)
        sync_jira = False
        sync_workspaces = True
    else:
        # No filters → sync based on JIRA configuration
        if jira_configured:
            # JIRA configured → sync JIRA only
            sync_jira = True
            sync_workspaces = False
        else:
            # No JIRA configured → sync workspaces only
            sync_jira = False
            sync_workspaces = True

    output_json = ctx.obj.get('output_json', False) if ctx.obj else False
    sync_multi_backend(
        field_filters=field_filters,
        ticket_type=ticket_type,
        epic=epic,
        workspace_filter=workspace,
        repository_filter=repository,
        sync_jira=sync_jira,
        sync_workspaces=sync_workspaces,
        output_json=output_json
    )


@cli.command()
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--all", "all_sessions", is_flag=True, help="Export all sessions")
@click.option("--output", shell_complete=complete_file_paths, help="Output file path")
@json_option
def export(ctx: click.Context, identifier: str, all_sessions: bool, output: str) -> None:
    """Export a session for team handoff.

    Exports complete session including ALL conversations (all projects),
    metadata, notes, and conversation history. Each session represents one
    issue tracker ticket's work across all repositories.

    Specify IDENTIFIER (issue key or session name) to export a single session,
    or use --all to export all sessions.

    Examples:
        daf export PROJ-60640 --output ~/export.tar.gz
        daf export --all --output ~/all-sessions.tar.gz
    """
    from devflow.cli.commands.export_command import export_sessions

    export_sessions(
        issue_keys=[identifier] if identifier else None,
        all_sessions=all_sessions,
        output=output,
    )


@cli.command(name="export-md")
@click.option("--identifier", "-i", "identifiers", multiple=True, required=True, shell_complete=complete_session_identifiers, help="Session identifier (issue key or session name). Can be specified multiple times.")
@click.option("--output-dir", shell_complete=complete_file_paths, help="Output directory (defaults to current directory)")
@click.option("--no-activity", is_flag=True, help="Exclude session activity summary")
@click.option("--no-statistics", is_flag=True, help="Exclude detailed statistics")
@click.option("--ai-summary", is_flag=True, help="Use AI-powered summary (requires ANTHROPIC_API_KEY)")
@click.option("--combined", is_flag=True, help="Export all sessions to a single combined file")
@json_option
def export_md(ctx: click.Context, identifiers: tuple, output_dir: str, no_activity: bool, no_statistics: bool, ai_summary: bool, combined: bool) -> None:
    """Export sessions to Markdown documentation format.

    Use --identifier/-i to specify session(s) to export (JIRA keys or session names).

    \b
    Creates standalone Markdown files suitable for documentation with:
    - Formatted metadata (issue key, goal, status, time tracking)
    - Progress notes in chronological order
    - issue tracker ticket details and links
    - Session activity summary
    - Session statistics (message count, work sessions, total time)

    \b
    Examples:
        daf export-md -i PROJ-12345                          # Export single session
        daf export-md -i PROJ-12345 -i PROJ-12346             # Export multiple sessions
        daf export-md -i PROJ-12345 --output-dir ./docs      # Export to specific directory
        daf export-md -i PROJ-12345 --ai-summary             # Use AI-powered summary
        daf export-md -i PROJ-12345 -i PROJ-12346 --combined  # Export to single file
    """
    from devflow.cli.commands.export_md_command import export_markdown

    export_markdown(
        identifiers=list(identifiers),
        output_dir=output_dir,
        include_activity=not no_activity,
        include_statistics=not no_statistics,
        ai_summary=ai_summary,
        combined=combined,
    )


@cli.command()
@click.option("--output", shell_complete=complete_file_paths, help="Output file path")
@json_option
def backup(ctx: click.Context, output: str) -> None:
    """Create a complete backup of all sessions."""
    from devflow.cli.commands.backup_command import create_backup

    create_backup(output=output)


@cli.command()
@click.argument("backup_file", shell_complete=complete_file_paths)
@click.option("--merge", is_flag=True, help="Merge with existing sessions instead of replacing")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@json_option
def restore(ctx: click.Context, backup_file: str, merge: bool, force: bool) -> None:
    """Restore from a complete backup."""
    from devflow.cli.commands.restore_command import restore_backup

    restore_backup(backup_file, merge=merge, force=force)


@cli.command()
@click.argument("export_file", shell_complete=complete_file_paths)
@click.option("--merge/--replace", default=True, help="Merge with existing sessions (default) or replace")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@json_option
def import_cmd(ctx: click.Context, export_file: str, merge: bool, force: bool) -> None:
    """Import sessions from an export file."""
    from devflow.cli.commands.import_command import import_sessions

    import_sessions(export_file, merge=merge, force=force)


@cli.command(hidden=True)
@json_option
def discover(ctx: click.Context) -> None:
    """[Hidden] Discover existing Claude Code sessions not managed by daf tool.

    Use 'daf maintenance discover' instead.
    """
    from devflow.cli.commands.discover_command import discover_sessions

    discover_sessions()


@cli.command(name="import-session")
@click.argument("uuid")
@click.option("--jira", help="issue tracker key (will prompt if not provided)")
@click.option("--goal", help="Session goal (auto-detection of file:// paths and http(s):// URLs)")
@click.option("--goal-file", help="Explicit file path or URL for goal input (mutually exclusive with --goal)")
@json_option
def import_session_cmd(ctx: click.Context, uuid: str, jira: str, goal: str, goal_file: str) -> None:
    """Import an existing Claude Code session that is not yet managed by daf tool.

    This registers a Claude Code session (created manually with 'claude --session-id')
    with daf tool so you can manage it using daf commands.

    Use 'daf discover' to find available session UUIDs on your machine.

    Note: This is different from 'daf import', which imports sessions from export files.
    """
    from devflow.cli.commands.import_session_command import import_session
    from devflow.cli.utils import process_goal_options

    # Process --goal and --goal-file options (mutual exclusion and resolution)
    goal = process_goal_options(goal, goal_file)

    import_session(uuid, issue_key=jira, goal=goal)


@cli.command()
@click.argument("name", shell_complete=complete_session_identifiers)
@click.option("--jira", "issue_key", required=True, help="issue tracker key to link")
@click.option("--force", is_flag=True, help="Skip confirmation prompts (auto-replace existing links)")
@json_option
def link(ctx: click.Context, name: str, issue_key: str, force: bool) -> None:
    """Link a issue tracker ticket to a session group.

    Associates a issue tracker ticket with all sessions in the specified session group.
    After linking, you can use either the session name or issue key to access the sessions.
    """
    from devflow.cli.commands.link_command import link_jira

    link_jira(name, issue_key, force)


@cli.command()
@click.argument("name", shell_complete=complete_session_identifiers)
@click.option("--force", is_flag=True, help="Skip confirmation prompts")
@json_option
def unlink(ctx: click.Context, name: str, force: bool) -> None:
    """Remove JIRA association from a session group.

    Removes the issue tracker ticket link from all sessions in the specified group.
    Can be called with either the session name or issue key.
    """
    from devflow.cli.commands.link_command import unlink_jira

    unlink_jira(name, force)


@cli.command(name="cleanup-sessions", hidden=True)
@click.option("--dry-run", is_flag=True, help="Show what would be cleaned without actually cleaning")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@json_option
def cleanup_sessions_cmd(ctx: click.Context, dry_run: bool, force: bool) -> None:
    """[Hidden] Find and fix orphaned sessions (sessions with missing conversation files).

    Use 'daf maintenance cleanup-sessions' instead.

    Scans all sessions and identifies ones where the conversation file no longer exists.
    This can happen when:
    - Session was interrupted during creation
    - Claude Code crashed before creating the conversation file
    - Conversation files were manually deleted

    \b
    What it does:
        - Scans all sessions for orphaned ai_agent_session_ids
        - Clears the orphaned IDs from session metadata
        - Next 'daf open' will generate fresh UUIDs

    \b
    Examples:
        daf cleanup-sessions --dry-run    # Preview what would be cleaned
        daf cleanup-sessions              # Clean with confirmation
        daf cleanup-sessions --force      # Clean without confirmation
    """
    from devflow.cli.commands.cleanup_sessions_command import cleanup_sessions

    cleanup_sessions(dry_run=dry_run, force=force)


@cli.command(name="rebuild-index", hidden=True)
@click.option("--dry-run", is_flag=True, help="Show what would be rebuilt without actually rebuilding")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@json_option
def rebuild_index_cmd(ctx: click.Context, dry_run: bool, force: bool) -> None:
    """[Hidden] Rebuild sessions.json index from session directories.

    Use 'daf maintenance rebuild-index' instead.

    Scans all session directories and rebuilds the sessions.json index file
    from their metadata.json files. This is useful when:
    - The sessions.json file was corrupted or deleted
    - Sessions exist but don't appear in 'daf list'
    - The index got out of sync with actual session data

    \b
    What it does:
        - Scans all session directories
        - Reads metadata.json from each directory
        - Rebuilds sessions.json with all valid sessions
        - Creates backup of existing sessions.json

    \b
    Examples:
        daf rebuild-index --dry-run    # Preview what would be rebuilt
        daf rebuild-index              # Rebuild with confirmation
        daf rebuild-index --force      # Rebuild without confirmation
    """
    from devflow.cli.commands.rebuild_index_command import rebuild_index

    rebuild_index(dry_run=dry_run, force=force)


@cli.command(name="repair-conversation", hidden=True)
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--conversation-id", type=int, help="Repair specific conversation by number (1, 2, 3...)")
@click.option("--max-size", type=int, default=10000, help="Maximum size for content truncation (default: 10000 chars)")
@click.option("--check-all", is_flag=True, help="Check all sessions for corruption (dry run)")
@click.option("--all", "repair_all", is_flag=True, help="Repair all corrupted sessions found")
@click.option("--dry-run", is_flag=True, help="Report issues without making changes")
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def repair_conversation_cmd(ctx: click.Context, identifier: str, conversation_id: int, max_size: int, check_all: bool, repair_all: bool, dry_run: bool, latest: bool) -> None:
    """[Hidden] Repair corrupted Claude Code conversation files.

    Use 'daf maintenance repair-conversation' instead.

    IDENTIFIER can be a session name, issue key, or Claude Code UUID.
    If not provided or --latest is specified, uses the most recently active session.

    This tool repairs corrupted .jsonl conversation files by:
    - Detecting and fixing invalid JSON lines
    - Removing invalid Unicode surrogate pairs
    - Truncating oversized tool results
    - Creating automatic backups before repair

    \b
    Examples:
        daf repair-conversation PROJ-60039                    # Repair by issue key
        daf repair-conversation --latest                     # Repair most recent session
        daf repair-conversation my-session                   # Repair by session name
        daf repair-conversation f545206f-480f-4c2d-8823      # Repair by UUID
        daf repair-conversation PROJ-60039 --conversation-id 1  # Repair specific conversation
        daf repair-conversation --check-all                  # Scan for corruption (dry run)
        daf repair-conversation --all                        # Repair all corrupted sessions
        daf repair-conversation PROJ-60039 --max-size 15000   # Custom truncation size
        daf repair-conversation PROJ-60039 --dry-run          # Preview changes

    \b
    Identifier types:
        - Session name (e.g., 'implement-backup-feature')
        - issue key (e.g., 'PROJ-60039')
        - Claude UUID (e.g., 'f545206f-480f-4c2d-8823-c6643f0e693d')

    \b
    Repair actions:
        - Automatically creates .jsonl.backup-TIMESTAMP before repair
        - Truncates large tool results to configurable size
        - Removes invalid Unicode surrogate pairs
        - Validates repaired file is valid JSON
        - Reports what was fixed (line numbers, truncation stats)

    \b
    Note: You'll need to restart Claude Code after repair for changes to take effect.
    """
    from devflow.cli.commands.repair_conversation_command import repair_conversation

    repair_conversation(
        identifier=identifier,
        conversation_id=conversation_id,
        max_size=max_size,
        check_all=check_all,
        repair_all=repair_all,
        dry_run=dry_run,
        latest=latest,
    )


@cli.command(name="cleanup-conversation", hidden=True)
@click.argument("identifier", required=False, shell_complete=complete_session_identifiers)
@click.option("--older-than", help="Remove messages older than duration (e.g., '2h', '1d', '30m')")
@click.option("--keep-last", type=int, help="Keep only the last N messages")
@click.option("--dry-run", is_flag=True, help="Show what would be removed without actually removing")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
@click.option("--list-backups", is_flag=True, help="List available backups for this session")
@click.option("--restore-backup", help="Restore from a specific backup (timestamp)")
@click.option("--latest", is_flag=True, help="Use the most recently active session")
@json_option
def cleanup_conversation_cmd(ctx: click.Context, identifier: str, older_than: str, keep_last: int, dry_run: bool, force: bool, list_backups: bool, restore_backup: str, latest: bool) -> None:
    """[Hidden] Clean up Claude Code conversation history to reduce context size.

    Use 'daf maintenance cleanup-conversation' instead.

    IDENTIFIER can be either a session group name or issue tracker key.
    If not provided or --latest is specified, uses the most recently active session.

    This is useful when you hit the 413 "Prompt is too long" error during long sessions.
    The command removes old messages from the conversation file while keeping recent context.

    \b
    Examples:
        daf cleanup-conversation PROJ-12345 --older-than 2h        # Remove messages older than 2 hours
        daf cleanup-conversation --latest --older-than 2h         # Clean most recent session
        daf cleanup-conversation PROJ-12345 --keep-last 50         # Keep only last 50 messages
        daf cleanup-conversation my-session --older-than 1d --dry-run  # Preview changes
        daf cleanup-conversation PROJ-12345 --older-than 8h --force  # Skip confirmation

    \b
    Backup management:
        daf cleanup-conversation PROJ-12345 --list-backups              # List all backups
        daf cleanup-conversation PROJ-12345 --restore-backup 20251120-163147  # Restore from backup

    \b
    A backup is automatically created before cleanup (stored in $DEVAIFLOW_HOME/backups/).
    Old backups are automatically cleaned up (keeping last 5 by default).
    You'll need to restart Claude Code to see the effect (conversation is cached).
    """
    from devflow.cli.commands.cleanup_command import cleanup_conversation

    cleanup_conversation(
        identifier,
        older_than=older_than,
        keep_last=keep_last,
        dry_run=dry_run,
        force=force,
        list_backups=list_backups,
        restore_backup=restore_backup,
        latest=latest,
    )


@cli.group()
@json_option
def jira(ctx: click.Context) -> None:
    """JIRA integration commands."""
    pass


@jira.command(name="view")
@json_option
@click.argument("issue_key")
@click.option("--history", is_flag=True, help="Show changelog/history of status transitions")
@click.option("--children", is_flag=True, help="Show child issues (subtasks and epic children)")
@click.option("--comments", is_flag=True, help="Show comments on the ticket")
def jira_view(ctx: click.Context, issue_key: str, history: bool, children: bool, comments: bool) -> None:
    """View a issue tracker ticket in Claude-friendly format.

    ISSUE_KEY is the ticket key (e.g., PROJ-12345).

    This command fetches the ticket from JIRA and displays it in a format
    optimized for Claude to read, making it more reliable than using curl.

    Use --history to also display the changelog showing status transitions
    and field changes with timestamps and user names.

    Use --children to display all child issues (subtasks and stories/tasks
    linked via Epic Link) with their key, type, status, summary, and assignee.

    Use --comments to display all comments on the ticket with author, timestamp,
    and comment text.
    """
    from devflow.cli.commands.jira_view_command import view_jira_ticket

    output_json = ctx.obj.get('output_json', False) if ctx.obj else False
    view_jira_ticket(issue_key, show_history=history, show_children=children, show_comments=comments, output_json=output_json)


@jira.command(name="add-comment")
@json_option
@click.argument("issue_key")
@click.argument("comment", required=False)
@click.option("--file", "file_path", type=click.Path(exists=True), help="Read comment from file")
@click.option("--stdin", is_flag=True, help="Read comment from stdin")
@click.option("--public", is_flag=True, help="Make comment public (requires confirmation)")
def jira_add_comment(ctx: click.Context, issue_key: str, comment: str, file_path: str, stdin: bool, public: bool) -> None:
    """Add a comment to a JIRA issue.

    By default, comments are restricted to Example Group visibility.
    Use --public to make the comment visible to all (requires confirmation).

    ISSUE_KEY is the ticket key (e.g., PROJ-12345).

    Comment text can be provided in three ways:
    - As an argument: daf jira add-comment PROJ-12345 "Your comment"
    - From a file: daf jira add-comment PROJ-12345 --file comment.txt
    - From stdin: echo "Comment" | daf jira add-comment PROJ-12345 --stdin

    Examples:
        daf jira add-comment PROJ-12345 "Fixed the issue"
        daf jira add-comment PROJ-12345 --file notes.txt
        echo "Update from CI" | daf jira add-comment PROJ-12345 --stdin
        daf jira add-comment PROJ-12345 "Public announcement" --public
    """
    from devflow.cli.commands.jira_add_comment_command import add_comment

    output_json = ctx.obj.get('output_json', False) if ctx.obj else False
    add_comment(issue_key, comment, file_path, stdin, public, output_json)


# Add dynamic jira create command with field discovery
from devflow.cli.commands.jira_create_dynamic import create_jira_create_command
jira.add_command(create_jira_create_command())


# Add dynamic jira update command with field discovery
from devflow.cli.commands.jira_update_dynamic import create_jira_update_command
jira.add_command(create_jira_update_command())


@jira.command(name="new")
@json_option
@click.argument("issue_type", type=click.Choice(["epic", "story", "task", "bug"], case_sensitive=False))
@click.option("--parent", required=False, help="Parent issue key (epic for story/task/bug, story for subtask)")
@click.option("--goal", help="Goal/description for the ticket (auto-detection of file:// paths and http(s):// URLs)")
@click.option("--goal-file", help="Explicit file path or URL for goal input (mutually exclusive with --goal)")
@click.option("--name", help="Session name (auto-generated from goal if not provided)")
@click.option("--path", help="Project path (bypasses interactive selection)")
@click.option("--branch", help="Git branch name (bypasses interactive creation prompt)")
@workspace_option()
@click.option("--projects", help="Comma-separated list of repository names for multi-project sessions (requires --workspace)")
@click.option("--temp-clone/--no-temp-clone", default=None, help="Clone to temporary directory for clean analysis (default: prompt)")
@click.option("--affects-versions", help="Affected version for bugs (required for bug type)")
def jira_new(ctx: click.Context, issue_type: str, parent: Optional[str], goal: str, goal_file: str, name: str, path: str, branch: str, workspace: str, projects: str, temp_clone: bool, affects_versions: Optional[str]) -> None:
    """Create issue tracker ticket with analysis-only session.

    Creates a session with session_type="ticket_creation" that:
    - Skips branch creation automatically
    - Provides analysis-only constraints in the initial prompt
    - Persists the session type for reopening

    Examples:
        daf jira new story --parent PROJ-59038 --goal "Add retry logic to subscription API"
        daf jira new bug --parent PROJ-60000 --goal "Fix timeout in backup operation"
        daf jira new story --parent PROJ-59038 --goal "file:///path/to/requirements.md"
        daf jira new task --parent PROJ-59038 --goal "https://docs.example.com/spec.txt"
    """
    from devflow.cli.commands.jira_new_command import create_jira_ticket_session
    from devflow.cli.utils import process_goal_options

    # Capitalize issue_type to match JIRA field_mappings format (e.g., "bug" -> "Bug")
    issue_type = issue_type.capitalize()

    # Prompt for goal if not provided
    if not goal and not goal_file:
        goal = click.prompt("Enter goal/description for the ticket")

    # Process --goal and --goal-file options (mutual exclusion and resolution)
    goal = process_goal_options(goal, goal_file)

    # Handle affects_versions - check if required for current issue type
    from devflow.config.loader import ConfigLoader
    from devflow.jira.field_mapper import JiraFieldMapper
    from devflow.jira import JiraClient
    from devflow.jira.utils import prompt_for_affected_version, validate_affected_version, is_version_field_required
    from devflow.utils import is_mock_mode

    # Load field mappings to check if version field is required for this issue type
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    field_mapper = None

    if config and config.jira:
        try:
            jira_client = JiraClient()
            # Use cached field mappings if available
            if config.jira.field_mappings:
                field_mapper = JiraFieldMapper(jira_client, config.jira.field_mappings)
        except Exception:
            # If field mapper fails, continue without it
            pass

    if affects_versions:
        # Validate provided version
        if not validate_affected_version(affects_versions, field_mapper):
            console.print(f"[red]✗[/red] Invalid affected version: \"{affects_versions}\"")
            console.print(f"[dim]This version is not in the allowed versions list.[/dim]")
            console.print(f"[dim]Please check the allowed versions in your JIRA project.[/dim]")
            raise click.Abort()
    else:
        # Only prompt if field is required for this issue type
        # Checks field_mappings['affects_version/s']['required_for'] to see if current issue_type is listed
        field_required = is_version_field_required(field_mapper, issue_type=issue_type)
        if field_required:
            # Prompt for version
            if is_mock_mode():
                affects_versions = "v1.0.0"
            else:
                affects_versions = prompt_for_affected_version(field_mapper)
        # else: affects_versions stays None (field is optional for this issue type)

    create_jira_ticket_session(issue_type, parent, goal, name, path, branch, workspace, affects_versions, projects=projects, temp_clone=temp_clone)


@jira.command(name="open")
@json_option
@click.argument("issue_key")
def jira_open(ctx: click.Context, issue_key: str) -> None:
    """Open or create session for issue tracker ticket.

    Validates that the issue tracker ticket exists, then either:
    - Opens the existing session if one exists for this ticket
    - Creates a new session named 'creation-<issue_key>' if no session exists

    ISSUE_KEY is the ticket key (e.g., PROJ-12345).

    Examples:
        daf jira open PROJ-12345
    """
    from devflow.cli.commands.jira_open_command import jira_open_session

    jira_open_session(issue_key)


@cli.group()
@json_option
def git(ctx: click.Context) -> None:
    """Git-based issue tracker commands (GitHub/GitLab).

    Commands for managing GitHub Issues and GitLab Issues workflows in DevAIFlow.
    Automatically detects the platform from your repository.

    Requirements:
    - GitHub: GitHub CLI (gh) installed and authenticated
    - GitLab: GitLab CLI (glab) installed and authenticated
    """
    pass


@git.command(name="view")
@json_option
@click.argument("issue_key", required=False)
@click.option("--comments", is_flag=True, help="Show comments on the issue")
@click.option("--repository", help="Repository in owner/repo format (optional, will auto-detect)")
def git_view(ctx: click.Context, issue_key: Optional[str], comments: bool, repository: Optional[str]) -> None:
    """View a GitHub/GitLab issue in Claude-friendly format.

    ISSUE_KEY is the issue key (#123 or owner/repo#123).
    If not provided, auto-detects from current session.

    This command fetches the issue from GitHub/GitLab and displays it in a format
    optimized for Claude to read.

    Use --comments to display all comments on the issue.

    Examples:
        daf git view           # Auto-detect from current session
        daf git view 123       # View issue #123 in current repo
        daf git view owner/repo#123  # View issue in specific repo
        daf git view 123 --comments  # Include comments
    """
    from devflow.cli.commands.git_view_command import git_view

    output_json = ctx.obj.get('output_json', False) if ctx.obj else False
    git_view(issue_key, comments, repository, output_json)


@git.command(name="create")
@json_option
@click.argument("issue_type", required=False, default=None)
@click.option("--summary", required=True, help="Issue summary/title")
@click.option("--description", help="Issue description")
@click.option("--priority", type=click.Choice(["low", "medium", "high", "critical"], case_sensitive=False), help="Priority (uses labels)")
@click.option("--points", type=int, help="Story points (uses labels)")
@click.option("--labels", help="Additional labels (comma-separated)")
@click.option("--assignee", help="Assign to username")
@click.option("--milestone", help="Milestone name or number")
@click.option("--parent", help="Parent issue key (owner/repo#123 or #123)")
@click.option("--repository", help="Repository in owner/repo format (optional, will auto-detect)")
@click.option("--acceptance-criteria", multiple=True, help="Acceptance criteria (can be used multiple times)")
def git_create(ctx: click.Context, issue_type: Optional[str], summary: str, description: Optional[str], priority: Optional[str], points: Optional[int], labels: Optional[str], assignee: Optional[str], milestone: Optional[str], parent: Optional[str], repository: Optional[str], acceptance_criteria: tuple) -> None:
    """Create a new GitHub/GitLab issue.

    Creates an issue with convention-based labels for type, priority, and points.

    ISSUE_TYPE is optional positional argument (bug, enhancement, task, spike, epic).
    Valid types are configurable in enterprise.json and organization.json.

    Examples:
        daf git create enhancement --summary "Add feature X"
        daf git create bug --summary "Fix bug" --priority high --points 5
        daf git create task --summary "Task" --assignee username --milestone v1.0
        daf git create --summary "No type label"
        daf git create enhancement --summary "Feature" \\
            --acceptance-criteria "Tests pass" \\
            --acceptance-criteria "Docs updated"
        daf git create task --summary "Implement auth" --parent "#123"
        daf git create task --summary "Add validation" --parent "owner/repo#456"
    """
    from devflow.cli.commands.git_create_command import git_create

    output_json = ctx.obj.get('output_json', False) if ctx.obj else False
    git_create(summary, issue_type, description, priority, points, labels, assignee, milestone, parent, repository, acceptance_criteria, output_json)


@git.command(name="update")
@json_option
@click.argument("issue_key")
@click.option("--state", type=click.Choice(["open", "closed"], case_sensitive=False), help="New state")
@click.option("--title", help="New title")
@click.option("--description", help="New description")
@click.option("--labels", help="New labels (comma-separated, replaces all labels)")
@click.option("--assignee", help="Assign to username")
@click.option("--milestone", help="Set milestone")
@click.option("--parent", help="Link to parent issue (owner/repo#123 or #123)")
@click.option("--repository", help="Repository in owner/repo format (optional, will auto-detect)")
def git_update(ctx: click.Context, issue_key: str, state: Optional[str], title: Optional[str], description: Optional[str], labels: Optional[str], assignee: Optional[str], milestone: Optional[str], parent: Optional[str], repository: Optional[str]) -> None:
    """Update a GitHub/GitLab issue.

    ISSUE_KEY is the issue key (#123 or owner/repo#123).

    Examples:
        daf git update 123 --state closed
        daf git update 123 --labels "bug,priority: high"
        daf git update 123 --assignee username --milestone v1.0
        daf git update 123 --parent "#456"
    """
    from devflow.cli.commands.git_update_command import git_update

    output_json = ctx.obj.get('output_json', False) if ctx.obj else False
    git_update(issue_key, state, title, description, labels, assignee, milestone, parent, repository, output_json)


@git.command(name="add-comment")
@json_option
@click.argument("issue_key")
@click.argument("comment")
@click.option("--repository", help="Repository in owner/repo format (optional, will auto-detect)")
def git_add_comment(ctx: click.Context, issue_key: str, comment: str, repository: Optional[str]) -> None:
    """Add a comment to a GitHub/GitLab issue.

    ISSUE_KEY is the issue key (#123 or owner/repo#123).

    Examples:
        daf git add-comment 123 "Work in progress"
        daf git add-comment owner/repo#123 "Fixed the issue"
    """
    from devflow.cli.commands.git_add_comment_command import git_add_comment

    output_json = ctx.obj.get('output_json', False) if ctx.obj else False
    git_add_comment(issue_key, comment, repository, output_json)


@git.command(name="open")
@json_option
@click.argument("issue_key")
@click.option("--repository", help="Repository in owner/repo format (optional, will auto-detect)")
def git_open(ctx: click.Context, issue_key: str, repository: Optional[str]) -> None:
    """Open or create session for GitHub/GitLab issue.

    Validates that the issue exists, then either:
    - Opens the existing session if one exists for this issue
    - Creates a new session if no session exists

    ISSUE_KEY is the issue key (#123 or owner/repo#123).

    Examples:
        daf git open 123
        daf git open owner/repo#123
    """
    from devflow.cli.commands.git_open_command import git_open_session

    git_open_session(issue_key, repository)


@git.command(name="new")
@json_option
@click.argument("issue_type", required=False, default=None)
@click.option("--goal", help="Goal/description for the issue (auto-detection of file:// paths and http(s):// URLs)")
@click.option("--goal-file", help="Explicit file path or URL for goal input (mutually exclusive with --goal)")
@click.option("--name", help="Session name (auto-generated from goal if not provided)")
@click.option("--path", help="Project path (bypasses interactive selection)")
@click.option("--branch", help="Git branch name (bypasses interactive creation prompt)")
@click.option("--parent", help="Parent issue key (owner/repo#123 or #123)")
@workspace_option()
@click.option("--projects", help="Comma-separated list of repository names for multi-project sessions (requires --workspace)")
@click.option("--temp-clone/--no-temp-clone", default=None, help="Clone to temporary directory for clean analysis (default: prompt)")
@click.option("--repository", help="Repository in owner/repo format (optional, will auto-detect)")
def git_new(ctx: click.Context, issue_type: Optional[str], goal: Optional[str], goal_file: Optional[str], name: str, path: str, branch: str, parent: Optional[str], workspace: str, projects: str, temp_clone: bool, repository: Optional[str]) -> None:
    """Create GitHub/GitLab issue with analysis-only session.

    Creates a session with session_type="ticket_creation" that:
    - Skips branch creation automatically
    - Provides analysis-only constraints in the initial prompt
    - Persists the session type for reopening

    ISSUE_TYPE is optional positional argument (bug, enhancement, task, spike, epic).
    Valid types are configurable in enterprise.json and organization.json.

    Examples:
        daf git new enhancement --goal "Add retry logic to API"
        daf git new bug --goal "Fix timeout in operation"
        daf git new --goal "General investigation"  (no type)
        daf git new --goal "file:///path/to/requirements.md"
        daf git new task --goal "Implement auth" --parent "#123"
        daf git new enhancement --goal "Add caching" --parent "owner/repo#456"
    """
    from devflow.cli.commands.git_new_command import create_git_issue_session
    from devflow.cli.utils import process_goal_options

    # Prompt for goal if not provided
    if not goal and not goal_file:
        goal = click.prompt("Enter goal/description for the issue")

    # Process --goal and --goal-file options (mutual exclusion and resolution)
    goal = process_goal_options(goal, goal_file)

    create_git_issue_session(goal, issue_type, name, path, branch, parent, workspace, repository, projects=projects, temp_clone=temp_clone)


@git.command(name="check-auth")
@click.argument("repository", required=False)
def git_check_auth(ctx: click.Context, repository: Optional[str]) -> None:
    """Check GitHub authentication and repository access.

    REPOSITORY is optional repository in owner/repo format.
    If not provided, auto-detects from git remotes.

    Examples:
        daf git check-auth owner/repo
        daf git check-auth  # Auto-detect from git remote
    """
    from devflow.cli.commands.git_check_auth_command import check_auth_command

    check_auth_command.callback(repository)


@cli.command(name="investigate")
@json_option
@click.option("--goal", help="Goal/description for the investigation (auto-detection of file:// paths and http(s):// URLs)")
@click.option("--goal-file", help="Explicit file path or URL for goal input (mutually exclusive with --goal)")
@click.option("--parent", required=False, help="Optional parent issue key (for tracking investigation under an epic)")
@click.option("--name", help="Session name (auto-generated from goal if not provided)")
@click.option("--path", help="Project path (bypasses interactive selection)")
@workspace_option()
@click.option("--projects", help="Comma-separated list of repository names for multi-project sessions (requires --workspace)")
@click.option("--temp-clone/--no-temp-clone", default=None, help="Clone to temporary directory for clean analysis (default: prompt)")
@click.option("--model-profile", help="Model provider profile to use (e.g., 'vertex', 'llama-cpp')")
def investigate(ctx: click.Context, goal: str, goal_file: str, parent: Optional[str], name: str, path: str, workspace: str, projects: str, temp_clone: bool, model_profile: str) -> None:
    """Create investigation-only session without ticket creation.

    Creates a session with session_type="investigation" that:
    - Skips branch creation automatically
    - Provides analysis-only constraints in the initial prompt
    - Does NOT expect ticket creation
    - Generates investigation report instead

    Use this when you want to explore the codebase before committing to creating a issue tracker ticket.

    Examples:
        daf investigate --goal "Research Redis caching options for subscription API"
        daf investigate --goal "Investigate timeout issue in backup service" --parent PROJ-59038
        daf investigate --goal "file:///path/to/research-notes.md"
        daf investigate --goal "https://docs.example.com/requirements.txt" --parent PROJ-60000
    """
    from devflow.cli.commands.investigate_command import create_investigation_session
    from devflow.cli.utils import process_goal_options

    # Prompt for goal if not provided
    if not goal and not goal_file:
        goal = click.prompt("Enter goal/description for the investigation")

    # Process --goal and --goal-file options (mutual exclusion and resolution)
    goal = process_goal_options(goal, goal_file)

    create_investigation_session(goal, parent, name, path, workspace, model_profile, projects=projects, temp_clone=temp_clone)


@cli.group()
@json_option
def config(ctx: click.Context) -> None:
    """Configuration management commands."""
    pass


@config.command(name="refresh-jira-fields")
@json_option
def refresh_jira_fields(ctx: click.Context) -> None:
    """Refresh cached JIRA field mappings.

    Discovers JIRA custom fields for the configured project and updates
    the cached field mappings in config.json. This is useful when:
    - New custom fields are added to your JIRA instance
    - Field configurations change
    - You want to ensure mappings are up-to-date

    Note: This only refreshes creation fields. Editable fields are discovered
    on-demand when using 'daf jira update --field'.

    Example:
        daf config refresh-jira-fields

    Requires JIRA_API_TOKEN environment variable to be set.
    """
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()

    # Load existing config
    config = config_loader.load_config()
    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.jira:
        console.print("[red]✗[/red] JIRA not configured. Run [cyan]daf init[/cyan] first.")
        return

    # Discover and cache creation fields
    _discover_and_cache_jira_fields(config, config_loader)


def _show_prompts(config, output_json: bool) -> None:
    """Helper function to display prompt configuration."""
    from rich.table import Table

    console.print("\n[bold]Prompt Configuration[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_column("Command", style="dim")

    prompts = config.prompts

    table.add_row(
        "auto_commit_on_complete",
        str(prompts.auto_commit_on_complete) if prompts.auto_commit_on_complete is not None else "[dim]not set[/dim]",
        "daf complete"
    )
    table.add_row(
        "auto_create_pr_on_complete",
        str(prompts.auto_create_pr_on_complete) if prompts.auto_create_pr_on_complete is not None else "[dim]not set[/dim]",
        "daf complete"
    )
    table.add_row(
        "auto_create_pr_status",
        prompts.auto_create_pr_status,
        "daf complete"
    )
    table.add_row(
        "auto_add_issue_summary",
        str(prompts.auto_add_issue_summary) if prompts.auto_add_issue_summary is not None else "[dim]not set[/dim]",
        "daf complete"
    )
    table.add_row(
        "auto_launch_claude",
        str(prompts.auto_launch_claude) if prompts.auto_launch_claude is not None else "[dim]not set[/dim]",
        "daf open"
    )
    table.add_row(
        "auto_checkout_branch",
        str(prompts.auto_checkout_branch) if prompts.auto_checkout_branch is not None else "[dim]not set[/dim]",
        "daf open"
    )
    table.add_row(
        "auto_sync_with_base",
        prompts.auto_sync_with_base if prompts.auto_sync_with_base else "[dim]not set[/dim]",
        "daf open"
    )
    table.add_row(
        "default_branch_strategy",
        prompts.default_branch_strategy if prompts.default_branch_strategy else "[dim]not set[/dim]",
        "daf new"
    )
    table.add_row(
        "show_prompt_unit_tests",
        str(prompts.show_prompt_unit_tests),
        "daf new, daf open"
    )

    console.print(table)

    if prompts.remember_last_repo_per_project:
        console.print("\n[bold]Last Repository Per Project:[/bold]")
        for project, repo in prompts.remember_last_repo_per_project.items():
            console.print(f"  {project}: {repo}")
    else:
        console.print("\n[dim]No repositories remembered yet[/dim]")

    console.print()


def _show_fields(config, output_json: bool) -> None:
    """Helper function to display available JIRA fields."""
    from rich.table import Table
    import json

    if not config.jira or not config.jira.field_mappings:
        if output_json:
            print(json.dumps({"success": True, "data": {"fields": []}, "message": "No custom fields configured in field_mappings"}))
        else:
            console.print("\n[yellow]⚠[/yellow] No custom fields configured in field_mappings.")
            console.print("[dim]Run [cyan]daf config refresh-jira-fields[/cyan] to discover fields from JIRA[/dim]\n")
        return

    field_mappings = config.jira.field_mappings

    # JSON output
    if output_json:
        fields_data = []
        for field_name, field_info in field_mappings.items():
            field_data = {
                "field_name": field_name,
                "display_name": field_info.get("name", field_name),
                "jira_id": field_info.get("id", ""),
                "type": field_info.get("type", "unknown"),
            }
            if "schema" in field_info:
                field_data["schema"] = field_info["schema"]
            if "allowed_values" in field_info and field_info["allowed_values"]:
                field_data["allowed_values"] = field_info["allowed_values"]
            if "required_for" in field_info and field_info["required_for"]:
                field_data["required_for"] = field_info["required_for"]
            fields_data.append(field_data)

        print(json.dumps({"success": True, "data": {"fields": fields_data, "count": len(fields_data)}}))
        return

    # Human-readable output
    console.print(f"\n[bold]Available Custom Fields[/bold] ({len(field_mappings)} fields)\n")
    console.print("[dim]Use these field names with --field option (e.g., --field field_name=value)[/dim]\n")

    for field_name, field_info in sorted(field_mappings.items()):
        console.print(f"[bold cyan]{field_name}[/bold cyan]")
        console.print(f"  Display Name: {field_info.get('name', field_name)}")
        console.print(f"  JIRA ID: [dim]{field_info.get('id', 'unknown')}[/dim]")

        # Type and schema
        field_type = field_info.get("type", "unknown")
        if "schema" in field_info:
            console.print(f"  Type: {field_type} (schema: {field_info['schema']})")
        else:
            console.print(f"  Type: {field_type}")

        # Allowed values
        if "allowed_values" in field_info and field_info["allowed_values"]:
            values = field_info["allowed_values"]
            if len(values) <= 5:
                console.print(f"  Allowed Values: {', '.join(map(str, values))}")
            else:
                console.print(f"  Allowed Values: {', '.join(map(str, values[:5]))}, ... ({len(values)} total)")

        # Required for issue types
        if "required_for" in field_info and field_info["required_for"]:
            console.print(f"  Required For: {', '.join(field_info['required_for'])}")

        console.print()

    console.print(f"[dim]Total: {len(field_mappings)} custom field(s)[/dim]")
    console.print(f"[dim]Refresh with: daf config refresh-jira-fields[/dim]\n")


def _show_sync_filters(config, output_json: bool) -> None:
    """Helper function to display sync filter configuration."""
    from rich.table import Table
    import json

    if not config.jira or not config.jira.filters:
        if output_json:
            print(json.dumps({"success": True, "data": {"sync_filters": None}, "message": "No sync filters configured"}))
        else:
            console.print("\n[yellow]⚠[/yellow] No sync filters configured.")
            console.print("[dim]Configure in organization.json under jira.filters.sync[/dim]\n")
        return

    sync_filters = config.jira.filters.get("sync")
    if not sync_filters:
        if output_json:
            print(json.dumps({"success": True, "data": {"sync_filters": None}, "message": "No sync filters configured"}))
        else:
            console.print("\n[yellow]⚠[/yellow] No sync filters configured.")
            console.print("[dim]Configure in organization.json under jira.filters.sync[/dim]\n")
        return

    # JSON output
    if output_json:
        sync_data = {
            "status": sync_filters.status if hasattr(sync_filters, 'status') else [],
            "required_fields": sync_filters.required_fields if hasattr(sync_filters, 'required_fields') else [],
            "assignee": sync_filters.assignee if hasattr(sync_filters, 'assignee') else "currentUser()",
        }
        print(json.dumps({"success": True, "data": {"sync_filters": sync_data}}))
        return

    # Human-readable output
    console.print("\n[bold]Sync Filter Configuration[/bold]")
    console.print("[dim]These filters determine which JIRA tickets are synced with 'daf sync'[/dim]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_column("Description", style="dim")

    # Status filter
    status_list = sync_filters.status if hasattr(sync_filters, 'status') else []
    table.add_row(
        "status",
        ", ".join(status_list) if status_list else "[dim]not set[/dim]",
        "JIRA statuses to sync (e.g., 'To Do', 'In Progress')"
    )

    # Required fields
    required_fields = sync_filters.required_fields if hasattr(sync_filters, 'required_fields') else []

    # Check if required_fields is a dict (type-specific) or list (legacy)
    if isinstance(required_fields, dict):
        # Type-specific required fields
        required_fields_display = f"{len(required_fields)} issue types configured"
        required_fields_desc = "Required fields per issue type (see below for details)"
    elif required_fields:
        # Legacy list format
        required_fields_display = ", ".join(required_fields)
        required_fields_desc = "Fields that must be present on tickets (uses field names from field_mappings)"
    else:
        required_fields_display = "[dim]none[/dim]"
        required_fields_desc = "Fields that must be present on tickets (uses field names from field_mappings)"

    table.add_row(
        "required_fields",
        required_fields_display,
        required_fields_desc
    )

    # Assignee filter
    assignee = sync_filters.assignee if hasattr(sync_filters, 'assignee') else "currentUser()"
    table.add_row(
        "assignee",
        assignee,
        "'currentUser()' (your tickets) | username | null (all tickets)"
    )

    console.print(table)
    console.print()

    # Display required fields explanation
    if required_fields:
        if isinstance(required_fields, dict):
            # Type-specific required fields - show per issue type
            console.print("[bold]Required Fields by Issue Type:[/bold]")
            console.print("[dim]Each issue type has its own set of required fields:[/dim]\n")

            # Create a table for type-specific fields
            fields_table = Table(show_header=True, header_style="bold cyan")
            fields_table.add_column("Issue Type", style="cyan")
            fields_table.add_column("Required Fields", style="yellow")

            for issue_type, fields in sorted(required_fields.items()):
                fields_table.add_row(issue_type, ", ".join(fields) if fields else "[dim]none[/dim]")

            console.print(fields_table)
            console.print()
            console.print("[dim]Use 'daf config show --fields' to see all available field names[/dim]")
        else:
            # Legacy list format
            console.print("[bold]Required Fields Explanation:[/bold]")
            console.print(f"[dim]Tickets must have ALL of these fields set to be synced:[/dim]")
            for field in required_fields:
                console.print(f"  • {field}")
            console.print()
            console.print("[dim]Use 'daf config show --fields' to see all available field names[/dim]")
    else:
        console.print("[dim]No required fields configured - all tickets matching status/assignee filters will be synced[/dim]")

    console.print()
    console.print("[dim]Configuration file: organization.json (jira.filters.sync section)[/dim]\n")


@config.command(name="show")
@json_option
@click.option("--format", type=click.Choice(["merged", "split"]), default="merged", help="Show merged config or split files separately")
@click.option("--validate", is_flag=True, help="Validate configuration and show detailed issues")
@click.option("--fields", is_flag=True, help="Show available JIRA custom fields from field_mappings")
@click.option("--prompts", is_flag=True, help="Show prompt configuration settings")
@click.option("--sync-filters", is_flag=True, help="Show sync filter configuration for 'daf sync'")
def config_show(ctx: click.Context, format: str, validate: bool, fields: bool, prompts: bool, sync_filters: bool) -> None:
    """Show current configuration.

    By default, shows merged configuration from all config files.
    Use specialized flags to show specific configuration areas.

    Examples:
        daf config show                    # Show merged config (default)
        daf config show --fields           # Show available JIRA fields
        daf config show --prompts          # Show prompt settings
        daf config show --sync-filters     # Show sync filter configuration
        daf config show --format split     # Show split config files
        daf config show --validate         # Validate configuration
        daf config show --json             # Show as JSON
    """
    from devflow.config.loader import ConfigLoader
    from devflow.config.validator import ConfigValidator
    from pathlib import Path
    import json

    # Check for mutually exclusive flags
    specialized_flags = sum([fields, prompts, sync_filters])
    if specialized_flags > 1:
        console.print("[red]✗[/red] Only one of --fields, --prompts, --sync-filters can be used at a time")
        return

    config_loader = ConfigLoader()

    # Extract output_json from context
    output_json = ctx.obj.get('output_json', False) if ctx.obj else False

    # Load config (suppress automatic validation warnings since we'll show detailed validation if --validate flag is used)
    config = config_loader.load_config()

    if not config:
        _show_no_config_error()
        return

    # Route to specialized views
    if fields:
        return _show_fields(config, output_json)
    elif prompts:
        return _show_prompts(config, output_json)
    elif sync_filters:
        return _show_sync_filters(config, output_json)

    # If --validate flag is used, show detailed validation report
    if validate:
        validator = ConfigValidator(config_loader.config_dir)

        # Check if using old or new format and validate accordingly
        is_old_format = config_loader._is_old_format()
        if is_old_format:
            validation_result = validator.validate_merged_config(config)
        else:
            validation_result = validator.validate_split_config_files()

        console.print("\n[bold]Configuration Validation Report[/bold]\n")
        validator.print_validation_result(validation_result, verbose=True)
        return

    if output_json:
        # Output raw JSON
        print(json.dumps(config.model_dump(by_alias=True), indent=2, default=str))
        return

    # Display formatted configuration
    console.print("\n[bold]Current Configuration[/bold]")

    # Show configuration format
    is_old_format = config_loader._is_old_format()
    if is_old_format:
        console.print("[dim](legacy single-file format)[/dim]")
    else:
        console.print("[dim](new 4-file format)[/dim]")

    console.print()

    # Show configuration files
    console.print("[bold]Configuration Files:[/bold]")
    if is_old_format:
        console.print(f"  • {config_loader.config_file} [dim](legacy format)[/dim]")
    else:
        console.print(f"  • {config_loader.config_file} [dim](user preferences)[/dim]")
        console.print(f"  • {config_loader.config_dir / 'organization.json'} [dim](organization settings)[/dim]")
        console.print(f"  • {config_loader.config_dir / 'team.json'} [dim](team settings)[/dim]")
        console.print(f"  • {config_loader.config_dir / 'backends' / 'jira.json'} [dim](JIRA backend)[/dim]")

    console.print()

    # Show JIRA configuration
    console.print("[bold]JIRA:[/bold]")
    console.print(f"  URL: {config.jira.url}")
    console.print(f"  Project: {config.jira.project or '(not set)'}")
    if config.jira.custom_field_defaults:
        console.print(f"  Custom Field Defaults: {config.jira.custom_field_defaults}")
    else:
        console.print("  Custom Field Defaults: (not set)")
    console.print(f"  Affected Version: {config.jira.affected_version or '(not set)'}")
    console.print(f"  Time Tracking: {config.jira.time_tracking}")

    # Show field cache info
    if config.jira.field_mappings:
        console.print(f"  Field Mappings: {len(config.jira.field_mappings)} fields cached")
        if config.jira.field_cache_timestamp:
            console.print(f"  Cache Timestamp: {config.jira.field_cache_timestamp}")
    else:
        console.print("  Field Mappings: (not cached)")

    console.print()

    # Show repository configuration
    console.print("[bold]Repositories:[/bold]")
    if config.repos.workspaces:
        console.print("  Workspaces:")
        for ws in config.repos.workspaces:
            default_marker = " [last used]" if config.repos.last_used_workspace == ws.name else ""
            console.print(f"    • {ws.name}: {ws.path}{default_marker}")
    else:
        console.print("  Workspaces: (none configured)")
    if config.repos.keywords:
        console.print(f"  Keywords: {len(config.repos.keywords)} mappings")
    else:
        console.print("  Keywords: (none configured)")

    console.print()

    # Show time tracking configuration
    console.print("[bold]Time Tracking:[/bold]")
    console.print(f"  Auto Start: {config.time_tracking.auto_start}")
    console.print(f"  Auto Pause After: {config.time_tracking.auto_pause_after or '(not set)'}")
    console.print(f"  Reminder Interval: {config.time_tracking.reminder_interval or '(not set)'}")

    console.print()

    # Show PR template
    if config.pr_template_url:
        console.print(f"[bold]PR Template URL:[/bold] {config.pr_template_url}")
    else:
        console.print("[bold]PR Template URL:[/bold] (not set)")

    console.print()


@config.command(name="edit")
@json_option
@click.option("--advanced", is_flag=True, help="Start in Advanced Mode (file-based tabs)")
def config_edit(ctx: click.Context, advanced: bool) -> None:
    """Launch interactive TUI for configuration editing.

    Opens a full-screen text-based user interface for managing all
    daf configuration settings. Provides:
    - Simple Mode: Topic-based tabs (JIRA, AI, Repository, etc.) - default
    - Advanced Mode: File-based tabs (Enterprise, Organization, Team, User) - use --advanced
    - Input validation for URLs, paths, and required fields
    - Help screen with keyboard shortcuts
    - Preview mode before saving
    - Automatic backup creation

    Keyboard Shortcuts:
        Tab / Shift+Tab     - Navigate between fields
        Arrow Keys          - Navigate tabs and fields
        Ctrl+S              - Save configuration
        Ctrl+M              - Toggle between Simple and Advanced modes
        ?                   - Show help
        Q / Ctrl+C          - Quit

    Examples:
        daf config edit                # Start in Simple Mode (default)
        daf config edit --advanced     # Start in Advanced Mode
    """
    from devflow.ui.config_tui import run_config_tui

    try:
        run_config_tui(advanced_mode=advanced)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to launch configuration TUI: {e}")
        console.print("[dim]You can still edit configuration manually in config.json[/dim]")


@config.command(name="unset-prompts")
@json_option
@click.option("--auto-commit", is_flag=True, help="Unset auto-commit setting")
@click.option("--auto-create-pr", is_flag=True, help="Unset auto-create-pr setting")
@click.option("--auto-create-pr-status", is_flag=True, help="Reset auto-create-pr-status to prompt")
@click.option("--auto-add-jira-summary", is_flag=True, help="Unset auto-add-jira-summary setting")
@click.option("--auto-launch-claude", is_flag=True, help="Unset auto-launch-claude setting")
@click.option("--auto-checkout-branch", is_flag=True, help="Unset auto-checkout-branch setting")
@click.option("--auto-sync-base", is_flag=True, help="Unset auto-sync-base setting")
@click.option("--default-branch-strategy", is_flag=True, help="Unset default-branch-strategy setting")
@click.option("--show-prompt-unit-tests", is_flag=True, help="Reset show-prompt-unit-tests to default (true)")
@click.option("--all", is_flag=True, help="Unset all prompt settings")
def unset_prompts(ctx: click.Context, 
    auto_commit: bool,
    auto_create_pr: bool,
    auto_create_pr_status: bool,
    auto_add_issue_summary: bool,
    auto_launch_claude: bool,
    auto_checkout_branch: bool,
    auto_sync_base: bool,
    default_branch_strategy: bool,
    show_prompt_unit_tests: bool,
    all: bool,
) -> None:
    """Remove prompt configuration settings.

    Unset specific prompt settings to restore interactive prompting.
    Use --all to reset all prompt settings at once.

    Examples:
        daf config unset-prompts --auto-commit           # Unset auto-commit only
        daf config unset-prompts --auto-create-pr        # Unset auto-create-pr only
        daf config unset-prompts --all                   # Reset all to interactive
    """
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if all:
        # Reset all prompt settings
        config.prompts.auto_commit_on_complete = None
        config.prompts.auto_create_pr_on_complete = None
        config.prompts.auto_create_pr_status = "prompt"  # Reset to default
        config.prompts.auto_add_issue_summary = None
        config.prompts.auto_launch_claude = None
        config.prompts.auto_checkout_branch = None
        config.prompts.auto_sync_with_base = None
        config.prompts.default_branch_strategy = None
        config.prompts.show_prompt_unit_tests = True  # Reset to default (true)
        config.prompts.remember_last_repo_per_project = {}

        config_loader.save_config(config)
        console.print("[green]✓[/green] All prompt settings reset to interactive mode")
        return

    # Unset specific settings
    unset_count = 0

    if auto_commit:
        config.prompts.auto_commit_on_complete = None
        console.print("[green]✓[/green] Unset auto_commit_on_complete")
        unset_count += 1

    if auto_create_pr:
        config.prompts.auto_create_pr_on_complete = None
        console.print("[green]✓[/green] Unset auto_create_pr_on_complete")
        unset_count += 1

    if auto_create_pr_status:
        config.prompts.auto_create_pr_status = "prompt"
        console.print("[green]✓[/green] Reset auto_create_pr_status to prompt")
        unset_count += 1

    if auto_add_issue_summary:
        config.prompts.auto_add_issue_summary = None
        console.print("[green]✓[/green] Unset auto_add_issue_summary")
        unset_count += 1

    if auto_launch_claude:
        config.prompts.auto_launch_claude = None
        console.print("[green]✓[/green] Unset auto_launch_claude")
        unset_count += 1

    if auto_checkout_branch:
        config.prompts.auto_checkout_branch = None
        console.print("[green]✓[/green] Unset auto_checkout_branch")
        unset_count += 1

    if auto_sync_base:
        config.prompts.auto_sync_with_base = None
        console.print("[green]✓[/green] Unset auto_sync_with_base")
        unset_count += 1

    if default_branch_strategy:
        config.prompts.default_branch_strategy = None
        console.print("[green]✓[/green] Unset default_branch_strategy")
        unset_count += 1

    if show_prompt_unit_tests:
        config.prompts.show_prompt_unit_tests = True  # Reset to default (true)
        console.print("[green]✓[/green] Reset show_prompt_unit_tests to default (true)")
        unset_count += 1

    if unset_count == 0:
        console.print("[yellow]⚠[/yellow] No settings specified. Use --all or specify individual settings.")
        console.print("  Run [cyan]daf config unset-prompts --help[/cyan] for usage.")
        return

    config_loader.save_config(config)
    console.print(f"\n[green]✓[/green] {unset_count} prompt setting(s) reset to interactive mode")


# Context file management commands
@config.group(name="context")
def context() -> None:
    """Manage context files for initial prompts."""
    pass


@context.command(name="list")
@json_option
def context_list(ctx: click.Context) -> None:
    """List all configured context files (including defaults).

    Shows default context files (AGENTS.md, CLAUDE.md) that are always included,
    plus any additional configured files.

    Example:
        daf config context list
    """
    from devflow.cli.commands.context_commands import list_context_files

    list_context_files()


@context.command(name="add")
@json_option
@click.argument("path", required=False)
@click.argument("description", required=False)
def context_add(ctx: click.Context, path: str, description: str) -> None:
    """Add a context file to initial prompts.

    PATH can be a local file path or URL (GitHub/GitLab).
    DESCRIPTION is a human-readable description of the context file.

    Claude automatically detects which tool to use based on the path:
    - Local paths → Read tool
    - HTTP/HTTPS URLs → WebFetch tool

    If not provided, will prompt for input.

    Examples:
        daf config context add ARCHITECTURE.md "system architecture"
        daf config context add https://github.com/YOUR-ORG/.github/blob/main/STANDARDS.md "coding standards"
        daf config context add          # Interactive mode
    """
    from devflow.cli.commands.context_commands import add_context_file

    add_context_file(path, description)


@context.command(name="remove")
@json_option
@click.argument("path", required=False)
def context_remove(ctx: click.Context, path: str) -> None:
    """Remove a context file from initial prompts.

    PATH is the file path or URL to remove.
    If not provided, will show a list and prompt for selection.

    Examples:
        daf config context remove ARCHITECTURE.md
        daf config context remove https://github.com/YOUR-ORG/.github/blob/main/STANDARDS.md
        daf config context remove          # Interactive mode
    """
    from devflow.cli.commands.context_commands import remove_context_file

    remove_context_file(path)


@context.command(name="reset")
@json_option
def context_reset(ctx: click.Context) -> None:
    """Reset context files to defaults (clear all configured files).

    This removes all configured context files, keeping only the defaults:
    - AGENTS.md (agent-specific instructions)
    - CLAUDE.md (project guidelines and standards)

    Example:
        daf config context reset
    """
    from devflow.cli.commands.context_commands import reset_context_files

    reset_context_files()


@config.command(name="validate")
@json_option
def config_validate(ctx: click.Context) -> None:
    """Validate configuration file against JSON Schema.

    Validates config.json using the Pydantic model schema.
    Reports any validation errors found.

    Example:
        daf config validate
    """
    from devflow.config.loader import ConfigLoader

    output_json = ctx.obj.get('output_json', False)

    config_loader = ConfigLoader()
    config_path = config_loader.config_file

    if not config_path.exists():
        if output_json:
            import json as json_module
            print(json_module.dumps({
                "valid": False,
                "error": "Config file not found"
            }))
        else:
            console.print("[red]✗[/red] Config file not found")
            console.print(f"[dim]Expected: {config_path}[/dim]")
            console.print("[dim]Run 'daf init' to create configuration[/dim]")
        raise click.exceptions.Exit(1)

    is_valid, error_message = config_loader.validate_config_file()

    if output_json:
        import json as json_module
        result = {"valid": is_valid}
        if error_message:
            result["error"] = error_message
        print(json_module.dumps(result))
    else:
        if is_valid:
            console.print("[green]✓[/green] Configuration is valid")
        else:
            console.print("[red]✗[/red] Configuration validation failed:")
            console.print()
            console.print(error_message)
            raise click.exceptions.Exit(1)


@config.command(name="generate-schema")
@json_option
@click.option("--output", "-o", help="Output path for schema file (default: config.schema.json)")
def config_generate_schema(ctx: click.Context, output: str) -> None:
    """Generate JSON Schema file from Pydantic models.

    Generates a JSON Schema file (config.schema.json) that can be used to:
    - Validate config.json in editors (VSCode, IntelliJ, etc.)
    - Validate config files with external tools
    - Document the configuration schema

    The schema is auto-generated from the Pydantic models, ensuring it's
    always in sync with the validation code.

    Example:
        daf config generate-schema
        daf config generate-schema --output /path/to/schema.json
    """
    from pathlib import Path
    from devflow.config.schema import save_schema

    output_json = ctx.obj.get('output_json', False)

    try:
        if output:
            output_path = Path(output).expanduser().resolve()
        else:
            output_path = None  # Use default

        schema_path = save_schema(output_path)

        if output_json:
            import json as json_module
            print(json_module.dumps({
                "success": True,
                "schema_path": str(schema_path)
            }))
        else:
            console.print(f"[green]✓[/green] JSON Schema generated: {schema_path}")
            console.print()
            console.print("[dim]This schema can be used to validate config.json in editors like VSCode[/dim]")
            console.print("[dim]For VSCode, add this to .vscode/settings.json:[/dim]")
            console.print()
            console.print('[dim]  "json.schemas": [{[/dim]')
            console.print(f'[dim]    "fileMatch": ["$DEVAIFLOW_HOME/config.json"],[/dim]')
            console.print(f'[dim]    "url": "{schema_path}"[/dim]')
            console.print('[dim]  }][/dim]')

    except Exception as e:
        if output_json:
            import json as json_module
            print(json_module.dumps({
                "success": False,
                "error": str(e)
            }))
        else:
            console.print(f"[red]✗[/red] Failed to generate schema: {e}")
        raise click.exceptions.Exit(1)


@config.command(name="export")
@click.option("--output", "-o", help="Output file path (default: ~/config-export.tar.gz)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompts")
def config_export(output: str, force: bool) -> None:
    """Export configuration files for user onboarding.

    Exports all configuration files (config.json, organization.json, team.json,
    enterprise.json, backends/jira.json) to a tar.gz archive that can be shared
    with teammates for quick onboarding.

    The export command will:
    - Scan for local file paths that won't work on other machines
    - Display warnings about file:// URLs and absolute paths
    - Suggest converting to GitHub/GitLab URLs
    - Ask for confirmation before exporting

    Example:
        daf config export
        daf config export --output /tmp/my-config.tar.gz
        daf config export --force  # Skip confirmation
    """
    from devflow.cli.commands.config_export_command import export_config
    export_config(output=output, force=force)


@config.command(name="import")
@click.argument("export_file", type=click.Path(exists=True))
@click.option("--merge", is_flag=True, default=True, help="Merge with existing config (default)")
@click.option("--replace", is_flag=True, help="Replace existing config entirely")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompts")
def config_import(export_file: str, merge: bool, replace: bool, force: bool) -> None:
    """Import configuration from export file.

    Imports configuration files from a tar.gz archive created by 'daf config export'.

    Import modes:
    - --merge (default): Merge with existing config, preserving workspace paths
    - --replace: Replace existing config entirely

    After importing, you should run 'daf upgrade' to install skills and update
    field mappings.

    Example:
        daf config import config-export.tar.gz
        daf config import config-export.tar.gz --replace
        daf config import config-export.tar.gz --force  # Skip confirmation
    """
    from devflow.cli.commands.config_import_command import import_config
    import_config(export_file=export_file, merge=merge, replace=replace, force=force)


@cli.group()
@json_option
def template(ctx: click.Context) -> None:
    """Manage session templates."""
    pass


@template.command(name="save")
@json_option
@click.argument("identifier", shell_complete=complete_session_identifiers)
@click.argument("template_name")
@click.option("--description", help="Template description")
def template_save(ctx: click.Context, identifier: str, template_name: str, description: str) -> None:
    """Save a session as a template.

    IDENTIFIER can be either a session group name or issue tracker key.
    TEMPLATE_NAME is the name for the new template.
    """
    from devflow.cli.commands.template_commands import save_template

    save_template(identifier, template_name, description)


@template.command(name="list")
@json_option
def template_list(ctx: click.Context) -> None:
    """List all available templates."""
    from devflow.cli.commands.template_commands import list_templates

    list_templates()


@template.command(name="show")
@json_option
@click.argument("template_name")
def template_show(ctx: click.Context, template_name: str) -> None:
    """Show details of a template.

    TEMPLATE_NAME is the name of the template to display.
    """
    from devflow.cli.commands.template_commands import show_template

    show_template(template_name)


@template.command(name="delete")
@json_option
@click.argument("template_name")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def template_delete(ctx: click.Context, template_name: str, force: bool) -> None:
    """Delete a template.

    TEMPLATE_NAME is the name of the template to delete.
    """
    from devflow.cli.commands.template_commands import delete_template

    delete_template(template_name, force)


# Workspace management commands (AAP-63377)
@cli.group()
@json_option
def workspace(ctx: click.Context) -> None:
    """Manage multiple named workspaces for concurrent development."""
    pass


@workspace.command(name="list")
@json_option
def workspace_list(ctx: click.Context) -> None:
    """List all configured workspaces.

    Shows workspace name, path, and default status.

    Example:
        daf workspace list
    """
    from devflow.cli.commands.workspace_commands import list_workspaces

    list_workspaces()


@workspace.command(name="add")
@json_option
@click.argument("name", required=False)
@click.argument("path", required=False)
@click.option("--default", "set_default", is_flag=True, help="Set as default workspace")
def workspace_add(ctx: click.Context, name: str, path: str, set_default: bool) -> None:
    """Add a new workspace.

    NAME is a unique workspace identifier (e.g., 'primary', 'product-a', 'feat-caching').
    PATH is the directory path for the workspace (supports ~ expansion).

    If only PATH is provided (looks like a path with /), the workspace name
    will be auto-derived from the last directory component.

    If not provided, will prompt for input.

    Examples:
        daf workspace add primary ~/development --default
        daf workspace add product-a ~/repos/product-a
        daf workspace add ~/development/my-project        # Auto-derives name: my-project
        daf workspace add                                  # Interactive mode
    """
    from devflow.cli.commands.workspace_commands import add_workspace

    add_workspace(name, path, set_default)


@workspace.command(name="remove")
@json_option
@click.argument("name", required=False)
def workspace_remove(ctx: click.Context, name: str) -> None:
    """Remove a workspace.

    NAME is the workspace to remove.
    If not provided, will show a list and prompt for selection.

    Examples:
        daf workspace remove feat-caching
        daf workspace remove          # Interactive mode
    """
    from devflow.cli.commands.workspace_commands import remove_workspace

    remove_workspace(name)


@workspace.command(name="set-default")
@json_option
@click.argument("name", required=False)
def workspace_set_default(ctx: click.Context, name: str) -> None:
    """Set a workspace as the default.

    NAME is the workspace to set as default.
    If not provided, will show a list and prompt for selection.

    The default workspace is used when no --workspace flag is provided
    and the session doesn't have a stored workspace preference.

    Examples:
        daf workspace set-default primary
        daf workspace set-default          # Interactive mode
    """
    from devflow.cli.commands.workspace_commands import set_default_workspace

    set_default_workspace(name)


@workspace.command(name="rename")
@json_option
@click.argument("old_name", required=False)
@click.argument("new_name", required=False)
def workspace_rename(ctx: click.Context, old_name: str, new_name: str) -> None:
    """Rename a workspace.

    OLD_NAME is the current workspace name.
    NEW_NAME is the new workspace name.
    If not provided, will prompt for input.

    This command also updates all sessions that use the old workspace name
    to use the new name automatically.

    Examples:
        daf workspace rename old-name new-name
        daf workspace rename                   # Interactive mode
    """
    from devflow.cli.commands.workspace_commands import rename_workspace

    rename_workspace(old_name, new_name)


@cli.group()
@json_option
def agent(ctx: click.Context) -> None:
    """Manage AI agent backends and switch between agents."""
    pass


@agent.command(name="list")
@json_option
def agent_list(ctx: click.Context) -> None:
    """List all supported AI agents with installation status.

    Shows agent name, description, installation status, and capabilities.

    Example:
        daf agent list
        daf agent list --json
    """
    from devflow.cli.commands.agent_commands import list_agents

    list_agents(output_json=ctx.obj.get('output_json', False))


@agent.command(name="set-default")
@json_option
@click.argument("name", required=False)
def agent_set_default(ctx: click.Context, name: str) -> None:
    """Set the default AI agent backend.

    NAME is the agent to use (e.g., 'claude', 'ollama', 'cursor').

    If not provided, will prompt with a list of available agents.

    Examples:
        daf agent set-default claude
        daf agent set-default ollama
        daf agent set-default          # Interactive mode
    """
    from devflow.cli.commands.agent_commands import set_default_agent

    set_default_agent(name, output_json=ctx.obj.get('output_json', False))


@agent.command(name="test")
@json_option
@click.argument("name", required=False)
def agent_test(ctx: click.Context, name: str) -> None:
    """Test if an agent is available and working.

    NAME is the agent to test (e.g., 'claude', 'ollama').
    Defaults to the active/default agent if not specified.

    Examples:
        daf agent test claude
        daf agent test ollama
        daf agent test              # Test default agent
    """
    from devflow.cli.commands.agent_commands import test_agent

    test_agent(name, output_json=ctx.obj.get('output_json', False))


@agent.command(name="info")
@json_option
@click.argument("name", required=False)
def agent_info(ctx: click.Context, name: str) -> None:
    """Show detailed information about an agent.

    NAME is the agent to show info for (e.g., 'claude', 'ollama').
    Defaults to the active/default agent if not specified.

    Displays:
    - Installation status and CLI path
    - Supported features
    - Installation instructions
    - Additional requirements

    Examples:
        daf agent info claude
        daf agent info ollama
        daf agent info              # Show default agent
    """
    from devflow.cli.commands.agent_commands import show_agent_info

    show_agent_info(name, output_json=ctx.obj.get('output_json', False))


@agent.command(name="active")
@json_option
def agent_active(ctx: click.Context) -> None:
    """Show the currently active/default agent.

    Convenient alias for 'daf agent info' without arguments.

    Examples:
        daf agent active
        daf agent active --json
    """
    from devflow.cli.commands.agent_commands import show_agent_info

    show_agent_info(None, output_json=ctx.obj.get('output_json', False))


@cli.group()
@json_option
def provider(ctx: click.Context) -> None:
    """Manage model provider profiles for alternative AI providers."""
    pass


@provider.command(name="list")
@json_option
def provider_list(ctx: click.Context) -> None:
    """List all configured model provider profiles.

    Shows profile name, base URL, model, type, and default status.

    Example:
        daf provider list
        daf provider list --json
    """
    from devflow.cli.commands.provider_commands import list_profiles

    list_profiles(output_json=ctx.obj.get('output_json', False))


@provider.command(name="add")
@json_option
@click.argument("name", required=False)
def provider_add(ctx: click.Context, name: str) -> None:
    """Add a new model provider profile.

    NAME is a unique profile identifier (e.g., 'vertex', 'llama-cpp', 'openrouter').

    If not provided, will prompt for input and guide through profile configuration.

    Supported providers:
      - Anthropic Claude (default)
      - Google Vertex AI
      - Local llama.cpp server
      - Custom providers (OpenRouter, etc.)

    Examples:
        daf provider add vertex              # Interactive wizard for Vertex AI
        daf provider add llama-cpp           # Interactive wizard for llama.cpp
        daf provider add                     # Interactive mode (prompts for name)
    """
    from devflow.cli.commands.provider_commands import add_profile

    add_profile(name=name, interactive=True, output_json=ctx.obj.get('output_json', False))


@provider.command(name="remove")
@json_option
@click.argument("name", required=False)
def provider_remove(ctx: click.Context, name: str) -> None:
    """Remove a model provider profile.

    NAME is the profile to remove.
    If not provided, will show a list and prompt for selection.

    Examples:
        daf provider remove llama-cpp
        daf provider remove          # Interactive mode
    """
    from devflow.cli.commands.provider_commands import remove_profile

    remove_profile(name=name, output_json=ctx.obj.get('output_json', False))


@provider.command(name="set-default")
@json_option
@click.argument("name", required=False)
def provider_set_default(ctx: click.Context, name: str) -> None:
    """Set a profile as the default.

    NAME is the profile to set as default.
    If not provided, will show a list and prompt for selection.

    The default profile is used when no --model-profile flag is provided
    in daf new/open commands.

    Examples:
        daf provider set-default vertex
        daf provider set-default          # Interactive mode
    """
    from devflow.cli.commands.provider_commands import set_default_profile

    set_default_profile(name=name, output_json=ctx.obj.get('output_json', False))


@provider.command(name="show")
@json_option
@click.argument("name", required=False)
def provider_show(ctx: click.Context, name: str) -> None:
    """Show configuration for a specific profile.

    NAME is the profile to show.
    Defaults to the active/default profile if not specified.

    Examples:
        daf provider show vertex
        daf provider show              # Shows default profile
        daf provider show --json
    """
    from devflow.cli.commands.provider_commands import show_profile

    show_profile(name=name, output_json=ctx.obj.get('output_json', False))


@provider.command(name="active")
@json_option
def provider_active(ctx: click.Context) -> None:
    """Show the currently active/default model profile.

    Convenient alias for 'daf provider show' without arguments.

    Examples:
        daf provider active
        daf provider active --json
    """
    from devflow.cli.commands.provider_commands import show_profile

    show_profile(name=None, output_json=ctx.obj.get('output_json', False))


@provider.command(name="test")
@json_option
@click.argument("name", required=False)
def provider_test(ctx: click.Context, name: str) -> None:
    """Test and validate a profile configuration.

    NAME is the profile to test.
    Defaults to the active/default profile if not specified.

    Validates:
      - Required fields are present
      - URL formats are correct
      - Configuration is internally consistent

    Note: This validates configuration only. To test actual connectivity,
    use the profile with Claude Code.

    Examples:
        daf provider test vertex
        daf provider test              # Tests default profile
        daf provider test --json
    """
    from devflow.cli.commands.provider_commands import test_profile

    test_profile(name=name, output_json=ctx.obj.get('output_json', False))


@cli.command()
@click.option("--check", is_flag=True, help="Check external tool dependencies instead of initializing")
@click.option("--refresh", is_flag=True, help="Refresh automatically discovered data (custom field mappings)")
@click.option("--reset", is_flag=True, help="Re-prompt for all configuration values")
@click.option("--skip-jira-discovery", is_flag=True, help="Skip JIRA field discovery during init")
@json_option
def init(ctx: click.Context, check: bool, refresh: bool, reset: bool, skip_jira_discovery: bool) -> None:
    """Initialize, refresh, or review configuration.

    Use --refresh to update automatically discovered data (JIRA custom field mappings)
    without changing user-provided configuration values.

    Use --reset to re-prompt for all configuration values using current values as defaults.
    """
    # Handle --check flag (check external dependencies)
    if check:
        from devflow.cli.commands.check_command import check_dependencies
        output_json = ctx.obj.get('output_json', False) if ctx.obj else False
        exit_code = check_dependencies(output_json=output_json)
        raise SystemExit(exit_code)

    from devflow.config.loader import ConfigLoader
    from devflow.jira.client import JiraClient
    from devflow.jira.field_mapper import JiraFieldMapper
    from rich.prompt import Prompt, Confirm
    import os

    config_loader = ConfigLoader()

    # Check if config exists
    config_exists = config_loader.config_file.exists()

    # Validate flags
    if refresh and reset:
        console.print("[red]✗[/red] Cannot use --refresh and --reset together")
        console.print("Use either --refresh or --reset, not both")
        return

    # Handle --reset flag (re-prompt for all values)
    if reset:
        if not config_exists:
            console.print("[yellow]⚠[/yellow] No configuration to reset")
            console.print("Run [cyan]daf init[/cyan] to create initial configuration")
            return

        # Load current config
        console.print("Reviewing configuration values...")
        console.print("Current values shown as defaults. Press Enter to keep, or type new value.")
        console.print()

        try:
            current_config = config_loader.load_config()
        except Exception as e:
            console.print(f"[red]✗[/red] Could not load config: {e}")
            console.print("Please fix config.json manually or delete it and run [cyan]daf init[/cyan]")
            return

        # Run interactive wizard with current values as defaults
        from devflow.config.init_wizard import run_init_wizard
        new_config = run_init_wizard(current_config)

        # Always re-discover JIRA field mappings (unless explicitly skipped)
        if not skip_jira_discovery:
            console.print()
            console.print("Discovering JIRA custom field mappings...")
            _discover_and_cache_jira_fields(new_config, config_loader)
        else:
            # Save config without field discovery - preserve existing field mappings
            new_config.jira.field_mappings = current_config.jira.field_mappings
            new_config.jira.field_cache_timestamp = current_config.jira.field_cache_timestamp
            config_loader.save_config(new_config)

        # Show summary of changes
        console.print()
        console.print("[green]✓[/green] Configuration updated")
        console.print(f"Location: {config_loader.config_file}")

        # Show what changed
        changes = _get_config_changes(current_config, new_config)
        if changes:
            console.print()
            console.print("Changes:")
            for change in changes:
                console.print(f"  • {change}")
        else:
            console.print()
            console.print("No changes made")

        return

    if not config_exists:
        # First-time setup
        if refresh:
            console.print("[red]✗[/red] No configuration found. Cannot refresh without existing config.")
            console.print("  Run [cyan]daf init[/cyan] (without --refresh) to create initial configuration.")
            return

        # Ask if user wants JIRA integration
        console.print("\n[bold]=== Initial Setup ===[/bold]\n")
        enable_jira = Confirm.ask("Do you want to integrate with JIRA?", default=True)

        if enable_jira:
            # Run interactive wizard to collect JIRA URL and other settings
            from devflow.config.init_wizard import run_init_wizard
            console.print("\nCollecting configuration values...")
            console.print()
            config = run_init_wizard(current_config=None)
            config_loader.save_config(config)
            console.print(f"\n[green]✓[/green] Configuration saved")
            console.print(f"Location: {config_loader.config_file}")

            # Check JIRA authentication environment variables
            console.print("\n[bold]JIRA Authentication Check[/bold]")
            jira_token = os.getenv("JIRA_API_TOKEN")
            jira_auth_type = os.getenv("JIRA_AUTH_TYPE", "bearer")

            if not jira_token:
                console.print("[yellow]⚠[/yellow] JIRA_API_TOKEN environment variable is not set")
                console.print("  You need to set this to authenticate with JIRA:")
                console.print("  [cyan]export JIRA_API_TOKEN='your-jira-api-token'[/cyan]")
                console.print("  Generate a token at: [dim]https://id.atlassian.com/manage-profile/security/api-tokens[/dim]")
            else:
                console.print(f"[green]✓[/green] JIRA_API_TOKEN is set")
                console.print(f"[dim]  Authentication type: {jira_auth_type}[/dim]")
                if jira_auth_type != "bearer" and jira_auth_type != "basic":
                    console.print(f"[yellow]⚠[/yellow] Unknown JIRA_AUTH_TYPE: {jira_auth_type}")
                    console.print("  Supported types: 'bearer' (default), 'basic'")

            # Validate JIRA URL before attempting field discovery
            if not _validate_jira_url(config.jira.url):
                console.print(f"[yellow]⚠[/yellow] JIRA URL appears to be invalid or unreachable: {config.jira.url}")
                console.print("  You can update it later with: [cyan]daf init --reset[/cyan]")
                console.print("  Then run field discovery with: [cyan]daf config refresh-jira-fields[/cyan]")
            elif not skip_jira_discovery:
                # Only attempt field discovery if both JIRA_API_TOKEN and project key are set
                if not jira_token:
                    console.print("\n[dim]Skipping JIRA field discovery (JIRA_API_TOKEN not set)[/dim]")
                    console.print("[dim]Run [cyan]daf config refresh-jira-fields[/cyan] after setting the token[/dim]")
                elif not config.jira.project:
                    console.print("\n[yellow]⚠[/yellow] Project key not set - skipping field discovery")
                    console.print("[dim]  Limited functionality: Cannot create JIRA issues until project key is set[/dim]")
                    console.print("[dim]  Set project key with: [cyan]daf config edit[/cyan] or [cyan]daf init --reset[/cyan][/dim]")
                    console.print("[dim]  Then run: [cyan]daf config refresh-jira-fields[/cyan][/dim]")
                else:
                    # Ask if user wants to discover fields now
                    console.print("\n[bold]JIRA Field Discovery[/bold]")
                    if Confirm.ask("Discover JIRA custom fields now?", default=True):
                        _discover_and_cache_jira_fields(config, config_loader)
        else:
            # Create default config without JIRA prompts
            config = config_loader.create_default_config()
            config_loader.save_config(config)
            console.print(f"\n[green]✓[/green] Created default configuration")
            console.print(f"Location: {config_loader.config_file}")
            console.print("\n[dim]JIRA integration skipped. You can configure it later with:[/dim]")
            console.print("  [cyan]daf init --reset[/cyan]")

        console.print("\n[yellow]Please review and edit the configuration file:[/yellow]")
        console.print("  - JIRA URL and project")
        console.print("  - Repository workspace path")
        console.print("  - Keyword mappings for smart repo detection")
        console.print("  - Custom field defaults (if needed) via [cyan]daf config edit[/cyan]")

        console.print("\n[bold cyan]Next Step: Install Claude Code Commands[/bold cyan]")
        console.print("To use DevAIFlow commands in Claude Code sessions:")
        console.print("  [cyan]daf upgrade[/cyan]")
        console.print()
        console.print("[dim]This installs /daf-* slash commands into Claude Code[/dim]")

        # Offer to set up shell completion
        _setup_shell_completion_if_desired()

        return

    # Config exists
    if not refresh:
        # No --refresh flag, show helpful message
        console.print("Configuration already exists")
        console.print(f"Location: {config_loader.config_file}")
        console.print()
        console.print("To refresh automatically discovered data (custom field mappings):")
        console.print("  [cyan]daf init --refresh[/cyan]")
        console.print()
        console.print("To review and update all configuration values:")
        console.print("  [cyan]daf init --reset[/cyan]")
        console.print()
        console.print("To update specific configuration values:")
        console.print("  - Edit config.json manually")
        console.print("  - Use: [cyan]daf config edit <WORKSTREAM>[/cyan]")
        return

    # Refresh mode - only update automatically discovered data
    console.print("Refreshing automatically discovered data...")
    console.print()

    # Load existing config
    config = config_loader.load_config()

    if not config or not config.jira:
        console.print("[red]✗[/red] Invalid configuration. Please check config.json")
        return

    # Refresh JIRA field mappings
    _discover_and_cache_jira_fields(config, config_loader)

    console.print()
    console.print("[green]✓[/green] Configuration refreshed")
    console.print(f"Location: {config_loader.config_file}")


def _setup_shell_completion_if_desired() -> None:
    """Offer to set up shell completion automatically during init."""
    import os
    from pathlib import Path
    from rich.prompt import Confirm

    # Skip in test/CI environments
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CI"):
        return

    # Auto-detect shell
    shell_env = os.environ.get("SHELL", "")
    if "bash" in shell_env:
        shell = "bash"
        shell_file = Path.home() / ".bashrc"
        completion_line = 'eval "$(_DAF_COMPLETE=bash_source daf)"'
    elif "zsh" in shell_env:
        shell = "zsh"
        shell_file = Path.home() / ".zshrc"
        completion_line = 'eval "$(_DAF_COMPLETE=zsh_source daf)"'
    elif "fish" in shell_env:
        shell = "fish"
        shell_file = Path.home() / ".config" / "fish" / "completions" / "daf.fish"
        completion_line = None  # Fish uses a different approach
    else:
        # Can't detect shell, show manual instructions
        console.print("\n[bold cyan]Optional: Set Up Shell Completion[/bold cyan]")
        console.print("Run [cyan]daf completion[/cyan] to set up command auto-completion")
        return

    # Check if completion is already set up
    if shell == "fish":
        if shell_file.exists():
            console.print("\n[dim]Fish shell completion already configured[/dim]")
            return
    else:
        if shell_file.exists():
            content = shell_file.read_text()
            if completion_line in content:
                console.print(f"\n[dim]{shell.capitalize()} shell completion already configured[/dim]")
                return

    # Ask if user wants to set up completion
    console.print(f"\n[bold cyan]Optional: Set Up {shell.capitalize()} Shell Completion[/bold cyan]")
    if not Confirm.ask(f"Add command auto-completion to {shell_file}?", default=True):
        console.print(f"[dim]Skipped. Run [cyan]daf completion[/cyan] later to set up manually[/dim]")
        return

    try:
        if shell == "fish":
            # For fish, generate completion file
            shell_file.parent.mkdir(parents=True, exist_ok=True)
            import subprocess
            result = subprocess.run(
                ["daf", "--help"],  # Test if daf is in PATH
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                # Generate fish completion
                subprocess.run(
                    f'_DAF_COMPLETE=fish_source daf > "{shell_file}"',
                    shell=True,
                    check=True,
                )
                console.print(f"[green]✓[/green] Fish completion installed to {shell_file}")
                console.print("[dim]Restart your fish shell or run: source ~/.config/fish/config.fish[/dim]")
            else:
                console.print(f"[yellow]Could not generate fish completion[/yellow]")
                console.print(f"[dim]Run [cyan]daf completion fish[/cyan] for manual setup instructions[/dim]")
        else:
            # For bash/zsh, append to config file
            with open(shell_file, "a") as f:
                f.write(f"\n# daf command completion\n{completion_line}\n")
            console.print(f"[green]✓[/green] Added completion to {shell_file}")
            console.print(f"[dim]Restart your shell or run: source {shell_file}[/dim]")

    except Exception as e:
        console.print(f"[yellow]Could not set up completion automatically: {e}[/yellow]")
        console.print(f"[dim]Run [cyan]daf completion[/cyan] for manual setup instructions[/dim]")


def _validate_jira_url(url: str) -> bool:
    """Validate JIRA URL by checking if it's reachable.

    Args:
        url: JIRA URL to validate

    Returns:
        True if URL appears valid and reachable, False otherwise
    """
    # Check for example/placeholder URLs
    if "example.com" in url.lower() or not url.startswith(("http://", "https://")):
        return False

    # Try to make a simple request to verify the URL is reachable
    import requests
    try:
        # Use a simple HEAD request with short timeout
        response = requests.head(url, timeout=5, allow_redirects=True)
        # Accept any response that doesn't indicate a connection error
        # (we don't check auth here, just reachability)
        return True
    except (requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException):
        return False


def _discover_and_cache_jira_fields(config, config_loader) -> None:
    """Helper function to discover and cache JIRA creation fields.

    Args:
        config: Config object
        config_loader: ConfigLoader instance
    """
    from devflow.jira.client import JiraClient
    from devflow.jira.field_mapper import JiraFieldMapper
    from datetime import datetime

    try:
        console.print(f"\nDiscovering JIRA custom fields for project {config.jira.project}...")

        jira_client = JiraClient()
        field_mapper = JiraFieldMapper(jira_client)

        field_mappings = field_mapper.discover_fields(config.jira.project)

        console.print(f"[green]✓[/green] Found {len(field_mappings)} custom fields")

        # Update config with field mappings
        config.jira.field_mappings = field_mappings
        config.jira.field_cache_timestamp = datetime.now().isoformat()

        # Save updated config
        config_loader.save_config(config)
        console.print("[green]✓[/green] Cached field mappings to config")

    except RuntimeError as e:
        console.print(f"[yellow]⚠[/yellow] Could not discover fields: {e}")
        console.print("  You can refresh field mappings later with: [cyan]daf config refresh-jira-fields[/cyan]")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Unexpected error during field discovery: {e}")
        console.print("  You can refresh field mappings later with: [cyan]daf config refresh-jira-fields[/cyan]")


def _get_config_changes(old_config, new_config) -> list:
    """Get list of configuration changes between old and new config.

    Args:
        old_config: Old Config object
        new_config: New Config object

    Returns:
        List of change description strings
    """
    changes = []

    # Compare JIRA settings
    if old_config.jira.url != new_config.jira.url:
        changes.append(f"JIRA URL: {old_config.jira.url} → {new_config.jira.url}")

    if old_config.jira.project != new_config.jira.project:
        changes.append(f"JIRA Project: {old_config.jira.project} → {new_config.jira.project}")

    if old_config.jira.custom_field_defaults != new_config.jira.custom_field_defaults:
        old_defaults = old_config.jira.custom_field_defaults or {}
        new_defaults = new_config.jira.custom_field_defaults or {}
        if old_defaults != new_defaults:
            changes.append(f"Custom Field Defaults: {old_defaults} → {new_defaults}")

    # Compare repository settings
    # Compare workspaces lists (comparing all properties)
    old_workspaces = {ws.name: ws.path for ws in old_config.repos.workspaces} if old_config.repos.workspaces else {}
    new_workspaces = {ws.name: ws.path for ws in new_config.repos.workspaces} if new_config.repos.workspaces else {}
    if old_workspaces != new_workspaces:
        changes.append(f"Workspaces: {len(old_workspaces)} → {len(new_workspaces)} configured")

    # Compare keywords (simplified comparison)
    old_keywords = set(old_config.repos.keywords.keys())
    new_keywords = set(new_config.repos.keywords.keys())

    added_keywords = new_keywords - old_keywords
    removed_keywords = old_keywords - new_keywords

    if added_keywords:
        changes.append(f"Keywords added: {', '.join(sorted(added_keywords))}")
    if removed_keywords:
        changes.append(f"Keywords removed: {', '.join(sorted(removed_keywords))}")

    # Check for modified keyword mappings
    for keyword in old_keywords & new_keywords:
        old_repos = set(old_config.repos.keywords[keyword])
        new_repos = set(new_config.repos.keywords[keyword])
        if old_repos != new_repos:
            changes.append(f"Keyword '{keyword}' mapping changed")

    return changes


@cli.command(hidden=True)
@json_option
def check(ctx: click.Context) -> None:
    """[Hidden] Check external tool dependencies.

    Use 'daf init --check' instead.

    Verifies that all required and optional external tools are installed
    and available in PATH. Displays version information for available tools
    and installation URLs for missing tools.

    \b
    Required dependencies:
      - git: Version control operations
      - claude: Claude Code CLI for session launching

    \b
    Optional dependencies:
      - gh: GitHub CLI for PR creation
      - glab: GitLab CLI for MR creation
      - pytest: Python testing framework

    \b
    Examples:
      daf check              # Check all dependencies
      daf check --json       # JSON output for automation

    \b
    Exit codes:
      0: All required dependencies available
      1: One or more required dependencies missing
    """
    from devflow.cli.commands.check_command import check_dependencies

    output_json = ctx.obj.get('output_json', False) if ctx.obj else False
    exit_code = check_dependencies(output_json=output_json)
    raise SystemExit(exit_code)


@cli.command(hidden=True)
@json_option
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False), required=False)
def completion(ctx: click.Context, shell: str) -> None:
    """[Hidden] Install shell completion for daf command.

    Shell completion is now automatically offered during 'daf init'.
    This command remains available for manual setup if needed.

    SHELL can be bash, zsh, or fish. If not specified, auto-detects your shell.

    Installation instructions:

    Bash:
      Add to ~/.bashrc:
      eval "$(_DAF_COMPLETE=bash_source daf)"

    Zsh:
      Add to ~/.zshrc:
      eval "$(_DAF_COMPLETE=zsh_source daf)"

    Fish:
      Save to ~/.config/fish/completions/daf.fish:
      _DAF_COMPLETE=fish_source daf > ~/.config/fish/completions/daf.fish

    See COMPLETION.md for detailed instructions.
    """
    import os

    # Auto-detect shell if not specified
    if not shell:
        shell_env = os.environ.get("SHELL", "")
        if "bash" in shell_env:
            shell = "bash"
        elif "zsh" in shell_env:
            shell = "zsh"
        elif "fish" in shell_env:
            shell = "fish"
        else:
            console.print("[red]Could not auto-detect shell. Please specify: daf completion [bash|zsh|fish][/red]")
            return

    shell = shell.lower()

    if shell == "bash":
        console.print("[bold]Bash Completion Setup[/bold]\n")
        console.print("Add the following line to your ~/.bashrc:\n")
        console.print('  [cyan]eval "$(_DAF_COMPLETE=bash_source daf)"[/cyan]\n')
        console.print("Then reload your shell:")
        console.print("  [cyan]source ~/.bashrc[/cyan]\n")

    elif shell == "zsh":
        console.print("[bold]Zsh Completion Setup[/bold]\n")
        console.print("Add the following line to your ~/.zshrc:\n")
        console.print('  [cyan]eval "$(_DAF_COMPLETE=zsh_source daf)"[/cyan]\n')
        console.print("Then reload your shell:")
        console.print("  [cyan]source ~/.zshrc[/cyan]\n")

    elif shell == "fish":
        console.print("[bold]Fish Completion Setup[/bold]\n")
        console.print("Run the following command:\n")
        console.print('  [cyan]_DAF_COMPLETE=fish_source daf > ~/.config/fish/completions/daf.fish[/cyan]\n')
        console.print("Then reload:")
        console.print("  [cyan]source ~/.config/fish/config.fish[/cyan]\n")

    console.print("[dim]See COMPLETION.md for more details and troubleshooting.[/dim]")


@cli.command(name="purge-mock-data", hidden=True)
@json_option
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def purge_mock_data_cmd(ctx: click.Context, force: bool) -> None:
    """Purge all mock data (hidden developer/testing utility).

    This command is hidden from main help but available for developers
    and automated testing. To clean mock data, you can also manually
    delete the $DEVAIFLOW_HOME/mocks/ directory.
    """
    from devflow.mocks.persistence import MockDataStore
    from rich.prompt import Confirm

    store = MockDataStore()

    console.print()
    console.print("[bold yellow]⚠️  WARNING: This will purge ALL mock data[/bold yellow]")
    console.print()
    console.print("The following will be [bold red]permanently deleted[/bold red]:")
    console.print("  • Mock sessions")
    console.print("  • Mock issue tracker tickets and comments")
    console.print("  • Mock GitHub pull requests")
    console.print("  • Mock GitLab merge requests")
    console.print("  • Mock Claude Code sessions")
    console.print()
    console.print(f"[dim]Location: {store.data_dir}[/dim]")
    console.print()

    if not force:
        if not Confirm.ask("[yellow]Are you sure you want to purge all mock data?[/yellow]", default=False):
            console.print("[dim]Cancelled.[/dim]")
            return

    try:
        store.clear_all()
        console.print()
        console.print("[green]✓[/green] Mock data purged successfully")
        console.print("[dim]You can now start fresh with mock testing.[/dim]")
    except Exception as e:
        console.print()
        console.print(f"[red]✗[/red] Failed to purge mock data: {e}")
        raise


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be upgraded without actually upgrading")
@click.option("--commands-only", is_flag=True, help="Upgrade only bundled slash commands")
@click.option("--skills-only", is_flag=True, help="Upgrade only bundled skills")
@click.option("--project-path", type=click.Path(), help="Install skills to project directory (e.g., '.', '/path/to/project')")
@json_option
def upgrade(ctx: click.Context, dry_run: bool, commands_only: bool, skills_only: bool, project_path: str) -> None:
    """Upgrade bundled Claude Code skills.

    This command installs skills to ~/.claude/skills/ (global) by default.
    Use --project-path to install to a specific project directory instead.

    Installation locations:
    - Default: ~/.claude/skills/ (available in all projects)
    - With --project-path: <project>/.claude/skills/ (project-specific)
    - Hierarchical skills: ~/.daf-sessions/.claude/skills/ (organization config)

    Skills installed:
    - Slash commands: /daf-active, /daf-help, /daf-info, etc.
    - Reference skills: daf-cli, gh-cli, git-cli, glab-cli
    - Hierarchical skills from organization config files

    Items that are already up-to-date will be skipped.

    Examples:
        daf upgrade                      # Install to ~/.claude/skills/ (global)
        daf upgrade --project-path .     # Install to current directory
        daf upgrade --project-path /path # Install to specific project
        daf upgrade --dry-run            # Preview what would be upgraded
    """
    from devflow.cli.commands.upgrade_command import upgrade_all

    # commands_only and skills_only are deprecated but kept for backward compatibility
    if commands_only or skills_only:
        console.print("[yellow]⚠[/yellow] Note: --commands-only and --skills-only are deprecated.")
        console.print("[dim]All slash commands are now skills. Upgrading all skills...[/dim]")
        console.print()

    upgrade_all(dry_run=dry_run, upgrade_skills=True, project_path=project_path)


# Note: 'import' is a Python keyword, so we name the function import_cmd
# and use @cli.command(name="import") would be better, but Click doesn't allow
# reserving Python keywords. Users will use 'daf import' which maps to import_cmd.
cli.add_command(import_cmd, name="import")


if __name__ == "__main__":
    cli()


@cli.command()
@click.argument("version", required=False)
@click.argument("approve", required=False)
@click.option("--from", "from_tag", help="Base tag for patches (default: latest tag for minor version)")
@click.option("--dry-run", is_flag=True, help="Preview changes without executing")
@click.option("--auto-push", is_flag=True, help="Push to remote without confirmation (use with caution)")
@click.option("--force", is_flag=True, help="Force release even if tests fail (emergency use only)")
@click.option("--suggest", is_flag=True, help="Suggest release type based on commits since last release")
@click.option("--skip-pr-fetch", is_flag=True, help="Skip PR/MR metadata fetching for changelog (offline mode)")
def release(version: str, approve: str, from_tag: str, dry_run: bool, auto_push: bool, force: bool, suggest: bool, skip_pr_fetch: bool) -> None:
    """Create a new release (minor, major, or patch) or approve a prepared release.

    VERSION is the target version (e.g., "1.0.0").

    For release approval, use: daf release <M.m.p> approve

    The command auto-detects release type from version numbers:
    - Minor release: 0.1.x → 0.2.0 (minor version bump)
    - Major release: 0.x.x → 1.0.0 (major version bump)
    - Patch release: 0.1.0 → 0.1.1 (patch version bump)

    \b
    Examples:
        daf release --suggest                        # Analyze commits and suggest release type
        daf release 0.2.0                            # Create minor release
        daf release 1.0.0                            # Create major release
        daf release 0.1.1 --from v0.1.0              # Create patch release from tag
        daf release 0.2.0 --dry-run                  # Preview changes without executing
        daf release 0.2.0 --force                    # Force release despite test failures (emergency)
        daf release 0.2.0 approve                    # Approve and complete prepared release
        daf release 0.2.0 approve --dry-run          # Preview approval steps

    \b
    What 'daf release' does:
    1. Checks release permissions (requires Maintainer or Owner access)
    2. Creates appropriate branch (release/X.Y or hotfix/X.Y.Z)
    3. Updates version in devflow/__init__.py and setup.py
    4. Updates CHANGELOG.md with new version section
    5. Commits version bump
    6. Runs complete unit test suite
    7. Runs integration tests (prompts if failed, unless --force)
    8. Creates annotated git tag (vX.Y.Z)
    9. Bumps to next dev version on release branch
    10. Shows summary and next steps

    \b
    What 'daf release approve' does:
    1. Validates release preparation (tag exists, versions correct)
    2. Pushes release branch and tag to remote
    3. Creates GitLab/GitHub release with CHANGELOG content
    4. For minor/major: merges to main and bumps to next minor dev version

    \b
    Security:
    This command requires Maintainer (GitLab 40) or Owner (GitLab 50) access,
    or "maintain"/"admin" permission on GitHub. Regular developers cannot
    create releases.
    """
    from devflow.cli.commands.release_command import create_release, suggest_release, approve_release

    # If --suggest flag is used, show suggestion and exit
    if suggest:
        suggest_release()
        return

    # If approve subcommand is used, run approval workflow
    if approve == "approve":
        if not version:
            console.print("[red]✗[/red] Version required for approval. Usage: daf release <M.m.p> approve")
            return
        approve_release(version=version, dry_run=dry_run)
        return

    # Otherwise, version is required
    if not version:
        console.print("[red]Error: VERSION argument is required (or use --suggest to get a recommendation)[/red]")
        console.print("Usage: daf release VERSION [OPTIONS]")
        console.print("       daf release --suggest")
        return

    create_release(version, from_tag, dry_run, auto_push, force, skip_pr_fetch)


