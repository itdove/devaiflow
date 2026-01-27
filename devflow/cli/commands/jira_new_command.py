"""Command for daf jira new - create issue tracker ticket with session-type for ticket creation workflow."""

import os
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm

from devflow.cli.utils import console_print, is_json_mode, output_json, require_outside_claude, should_launch_claude_code
from devflow.git.utils import GitUtils

console = Console()

# Global variables for signal handler cleanup
_cleanup_session = None
_cleanup_session_manager = None
_cleanup_name = None
_cleanup_config = None
_cleanup_done = False


def _cleanup_on_signal(signum, frame):
    """Handle signals by performing cleanup before exit."""
    global _cleanup_done

    console_print(f"\n[yellow]Received signal {signum}, cleaning up...[/yellow]")

    if _cleanup_session and _cleanup_session_manager and _cleanup_name:
        console_print(f"[green]✓[/green] Claude session completed")

        # Reload index from disk before checking for rename
        # This is critical because the child process (Claude) may have renamed the session
        # and we need to see the latest state from disk, not our stale in-memory index
        _cleanup_session_manager.index = _cleanup_session_manager.config_loader.load_sessions()

        # Check if session was renamed during execution
        current_session = _cleanup_session_manager.get_session(_cleanup_name)
        actual_name = _cleanup_name

        if not current_session:
            # Session not found with original name - it was likely renamed
            console_print(f"[dim]Detecting renamed session...[/dim]")
            all_sessions = _cleanup_session_manager.list_sessions()
            # Match by Claude session ID which doesn't change during rename
            cleanup_claude_id = (_cleanup_session.active_conversation.ai_agent_session_id
                                if _cleanup_session.active_conversation else None)
            for s in all_sessions:
                s_claude_id = s.active_conversation.ai_agent_session_id if s.active_conversation else None
                if (s_claude_id and cleanup_claude_id and
                    s_claude_id == cleanup_claude_id and
                    s.session_type == "ticket_creation" and
                    s.name.startswith("creation-")):
                    actual_name = s.name
                    current_session = s
                    console_print(f"[dim]Session was renamed to: {actual_name}[/dim]")
                    break

        # Catch only specific exceptions that are expected from rename failures
        try:
            _cleanup_session_manager.end_work_session(actual_name)
        except ValueError as e:
            # Session name or ID mismatch - log but continue cleanup
            console_print(f"[yellow]⚠[/yellow] Could not end work session: {e}")

        console_print(f"[dim]Resume anytime with: daf open {actual_name}[/dim]")

        # Save conversation file to stable location before cleaning up temp directory
        if current_session and current_session.active_conversation and current_session.active_conversation.temp_directory:
            from devflow.cli.commands.open_command import _copy_conversation_from_temp
            _copy_conversation_from_temp(current_session, current_session.active_conversation.temp_directory)

        # Clean up temporary directory if present
        if _cleanup_session.active_conversation and _cleanup_session.active_conversation.temp_directory:
            from devflow.utils.temp_directory import cleanup_temp_directory
            cleanup_temp_directory(_cleanup_session.active_conversation.temp_directory)

        # Call the complete prompt
        # IMPORTANT: Do NOT wrap this in a broad exception handler
        # KeyboardInterrupt and EOFError should propagate to allow proper cleanup
        # Any exceptions from _prompt_for_complete_on_exit are already handled inside that function
        from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
        if current_session:
            _prompt_for_complete_on_exit(current_session, _cleanup_config)
        else:
            _prompt_for_complete_on_exit(_cleanup_session, _cleanup_config)

        # Mark cleanup as done so finally block doesn't repeat it
        _cleanup_done = True

    # Exit gracefully
    sys.exit(0)


def slugify_goal(goal: str) -> str:
    """Convert a goal string into a valid session name slug.

    Args:
        goal: The goal/description text

    Returns:
        Slugified name suitable for session identifier with random suffix
    """
    import re
    import secrets

    # Convert to lowercase
    slug = goal.lower()

    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)

    # Remove leading/trailing hyphens
    slug = slug.strip('-')

    # Limit length to 43 chars to leave room for random suffix (43 + 1 hyphen + 6 random = 50)
    if len(slug) > 43:
        slug = slug[:43].rstrip('-')

    # Add 6-character random suffix to prevent session name collisions
    # This prevents issues when multiple ticket creations with similar goals
    # fail to rename (e.g., "test-ticket-abc123", "test-ticket-def456")
    random_suffix = secrets.token_hex(3)  # 3 bytes = 6 hex chars
    slug = f"{slug}-{random_suffix}"

    return slug


