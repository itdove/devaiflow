"""Command for daf investigate - create investigation-only session without ticket creation."""

import os
import re
import signal
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm

from devflow.agent import get_agent_display_name
from devflow.agent.factory import resolve_agent_backend
from devflow.cli.utils import console_print, get_workspace_path, is_json_mode, output_json, require_outside_claude, resolve_workspace_path, scan_workspace_repositories, select_workspace, should_launch_claude_code, unified_project_selection
from devflow.git.utils import GitUtils
from devflow.utils.backend_detection import detect_backend_from_key
from devflow.issue_tracker.factory import create_issue_tracker_client
from devflow.issue_tracker.exceptions import IssueTrackerNotFoundError, IssueTrackerAuthError, IssueTrackerApiError
from devflow.utils.git_remote import GitRemoteDetector

# Import unified utilities
from devflow.cli.signal_handler import setup_signal_handlers, is_cleanup_done
from devflow.cli.skills_discovery import discover_skills
from devflow.utils.context_files import load_hierarchical_context_files
from devflow.utils.daf_agents_validation import validate_daf_agents_md

console = Console()


@require_outside_claude
def create_investigation_from_issue(
    issue_key: str,
    goal_override: Optional[str] = None,
    parent: Optional[str] = None,
    name: Optional[str] = None,
    path: Optional[str] = None,
    workspace: Optional[str] = None,
    model_profile: Optional[str] = None,
    projects: Optional[str] = None,
    temp_clone: Optional[bool] = None,
    agent: Optional[str] = None,
) -> None:
    """Create investigation session from an existing issue tracker ticket.

    This function fetches the issue details and creates an investigation session
    with the issue summary as the goal.

    Args:
        issue_key: Issue identifier (PROJ-12345, owner/repo#123, #123)
        goal_override: Optional goal to override issue summary
        parent: Optional parent issue key (for tracking investigation under an epic)
        name: Optional session name (auto-generated from issue key if not provided)
        path: Optional project path (bypasses interactive selection if provided)
        workspace: Optional workspace name (overrides session default and config default)
        model_profile: Optional model provider profile to use
        projects: Optional comma-separated list of project names for multi-project mode
        temp_clone: Whether to clone to temp directory (None = prompt, True = clone, False = no clone)
    """
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console_print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        if is_json_mode():
            output_json(success=False, error={"message": "No configuration found", "code": "NO_CONFIG"})
        sys.exit(1)

    console_print(f"[dim]Fetching issue details for: {issue_key}[/dim]")

    # Detect backend from issue key format
    backend = detect_backend_from_key(issue_key, config)
    console_print(f"[dim]Detected backend: {backend}[/dim]")

    # Fetch issue details
    try:
        if backend == "jira":
            # JIRA backend
            from devflow.jira import JiraClient
            client = JiraClient()
            issue = client.get_ticket(issue_key)
            issue_summary = issue.get("summary", "")
            issue_description = issue.get("description", "")

        else:
            # GitHub/GitLab backend
            detector = GitRemoteDetector()
            platform_info = detector.parse_repository_info()
            hostname = detector.get_hostname()

            if platform_info:
                platform, owner, repo_name = platform_info
                actual_backend = "gitlab" if platform == "gitlab" else "github"
                repository = f"{owner}/{repo_name}"
            else:
                # Default to GitHub if can't detect
                actual_backend = "github"
                repository = None

            # Create appropriate client
            client = create_issue_tracker_client(backend=actual_backend, hostname=hostname)

            # Set repository if we have one
            if repository and hasattr(client, 'repository'):
                client.repository = repository

            # Fetch issue
            issue = client.get_ticket(issue_key)
            issue_summary = issue.get("title", "") or issue.get("summary", "")
            issue_description = issue.get("body", "") or issue.get("description", "")

        console_print(f"[green]✓[/green] Fetched issue: {issue_summary}")

    except IssueTrackerNotFoundError:
        console_print(f"[red]✗[/red] Issue not found: {issue_key}")
        if is_json_mode():
            output_json(success=False, error={"message": f"Issue not found: {issue_key}", "code": "ISSUE_NOT_FOUND"})
        sys.exit(1)
    except IssueTrackerAuthError as e:
        console_print(f"[red]✗[/red] Authentication failed: {e}")
        if is_json_mode():
            output_json(success=False, error={"message": str(e), "code": "AUTH_ERROR"})
        sys.exit(1)
    except IssueTrackerApiError as e:
        console_print(f"[red]✗[/red] API error: {e}")
        if is_json_mode():
            output_json(success=False, error={"message": str(e), "code": "API_ERROR"})
        sys.exit(1)
    except Exception as e:
        console_print(f"[red]✗[/red] Failed to fetch issue: {e}")
        if is_json_mode():
            output_json(success=False, error={"message": str(e), "code": "FETCH_ERROR"})
        sys.exit(1)

    # Use goal override if provided, otherwise use issue summary
    goal = goal_override if goal_override else issue_summary

    # Auto-generate session name from issue key if not provided
    if not name:
        sanitized_key = issue_key.replace('#', 'issue-')
        sanitized_key = re.sub(r'[^a-zA-Z0-9_\-]', '-', sanitized_key)
        name = f"investigate-{sanitized_key}"
        console_print(f"[dim]Auto-generated session name: {name}[/dim]")

    # Create investigation session with fetched details
    create_investigation_session(
        goal=goal,
        parent=parent or issue_key,  # Track under the issue if no parent provided
        name=name,
        path=path,
        workspace=workspace,
        model_profile=model_profile,
        projects=projects,
        temp_clone=temp_clone,
        issue_key=issue_key,
        issue_details={"summary": issue_summary, "description": issue_description},
        agent=agent,
    )


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

    # Limit length to 43 chars to leave room for random suffix
    if len(slug) > 43:
        slug = slug[:43].rstrip('-')

    # Add 6-character random suffix to prevent collisions
    random_suffix = secrets.token_hex(3)
    slug = f"{slug}-{random_suffix}"

    return slug


