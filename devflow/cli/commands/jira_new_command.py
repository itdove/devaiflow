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

from devflow.cli.utils import console_print, is_json_mode, output_json, prompt_repository_selection, require_outside_claude, scan_workspace_repositories, select_workspace, should_launch_claude_code
from devflow.git.utils import GitUtils

# Import unified utilities
from devflow.cli.signal_handler import setup_signal_handlers, is_cleanup_done
from devflow.cli.skills_discovery import discover_skills
from devflow.utils.context_files import load_hierarchical_context_files

console = Console()


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
    project_path: str,
    affects_versions: Optional[str] = None
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
    # AAP-64886: Get workspace path from session instead of using default
    from devflow.cli.utils import get_workspace_path
    workspace_path = None
    if session.workspace_name and config and config.repos:
        workspace_path = get_workspace_path(config, session.workspace_name)
    elif config and config.repos and config.repos.workspaces:
        # Fallback to default if session doesn't have workspace
        workspace_path = config.repos.get_default_workspace_path()
    initial_prompt = _build_ticket_creation_prompt(issue_type, parent, goal, config, name, project_path=project_path, workspace=workspace_path, affects_versions=affects_versions)

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
    workspace: Optional[str] = None,
    affects_versions: Optional[str] = None,
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
        workspace: Optional workspace name (overrides session default and config default)
        affects_versions: Optional affected version (required for bugs)
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
    selected_workspace_name = None
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
        project_path, selected_workspace_name = _prompt_for_repository_selection(config, workspace_flag=workspace)
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

    # AAP-64296: Store selected workspace in session
    if selected_workspace_name:
        session.workspace_name = selected_workspace_name

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
            project_path=project_path,
            affects_versions=affects_versions
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
    current_branch = GitUtils.get_current_branch(Path(temp_directory)) if temp_directory and GitUtils.is_git_repository(Path(temp_directory)) else None

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
    # AAP-64886: Get workspace path from session instead of using default
    from devflow.cli.utils import get_workspace_path
    workspace_path = None
    if session.workspace_name and config and config.repos:
        workspace_path = get_workspace_path(config, session.workspace_name)
    elif config and config.repos and config.repos.workspaces:
        # Fallback to default if session doesn't have workspace
        workspace_path = config.repos.get_default_workspace_path()
    initial_prompt = _build_ticket_creation_prompt(issue_type, parent, goal, config, name, project_path=project_path, workspace=workspace_path, affects_versions=affects_versions)

    # Set up signal handlers for cleanup (using unified utility)
    setup_signal_handlers(session, session_manager, name, config)

    # Set CS_SESSION_NAME environment variable so daf jira create can find the active session
    # This is more reliable than depending on AI_AGENT_SESSION_ID which may not be exported
    env = os.environ.copy()
    env["CS_SESSION_NAME"] = name

    # Set GCP Vertex AI region if configured
    if config and config.gcp_vertex_region:
        env["CLOUD_ML_REGION"] = config.gcp_vertex_region

    # Launch Claude Code with the session ID and initial prompt
    try:
        # Build command with all skills and context directories
        from devflow.utils.claude_commands import build_claude_command

        # AAP-64886: Get workspace path from session instead of using default
        workspace_path_for_skills = None
        if session.workspace_name and config and config.repos:
            workspace_path_for_skills = get_workspace_path(config, session.workspace_name)
        elif config and config.repos and config.repos.workspaces:
            # Fallback to default if session doesn't have workspace
            workspace_path_for_skills = config.repos.get_default_workspace_path()

        cmd = build_claude_command(
            session_id=ai_agent_session_id,
            initial_prompt=initial_prompt,
            project_path=project_path,
            workspace_path=workspace_path_for_skills,
            config=config
        )

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
        if not is_cleanup_done():
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




