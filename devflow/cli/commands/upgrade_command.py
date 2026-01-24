"""Implementation of 'daf upgrade' command."""

from pathlib import Path
from rich.console import Console
from rich.table import Table

from devflow.config.loader import ConfigLoader
from devflow.utils.claude_commands import (
    install_or_upgrade_commands,
    install_or_upgrade_skills,
    get_all_command_statuses,
    get_all_skill_statuses,
)

console = Console()


def upgrade_commands_only(
    dry_run: bool = False,
    quiet: bool = False
) -> None:
    """Upgrade bundled Claude Code slash commands in workspace.

    This command will:
    - Install commands if they don't exist yet
    - Upgrade commands if they are outdated
    - Skip commands that are already up-to-date

    Args:
        dry_run: If True, only report what would be changed without actually changing
        quiet: If True, suppress console output (errors still shown)

    Note:
        In the future, daf upgrade will also upgrade the daf tool itself.
        For now, it only upgrades slash commands.
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config or not config.repos or not config.repos.get_default_workspace_path():
        console.print("[red]✗[/red] Workspace not configured")
        console.print("[dim]Run 'daf config tui' to configure your workspace[/dim]")
        return

    workspace = config.repos.get_default_workspace_path()

    # Verify workspace exists
    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.exists():
        console.print(f"[red]✗[/red] Workspace directory does not exist: {workspace}")
        console.print("[dim]Please update your workspace configuration with 'daf config tui'[/dim]")
        return

    if not quiet:
        if dry_run:
            console.print("[cyan]Checking for command updates (dry run)...[/cyan]")
        else:
            console.print("[cyan]Upgrading bundled slash commands...[/cyan]")
        console.print(f"[dim]Workspace: {workspace}[/dim]")
        console.print()

    # Get current status before upgrade
    statuses_before = get_all_command_statuses(workspace)

    # Install or upgrade commands
    try:
        changed, up_to_date, failed = install_or_upgrade_commands(
            workspace,
            dry_run=dry_run,
            quiet=quiet
        )
    except FileNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        return
    except Exception as e:
        console.print(f"[red]✗[/red] Upgrade failed: {e}")
        raise

    # Report results
    if not quiet:
        if dry_run:
            console.print("[bold]Would perform these changes:[/bold]")
        else:
            console.print("[bold]Results:[/bold]")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Command", style="cyan")
        table.add_column("Status Before")
        table.add_column("Status After")

        # Show changed commands
        for cmd_name in changed:
            status_before = statuses_before.get(cmd_name, "not_installed")
            status_after = "up_to_date" if not dry_run else status_before

            if status_before == "not_installed":
                status_before_display = "[yellow]not installed[/yellow]"
                status_after_display = "[green]installed[/green]" if not dry_run else "[yellow]would install[/yellow]"
            else:
                status_before_display = "[yellow]outdated[/yellow]"
                status_after_display = "[green]upgraded[/green]" if not dry_run else "[yellow]would upgrade[/yellow]"

            table.add_row(cmd_name, status_before_display, status_after_display)

        # Show up-to-date commands
        for cmd_name in up_to_date:
            table.add_row(cmd_name, "[green]up-to-date[/green]", "[dim]no change[/dim]")

        # Show failed commands
        for cmd_name in failed:
            status_before = statuses_before.get(cmd_name, "unknown")
            table.add_row(cmd_name, f"[dim]{status_before}[/dim]", "[red]failed[/red]")

        console.print(table)
        console.print()

        # Summary
        if dry_run:
            if changed:
                console.print(f"[yellow]Would change {len(changed)} command(s)[/yellow]")
                console.print("[dim]Run without --dry-run to apply changes[/dim]")
            else:
                console.print("[green]✓[/green] All commands are up-to-date")
        else:
            if changed:
                console.print(f"[green]✓[/green] Updated {len(changed)} command(s)")
            elif up_to_date:
                console.print("[green]✓[/green] All commands are up-to-date")

            if failed:
                console.print(f"[red]✗[/red] Failed to update {len(failed)} command(s)")

        # Show location
        commands_dir = workspace_path / ".claude" / "commands"
        console.print(f"[dim]Commands location: {commands_dir}[/dim]")


def upgrade_all(
    dry_run: bool = False,
    quiet: bool = False,
    upgrade_commands: bool = True,
    upgrade_skills: bool = True
) -> None:
    """Upgrade bundled Claude Code slash commands and/or skills in workspace.

    This command will:
    - Install commands/skills if they don't exist yet
    - Upgrade commands/skills if they are outdated
    - Skip commands/skills that are already up-to-date

    Args:
        dry_run: If True, only report what would be changed without actually changing
        quiet: If True, suppress console output (errors still shown)
        upgrade_commands: If True, upgrade bundled slash commands
        upgrade_skills: If True, upgrade bundled skills
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config or not config.repos or not config.repos.get_default_workspace_path():
        console.print("[red]✗[/red] Workspace not configured")
        console.print("[dim]Run 'daf config tui' to configure your workspace[/dim]")
        return

    workspace = config.repos.get_default_workspace_path()

    # Verify workspace exists
    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.exists():
        console.print(f"[red]✗[/red] Workspace directory does not exist: {workspace}")
        console.print("[dim]Please update your workspace configuration with 'daf config tui'[/dim]")
        return

    if not quiet:
        if dry_run:
            console.print("[cyan]Checking for updates (dry run)...[/cyan]")
        else:
            console.print("[cyan]Upgrading bundled slash commands and skills...[/cyan]")
        console.print(f"[dim]Workspace: {workspace}[/dim]")
        console.print()

    # Track overall results
    all_changed = []
    all_up_to_date = []
    all_failed = []

    # Upgrade commands if requested
    if upgrade_commands:
        if not quiet:
            console.print("[bold]Slash Commands:[/bold]")

        statuses_before = get_all_command_statuses(workspace)

        try:
            changed, up_to_date, failed = install_or_upgrade_commands(
                workspace,
                dry_run=dry_run,
                quiet=quiet
            )
            all_changed.extend([f"cmd:{name}" for name in changed])
            all_up_to_date.extend([f"cmd:{name}" for name in up_to_date])
            all_failed.extend([f"cmd:{name}" for name in failed])

            _print_upgrade_table(
                changed, up_to_date, failed, statuses_before,
                item_type="command", dry_run=dry_run, quiet=quiet
            )

        except FileNotFoundError as e:
            console.print(f"[red]✗[/red] {e}")
            return
        except Exception as e:
            console.print(f"[red]✗[/red] Upgrade failed: {e}")
            raise

        if not quiet:
            console.print()

    # Upgrade skills if requested
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
            all_changed.extend([f"skill:{name}" for name in changed])
            all_up_to_date.extend([f"skill:{name}" for name in up_to_date])
            all_failed.extend([f"skill:{name}" for name in failed])

            _print_upgrade_table(
                changed, up_to_date, failed, statuses_before,
                item_type="skill", dry_run=dry_run, quiet=quiet
            )

        except FileNotFoundError as e:
            console.print(f"[red]✗[/red] {e}")
            return
        except Exception as e:
            console.print(f"[red]✗[/red] Upgrade failed: {e}")
            raise

        if not quiet:
            console.print()

    # Overall summary
    if not quiet:
        console.print("[bold]Summary:[/bold]")
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

        # Show locations
        if upgrade_commands:
            commands_dir = workspace_path / ".claude" / "commands"
            console.print(f"[dim]Commands location: {commands_dir}[/dim]")
        if upgrade_skills:
            skills_dir = workspace_path / ".claude" / "skills"
            console.print(f"[dim]Skills location: {skills_dir}[/dim]")


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
