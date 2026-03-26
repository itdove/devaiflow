"""Implementation of 'daf upgrade' command."""

from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.table import Table

from devflow.config.loader import ConfigLoader
from devflow.utils.claude_commands import (
    install_or_upgrade_reference_skills,
    install_or_upgrade_slash_commands,
    install_skills_to_agents,
)

console = Console()


def upgrade_all(
    dry_run: bool = False,
    quiet: bool = False,
    upgrade_skills: bool = True,
    upgrade_hierarchical_skills: bool = True,
    project_path: str = None,
    agents: Optional[List[str]] = None,
    level: str = 'global'
) -> None:
    """Upgrade bundled Claude Code skills.

    This command will:
    - Install slash commands (daf-*) to target directory
    - Install reference skills (daf-cli, gh-cli, etc.) to target directory
    - Install organization-specific skills from hierarchical config files
    - Skip items that are already up-to-date

    Args:
        dry_run: If True, only report what would be changed without actually changing
        quiet: If True, suppress console output (errors still shown)
        upgrade_skills: If True, upgrade bundled skills (slash commands + reference skills)
        upgrade_hierarchical_skills: If True, install hierarchical skills from config files
        project_path: Project directory path for project-level installation (default: None = global)
        agents: List of agent names to install to (default: ['claude'] for backward compatibility)
        level: Installation level - 'global', 'project', or 'both' (default: 'global')

    Note:
        By default, skills are installed globally to ~/.claude/skills/.
        With --project-path, skills are installed to <project>/.claude/skills/.
        Hierarchical skills are always installed to ~/.daf-sessions/.claude/skills/.

        Multi-agent support:
        - Use agents parameter to install to multiple AI agents
        - Use level parameter to control installation location
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config or not config.repos:
        console.print("[red]✗[/red] Configuration not found")
        console.print("[dim]Run 'daf init' to configure your setup[/dim]")
        return

    if not config.repos.workspaces:
        console.print("[yellow]⚠[/yellow] No workspaces configured")
        console.print("[dim]Add a workspace with: daf workspace add <name> <path>[/dim]")
        return

    # Determine agents to install to
    if agents is None:
        # Default to Claude only for backward compatibility
        agents = ['claude']

    # Validate and determine project path for level=project or level=both
    project_path_obj = None
    if level in ('project', 'both'):
        if not project_path:
            console.print("[red]✗[/red] --project-path is required for level=project or level=both")
            return

        project_path_obj = Path(project_path).expanduser().resolve()

        # Validate that project path exists
        if not project_path_obj.exists():
            console.print(f"[red]✗[/red] Project path does not exist: {project_path_obj}")
            return

        if not project_path_obj.is_dir():
            console.print(f"[red]✗[/red] Project path is not a directory: {project_path_obj}")
            return

    if not quiet:
        if dry_run:
            console.print("[cyan]Checking for updates (dry run)...[/cyan]")
        else:
            console.print("[cyan]Upgrading bundled skills...[/cyan]")
        console.print()

    # Track overall results
    all_changed = []
    all_up_to_date = []
    all_failed = []

    # Install skills using multi-agent installation
    if upgrade_skills:
        try:
            results = install_skills_to_agents(
                agents=agents,
                level=level,
                project_path=project_path_obj,
                skip_confirmation=True,  # CLI already confirmed via command execution
                dry_run=dry_run,
                quiet=quiet
            )

            # Aggregate results across all agents
            for agent, (changed, up_to_date, failed) in results.items():
                all_changed.extend([f"{agent}:{name}" for name in changed])
                all_up_to_date.extend([f"{agent}:{name}" for name in up_to_date])
                all_failed.extend([f"{agent}:{name}" for name in failed])

        except Exception as e:
            console.print(f"[red]✗[/red] Skill installation failed: {e}")
            import traceback
            if not quiet:
                console.print(f"[dim]{traceback.format_exc()}[/dim]")

    # Upgrade hierarchical skills if requested (only once, they're global)
    if upgrade_hierarchical_skills:
        if not quiet:
            console.print("\n[bold]Hierarchical Skills (from config files):[/bold]")

        from devflow.utils.hierarchical_skills import (
            install_hierarchical_skills,
            get_hierarchical_skill_statuses
        )

        statuses_before = get_hierarchical_skill_statuses()

        try:
            changed, up_to_date, failed = install_hierarchical_skills(
                dry_run=dry_run,
                quiet=quiet
            )
            all_changed.extend([f"hierarchical:{name}" for name in changed])
            all_up_to_date.extend([f"hierarchical:{name}" for name in up_to_date])
            all_failed.extend([f"hierarchical:{name}" for name in failed])

            _print_upgrade_table(
                changed, up_to_date, failed, statuses_before,
                item_type="hierarchical skill", dry_run=dry_run, quiet=quiet
            )

        except Exception as e:
            console.print(f"[red]✗[/red] Hierarchical skill installation failed: {e}")
            # Don't raise - continue with summary

        if not quiet:
            console.print()

    # Overall summary
    if not quiet:
        console.print("\n[bold]Summary:[/bold]")
        if dry_run:
            if all_changed:
                console.print(f"[yellow]Would change {len(all_changed)} item(s)[/yellow]")
                console.print("[dim]Run without --dry-run to apply changes[/dim]")
            else:
                console.print("[green]✓[/green] All items are up-to-date")
        else:
            if all_changed:
                console.print(f"[green]✓[/green] Updated {len(all_changed)} item(s)")
            elif all_up_to_date:
                console.print("[green]✓[/green] All items are up-to-date")

            if all_failed:
                console.print(f"[red]✗[/red] Failed to update {len(all_failed)} item(s)")

        # Show installation info
        if upgrade_skills:
            console.print(f"\n[bold]Installed to:[/bold]")
            console.print(f"  Agents: {', '.join(agents)}")
            console.print(f"  Level: {level}")
            if level == 'global':
                console.print(f"  Location: ~/.agent/skills/ (varies by agent)")
            elif level == 'project':
                console.print(f"  Location: {project_path_obj}/.agent/skills/")
            elif level == 'both':
                console.print(f"  Locations: ~/.agent/skills/ AND {project_path_obj}/.agent/skills/")

        if upgrade_hierarchical_skills:
            from devflow.utils.paths import get_cs_home
            hierarchical_skills_dir = get_cs_home() / ".claude" / "skills"
            console.print(f"\n[dim]Hierarchical skills: {hierarchical_skills_dir}[/dim]")


def _print_upgrade_table(
    changed: list,
    up_to_date: list,
    failed: list,
    statuses_before: dict,
    item_type: str,
    dry_run: bool,
    quiet: bool
) -> None:
    """Print upgrade table for commands or skills.

    Args:
        changed: List of changed item names
        up_to_date: List of up-to-date item names
        failed: List of failed item names
        statuses_before: Dict mapping item names to status before upgrade
        item_type: "command" or "skill"
        dry_run: Whether this is a dry run
        quiet: Whether to suppress output
    """
    if quiet:
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column(item_type.capitalize(), style="cyan")
    table.add_column("Status Before")
    table.add_column("Status After")

    # Show changed items
    for item_name in changed:
        status_before = statuses_before.get(item_name, "not_installed")

        if status_before == "not_installed":
            status_before_display = "[yellow]not installed[/yellow]"
            status_after_display = "[green]installed[/green]" if not dry_run else "[yellow]would install[/yellow]"
        else:
            status_before_display = "[yellow]outdated[/yellow]"
            status_after_display = "[green]upgraded[/green]" if not dry_run else "[yellow]would upgrade[/yellow]"

        table.add_row(item_name, status_before_display, status_after_display)

    # Show up-to-date items
    for item_name in up_to_date:
        table.add_row(item_name, "[green]up-to-date[/green]", "[dim]no change[/dim]")

    # Show failed items
    for item_name in failed:
        status_before = statuses_before.get(item_name, "unknown")
        table.add_row(item_name, f"[dim]{status_before}[/dim]", "[red]failed[/red]")

    console.print(table)