def _create_mock_jira_ticket(
    session,
    session_manager,
    name: str,
    issue_type: str,
    parent: str,
    goal: str,
    config,
    project_path: str
) -> str:
    """Create a mock issue tracker ticket in mock mode.

    This function simulates the ticket creation workflow using MockClaudeCode
    and MockJiraClient without actually launching Claude or creating real issue tracker tickets.

    Args:
        session: Session object
        session_manager: SessionManager instance
        name: Session name
        issue_type: Type of JIRA issue (epic, story, task, bug)
        parent: Parent issue key
        goal: Goal/description for the ticket
        config: Configuration object
        project_path: Full path to the project directory

    Returns:
        The created ticket key (e.g., "PROJ-1")
    """
    from devflow.mocks.claude_mock import MockClaudeCode
    from devflow.mocks.jira_mock import MockJiraClient
    from devflow.utils import get_current_user
    from datetime import datetime

    console_print()
    console_print("[yellow]📝 Mock mode: Creating mock issue tracker ticket[/yellow]")

    # Initialize mock services
    mock_claude = MockClaudeCode()
    mock_jira = MockJiraClient(config=config)

    # Build initial prompt with session name
    # Get default workspace path for skills discovery (mock mode doesn't select workspace interactively)
    from devflow.cli.utils import get_workspace_path
    workspace_path = None
    if config and config.repos and config.repos.workspaces:
        workspace_path = config.repos.get_default_workspace_path()
    initial_prompt = _build_ticket_creation_prompt(issue_type, parent, goal, config, name, project_path=project_path, workspace=workspace_path, affected_version=affected_version)

    # Create mock Claude session with initial prompt
    ai_agent_session_id = mock_claude.create_session(
        project_path=project_path,
        initial_prompt=initial_prompt
    )

    # Simulate assistant response that creates the ticket
    if not config.jira.project:
        console.print("[yellow]Warning: No JIRA project configured. Run 'daf config tui' to set it.[/yellow]")
        project = "PROJ"  # Fallback for mock mode
    else:
        project = config.jira.project

    # Get all custom field defaults generically
    custom_fields = config.jira.custom_field_defaults if config.jira.custom_field_defaults else {}

    # Generate mock ticket summary and description
    summary = goal[:100]  # Limit to 100 chars for summary
    description = f"Mock ticket created for: {goal}"

    # Create mock issue tracker ticket with appropriate defaults
    # Pass custom fields generically (mock will handle formatting)
    ticket_data = mock_jira.create_ticket(
        issue_type=issue_type.capitalize(),
        summary=summary,
        description=description,
        project=project,
        priority="Major",
        parent=parent,
        **custom_fields,  # Pass all custom fields generically
    )

    mock_ticket_key = ticket_data["key"]

    # Build custom fields display string
    custom_fields_str = "\n".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in custom_fields.items()])

    # Simulate assistant message acknowledging ticket creation
    mock_claude.add_message(
        session_id=ai_agent_session_id,
        role="assistant",
        content=f"I've created mock issue tracker ticket {mock_ticket_key} with the following details:\n\n"
                f"Summary: {summary}\n"
                f"Type: {issue_type}\n"
                f"Parent: {parent}\n"
                f"Project: {project}\n"
                f"{custom_fields_str}"
    )

    # Update session with Claude session ID
    # Extract the working directory name from project_path
    working_dir_name = Path(project_path).name

    # Get current branch (or None if not a git repo)
    current_branch = GitUtils.get_current_branch(Path(project_path)) if GitUtils.is_git_repository(Path(project_path)) else None

    session.add_conversation(
        working_dir=working_dir_name,
        ai_agent_session_id=ai_agent_session_id,
        project_path=project_path,
        branch=current_branch,  # Current branch (or None if not a git repo)
    )
    session.working_directory = working_dir_name  # Set working_directory for active_conversation lookup

    session_manager.update_session(session)

    # Auto-rename session to creation-<ticket_key>
    new_name = f"creation-{mock_ticket_key}"
    try:
        session_manager.rename_session(name, new_name)
        # Verify the rename was successful
        renamed_session = session_manager.get_session(new_name)
        if renamed_session and renamed_session.name == new_name:
            # Set JIRA metadata on renamed session
            renamed_session.issue_key = mock_ticket_key
            if not renamed_session.issue_metadata:
                renamed_session.issue_metadata = {}
            renamed_session.issue_metadata["summary"] = summary
            renamed_session.issue_metadata["type"] = issue_type.capitalize()
            renamed_session.issue_metadata["status"] = "New"
            session_manager.update_session(renamed_session)

            console_print(f"[green]✓[/green] Created mock issue tracker ticket: [bold]{mock_ticket_key}[/bold]")
            console_print(f"[green]✓[/green] Renamed session to: [bold]{new_name}[/bold]")
        else:
            # Rename may have failed silently
            console_print(f"[green]✓[/green] Created mock issue tracker ticket: [bold]{mock_ticket_key}[/bold]")
            console_print(f"[yellow]⚠[/yellow] Session rename may have failed")
            console_print(f"   Expected: [bold]{new_name}[/bold]")
            console_print(f"   Actual: [bold]{name}[/bold]")
            new_name = name  # Keep original name
    except ValueError as e:
        # Session name already exists - warn but continue
        console_print(f"[green]✓[/green] Created mock issue tracker ticket: [bold]{mock_ticket_key}[/bold]")
        console_print(f"[yellow]⚠[/yellow] Could not rename session: {e}")
        console_print(f"   Session name: [bold]{name}[/bold]")
        new_name = name  # Keep original name

    console_print(f"[dim]Summary: {summary}[/dim]")
    console_print(f"[dim]Type: {issue_type}[/dim]")
    console_print(f"[dim]Parent: {parent}[/dim]")
    console_print(f"[dim]Status: New[/dim]")
    console_print()
    console_print(f"[dim]View with: daf jira view {mock_ticket_key}[/dim]")
    console_print(f"[dim]Reopen session with: daf open {new_name}[/dim]")
    console_print()

    return mock_ticket_key


