"""Command for daf git new - create GitHub/GitLab issue with session-type for ticket creation workflow."""

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
from devflow.cli.commands.sync_command import issue_key_to_session_name
from devflow.git.utils import GitUtils

# Import unified utilities
from devflow.cli.signal_handler import setup_signal_handlers, is_cleanup_done
from devflow.cli.skills_discovery import discover_skills
from devflow.utils.context_files import load_hierarchical_context_files
from devflow.utils.daf_agents_validation import validate_daf_agents_md

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


def _create_mock_git_issue(
    session,
    session_manager,
    name: str,
    issue_type: Optional[str],
    goal: str,
    config,
    project_path: str,
    parent: Optional[str] = None,
    repository: Optional[str] = None,
) -> str:
    """Create a mock GitHub/GitLab issue in mock mode.

    This function simulates the issue creation workflow using MockClaudeCode
    and MockGitHubClient without actually launching Claude or creating real issues.

    Args:
        session: Session object
        session_manager: SessionManager instance
        name: Session name
        issue_type: Optional type of issue (bug, enhancement, task). If None, no type label is added
        goal: Goal/description for the issue
        config: Configuration object
        project_path: Full path to the project directory
        parent: Optional parent issue key (owner/repo#123 or #123)
        repository: Optional repository in owner/repo format

    Returns:
        The created issue key (e.g., "#123")
    """
    from devflow.mocks.claude_mock import MockClaudeCode
    from devflow.utils import get_current_user
    from datetime import datetime

    console_print()
    console_print("[yellow]📝 Mock mode: Creating mock GitHub/GitLab issue[/yellow]")

    # Initialize mock services
    mock_claude = MockClaudeCode()

    # Generate a mock issue number and create it in the mock store
    import random
    mock_issue_number = random.randint(100, 999)
    mock_issue_key = f"#{mock_issue_number}"

    # Construct full issue key (e.g., "owner/repo#123")
    repo_owner_repo = repository or "mock-owner/mock-repo"
    full_issue_key = f"{repo_owner_repo}{mock_issue_key}"  # Concatenate repo and #123

    # Create the mock issue in the data store so it can be retrieved later
    from devflow.mocks.persistence import MockDataStore
    store = MockDataStore()

    # Generate mock issue summary and description
    summary = goal[:100]
    description = f"Mock issue created for: {goal}"

    mock_issue = {
        "key": full_issue_key,
        "summary": summary,
        "description": description,
        "type": issue_type or "task",
        "status": "open",
        "project": repository or "mock-repo",
        "assignee": None,
        "reporter": "mock-user",
        "priority": None,
        "labels": [issue_type] if issue_type else [],
        "epic": None,
        "sprint": None,
        "points": None,
        "acceptance_criteria": None,
    }
    store.set_jira_ticket(full_issue_key, mock_issue)

    # Build initial prompt with session name
    from devflow.cli.utils import get_workspace_path
    workspace_path = None
    if session.workspace_name and config and config.repos:
        workspace_path = get_workspace_path(config, session.workspace_name)
    elif config and config.repos and config.repos.workspaces:
        workspace_path = config.repos.get_default_workspace_path()
    initial_prompt = _build_issue_creation_prompt(issue_type, goal, config, name, project_path=project_path, workspace=workspace_path, parent=parent, repository=repository)

    # Create mock Claude session with initial prompt
    ai_agent_session_id = mock_claude.create_session(
        project_path=project_path,
        initial_prompt=initial_prompt
    )

    # Simulate assistant message acknowledging issue creation
    type_info = f"Type: {issue_type}\nLabels: {issue_type}" if issue_type else "No type label"
    mock_claude.add_message(
        session_id=ai_agent_session_id,
        role="assistant",
        content=f"I've created mock GitHub issue {full_issue_key} with the following details:\n\n"
                f"Summary: {summary}\n"
                f"{type_info}"
    )

    # Update session with Claude session ID
    working_dir_name = Path(project_path).name

    # Get current branch (or None if not a git repo)
    current_branch = GitUtils.get_current_branch(Path(project_path)) if GitUtils.is_git_repository(Path(project_path)) else None

    session.add_conversation(
        working_dir=working_dir_name,
        ai_agent_session_id=ai_agent_session_id,
        project_path=project_path,
        branch=current_branch,
    )
    session.working_directory = working_dir_name

    session_manager.update_session(session)

    # Auto-rename session to creation-<base_name>
    # For GitHub, use format like "creation-owner-repo-123"
    base_name = issue_key_to_session_name(full_issue_key)
    new_name = f"creation-{base_name}"
    try:
        session_manager.rename_session(name, new_name)
        renamed_session = session_manager.get_session(new_name)
        if renamed_session and renamed_session.name == new_name:
            # Set GitHub metadata on renamed session
            renamed_session.issue_key = full_issue_key
            renamed_session.issue_tracker = "github"  # or "gitlab" based on detection
            if not renamed_session.issue_metadata:
                renamed_session.issue_metadata = {}
            renamed_session.issue_metadata["summary"] = summary
            if issue_type:
                renamed_session.issue_metadata["type"] = issue_type
            renamed_session.issue_metadata["status"] = "open"
            session_manager.update_session(renamed_session)

            console_print(f"[green]✓[/green] Created mock GitHub issue: [bold]{full_issue_key}[/bold]")
            console_print(f"[green]✓[/green] Renamed session to: [bold]{new_name}[/bold]")
        else:
            console_print(f"[green]✓[/green] Created mock GitHub issue: [bold]{full_issue_key}[/bold]")
            console_print(f"[yellow]⚠[/yellow] Session rename may have failed")
            console_print(f"   Expected: [bold]{new_name}[/bold]")
            console_print(f"   Actual: [bold]{name}[/bold]")
            new_name = name
    except ValueError as e:
        console_print(f"[green]✓[/green] Created mock GitHub issue: [bold]{full_issue_key}[/bold]")
        console_print(f"[yellow]⚠[/yellow] Could not rename session: {e}")
        console_print(f"   Session name: [bold]{name}[/bold]")
        new_name = name

    console_print(f"[dim]Summary: {summary}[/dim]")
    if issue_type:
        console_print(f"[dim]Type: {issue_type}[/dim]")
    console_print(f"[dim]Status: open[/dim]")
    console_print()
    console_print(f"[dim]View with: daf git view {full_issue_key}[/dim]")
    console_print(f"[dim]Reopen session with: daf open {new_name}[/dim]")
    console_print()

    return full_issue_key