def _build_ticket_creation_prompt(
    issue_type: str,
    parent: Optional[str],
    goal: str,
    config,
    session_name: str,
    project_path: Optional[str] = None,
    workspace: Optional[str] = None,
    affects_versions: Optional[str] = None,
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
        affects_versions: Affected version for bugs (optional)

    Returns:
        Initial prompt string with analysis-only instructions
    """
    # Get JIRA project and field defaults from config
    project = config.jira.project if config.jira.project else "PROJ"

    # Load field mappings to check if version field is required for this issue type
    field_mapper = None
    if config and config.jira and config.jira.field_mappings:
        from devflow.jira.field_mapper import JiraFieldMapper
        from devflow.jira import JiraClient
        try:
            jira_client = JiraClient()
            field_mapper = JiraFieldMapper(jira_client, config.jira.field_mappings)
        except Exception:
            # If field mapper fails, continue without it
            pass
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
    hierarchical_files = load_hierarchical_context_files(config)

    # Discover skills from filesystem (instead of loading from config)
    # This ensures we only reference skills that actually exist on disk
    skill_files = discover_skills(project_path=project_path, workspace=workspace)

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

    # If affects_versions is required for this issue type, add to example command
    # Check field_mappings['affects_version/s']['required_for'] to see if issue_type is listed
    from devflow.jira.utils import is_version_field_required
    if is_version_field_required(field_mapper, issue_type=issue_type.capitalize()):
        # Use the provided affects_versions or show placeholder
        affected_ver = affects_versions if affects_versions else "VERSION"
        example_cmd_parts.append(f'--affects-versions "{affected_ver}"')

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

    # Add affects_versions note if required for this issue type
    # Check field_mappings['affects_version/s']['required_for'] to see if issue_type is listed
    if is_version_field_required(field_mapper, issue_type=issue_type.capitalize()):
        affected_version_note = f"IMPORTANT: For {issue_type}s, you MUST specify --affects-versions with the version affected."
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
        "⚠️  CRITICAL: Use EXACTLY this command format (do not modify syntax):",
        "",
        example_command,
        "",
        "⚠️  The command above is the EXACT format you MUST use. Do not attempt alternative formats.",
        "   Use this template precisely, filling in your analysis and findings.",
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


def _prompt_for_repository_selection(config, workspace_flag: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Prompt user to select a repository from workspace.

    Args:
        config: Configuration object
        workspace_flag: Optional workspace name from command line flag

    Returns:
        Tuple of (project_path, workspace_name) if selected, (None, None) if cancelled
    """
    # Select workspace using priority resolution system
    selected_workspace_name = select_workspace(
        config,
        workspace_flag=workspace_flag,  # Use workspace from --workspace flag if provided
        session=None,  # No existing session yet
        skip_prompt=False  # Always prompt for workspace selection
    )

    if not selected_workspace_name:
        # No workspace selected - fall back to current directory
        console_print(f"[yellow]⚠[/yellow] No workspace selected")
        console_print(f"[dim]Using current directory: {Path.cwd()}[/dim]")
        return str(Path.cwd()), None

    # Get workspace path from workspace name
    from devflow.cli.utils import get_workspace_path
    workspace_path = get_workspace_path(config, selected_workspace_name)
    if not workspace_path:
        console_print(f"[yellow]⚠[/yellow] Could not find workspace path for: {selected_workspace_name}")
        console_print(f"[dim]Using current directory: {Path.cwd()}[/dim]")
        return str(Path.cwd()), None

    console_print(f"\n[cyan]Scanning workspace:[/cyan] {workspace_path}")

    # Scan for git repositories in workspace
    try:
        repo_options = scan_workspace_repositories(workspace_path)
    except (ValueError, RuntimeError) as e:
        console_print(f"[yellow]Warning: {e}[/yellow]")
        console_print(f"[dim]Using current directory: {Path.cwd()}[/dim]")
        return str(Path.cwd()), None

    if not repo_options:
        console_print(f"[yellow]⚠[/yellow] No git repositories found in workspace")
        console_print(f"[dim]Make sure your workspace contains git repositories.[/dim]")
        console_print(f"[dim]Using current directory: {Path.cwd()}[/dim]")
        return str(Path.cwd()), None

    # Prompt user to select repository
    project_path = prompt_repository_selection(repo_options, workspace_path, allow_cancel=True)
    if not project_path:
        return None, None

    return project_path, selected_workspace_name