@require_outside_claude
def create_jira_ticket_session(
    issue_type: str,
    parent: Optional[str],
    goal: str,
    name: Optional[str] = None,
    path: Optional[str] = None,
    branch: Optional[str] = None,
    affected_version: Optional[str] = None,
) -> None:
    """Create a new session for issue tracker ticket creation.

    This creates a session with session_type="ticket_creation" which:
    - Skips branch creation automatically
    - Includes analysis-only instructions in the initial prompt
    - Persists the session type for reopening

    Args:
        issue_type: Type of JIRA issue (epic, story, task, bug)
        parent: Optional parent issue key (epic for story/task/bug, story for subtask)
        goal: Goal/description for the ticket
        name: Optional session name (auto-generated from goal if not provided)
        path: Optional project path (bypasses interactive selection if provided)
        branch: Optional git branch name
        affected_version: Optional affected version (required for bugs)
    """
    from devflow.session.manager import SessionManager
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console_print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        if is_json_mode():
            output_json(success=False, error={"message": "No configuration found", "code": "NO_CONFIG"})
        return

    # Validate parent ticket if provided
    # Skip validation in mock mode to allow tests to run
    from devflow.utils import is_mock_mode
    if parent and not is_mock_mode():
        console_print(f"[dim]Validating parent ticket: {parent}[/dim]")
        from devflow.jira.utils import validate_jira_ticket
        from devflow.jira import JiraClient

        try:
            jira_client = JiraClient()
            parent_ticket = validate_jira_ticket(parent, client=jira_client)

            if not parent_ticket:
                # Error already displayed by validate_jira_ticket
                console_print(f"[red]✗[/red] Cannot proceed with invalid parent ticket")
                if is_json_mode():
                    output_json(
                        success=False,
                        error={
                            "code": "INVALID_PARENT",
                            "message": f"Parent ticket {parent} not found or validation failed"
                        }
                    )
                return
        except Exception as e:
            console_print(f"[red]✗[/red] Failed to validate parent ticket: {e}")
            if is_json_mode():
                output_json(success=False, error={"message": f"Parent validation failed: {e}", "code": "VALIDATION_ERROR"})
            return

        console_print(f"[green]✓[/green] Parent ticket validated: {parent}")

    # Auto-generate session name from goal if not provided
    if not name:
        name = slugify_goal(goal)
        console_print(f"[dim]Auto-generated session name: {name}[/dim]")

    # Determine project path
    if path is not None:
        # Use provided path
        project_path = str(Path(path).absolute())
        # Validate path exists
        if not Path(project_path).exists():
            console_print(f"[red]✗[/red] Directory does not exist: {project_path}")
            if is_json_mode():
                output_json(success=False, error={"message": f"Directory does not exist: {project_path}", "code": "INVALID_PATH"})
            return
        console_print(f"[dim]Using specified path: {project_path}[/dim]")
    else:
        # Prompt for repository selection from workspace (similar to daf new and daf open)
        project_path = _prompt_for_repository_selection(config)
        if not project_path:
            # User cancelled or no workspace configured
            return

    working_directory = Path(project_path).name

    # Prompt to clone project in temporary directory for clean analysis
    # Skip in mock mode or JSON mode to avoid interactive prompts in tests/automation
    temp_directory = None
    original_project_path = None
    from devflow.utils import is_mock_mode
    mock_mode = is_mock_mode()
    is_json = is_json_mode()

    # Skip temp directory prompt in non-interactive modes
    should_skip_temp_prompt = mock_mode or is_json

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
                # This ensures exports/imports show the actual repo name, not the temp directory name
                working_directory = Path(original_project_path).name
                console_print(f"[green]✓[/green] Using temporary clone: {temp_directory}")
            else:
                console_print(f"[dim]User declined temp clone or cloning failed - using current directory[/dim]")

    # Build the goal string that includes the ticket creation task
    if parent:
        full_goal = f"Create JIRA {issue_type} under {parent}: {goal}"
    else:
        full_goal = f"Create JIRA {issue_type}: {goal}"

    # Create session with session_type="ticket_creation"
    session_manager = SessionManager(config_loader=config_loader)

    session = session_manager.create_session(
        name=name,
        goal=full_goal,
        working_directory=working_directory,
        project_path=project_path,
        branch=branch,  # Use provided branch or None for no branch
    )

    # Set session_type to "ticket_creation"
    session.session_type = "ticket_creation"
    session_manager.update_session(session)

    console_print(f"\n[green]✓[/green] Created session [cyan]{name}[/cyan] (session_type: [yellow]ticket_creation[/yellow])")
    console_print(f"[dim]Goal: {full_goal}[/dim]")
    if parent:
        console_print(f"[dim]Parent: {parent}[/dim]")
    console_print(f"[dim]Working directory: {working_directory}[/dim]")
    console_print(f"[dim]No branch will be created (analysis-only mode)[/dim]\n")

    # In mock mode, create mock ticket instead of launching Claude
    if is_mock_mode():
        ticket_key = _create_mock_jira_ticket(
            session=session,
            session_manager=session_manager,
            name=name,
            issue_type=issue_type,
            parent=parent,
            goal=goal,
            config=config,
            project_path=project_path
        )

        # Output JSON if in JSON mode
        if is_json_mode():
            from devflow.cli.utils import serialize_session
            # After PROJ-60665, session is renamed to creation-<ticket_key>
            renamed_session_name = f"creation-{ticket_key}"
            # Get the renamed session for serialization
            renamed_session = session_manager.get_session(renamed_session_name)
            if renamed_session is None:
                # Fallback if rename failed
                renamed_session = session
                renamed_session_name = name
            output_json(
                success=True,
                data={
                    "ticket_key": ticket_key,
                    "session_name": renamed_session_name,
                    "session": serialize_session(renamed_session),
                    "issue_type": issue_type,
                    "parent": parent,
                    "goal": goal
                }
            )
        return

    # Check if we should launch Claude Code
    if not should_launch_claude_code(config=config, mock_mode=False):
        console_print("[yellow]⚠[/yellow] Session created but Claude Code not launched.")
        console_print(f"  Run [cyan]daf open {name}[/cyan] to start working on it.")
        return

    # Generate a new Claude session ID
    ai_agent_session_id = str(uuid.uuid4())

    # Update session with Claude session ID
    # Get current branch from temp directory (or None if not a git repo)
    current_branch = GitUtils.get_current_branch(Path(temp_directory)) if GitUtils.is_git_repository(Path(temp_directory)) else None

    session.add_conversation(
        working_dir=working_directory,
        ai_agent_session_id=ai_agent_session_id,
        project_path=project_path,
        branch=current_branch,  # Current branch from temp directory
        temp_directory=temp_directory,
        original_project_path=original_project_path,
    )
    session.working_directory = working_directory  # Set working_directory for active_conversation lookup

    # Start time tracking
    session_manager.start_work_session(name)

    session_manager.update_session(session)

    # Build initial prompt with analysis-only constraints and session metadata
    # Get default workspace path for skills discovery
    from devflow.cli.utils import get_workspace_path
    workspace_path = None
    if config and config.repos and config.repos.workspaces:
        workspace_path = config.repos.get_default_workspace_path()
    initial_prompt = _build_ticket_creation_prompt(issue_type, parent, goal, config, name, project_path=project_path, workspace=workspace_path, affected_version=affected_version)

    # Set up signal handlers for cleanup
    global _cleanup_session, _cleanup_session_manager, _cleanup_name, _cleanup_config, _cleanup_done
    _cleanup_session = session
    _cleanup_session_manager = session_manager
    _cleanup_name = name
    _cleanup_config = config

    # Register signal handlers for graceful shutdown
    # SIGTERM is not available on Windows, use SIGBREAK instead
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _cleanup_on_signal)
    else:
        signal.signal(signal.SIGBREAK, _cleanup_on_signal)
    signal.signal(signal.SIGINT, _cleanup_on_signal)

    # Set CS_SESSION_NAME environment variable so daf jira create can find the active session
    # This is more reliable than depending on AI_AGENT_SESSION_ID which may not be exported
    env = os.environ.copy()
    env["CS_SESSION_NAME"] = name

    # Set GCP Vertex AI region if configured
    if config and config.gcp_vertex_region:
        env["CLOUD_ML_REGION"] = config.gcp_vertex_region

    # Launch Claude Code with the session ID and initial prompt
    try:
        # Build command: prompt must come BEFORE --add-dir flags (positional argument)
        cmd = ["claude", "--session-id", ai_agent_session_id, initial_prompt]

        # Add all skills directories to allowed paths (auto-approve skill file reads)
        # Skills can be in 3 locations: user-level, workspace-level, project-level
        skills_dirs = []

        # 1. User-level skills: ~/.claude/skills/
        user_skills = Path.home() / ".claude" / "skills"
        if user_skills.exists():
            skills_dirs.append(str(user_skills))

        # 2. Workspace-level skills: <workspace>/.claude/skills/
        # Use default workspace path for skills discovery
        if config and config.repos and config.repos.workspaces:
            from devflow.utils.claude_commands import get_workspace_skills_dir
            default_workspace_path = config.repos.get_default_workspace_path()
            if default_workspace_path:
                workspace_skills = get_workspace_skills_dir(default_workspace_path)
                if workspace_skills.exists():
                    skills_dirs.append(str(workspace_skills))

        # 3. Project-level skills: <project>/.claude/skills/
        project_skills = Path(project_path) / ".claude" / "skills"
        if project_skills.exists():
            skills_dirs.append(str(project_skills))

        # Add all discovered skills directories AFTER the prompt
        for skills_dir in skills_dirs:
            cmd.extend(["--add-dir", skills_dir])

        # Add DEVAIFLOW_HOME to allowed paths if hierarchical context files exist
        # This allows Claude Code to read ENTERPRISE.md, ORGANIZATION.md, TEAM.md, USER.md
        from devflow.utils.paths import get_cs_home
        cs_home = get_cs_home()
        if cs_home.exists():
            hierarchical_files = _load_hierarchical_context_files(config)
            if hierarchical_files:
                cmd.extend(["--add-dir", str(cs_home)])

        # Debug: Print command being executed
        console_print(f"\n[dim]Debug - Command:[/dim]")
        console_print(f"[dim]  claude executable: {cmd[0]}[/dim]")
        console_print(f"[dim]  --session-id: {cmd[2]}[/dim]")
        console_print(f"[dim]  --add-dir flags: {len([x for x in cmd if x == '--add-dir'])}[/dim]")
        console_print(f"[dim]  Prompt (first 100 chars): {cmd[-1][:100]}...[/dim]")
        console_print(f"[dim]  Working directory: {project_path}[/dim]")
        console_print()

        subprocess.run(
            cmd,
            cwd=project_path,
            env=env,
            check=False
        )
    finally:
        if not _cleanup_done:
            console_print(f"\n[green]✓[/green] Claude session completed")

            # Reload index from disk before checking for rename
            # This is critical because the child process (Claude) may have renamed the session
            # and we need to see the latest state from disk, not our stale in-memory index
            session_manager.index = session_manager.config_loader.load_sessions()

            # Check if session was renamed during execution
            # This happens when daf jira create renames from temp name to creation-PROJ-*
            current_session = session_manager.get_session(name)
            actual_name = name

            if not current_session:
                # Session not found with original name - it was likely renamed
                # Find the renamed session by searching for ticket_creation sessions
                # with creation-* pattern that have the same Claude session ID
                console_print(f"[dim]Detecting renamed session...[/dim]")
                all_sessions = session_manager.list_sessions()
                # Match by Claude session ID which doesn't change during rename
                session_claude_id = (session.active_conversation.ai_agent_session_id
                                    if session.active_conversation else None)
                for s in all_sessions:
                    s_claude_id = s.active_conversation.ai_agent_session_id if s.active_conversation else None
                    if (s_claude_id and session_claude_id and
                        s_claude_id == session_claude_id and
                        s.session_type == "ticket_creation" and
                        s.name.startswith("creation-")):
                        actual_name = s.name
                        current_session = s
                        console_print(f"[dim]Session was renamed to: {actual_name}[/dim]")
                        break

            # Auto-pause: End work session when Claude Code closes
            # Catch only specific exceptions that are expected from rename failures
            try:
                session_manager.end_work_session(actual_name)
            except ValueError as e:
                # Session name or ID mismatch - log but continue cleanup
                console_print(f"[yellow]⚠[/yellow] Could not end work session: {e}")

            console_print(f"[dim]Resume anytime with: daf open {actual_name}[/dim]")

            # Save conversation file to stable location before cleaning up temp directory
            # This is needed when temp_directory was used (stored in session metadata)
            if current_session and current_session.active_conversation and current_session.active_conversation.temp_directory:
                from devflow.cli.commands.open_command import _copy_conversation_from_temp
                _copy_conversation_from_temp(current_session, current_session.active_conversation.temp_directory)

            # Clean up temporary directory if present
            if temp_directory:
                from devflow.utils.temp_directory import cleanup_temp_directory
                cleanup_temp_directory(temp_directory)

            # Check if we should run 'daf complete' on exit
            # Import here to avoid circular dependency
            # IMPORTANT: Do NOT wrap this in a broad exception handler
            # KeyboardInterrupt and EOFError should propagate to allow proper cleanup
            # Any exceptions from _prompt_for_complete_on_exit are already handled inside that function
            from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
            # Use the current session (which may be renamed) and actual name
            if current_session:
                _prompt_for_complete_on_exit(current_session, config)
            else:
                # Fallback if we couldn't find the session
                _prompt_for_complete_on_exit(session, config)