def _select_from_workspace_repos(
    config,
    config_loader,
    workspace_flag: Optional[str],
    name: str,
    goal: str,
    parent: Optional[str],
    model_profile: Optional[str],
    agent: Optional[str] = None,
):
    """Select project(s) from workspace repositories.

    This is the existing workspace selection flow extracted into a helper.

    Returns:
        Tuple of (project_path, selected_workspace_name) for single project,
        or calls _create_multi_project_investigation_session and returns
        ("multi_project_handled",) sentinel for multi-project.
        Returns None if selection was cancelled or failed.
    """
    selected_workspace_name = select_workspace(
        config,
        workspace_flag=workspace_flag,
        session=None,
        skip_prompt=is_json_mode(),
    )

    if not selected_workspace_name:
        console_print("[yellow]⚠[/yellow] No workspace selected")
        if is_json_mode():
            output_json(success=False, error={"message": "No workspace selected", "code": "NO_WORKSPACE"})
        return None

    ws_path = get_workspace_path(config, selected_workspace_name)
    if not ws_path:
        console_print(f"[yellow]⚠[/yellow] Could not find workspace path for: {selected_workspace_name}")
        if is_json_mode():
            output_json(success=False, error={"message": f"Workspace path not found: {selected_workspace_name}", "code": "NO_WORKSPACE"})
        return None

    console_print(f"[dim]Scanning workspace: {ws_path}[/dim]")
    try:
        repo_options = scan_workspace_repositories(ws_path)
    except (ValueError, RuntimeError) as e:
        console_print(f"[yellow]Warning: {e}[/yellow]")
        repo_options = []

    if not repo_options:
        console_print("[yellow]⚠[/yellow] No git repositories found in workspace")
        if is_json_mode():
            output_json(success=False, error={"message": "No repositories found", "code": "NO_REPOSITORY"})
        return None

    project_paths_result, is_multi = unified_project_selection(
        workspace_path=ws_path,
        repo_options=repo_options,
        allow_multi_project=True,
        config_loader=config_loader,
        workspace_name=selected_workspace_name,
    )
    if not project_paths_result:
        if is_json_mode():
            output_json(success=False, error={"message": "Repository selection cancelled or failed", "code": "NO_REPOSITORY"})
        return None

    if is_multi:
        _create_multi_project_investigation_session(
            config=config,
            config_loader=config_loader,
            name=name,
            goal=goal,
            parent=parent,
            project_paths=project_paths_result,
            workspace=workspace_flag,
            selected_workspace_name=selected_workspace_name,
            model_profile=model_profile,
            agent=agent,
        )
        return ("multi_project_handled",)

    return (project_paths_result[0], selected_workspace_name)


def _prompt_investigation_location(config, config_loader, name, goal, parent, model_profile, agent=None):
    """Prompt user for investigation location when no path/workspace specified.

    Presents 4 options:
      1. Current directory
      2. Empty temporary directory
      3. Specify a custom path
      4. Select from workspace repositories

    In mock/JSON mode, defaults to current directory without prompting.

    Returns:
        Tuple of (project_path, selected_workspace_name, temp_directory, original_project_path)
        or ("multi_project_handled",) sentinel if multi-project was created.
        Returns None if selection was cancelled or failed.
    """
    from devflow.utils.paths import is_mock_mode

    mock_mode = is_mock_mode()
    is_json = is_json_mode()

    if mock_mode or is_json:
        cwd = os.getcwd()
        console_print(f"[dim]Non-interactive mode - using current directory: {cwd}[/dim]")
        return (cwd, None, None, None)

    cwd = os.getcwd()
    console_print("\nWhere would you like to run this investigation?\n")
    console_print(f"  1. Current directory ({cwd})")
    console_print("  2. Empty temporary directory (auto-cleaned on session exit)")
    console_print("  3. Specify a custom path")
    console_print("  4. Select from workspace repositories")
    console_print()

    choice = Prompt.ask("Selection", default="1")

    if choice == "1":
        console_print(f"[dim]Using current directory: {cwd}[/dim]")
        return (cwd, None, None, None)

    elif choice == "2":
        from devflow.utils.temp_directory import create_empty_temp_directory
        temp_dir = create_empty_temp_directory()
        if temp_dir:
            console_print(f"[green]✓[/green] Created temporary directory: {temp_dir}")
            return (temp_dir, None, temp_dir, None)
        else:
            console_print("[red]✗[/red] Failed to create temporary directory")
            return None

    elif choice == "3":
        custom_path = Prompt.ask("Enter path")
        abs_path = str(Path(custom_path).expanduser().absolute())
        if not Path(abs_path).exists():
            console_print(f"[yellow]⚠[/yellow] Directory does not exist: {abs_path}")
            if Confirm.ask("Create this directory?", default=True):
                Path(abs_path).mkdir(parents=True, exist_ok=True)
                console_print(f"[green]✓[/green] Created directory: {abs_path}")
            else:
                return None
        console_print(f"[dim]Using custom path: {abs_path}[/dim]")
        return (abs_path, None, None, None)

    elif choice == "4":
        result = _select_from_workspace_repos(
            config, config_loader, None, name, goal, parent, model_profile, agent=agent,
        )
        if result is None:
            return None
        if len(result) == 1 and result[0] == "multi_project_handled":
            return result
        project_path, ws_name = result
        return (project_path, ws_name, None, None)

    else:
        console_print(f"[red]✗[/red] Invalid selection: {choice}")
        return None


