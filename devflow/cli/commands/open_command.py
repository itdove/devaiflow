"""Implementation of 'daf open' command."""

import logging
import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm

from devflow.cli.commands.new_command import _generate_initial_prompt
from devflow.cli.utils import check_concurrent_session, get_session_with_prompt, get_status_display, require_outside_claude, should_launch_claude_code
from devflow.config.loader import ConfigLoader
from devflow.git.utils import GitUtils
from devflow.jira import transition_on_start
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError
from devflow.session.capture import SessionCapture
from devflow.session.manager import SessionManager
from devflow.session.summary import generate_session_summary

console = Console()

# Global variables for signal handler cleanup
_cleanup_session = None
_cleanup_session_manager = None
_cleanup_identifier = None
_cleanup_config = None
_cleanup_done = False


def _set_terminal_title(session) -> None:
    """Set terminal window/tab title using ANSI escape sequences.

    Args:
        session: Session object with name, issue_key, and session_id attributes

    The ANSI escape sequence \033]0;TITLE\007 sets the terminal title.
    This works across most modern terminal emulators (xterm, iTerm2, Terminal.app, etc.).
    """
    # Build title from session metadata
    if session.issue_key:
        # Format: "PROJ-12345: session-name (#42)"
        title = f"{session.issue_key}: {session.name}"
    else:
        # Format: "session-name (#42)"
        title = f"{session.name}"

    # Write ANSI escape sequence to set terminal title
    # \033 = ESC, ]0; = set window title, \007 = BEL
    sys.stdout.write(f"\033]0;{title}\007")
    sys.stdout.flush()


def _cleanup_on_signal(signum, frame):
    """Handle signals by performing cleanup before exit."""
    global _cleanup_done

    console.print(f"\n[yellow]Received signal {signum}, cleaning up...[/yellow]")

    if _cleanup_session and _cleanup_session_manager and _cleanup_identifier:
        try:
            console.print(f"[green]✓[/green] Claude session completed")

            # Update session status to paused
            # CRITICAL: Explicitly set status before calling update_session
            _cleanup_session.status = "paused"

            # Log the update for debugging
            _log_error(f"Signal handler: Updating session {_cleanup_session.name} to paused status")

            # Update session (this now includes explicit fsync to prevent data loss)
            _cleanup_session_manager.update_session(_cleanup_session)

            # Verify the update was persisted (for debugging intermittent issues)
            _log_error(f"Signal handler: Session update completed for {_cleanup_session.name}")

            _cleanup_session_manager.end_work_session(_cleanup_identifier)
            console.print(f"[dim]Resume anytime with: daf open {_cleanup_session.name}[/dim]")

            # Save conversation file to stable location before cleaning up temp directory
            if _cleanup_session.active_conversation and _cleanup_session.active_conversation.temp_directory:
                _copy_conversation_from_temp(_cleanup_session, _cleanup_session.active_conversation.temp_directory)

            # Clean up temporary directory if present (for ticket_creation sessions)
            if _cleanup_session.active_conversation and _cleanup_session.active_conversation.temp_directory:
                _cleanup_temp_directory_on_exit(_cleanup_session.active_conversation.temp_directory)

            # Call the complete prompt
            _prompt_for_complete_on_exit(_cleanup_session, _cleanup_config)

            # Mark cleanup as done so finally block doesn't repeat it
            _cleanup_done = True
        except Exception as e:
            console.print(f"[red]Error during cleanup: {e}[/red]")
            import traceback
            error_details = traceback.format_exc()
            console.print(f"[dim]{error_details}[/dim]")
            _log_error(f"Signal handler error: {e}\n{error_details}")

    # Exit gracefully
    sys.exit(0)