@require_outside_claude
def create_git_issue_session(
    goal: str,
    issue_type: Optional[str] = None,
    name: Optional[str] = None,
    path: Optional[str] = None,
    branch: Optional[str] = None,
    parent: Optional[str] = None,
    workspace: Optional[str] = None,
    repository: Optional[str] = None,
) -> None:
    """Create a new session for GitHub/GitLab issue creation.

    This creates a session with session_type="ticket_creation" which:
    - Skips branch creation automatically
    - Includes analysis-only instructions in the initial prompt
    - Persists the session type for reopening

    Args:
        goal: Goal/description for the issue
        issue_type: Optional type of issue (bug, enhancement, task). If not provided, no type label is added
        name: Optional session name (auto-generated from goal if not provided)
        path: Optional project path (bypasses interactive selection if provided)
        branch: Optional git branch name
        parent: Optional parent issue key (owner/repo#123 or #123)
        workspace: Optional workspace name (overrides session default and config default)
        repository: Optional repository in owner/repo format
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

    # Validate issue_type if provided
    from devflow.github.field_mapper import GitHubFieldMapper

    if issue_type:
        # Check if validation is configured
        if config.github and config.github.issue_types is not None:
            # Explicit list provided - validate against it
            valid_types = config.github.issue_types
            issue_type_lower = issue_type.lower()
            valid_types_lower = [t.lower() for t in valid_types]

            if issue_type_lower not in valid_types_lower:
                console_print(f"[red]✗[/red] Invalid issue type '{issue_type}'.")
                console_print(f"[yellow]Valid types:[/yellow] {', '.join(valid_types)}")
                console_print()
                console_print("[dim]Configure valid types in enterprise.json or organization.json:[/dim]")
                console_print(f'[dim]  "github_issue_types": {valid_types}[/dim]')
                if is_json_mode():
                    output_json(
                        success=False,
                        error={
                            "message": f"Invalid issue type '{issue_type}'",
                            "code": "INVALID_ISSUE_TYPE",
                            "valid_types": valid_types
                        }
                    )
                return

            # Normalize to configured case
            for vt in valid_types:
                if vt.lower() == issue_type_lower:
                    issue_type = vt
                    break
        elif config.github and config.github.issue_types is None:
            # Explicitly set to null - issue types disabled
            console_print("[red]✗[/red] Issue types are disabled in configuration.")
            console_print("Set [cyan]github_issue_types[/cyan] to a list to enable type validation,")
            console_print("or omit the TYPE parameter to create issues without types.")
            if is_json_mode():
                output_json(
                    success=False,
                    error={
                        "message": "Issue types are disabled in configuration",
                        "code": "ISSUE_TYPES_DISABLED"
                    }
                )
            return
        else:
            # No config - use field mapper defaults
            valid_types = list(GitHubFieldMapper.ISSUE_TYPES.values())

            issue_type_lower = issue_type.lower()
            valid_types_lower = [t.lower() for t in valid_types]

            if issue_type_lower not in valid_types_lower:
                console_print(f"[red]✗[/red] Invalid issue type '{issue_type}'.")
                console_print(f"[yellow]Valid types:[/yellow] {', '.join(valid_types)}")
                console_print()
                console_print("[dim]Configure valid types in enterprise.json or organization.json:[/dim]")
                console_print(f'[dim]  "github_issue_types": {valid_types}[/dim]')
                if is_json_mode():
                    output_json(
                        success=False,
                        error={
                            "message": f"Invalid issue type '{issue_type}'",
                            "code": "INVALID_ISSUE_TYPE",
                            "valid_types": valid_types
                        }
                    )
                return

            # Normalize to field mapper case
            for vt in valid_types:
                if vt.lower() == issue_type_lower:
                    issue_type = vt
                    break

    # Validate parent issue exists if provided
    if parent:
        from devflow.issue_tracker.factory import create_issue_tracker_client
        from devflow.utils.git_remote import GitRemoteDetector
        from devflow.issue_tracker.exceptions import IssueTrackerNotFoundError, IssueTrackerValidationError as ValidationError

        console_print(f"\n[cyan]Validating parent issue {parent}...[/cyan]")
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

            # Create appropriate client
            client = create_issue_tracker_client(backend=backend, hostname=hostname)

            # Set repository if we have one
            if repository and hasattr(client, 'repository'):
                client.repository = repository

            parent_issue = client.get_ticket(parent)
            if not parent_issue:
                console_print(f"[red]✗[/red] Parent issue {parent} not found")
                if is_json_mode():
                    output_json(success=False, error={"message": f"Parent issue {parent} not found", "code": "PARENT_NOT_FOUND"})
                return
            console_print(f"[dim]Parent issue found: {parent_issue.get('summary', 'N/A')}[/dim]")
        except ValidationError as e:
            console_print(f"[red]✗[/red] Invalid parent issue key format: {parent}")
            console_print(f"[dim]Expected '#123' or 'owner/repo#123'[/dim]")
            if is_json_mode():
                output_json(success=False, error={"message": str(e), "code": "INVALID_PARENT_FORMAT"})
            return
        except IssueTrackerNotFoundError:
            console_print(f"[red]✗[/red] Parent issue {parent} not found")
            if is_json_mode():
                output_json(success=False, error={"message": f"Parent issue {parent} not found", "code": "PARENT_NOT_FOUND"})
            return
        except Exception as e:
            console_print(f"[yellow]⚠[/yellow] Could not validate parent issue: {e}")
            console_print(f"[dim]Continuing anyway...[/dim]")

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
        # Prompt for repository selection from workspace with multi-project support (Issue #179)
        from devflow.cli.utils import prompt_repository_selection_with_multiproject
        project_paths, selected_workspace_name = prompt_repository_selection_with_multiproject(
            config,
            workspace_flag=workspace,
            allow_multiple=True  # Enable multi-project mode for git new
        )
        if not project_paths:
            # User cancelled or no workspace configured
            return

        # Check if multi-project mode was selected
        if len(project_paths) > 1:
            # Multi-project ticket creation session - need to select target repository
            target_repo_path = _prompt_for_target_repository(project_paths, repository)
            if not target_repo_path:
                console_print("[yellow]Cancelled[/yellow]")
                return

            # Multi-project issue creation session
            return _create_multi_project_git_session(
                config=config,
                config_loader=config_loader,
                name=name,
                goal=goal,
                issue_type=issue_type,
                parent=parent,
                project_paths=project_paths,
                target_repo_path=target_repo_path,
                workspace=workspace,
                selected_workspace_name=selected_workspace_name,
                repository=repository,
            )

        # Single project mode - use first (and only) path
        project_path = project_paths[0]

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
                working_directory = Path(original_project_path).name
                console_print(f"[green]✓[/green] Using temporary clone: {temp_directory}")
            else:
                console_print(f"[dim]User declined temp clone or cloning failed - using current directory[/dim]")

    # Build the goal string that includes the issue creation task
    full_goal = f"Create GitHub/GitLab issue: {goal}" if not issue_type else f"Create GitHub/GitLab {issue_type}: {goal}"

    # Create session with session_type="ticket_creation"
    session_manager = SessionManager(config_loader=config_loader)

    session = session_manager.create_session(
        name=name,
        goal=full_goal,
        working_directory=working_directory,
        project_path=project_path,
        branch=branch,
    )

    # Set session_type to "ticket_creation"
    session.session_type = "ticket_creation"

    # Set issue tracker backend (github or gitlab)
    # Detect from repository remote URL
    from devflow.utils.git_remote import GitRemoteDetector
    detector = GitRemoteDetector(project_path)
    repo_info = detector.parse_repository_info()

    if repo_info:
        backend = repo_info[0]  # 'github' or 'gitlab'
        session.issue_tracker = backend
    else:
        # Fallback to github if can't detect
        session.issue_tracker = "github"

    # Store selected workspace in session
    if selected_workspace_name:
        session.workspace_name = selected_workspace_name

    session_manager.update_session(session)

    console_print(f"\n[green]✓[/green] Created session [cyan]{name}[/cyan] (session_type: [yellow]ticket_creation[/yellow])")
    console_print(f"[dim]Goal: {full_goal}[/dim]")
    console_print(f"[dim]Working directory: {working_directory}[/dim]")
    console_print(f"[dim]No branch will be created (analysis-only mode)[/dim]\n")

    # In mock mode, create mock issue instead of launching Claude
    if is_mock_mode():
        issue_key = _create_mock_git_issue(
            session=session,
            session_manager=session_manager,
            name=name,
            issue_type=issue_type,
            goal=goal,
            config=config,
            project_path=project_path,
            parent=parent,
            repository=repository,
        )

        # Output JSON if in JSON mode
        if is_json_mode():
            from devflow.cli.utils import serialize_session
            issue_num = issue_key.lstrip('#')
            renamed_session_name = f"creation-{issue_num}"
            renamed_session = session_manager.get_session(renamed_session_name)
            if renamed_session is None:
                renamed_session = session
                renamed_session_name = name
            output_json(
                success=True,
                data={
                    "issue_key": issue_key,
                    "session_name": renamed_session_name,
                    "session": serialize_session(renamed_session),
                    "issue_type": issue_type,
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
        branch=current_branch,
        temp_directory=temp_directory,
        original_project_path=original_project_path,
    )
    session.working_directory = working_directory

    # Start time tracking
    session_manager.start_work_session(name)

    session_manager.update_session(session)

    # Build initial prompt with analysis-only constraints and session metadata
    from devflow.cli.utils import get_workspace_path
    workspace_path = None
    if session.workspace_name and config and config.repos:
        workspace_path = get_workspace_path(config, session.workspace_name)
    elif config and config.repos and config.repos.workspaces:
        workspace_path = config.repos.get_default_workspace_path()
    initial_prompt = _build_issue_creation_prompt(issue_type, goal, config, name, project_path=project_path, workspace=workspace_path, parent=parent, repository=repository)

    # Note: daf-workflow skill is auto-loaded, no validation needed
    if not validate_daf_agents_md(session, config_loader):
        return

    # Set up signal handlers for cleanup
    setup_signal_handlers(session, session_manager, name, config)

    # Set CS_SESSION_NAME environment variable
    env = os.environ.copy()
    env["CS_SESSION_NAME"] = name

    # Set GCP Vertex AI region if configured
    if config and config.gcp_vertex_region:
        env["CLOUD_ML_REGION"] = config.gcp_vertex_region

    # Launch agent with the session ID and initial prompt
    try:
        # Get agent backend from config
        from devflow.agent import create_agent_client

        agent_backend = config.agent_backend if config else "claude"
        agent = create_agent_client(agent_backend)

        # Get model provider profile if configured
        from devflow.utils.model_provider import get_active_profile as get_model_profile
        model_profile = None
        if config and config.model_provider:
            model_profile = get_model_profile(config, override_profile_name=session.model_profile)

        workspace_path_for_skills = None
        if session.workspace_name and config and config.repos:
            workspace_path_for_skills = get_workspace_path(config, session.workspace_name)
        elif config and config.repos and config.repos.workspaces:
            workspace_path_for_skills = config.repos.get_default_workspace_path()

        # Debug: Print agent being executed
        console_print(f"\n[dim]Debug - Agent launch:[/dim]")
        console_print(f"[dim]  Agent backend: {agent_backend}[/dim]")
        console_print(f"[dim]  Session ID: {ai_agent_session_id}[/dim]")
        console_print(f"[dim]  Workspace path: {workspace_path_for_skills}[/dim]")
        console_print(f"[dim]  Prompt (first 100 chars): {initial_prompt[:100]}...[/dim]")
        console_print(f"[dim]  Working directory: {project_path}[/dim]")
        console_print()

        # Launch agent with initial prompt
        process = agent.launch_with_prompt(
            project_path=project_path,
            initial_prompt=initial_prompt,
            session_id=ai_agent_session_id,
            model_provider_profile=model_profile,
            skills_dirs=None,  # Will be auto-discovered
            workspace_path=workspace_path_for_skills,
            config=config
        )
        # Wait for the agent process to complete
        process.wait()
    finally:
        if not is_cleanup_done():
            console_print(f"\n[green]✓[/green] Claude session completed")

            # Reload index from disk
            session_manager.index = session_manager.config_loader.load_sessions()

            # Check if session was renamed during execution
            current_session = session_manager.get_session(name)
            actual_name = name

            if not current_session:
                # Session not found with original name - it was likely renamed
                console_print(f"[dim]Detecting renamed session...[/dim]")
                all_sessions = session_manager.list_sessions()
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
            try:
                session_manager.end_work_session(actual_name)
            except ValueError as e:
                console_print(f"[yellow]⚠[/yellow] Could not end work session: {e}")

            console_print(f"[dim]Resume anytime with: daf open {actual_name}[/dim]")

            # Save conversation file to stable location before cleaning up temp directory
            if current_session and current_session.active_conversation and current_session.active_conversation.temp_directory:
                from devflow.cli.commands.open_command import _copy_conversation_from_temp
                _copy_conversation_from_temp(current_session, current_session.active_conversation.temp_directory)

            # Clean up temporary directory if present
            if temp_directory:
                from devflow.utils.temp_directory import cleanup_temp_directory
                cleanup_temp_directory(temp_directory)

            # Check if we should run 'daf complete' on exit
            from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
            if current_session:
                _prompt_for_complete_on_exit(current_session, config)
            else:
                _prompt_for_complete_on_exit(session, config)




def _build_issue_creation_prompt(
    issue_type: Optional[str],
    goal: str,
    config,
    session_name: str,
    project_path: Optional[str] = None,
    workspace: Optional[str] = None,
    parent: Optional[str] = None,
    repository: Optional[str] = None,
) -> str:
    """Build the initial prompt for GitHub/GitLab issue creation sessions.

    Args:
        issue_type: Optional type of issue (bug, enhancement, task). If None, no type label is added
        goal: Goal/description for the issue
        config: Configuration object
        session_name: Name of the session (unused, kept for backward compatibility)
        project_path: Unused, kept for backward compatibility
        workspace: Workspace path for skill discovery
        parent: Optional parent issue key (owner/repo#123 or #123)
        repository: Optional repository in owner/repo format

    Returns:
        Initial prompt string with analysis-only instructions
    """
    # Build the "Work on" line
    work_on_line = f"Work on: Create GitHub/GitLab issue for: {goal}" if not issue_type else f"Work on: Create GitHub/GitLab {issue_type} for: {goal}"

    prompt_parts = [
        work_on_line,
        "",
    ]

    # Add context files section
    default_files = [
        ("AGENTS.md", "agent-specific instructions"),
        ("CLAUDE.md", "project guidelines and standards"),
        # Note: daf-workflow skill is auto-loaded by Claude Code
    ]

    # Load configured context files from config
    configured_files = []
    if config and config.context_files:
        configured_files = [(f.path, f.description) for f in config.context_files.files if not f.hidden]

    # Load hierarchical context files
    hierarchical_files = load_hierarchical_context_files(config)

    # Discover skills from filesystem
    skill_files = discover_skills(project_path=project_path, workspace=workspace)

    # Combine regular context files
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

    # Build example command
    example_cmd_parts = ["daf git create"]
    if issue_type:
        example_cmd_parts.append(issue_type)
    example_cmd_parts.append('--summary "..."')

    # Add parent if specified
    if parent:
        example_cmd_parts.append(f'--parent "{parent}"')

    # Add repository if specified
    if repository:
        example_cmd_parts.append(f'--repository {repository}')

    # Add optional fields based on issue type
    example_cmd_parts.append('--description "<your analysis here>"')

    # Add acceptance criteria
    example_cmd_parts.append('--acceptance-criteria "..."')

    example_command = " \\\n  ".join(example_cmd_parts)

    prompt_parts.extend([
        "⚠️  IMPORTANT CONSTRAINTS:",
        "   • This is an ANALYSIS-ONLY session for GitHub/GitLab issue creation",
        "   • DO NOT modify any code or create/checkout git branches",
        "   • DO NOT make any file changes - only READ and ANALYZE",
        "   • Focus on understanding the codebase to write a good issue",
        "",
        "Your task:",
        f"1. Analyze the codebase to understand how to implement: {goal}",
        "2. Read relevant files, search for patterns, understand the architecture",
        f"3. Create a detailed GitHub/GitLab issue{' (' + issue_type + ')' if issue_type else ''} using the 'daf git create' command",
        "4. Include detailed description and acceptance criteria based on your analysis",
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
        "After you create the issue, the session will be automatically renamed to 'creation-<issue_number>'",
        "for easy identification. Users can reopen with: daf open creation-<issue_number>",
        "",
        "Remember: This is READ-ONLY analysis. Do not modify any files.",
    ])

    return "\n".join(prompt_parts)


def _prompt_for_target_repository(project_paths: list[str], repository: Optional[str]) -> Optional[str]:
    """Prompt user to select target repository for GitHub/GitLab issue creation (Issue #179).

    Args:
        project_paths: List of selected project paths
        repository: Optional repository from command line (owner/repo format)

    Returns:
        Full path to target repository, or None if cancelled
    """
    project_names = [Path(p).name for p in project_paths]

    console.print("\n[bold]Which repository should the GitHub/GitLab issue be created in?[/bold]")
    for i, (name, path) in enumerate(zip(project_names, project_paths), 1):
        console.print(f"  {i}. {name}")

    from rich.prompt import Prompt
    selection = Prompt.ask(f"\nSelect repository (1-{len(project_paths)})")

    # Validate selection
    if selection.isdigit():
        idx = int(selection) - 1
        if 0 <= idx < len(project_paths):
            selected = project_paths[idx]
            console.print(f"[green]✓[/green] Issue will be created in: [bold]{Path(selected).name}[/bold]")
            return selected
        else:
            console.print(f"[red]✗[/red] Invalid selection: {selection}")
            return None
    else:
        # Try name matching
        for path in project_paths:
            if Path(path).name == selection:
                console.print(f"[green]✓[/green] Issue will be created in: [bold]{selection}[/bold]")
                return path
        console.print(f"[red]✗[/red] Repository not found: {selection}")
        return None


def _build_multiproject_issue_creation_prompt(
    issue_type: Optional[str],
    goal: str,
    config,
    name: str,
    project_paths: list[str],
    workspace: str,
    target_repo_path: str,
    parent: Optional[str] = None,
    repository: Optional[str] = None,
) -> str:
    """Build initial prompt for multi-project GitHub/GitLab issue creation (Issue #179).

    Args:
        issue_type: Optional issue type (bug, enhancement, task)
        goal: Goal/description
        config: Configuration object
        name: Session name
        project_paths: List of full project paths to analyze
        workspace: Workspace path
        target_repo_path: Target repository for issue creation
        parent: Optional parent issue key
        repository: Optional repository in owner/repo format

    Returns:
        Initial prompt string for Claude
    """
    project_names = [Path(p).name for p in project_paths]
    projects_list = "\n".join([f"  • {name}" for name in project_names])
    target_repo_name = Path(target_repo_path).name

    # Build example command
    example_cmd_parts = ["daf git create"]
    if issue_type:
        example_cmd_parts.append(issue_type)
    example_cmd_parts.extend([
        '--summary "..."',
        '--description "..."',
    ])
    if parent:
        example_cmd_parts.append(f'--parent "{parent}"')
    example_cmd_parts.append('--acceptance-criteria "..." --acceptance-criteria "..."')

    example_command = " \\\n  ".join(example_cmd_parts)

    prompt_parts = [
        f"Work on daf session: {name}",
        "",
        f"This is a MULTI-PROJECT issue creation session for analyzing {len(project_paths)} repositories:",
        projects_list,
        "",
        f"⚠️  Issue will be created in: {target_repo_name}",
        "",
        "⚠️  CRITICAL CONSTRAINTS:",
        "• This is a READ-ONLY analysis session",
        "• Do NOT modify any code or files in any project",
        "• Do NOT create git commits or checkout branches",
        "• ONLY analyze the codebases to inform issue creation",
        "",
        f"Your task: Analyze all {len(project_paths)} projects and create a comprehensive GitHub/GitLab issue{' (' + issue_type + ')' if issue_type else ''}",
        "",
        f"User's goal: {goal}",
        "",
        "Steps to complete this task:",
        f"1. Analyze ALL {len(project_paths)} projects to understand:",
        "   • Current architecture and implementation across projects",
        "   • How the projects interact (APIs, shared code, dependencies)",
        "   • Relevant code patterns and conventions",
        "   • Potential impact areas in each project",
        "2. Identify what needs to be implemented/fixed across all projects",
        "3. Determine clear, testable acceptance criteria considering all projects",
        f"4. Create the GitHub/GitLab issue in {target_repo_name} with your cross-project analysis",
        "",
        "⚠️  CRITICAL: Use EXACTLY this command format (do not modify syntax):",
        "",
        example_command,
        "",
        "⚠️  The command above is the EXACT format you MUST use. Do not attempt alternative formats.",
        "   Use this template precisely, filling in your cross-project analysis and findings.",
        "",
        "After you create the issue, the session will be automatically renamed to 'creation-<issue_number>'",
        "for easy identification. Users can reopen with: daf open creation-<issue_number>",
        "",
        f"Remember: This is READ-ONLY analysis across {len(project_paths)} projects. Do not modify any files.",
    ]

    return "\n".join(prompt_parts)


def _create_multi_project_git_session(
    config,
    config_loader,
    name: str,
    goal: str,
    issue_type: Optional[str],
    parent: Optional[str],
    project_paths: list[str],
    target_repo_path: str,
    workspace: Optional[str],
    selected_workspace_name: str,
    repository: Optional[str] = None,
) -> None:
    """Create a multi-project ticket creation session for GitHub/GitLab (Issue #179).

    Args:
        config: Configuration object
        config_loader: ConfigLoader instance
        name: Session name
        goal: Session goal
        issue_type: Optional issue type (bug, enhancement, task)
        parent: Optional parent issue key
        project_paths: List of full paths to selected projects
        target_repo_path: Target repository for issue creation
        workspace: Workspace flag
        selected_workspace_name: Selected workspace name
        repository: Optional repository in owner/repo format
    """
    from devflow.cli.commands.ticket_creation_multiproject import create_multi_project_ticket_creation_session
    from devflow.cli.utils import get_workspace_path
    from devflow.session.manager import SessionManager

    # Build the goal string that includes the issue creation task
    full_goal = f"Create GitHub/GitLab issue: {goal}" if not issue_type else f"Create GitHub/GitLab {issue_type}: {goal}"

    # Get workspace path
    workspace_path = get_workspace_path(config, selected_workspace_name)
    if not workspace_path:
        console_print(f"[red]✗[/red] Could not find workspace path")
        return

    # Create session manager
    session_manager = SessionManager(config_loader=config_loader)

    # Create multi-project ticket creation session
    session, ai_agent_session_id = create_multi_project_ticket_creation_session(
        session_manager=session_manager,
        config=config,
        name=name,
        goal=full_goal,
        project_paths=project_paths,
        workspace_path=workspace_path,
        selected_workspace_name=selected_workspace_name,
        session_type="ticket_creation",
        issue_type=issue_type,
    )

    # Set issue tracker backend (github or gitlab) from target repository
    from devflow.utils.git_remote import GitRemoteDetector
    detector = GitRemoteDetector(target_repo_path)
    repo_info = detector.parse_repository_info()

    if repo_info:
        backend = repo_info[0]  # 'github' or 'gitlab'
        session.issue_tracker = backend
    else:
        # Fallback to github if can't detect
        session.issue_tracker = "github"

    session_manager.update_session(session)

    # Check if we should launch Claude Code
    if not should_launch_claude_code(config=config, mock_mode=False):
        console_print("[yellow]⚠[/yellow] Session created but Claude Code not launched.")
        console_print(f"  Run [cyan]daf open {name}[/cyan] to start working on it.")
        return

    # Build initial prompt for multi-project issue creation
    initial_prompt = _build_multiproject_issue_creation_prompt(
        issue_type=issue_type,
        goal=goal,
        config=config,
        name=name,
        project_paths=project_paths,
        workspace=workspace_path,
        target_repo_path=target_repo_path,
        parent=parent,
        repository=repository,
    )

    # Launch Claude Code
    from devflow.claude_code.launcher import launch_claude_code
    from devflow.cli.utils import handle_claude_code_launch_failure

    # Use the first project as the primary working directory for Claude Code
    primary_project_path = project_paths[0]

    success = launch_claude_code(
        project_path=primary_project_path,
        initial_prompt=initial_prompt,
        ai_agent_session_id=ai_agent_session_id,
        config=config
    )

    if not success:
        handle_claude_code_launch_failure(session, session_manager, name)


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
        workspace_flag=workspace_flag,
        session=None,
        skip_prompt=False
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