@require_outside_claude
def create_investigation_session(
    goal: str,
    parent: Optional[str] = None,
    name: Optional[str] = None,
    path: Optional[str] = None,
    workspace: Optional[str] = None,
    model_profile: Optional[str] = None,
    projects: Optional[str] = None,
    temp_clone: Optional[bool] = None,
    issue_key: Optional[str] = None,
    issue_details: Optional[dict] = None,
    headless: bool = False,
    auto_approve: bool = False,
    agent: Optional[str] = None,
) -> None:
    """Create a new investigation session for codebase analysis.

    This creates a session with session_type="investigation" which:
    - Skips branch creation automatically
    - Includes analysis-only instructions in the initial prompt
    - Does NOT expect ticket creation
    - Generates investigation report instead

    Args:
        goal: Goal/description for the investigation
        parent: Optional parent issue key (for tracking investigation under an epic)
        name: Optional session name (auto-generated from goal if not provided)
        path: Optional project path (bypasses interactive selection if provided)
        workspace: Optional workspace name (overrides session default and config default)
        model_profile: Optional model provider profile to use (e.g., "vertex", "llama-cpp")
        projects: Optional comma-separated list of project names for multi-project mode
        temp_clone: Whether to clone to temp directory (None = prompt, True = clone, False = no clone)
        issue_key: Optional issue key (for sessions created from issues)
        issue_details: Optional issue details dict with 'summary' and 'description' keys
    """
    from devflow.session.manager import SessionManager
    from devflow.config.loader import ConfigLoader

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console_print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        if is_json_mode():
            output_json(success=False, error={"message": "No configuration found", "code": "NO_CONFIG"})
        sys.exit(1)

    # Validate parent ticket if provided (for tracking purposes)
    from devflow.utils import is_mock_mode
    if parent and not is_mock_mode():
        console_print(f"[dim]Validating parent ticket: {parent}[/dim]")
        from devflow.jira.utils import validate_jira_ticket
        from devflow.jira import JiraClient

        try:
            jira_client = JiraClient()
            parent_ticket = validate_jira_ticket(parent, client=jira_client)

            if not parent_ticket:
                console_print(f"[red]✗[/red] Cannot proceed with invalid parent ticket")
                if is_json_mode():
                    output_json(
                        success=False,
                        error={
                            "code": "INVALID_PARENT",
                            "message": f"Parent ticket {parent} not found or validation failed"
                        }
                    )
                sys.exit(1)
        except Exception as e:
            console_print(f"[red]✗[/red] Failed to validate parent ticket: {e}")
            if is_json_mode():
                output_json(success=False, error={"message": f"Parent validation failed: {e}", "code": "VALIDATION_ERROR"})
            sys.exit(1)

        console_print(f"[green]✓[/green] Parent ticket validated: {parent}")

    # Auto-generate session name from goal if not provided
    if not name:
        name = slugify_goal(goal)
        console_print(f"[dim]Auto-generated session name: {name}[/dim]")

    # Determine project path
    selected_workspace_name = None
    loc_temp_directory = None
    loc_original_path = None
    if projects and workspace:
        # Multi-project mode via --projects flag
        # Parse project names
        project_names = [p.strip() for p in projects.split(',')]

        # Get workspace path
        workspace_path = get_workspace_path(config, workspace)
        if not workspace_path:
            console_print(f"[red]✗[/red] Workspace '{workspace}' not found")
            if is_json_mode():
                output_json(success=False, error={"message": f"Workspace '{workspace}' not found", "code": "INVALID_WORKSPACE"})
            sys.exit(1)

        # Build full paths for each project
        project_paths = []
        workspace_path_obj = Path(workspace_path)
        for proj_name in project_names:
            proj_path = workspace_path_obj / proj_name
            if not proj_path.exists():
                console_print(f"[red]✗[/red] Project not found: {proj_path}")
                if is_json_mode():
                    output_json(success=False, error={"message": f"Project not found: {proj_path}", "code": "INVALID_PROJECT"})
                sys.exit(1)
            project_paths.append(str(proj_path))

        console_print(f"[dim]Using {len(project_paths)} projects from workspace: {workspace}[/dim]")
        selected_workspace_name = workspace

        # Multi-project investigation session
        return _create_multi_project_investigation_session(
            config=config,
            config_loader=config_loader,
            name=name,
            goal=goal,
            parent=parent,
            project_paths=project_paths,
            workspace=workspace,
            selected_workspace_name=selected_workspace_name,
            model_profile=model_profile,
            agent=agent,
        )
    elif path is not None:
        # Use provided path
        project_path = str(Path(path).absolute())
        # Validate path exists
        if not Path(project_path).exists():
            console_print(f"[red]✗[/red] Directory does not exist: {project_path}")
            if is_json_mode():
                output_json(success=False, error={"message": f"Directory does not exist: {project_path}", "code": "INVALID_PATH"})
            sys.exit(1)
        console_print(f"[dim]Using specified path: {project_path}[/dim]")
    elif workspace:
        # --workspace provided without --projects: go to workspace repo selection
        result = _select_from_workspace_repos(
            config, config_loader, workspace, name, goal, parent, model_profile, agent=agent,
        )
        if result is None:
            sys.exit(1)
        if len(result) == 1 and result[0] == "multi_project_handled":
            return
        project_path, selected_workspace_name = result
    else:
        # No --path, --projects, or --workspace: ask user where to work
        result = _prompt_investigation_location(
            config, config_loader, name, goal, parent, model_profile, agent=agent,
        )
        if result is None:
            if is_json_mode():
                output_json(success=False, error={"message": "Location selection cancelled", "code": "NO_LOCATION"})
            sys.exit(1)
        if len(result) == 1 and result[0] == "multi_project_handled":
            return
        project_path, selected_workspace_name, loc_temp_directory, loc_original_path = result

    # For empty temp directories (no project), use session name as working_directory
    temp_directory = None
    original_project_path = None
    if loc_temp_directory:
        temp_directory = loc_temp_directory
        original_project_path = loc_original_path
        working_directory = name
    else:
        working_directory = Path(project_path).name
    mock_mode = is_mock_mode()
    is_json = is_json_mode()

    # Handle temp_clone parameter (skip if we already have a temp dir from location prompt)
    if temp_directory:
        console_print(f"[dim]Using temporary directory from location selection[/dim]")
    elif temp_clone is False:
        # --no-temp-clone flag: explicitly skip temp cloning
        console_print(f"[dim]Skipping temp directory clone (--no-temp-clone flag set)[/dim]")
    elif temp_clone is True:
        # --temp-clone flag: explicitly request temp cloning
        from devflow.utils.temp_directory import should_clone_to_temp, clone_to_temp_directory
        if should_clone_to_temp(Path(project_path)):
            console_print(f"[dim]Cloning to temp directory (--temp-clone flag set)[/dim]")
            temp_dir_result = clone_to_temp_directory(Path(project_path))
            if temp_dir_result:
                temp_directory, original_project_path = temp_dir_result
                # Use temp directory as project_path for this session
                project_path = temp_directory
                # Use the original repository name for working_directory
                working_directory = Path(original_project_path).name
                console_print(f"[green]✓[/green] Using temporary clone: {temp_directory}")
            else:
                console_print(f"[red]✗[/red] Failed to clone to temp directory - using current directory")
        else:
            console_print(f"[dim]Skipping temp clone (not a git repository)[/dim]")
    elif mock_mode or is_json:
        # Non-interactive mode: skip temp directory prompt
        console_print(f"[dim]Non-interactive mode - skipping temp directory clone prompt[/dim]")
    else:
        # No flag provided: prompt user
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

    # Build the goal string for investigation
    if issue_key:
        # Session created from issue - include issue key in goal
        full_goal = f"Investigate {issue_key}: {goal}"
    elif parent:
        full_goal = f"Investigate (under {parent}): {goal}"
    else:
        full_goal = f"Investigate: {goal}"

    # Create session with session_type="investigation"
    session_manager = SessionManager(config_loader=config_loader)

    session = session_manager.create_session(
        name=name,
        goal=full_goal,
        working_directory=working_directory,
        project_path=project_path,
        branch=None,  # No branch for investigation sessions
        model_profile=model_profile,
        agent_backend=resolve_agent_backend(cli_override=agent, config=config),
    )

    # Set session_type to "investigation"
    session.session_type = "investigation"
    # Set issue_key for tracking (use issue_key or parent)
    if issue_key:
        session.issue_key = issue_key
    elif parent:
        session.issue_key = parent

    # AAP-64296: Store selected workspace in session
    if selected_workspace_name:
        session.workspace_name = selected_workspace_name

    session_manager.update_session(session)

    console_print(f"\n[green]✓[/green] Created session [cyan]{name}[/cyan] (session_type: [yellow]investigation[/yellow])")
    console_print(f"[dim]Goal: {full_goal}[/dim]")
    if parent:
        console_print(f"[dim]Tracking under: {parent}[/dim]")
    console_print(f"[dim]Working directory: {working_directory}[/dim]")
    console_print(f"[dim]No branch will be created (analysis-only mode)[/dim]\n")

    # In mock mode, simulate investigation without launching Claude
    if is_mock_mode():
        console_print("[yellow]📝 Mock mode: Simulating investigation session[/yellow]")
        console_print(f"[green]✓[/green] Investigation session created: [bold]{name}[/bold]")
        console_print(f"[dim]Reopen session with: daf open {name}[/dim]")

        if is_json_mode():
            from devflow.cli.utils import serialize_session
            output_json(
                success=True,
                data={
                    "session_name": name,
                    "session": serialize_session(session),
                    "goal": goal,
                    "parent": parent
                }
            )
        return

    # Resolve agent display name for user-facing messages
    agent_backend = resolve_agent_backend(cli_override=agent, config=config)
    agent_name = get_agent_display_name(agent_backend)

    # Check if we should launch Claude Code
    if not should_launch_claude_code(config=config, mock_mode=False):
        console_print(f"[yellow]⚠[/yellow] Session created but {agent_name} not launched.")
        console_print(f"  Run [cyan]daf open {name}[/cyan] to start working on it.")
        return

    # Generate a new agent session ID (agent-aware: placeholder for self-ID backends)
    from devflow.agent.factory import generate_agent_session_id
    ai_agent_session_id = generate_agent_session_id(agent_backend)

    # Update session with Claude session ID
    current_branch = GitUtils.get_current_branch(Path(temp_directory)) if temp_directory and GitUtils.is_git_repository(Path(temp_directory)) else None

    session.add_conversation(
        working_dir=working_directory,
        ai_agent_session_id=ai_agent_session_id,
        project_path=project_path,
        branch=current_branch,
        temp_directory=temp_directory,
        original_project_path=original_project_path,
        workspace=resolve_workspace_path(config, session.workspace_name),
    )
    session.working_directory = working_directory

    # Start time tracking
    session_manager.start_work_session(name)

    session_manager.update_session(session)

    # Build initial prompt with investigation-only constraints
    # AAP-64886: Get workspace path from session instead of using default
    workspace = resolve_workspace_path(config, session.workspace_name)
    if headless:
        initial_prompt = _build_investigation_prompt(
            goal, parent, config, name,
            project_path=project_path,
            workspace=workspace,
            issue_key=issue_key,
            issue_details=issue_details
        )
    else:
        initial_prompt = "Read your daf-workflow skill and follow the Session Initialization instructions."

    # Note: daf-workflow skill is auto-loaded, no validation needed
    if not validate_daf_agents_md(session, config_loader):
        return

    # Set up signal handlers for cleanup (using unified utility)
    setup_signal_handlers(session, session_manager, name, config)

    # Get active model provider profile
    from devflow.utils.model_provider import get_active_profile, build_env_from_profile, get_profile_display_name
    model_provider_profile = get_active_profile(config, override_profile_name=session.model_profile) if config else None

    # Display which model provider is being used
    if model_provider_profile:
        provider_name = get_profile_display_name(model_provider_profile)
        console_print(f"[dim]Using model provider: {provider_name}[/dim]")

    # Build environment variables from model provider profile
    env = build_env_from_profile(model_provider_profile)

    # Set additional DevAIFlow environment variables
    env["CS_SESSION_NAME"] = name
    env["DAF_SESSION_NAME"] = name
    env["DAF_COMMAND"] = "investigate"
    env["DEVAIFLOW_IN_SESSION"] = "1"

    # Set GCP Vertex AI region if configured (deprecated - use model_provider instead)
    if config and config.gcp_vertex_region and not model_provider_profile:
        env["CLOUD_ML_REGION"] = config.gcp_vertex_region

    # Launch agent
    try:
        # Get agent backend from config
        from devflow.agent import create_agent_client

        agent_backend = resolve_agent_backend(cli_override=agent, config=config)
        agent_client = create_agent_client(agent_backend)

        # Get model provider profile if configured
        from devflow.utils.model_provider import get_active_profile as get_model_profile
        model_profile = None
        if config and config.model_provider:
            model_profile = get_model_profile(config, override_profile_name=session.model_profile)

        # AAP-64886: Get workspace path from session instead of using default
        workspace_path = resolve_workspace_path(config, session.workspace_name)

        # Debug output
        console_print(f"\n[dim]Debug - Agent launch:[/dim]")
        console_print(f"[dim]  Agent backend: {agent_backend}[/dim]")
        console_print(f"[dim]  Session ID: {ai_agent_session_id}[/dim]")
        console_print(f"[dim]  Workspace path: {workspace_path}[/dim]")
        console_print(f"[dim]  Prompt (first 100 chars): {initial_prompt[:100]}...[/dim]")
        console_print(f"[dim]  Working directory: {project_path}[/dim]")
        console_print()

        # Launch agent with snapshot/capture lifecycle
        from devflow.agent.factory import launch_and_capture
        launch_and_capture(
            agent_client, agent_backend, project_path,
            session.active_conversation,
            initial_prompt=initial_prompt,
            session_id=ai_agent_session_id,
            model_provider_profile=model_profile,
            workspace_path=workspace_path,
            config=config,
            env=env,
            headless=headless,
            auto_approve=auto_approve,
        )
    finally:
        if not is_cleanup_done():
            console_print(f"\n[green]✓[/green] {agent_name} session completed")

            # Reload index from disk
            session_manager.index = session_manager.config_loader.load_sessions()

            # Get current session
            current_session = session_manager.get_session(name)
            if not current_session:
                current_session = session

            # End work session
            try:
                session_manager.end_work_session(name)
            except ValueError as e:
                console_print(f"[yellow]⚠[/yellow] Could not end work session: {e}")

            console_print(f"[dim]Resume anytime with: daf open {name}[/dim]")

            # Save conversation file before cleanup
            if current_session and current_session.active_conversation and current_session.active_conversation.temp_directory:
                from devflow.cli.commands.open_command import _copy_conversation_from_temp
                _copy_conversation_from_temp(current_session, current_session.active_conversation.temp_directory)

            # Clean up temporary directory
            if temp_directory:
                from devflow.utils.temp_directory import cleanup_temp_directory
                cleanup_temp_directory(temp_directory)

            # Prompt for complete on exit
            from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
            if current_session:
                _prompt_for_complete_on_exit(current_session, config)
            else:
                _prompt_for_complete_on_exit(session, config)




