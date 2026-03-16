"""Multi-project ticket creation session logic for DevAIFlow (Issue #179)."""

import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

from devflow.cli.utils import console_print
from devflow.git.utils import GitUtils
from devflow.session.manager import SessionManager

console = Console()


def create_multi_project_ticket_creation_session(
    session_manager: SessionManager,
    config,
    name: str,
    goal: str,
    project_paths: List[str],
    workspace_path: str,
    selected_workspace_name: str,
    session_type: str = "ticket_creation",
    issue_type: Optional[str] = None,
) -> tuple[object, str]:
    """Create a multi-project ticket creation session (analysis-only, no branches).

    Similar to create_multi_project_session but skips branch creation since
    ticket creation sessions are analysis-only (Issue #179).

    Args:
        session_manager: Session manager instance
        config: Loaded configuration
        name: Session name
        goal: Session goal
        project_paths: List of full paths to projects
        workspace_path: Workspace root path
        selected_workspace_name: Selected workspace name
        session_type: Session type ("ticket_creation" for both jira/git new)
        issue_type: Optional issue type (for git new)

    Returns:
        Tuple of (session, ai_agent_session_id)
    """
    workspace_path_obj = Path(workspace_path)

    # Extract project names from paths
    project_names = [Path(p).name for p in project_paths]

    console.print(f"\n[bold cyan]Creating multi-project {session_type} session:[/bold cyan]")
    console.print(f"  Session: {name}")
    console.print(f"  Goal: {goal}")
    console.print(f"  Workspace: {selected_workspace_name}")
    console.print(f"  Projects ({len(project_names)}):")
    for proj in project_names:
        console.print(f"    • {proj}")
    console.print(f"  [dim]Session type: {session_type} (no branches will be created)[/dim]")
    console.print()

    # Create ONE shared session ID for all projects
    session_id = str(uuid.uuid4())

    # Build projects_info dict for multi-project conversation
    # For ticket creation, we don't create branches - just use current branch
    projects_info = {}
    for proj_path in project_paths:
        proj_name = Path(proj_path).name

        # Get current branch (or None if not a git repo)
        current_branch = None
        if GitUtils.is_git_repository(Path(proj_path)):
            current_branch = GitUtils.get_current_branch(Path(proj_path))

        projects_info[proj_name] = {
            'project_path': proj_path,
            'branch': current_branch,  # Current branch, not creating new one
            'base_branch': None,  # Not applicable for ticket creation
        }

    # Create session without initial conversation
    session = session_manager.create_session(
        name=name,
        goal=goal,
        working_directory=None,  # Will be set by add_multi_project_conversation
        project_path=None,
        branch=None,
        ai_agent_session_id=None,  # Will be set by add_multi_project_conversation
    )

    # Set session_type to "ticket_creation"
    session.session_type = session_type

    # Add multi-project conversation (ONE conversation for all projects)
    session.add_multi_project_conversation(
        ai_agent_session_id=session_id,
        projects_info=projects_info,
        workspace_path=workspace_path,
    )

    # Store workspace name
    if selected_workspace_name:
        session.workspace_name = selected_workspace_name

    # Save session
    session_manager.update_session(session)

    # Display success message
    console.print(f"\n[green]✓[/green] Created multi-project {session_type} session: [cyan]{name}[/cyan]")
    console.print(f"[dim]Goal: {goal}[/dim]")
    console.print(f"[dim]Projects: {', '.join(project_names)}[/dim]")
    console.print(f"[dim]No branches will be created (analysis-only mode)[/dim]\n")

    return session, session_id
