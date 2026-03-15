"""Commands for managing projects/conversations in sessions."""

import sys
import uuid
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.prompt import Confirm

from devflow.cli.utils import console_print
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager

console = Console()


def add_project_to_session(
    session_name: str,
    project_names: List[str],
    workspace_name: str,
    branch: Optional[str] = None,
) -> None:
    """Add one or more projects to an existing session.

    Args:
        session_name: Name of the session to add projects to
        project_names: List of project/repository names to add
        workspace_name: Workspace name containing the projects
        branch: Optional shared branch name for all projects
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        sys.exit(1)

    # Get session
    session = session_manager.get_session(session_name)
    if not session:
        console.print(f"[red]✗[/red] Session not found: {session_name}")
        sys.exit(1)

    # Validate workspace
    if not config.repos or not config.repos.workspaces:
        console.print("[red]✗[/red] No workspaces configured. Run [cyan]daf init[/cyan] first.")
        sys.exit(1)

    workspace = config.repos.workspaces.get(workspace_name)
    if not workspace:
        console.print(f"[red]✗[/red] Workspace not found: {workspace_name}")
        console.print(f"[dim]Available workspaces: {', '.join(config.repos.workspaces.keys())}[/dim]")
        sys.exit(1)

    workspace_path = Path(workspace.path).expanduser().resolve()
    if not workspace_path.exists():
        console.print(f"[red]✗[/red] Workspace path does not exist: {workspace_path}")
        sys.exit(1)

    # Import here to avoid circular dependency
    from devflow.cli.commands.new_command import _handle_branch_creation

    added_count = 0
    skipped_count = 0

    console.print(f"\n[bold cyan]Adding projects to session:[/bold cyan] {session_name}")
    console.print(f"[dim]Workspace: {workspace_name} ({workspace_path})[/dim]\n")

    for project_name in project_names:
        # Check if conversation already exists
        if project_name in session.conversations:
            console.print(f"[yellow]⚠[/yellow] Project already exists: {project_name} [dim](skipping)[/dim]")
            skipped_count += 1
            continue

        # Validate project path exists
        project_path = workspace_path / project_name
        if not project_path.exists():
            console.print(f"[red]✗[/red] Project path does not exist: {project_path} [dim](skipping)[/dim]")
            skipped_count += 1
            continue

        console.print(f"\n[cyan]Adding project:[/cyan] {project_name}")

        # Handle branch creation with project context
        branch_result = _handle_branch_creation(
            project_path=str(project_path),
            issue_key=session.issue_key or session.name,
            goal=session.goal,
            auto_from_default=False,
            config=config,
            source_branch=None,  # Let user choose base branch
            branch_name=branch,  # Use shared branch if provided
            project_name=project_name,  # Add context to prompts
        )

        # Check if user cancelled
        if branch_result is False or branch_result is None:
            console.print(f"[yellow]Cancelled adding {project_name}[/yellow]")
            skipped_count += 1
            continue

        # Extract branch name and base branch
        if isinstance(branch_result, tuple):
            created_branch, base_branch = branch_result
        else:
            created_branch = branch_result
            base_branch = None

        # Generate new session UUID for this conversation
        conversation_id = str(uuid.uuid4())

        # Add conversation to session
        session.add_conversation(
            working_dir=project_name,
            ai_agent_session_id=conversation_id,
            project_path=str(project_path),
            branch=created_branch or "",
            base_branch=base_branch,
            workspace=str(workspace_path),
        )

        console.print(f"[green]✓[/green] Added project: {project_name}")
        console.print(f"  Branch: {created_branch}")
        if base_branch:
            console.print(f"  Base: {base_branch}")
        added_count += 1

    # Save session
    if added_count > 0:
        session_manager.update_session(session)

    # Summary
    console.print("\n" + "━" * 60)
    if added_count > 0:
        console.print(f"[bold green]✓ Added {added_count} project(s) to session[/bold green]")
    if skipped_count > 0:
        console.print(f"[yellow]⚠ Skipped {skipped_count} project(s)[/yellow]")

    if added_count == 0:
        console.print("[yellow]No projects were added[/yellow]")
    else:
        console.print(f"\n[bold]To work on added projects:[/bold]")
        console.print(f"  daf open {session_name} --path <project-name>")
    console.print("━" * 60 + "\n")


def remove_project_from_session(
    session_name: str,
    project_name: str,
    force: bool = False,
) -> None:
    """Remove a project/conversation from an existing session.

    Args:
        session_name: Name of the session to remove project from
        project_name: Project/repository name to remove
        force: Skip confirmation prompt if True
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Get session
    session = session_manager.get_session(session_name)
    if not session:
        console.print(f"[red]✗[/red] Session not found: {session_name}")
        sys.exit(1)

    # Check if conversation exists
    if project_name not in session.conversations:
        console.print(f"[red]✗[/red] No conversation found for project: {project_name}")
        console.print(f"\n[dim]Available projects in session:[/dim]")
        for conv_name in session.conversations.keys():
            console.print(f"  • {conv_name}")
        sys.exit(1)

    # Get conversation details for confirmation message
    conversation = session.conversations[project_name]
    active_session = conversation.active_session

    # Confirm removal
    if not force:
        console.print(f"\n[yellow]⚠ About to remove project:[/yellow] {project_name}")
        console.print(f"  Branch: {active_session.branch}")
        console.print(f"  Path: {active_session.project_path}")
        console.print(f"  Messages: {active_session.message_count}")

        if not Confirm.ask("\n[bold]Remove this project from the session?[/bold]", default=False):
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Remove the conversation
    del session.conversations[project_name]

    # If this was the active working directory, switch to another one or clear it
    if session.working_directory == project_name:
        if len(session.conversations) > 0:
            # Switch to first remaining conversation
            session.working_directory = list(session.conversations.keys())[0]
            console.print(f"[dim]Active conversation switched to: {session.working_directory}[/dim]")
        else:
            session.working_directory = ""
            console.print("[dim]No conversations remaining in session[/dim]")

    # Save session
    session_manager.update_session(session)

    console.print(f"\n[green]✓[/green] Removed project: {project_name}")

    # Show remaining projects if any
    if len(session.conversations) > 0:
        console.print(f"\n[dim]Remaining projects in session:[/dim]")
        for conv_name in session.conversations.keys():
            marker = "← active" if conv_name == session.working_directory else ""
            console.print(f"  • {conv_name} {marker}")
    else:
        console.print("\n[yellow]⚠ Session has no projects remaining[/yellow]")
        console.print("[dim]Consider deleting the session or adding new projects[/dim]")