def _build_investigation_prompt(
    goal: str,
    parent: Optional[str],
    config,
    session_name: str,
    project_path: Optional[str] = None,
    workspace: Optional[str] = None,
    issue_key: Optional[str] = None,
    issue_details: Optional[dict] = None,
) -> str:
    """Build the initial prompt for investigation sessions.

    Args:
        goal: Goal/description for the investigation
        parent: Parent issue key (optional, for tracking)
        config: Configuration object
        session_name: Name of the session
        project_path: Project path
        workspace: Workspace path
        issue_key: Optional issue key (for sessions created from issues)
        issue_details: Optional issue details dict with 'summary' and 'description' keys

    Returns:
        Initial prompt string with investigation-focused instructions
    """
    # Build the "Work on" line
    if issue_key:
        work_on_line = f"Work on: Investigate {issue_key}: {goal}"
    elif parent:
        work_on_line = f"Work on: Investigate (tracking under {parent}): {goal}"
    else:
        work_on_line = f"Work on: Investigate: {goal}"

    prompt_parts = [
        work_on_line,
        "",
    ]

    # Add issue details section if session was created from an issue
    if issue_key and issue_details:
        from devflow.utils.backend_detection import detect_backend_from_key
        backend = detect_backend_from_key(issue_key, config)

        # Build issue URL if possible
        issue_url = None
        if backend == "jira" and config and hasattr(config, 'jira') and config.jira and hasattr(config.jira, 'url'):
            issue_url = f"{config.jira.url.rstrip('/')}/browse/{issue_key}"

        prompt_parts.append("## Issue Details")
        prompt_parts.append("")
        if issue_url:
            prompt_parts.append(f"**Issue:** {issue_key} ({issue_url})")
        else:
            prompt_parts.append(f"**Issue:** {issue_key}")

        if issue_details.get("summary"):
            prompt_parts.append(f"**Summary:** {issue_details['summary']}")

        if issue_details.get("description"):
            prompt_parts.append("")
            prompt_parts.append("**Description:**")
            prompt_parts.append(issue_details['description'])

        prompt_parts.append("")
        prompt_parts.append("---")
        prompt_parts.append("")

    # Load configured context files
    configured_files = []
    if config and config.context_files:
        configured_files = [(f.path, f.description) for f in config.context_files.files if not f.hidden]

    # Load hierarchical context files
    hierarchical_files = load_hierarchical_context_files(config)

    # Discover only hierarchical + project-level skills for prompt
    # User-level and workspace-level skills are already auto-discovered by Claude Code via --add-dir
    skill_files = discover_skills(
        project_path=project_path, workspace=workspace,
        include_levels={"hierarchical", "project"},
    )

    # Combine context files (AGENTS.md/CLAUDE.md auto-read by Claude Code)
    regular_files = hierarchical_files + configured_files

    if regular_files:
        prompt_parts.append("Please start by reading the following context files if they exist:")
        for path, description in regular_files:
            prompt_parts.append(f"- {path} ({description})")

    # Add skill loading section
    if skill_files:
        prompt_parts.append("")
        prompt_parts.append("⚠️  CRITICAL: Read ALL of the following skill files before proceeding:")
        for path, description in skill_files:
            prompt_parts.append(f"- {path}")
        prompt_parts.append("")
        prompt_parts.append("These skills contain essential tool usage information and must be read completely.")

    prompt_parts.append("")

    # Add investigation instructions
    prompt_parts.extend([
        "⚠️  IMPORTANT CONSTRAINTS:",
        "   • This is an INVESTIGATION-ONLY session for codebase analysis",
        "   • DO NOT modify any code or create/checkout git branches",
        "   • DO NOT make any file changes - only READ and ANALYZE",
        "   • Focus on understanding the codebase and documenting findings",
        "",
        "Your task:",
        f"1. Investigate the codebase to understand: {goal}",
        "2. Read relevant files, search for patterns, understand the architecture",
        "3. Analyze feasibility and identify implementation approaches",
        "4. Generate a summary of your findings and recommendations",
        "5. Suggest whether this work should proceed and what approach to take",
        "6. If you discover bugs or improvements during investigation, you MAY create issue tracker tickets using 'daf jira create' (for JIRA) or 'gh issue create' / 'glab issue create' (for GitHub/GitLab)",
        "",
        "When you're done investigating:",
        "- Provide a clear summary of what you discovered",
        "- List the key files and components involved",
        "- Suggest implementation approaches (if applicable)",
        "- Note any concerns or blockers",
        "- Create issue tracker tickets using 'daf jira create' (JIRA) or 'gh issue create' / 'glab issue create' (GitHub/GitLab) for any bugs or improvements discovered (if applicable)",
        "",
        "The user will save your findings using 'daf note' or export them.",
        "",
        "Remember: This is READ-ONLY investigation for code/git. Do not modify any files or branches.",
    ])

    return "\n".join(prompt_parts)