@require_outside_claude
def open_session(
    identifier: str,
    output_json: bool = False,
    skip_jira_transition: bool = False,
    path: Optional[str] = None,
    workspace: Optional[str] = None,
    new_conversation: bool = False,
    conversation_id: Optional[str] = None,
) -> None:
    """Open/resume an existing session.

    Args:
        identifier: Session group name or issue tracker key
        output_json: If True, output results in JSON format
        skip_jira_transition: If True, skip JIRA status transition (used by daf jira open)
        path: Optional project path to auto-select conversation in multi-conversation sessions
        workspace: Optional workspace name to override session's stored workspace (AAP-63377)
        new_conversation: If True, create a new conversation (archive current and start fresh) - PROJ-63490
        conversation_id: Optional Claude session UUID to resume specific archived conversation - PROJ-63490
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    # Get session using common utility (handles multi-session selection)
    session = get_session_with_prompt(session_manager, identifier, error_if_not_found=False)

    # If the found session is a ticket_creation session and the user searched by issue key
    # (not by full session name), treat it as not found.
    # This prevents `daf open PROJ-12345` from matching `creation-PROJ-12345`
    # But allows `daf open creation-PROJ-12345` or `daf open test-session-name`
    ticket_creation_session = None
    if session and session.session_type == "ticket_creation":
        # Check if identifier is a issue key that matched this session
        # (identifier != session.name means it was found by issue key, not by exact name)
        if identifier != session.name and not identifier.startswith("creation-"):
            console.print(f"[yellow]No development session found for '{identifier}'[/yellow]")
            console.print(f"[dim]Found ticket creation session '{session.name}' (for analysis only)[/dim]")
            console.print(f"[dim]To create a development session, use: [cyan]daf sync[/cyan][/dim]")
            console.print(f"[dim]To open the creation session: daf open {session.name}[/dim]")
            ticket_creation_session = session  # Save reference
            session = None  # Treat as not found

    if not session:
        # Check if identifier matches issue key pattern
        from devflow.jira.utils import is_issue_key_pattern, validate_jira_ticket

        if is_issue_key_pattern(identifier):
            # If we found a ticket_creation session, don't try to create a new one
            if ticket_creation_session:
                # Session creation analysis already exists - user should use daf sync
                # Error message already printed above in ticket_creation_session check
                sys.exit(1)

            console.print(f"[dim]Identifier looks like issue key, checking if ticket exists...[/dim]")

            # Try to validate the ticket
            from devflow.jira import JiraClient
            try:
                jira_client = JiraClient()
                ticket = validate_jira_ticket(identifier, client=jira_client)

                if ticket:
                    # Valid ticket - delegate to daf jira open
                    console.print(f"[green]✓[/green] issue tracker ticket validated, creating session...")
                    console.print()

                    from devflow.cli.commands.jira_open_command import jira_open_session
                    jira_open_session(identifier)
                    return
                else:
                    # Invalid ticket or error - message already displayed by validate_jira_ticket
                    sys.exit(1)
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Could not validate issue tracker ticket: {e}")
                console.print(f"[red]No sessions found for '{identifier}'[/red]")
                console.print(
                    f"[dim]Use 'daf new --name {identifier} --goal \"...\"' to create a session[/dim]"
                )
                sys.exit(1)
        else:
            # Not a issue key pattern - show standard error
            console.print(f"[red]No sessions found for '{identifier}'[/red]")
            console.print(
                f"[dim]Use 'daf new --name {identifier} --goal \"...\"' to create a session[/dim]"
            )
            sys.exit(1)

    # AAP-63377: Workspace selection
    # Select workspace using priority resolution (--workspace flag > session.workspace_name > default > prompt)
    from devflow.cli.utils import select_workspace, get_workspace_path
    selected_workspace_name = select_workspace(
        config,
        workspace_flag=workspace,
        session=session,
        skip_prompt=output_json
    )

    # Get workspace path (will be None if using old single workspace config)
    workspace_path = None
    if selected_workspace_name:
        workspace_path = get_workspace_path(config, selected_workspace_name)

    # Handle --conversation-id flag
    # This allows resuming a specific archived conversation
    if conversation_id:
        console.print(f"[cyan]Resuming conversation: {conversation_id}[/cyan]")
        if session.reactivate_conversation(conversation_id):
            console.print(f"[green]✓[/green] Reactivated conversation")
            session_manager.update_session(session)
        else:
            console.print(f"[red]✗[/red] Conversation {conversation_id} not found in this session")
            console.print(f"[dim]Use 'daf info {session.name}' to see all conversations[/dim]")
            return

    # Handle --new-conversation flag
    # This creates a new conversation and archives the current active one
    if new_conversation:
        # Get the active conversation to copy its settings
        active_conv = session.active_conversation
        if not active_conv:
            console.print(f"[red]✗[/red] No active conversation found to create a new one from")
            console.print(f"[dim]This flag requires an existing conversation in the session[/dim]")
            return

        # Get the working directory and project path
        working_dir = session.working_directory
        if not working_dir:
            console.print(f"[red]✗[/red] No working directory set")
            return

        # AAP-63377: Use selected workspace path
        # Create new conversation (this archives the current one)
        console.print(f"[yellow]Archiving current conversation ({active_conv.message_count} messages)[/yellow]")
        new_conv = session.create_new_conversation(
            working_dir=working_dir,
            project_path=active_conv.project_path,
            branch=active_conv.branch,
            base_branch=active_conv.base_branch,
            remote_url=active_conv.remote_url,
            workspace=workspace_path,
        )

        console.print(f"[green]✓[/green] Created new conversation with fresh Claude session")
        console.print(f"[dim]New session ID: {new_conv.ai_agent_session_id}[/dim]")

        # Save session
        session_manager.update_session(session)

    # Multi-conversation selection 
    # If --path parameter is provided, auto-detect the conversation based on path
    # Otherwise prompt user to select which conversation to open
    if path:
        # User provided --path parameter - auto-detect conversation
        detected_repo_name = _detect_working_directory_from_path(Path(path), config_loader)

        if not detected_repo_name:
            console.print(f"[red]✗[/red] Could not detect repository from path: {path}")
            console.print(f"[yellow]Please specify a valid repository path or name[/yellow]")
            return

        # Check if conversation exists for this detected repository
        existing_conversation = session.get_conversation(detected_repo_name)

        if existing_conversation:
            # Conversation exists for specified path - switch to it
            console.print(f"[dim]Detected working directory from --path: {detected_repo_name}[/dim]")
            session.working_directory = detected_repo_name
            session_manager.update_session(session)
        elif len(session.conversations) > 0:
            # Conversation does NOT exist for this path, but other conversations exist
            # Create new conversation for this path
            console.print(f"[yellow]⚠ No conversation found for repository: {detected_repo_name}[/yellow]")
            console.print(f"[cyan]Creating new conversation for: {detected_repo_name}[/cyan]")

            if not _create_conversation_for_path(session, detected_repo_name, Path(path), session_manager, config_loader):
                # User cancelled or failed to create conversation
                return
        # else: No conversations exist yet - will be handled by _prompt_for_working_directory below
    elif len(session.conversations) > 1:
        # No --path parameter and multiple conversations exist - prompt user to select
        if not _handle_conversation_selection_without_detection(session, session_manager, config_loader):
            # User cancelled or failed to select/create conversation
            return
    else:
        # Single conversation or no conversations yet
        # Auto-detect working directory from current directory
        current_dir = Path.cwd()
        detected_repo_name = _detect_working_directory_from_cwd(current_dir, config_loader)

        if detected_repo_name:
            # Check if conversation exists for this detected repository
            existing_conversation = session.get_conversation(detected_repo_name)

            if existing_conversation:
                # Conversation exists for current directory - switch to it
                console.print(f"[dim]Detected working directory: {detected_repo_name}[/dim]")
                session.working_directory = detected_repo_name
                session_manager.update_session(session)
            elif session.conversations:
                # Conversation does NOT exist for current directory, but other conversations exist
                # Prompt user to create new conversation or select existing one
                if not _handle_conversation_selection(session, detected_repo_name, current_dir, session_manager, config_loader):
                    # User cancelled or failed to select/create conversation
                    return
            # else: No conversations exist yet - will be handled by _prompt_for_working_directory below
        else:
            # Not in a detected repository - if conversations exist and no working_directory
            # is set, prompt to select one or create a new one
            if session.conversations and len(session.conversations) > 0 and not session.working_directory:
                if not _handle_conversation_selection_without_detection(session, session_manager, config_loader):
                    # User cancelled or failed to select/create conversation
                    return

    # Check if this is a first-time launch
    # This happens when:
    # 1. Sessions created via 'daf sync' (no ai_agent_session_id)
    # 2. Session has a ai_agent_session_id but conversation file doesn't exist
    # Use conversation-based API
    active_conv = session.active_conversation
    is_first_launch = not (active_conv and active_conv.ai_agent_session_id)

    if active_conv and active_conv.ai_agent_session_id and active_conv.project_path:
        # For ticket_creation sessions, check conversation file at stable location
        # Stable location uses original_project_path for sessions with temp_directory
        capture = SessionCapture()

        # Determine the correct location to check for conversation file
        if session.session_type == "ticket_creation" and active_conv and active_conv.original_project_path:
            # Use stable location based on original_project_path
            # This ensures we find the conversation even if temp directory was deleted
            session_dir = capture.get_session_dir(active_conv.original_project_path)
            console.print(f"[dim]Checking for conversation file at stable location (ticket_creation session)...[/dim]")
        else:
            # Use current project path for normal sessions
            session_dir = capture.get_session_dir(active_conv.project_path)
            console.print(f"[dim]Checking for conversation file...[/dim]")

        conversation_file = session_dir / f"{active_conv.ai_agent_session_id}.jsonl"
        conversation_exists = conversation_file.exists() and conversation_file.stat().st_size > 0
        console.print(f"[dim]  {'found' if conversation_exists else 'not found'}[/dim]")

        if not conversation_exists:
            if session.session_type == "ticket_creation":
                # For ticket_creation sessions, no conversation at stable location means first launch
                # Don't generate new session ID yet - will check again after temp directory handling
                console.print(f"[dim]No conversation at stable location - will verify after temp directory handling[/dim]")
            else:
                # Normal sessions: missing conversation file means we need a new session ID
                if conversation_file.exists():
                    console.print(f"\n[yellow]⚠ Conversation file is empty or invalid[/yellow]")
                else:
                    console.print(f"\n[yellow]⚠ Conversation file not found for session {active_conv.ai_agent_session_id}[/yellow]")
                console.print(f"[dim]This can happen if the session was interrupted or Claude Code failed to start.[/dim]")
                console.print(f"[dim]Will create a new conversation with a new session ID.[/dim]")
                is_first_launch = True

    if is_first_launch:
        console.print(f"\n[cyan]First-time launch for session: {session.name}[/cyan]")
        if not (active_conv and active_conv.ai_agent_session_id):
            console.print(f"[dim]This session was synced from JIRA but hasn't been opened yet.[/dim]")

        # Generate a new Claude session ID for the active conversation
        import uuid
        new_session_id = str(uuid.uuid4())

        # Update the active conversation with the new session ID
        if session.active_conversation:
            session.active_conversation.ai_agent_session_id = new_session_id
        else:
            # No active conversation exists - this shouldn't happen but handle gracefully
            # The conversation will be created by _prompt_for_working_directory below
            pass

        session_manager.update_session(session)
        console.print(f"[dim]Generated new session ID: {new_session_id}[/dim]")

    # Handle missing project_path (can happen with synced sessions)
    # Check conversation-based API for project_path
    if not (active_conv and active_conv.project_path):
        console.print(f"\n[yellow]⚠ Session is missing working directory information[/yellow]")
        console.print(f"[dim]This can happen when sessions are created via 'daf sync'[/dim]")

        if not _prompt_for_working_directory(session, config_loader, session_manager):
            # User cancelled or failed to set working directory
            # Error message already printed in _prompt_for_working_directory
            return
        # Refresh active_conv after working directory was set
        active_conv = session.active_conversation

    # Handle temporary directory for ticket_creation sessions
    if session.session_type == "ticket_creation":
        _handle_temp_directory_for_ticket_creation(session, session_manager)
        # Refresh active_conv after temp directory handling
        active_conv = session.active_conversation

        # After temp directory handling, verify if conversation file was restored
        # If not, we need to treat this as a first launch
        if not is_first_launch and active_conv and active_conv.ai_agent_session_id and active_conv.project_path:
            capture = SessionCapture()
            session_dir = capture.get_session_dir(active_conv.project_path)
            conversation_file = session_dir / f"{active_conv.ai_agent_session_id}.jsonl"

            conversation_exists = conversation_file.exists() and conversation_file.stat().st_size > 0

            if not conversation_exists:
                # Conversation file was not restored - this means user quit the session early
                # before any conversation was created. Generate a new session ID.
                console.print(f"\n[yellow]⚠ Conversation file was not restored (session was quit before any work was done)[/yellow]")
                console.print(f"[dim]Generating new session ID for fresh start[/dim]")
                is_first_launch = True

                # Generate new session ID
                import uuid
                new_session_id = str(uuid.uuid4())

                if session.active_conversation:
                    session.active_conversation.ai_agent_session_id = new_session_id

                session_manager.update_session(session)
                console.print(f"[dim]Generated new session ID: {new_session_id}[/dim]")

    # Check for concurrent active sessions in the same project BEFORE any git operations
    # This prevents branch switching before warning user about concurrent sessions
    # AAP-63377: Pass workspace_name to enable workspace-aware concurrent session checking
    if active_conv and active_conv.project_path:
        if not check_concurrent_session(session_manager, active_conv.project_path, session.name, selected_workspace_name, action="open"):
            return

    # Handle missing branch (can happen with synced sessions on first launch)
    # Skip branch creation for ticket_creation sessions (analysis-only) - PROJ-62990
    # Check session type BEFORE is_first_launch to prevent prompt for ticket_creation sessions
    if session.session_type == "ticket_creation":
        # Always skip branch creation for ticket_creation sessions regardless of is_first_launch
        if is_first_launch and active_conv and not active_conv.branch and active_conv.project_path:
            console.print(f"[dim]Skipping branch creation (session_type: {session.session_type})[/dim]")
    elif is_first_launch and active_conv and not active_conv.branch and active_conv.project_path:
        # Import here to avoid circular dependency
        from devflow.cli.commands.new_command import _handle_branch_creation

        # Use issue_key if available, otherwise use session name for branch creation
        branch_identifier = session.issue_key if session.issue_key else session.name
        # Prompt user for branch creation strategy (same as daf new)
        branch = _handle_branch_creation(
            active_conv.project_path,
            branch_identifier,
            session.goal
        )

        if branch:
            # Update active conversation's branch
            if session.active_conversation:
                session.active_conversation.branch = branch
            session_manager.update_session(session)

    # Display session summary (use conversation-based API)
    issue_display = f" ({session.issue_key})" if session.issue_key else ""
    action = "Opening" if is_first_launch else "Reopening"
    console.print(f"\n[bold]📋 {action}: {session.name}{issue_display}[/bold]")
    console.print(f"📁 Working Directory: {session.working_directory}")
    if active_conv and active_conv.project_path:
        console.print(f"📂 Path: {active_conv.project_path}")
    if active_conv and active_conv.branch:
        console.print(f"🌿 Branch: {active_conv.branch}")
    status_text, status_color = get_status_display(session.status)
    console.print(f"📊 Status: [{status_color}]{status_text}[/{status_color}]")
    if not is_first_launch:
        message_count = active_conv.message_count if active_conv else 0
        console.print(f"💬 Messages: {message_count}")
    console.print(f"📅 Last active: {session.last_active.strftime('%Y-%m-%d %H:%M')}")
    if active_conv and active_conv.ai_agent_session_id:
        console.print(f"🆔 Claude Session ID: {active_conv.ai_agent_session_id}")

    # Generate and display session summary
    _display_session_summary(session)

    # Show recent notes
    session_dir = config_loader.get_session_dir(session.name)
    notes_file = session_dir / "notes.md"
    if notes_file.exists():
        console.print("\n[bold]Recent notes:[/bold]")
        with open(notes_file, "r") as f:
            lines = f.readlines()
            # Show last 10 lines
            console.print("".join(lines[-10:]))

    # Load config for prompt settings
    config = config_loader.load_config()

    # Handle git branch sync and checkout if needed
    # Skip for ticket_creation sessions - they use placeholder branches and don't need git operations
    if active_conv and active_conv.project_path and active_conv.branch and session.session_type != "ticket_creation":
        # Sync branch for imported sessions FIRST (fetch from remote if needed)
        # This helps with team handoff when importing an exported session
        # Supports fork workflows by passing remote_url if available
        # Running this before _handle_branch_checkout ensures branch is fetched from remote
        # before we prompt to create it locally
        remote_url = active_conv.remote_url if active_conv else None
        _sync_branch_for_import(active_conv.project_path, active_conv.branch, remote_url)

        # Now handle branch checkout (will find branch if synced above)
        _handle_branch_checkout(active_conv.project_path, active_conv.branch, config)

        # Check if branch is behind base branch and offer to sync
        base_branch = active_conv.base_branch if active_conv and active_conv.base_branch else "main"
        sync_successful = _check_and_sync_with_base_branch(
            active_conv.project_path,
            active_conv.branch,
            base_branch,
            identifier,
            config
        )

        # Stop execution if sync failed (merge/rebase conflicts)
        if not sync_successful:
            _log_error("Branch sync failed - cannot continue until conflicts are resolved")
            return

        # Check for unresolved merge conflicts before continuing
        if GitUtils.has_merge_conflicts(Path(active_conv.project_path)):
            _log_error("Merge conflicts detected before launching Claude Code")
            _display_conflict_resolution_help(active_conv.project_path, session.name)
            return

    # JIRA auto-transition: New/To Do → In Progress
    # Skip for ticket_creation sessions (analysis-only, no status changes)
    # Skip if skip_jira_transition flag is set (e.g., from daf jira open command)
    if skip_jira_transition:
        console.print(f"[dim]Skipping JIRA status transition (opened via daf jira open)[/dim]")
    elif config and session.issue_key and session.session_type != "ticket_creation":
        # Fetch current JIRA status before attempting transition
        from devflow.jira import JiraClient
        jira_client = JiraClient()
        try:
            ticket_data = jira_client.get_ticket(session.issue_key)
            if not session.issue_metadata:
                session.issue_metadata = {}
            session.issue_metadata["status"] = ticket_data.get("status")
            console.print(f"[dim]Current JIRA status: {session.issue_metadata.get('status')}[/dim]")
        except JiraNotFoundError as e:
            console.print(f"[yellow]⚠[/yellow] issue tracker ticket not found: {e}")
        except (JiraAuthError, JiraApiError, JiraConnectionError) as e:
            console.print(f"[dim]Could not fetch JIRA status: {e}[/dim]")

        # Check if ticket is in a closed/done state and handle reopening
        current_status = session.issue_metadata.get("status") if session.issue_metadata else None
        if current_status and _is_closed_status(current_status):
            if not _handle_closed_ticket_reopen(session, jira_client):
                # User declined to reopen or reopen failed
                return

        # Attempt JIRA transition and stop if it fails
        if not transition_on_start(session, config):
            console.print(f"\n[red]Cannot continue without successful JIRA transition[/red]")
            console.print(f"[yellow]Please update the required fields in JIRA and try again[/yellow]")
            return

        # Save updated session (JIRA status may have changed)
        session_manager.update_session(session)
    elif session.session_type == "ticket_creation":
        console.print(f"[dim]Skipping JIRA status transition (session_type: ticket_creation)[/dim]")

    # Check if we should launch Claude Code (after all prerequisites)
    if not should_launch_claude_code(config=config, mock_mode=True):
        return

    # Display launch/resume message
    if is_first_launch:
        console.print(f"\n[cyan]Launching Claude Code for the first time...[/cyan]")
    else:
        console.print(f"\n[cyan]Resuming Claude Code session...[/cyan]")

    # Update session status and start work session
    session.status = "in_progress"
    session_manager.start_work_session(identifier)

    # Display context banner
    jira_url = config.jira.url if config and config.jira else None
    _display_resume_banner(session, jira_url)

    # Set up signal handlers for cleanup
    global _cleanup_session, _cleanup_session_manager, _cleanup_identifier, _cleanup_config
    _cleanup_session = session
    _cleanup_session_manager = session_manager
    _cleanup_identifier = identifier
    _cleanup_config = config

    # Register signal handlers for graceful shutdown
    # SIGTERM is not available on Windows, use SIGBREAK instead
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _cleanup_on_signal)
    else:
        signal.signal(signal.SIGBREAK, _cleanup_on_signal)
    signal.signal(signal.SIGINT, _cleanup_on_signal)

    # Declare global variable for cleanup tracking
    global _cleanup_done

    # Validate that DAF_AGENTS.md exists before launching Claude
    if active_conv and not _validate_context_files(active_conv.project_path, config_loader):
        return

    try:
        # Set environment variables for the AI agent process
        # DEVAIFLOW_IN_SESSION: Flag to indicate we're inside an AI session (used by safety guards)
        # AI_AGENT_SESSION_ID: Generic session ID (works with any AI agent)
        env = os.environ.copy()
        env["DEVAIFLOW_IN_SESSION"] = "1"
        if active_conv and active_conv.ai_agent_session_id:
            env["AI_AGENT_SESSION_ID"] = active_conv.ai_agent_session_id

        # Set GCP Vertex AI region if configured
        if config and config.gcp_vertex_region:
            env["CLOUD_ML_REGION"] = config.gcp_vertex_region

        if is_first_launch:
            # First launch: use --session-id with initial prompt
            # Check if this session has multiple conversations (multi-project work)
            current_project = session.working_directory
            other_projects = None
            if len(session.conversations) > 1:
                # Build list of other project names (excluding current)
                other_projects = [
                    working_dir for working_dir in session.conversations.keys()
                    if working_dir != current_project
                ]

            workspace = config.repos.get_default_workspace_path() if config and config.repos else None
            initial_prompt = _generate_initial_prompt(
                name=session.name,
                goal=session.goal,
                issue_key=session.issue_key,
                issue_title=session.issue_metadata.get("summary") if session.issue_metadata else None,
                session_type=session.session_type,
                current_project=current_project,
                other_projects=other_projects,
                project_path=active_conv.project_path if active_conv else None,
                workspace=workspace,
            )

            # Build command: prompt must come BEFORE --add-dir flags (positional argument)
            cmd = ["claude", "--session-id", active_conv.ai_agent_session_id, initial_prompt]

            # Add all skills directories to allowed paths (auto-approve skill file reads)
            # Skills can be in 3 locations: user-level, workspace-level, project-level
            skills_dirs = []

            # 1. User-level skills: ~/.claude/skills/
            user_skills = Path.home() / ".claude" / "skills"
            if user_skills.exists():
                skills_dirs.append(str(user_skills))

            # 2. Workspace-level skills: <workspace>/.claude/skills/
            if config and config.repos and config.repos.get_default_workspace_path():
                from devflow.utils.claude_commands import get_workspace_skills_dir
                workspace_skills = get_workspace_skills_dir(config.repos.get_default_workspace_path())
                if workspace_skills.exists():
                    skills_dirs.append(str(workspace_skills))

            # 3. Project-level skills: <project>/.claude/skills/
            if active_conv:
                project_skills = Path(active_conv.project_path) / ".claude" / "skills"
                if project_skills.exists():
                    skills_dirs.append(str(project_skills))

            # Add all discovered skills directories AFTER the prompt
            for skills_dir in skills_dirs:
                cmd.extend(["--add-dir", skills_dir])

            # Set terminal window/tab title before launching Claude Code
            _set_terminal_title(session)

            try:
                if active_conv:
                    subprocess.run(cmd, cwd=active_conv.project_path, env=env)
            finally:
                if not _cleanup_done:
                    console.print(f"\n[green]✓[/green] Claude session completed")

                    # Update session status to paused
                    session.status = "paused"
                    session_manager.update_session(session)

                    # Auto-pause: End work session when Claude Code closes
                    session_manager.end_work_session(identifier)

                    console.print(f"[dim]Resume anytime with: daf open {session.name}[/dim]")

                    # Save conversation file to stable location before cleaning up temp directory
                    if session.active_conversation and session.active_conversation.temp_directory:
                        _copy_conversation_from_temp(session, session.active_conversation.temp_directory)

                    # Clean up temporary directory if present (for ticket_creation sessions)
                    if session.active_conversation and session.active_conversation.temp_directory:
                        _cleanup_temp_directory_on_exit(session.active_conversation.temp_directory)

                    # Check if we should run 'daf complete' on exit
                    _prompt_for_complete_on_exit(session, config)
        else:
            # Resume existing session
            # On resume, we only need --add-dir flags for auto-approval
            # The initial prompt and skills are already in the conversation context
            cmd = ["claude", "--resume", active_conv.ai_agent_session_id]

            # Add all skills directories to allowed paths (auto-approve skill file reads)
            # Skills can be in 3 locations: user-level, workspace-level, project-level
            skills_dirs = []

            # 1. User-level skills: ~/.claude/skills/
            user_skills = Path.home() / ".claude" / "skills"
            if user_skills.exists():
                skills_dirs.append(str(user_skills))

            # 2. Workspace-level skills: <workspace>/.claude/skills/
            if config and config.repos and config.repos.get_default_workspace_path():
                from devflow.utils.claude_commands import get_workspace_skills_dir
                workspace_skills = get_workspace_skills_dir(config.repos.get_default_workspace_path())
                if workspace_skills.exists():
                    skills_dirs.append(str(workspace_skills))

            # 3. Project-level skills: <project>/.claude/skills/
            if active_conv:
                project_skills = Path(active_conv.project_path) / ".claude" / "skills"
                if project_skills.exists():
                    skills_dirs.append(str(project_skills))

            # Add all discovered skills directories
            for skills_dir in skills_dirs:
                cmd.extend(["--add-dir", skills_dir])

            # Set terminal window/tab title before launching Claude Code
            _set_terminal_title(session)

            try:
                if active_conv:
                    subprocess.run(
                        cmd,
                        cwd=active_conv.project_path,
                        env=env,
                    )
            finally:
                if not _cleanup_done:
                    console.print(f"\n[green]✓[/green] Claude session completed")

                    # Update session status to paused
                    session.status = "paused"
                    session_manager.update_session(session)

                    # Auto-pause: End work session when Claude Code closes
                    session_manager.end_work_session(identifier)

                    console.print(f"[dim]Resume anytime with: daf open {session.name}[/dim]")

                    # Save conversation file to stable location before cleaning up temp directory
                    if session.active_conversation and session.active_conversation.temp_directory:
                        _copy_conversation_from_temp(session, session.active_conversation.temp_directory)

                    # Clean up temporary directory if present (for ticket_creation sessions)
                    if session.active_conversation and session.active_conversation.temp_directory:
                        _cleanup_temp_directory_on_exit(session.active_conversation.temp_directory)

                    # Check if we should run 'daf complete' on exit
                    _prompt_for_complete_on_exit(session, config)

    except Exception as e:
        console.print(f"\n[red]Error launching Claude Code:[/red] {e}")

        # Update session status to paused on error
        session.status = "paused"
        session_manager.update_session(session)

        # Auto-pause: End work session even if Claude launch failed
        try:
            session_manager.end_work_session(identifier)
        except Exception:
            # Silently ignore if work session wasn't started
            pass

        if active_conv and active_conv.ai_agent_session_id:
            console.print(f"\n[yellow]You can manually resume with:[/yellow]")
            console.print(f"  cd {active_conv.project_path}")
            console.print(f"  claude --resume {active_conv.ai_agent_session_id}")


def _display_session_summary(session) -> None:
    """Display session summary from conversation parsing.

    Args:
        session: Session object
    """
    try:
        summary = generate_session_summary(session)

        # Only display if we have some summary data
        if (summary.files_created or summary.files_modified or
            summary.commands_run or summary.last_assistant_message):

            console.print("\n[bold]━━━ Session Summary ━━━[/bold]\n")

            # Files modified
            total_files = len(summary.files_created) + len(summary.files_modified)
            if total_files > 0:
                console.print(f"[bold]Files Modified ({total_files}):[/bold]")
                for file in summary.files_created[:5]:  # Limit to 5
                    console.print(f"  ✏️  {file} [dim](created)[/dim]")
                for file in summary.files_modified[:5]:  # Limit to 5
                    console.print(f"  ✏️  {file} [dim](edited)[/dim]")
                if total_files > 10:
                    console.print(f"  [dim]... and {total_files - 10} more[/dim]")
                console.print()

            # Commands run
            if summary.commands_run:
                console.print(f"[bold]Commands Run ({len(summary.commands_run)}):[/bold]")
                for cmd in summary.commands_run[:5]:  # Limit to 5
                    # Truncate long commands
                    command_text = cmd.command
                    if len(command_text) > 60:
                        command_text = command_text[:57] + "..."
                    console.print(f"  $ {command_text}")
                if len(summary.commands_run) > 5:
                    console.print(f"  [dim]... and {len(summary.commands_run) - 5} more[/dim]")
                console.print()

            # Last activity
            if summary.last_assistant_message:
                # Truncate to reasonable length
                message = summary.last_assistant_message
                if len(message) > 300:
                    message = message[:297] + "..."

                console.print("[bold]Last Activity:[/bold]")
                console.print(f"  \"{message}\"")
                console.print()

            console.print("[bold]━━━━━━━━━━━━━━━━━━━━[/bold]")

    except Exception as e:
        # If summary generation fails, don't block the open command
        # Just silently skip the summary
        pass


def _sync_branch_for_import(project_path: str, branch_name: str, remote_url: Optional[str] = None) -> bool:
    """Sync branch after import for team handoff (with fork support).

    Fetches branch from remote if missing, or merges if behind.
    Supports cross-fork collaboration by handling remote URLs.

    Args:
        project_path: Project directory path
        branch_name: Branch name to sync
        remote_url: Optional git remote URL where branch was pushed (for fork support)

    Returns:
        True if branch was synced successfully, False otherwise
    """
    from rich.prompt import Prompt

    path = Path(project_path)

    # Check if this is a git repository
    if not GitUtils.is_git_repository(path):
        return True  # Not a git repo, nothing to sync

    console.print(f"\n[cyan]Syncing branch for imported session...[/cyan]")

    # Handle fork support: add remote if needed
    # Convention: 'origin' is your primary remote (your fork or main repo)
    remote_name = "origin"

    # Check if 'origin' remote exists, prompt if not
    local_origin_url = GitUtils.get_remote_url(path, "origin")
    if not local_origin_url:
        # No 'origin' remote found - ask user which remote to use
        remotes = GitUtils.get_remote_names(path)
        if remotes:
            console.print("\n[yellow]No 'origin' remote found[/yellow]")
            console.print("[dim]Available remotes:[/dim]")
            for remote in remotes:
                url = GitUtils.get_remote_url(path, remote)
                console.print(f"  - {remote}: {url}")
            console.print("\n[cyan]Which remote should be used as your primary remote?[/cyan]")
            console.print("[dim]Common convention: 'origin' points to your fork or main repository[/dim]")
            remote_name = Prompt.ask("Primary remote name", choices=remotes, default=remotes[0])
            local_origin_url = GitUtils.get_remote_url(path, remote_name)
        else:
            console.print("[yellow]⚠[/yellow] No git remotes configured")
            remote_name = "origin"  # Use default, will likely fail but handled below

    if remote_url and local_origin_url:
        # Check if this remote URL is different from our primary remote
        if GitUtils._normalize_git_url(local_origin_url) != GitUtils._normalize_git_url(remote_url):
            # Different fork - check if we already have this remote
            existing_remote = GitUtils.get_remote_name_for_url(path, remote_url)
            if existing_remote:
                console.print(f"[dim]Using existing remote '{existing_remote}' for fork: {remote_url}[/dim]")
                remote_name = existing_remote
            else:
                # Need to add a new remote for this fork
                # Extract username/org from URL for remote name
                import re
                match = re.search(r'[:/]([^/]+)/[^/]+(?:\.git)?$', remote_url)
                suggested_remote_name = match.group(1) if match else "teammate"

                console.print(f"\n[yellow]⚠[/yellow] This branch is from a different fork: {remote_url}")
                console.print(f"[dim]Your origin: {local_origin_url}[/dim]")

                if Confirm.ask(f"Add remote '{suggested_remote_name}' for this fork?", default=True):
                    remote_name = Prompt.ask("Remote name", default=suggested_remote_name)
                    if GitUtils.add_remote(path, remote_name, remote_url):
                        console.print(f"[green]✓[/green] Added remote '{remote_name}': {remote_url}")
                    else:
                        console.print(f"[red]✗[/red] Failed to add remote")
                        console.print(f"[yellow]Falling back to 'origin' - branch may not exist there[/yellow]")
                        remote_name = "origin"
                else:
                    console.print(f"[yellow]Skipping remote add - will try to fetch from 'origin'[/yellow]")
                    remote_name = "origin"

    # Fetch latest from remote
    console.print(f"[dim]Fetching latest from {remote_name}...[/dim]")
    result = subprocess.run(
        ["git", "fetch", remote_name],
        cwd=path,
        capture_output=True,
        timeout=30,
    )
    if result.returncode != 0:
        console.print(f"[yellow]⚠[/yellow] Could not fetch from {remote_name}")
        console.print(f"[yellow]Continuing anyway - branch may be out of sync[/yellow]")
        return True

    # Check if branch exists locally
    branch_exists_locally = GitUtils.branch_exists(path, branch_name)

    # Check if branch exists on remote (use the correct remote name)
    branch_exists_remotely = subprocess.run(
        ["git", "ls-remote", "--heads", remote_name, branch_name],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=10,
    ).returncode == 0 and bool(subprocess.run(
        ["git", "ls-remote", "--heads", remote_name, branch_name],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip())

    if not branch_exists_locally and not branch_exists_remotely:
        # Branch doesn't exist anywhere - this is unexpected but not critical
        console.print(f"[yellow]⚠[/yellow] Branch '{branch_name}' does not exist locally or on {remote_name}")
        console.print(f"[dim]This can happen if the branch was deleted or the export was from a different repo[/dim]")
        return True

    if not branch_exists_locally and branch_exists_remotely:
        # Branch only exists on remote - fetch and checkout
        console.print(f"[yellow]Branch '{branch_name}' does not exist locally[/yellow]")
        if Confirm.ask(f"Fetch branch '{branch_name}' from {remote_name}?", default=True):
            console.print(f"[dim]Fetching {branch_name} from {remote_name}...[/dim]")
            # Use custom fetch+checkout since we need to specify remote name
            fetch_result = subprocess.run(
                ["git", "fetch", remote_name, branch_name],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if fetch_result.returncode == 0:
                checkout_result = subprocess.run(
                    ["git", "checkout", "-b", branch_name, f"{remote_name}/{branch_name}"],
                    cwd=path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if checkout_result.returncode == 0:
                    console.print(f"[green]✓[/green] Fetched and checked out branch: {branch_name}")
                    return True

            console.print(f"[red]✗[/red] Failed to fetch branch from {remote_name}")
            console.print(f"[yellow]You'll need to create the branch manually[/yellow]")
            return False
        else:
            console.print(f"[dim]Skipping branch fetch - you'll need to create it manually[/dim]")
            return False

    # Branch exists locally - check if it's behind remote
    if branch_exists_remotely:
        # Use git rev-list to count commits behind
        result = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..{remote_name}/{branch_name}"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        commits_behind = 0
        if result.returncode == 0:
            count_str = result.stdout.strip()
            commits_behind = int(count_str) if count_str.isdigit() else 0

        if commits_behind > 0:
            console.print(f"\n[yellow]⚠[/yellow] Local branch '{branch_name}' is {commits_behind} commits behind {remote_name}")
            if Confirm.ask(f"Merge {remote_name} changes into local branch?", default=True):
                # Checkout the branch first
                current_branch = GitUtils.get_current_branch(path)
                if current_branch != branch_name:
                    if not GitUtils.checkout_branch(path, branch_name):
                        console.print(f"[red]✗[/red] Failed to checkout branch")
                        return False

                # Merge remote changes
                console.print(f"[dim]Merging {remote_name}/{branch_name} into {branch_name}...[/dim]")
                if GitUtils.merge_branch(path, f"{remote_name}/{branch_name}"):
                    console.print(f"[green]✓[/green] Successfully merged remote changes")
                    return True
                else:
                    console.print(f"[red]✗[/red] Merge conflicts detected")
                    console.print(f"[yellow]Please resolve conflicts manually:[/yellow]")
                    console.print(f"  1. Resolve conflicts in your editor")
                    console.print(f"  2. Run: git add <resolved-files>")
                    console.print(f"  3. Run: git commit")
                    console.print(f"\n[dim]Continuing with session open - conflicts need to be resolved[/dim]")
                    return False
            else:
                console.print(f"[dim]Skipping merge - branch may be out of sync[/dim]")
        else:
            console.print(f"[dim]Branch '{branch_name}' is up-to-date with {remote_name}[/dim]")

    return True


def _handle_branch_checkout(project_path: str, branch_name: str, config: Optional[any] = None) -> None:
    """Handle git branch checkout.

    Args:
        project_path: Project directory path
        branch_name: Branch name to checkout
        config: Configuration object (optional)
    """
    path = Path(project_path)

    # Check if this is a git repository
    if not GitUtils.is_git_repository(path):
        console.print(f"[yellow]Warning: Not a git repository, cannot checkout branch {branch_name}[/yellow]")
        return

    # Get current branch
    current_branch = GitUtils.get_current_branch(path)
    if current_branch == branch_name:
        console.print(f"[dim]Already on branch: {branch_name}[/dim]")
        return

    # Check if branch exists
    if not GitUtils.branch_exists(path, branch_name):
        console.print(f"[yellow]Branch '{branch_name}' does not exist[/yellow]")
        if Confirm.ask("Create it now?", default=True):
            if GitUtils.create_branch(path, branch_name):
                console.print(f"[green]✓[/green] Created and switched to branch: {branch_name}")
            else:
                console.print(f"[red]✗[/red] Failed to create branch")
        return

    # Branch exists, ask to switch (or use configured default)
    should_checkout = True
    if config and config.prompts and config.prompts.auto_checkout_branch is not None:
        should_checkout = config.prompts.auto_checkout_branch
        if should_checkout:
            console.print(f"[dim]Automatically checking out branch (configured in prompts)[/dim]")
    else:
        should_checkout = Confirm.ask(f"Switch to branch '{branch_name}'?", default=True)

    if should_checkout:
        if GitUtils.checkout_branch(path, branch_name):
            console.print(f"[green]✓[/green] Switched to branch: {branch_name}")
        else:
            console.print(f"[red]✗[/red] Failed to switch branch")


def _detect_working_directory_from_path(path: Path, config_loader) -> Optional[str]:
    """Detect the working directory name from a given path.

    This function handles both absolute paths and repository names from workspace.
    It resolves the path and determines the repository name.

    Args:
        path: Path to resolve (can be absolute path or repo name)
        config_loader: ConfigLoader instance

    Returns:
        Repository name (directory name) if detected, None otherwise
    """
    # Convert string to Path if needed
    if isinstance(path, str):
        path = Path(path)

    # Case 1: Absolute path provided
    if path.is_absolute():
        # Check if it's a git repository
        if not GitUtils.is_git_repository(path):
            console.print(f"[yellow]⚠[/yellow] Path is not a git repository: {path}")
            return None

        # Get configuration to check if we're in the workspace
        try:
            config = config_loader.load_config()
        except Exception:
            # If config loading fails, use directory name
            return path.name

        if config and config.repos:
            workspace_path = config.repos.get_default_workspace_path()

            if not workspace_path:

                console.print("[yellow]⚠[/yellow] No default workspace configured")

                return None

            workspace = Path(workspace_path).expanduser().absolute()

            # Check if path is within the workspace
            try:
                relative = path.relative_to(workspace)
                # Get the first component of the relative path (the repository name)
                repo_name = relative.parts[0] if relative.parts else path.name
                return repo_name
            except ValueError:
                # Path is not within workspace, use directory name
                return path.name
        else:
            # No workspace configured - use directory name
            return path.name

    # Case 2: Relative path or repository name
    else:
        # Try to interpret as repository name within workspace
        try:
            config = config_loader.load_config()
            if config and config.repos:
                workspace_path = config.repos.get_default_workspace_path()

                if not workspace_path:

                    console.print("[yellow]⚠[/yellow] No default workspace configured")

                    return None

                workspace = Path(workspace_path).expanduser()
                repo_path = workspace / str(path)

                # Check if this repository exists in workspace
                if repo_path.exists() and repo_path.is_dir():
                    # Use the repository name
                    return str(path)
                else:
                    # Try current directory + relative path
                    resolved_path = (Path.cwd() / path).resolve()
                    if resolved_path.exists() and GitUtils.is_git_repository(resolved_path):
                        return resolved_path.name

            # Fallback: try as relative to current directory
            resolved_path = (Path.cwd() / path).resolve()
            if resolved_path.exists() and GitUtils.is_git_repository(resolved_path):
                return resolved_path.name

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Error resolving path: {e}")

        return None


def _detect_working_directory_from_cwd(current_dir: Path, config_loader) -> Optional[str]:
    """Detect the working directory name from current working directory.

    This function checks if the current directory is:
    1. A git repository (indicating it's a project directory)
    2. Located within the configured workspace

    Args:
        current_dir: Current working directory path
        config_loader: ConfigLoader instance

    Returns:
        Repository name (directory name) if detected, None otherwise
    """
    # Check if current directory is a git repository
    if not GitUtils.is_git_repository(current_dir):
        # Silently return None - not a git repo, so can't auto-detect
        return None

    # Get configuration to check if we're in the workspace
    try:
        config = config_loader.load_config()
    except Exception:
        # If config loading fails, silently use directory name
        return current_dir.name

    if config and config.repos and config.repos.workspaces:
        # Check if current_dir is within ANY of the configured workspaces
        for workspace_def in config.repos.workspaces:
            workspace = Path(workspace_def.path).expanduser().absolute()

            # Check if current_dir is within the workspace or IS the workspace
            try:
                # This will raise ValueError if current_dir is not relative to workspace
                relative = current_dir.relative_to(workspace)
                # Get the first component of the relative path (the repository name)
                repo_name = relative.parts[0] if relative.parts else current_dir.name
                console.print(f"[dim]Detected repository in workspace '{workspace_def.name}': {repo_name}[/dim]")
                return repo_name
            except ValueError:
                # current_dir is not within this workspace, try next one
                continue

        # Not in any workspace, use directory name
        repo_name = current_dir.name
        console.print(f"[dim]Detected repository outside workspace: {repo_name}[/dim]")
        return repo_name
    else:
        # No workspace configured - use current directory name
        repo_name = current_dir.name
        console.print(f"[dim]Detected repository (no workspace configured): {repo_name}[/dim]")
        return repo_name


def _handle_conversation_selection_without_detection(
    session,
    session_manager,
    config_loader,
) -> bool:
    """Handle conversation selection when no repository is detected.

    Shows existing conversations with option to create a new one.
    This is called when user runs 'daf open' from a non-project directory.

    Args:
        session: Session object
        session_manager: SessionManager instance
        config_loader: ConfigLoader instance

    Returns:
        True if conversation was selected/created successfully, False if user cancelled
    """
    from rich.prompt import IntPrompt

    console.print(f"\n[bold]Found {len(session.conversations)} conversation(s) for {session.name}:[/bold]\n")

    # Show existing conversations
    for i, (working_dir, conversation) in enumerate(session.conversations.items(), 1):
        # Get active session
        active = conversation.active_session

        # Get workspace for path display
        config = config_loader.load_config()
        workspace = config.repos.get_default_workspace_path() if config and config.repos else None
        project_path = active.get_project_path(workspace)

        # Format last active time
        from datetime import datetime
        time_diff = datetime.now() - active.last_active
        hours_ago = int(time_diff.total_seconds() // 3600)
        if hours_ago > 24:
            days_ago = hours_ago // 24
            last_active = f"{days_ago}d ago"
        elif hours_ago > 0:
            last_active = f"{hours_ago}h ago"
        else:
            minutes_ago = int((time_diff.total_seconds() % 3600) // 60)
            last_active = f"{minutes_ago}m ago" if minutes_ago > 0 else "just now"

        console.print(f"  {i}. {working_dir}")
        console.print(f"     Path: {project_path}")
        if active.branch:
            console.print(f"     Branch: {active.branch}")
        console.print(f"     Last active: {last_active}")
        console.print()

    # Add "Create new conversation" option
    new_option_number = len(session.conversations) + 1
    console.print(f"  {new_option_number}. → Create new conversation (in a different project)")
    console.print()

    # Build choices list
    choices = [str(i) for i in range(1, new_option_number + 1)]

    choice = IntPrompt.ask(
        "Which conversation?",
        choices=choices,
        default="1"
    )

    # Check if user selected "Create new conversation"
    if choice == new_option_number:
        # Prompt for directory selection and create new conversation
        return _create_conversation_from_workspace_selection(session, session_manager, config_loader)

    # User selected an existing conversation by number
    if 1 <= choice < new_option_number:
        # Get the Nth conversation
        selected_working_dir = list(session.conversations.keys())[choice - 1]
        console.print(f"[dim]Selected conversation: {selected_working_dir}[/dim]")
        session.working_directory = selected_working_dir
        session_manager.update_session(session)
        return True

    console.print(f"[red]Invalid selection[/red]")
    return False


def _handle_conversation_selection(
    session,
    detected_repo_name: str,
    current_dir: Path,
    session_manager,
    config_loader,
) -> bool:
    """Handle conversation selection when opening a session in a new repository.

    This prompts the user to either:
    1. Create a new conversation for the detected repository
    2. Select an existing conversation from the session

    Args:
        session: Session object
        detected_repo_name: Detected repository name from current directory
        current_dir: Current working directory path
        session_manager: SessionManager instance
        config_loader: ConfigLoader instance

    Returns:
        True if conversation was selected/created successfully, False if user cancelled
    """
    from rich.prompt import Prompt

    console.print(f"\n[yellow]⚠ No conversation found for repository: {detected_repo_name}[/yellow]")
    console.print(f"[dim]This session has {len(session.conversations)} existing conversation(s)[/dim]")

    # Show existing conversations
    console.print(f"\n[bold]Existing conversations:[/bold]")
    for i, (working_dir, conversation) in enumerate(session.conversations.items(), 1):
        console.print(f"  {i}. {working_dir}")
        # Access active_session fields
        active = conversation.active_session
        console.print(f"     Path: {active.project_path}")
        if active.branch:
            console.print(f"     Branch: {active.branch}")

    # In mock mode, auto-select the first conversation if there's only one
    from devflow.utils import is_mock_mode
    mock_mode = is_mock_mode()
    if mock_mode and len(session.conversations) == 1:
        console.print(f"\n[dim]Mock mode: Auto-selecting the existing conversation[/dim]")
        choice = "1"
    else:
        console.print(f"\n[bold]Options:[/bold]")
        console.print(f"  [cyan]n[/cyan] - Create new conversation for '{detected_repo_name}'")
        console.print(f"  [cyan]1-{len(session.conversations)}[/cyan] - Select existing conversation")
        console.print(f"  [cyan]c[/cyan] - Cancel")

        choice = Prompt.ask("Selection", default="n")

    if choice.lower() == "c":
        console.print(f"\n[yellow]Cancelled[/yellow] - session not opened")
        return False

    if choice.lower() == "n":
        # Create new conversation for current repository
        return _create_conversation_for_current_directory(
            session, detected_repo_name, current_dir, session_manager, config_loader
        )

    # User selected an existing conversation by number
    try:
        selection_index = int(choice)
        if 1 <= selection_index <= len(session.conversations):
            # Get the Nth conversation
            selected_working_dir = list(session.conversations.keys())[selection_index - 1]
            console.print(f"[dim]Selected conversation: {selected_working_dir}[/dim]")
            session.working_directory = selected_working_dir
            session_manager.update_session(session)
            return True
        else:
            console.print(f"[red]Invalid selection. Please choose 1-{len(session.conversations)}[/red]")
            return False
    except ValueError:
        console.print(f"[red]Invalid selection. Please enter 'n', 'c', or a number[/red]")
        return False


def _create_conversation_from_workspace_selection(
    session,
    session_manager,
    config_loader,
) -> bool:
    """Create a new conversation by selecting a directory from workspace.

    Prompts user to select a project directory from workspace and creates
    a new conversation for that project.

    Args:
        session: Session object
        session_manager: SessionManager instance
        config_loader: ConfigLoader instance

    Returns:
        True if conversation was created successfully, False otherwise
    """
    from rich.prompt import IntPrompt, Prompt
    import uuid

    console.print(f"\n[bold]Create conversation in another directory:[/bold]\n")

    # Get workspace configuration
    config = config_loader.load_config()
    repo_options = []

    if config and config.repos:
        workspace_path = config.repos.get_default_workspace_path()

        if not workspace_path:

            console.print("[yellow]⚠[/yellow] No default workspace configured")

            return None

        workspace = Path(workspace_path).expanduser()

        if workspace.exists() and workspace.is_dir():
            # List all git repositories in workspace, excluding those already in conversations
            try:
                from devflow.git.utils import GitUtils
                directories = [d for d in workspace.iterdir() if d.is_dir() and not d.name.startswith('.')]
                # Filter to only include git repositories
                git_repos = [d.name for d in directories if GitUtils.is_git_repository(d)]
                existing_dirs = set(session.conversations.keys())

                # Filter out directories that already have conversations
                all_repos = sorted(git_repos)
                available_repos = [repo for repo in all_repos if repo not in existing_dirs]
                repo_options = available_repos

                if not available_repos:
                    console.print(f"[yellow]All projects in workspace already have conversations[/yellow]")
                    console.print(f"\n[bold]Existing conversations:[/bold]")
                    for existing_dir in sorted(existing_dirs):
                        console.print(f"  • {existing_dir}")
                    console.print(f"\n[dim]You can specify a different path using 'Other' option[/dim]")
                else:
                    console.print("[bold]Available projects (for new conversation):[/bold]")
                    option_number = 1
                    for repo_name in available_repos:
                        console.print(f"  {option_number}. {repo_name}")
                        option_number += 1

                    if existing_dirs:
                        console.print(f"\n[dim]Note: {len(existing_dirs)} project(s) already have conversations[/dim]")

                console.print(f"  {len(repo_options) + 1}. Other (specify path)")
                console.print()

            except Exception as e:
                console.print(f"[yellow]Warning: Could not scan workspace: {e}[/yellow]")
                return False
    else:
        console.print(f"[yellow]No workspace configured[/yellow]")
        console.print(f"[dim]Configure workspace with: daf config tui[/dim]")
        return False

    if not repo_options:
        console.print(f"[yellow]No directories found in workspace[/yellow]")
        return False

    # Prompt for selection
    choices = [str(i) for i in range(1, len(repo_options) + 2)]  # +2 for "Other" option
    choice = IntPrompt.ask("Which project?", choices=choices, default="1")

    # Handle "Other" option
    if choice == len(repo_options) + 1:
        path_input = Prompt.ask("Enter full path to project directory")
        if not path_input or not path_input.strip():
            console.print("[red]✗[/red] Project path cannot be empty")
            return False
        path_input = path_input.strip()
        project_path = Path(path_input).expanduser().absolute()
        repo_name = project_path.name
    else:
        # User selected from list
        repo_name = repo_options[choice - 1]
        project_path = workspace / repo_name

    # Verify path exists
    if not project_path.exists():
        console.print(f"[red]✗[/red] Path does not exist: {project_path}")
        return False

    console.print(f"\n[cyan]Creating conversation for: {repo_name}[/cyan]")

    # Check if conversation already exists for this directory
    if session.get_conversation(repo_name):
        console.print(f"\n[yellow]⚠[/yellow] Conversation already exists for '{repo_name}'")
        console.print(f"[dim]Switching to existing conversation instead[/dim]")
        session.working_directory = repo_name
        session_manager.update_session(session)
        return True

    # Generate a new Claude session ID for this conversation
    new_session_id = str(uuid.uuid4())

    # Get workspace for portable paths
    workspace_path = config.repos.get_default_workspace_path() if config and config.repos else None

    # Create the conversation
    try:
        session.add_conversation(
            working_dir=repo_name,
            ai_agent_session_id=new_session_id,
            project_path=str(project_path),
            branch="",  # Leave empty so branch creation logic can run
            workspace=workspace_path,
        )
    except ValueError as e:
        # This shouldn't happen due to check above, but handle gracefully
        console.print(f"[red]✗[/red] {e}")
        return False

    # Set this as the active conversation
    session.working_directory = repo_name

    # Save the session
    session_manager.update_session(session)

    console.print(f"[green]✓[/green] Created conversation for {repo_name}")
    console.print(f"[dim]Project path: {project_path}[/dim]")
    console.print(f"[dim]Claude session ID: {new_session_id}[/dim]")

    return True


def _create_conversation_for_path(
    session, repo_name: str, path: Path, session_manager, config_loader
) -> bool:
    """Create a new conversation for the specified path.

    Args:
        session: Session object
        repo_name: Repository name (working directory name)
        path: Path to the project directory
        session_manager: SessionManager instance
        config_loader: ConfigLoader instance

    Returns:
        True if conversation was created successfully, False otherwise
    """
    import uuid

    console.print(f"[cyan]Creating new conversation for: {repo_name}[/cyan]")

    # Check if conversation already exists for this directory
    if session.get_conversation(repo_name):
        console.print(f"\n[yellow]⚠[/yellow] Conversation already exists for '{repo_name}'")
        console.print(f"[dim]Switching to existing conversation instead[/dim]")
        session.working_directory = repo_name
        session_manager.update_session(session)
        return True

    # Resolve the path to get the absolute project path
    project_path = path.resolve()

    # Verify path exists
    if not project_path.exists():
        console.print(f"[red]✗[/red] Path does not exist: {project_path}")
        return False

    # Generate a new Claude session ID for this conversation
    new_session_id = str(uuid.uuid4())

    # Get workspace for portable paths
    config = config_loader.load_config()
    workspace = config.repos.get_default_workspace_path() if config and config.repos else None

    # Create the conversation
    try:
        session.add_conversation(
            working_dir=repo_name,
            ai_agent_session_id=new_session_id,
            project_path=str(project_path),
            branch="",  # Leave empty so branch creation logic can run
            workspace=workspace,
        )
    except ValueError as e:
        # This shouldn't happen due to check above, but handle gracefully
        console.print(f"[red]✗[/red] {e}")
        return False

    # Set this as the active conversation
    session.working_directory = repo_name

    # Save the session
    session_manager.update_session(session)

    console.print(f"[green]✓[/green] Created conversation for {repo_name}")
    console.print(f"[dim]Project path: {project_path}[/dim]")
    console.print(f"[dim]Claude session ID: {new_session_id}[/dim]")

    # Auto-create template if enabled
    from devflow.templates.manager import TemplateManager
    template_manager = TemplateManager()

    config = config_loader.load_config()
    if config and config.templates.auto_create:
        # Check if template already exists for this directory
        existing_template = template_manager.find_matching_template(project_path)

        if not existing_template:
            # Auto-create template
            template = template_manager.auto_create_template(
                project_path=project_path,
                description=f"Auto-created template for {repo_name}",
                default_jira_project=session.issue_key.split('-')[0] if session.issue_key and '-' in session.issue_key else None,
            )
            console.print(f"\n[cyan]✓ Auto-created template:[/cyan] [bold]{template.name}[/bold]")
            console.print(f"[dim]Template will be automatically used for future sessions in this directory[/dim]")

    return True


def _create_conversation_for_current_directory(
    session, repo_name: str, current_dir: Path, session_manager, config_loader
) -> bool:
    """Create a new conversation for the current directory.

    Args:
        session: Session object
        repo_name: Repository name (working directory name)
        current_dir: Current directory path
        session_manager: SessionManager instance
        config_loader: ConfigLoader instance

    Returns:
        True if conversation was created successfully, False otherwise
    """
    import uuid

    console.print(f"\n[cyan]Creating new conversation for: {repo_name}[/cyan]")

    # Check if conversation already exists for this directory
    if session.get_conversation(repo_name):
        console.print(f"\n[yellow]⚠[/yellow] Conversation already exists for '{repo_name}'")
        console.print(f"[dim]Switching to existing conversation instead[/dim]")
        session.working_directory = repo_name
        session_manager.update_session(session)
        return True

    # Use current_dir as project_path
    project_path = str(current_dir.absolute())

    # Generate a new Claude session ID for this conversation
    new_session_id = str(uuid.uuid4())

    # Get workspace for portable paths
    config = config_loader.load_config()
    workspace = config.repos.get_default_workspace_path() if config and config.repos else None

    # Create the conversation
    try:
        session.add_conversation(
            working_dir=repo_name,
            ai_agent_session_id=new_session_id,
            project_path=project_path,
            branch="",  # Leave empty so branch creation logic can run
            workspace=workspace,
        )
    except ValueError as e:
        # This shouldn't happen due to check above, but handle gracefully
        console.print(f"[red]✗[/red] {e}")
        return False

    # Set this as the active conversation
    session.working_directory = repo_name

    # Save the session
    session_manager.update_session(session)

    console.print(f"[green]✓[/green] Created conversation for {repo_name}")
    console.print(f"[dim]Project path: {project_path}[/dim]")
    console.print(f"[dim]Claude session ID: {new_session_id}[/dim]")

    # Auto-create template if enabled
    from devflow.templates.manager import TemplateManager
    template_manager = TemplateManager()

    config = config_loader.load_config()
    if config and config.templates.auto_create:
        # Check if template already exists for this directory
        existing_template = template_manager.find_matching_template(current_dir)

        if not existing_template:
            # Auto-create template
            template = template_manager.auto_create_template(
                project_path=current_dir,
                description=f"Auto-created template for {repo_name}",
                default_jira_project=session.issue_key.split('-')[0] if session.issue_key and '-' in session.issue_key else None,
            )
            console.print(f"\n[cyan]✓ Auto-created template:[/cyan] [bold]{template.name}[/bold]")
            console.print(f"[dim]Template will be automatically used for future sessions in this directory[/dim]")

    return True


def _prompt_for_working_directory(session, config_loader, session_manager) -> bool:
    """Prompt user to select a working directory for a session.

    This is used when opening sessions that were created via 'daf sync' without
    specifying a working directory.

    Args:
        session: Session object to update
        config_loader: ConfigLoader instance
        session_manager: SessionManager instance

    Returns:
        True if working directory was set successfully, False if user cancelled
    """
    from rich.prompt import Prompt

    console.print(f"\n[bold]Select working directory for session:[/bold] {session.name}")
    if session.issue_key:
        console.print(f"[dim]JIRA: {session.issue_key}[/dim]")
    if session.goal:
        console.print(f"[dim]Goal: {session.goal}[/dim]")

    # Try to detect available repositories from config
    config = config_loader.load_config()
    repo_options = []

    if config and config.repos:
        workspace_path = config.repos.get_default_workspace_path()
        if workspace_path:
            workspace = Path(workspace_path).expanduser()
            console.print(f"\n[cyan]Scanning workspace:[/cyan] {workspace}")

            if workspace.exists() and workspace.is_dir():
                # List all git repositories in workspace
                try:
                    from devflow.git.utils import GitUtils
                    directories = [d for d in workspace.iterdir() if d.is_dir() and not d.name.startswith('.')]
                    # Filter to only include git repositories
                    git_repos = [d.name for d in directories if GitUtils.is_git_repository(d)]
                    repo_options = sorted(git_repos)

                    if repo_options:
                        console.print(f"\n[bold]Available repositories ({len(repo_options)}):[/bold]")
                        for i, repo in enumerate(repo_options, 1):  # Show all repositories
                            console.print(f"  {i}. {repo}")
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not scan workspace: {e}[/yellow]")

    # Prompt for working directory
    console.print(f"\n[bold]Select working directory:[/bold]")
    if repo_options:
        console.print(f"  • Enter a number (1-{len(repo_options)}) to select from the list above")
        console.print(f"  • Enter a repository name")
        console.print(f"  • Enter an absolute path (starting with / or ~)")
        console.print(f"  • Enter 'cancel' to exit")
    else:
        console.print(f"  • Enter a repository name from workspace")
        console.print(f"  • Enter an absolute path (starting with / or ~)")
        console.print(f"  • Enter 'cancel' to exit")

    selection = Prompt.ask("Selection")

    # Validate input is not empty
    if not selection or selection.strip() == "":
        if repo_options:
            console.print(f"[red]✗[/red] Empty selection not allowed. Please enter a number (1-{len(repo_options)}), repository name, path, or 'cancel'")
        else:
            console.print(f"[red]✗[/red] Empty selection not allowed. Please enter a repository name, path, or 'cancel'")
        return False

    # Handle cancel
    if selection.lower() == "cancel":
        console.print(f"\n[yellow]Cancelled[/yellow] - session not opened")
        return False

    # Check if it's a number (selecting from list)
    if selection.isdigit() and repo_options:
        repo_index = int(selection) - 1
        if 0 <= repo_index < len(repo_options):
            repo_name = repo_options[repo_index]
            console.print(f"[dim]Selected: {repo_name}[/dim]")

            if config and config.repos:
                workspace_path = config.repos.get_default_workspace_path()

                if not workspace_path:

                    console.print("[yellow]⚠[/yellow] No default workspace configured")

                    return None

                workspace = Path(workspace_path).expanduser()
                project_path = workspace / repo_name
            else:
                console.print(f"[red]✗[/red] No workspace configured in config")
                return False
        else:
            console.print(f"[red]✗[/red] Invalid selection. Please choose 1-{len(repo_options)}")
            return False
    # Check if it's an absolute path
    elif selection.startswith("/") or selection.startswith("~"):
        project_path = Path(selection).expanduser().absolute()

        if not project_path.exists():
            console.print(f"[yellow]⚠[/yellow] Path does not exist: {project_path}")
            if not Confirm.ask("Use this path anyway?", default=False):
                console.print(f"\n[yellow]Cancelled[/yellow] - session not opened")
                return False
    # Otherwise treat as repository name
    else:
        repo_name = selection

        if config and config.repos:
            workspace_path = config.repos.get_default_workspace_path()

            if not workspace_path:

                console.print("[yellow]⚠[/yellow] No default workspace configured")

                return None

            workspace = Path(workspace_path).expanduser()
            project_path = workspace / repo_name

            if not project_path.exists():
                console.print(f"[yellow]⚠[/yellow] Repository not found: {project_path}")
                if not Confirm.ask("Use this path anyway?", default=False):
                    console.print(f"\n[yellow]Cancelled[/yellow] - session not opened")
                    return False
        else:
            console.print(f"[red]✗[/red] No workspace configured in config")
            return False

    # Update session with selected directory
    # For multi-conversation sessions, update or create active conversation
    if session.active_conversation:
        session.active_conversation.project_path = str(project_path)
    else:
        # Create initial conversation
        import uuid

        # Get workspace for portable paths
        config = config_loader.load_config()
        workspace = config.repos.get_default_workspace_path() if config and config.repos else None

        session.add_conversation(
            working_dir=project_path.name,
            ai_agent_session_id=str(uuid.uuid4()),
            project_path=str(project_path),
            branch="",  # Leave empty so branch creation logic can run
            workspace=workspace,
        )
    session.working_directory = project_path.name

    # Auto-create template if enabled and this is the first time using this directory
    from devflow.templates.manager import TemplateManager
    template_manager = TemplateManager()

    if config and config.templates.auto_create:
        # Check if template already exists for this directory
        existing_template = template_manager.find_matching_template(project_path)

        if not existing_template:
            # Auto-create template
            template = template_manager.auto_create_template(
                project_path=project_path,
                description=f"Auto-created template for {project_path.name}",
                default_jira_project=session.issue_key.split('-')[0] if session.issue_key and '-' in session.issue_key else None,
            )
            console.print(f"\n[cyan]✓ Auto-created template:[/cyan] [bold]{template.name}[/bold]")
            console.print(f"[dim]Template will be automatically used for future sessions in this directory[/dim]")

    # Save updated session
    session_manager.update_session(session)

    console.print(f"\n[green]✓[/green] Working directory set to: {project_path}")
    return True


def _check_and_sync_with_base_branch(project_path: str, branch: str, base_branch: str, identifier: str, config: Optional[any] = None) -> bool:
    """Check if branch is behind base branch and prompt to sync.

    Args:
        project_path: Project directory path
        branch: Current branch name
        base_branch: Base branch to check against (e.g., 'main')
        identifier: Session identifier (session name or JIRA key) for resume command
        config: Configuration object (optional)

    Returns:
        True if sync was successful or not needed, False if sync failed
    """
    from rich.prompt import Prompt

    path = Path(project_path)

    # Check if this is a git repository
    if not GitUtils.is_git_repository(path):
        return True

    # Fetch latest from remote to get up-to-date comparison
    console.print(f"[dim]Fetching latest changes from remote...[/dim]")
    if not GitUtils.fetch_origin(path):
        console.print(f"[yellow]Warning: Could not fetch from remote - skipping branch sync check[/yellow]")
        return True

    # Check how many commits behind
    commits_behind = GitUtils.commits_behind(path, branch, base_branch)

    if commits_behind == 0:
        console.print(f"[dim]Branch '{branch}' is up-to-date with '{base_branch}'[/dim]")
        return True

    # Branch is behind - check configured behavior
    console.print(f"\n[yellow]⚠ Your branch '{branch}' is {commits_behind} commits behind '{base_branch}'[/yellow]")

    should_sync = True
    if config and config.prompts and config.prompts.auto_sync_with_base:
        auto_sync_setting = config.prompts.auto_sync_with_base
        if auto_sync_setting == "always":
            console.print(f"[dim]Automatically syncing (configured in prompts)[/dim]")
            should_sync = True
        elif auto_sync_setting == "never":
            console.print(f"[dim]Skipping sync (configured in prompts)[/dim]")
            console.print(f"[dim]Continuing with current branch state[/dim]")
            return True
        else:  # "prompt" or anything else
            should_sync = Confirm.ask(f"Update your branch with latest changes from {base_branch}?", default=True)
    else:
        should_sync = Confirm.ask(f"Update your branch with latest changes from {base_branch}?", default=True)

    if not should_sync:
        console.print(f"[dim]Continuing with current branch state[/dim]")
        return True

    # Prompt for sync strategy
    console.print(f"\n[bold]Sync strategy:[/bold]")
    console.print("  [cyan]m[/cyan] - Merge (preserves commit history)")
    console.print("  [cyan]r[/cyan] - Rebase (linear history)")

    strategy = Prompt.ask("Choose strategy", choices=["m", "r"], default="m")

    if strategy == "m":
        console.print(f"\n[cyan]Merging {base_branch} into {branch}...[/cyan]")
        success = GitUtils.merge_branch(path, f"origin/{base_branch}")
        if success:
            console.print(f"[green]✓[/green] Successfully merged {base_branch} into {branch}")
            return True
        else:
            console.print(f"[red]✗[/red] Merge conflicts detected")
            console.print(f"\n[yellow]Cannot continue - please resolve conflicts first:[/yellow]")
            console.print(f"  1. Resolve conflicts in your editor")
            console.print(f"  2. Run: git add <resolved-files>")
            console.print(f"  3. Run: git commit")
            console.print(f"  4. Run: daf open {identifier} (to resume session after resolving conflicts)")
            return False
    else:
        console.print(f"\n[cyan]Rebasing {branch} onto {base_branch}...[/cyan]")
        success = GitUtils.rebase_branch(path, f"origin/{base_branch}")
        if success:
            console.print(f"[green]✓[/green] Successfully rebased {branch} onto {base_branch}")
            return True
        else:
            console.print(f"[red]✗[/red] Rebase conflicts detected")
            console.print(f"\n[yellow]Cannot continue - please resolve conflicts first:[/yellow]")
            console.print(f"  1. Resolve conflicts in your editor")
            console.print(f"  2. Run: git add <resolved-files>")
            console.print(f"  3. Run: git rebase --continue")
            console.print(f"  4. Run: daf open {identifier} (to resume session after resolving conflicts)")
            return False


def _display_resume_banner(session, jira_url: Optional[str] = None) -> None:
    """Display session resume banner.

    Args:
        session: Session object
    """
    console.print("\n" + "━" * 60)

    # Build session title
    if session.issue_key:
        title = f"{session.name} ({session.issue_key})"
        issue_summary = session.issue_metadata.get("summary") if session.issue_metadata else None
        if issue_summary:
            title = f"{session.issue_key}: {issue_summary}"
    else:
        title = session.name

    console.print(f"📋 Session: {title}")
    if session.goal:
        console.print(f"🎯 Goal: {session.goal}")
    console.print(f"📁 Working Directory: {session.working_directory}")
    active_conv = session.active_conversation
    if active_conv and active_conv.project_path:
        console.print(f"📂 Path: {active_conv.project_path}")
    if active_conv and active_conv.branch:
        console.print(f"🌿 Branch: {active_conv.branch}")
    if session.issue_key and jira_url:
        console.print(f"🔗 JIRA: {jira_url}/browse/{session.issue_key}")

    # Show time tracking
    if session.work_sessions:
        total_seconds = 0
        for ws in session.work_sessions:
            if ws.end:
                delta = ws.end - ws.start
                total_seconds += delta.total_seconds()

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        console.print(f"⏱️  Time: {hours}h {minutes}m (resumed)")

    console.print("━" * 60 + "\n")


def _is_closed_status(status: str) -> bool:
    """Check if a JIRA status indicates a closed/done ticket.

    Args:
        status: issue tracker ticket status

    Returns:
        True if status indicates ticket is closed, False otherwise
    """
    # Common closed/done statuses in JIRA workflows
    closed_statuses = [
        "Done",
        "Closed",
        "Resolved",
        "Complete",
        "Release Pending",
        "Review",  # Tickets in Review might also need to be reopened if changes are needed
    ]
    return status in closed_statuses


def _handle_closed_ticket_reopen(session, jira_client) -> bool:
    """Handle reopening of a closed issue tracker ticket.

    Prompts the user to confirm transition back to In Progress and adds a comment.
    In mock mode, automatically transitions without prompting.

    Args:
        session: Session object with issue key
        jira_client: JiraClient instance

    Returns:
        True if ticket was successfully reopened or user wants to continue anyway,
        False if user declined or reopen failed critically
    """
    # Check if we're in mock mode
    from devflow.utils import is_mock_mode
    mock_mode = is_mock_mode()

    current_status = session.issue_metadata.get("status") if session.issue_metadata else "Unknown"
    console.print(f"\n[yellow]⚠  issue tracker ticket {session.issue_key} is currently: {current_status}[/yellow]")
    console.print(f"[dim]You are reopening work on a ticket that was previously marked as complete.[/dim]")

    # In mock mode, automatically transition without prompting
    should_transition = True
    if not mock_mode:
        should_transition = Confirm.ask(f"\nTransition {session.issue_key} back to 'In Progress'?", default=True)

    if not should_transition:
        console.print("[dim]Skipping JIRA transition[/dim]")
        console.print(f"[yellow]Note: Ticket status will remain as {current_status}[/yellow]")

        # Ask if user wants to continue anyway (skip in mock mode)
        if mock_mode:
            return True
        if not Confirm.ask("Continue opening session without updating JIRA?", default=False):
            console.print("\n[yellow]Session open cancelled[/yellow]")
            return False
        return True

    # Attempt to transition ticket to In Progress
    try:
        jira_client.transition_ticket(session.issue_key, "In Progress")
        old_status = session.issue_metadata.get("status") if session.issue_metadata else "Unknown"
        if not session.issue_metadata:
            session.issue_metadata = {}
        session.issue_metadata["status"] = "In Progress"
        console.print(f"[green]✓[/green] Transitioned {session.issue_key}: {old_status} → In Progress")

        # Add comment explaining why ticket was reopened
        comment = f"Ticket reopened via daf open (Session: {session.name})\n\nResuming work on this ticket."
        try:
            jira_client.add_comment(session.issue_key, comment)
            console.print(f"[green]✓[/green] Added comment to {session.issue_key}")
        except (JiraValidationError, JiraApiError, JiraAuthError, JiraConnectionError) as e:
            console.print(f"[dim]Could not add comment to {session.issue_key}: {e}[/dim]")

        return True
    except JiraValidationError as e:
        console.print(f"[red]✗[/red] Failed to transition {session.issue_key} to In Progress")
        console.print(f"[yellow]The ticket may have required fields that need to be set in JIRA.[/yellow]")
        if e.field_errors:
            console.print("  [red]Field errors:[/red]")
            for field, msg in e.field_errors.items():
                console.print(f"    [red]• {field}: {msg}[/red]")
        if e.error_messages:
            for msg in e.error_messages:
                console.print(f"    [red]• {msg}[/red]")

        # Ask if user wants to continue anyway (auto-continue in mock mode)
        if mock_mode:
            console.print("[dim]Mock mode: Continuing without JIRA update[/dim]")
            return True
        if Confirm.ask("Continue opening session without updating JIRA?", default=False):
            return True

        console.print("\n[yellow]Session open cancelled[/yellow]")
        console.print(f"[dim]Please update required fields in JIRA and try again[/dim]")
        return False
    except (JiraNotFoundError, JiraAuthError, JiraApiError, JiraConnectionError) as e:
        console.print(f"[red]✗[/red] Failed to transition {session.issue_key} to In Progress: {e}")

        # Ask if user wants to continue anyway (auto-continue in mock mode)
        if mock_mode:
            console.print("[dim]Mock mode: Continuing without JIRA update[/dim]")
            return True
        if Confirm.ask("Continue opening session without updating JIRA?", default=False):
            return True

        console.print("\n[yellow]Session open cancelled[/yellow]")
        console.print(f"[dim]Please update required fields in JIRA and try again[/dim]")
        return False


def _prompt_for_complete_on_exit(session, config: Optional[any] = None) -> None:
    """Prompt user to run 'daf complete' when Claude Code session ends.

    This function checks the configuration setting and either:
    - Automatically runs 'daf complete' if auto_complete_on_exit is True
    - Skips running 'daf complete' if auto_complete_on_exit is False
    - Prompts the user if auto_complete_on_exit is None (default)

    Args:
        session: Session object
        config: Configuration object (optional)
    """
    # Check configuration setting
    should_complete = None
    if config and config.prompts and config.prompts.auto_complete_on_exit is not None:
        should_complete = config.prompts.auto_complete_on_exit
        if should_complete:
            console.print("\n[dim]Automatically running 'daf complete' (configured in prompts)[/dim]")
        else:
            console.print("\n[dim]Skipping 'daf complete' (configured in prompts)[/dim]")
            return
    else:
        # Prompt user
        console.print()
        should_complete = Confirm.ask("Run 'daf complete' now?", default=True)

    if not should_complete:
        console.print("[dim]You can complete this session later with: daf complete {session.name}[/dim]")
        return

    # Import complete_session to avoid circular import
    from devflow.cli.commands.complete_command import complete_session

    # Run daf complete for this session
    console.print()
    try:
        # Call complete_session directly with the session name
        # Use the session name as the identifier
        complete_session(identifier=session.name, status=None, attach_to_issue=False, latest=False)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to complete session: {e}")
        console.print(f"[dim]You can complete manually with: daf complete {session.name}[/dim]")


def _log_error(message: str) -> None:
    """Log error messages to the session manager log file.

    Args:
        message: Error message to log
    """
    try:
        from devflow.utils.paths import get_cs_home

        # Get log directory
        log_dir = get_cs_home() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create/append to open.log
        log_file = log_dir / "open.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        # Silently ignore logging errors to avoid breaking the main flow
        pass


def _cleanup_temp_directory_on_exit(temp_dir: Optional[str]) -> None:
    """Clean up a temporary directory when exiting a session.

    Args:
        temp_dir: Path to temporary directory (can be None)
    """
    import shutil

    if not temp_dir:
        return

    try:
        if Path(temp_dir).exists():
            console.print(f"[dim]Cleaning up temporary directory: {temp_dir}[/dim]")
            shutil.rmtree(temp_dir)
            console.print(f"[green]✓[/green] Temporary directory removed")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not remove temporary directory: {e}")
        console.print(f"[dim]You may need to manually delete: {temp_dir}[/dim]")


def _copy_conversation_to_temp(session, temp_dir: str) -> bool:
    """Copy conversation file from stable location to temp directory.

    For ticket_creation sessions, we store conversation files using the original_project_path
    as a stable identifier, then copy them to the temp directory before launching Claude.

    Args:
        session: Session object
        temp_dir: Temporary directory path

    Returns:
        True if conversation was copied, False otherwise
    """
    import shutil

    conv = session.active_conversation
    if not conv or not conv.ai_agent_session_id or not conv.original_project_path:
        console.print(f"[dim]Cannot copy conversation: missing required fields[/dim]")
        console.print(f"[dim]  ai_agent_session_id: {conv.ai_agent_session_id if conv else 'N/A'}[/dim]")
        console.print(f"[dim]  original_project_path: {conv.original_project_path if conv else 'N/A'}[/dim]")
        return False

    # Get conversation file from stable location (based on original_project_path)
    capture = SessionCapture()
    stable_session_dir = capture.get_session_dir(conv.original_project_path)
    stable_conversation_file = stable_session_dir / f"{conv.ai_agent_session_id}.jsonl"

    console.print(f"[dim]Looking for conversation at stable location:[/dim]")
    console.print(f"[dim]  {stable_conversation_file}[/dim]")

    if not stable_conversation_file.exists():
        console.print(f"[dim]Conversation file not found at stable location[/dim]")
        return False

    # Copy to temp directory location
    # IMPORTANT: Use the actual resolved path that Claude Code will see
    # This handles macOS /var -> /private/var canonicalization
    temp_path_resolved = str(Path(temp_dir).resolve())

    temp_session_dir = capture.get_session_dir(temp_path_resolved)
    temp_session_dir.mkdir(parents=True, exist_ok=True)
    temp_conversation_file = temp_session_dir / f"{conv.ai_agent_session_id}.jsonl"

    try:
        shutil.copy2(stable_conversation_file, temp_conversation_file)
        console.print(f"[dim]Copied conversation file to temp directory ({stable_conversation_file.stat().st_size} bytes)[/dim]")
        console.print(f"[dim]  Target: {temp_conversation_file}[/dim]")
        return True
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not copy conversation file: {e}")
        return False


def _copy_conversation_from_temp(session, temp_dir: str) -> bool:
    """Copy conversation file from temp directory back to stable location.

    After Claude exits, copy the conversation file from the temp directory
    back to the stable location (based on original_project_path).

    Args:
        session: Session object
        temp_dir: Temporary directory path

    Returns:
        True if conversation was copied, False otherwise
    """
    import shutil

    conv = session.active_conversation
    if not conv or not conv.ai_agent_session_id or not conv.original_project_path:
        console.print(f"[dim]Cannot save conversation: missing required fields[/dim]")
        console.print(f"[dim]  ai_agent_session_id: {conv.ai_agent_session_id if conv else 'N/A'}[/dim]")
        console.print(f"[dim]  original_project_path: {conv.original_project_path if conv else 'N/A'}[/dim]")
        return False

    # Get conversation file from temp directory
    # Use resolved path to handle macOS /var -> /private/var canonicalization
    # SessionCapture now correctly encodes underscores as dashes
    capture = SessionCapture()
    temp_path_resolved = str(Path(temp_dir).resolve())

    temp_session_dir = capture.get_session_dir(temp_path_resolved)
    temp_conversation_file = temp_session_dir / f"{conv.ai_agent_session_id}.jsonl"

    if not temp_conversation_file.exists():
        console.print(f"[dim]Conversation file not found in temp directory[/dim]")
        console.print(f"[dim]  Expected: {temp_conversation_file}[/dim]")
        return False

    # Copy to stable location (based on original_project_path)
    stable_session_dir = capture.get_session_dir(conv.original_project_path)
    stable_session_dir.mkdir(parents=True, exist_ok=True)
    stable_conversation_file = stable_session_dir / f"{conv.ai_agent_session_id}.jsonl"

    try:
        shutil.copy2(temp_conversation_file, stable_conversation_file)
        console.print(f"[dim]Saved conversation file to stable location ({temp_conversation_file.stat().st_size} bytes)[/dim]")
        return True
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not save conversation file: {e}")
        return False


def _handle_temp_directory_for_ticket_creation(session, session_manager) -> None:
    """Handle temporary directory management for ticket_creation sessions.

    This function:
    1. Checks if session has temp_directory metadata
    2. If yes, deletes old temp directory and re-clones to fresh location
    3. If no, prompts user to clone to temp directory
    4. Updates session with new temp directory path
    5. Copies conversation file from stable location to temp directory

    Args:
        session: Session object
        session_manager: SessionManager instance
    """
    import tempfile
    import shutil
    from rich.prompt import Confirm

    conv = session.active_conversation
    if not conv:
        return

    # Case 1: Session was previously created with temp_directory
    if conv.temp_directory:
        console.print(f"\n[cyan]This session was created with a temporary directory[/cyan]")
        console.print(f"[dim]Previous temp directory: {conv.temp_directory}[/dim]")

        # Preserve conversation file using stable storage location
        # Conversation files are stored at stable location based on original_project_path
        # This allows conversation to persist even when temp directory changes

        # Delete old temp directory if it exists
        if Path(conv.temp_directory).exists():
            console.print(f"[dim]Deleting old temporary directory...[/dim]")
            try:
                shutil.rmtree(conv.temp_directory)
                console.print(f"[green]✓[/green] Old temporary directory removed")
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Could not delete old temp directory: {e}")

        # Get remote URL from original project path
        original_path = Path(conv.original_project_path) if conv.original_project_path else Path.cwd()
        remote_url = GitUtils.get_remote_url(original_path)

        if not remote_url:
            console.print(f"[yellow]⚠[/yellow] Could not detect git remote URL from original path")
            console.print(f"[yellow]Falling back to existing project path[/yellow]")
            # Clear temp directory metadata
            conv.temp_directory = None
            conv.original_project_path = None
            session_manager.update_session(session)
            return

        # Re-clone to fresh temp directory
        console.print(f"[cyan]Re-cloning repository to get latest version from main branch...[/cyan]")
        console.print(f"[dim]Remote URL: {remote_url}[/dim]")

        try:
            new_temp_dir = tempfile.mkdtemp(prefix="daf-jira-analysis-")
            console.print(f"[dim]Created new temporary directory: {new_temp_dir}[/dim]")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to create temporary directory: {e}")
            console.print(f"[yellow]Falling back to existing project path[/yellow]")
            conv.temp_directory = None
            conv.original_project_path = None
            session_manager.update_session(session)
            return

        console.print(f"[dim]Cloning... (this may take a moment)[/dim]")
        if not GitUtils.clone_repository(remote_url, Path(new_temp_dir), branch=None):
            console.print(f"[red]✗[/red] Failed to clone repository")
            console.print(f"[yellow]Falling back to existing project path[/yellow]")
            try:
                shutil.rmtree(new_temp_dir)
            except:
                pass
            conv.temp_directory = None
            conv.original_project_path = None
            session_manager.update_session(session)
            return

        # Checkout default branch
        default_branch = GitUtils.get_default_branch(Path(new_temp_dir))
        if default_branch:
            console.print(f"[dim]Checked out default branch: {default_branch}[/dim]")
        else:
            # Try common default branches
            for branch in ["main", "master", "develop"]:
                if GitUtils.branch_exists(Path(new_temp_dir), branch):
                    if GitUtils.checkout_branch(Path(new_temp_dir), branch):
                        console.print(f"[dim]Checked out branch: {branch}[/dim]")
                        break

        # Update session with new temp directory
        # IMPORTANT: Store the resolved path (handles macOS /var -> /private/var)
        # This ensures the path matches what Claude Code will see
        resolved_temp_dir = str(Path(new_temp_dir).resolve())
        conv.temp_directory = resolved_temp_dir
        conv.project_path = resolved_temp_dir
        session_manager.update_session(session)
        console.print(f"[green]✓[/green] Using fresh clone in temporary directory")

        # Restore conversation file from stable location to new temp directory
        # This uses original_project_path as stable identifier
        if _copy_conversation_to_temp(session, new_temp_dir):
            console.print(f"[green]✓[/green] Restored conversation history from stable storage")
        else:
            console.print(f"[dim]No previous conversation to restore (this may be first launch)[/dim]")

    # Case 2: Session does NOT have temp_directory metadata - prompt user
    else:
        current_path = Path(conv.project_path) if conv.project_path else Path.cwd()

        # Only prompt if we're in a git repository
        if not GitUtils.is_git_repository(current_path):
            console.print(f"[dim]Not a git repository - skipping temp directory prompt[/dim]")
            return

        # Check if we should skip the prompt
        # Skip if: mock mode, JSON mode, OR this is a reopened session (already has ai_agent_session_id)
        from devflow.utils import is_mock_mode
        mock_mode = is_mock_mode()
        is_json = "--json" in sys.argv
        is_reopened_session = conv.ai_agent_session_id is not None

        # In non-interactive modes or when reopening an existing session, skip the prompt
        # Mock/JSON modes are for automated testing/scripting where no user interaction is expected
        # Reopened sessions already made the temp directory decision during initial creation
        if mock_mode or is_json or is_reopened_session:
            console.print("[dim]Non-interactive mode or reopened session: Using current directory (skipping temp directory prompt)[/dim]")
            return

        # Prompt user
        if not Confirm.ask(
            "Clone project in a temporary directory to ensure analysis is based on main branch?",
            default=True
        ):
            console.print("[dim]Using current directory[/dim]")
            return

        # Get remote URL
        console.print("[dim]Detecting git remote URL...[/dim]")
        remote_url = GitUtils.get_remote_url(current_path)
        if not remote_url:
            console.print("[yellow]⚠[/yellow] Could not detect git remote URL")
            console.print("[yellow]Falling back to current directory[/yellow]")
            return

        console.print(f"[dim]Remote URL: {remote_url}[/dim]")

        # Create temporary directory
        try:
            temp_dir = tempfile.mkdtemp(prefix="daf-jira-analysis-")
            console.print(f"[dim]Created temporary directory: {temp_dir}[/dim]")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to create temporary directory: {e}")
            console.print("[yellow]Falling back to current directory[/yellow]")
            return

        # Clone repository
        console.print(f"[cyan]Cloning repository...[/cyan]")
        console.print(f"[dim]This may take a moment...[/dim]")

        if not GitUtils.clone_repository(remote_url, Path(temp_dir), branch=None):
            console.print(f"[red]✗[/red] Failed to clone repository")
            console.print("[yellow]Falling back to current directory[/yellow]")
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
            return

        # Checkout default branch
        default_branch = GitUtils.get_default_branch(Path(temp_dir))
        if default_branch:
            console.print(f"[dim]Checked out default branch: {default_branch}[/dim]")
        else:
            # Try common default branches
            for branch in ["main", "master", "develop"]:
                if GitUtils.branch_exists(Path(temp_dir), branch):
                    if GitUtils.checkout_branch(Path(temp_dir), branch):
                        console.print(f"[dim]Checked out branch: {branch}[/dim]")
                        break

        # Update session with temp directory
        # IMPORTANT: Store the resolved path (handles macOS /var -> /private/var)
        # This ensures the path matches what Claude Code will see
        resolved_temp_dir = str(Path(temp_dir).resolve())
        conv.temp_directory = resolved_temp_dir
        conv.original_project_path = str(current_path.absolute())
        conv.project_path = resolved_temp_dir
        session_manager.update_session(session)
        console.print(f"[green]✓[/green] Using temporary clone: {temp_dir}")


def _install_bundled_cs_agents(destination: Path) -> tuple[bool, list[str]]:
    """Install bundled DAF_AGENTS.md to specified location.

    Tries multiple methods to find and copy the bundled DAF_AGENTS.md:
    1. importlib.resources (Python 3.9+)
    2. Relative path from package (development mode)

    Args:
        destination: Path where DAF_AGENTS.md should be installed

    Returns:
        Tuple of (success: bool, diagnostics: list of error messages)
    """
    import importlib.resources
    import shutil

    diagnostics = []

    # Method 1: Try importlib.resources (works for installed package)
    method1_path = None
    try:
        if hasattr(importlib.resources, 'files'):
            daf_agents_resource = importlib.resources.files('devflow').parent / 'DAF_AGENTS.md'
            method1_path = str(daf_agents_resource)
            if daf_agents_resource is not None:
                with daf_agents_resource.open('rb') as src:
                    destination.write_bytes(src.read())
                return True, []
    except ImportError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): ImportError - {str(e)}")
    except AttributeError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): AttributeError - {str(e)}")
    except TypeError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): TypeError - {str(e)}")
    except FileNotFoundError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): FileNotFoundError - DAF_AGENTS.md not found")
        if method1_path:
            diagnostics.append(f"    Searched path: {method1_path}")
    except Exception as e:
        diagnostics.append(f"  Method 1 (importlib.resources): {type(e).__name__} - {str(e)}")

    # Method 2: Try relative path from package (development mode)
    try:
        package_cs_agents = Path(__file__).parent.parent.parent.parent / "DAF_AGENTS.md"
        diagnostics.append(f"  Method 2 (relative path): Searched: {package_cs_agents}")
        if package_cs_agents.exists():
            shutil.copy2(package_cs_agents, destination)
            return True, []
        else:
            diagnostics.append(f"  Method 2 (relative path): File does not exist")
    except PermissionError as e:
        diagnostics.append(f"  Method 2 (relative path): PermissionError - {str(e)}")
    except Exception as e:
        diagnostics.append(f"  Method 2 (relative path): {type(e).__name__} - {str(e)}")

    return False, diagnostics


def _get_bundled_daf_agents_content() -> tuple[str | None, list[str]]:
    """Read the bundled DAF_AGENTS.md content.

    Returns:
        Tuple of (content: str or None, diagnostics: list of error messages)
    """
    import importlib.resources

    diagnostics = []

    # Method 1: Try importlib.resources (works for installed package)
    try:
        if hasattr(importlib.resources, 'files'):
            daf_agents_resource = importlib.resources.files('devflow').parent / 'DAF_AGENTS.md'
            if daf_agents_resource is not None:
                with daf_agents_resource.open('r', encoding='utf-8') as src:
                    return src.read(), []
    except ImportError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): ImportError - {str(e)}")
    except AttributeError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): AttributeError - {str(e)}")
    except TypeError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): TypeError - {str(e)}")
    except FileNotFoundError:
        diagnostics.append(f"  Method 1 (importlib.resources): FileNotFoundError - DAF_AGENTS.md not found")
    except Exception as e:
        diagnostics.append(f"  Method 1 (importlib.resources): {type(e).__name__} - {str(e)}")

    # Method 2: Try relative path from package (development mode)
    try:
        package_cs_agents = Path(__file__).parent.parent.parent.parent / "DAF_AGENTS.md"
        diagnostics.append(f"  Method 2 (relative path): Searched: {package_cs_agents}")
        if package_cs_agents.exists():
            return package_cs_agents.read_text(encoding='utf-8'), []
        else:
            diagnostics.append(f"  Method 2 (relative path): File does not exist")
    except Exception as e:
        diagnostics.append(f"  Method 2 (relative path): {type(e).__name__} - {str(e)}")

    return None, diagnostics


def _check_and_upgrade_daf_agents(installed_file: Path, location: str) -> bool:
    """Check if installed DAF_AGENTS.md is outdated and offer upgrade.

    Args:
        installed_file: Path to the installed DAF_AGENTS.md
        location: Human-readable location description (e.g., "repository", "workspace")

    Returns:
        True if file is up-to-date or successfully upgraded, False if user declined or upgrade failed
    """
    # Get bundled content for comparison
    bundled_content, diagnostics = _get_bundled_daf_agents_content()
    if bundled_content is None:
        # Can't check version if we can't read bundled file
        # Continue anyway - don't block session opening
        if diagnostics:
            console.print(f"[yellow]⚠ Could not check for DAF_AGENTS.md updates[/yellow]")
        return True

    # Read installed content
    try:
        installed_content = installed_file.read_text(encoding='utf-8')
    except Exception as e:
        console.print(f"[yellow]⚠ Could not read installed DAF_AGENTS.md: {e}[/yellow]")
        return True

    # Compare contents
    if bundled_content == installed_content:
        # Up to date
        return True

    # File is outdated - prompt for upgrade
    console.print(f"\n[yellow]⚠ DAF_AGENTS.md has been updated[/yellow]")
    console.print(f"[dim]The bundled version contains newer documentation and command updates.[/dim]")

    # In mock mode, auto-upgrade without prompting
    from rich.prompt import Confirm
    from devflow.utils import is_mock_mode
    mock_mode = is_mock_mode()

    should_upgrade = True
    if not mock_mode:
        console.print(f"\n[bold]Upgrade DAF_AGENTS.md to the latest version?[/bold]")
        console.print(f"[dim]This will replace: {installed_file}[/dim]")
        should_upgrade = Confirm.ask("Upgrade to latest version?", default=True)
    else:
        console.print(f"[dim]Mock mode: Auto-upgrading DAF_AGENTS.md at {installed_file}[/dim]")

    if not should_upgrade:
        console.print(f"[dim]Continuing with current version[/dim]")
        return True

    # Perform upgrade
    success, install_diagnostics = _install_bundled_cs_agents(installed_file)
    if success:
        console.print(f"[green]✓ Upgraded DAF_AGENTS.md in {location}[/green]")
        console.print(f"[dim]  Location: {installed_file}[/dim]")
        return True
    else:
        console.print(f"\n[red]✗ Failed to upgrade DAF_AGENTS.md[/red]")
        if install_diagnostics:
            console.print(f"\n[yellow]Debug information:[/yellow]")
            for diag in install_diagnostics:
                console.print(f"[dim]{diag}[/dim]")
        console.print(f"[dim]Continuing with current version[/dim]")
        return True  # Don't block session opening


def _validate_context_files(project_path: str, config_loader) -> bool:
    """Validate that required context files exist before launching Claude.

    Checks for DAF_AGENTS.md in this order:
    1. Repository directory (project-specific customization)
    2. Workspace directory (shared across projects)
    3. Offer to auto-install bundled DAF_AGENTS.md if not found

    If found, checks if installed version is outdated and prompts for upgrade.

    Args:
        project_path: Path to the project repository
        config_loader: Config loader to get workspace path

    Returns:
        True if DAF_AGENTS.md is found or successfully installed, False otherwise
    """
    repo_path = Path(project_path)
    cs_agents_repo = repo_path / "DAF_AGENTS.md"

    # Check repository directory first
    if cs_agents_repo.exists():
        console.print(f"[dim]✓ Found DAF_AGENTS.md in repository[/dim]")
        # Check if upgrade is needed
        if not _check_and_upgrade_daf_agents(cs_agents_repo, "repository"):
            return False
        return True

    # Check workspace directory as fallback
    config = config_loader.load_config()
    if config and config.repos and config.repos.get_default_workspace_path():
        workspace_path = config.repos.get_default_workspace_path()

        if not workspace_path:

            console.print("[yellow]⚠[/yellow] No default workspace configured")

            return None

        workspace_path = Path(workspace_path).expanduser()
        cs_agents_workspace = workspace_path / "DAF_AGENTS.md"

        if cs_agents_workspace.exists():
            console.print(f"[dim]✓ Found DAF_AGENTS.md in workspace (shared)[/dim]")
            console.print(f"[dim]  Location: {cs_agents_workspace}[/dim]")
            # Check if upgrade is needed
            if not _check_and_upgrade_daf_agents(cs_agents_workspace, "workspace"):
                return False
            return True

    # Not found - offer to install bundled DAF_AGENTS.md
    console.print(f"\n[yellow]⚠ DAF_AGENTS.md not found[/yellow]")
    console.print(f"\n[dim]DAF_AGENTS.md provides daf tool usage instructions to Claude.[/dim]")
    console.print(f"\nSearched locations:")
    console.print(f"  1. Repository: {cs_agents_repo}")
    if config and config.repos and config.repos.get_default_workspace_path():
        console.print(f"  2. Workspace:  {cs_agents_workspace}")

    # Offer to install bundled DAF_AGENTS.md
    # In mock mode, auto-install without prompting
    from rich.prompt import Confirm
    from devflow.utils import is_mock_mode
    mock_mode = is_mock_mode()

    should_install = True
    if not mock_mode:
        console.print(f"\n[bold]Install DAF_AGENTS.md now?[/bold]")
        console.print(f"[dim]This will copy the bundled DAF_AGENTS.md to: {cs_agents_repo}[/dim]")
        should_install = Confirm.ask("Install DAF_AGENTS.md to repository?", default=True)
    else:
        console.print(f"[dim]Mock mode: Auto-installing DAF_AGENTS.md to {cs_agents_repo}[/dim]")

    if not should_install:
        console.print(f"\n[yellow]Cannot continue without DAF_AGENTS.md[/yellow]")
        console.print(f"\n[bold]Manual installation options:[/bold]")
        console.print(f"\n  Option 1: Copy to repository (project-specific)")
        console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {repo_path}/")
        console.print(f"\n  Option 2: Copy to workspace (shared across all projects)")
        if config and config.repos and config.repos.get_default_workspace_path():
            console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {workspace_path}/")
        console.print(f"\nSee: https://github.com/itdove/devaiflow/blob/main/docs/02-installation.md")
        return False

    # Install bundled DAF_AGENTS.md to repository
    success, diagnostics = _install_bundled_cs_agents(cs_agents_repo)
    if success:
        console.print(f"[green]✓ Installed DAF_AGENTS.md to repository[/green]")
        console.print(f"[dim]  Location: {cs_agents_repo}[/dim]")
        console.print(f"\n[dim]You can customize DAF_AGENTS.md for your organization's needs.[/dim]")
        console.print(f"[dim]See: docs/02-installation.md#customizing-for-your-organization[/dim]")
        return True
    else:
        console.print(f"\n[red]✗ Failed to install DAF_AGENTS.md[/red]")

        if diagnostics:
            console.print(f"\n[yellow]Debug information:[/yellow]")
            for diag in diagnostics:
                console.print(f"[dim]{diag}[/dim]")

        console.print(f"\n[yellow]This may indicate:[/yellow]")
        console.print(f"  • DAF_AGENTS.md is not included in the package distribution (check setup.py)")
        console.print(f"  • Package was installed incorrectly")
        console.print(f"  • File permissions issue")

        console.print(f"\n[bold]Manual installation options:[/bold]")
        console.print(f"\n  Option 1: Copy to repository (project-specific)")
        console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {repo_path}/")
        console.print(f"\n  Option 2: Copy to workspace (shared across all projects)")
        if config and config.repos and config.repos.get_default_workspace_path():
            console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {workspace_path}/")
        console.print(f"\nSee: https://github.com/itdove/devaiflow/blob/main/docs/02-installation.md")
        return False


def _display_conflict_resolution_help(project_path: str, session_name: str) -> None:
    """Display detailed help for resolving merge conflicts.

    Args:
        project_path: Path to the project repository
        session_name: Name of the session to resume after resolution
    """
    repo_path = Path(project_path)

    console.print(f"\n[red]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/red]")
    console.print(f"[red]✗ MERGE CONFLICTS DETECTED[/red]")
    console.print(f"[red]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/red]")
    console.print()
    console.print(f"[yellow]Cannot launch Claude Code with unresolved merge conflicts.[/yellow]")
    console.print()

    # Get merge info
    merge_info = GitUtils.get_merge_head_info(repo_path)
    if merge_info:
        console.print(f"[bold]Merge Operation:[/bold]")
        if merge_info['merge_msg']:
            # Extract branch name from merge message
            msg_lines = merge_info['merge_msg'].split('\n')
            if msg_lines:
                console.print(f"  {msg_lines[0]}")
        if merge_info['merge_mode'] == 'rebase':
            console.print(f"  [dim](rebase in progress)[/dim]")
        console.print()

    # Get and display conflicted files with details
    conflicted_files = GitUtils.get_conflicted_files(repo_path)
    if conflicted_files:
        console.print(f"[bold red]Conflicted Files ({len(conflicted_files)}):[/bold red]")
        console.print()

        for i, file_path in enumerate(conflicted_files[:5], 1):  # Show first 5 files
            console.print(f"  [red]✗[/red] [bold]{file_path}[/bold]")

            # Get conflict details
            details = GitUtils.get_conflict_details(repo_path, file_path)
            if details:
                console.print(f"    [dim]└─ {details['conflict_count']} conflict(s) | "
                             f"{details['ours_branch']} ⟷ {details['theirs_branch']}[/dim]")

                # Show a preview of the first conflict for the first file
                if i == 1 and details['preview']:
                    console.print()
                    console.print(f"    [bold]Preview of first conflict:[/bold]")
                    preview_lines = details['preview'].split('\n')
                    for line in preview_lines[:10]:  # Show first 10 lines
                        if line.startswith('<<<<<<<'):
                            console.print(f"    [yellow]{line}[/yellow]")
                        elif line.startswith('======='):
                            console.print(f"    [cyan]{line}[/cyan]")
                        elif line.startswith('>>>>>>>'):
                            console.print(f"    [magenta]{line}[/magenta]")
                        else:
                            console.print(f"    [dim]{line}[/dim]")
                    console.print()
            console.print()

        if len(conflicted_files) > 5:
            console.print(f"  [dim]... and {len(conflicted_files) - 5} more file(s)[/dim]")
            console.print()

    # Resolution instructions
    console.print(f"[bold]How to Resolve:[/bold]")
    console.print()
    console.print(f"  [bold cyan]Option 1: Manual Resolution[/bold cyan]")
    console.print(f"    1. Open conflicted files in your editor")
    console.print(f"    2. Look for conflict markers:")
    console.print(f"       [yellow]<<<<<<< HEAD[/yellow]          (your current changes)")
    console.print(f"       [cyan]=======[/cyan]              (separator)")
    console.print(f"       [magenta]>>>>>>> branch[/magenta]       (incoming changes)")
    console.print(f"    3. Edit the file to keep the desired changes")
    console.print(f"    4. Remove the conflict markers ([yellow]<<<<<<<[/yellow], [cyan]=======[/cyan], [magenta]>>>>>>>[/magenta])")
    console.print(f"    5. Stage resolved files: [cyan]git add <file>[/cyan]")
    console.print(f"    6. Complete the merge: [cyan]git commit[/cyan]")
    console.print()

    console.print(f"  [bold cyan]Option 2: Accept All Changes from One Side[/bold cyan]")
    if merge_info:
        our_branch = GitUtils.get_current_branch(repo_path) or "current branch"
        their_branch = merge_info.get('theirs_branch', 'incoming branch')
        console.print(f"    Keep your changes:      [cyan]git checkout --ours <file> && git add <file>[/cyan]")
        console.print(f"    Keep incoming changes:  [cyan]git checkout --theirs <file> && git add <file>[/cyan]")
    else:
        console.print(f"    Keep current changes:   [cyan]git checkout --ours <file> && git add <file>[/cyan]")
        console.print(f"    Keep incoming changes:  [cyan]git checkout --theirs <file> && git add <file>[/cyan]")
    console.print()

    console.print(f"  [bold cyan]Option 3: Abort the Merge[/bold cyan]")
    console.print(f"    Cancel and return to previous state: [cyan]git merge --abort[/cyan]")
    console.print()

    # Quick reference commands
    console.print(f"[bold]Quick Reference:[/bold]")
    console.print(f"  View conflicts:         [cyan]git diff --name-only --diff-filter=U[/cyan]")
    console.print(f"  View conflict details:  [cyan]git diff <file>[/cyan]")
    console.print(f"  Check status:           [cyan]git status[/cyan]")
    console.print()

    console.print(f"[bold]After resolving conflicts, run:[/bold]")
    console.print(f"  [cyan]daf open {session_name}[/cyan]")
    console.print()