def _load_hierarchical_context_files(config: Optional['Config']) -> list:
    """Load context files from hierarchical configuration.

    Returns list of (path, description) tuples for context files that EXIST.

    Checks for context files from:
    - Backend: backends/JIRA.md
    - Enterprise: ENTERPRISE.md
    - Organization: ORGANIZATION.md
    - Team: TEAM.md
    - User: USER.md

    Only returns files that physically exist on disk.
    Paths are resolved relative to DEVAIFLOW_HOME.

    Args:
        config: Configuration object (may be None, not used currently but kept for future use)

    Returns:
        List of (absolute_path, description) tuples for existing files only
    """
    from devflow.utils.paths import get_cs_home

    context_files = []
    cs_home = get_cs_home()

    # Backend context (JIRA backend specific)
    backend_path = cs_home / "backends" / "JIRA.md"
    if backend_path.exists() and backend_path.is_file():
        # Use absolute path so Claude can read it with Read tool
        context_files.append((str(backend_path), "JIRA backend integration rules"))

    # Enterprise context
    enterprise_path = cs_home / "ENTERPRISE.md"
    if enterprise_path.exists() and enterprise_path.is_file():
        context_files.append((str(enterprise_path), "enterprise-wide policies and standards"))

    # Organization context
    org_path = cs_home / "ORGANIZATION.md"
    if org_path.exists() and org_path.is_file():
        context_files.append((str(org_path), "organization-wide policies and requirements"))

    # Team context
    team_path = cs_home / "TEAM.md"
    if team_path.exists() and team_path.is_file():
        context_files.append((str(team_path), "team conventions and workflows"))

    # User context
    user_path = cs_home / "USER.md"
    if user_path.exists() and user_path.is_file():
        context_files.append((str(user_path), "personal notes and preferences"))

    return context_files


