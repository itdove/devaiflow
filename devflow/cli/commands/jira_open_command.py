"""Command for daf jira open - open or create session from issue tracker ticket."""

from pathlib import Path
from typing import Optional
from rich.console import Console

from devflow.cli.utils import console_print, require_outside_claude, is_json_mode, output_json
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.jira.utils import validate_jira_ticket

console = Console()


@require_outside_claude
def jira_open_session(issue_key: str) -> None:
    """Open session for issue tracker ticket, creating it if needed.

    This command validates that the issue tracker ticket exists, then either:
    1. Opens the existing session if one exists for this ticket
    2. Creates a new session named 'creation-<issue_key>' if no session exists

    Args:
        issue_key: issue tracker key (e.g., PROJ-12345)
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console_print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        if is_json_mode():
            output_json(success=False, error={"message": "No configuration found", "code": "NO_CONFIG"})
        return

    session_manager = SessionManager(config_loader=config_loader)

    # 1. Check if ticket_creation session already exists
    # Look for session group named "creation-{issue_key}" first
    # This is more specific than just searching by issue_key, which could match development sessions
    session_name = f"creation-{issue_key}"
    sessions = session_manager.index.get_sessions(session_name)

    if sessions:
        # Filter to only ticket_creation sessions
        # daf jira open should only reopen ticket_creation sessions (creation-*)
        # If a development session exists but no creation session, we'll create the creation session below
        ticket_creation_sessions = [s for s in sessions if s.session_type == "ticket_creation"]

        if ticket_creation_sessions:
            # Found ticket_creation session - reopen it (even if complete)
            session = ticket_creation_sessions[0]
            console_print(f"[green]✓[/green] Found existing ticket creation session: [cyan]{session.name}[/cyan]")
            console_print(f"[dim]Session type: {session.session_type}, status: {session.status}[/dim]")

            from devflow.cli.commands.open_command import open_session
            # Use the full session name to avoid infinite loop
            open_session(session.name)
            return
        # If we found sessions but none are ticket_creation, continue to create a new creation-* session
        # This allows creating analysis sessions even when development sessions exist

    # 2. No session found - validate issue tracker ticket exists
    console_print(f"[dim]No existing session found, validating issue tracker ticket...[/dim]")

    from devflow.jira import JiraClient
    try:
        jira_client = JiraClient()
    except Exception as e:
        console_print(f"[red]✗[/red] Failed to initialize JIRA client: {e}")
        if is_json_mode():
            output_json(success=False, error={"message": f"JIRA client initialization failed: {e}", "code": "JIRA_CLIENT_ERROR"})
        return

    ticket = validate_jira_ticket(issue_key, client=jira_client)

    if not ticket:
        # Error already displayed by validate_jira_ticket
        if is_json_mode():
            output_json(success=False, error={"message": f"issue tracker ticket {issue_key} not found or validation failed", "code": "JIRA_TICKET_NOT_FOUND"})
        return

    # 3. Create session from issue tracker ticket
    session_name = f"creation-{issue_key}"
    goal = f"{issue_key}: {ticket['summary']}"

    console_print(f"[green]✓[/green] issue tracker ticket validated: [bold]{issue_key}[/bold]")
    console_print(f"[dim]Creating session: {session_name}[/dim]")

    # Determine project path (use current directory if not specified)
    project_path = str(Path.cwd())
    working_directory = Path(project_path).name

    # Check if we should clone to temporary directory
    # This ensures analysis is based on clean main branch, not current working tree
    temp_directory = None
    original_project_path = None

    from devflow.utils import is_mock_mode
    mock_mode = is_mock_mode()
    should_skip_temp_prompt = mock_mode or is_json_mode()

    if should_skip_temp_prompt:
        console_print(f"[dim]Non-interactive mode - skipping temp directory clone prompt[/dim]")
    else:
        from devflow.utils.temp_directory import should_clone_to_temp, prompt_and_clone_to_temp
        if should_clone_to_temp(Path(project_path)):
            temp_dir_result = prompt_and_clone_to_temp(Path(project_path))
            if temp_dir_result:
                temp_directory, original_project_path = temp_dir_result
                # Use temp directory as project_path for this session
                project_path = temp_directory
                # Use the original repository name for working_directory
                # This ensures consistency with daf jira new behavior
                working_directory = Path(original_project_path).name
                console_print(f"[green]✓[/green] Using temporary clone: {temp_directory}")
            else:
                console_print(f"[dim]User declined temp clone or cloning failed - using current directory[/dim]")

    # Create session with JIRA metadata
    session = session_manager.create_session(
        name=session_name,
        goal=goal,
        working_directory=working_directory,
        project_path=project_path,
        branch=None,  # No branch for ticket creation sessions
    )

    # Set session_type to "ticket_creation"
    # This is important because daf open needs to know this is an analysis-only session
    session.session_type = "ticket_creation"

    # Set JIRA metadata
    session.issue_key = issue_key
    if not session.issue_metadata:
        session.issue_metadata = {}
    session.issue_metadata["summary"] = ticket.get('summary')
    session.issue_metadata["type"] = ticket.get('type')
    session.issue_metadata["status"] = ticket.get('status')

    # Add conversation metadata
    # Don't generate UUID here - let open_command.py handle it when it detects first launch
    # This prevents the issue where we generate a UUID but have no conversation file yet,
    # which causes open_command.py to generate a SECOND UUID and overwrite the first one
    from devflow.git.utils import GitUtils

    current_branch = GitUtils.get_current_branch(Path(project_path)) if GitUtils.is_git_repository(Path(project_path)) else None

    # Always add conversation so open_session() has working directory info
    # Use empty string for ai_agent_session_id - open_command.py will generate UUID on first launch
    # temp_directory and original_project_path will be None if user declined cloning
    # AAP-64347: Set branch=None for ticket_creation sessions (skip branch creation entirely)
    session.add_conversation(
        working_dir=working_directory,
        ai_agent_session_id="",  # Empty string signals first launch to open_command.py
        project_path=project_path,
        branch=None,  # AAP-64347: No branch for ticket_creation sessions
        temp_directory=temp_directory,  # None if user declined
        original_project_path=original_project_path,  # None if user declined
        workspace=config.repos.get_default_workspace_path(),
    )

    session_manager.update_session(session)

    console_print(f"[green]✓[/green] Session created: [cyan]{session_name}[/cyan]")
    console_print(f"[dim]Goal: {goal}[/dim]")
    if temp_directory:
        console_print(f"[dim]Using temporary directory for clean analysis[/dim]")
    console_print()

    # 4. Open the newly created session
    from devflow.cli.commands.open_command import open_session
    open_session(session_name, skip_jira_transition=True)
