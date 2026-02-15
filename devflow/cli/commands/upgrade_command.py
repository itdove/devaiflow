"""Implementation of 'daf upgrade' command."""

from pathlib import Path
from rich.console import Console
from rich.table import Table

from devflow.config.loader import ConfigLoader
from devflow.utils.claude_commands import (
    install_or_upgrade_skills,
    get_all_skill_statuses,
)

console = Console()


def upgrade_all(
    dry_run: bool = False,
    quiet: bool = False,
    upgrade_skills: bool = True,
    upgrade_hierarchical_skills: bool = True
) -> None:
    """Upgrade bundled Claude Code skills in ALL configured workspaces.

    This command will:
    - Install skills in ALL workspaces if they don't exist yet
    - Upgrade skills in ALL workspaces if they are outdated
    - Skip skills that are already up-to-date
    - Install organization-specific skills from hierarchical config files

    Args:
        dry_run: If True, only report what would be changed without actually changing
        quiet: If True, suppress console output (errors still shown)
        upgrade_skills: If True, upgrade bundled skills (including slash commands)
        upgrade_hierarchical_skills: If True, install hierarchical skills from config files

    Note:
        As of Claude Code 2.1.3, slash commands are now skills with SKILL.md files.
        All slash commands are installed as skills under .claude/skills/ directories.
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

    if not quiet:
        if dry_run:
            console.print("[cyan]Checking for updates in ALL workspaces (dry run)...[/cyan]")
        else:
            console.print("[cyan]Upgrading bundled skills in ALL workspaces...[/cyan]")
        console.print(f"[dim]Workspaces: {len(config.repos.workspaces)} configured[/dim]")
        console.print()

    # Track overall results across all workspaces
    all_changed = []
    all_up_to_date = []
    all_failed = []

    # Upgrade each workspace
    for workspace_def in config.repos.workspaces:
        workspace = workspace_def.path
        workspace_name = workspace_def.name

        # Verify workspace exists
        workspace_path = Path(workspace).expanduser().resolve()
        if not workspace_path.exists():
            if not quiet:
                console.print(f"[yellow]⚠[/yellow] Skipping '{workspace_name}': directory does not exist: {workspace}")
            continue

        if not quiet:
            console.print(f"\n[bold cyan]Workspace: {workspace_name}[/bold cyan]")
            console.print(f"[dim]Path: {workspace}[/dim]")
            console.print()

        # Upgrade skills (including slash commands) if requested
        if upgrade_skills:
            if not quiet:
                console.print("[bold]Skills:[/bold]")

            statuses_before = get_all_skill_statuses(workspace)

            try:
                changed, up_to_date, failed = install_or_upgrade_skills(
                    workspace,
                    dry_run=dry_run,
                    quiet=quiet
                )
                all_changed.extend([f"{workspace_name}:skill:{name}" for name in changed])
                all_up_to_date.extend([f"{workspace_name}:skill:{name}" for name in up_to_date])
                all_failed.extend([f"{workspace_name}:skill:{name}" for name in failed])

                _print_upgrade_table(
                    changed, up_to_date, failed, statuses_before,
                    item_type="skill", dry_run=dry_run, quiet=quiet
                )

            except FileNotFoundError as e:
                console.print(f"[red]✗[/red] {e}")
                continue  # Continue with next workspace
            except Exception as e:
                console.print(f"[red]✗[/red] Upgrade failed: {e}")
                continue  # Continue with next workspace

            if not quiet:
                console.print()

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
                console.print(f"[yellow]Would change {len(all_changed)} item(s) across {len(config.repos.workspaces)} workspace(s)[/yellow]")
                console.print("[dim]Run without --dry-run to apply changes[/dim]")
            else:
                console.print("[green]✓[/green] All items are up-to-date across all workspaces")
        else:
            if all_changed:
                console.print(f"[green]✓[/green] Updated {len(all_changed)} item(s) across {len(config.repos.workspaces)} workspace(s)")
            elif all_up_to_date:
                console.print("[green]✓[/green] All items are up-to-date across all workspaces")

            if all_failed:
                console.print(f"[red]✗[/red] Failed to update {len(all_failed)} item(s)")

        # Show locations for each workspace
        if upgrade_skills:
            console.print(f"\n[dim]Updated {len(config.repos.workspaces)} workspace(s):[/dim]")
            for ws in config.repos.workspaces:
                console.print(f"[dim]  - {ws.name}: {ws.path}/.claude/skills/[/dim]")

        if upgrade_hierarchical_skills:
            from devflow.utils.paths import get_cs_home
            hierarchical_skills_dir = get_cs_home() / ".claude" / "skills"
            console.print(f"[dim]Hierarchical skills location: {hierarchical_skills_dir}[/dim]")


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