def _build_multiproject_investigation_prompt(
    goal: str,
    parent: Optional[str],
    config,
    name: str,
    project_paths: list[str],
    workspace: str,
) -> str:
    """Build initial prompt for multi-project investigation (Issue #182).

    Args:
        goal: Goal/description for the investigation
        parent: Parent issue key (optional, for tracking)
        config: Configuration object
        name: Session name
        project_paths: List of full project paths to investigate
        workspace: Workspace path

    Returns:
        Initial prompt string for Claude
    """
    from devflow.cli.skills_discovery import discover_skills
    from devflow.utils.context_files import load_hierarchical_context_files

    project_names = [Path(p).name for p in project_paths]
    projects_list = "\n".join([f"  • {name}" for name in project_names])

    # Build the "Work on" line
    if parent:
        work_on_line = f"Work on daf session: {name} (tracking under {parent})"
    else:
        work_on_line = f"Work on daf session: {name}"

    prompt_parts = [
        work_on_line,
        "",
        f"This is a MULTI-PROJECT investigation session for analyzing {len(project_paths)} repositories:",
        projects_list,
        "",
    ]

    # Load configured context files
    configured_files = []
    if config and config.context_files:
        configured_files = [(f.path, f.description) for f in config.context_files.files if not f.hidden]

    # Load hierarchical context files
    hierarchical_files = load_hierarchical_context_files(config)

    # Discover only hierarchical + project-level skills for prompt
    # User-level and workspace-level skills are already auto-discovered by Claude Code via --add-dir
    skill_files = discover_skills(
        project_path=project_paths[0], workspace=workspace,
        include_levels={"hierarchical", "project"},
    )

    # Combine context files (AGENTS.md/CLAUDE.md auto-read by Claude Code)
    regular_files = hierarchical_files + configured_files

    if regular_files:
        prompt_parts.append("Please start by reading the following context files if they exist:")
        for path, description in regular_files:
            prompt_parts.append(f"- {path} ({description})")

    # Add skill loading section
    if skill_files:
        prompt_parts.append("")
        prompt_parts.append("⚠️  CRITICAL: Read ALL of the following skill files before proceeding:")
        for path, description in skill_files:
            prompt_parts.append(f"- {path}")
        prompt_parts.append("")
        prompt_parts.append("These skills contain essential tool usage information and must be read completely.")

    prompt_parts.append("")

    # Add multi-project investigation instructions
    prompt_parts.extend([
        "⚠️  CRITICAL CONSTRAINTS:",
        "• This is a READ-ONLY investigation session",
        "• Do NOT modify any code or files in any project",
        "• Do NOT create git commits or checkout branches",
        "• ONLY analyze the codebases to understand architecture and dependencies",
        "",
        f"Your task: Investigate ALL {len(project_paths)} projects to understand: {goal}",
        "",
        "Steps to complete this investigation:",
        f"1. Analyze ALL {len(project_paths)} projects to understand:",
        "   • Current architecture and implementation across projects",
        "   • How the projects interact (APIs, shared code, dependencies)",
        "   • Relevant code patterns and conventions",
        "   • Cross-project dependencies and integration points",
        "2. Read relevant files in each project, search for patterns, understand the architecture",
        "3. Document your findings considering all projects",
        "4. Identify feasibility and implementation approaches for cross-project changes",
        "5. Generate a comprehensive summary of your findings and recommendations",
        "6. Suggest whether this work should proceed and what approach to take",
        "7. If you discover bugs or improvements during investigation, you MAY create issue tracker tickets using 'daf jira create' (for JIRA) or 'gh issue create' / 'glab issue create' (for GitHub/GitLab)",
        "",
        "When you're done investigating:",
        "- Provide a clear summary of what you discovered across all projects",
        "- List the key files and components involved in each project",
        "- Explain how the projects interact and depend on each other",
        "- Suggest implementation approaches considering all projects (if applicable)",
        "- Note any concerns, blockers, or cross-project compatibility issues",
        "- Create issue tracker tickets using 'daf jira create' (JIRA) or 'gh issue create' / 'glab issue create' (GitHub/GitLab) for any bugs or improvements discovered (if applicable)",
        "",
        "The user will save your findings using 'daf note' or export them.",
        "",
        f"Remember: This is READ-ONLY investigation across {len(project_paths)} projects. Do not modify any files or branches.",
    ])

    return "\n".join(prompt_parts)


