"""Implementation of template management commands."""

import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from devflow.cli.utils import get_status_display, require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.templates.manager import TemplateManager

console = Console()


@require_outside_claude
def save_template(
    identifier: str,
    template_name: str,
    description: Optional[str] = None,
) -> None:
    """Save a session as a template.

    Args:
        identifier: Session name or issue key
        template_name: Name for the template
        description: Optional template description
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)
    template_manager = TemplateManager()

    # Find the session
    sessions = session_manager.index.get_sessions(identifier)
    if not sessions:
        console.print(f"[red]✗[/red] Session '{identifier}' not found")
        sys.exit(1)

    # If multiple sessions, ask which one to use as template
    session = None
    if len(sessions) > 1:
        console.print(f"\n[bold]Found {len(sessions)} sessions in group '{identifier}':[/bold]\n")
        for idx, sess in enumerate(sessions, 1):
            status_text, status_color = get_status_display(sess.status)
            console.print(f"  [{status_color}]{idx}.[/{status_color}] {sess.working_directory} - {status_text}")
            console.print(f"      Goal: {sess.goal}")
            console.print()

        choice = Prompt.ask("Which session to use as template?", choices=[str(i) for i in range(1, len(sessions) + 1)], default="1")
        session = sessions[int(choice) - 1]
    else:
        session = sessions[0]

    # Prompt for description if not provided
    if description is None:
        description = Prompt.ask(
            "Template description",
            default=session.goal if session.goal else ""
        )

    # Create template from session
    from devflow.templates.models import SessionTemplate
    from datetime import datetime

    # Get branch from active conversation
    active_conv = session.active_conversation
    branch = active_conv.branch if active_conv else None

    template = SessionTemplate(
        name=template_name,
        description=description,
        working_directory=session.working_directory,
        branch=branch,
        tags=session.tags if session.tags else [],
        issue_key=session.issue_key,
        created_at=datetime.now(),
    )

    # Check if template already exists
    if template_manager.get_template(template_name) is not None:
        console.print(f"[red]✗[/red] Template '{template_name}' already exists")
        return

    # Save the template
    try:
        template_manager.save_template(template)
        console.print(f"\n[green]✓[/green] Template '{template_name}' saved successfully")
        console.print(f"\n[dim]Use with: daf new --template {template_name}[/dim]")
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")


def list_templates() -> None:
    """List all available templates."""
    template_manager = TemplateManager()
    templates = template_manager.list_templates()

    if not templates:
        console.print("[yellow]No templates found[/yellow]")
        console.print("\n[dim]Create one with: daf template save <session-name> <template-name>[/dim]")
        return

    # Create a table
    table = Table(title="Available Templates")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("JIRA", style="dim")
    table.add_column("Created", style="dim")

    for template in templates:
        table.add_row(
            template.name,
            template.description or "",
            template.issue_key or "-",
            template.created_at.strftime("%Y-%m-%d %H:%M") if template.created_at else "-",
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Use with: daf new --template <name>[/dim]")


def show_template(template_name: str) -> None:
    """Show details of a template.

    Args:
        template_name: Template name
    """
    template_manager = TemplateManager()
    template = template_manager.get_template(template_name)

    if not template:
        console.print(f"[red]✗[/red] Template '{template_name}' not found")
        console.print("\n[dim]List templates with: daf template list[/dim]")
        return

    # Display template details
    console.print("\n" + "━" * 60)
    console.print(f"📋 Template: [bold]{template.name}[/bold]")
    if template.description:
        console.print(f"📝 Description: {template.description}")
    if template.issue_key:
        console.print(f"🔗 JIRA: {template.issue_key}")
    if template.working_directory:
        console.print(f"📁 Working Directory: {template.working_directory}")
    if template.branch:
        console.print(f"🌿 Branch Pattern: {template.branch}")
    if template.tags:
        console.print(f"🏷️  Tags: {', '.join(template.tags)}")
    if template.created_at:
        console.print(f"📅 Created: {template.created_at.strftime('%Y-%m-%d %H:%M')}")
    console.print("━" * 60)


@require_outside_claude
def delete_template(template_name: str, force: bool = False) -> None:
    """Delete a template.

    Args:
        template_name: Template name
        force: Skip confirmation prompt
    """
    template_manager = TemplateManager()

    # Check if template exists
    template = template_manager.get_template(template_name)
    if not template:
        console.print(f"[red]✗[/red] Template '{template_name}' not found")
        sys.exit(1)

    # Confirm deletion unless --force
    if not force:
        console.print(f"\n[yellow]Template to delete:[/yellow]")
        console.print(f"  Name: {template.name}")
        if template.description:
            console.print(f"  Description: {template.description}")
        console.print()

        if not Confirm.ask(f"Delete template '{template_name}'?", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

    # Delete the template
    try:
        template_manager.delete_template(template_name)
        console.print(f"\n[green]✓[/green] Template '{template_name}' deleted")
    except FileNotFoundError:
        console.print(f"[red]✗[/red] Template '{template_name}' not found")
        sys.exit(1)
