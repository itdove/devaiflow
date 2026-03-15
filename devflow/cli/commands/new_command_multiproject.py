"""Multi-project session creation logic for DevAIFlow (Issue #149)."""

import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt

from devflow.cli.utils import (
    console_print,
    get_status_display,
    output_json as json_output,
    serialize_session,
    should_launch_claude_code,
)
from devflow.config.loader import ConfigLoader
from devflow.git.utils import GitUtils
from devflow.session.manager import SessionManager

console = Console()


def create_multi_project_session(
    session_manager: SessionManager,
    config_loader: ConfigLoader,
    config,
    name: str,
    goal: Optional[str],
    issue_key: Optional[str],
    issue_metadata_dict: Optional[Dict],
    issue_title: Optional[str],
    project_names: List[str],
    workspace_path: str,
    selected_workspace_name: str,
    force_new_session: bool,
    model_profile: Optional[str],
    output_json: bool,
) -> None:
    """Create a multi-project session with conversations for multiple repositories.

    Args:
        session_manager: Session manager instance
        config_loader: Config loader instance
        config: Loaded configuration
        name: Session name
        goal: Session goal (optional)
        issue_key: Issue tracker key (optional)
        issue_metadata_dict: Issue metadata dict (optional)
        issue_title: Issue title from tracker (optional)
        project_names: List of project names to include in session
        workspace_path: Workspace root path
        selected_workspace_name: Selected workspace name
        force_new_session: Whether to force creation of new session
        model_profile: Model provider profile (optional)
        output_json: Whether to output JSON
    """
    from devflow.cli.commands.new_command import (
        _generate_initial_prompt,
        _handle_branch_creation,
        _get_default_source_branch,
    )

    # Build concatenated goal for storage
    storage_goal = goal
    if issue_key and issue_title:
        storage_goal = f"{issue_key}: {issue_title}"
    elif issue_key and goal:
        storage_goal = f"{issue_key}: {goal}"
    elif issue_key:
        storage_goal = issue_key

    # Display multi-project session info
    if not output_json:
        console.print(f"\n[bold cyan]Creating multi-project session:[/bold cyan]")
        console.print(f"  Session: {name}")
        if storage_goal:
            console.print(f"  Goal: {storage_goal}")
        console.print(f"  Workspace: {selected_workspace_name}")
        console.print(f"  Projects ({len(project_names)}):")
        for proj in project_names:
            console.print(f"    • {proj}")
        console.print()

    # Generate a shared branch name for all projects
    branch_identifier = issue_key if issue_key else name
    backend = None
    if issue_key:
        from devflow.utils.backend_detection import detect_backend_from_key
        backend = detect_backend_from_key(issue_key, config)

    # Get use_issue_key_only setting
    use_issue_key_only = True
    if config and hasattr(config, 'prompts') and config.prompts:
        use_issue_key_only = config.prompts.use_issue_key_as_branch

    suggested_branch = GitUtils.generate_branch_name(
        branch_identifier,
        goal,
        use_issue_key_only=use_issue_key_only,
        backend=backend
    )

    # Prompt for branch name (shared across all projects)
    if output_json:
        shared_branch_name = suggested_branch
    else:
        console.print(f"[bold]Branch name for all projects:[/bold] {suggested_branch}")
        shared_branch_name = Prompt.ask("Enter branch name", default=suggested_branch)

    # Collect base branch for each project
    project_base_branches = {}
    workspace_path_obj = Path(workspace_path)

    if not output_json:
        console.print(f"\n[bold]Select base branch for each project:[/bold]")

    for proj_name in project_names:
        proj_path = workspace_path_obj / proj_name

        # Get default base branch for this project
        default_base = _get_default_source_branch(proj_path)

        if output_json:
            # Use default in JSON mode
            selected_base = default_base
        else:
            # Prompt for base branch
            console.print(f"\n[cyan]{proj_name}[/cyan] (default: {default_base})")

            # Offer common base branch options
            from devflow.cli.commands.new_command import _prompt_for_source_branch
            selected_base = _prompt_for_source_branch(proj_path, default_base)

            if not selected_base:
                # User cancelled
                console.print("[yellow]Multi-project session creation cancelled[/yellow]")
                sys.exit(1)

        project_base_branches[proj_name] = selected_base

        if not output_json:
            console.print(f"  → Will create branch from: [bold]{selected_base}[/bold]")

    # Create branches in all projects
    if not output_json:
        console.print(f"\n[bold]Creating branches...[/bold]")

    branch_creation_results = {}
    for proj_name in project_names:
        proj_path = workspace_path_obj / proj_name
        base_branch = project_base_branches[proj_name]

        if not output_json:
            console.print(f"\n[cyan]Processing {proj_name}...[/cyan]")

        # Create branch using the shared name and project-specific base branch
        branch_result = _handle_branch_creation(
            project_path=str(proj_path),
            issue_key=branch_identifier,
            goal=goal,
            auto_from_default=output_json,
            config=config,
            source_branch=base_branch,
        )

        # Check if user explicitly cancelled
        if branch_result is False:
            console.print(f"\n[yellow]Branch creation cancelled for {proj_name}[/yellow]")
            sys.exit(1)

        # Extract branch name and source branch
        if isinstance(branch_result, tuple):
            created_branch, source_branch = branch_result
        else:
            created_branch = branch_result
            source_branch = base_branch

        branch_creation_results[proj_name] = {
            'branch': created_branch or shared_branch_name,
            'base_branch': source_branch or base_branch,
        }

    # Check if session already exists (multi-conversation support)
    existing_sessions = session_manager.index.get_sessions(name)
    session = None

    if force_new_session and existing_sessions and not output_json:
        console.print(f"\n[cyan]Creating new session (--new-session flag set)[/cyan]")
        console.print(f"[dim]Existing sessions: {len(existing_sessions)}. New session will be #{len(existing_sessions) + 1}[/dim]\n")

    if existing_sessions and not force_new_session:
        # For multi-project sessions, always create a new session
        # (Adding multiple conversations at once is not supported via existing session)
        if not output_json:
            console.print(f"\n[yellow]⚠ Session '{name}' already exists[/yellow]")
            console.print(f"[dim]Multi-project sessions require a new session. Use --new-session flag.[/dim]")
        sys.exit(1)

    # Create new session with first project as primary
    first_project = project_names[0]
    first_proj_path = workspace_path_obj / first_project
    first_branch_info = branch_creation_results[first_project]

    session_id = str(uuid.uuid4())

    session = session_manager.create_session(
        name=name,
        issue_key=issue_key,
        goal=storage_goal,
        working_directory=first_project,
        project_path=str(first_proj_path),
        branch=first_branch_info['branch'],
        ai_agent_session_id=session_id,
        model_profile=model_profile,
    )

    # Set base_branch for first conversation
    if session.active_conversation:
        session.active_conversation.base_branch = first_branch_info['base_branch']

    # Store workspace name
    if selected_workspace_name:
        session.workspace_name = selected_workspace_name

    # Add remaining projects as conversations
    for proj_name in project_names[1:]:
        proj_path = workspace_path_obj / proj_name
        branch_info = branch_creation_results[proj_name]
        conv_session_id = str(uuid.uuid4())

        session.add_conversation(
            working_dir=proj_name,
            ai_agent_session_id=conv_session_id,
            project_path=str(proj_path),
            branch=branch_info['branch'],
            base_branch=branch_info['base_branch'],
            workspace=workspace_path,
        )

    # Populate JIRA metadata if available
    if issue_metadata_dict:
        session.issue_metadata = {
            k: v for k, v in issue_metadata_dict.items()
            if k not in ('key', 'updated') and v is not None
        }

    # Save session
    session_manager.update_session(session)

    # JSON output mode
    if output_json:
        session_data = serialize_session(session)
        json_output(
            success=True,
            data={
                "session": session_data,
                "ai_agent_session_id": session_id,
                "conversations": len(session.conversations),
            }
        )
        return

    # Display success banner
    console.print("\n" + "━" * 60)
    console.print(f"[bold green]✓ Multi-project session created:[/bold green] {name}")
    if storage_goal:
        console.print(f"[bold]Goal:[/bold] {storage_goal}")
    console.print(f"[bold]Workspace:[/bold] {selected_workspace_name}")
    console.print(f"\n[bold]Projects ({len(project_names)}):[/bold]")
    for proj_name in project_names:
        info = branch_creation_results[proj_name]
        console.print(f"  • {proj_name}")
        console.print(f"    Branch: {info['branch']}")
        console.print(f"    Base: {info['base_branch']}")
    console.print("━" * 60 + "\n")

    # Generate initial prompt
    initial_prompt = _generate_initial_prompt(
        name=name,
        goal=storage_goal,
        issue_key=issue_key,
        issue_title=issue_title,
        session_type="development",
        current_project=None,  # Multi-project mode
        other_projects=project_names,
        project_path=workspace_path,  # Use workspace path for multi-project
        workspace=selected_workspace_name,
    )

    # Launch Claude Code at workspace level (not individual project)
    if should_launch_claude_code(config):
        console.print("[cyan]Launching Claude Code at workspace level...[/cyan]\n")

        # Setup signal handlers for graceful cleanup
        from devflow.cli.signal_handler import setup_signal_handlers
        setup_signal_handlers(session_manager, session)

        # Import after signal handlers are set up
        from devflow.cli.utils import launch_claude_code

        launch_claude_code(
            project_path=workspace_path,  # Launch at workspace root
            session_id=session_id,
            initial_prompt=initial_prompt,
            model_profile=model_profile,
        )
    else:
        console.print(f"\n[dim]Claude Code launch disabled in config[/dim]")
        console.print(f"[dim]Session UUID: {session_id}[/dim]")
        console.print(f"\n[bold]To resume:[/bold] daf open {name}")