def _create_multi_project_investigation_session(
    config,
    config_loader,
    name: str,
    goal: str,
    parent: Optional[str],
    project_paths: list[str],
    workspace: Optional[str],
    selected_workspace_name: str,
    model_profile: Optional[str] = None,
    agent: Optional[str] = None,
) -> None:
    """Create a multi-project investigation session (Issue #182).

    Args:
        config: Configuration object
        config_loader: ConfigLoader instance
        name: Session name
        goal: Investigation goal
        parent: Optional parent issue key (for tracking)
        project_paths: List of full paths to selected projects
        workspace: Workspace flag
        selected_workspace_name: Selected workspace name
        model_profile: Optional model provider profile
        agent: AI agent backend override (e.g., "claude", "opencode")
    """
    from devflow.cli.commands.ticket_creation_multiproject import create_multi_project_ticket_creation_session
    from devflow.cli.utils import get_workspace_path, resolve_workspace_path
    from devflow.session.manager import SessionManager

    # Build the goal string that includes the investigation task
    if parent:
        full_goal = f"Investigate (under {parent}): {goal}"
    else:
        full_goal = f"Investigate: {goal}"

    # Get workspace path
    workspace_path = get_workspace_path(config, selected_workspace_name)
    if not workspace_path:
        console_print(f"[red]✗[/red] Could not find workspace path")
        if is_json_mode():
            output_json(success=False, error={"message": "Could not find workspace path", "code": "NO_WORKSPACE"})
        sys.exit(1)

    # Create session manager
    session_manager = SessionManager(config_loader=config_loader)

    # Create multi-project ticket creation session with session_type="investigation"
    session, ai_agent_session_id = create_multi_project_ticket_creation_session(
        session_manager=session_manager,
        config=config,
        name=name,
        goal=full_goal,
        project_paths=project_paths,
        workspace_path=workspace_path,
        selected_workspace_name=selected_workspace_name,
        session_type="investigation",  # Use investigation session type
        agent=agent,
    )

    # Set model profile if provided
    if model_profile:
        session.model_profile = model_profile

    # Set parent for tracking if provided
    if parent:
        session.issue_key = parent

    session_manager.update_session(session)

    # Resolve agent display name for user-facing messages
    agent_backend = resolve_agent_backend(config=config, session=session)
    agent_name = get_agent_display_name(agent_backend)

    # Check if we should launch the AI agent
    if not should_launch_claude_code(config=config, mock_mode=False):
        console_print(f"[yellow]⚠[/yellow] Session created but {agent_name} not launched.")
        console_print(f"  Run [cyan]daf open {name}[/cyan] to start working on it.")
        return

    # Build initial prompt for multi-project investigation
    if headless:
        initial_prompt = _build_multiproject_investigation_prompt(
            goal=goal,
            parent=parent,
            config=config,
            name=name,
            project_paths=project_paths,
            workspace=workspace_path,
        )
    else:
        initial_prompt = "Read your daf-workflow skill and follow the Session Initialization instructions."

    # Note: daf-workflow skill is auto-loaded, no validation needed
    if not validate_daf_agents_md(session, config_loader):
        return

    # Set up signal handlers for cleanup
    setup_signal_handlers(session, session_manager, name, config)

    # Get active model provider profile
    from devflow.utils.model_provider import get_active_profile, build_env_from_profile, get_profile_display_name
    model_provider_profile = get_active_profile(config, override_profile_name=session.model_profile) if config else None

    # Display which model provider is being used
    if model_provider_profile:
        provider_name = get_profile_display_name(model_provider_profile)
        console_print(f"[dim]Using model provider: {provider_name}[/dim]")

    # Build environment variables from model provider profile
    env = build_env_from_profile(model_provider_profile)

    # Set additional DevAIFlow environment variables
    env["CS_SESSION_NAME"] = name
    env["DAF_SESSION_NAME"] = name
    env["DAF_COMMAND"] = "investigate"
    env["DEVAIFLOW_IN_SESSION"] = "1"

    # Set GCP Vertex AI region if configured (deprecated - use model_provider instead)
    if config and config.gcp_vertex_region and not model_provider_profile:
        env["CLOUD_ML_REGION"] = config.gcp_vertex_region

    # Launch agent at workspace level with all projects accessible
    try:
        # Get agent backend from config
        from devflow.agent import create_agent_client

        _agent_backend = resolve_agent_backend(config=config, session=session)
        agent_client = create_agent_client(_agent_backend)

        # Get model provider profile if configured
        from devflow.utils.model_provider import get_active_profile as get_model_profile
        model_profile = None
        if config and config.model_provider:
            model_profile = get_model_profile(config, override_profile_name=session.model_profile)

        # Use workspace path as the primary directory
        workspace_resolved = resolve_workspace_path(config, session.workspace_name)

        # Debug output
        console_print(f"\n[dim]Debug - Agent launch:[/dim]")
        console_print(f"[dim]  Agent backend: {agent_backend}[/dim]")
        console_print(f"[dim]  Session ID: {ai_agent_session_id}[/dim]")
        console_print(f"[dim]  Workspace path: {workspace_resolved}[/dim]")
        console_print(f"[dim]  Prompt (first 100 chars): {initial_prompt[:100]}...[/dim]")
        console_print(f"[dim]  Working directory: {workspace_path}[/dim]")
        console_print()

        # Launch agent with snapshot/capture lifecycle at workspace level
        from devflow.agent.factory import launch_and_capture
        launch_and_capture(
            agent_client, _agent_backend, workspace_path,
            session.active_conversation,
            initial_prompt=initial_prompt,
            session_id=ai_agent_session_id,
            model_provider_profile=model_profile,
            workspace_path=workspace_resolved,
            config=config,
            env=env,
            headless=headless,
            auto_approve=auto_approve,
        )
    finally:
        if not is_cleanup_done():
            console_print(f"\n[green]✓[/green] {agent_name} session completed")

            # Reload index from disk
            session_manager.index = session_manager.config_loader.load_sessions()

            # Get current session
            current_session = session_manager.get_session(name)
            if not current_session:
                current_session = session

            # End work session
            try:
                session_manager.end_work_session(name)
            except ValueError as e:
                console_print(f"[yellow]⚠[/yellow] Could not end work session: {e}")

            console_print(f"[dim]Resume anytime with: daf open {name}[/dim]")

            # Prompt for complete on exit
            from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
            if current_session:
                _prompt_for_complete_on_exit(current_session, config)
            else:
                _prompt_for_complete_on_exit(session, config)