def _discover_all_skills(project_path: Optional[str] = None, workspace: Optional[str] = None) -> list[tuple[str, str]]:
    """Discover all skills from user-level, workspace-level, hierarchical (DEVAIFLOW_HOME), and project-level locations.

    Discovery order (guarantees load order - generic skills before organization-specific extensions):
    1. User-level generic skills: ~/.claude/skills/ (alphabetical)
    2. Workspace-level skills: <workspace>/.claude/skills/ (alphabetical) - generic tool skills (daf-cli, gh-cli, etc.)
    3. Hierarchical skills: $DEVAIFLOW_HOME/.claude/skills/ (numbered: 01-enterprise, 02-organization, etc.) - extends generic skills
    4. Project-level skills: <project>/.claude/skills/ (alphabetical)

    Rationale: Hierarchical skills extend generic skills (see "Extends: daf-cli" in skill frontmatter),
    so generic skills must be loaded first.

    Args:
        project_path: Project directory path (for project-level skills)
        workspace: Workspace directory path (for workspace-level skills)

    Returns:
        List of tuples (skill_path, description) for all discovered skills in load order
    """
    discovered_skills = []

    def _scan_skill_dir(skill_file: Path, skill_dir_name: str) -> Optional[tuple[str, str]]:
        """Scan a single skill directory and extract description."""
        if not skill_file.exists():
            return None

        description = f"{skill_dir_name} skill"
        # Try to extract description from YAML frontmatter
        try:
            with open(skill_file, 'r') as f:
                lines = f.readlines()
                if lines and lines[0].strip() == '---':
                    for line in lines[1:]:
                        if line.strip() == '---':
                            break
                        if line.startswith('description:'):
                            description = line.split('description:', 1)[1].strip()
                            break
        except Exception:
            pass

        return (str(skill_file.resolve()), description)

    # 1. User-level skills: ~/.claude/skills/ (generic skills like daf-cli, git-cli)
    user_skills_dir = Path.home() / ".claude" / "skills"
    if user_skills_dir.exists():
        for skill_dir in sorted(user_skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                result = _scan_skill_dir(skill_file, skill_dir.name)
                if result:
                    discovered_skills.append(result)

    # 2. Workspace-level skills: <workspace>/.claude/skills/ (generic tool skills)
    if workspace:
        from devflow.utils.claude_commands import get_workspace_skills_dir
        workspace_skills_dir = get_workspace_skills_dir(workspace)
        if workspace_skills_dir.exists():
            for skill_dir in sorted(workspace_skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    result = _scan_skill_dir(skill_file, skill_dir.name)
                    if result:
                        discovered_skills.append(result)

    # 3. Hierarchical skills: $DEVAIFLOW_HOME/.claude/skills/ (organization-specific skills that extend generic ones)
    # These are numbered (01-enterprise, 02-organization, 03-team, 04-user) to guarantee order
    from devflow.utils.paths import get_cs_home
    cs_home = get_cs_home()
    hierarchical_skills_dir = cs_home / ".claude" / "skills"
    if hierarchical_skills_dir.exists():
        # Sort to ensure numbered order (01-, 02-, 03-, 04-)
        for skill_dir in sorted(hierarchical_skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                result = _scan_skill_dir(skill_file, skill_dir.name)
                if result:
                    discovered_skills.append(result)

    # 4. Project-level skills: <project>/.claude/skills/
    if project_path:
        project_skills_dir = Path(project_path) / ".claude" / "skills"
        if project_skills_dir.exists():
            for skill_dir in sorted(project_skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    result = _scan_skill_dir(skill_file, skill_dir.name)
                    if result:
                        discovered_skills.append(result)

    return discovered_skills


def _build_ticket_creation_prompt(
    issue_type: str,
    parent: Optional[str],
    goal: str,
    config,
    session_name: str,
    project_path: Optional[str] = None,
    workspace: Optional[str] = None,
    affected_version: Optional[str] = None,
) -> str:
    """Build the initial prompt for ticket creation sessions.

    Args:
        issue_type: Type of JIRA issue (epic, story, task, bug)
        parent: Parent issue key (optional)
        goal: Goal/description for the ticket
        config: Configuration object
        session_name: Name of the session (unused, kept for backward compatibility)
        project_path: Unused, kept for backward compatibility
        workspace: Workspace path for skill discovery
        affected_version: Affected version for bugs (optional)

    Returns:
        Initial prompt string with analysis-only instructions
    """
    # Get JIRA project and field defaults from config
    project = config.jira.project if config.jira.project else "PROJ"
    custom_fields = config.jira.custom_field_defaults if config.jira.custom_field_defaults else {}
    system_fields = config.jira.system_field_defaults if config.jira.system_field_defaults else {}

    # Build the "Work on" line based on whether parent is provided
    if parent:
        work_on_line = f"Work on: Create JIRA {issue_type} under {parent} for: {goal}"
    else:
        work_on_line = f"Work on: Create JIRA {issue_type} for: {goal}"

    prompt_parts = [
        work_on_line,
        "",
    ]

    # Add context files section (includes skills registered as hidden context files)
    default_files = [
        ("AGENTS.md", "agent-specific instructions"),
        ("CLAUDE.md", "project guidelines and standards"),
        ("DAF_AGENTS.md", "daf tool usage guide"),
    ]

    # Load configured context files from config (non-skill files only)
    configured_files = []
    if config and config.context_files:
        # Only include non-skill context files from config (hidden=false)
        # Skills will be discovered from filesystem instead
        configured_files = [(f.path, f.description) for f in config.context_files.files if not f.hidden]

    # Load hierarchical context files (only those that exist)
    hierarchical_files = _load_hierarchical_context_files(config)

    # Discover skills from filesystem (instead of loading from config)
    # This ensures we only reference skills that actually exist on disk
    skill_files = _discover_all_skills(project_path=project_path, workspace=workspace)

    # Combine regular context files: defaults + hierarchical + configured (no skills from config)
    regular_files = default_files + hierarchical_files + configured_files

    prompt_parts.append("Please start by reading the following context files if they exist:")
    for path, description in regular_files:
        prompt_parts.append(f"- {path} ({description})")

    # Add explicit skill loading section if skills are present
    if skill_files:
        prompt_parts.append("")
        prompt_parts.append("⚠️  CRITICAL: Read ALL of the following skill files before proceeding:")
        for path, description in skill_files:
            prompt_parts.append(f"- {path}")
        prompt_parts.append("")
        prompt_parts.append("These skills contain essential tool usage information and must be read completely.")

    prompt_parts.append("")

    # Build example command with all configured defaults
    example_cmd_parts = [f"daf jira create {issue_type}"]
    example_cmd_parts.append('--summary "..."')

    if parent:
        example_cmd_parts.append(f'--parent {parent}')

    # For bugs, add affected_version parameter (required field)
    if issue_type == "bug":
        # Use the provided affected_version or show placeholder
        affected_ver = affected_version if affected_version else "VERSION"
        example_cmd_parts.append(f'--affected-version "{affected_ver}"')

    # Add system field defaults (components, labels, etc.)
    if system_fields:
        if "components" in system_fields and system_fields["components"]:
            # components can be a list
            components = system_fields["components"]
            if isinstance(components, list):
                example_cmd_parts.append(f'--components {" ".join(components)}')
            else:
                example_cmd_parts.append(f'--components {components}')

        if "labels" in system_fields and system_fields["labels"]:
            labels = system_fields["labels"]
            if isinstance(labels, list):
                example_cmd_parts.append(f'--labels {" ".join(labels)}')
            else:
                example_cmd_parts.append(f'--labels {labels}')

    # Add description and acceptance criteria
    example_cmd_parts.append('--description "<your analysis here>"')
    example_cmd_parts.append('--field acceptance_criteria="..."')

    # Add custom field defaults (workstream, etc.)
    for key, value in custom_fields.items():
        example_cmd_parts.append(f'--field {key}="{value}"')

    example_command = " \\\n  ".join(example_cmd_parts)

    # Build instruction strings
    parent_instruction = f"4. IMPORTANT: Link to parent using --parent {parent}" if parent else "4. (Optional) Link to a parent epic using --parent EPIC-KEY if desired"

    # Add affected_version note for bugs
    if issue_type == "bug":
        affected_version_note = f"IMPORTANT: For bugs, you MUST specify --affected-version with the version this bug affects."
    else:
        affected_version_note = None

    parent_note = "Note: The --parent parameter automatically maps to the appropriate JIRA parent field based on your configuration."

    # Build defaults summary for instruction line
    defaults_parts = []
    if custom_fields:
        custom_parts = [f"{k}={v}" for k, v in custom_fields.items()]
        defaults_parts.append(f"custom fields: {', '.join(custom_parts)}")
    if system_fields:
        system_parts = [f"{k}={v}" for k, v in system_fields.items() if v]
        if system_parts:
            defaults_parts.append(f"system fields: {', '.join(system_parts)}")
    defaults_str = "; ".join(defaults_parts) if defaults_parts else "no defaults configured"

    prompt_parts.extend([
        "⚠️  IMPORTANT CONSTRAINTS:",
        "   • This is an ANALYSIS-ONLY session for issue tracker ticket creation",
        "   • DO NOT modify any code or create/checkout git branches",
        "   • DO NOT make any file changes - only READ and ANALYZE",
        "   • Focus on understanding the codebase to write a good issue tracker ticket",
        "",
        "Your task:",
        f"1. Analyze the codebase to understand how to implement: {goal}",
        "2. Read relevant files, search for patterns, understand the architecture",
        f"3. Create a detailed JIRA {issue_type} using the 'daf jira create' command",
        parent_instruction,
        f"5. Use project: {project}; configured defaults: {defaults_str}",
        "6. Include detailed description and acceptance criteria based on your analysis",
        "",
    ])

    prompt_parts.extend([
        example_command,
        "",
        parent_note,
    ])

    if affected_version_note:
        prompt_parts.append(affected_version_note)

    prompt_parts.extend([
        "",
        "After you create the ticket, the session will be automatically renamed to 'creation-<ticket_key>'",
        "for easy identification. Users can reopen with: daf open creation-<ticket_key>",
        "",
        "Remember: This is READ-ONLY analysis. Do not modify any files.",
    ])

    return "\n".join(prompt_parts)


def _prompt_for_repository_selection(config) -> Optional[str]:
    """Prompt user to select a repository from workspace.

    Args:
        config: Configuration object

    Returns:
        Project path string if selected, None if cancelled or no workspace
    """
    from rich.prompt import Prompt
    from devflow.cli.utils import select_workspace, get_workspace_path

    # Select workspace using priority resolution system
    selected_workspace_name = select_workspace(
        config,
        workspace_flag=None,  # No --workspace flag for jira new
        session=None,  # No existing session yet
        skip_prompt=False  # Always prompt for workspace selection
    )

    if not selected_workspace_name:
        # No workspace selected - fall back to current directory
        console_print(f"[yellow]⚠[/yellow] No workspace selected")
        console_print(f"[dim]Using current directory: {Path.cwd()}[/dim]")
        return str(Path.cwd())

    # Get workspace path from workspace name
    workspace_path = get_workspace_path(config, selected_workspace_name)
    if not workspace_path:
        console_print(f"[yellow]⚠[/yellow] Could not find workspace path for: {selected_workspace_name}")
        console_print(f"[dim]Using current directory: {Path.cwd()}[/dim]")
        return str(Path.cwd())

    workspace = Path(workspace_path).expanduser()

    if not workspace.exists() or not workspace.is_dir():
        console_print(f"[yellow]⚠[/yellow] Workspace directory does not exist: {workspace}")
        console_print(f"[dim]Using current directory: {Path.cwd()}[/dim]")
        return str(Path.cwd())

    console_print(f"\n[cyan]Scanning workspace:[/cyan] {workspace}")

    # List all git repositories in workspace
    repo_options = []
    try:
        from devflow.git.utils import GitUtils
        directories = [d for d in workspace.iterdir() if d.is_dir() and not d.name.startswith('.')]
        # Filter to only include git repositories
        git_repos = [d.name for d in directories if GitUtils.is_git_repository(d)]
        repo_options = sorted(git_repos)
    except Exception as e:
        console_print(f"[yellow]Warning: Could not scan workspace: {e}[/yellow]")
        console_print(f"[dim]Using current directory: {Path.cwd()}[/dim]")
        return str(Path.cwd())

    if not repo_options:
        console_print(f"[yellow]⚠[/yellow] No git repositories found in workspace")
        console_print(f"[dim]Make sure your workspace contains git repositories.[/dim]")
        console_print(f"[dim]Using current directory: {Path.cwd()}[/dim]")
        return str(Path.cwd())

    # Display available repositories
    console_print(f"\n[bold]Available repositories ({len(repo_options)}):[/bold]")
    for i, repo in enumerate(repo_options, 1):
        console_print(f"  {i}. {repo}")

    # Prompt for selection
    console_print(f"\n[bold]Select repository:[/bold]")
    console_print(f"  • Enter a number (1-{len(repo_options)}) to select from the list")
    console_print(f"  • Enter a repository name")
    console_print(f"  • Enter 'cancel' to exit")

    selection = Prompt.ask("Selection")

    # Validate input is not empty
    if not selection or selection.strip() == "":
        console_print(f"[red]✗[/red] Empty selection not allowed. Please enter a number (1-{len(repo_options)}), repository name, or 'cancel'")
        return None

    # Handle cancel
    if selection.lower() == "cancel":
        console_print(f"\n[yellow]Cancelled[/yellow]")
        return None

    # Check if it's a number (selecting from list)
    if selection.isdigit():
        repo_index = int(selection) - 1
        if 0 <= repo_index < len(repo_options):
            repo_name = repo_options[repo_index]
            console_print(f"[dim]Selected: {repo_name}[/dim]")
            project_path = workspace / repo_name
            return str(project_path)
        else:
            console_print(f"[red]✗[/red] Invalid selection. Please choose 1-{len(repo_options)}")
            return None

    # Otherwise treat as repository name
    repo_name = selection
    project_path = workspace / repo_name

    if not project_path.exists():
        console_print(f"[yellow]⚠[/yellow] Repository not found: {project_path}")
        if not Confirm.ask("Use this path anyway?", default=False):
            console_print(f"\n[yellow]Cancelled[/yellow]")
            return None

    return str(project_path)
