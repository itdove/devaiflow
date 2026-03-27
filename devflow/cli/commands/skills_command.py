"""Implementation of 'daf skills' command group."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from devflow.config.loader import ConfigLoader
from devflow.utils.claude_commands import install_skills_to_agents

console = Console()


@click.command()
@click.argument("skill_name", required=False)
@click.option("--install", is_flag=True, help="Install assets (default action)")
@click.option("--upgrade", is_flag=True, help="Upgrade assets (same as --install)")
@click.option("--uninstall", is_flag=True, help="Uninstall assets")
@click.option("--list", "list_skills", is_flag=True, help="List available or installed assets")
@click.option("--available", is_flag=True, help="Show available bundled skills (use with --list)")
@click.option("--installed", is_flag=True, help="Show installed skills (use with --list)")
@click.option("--type", "asset_type", type=click.Choice(['all', 'bundled', 'hierarchical']), help="Type of assets to install (default: all)")
@click.option("--dry-run", is_flag=True, help="Show what would be changed without actually changing")
@click.option("--agent", type=str, help="AI agent to target (claude, cursor, windsurf, copilot, aider, continue)")
@click.option("--all-agents", is_flag=True, help="Target all supported agents")
@click.option("--level", type=click.Choice(['global', 'project', 'both']), help="Installation level (default: global)")
@click.option("--project-path", type=click.Path(), help="Project directory for project-level operations")
@click.option("--no-sync-json", is_flag=True, help="Skip JSON config sync (hierarchical assets only)")
@click.option("--list-backups", is_flag=True, help="List available config backups")
@click.option("--restore-backup", type=str, help="Restore config file from backup (e.g., enterprise.json.2026-03-26T19:45:00.backup)")
def assets(
    skill_name: Optional[str],
    install: bool,
    upgrade: bool,
    uninstall: bool,
    list_skills: bool,
    available: bool,
    installed: bool,
    asset_type: Optional[str],
    dry_run: bool,
    agent: Optional[str],
    all_agents: bool,
    level: Optional[str],
    project_path: Optional[str],
    no_sync_json: bool,
    list_backups: bool,
    restore_backup: Optional[str]
) -> None:
    """Manage DevAIFlow assets (skills and config) for AI agents.

    Install, upgrade, or uninstall bundled skills and hierarchical configuration
    to one or more AI agents.

    \b
    Asset Types:
        - bundled: Skills bundled with DevAIFlow (daf-help, daf-cli, etc.)
        - hierarchical: Organization-specific skills from config files
        - all: Both bundled and hierarchical (default)

    \b
    Examples:
        # Install all assets to Claude (default)
        daf assets

        # Install only bundled skills
        daf assets --type bundled

        # Install only hierarchical skills
        daf assets --type hierarchical

        # Install all assets to Cursor
        daf assets --agent cursor

        # Install all assets to all agents
        daf assets --all-agents

        # Install specific skill to Claude
        daf assets daf-help

        # Install specific skill to Cursor
        daf assets daf-help --agent cursor

        # Uninstall all assets from Cursor
        daf assets --uninstall --agent cursor

        # Uninstall specific skill from all agents
        daf assets daf-help --uninstall --all-agents

        # Install to project directory
        daf assets --level project --project-path .

        # Preview changes without applying
        daf assets --dry-run --all-agents

        # List available bundled skills
        daf assets --list --available

        # List installed skills for all agents
        daf assets --list --installed

        # List installed skills for specific agent
        daf assets --list --installed --agent cursor

        # List available config backups
        daf assets --list-backups

        # Restore config from backup
        daf assets --restore-backup enterprise.json.2026-03-26T19:45:00.backup
    """
    # Handle backup operations first (standalone actions)
    if list_backups:
        _list_config_backups()
        return

    if restore_backup:
        _restore_config_backup(restore_backup)
        return

    # Handle list action (doesn't need config validation)
    if list_skills:
        # Determine which agents to list for
        agents_list = None
        if all_agents:
            from devflow.agent.skill_directories import SUPPORTED_AGENTS
            agents_list = [a for a in SUPPORTED_AGENTS if a != 'github-copilot']
        elif agent:
            agents_list = [agent]
        else:
            agents_list = ['claude']  # Default to Claude

        # Determine installation level for listing
        install_level = level or 'global'

        # Validate project_path if needed
        project_path_obj = None
        if install_level in ('project', 'both'):
            if not project_path:
                console.print("[red]✗[/red] --project-path is required for level=project or level=both")
                return
            project_path_obj = Path(project_path).expanduser().resolve()
            if not project_path_obj.exists():
                console.print(f"[red]✗[/red] Project path does not exist: {project_path_obj}")
                return
            if not project_path_obj.is_dir():
                console.print(f"[red]✗[/red] Project path is not a directory: {project_path_obj}")
                return

        _list_skills(
            available=available,
            installed=installed,
            agents=agents_list,
            level=install_level,
            project_path=project_path_obj
        )
        return

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

    # Determine action (default: install)
    action = "install"
    if uninstall:
        action = "uninstall"
    elif upgrade:
        action = "upgrade"  # Same as install, just clearer intent
    elif install:
        action = "install"

    # Determine which agents to target
    agents_list = None
    if all_agents:
        from devflow.agent.skill_directories import SUPPORTED_AGENTS
        agents_list = [a for a in SUPPORTED_AGENTS if a != 'github-copilot']
    elif agent:
        agents_list = [agent]
    # else: agents_list remains None, will default to ['claude']

    # Determine installation level
    install_level = level or 'global'

    # Validate project_path if needed
    project_path_obj = None
    if install_level in ('project', 'both'):
        if not project_path:
            console.print("[red]✗[/red] --project-path is required for level=project or level=both")
            return

        project_path_obj = Path(project_path).expanduser().resolve()
        if not project_path_obj.exists():
            console.print(f"[red]✗[/red] Project path does not exist: {project_path_obj}")
            return
        if not project_path_obj.is_dir():
            console.print(f"[red]✗[/red] Project path is not a directory: {project_path_obj}")
            return

    # Default asset_type to 'all' if not specified
    if asset_type is None:
        asset_type = 'all'

    # Execute action
    if action == "uninstall":
        _uninstall_skills(
            skill_name=skill_name,
            agents=agents_list,
            level=install_level,
            project_path=project_path_obj,
            dry_run=dry_run
        )
    else:
        # Install or upgrade
        _install_skills(
            skill_name=skill_name,
            agents=agents_list,
            level=install_level,
            project_path=project_path_obj,
            dry_run=dry_run,
            asset_type=asset_type,
            no_sync_json=no_sync_json
        )


def _install_skills(
    skill_name: Optional[str],
    agents: Optional[list],
    level: str,
    project_path: Optional[Path],
    dry_run: bool,
    asset_type: str = 'all',
    no_sync_json: bool = False
) -> None:
    """Install or upgrade skills.

    Args:
        skill_name: Specific skill name to install, or None for all
        agents: List of agent names to target
        level: Installation level ('global', 'project', or 'both')
        project_path: Project directory path (required for 'project' or 'both' level)
        dry_run: If True, only show what would be installed
        asset_type: Type of assets to install ('all', 'bundled', 'hierarchical')
        no_sync_json: If True, skip JSON config sync for hierarchical assets
    """
    if skill_name:
        # Install specific skill (only bundled skills have names, so install bundled + hierarchical)
        _install_specific_skill(skill_name, agents, level, project_path, dry_run, asset_type)
    else:
        # Install all skills
        _install_all_skills(agents, level, project_path, dry_run, asset_type, no_sync_json)


def _install_all_skills(
    agents: Optional[list],
    level: str,
    project_path: Optional[Path],
    dry_run: bool,
    asset_type: str = 'all',
    no_sync_json: bool = False
) -> None:
    """Install all bundled skills and/or hierarchical skills.

    Args:
        agents: List of agent names to target
        level: Installation level ('global', 'project', or 'both')
        project_path: Project directory path
        dry_run: If True, only show what would be installed
        asset_type: Type of assets to install ('all', 'bundled', 'hierarchical')
        no_sync_json: If True, skip JSON config sync for hierarchical assets
    """
    install_bundled = asset_type in ('all', 'bundled')
    install_hierarchical = asset_type in ('all', 'hierarchical')

    if not dry_run:
        if asset_type == 'bundled':
            console.print("[cyan]Installing bundled skills...[/cyan]")
        elif asset_type == 'hierarchical':
            console.print("[cyan]Installing hierarchical skills...[/cyan]")
        else:
            console.print("[cyan]Installing bundled and hierarchical skills...[/cyan]")
        console.print()
    else:
        console.print("[cyan]Checking for updates (dry run)...[/cyan]")
        console.print()

    try:
        # Install bundled skills if requested (split into slash commands and reference skills)
        if install_bundled:
            from devflow.agent.skill_directories import get_skill_install_paths
            from devflow.utils.claude_commands import (
                install_or_upgrade_slash_commands,
                install_or_upgrade_reference_skills
            )

            # Get installation paths for all agents
            agents_list = agents or ['claude']
            install_paths = get_skill_install_paths(
                agents=agents_list,
                level=level,
                project_path=project_path
            )

            # Install slash commands to each location
            all_slash_changed = []
            all_slash_up_to_date = []
            all_slash_failed = []

            for agent_name, target_dir in install_paths:
                if not dry_run:
                    target_dir.mkdir(parents=True, exist_ok=True)

                changed, up_to_date, failed = install_or_upgrade_slash_commands(
                    dry_run=dry_run,
                    quiet=True,
                    target_dir=target_dir
                )
                all_slash_changed.extend(changed)
                all_slash_up_to_date.extend(up_to_date)
                all_slash_failed.extend(failed)

            # Print slash commands table
            _print_skills_table(
                "Slash Commands",
                list(set(all_slash_changed)),
                list(set(all_slash_up_to_date)),
                list(set(all_slash_failed)),
                {},
                dry_run
            )

            # Install reference skills to each location
            all_ref_changed = []
            all_ref_up_to_date = []
            all_ref_failed = []

            for agent_name, target_dir in install_paths:
                changed, up_to_date, failed = install_or_upgrade_reference_skills(
                    dry_run=dry_run,
                    quiet=True,
                    target_dir=target_dir
                )
                all_ref_changed.extend(changed)
                all_ref_up_to_date.extend(up_to_date)
                all_ref_failed.extend(failed)

            # Print reference skills table
            _print_skills_table(
                "Reference Skills",
                list(set(all_ref_changed)),
                list(set(all_ref_up_to_date)),
                list(set(all_ref_failed)),
                {},
                dry_run
            )

        # Install hierarchical skills if requested
        if install_hierarchical:
            _install_hierarchical_skills(dry_run, sync_json=not no_sync_json)

    except Exception as e:
        console.print(f"[red]✗[/red] Installation failed: {e}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


def _install_specific_skill(
    skill_name: str,
    agents: Optional[list],
    level: str,
    project_path: Optional[Path],
    dry_run: bool,
    asset_type: str = 'all'
) -> None:
    """Install a specific skill by name.

    Args:
        skill_name: Name of the skill to install
        agents: List of agent names to target
        level: Installation level ('global', 'project', or 'both')
        project_path: Project directory path
        dry_run: If True, only show what would be installed
        asset_type: Type of assets to install ('all', 'bundled', 'hierarchical')
    """
    from devflow.utils.claude_commands import get_bundled_skills_dir
    from devflow.agent.skill_directories import get_skill_install_paths
    import shutil

    install_bundled = asset_type in ('all', 'bundled')
    install_hierarchical = asset_type in ('all', 'hierarchical')

    # Find the skill in bundled skills
    bundled_dir = get_bundled_skills_dir()
    skill_dir = bundled_dir / skill_name

    if not skill_dir.exists() or not (skill_dir / "SKILL.md").exists():
        console.print(f"[red]✗[/red] Skill '{skill_name}' not found in bundled skills")
        console.print(f"[dim]Available skills in: {bundled_dir}[/dim]")
        return

    # Get installation paths
    agents_list = agents or ['claude']
    try:
        install_paths = get_skill_install_paths(
            agents=agents_list,
            level=level,
            project_path=project_path
        )
    except ValueError as e:
        console.print(f"[red]✗[/red] Invalid configuration: {e}")
        return

    if not dry_run:
        if asset_type == 'bundled':
            console.print(f"[cyan]Installing skill '{skill_name}'...[/cyan]")
        elif asset_type == 'hierarchical':
            console.print(f"[cyan]Installing hierarchical skills...[/cyan]")
        else:
            console.print(f"[cyan]Installing skill '{skill_name}' and hierarchical skills...[/cyan]")
        console.print()
    else:
        console.print(f"[cyan]Checking skill '{skill_name}' (dry run)...[/cyan]")
        console.print()

    # Install bundled skill if requested
    if install_bundled:
        # Install to each agent and path
        for agent_name, target_dir in install_paths:
            console.print(f"[bold cyan]{'Would install' if dry_run else 'Installing'} to {agent_name} ({target_dir})...[/bold cyan]")

            dest_dir = target_dir / skill_name

            try:
                if not dry_run:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    if dest_dir.exists():
                        shutil.rmtree(dest_dir)
                    shutil.copytree(skill_dir, dest_dir)
                    console.print(f"  [green]✓[/green] Installed {skill_name}")
                else:
                    if dest_dir.exists():
                        console.print(f"  [yellow]Would upgrade[/yellow] {skill_name}")
                    else:
                        console.print(f"  [green]Would install[/green] {skill_name}")

            except Exception as e:
                console.print(f"  [red]✗[/red] Failed: {e}")

    if dry_run:
        console.print("\n[bold yellow]Dry run complete. No changes were made.[/bold yellow]")

    # Install hierarchical skills if requested (from config files)
    if install_hierarchical:
        _install_hierarchical_skills(dry_run, sync_json=True)


def _uninstall_skills(
    skill_name: Optional[str],
    agents: Optional[list],
    level: str,
    project_path: Optional[Path],
    dry_run: bool
) -> None:
    """Uninstall skills."""
    from devflow.agent.skill_directories import get_skill_install_paths
    import shutil

    agents_list = agents or ['claude']

    # Get installation paths
    try:
        install_paths = get_skill_install_paths(
            agents=agents_list,
            level=level,
            project_path=project_path
        )
    except ValueError as e:
        console.print(f"[red]✗[/red] Invalid configuration: {e}")
        return

    if not dry_run:
        console.print("[cyan]Uninstalling skills...[/cyan]")
        console.print()
    else:
        console.print("[cyan]Checking what would be uninstalled (dry run)...[/cyan]")
        console.print()

    # Uninstall from each agent and path
    for agent_name, target_dir in install_paths:
        console.print(f"[bold cyan]{'Would uninstall from' if dry_run else 'Uninstalling from'} {agent_name} ({target_dir})...[/bold cyan]")

        if skill_name:
            # Uninstall specific skill
            skill_dir = target_dir / skill_name
            if skill_dir.exists():
                if not dry_run:
                    shutil.rmtree(skill_dir)
                    console.print(f"  [green]✓[/green] Uninstalled {skill_name}")
                else:
                    console.print(f"  [yellow]Would uninstall[/yellow] {skill_name}")
            else:
                console.print(f"  [dim]Skill '{skill_name}' not installed[/dim]")
        else:
            # Uninstall all bundled skills
            if not target_dir.exists():
                console.print(f"  [dim]No skills directory found[/dim]")
                continue

            # Find all skill directories
            skills = [d for d in target_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]

            if not skills:
                console.print(f"  [dim]No skills installed[/dim]")
                continue

            for skill_dir in skills:
                if not dry_run:
                    shutil.rmtree(skill_dir)
                    console.print(f"  [green]✓[/green] Uninstalled {skill_dir.name}")
                else:
                    console.print(f"  [yellow]Would uninstall[/yellow] {skill_dir.name}")

    if dry_run:
        console.print("\n[bold yellow]Dry run complete. No changes were made.[/bold yellow]")
    else:
        console.print("\n[bold green]✓[/bold green] Uninstall complete")


def _print_skills_table(
    title: str,
    changed: list,
    up_to_date: list,
    failed: list,
    statuses_before: dict,
    dry_run: bool
) -> None:
    """Print detailed table for skill installation results.

    Args:
        title: Table title (e.g., "Slash Commands", "Reference Skills")
        changed: List of changed skill names
        up_to_date: List of up-to-date skill names
        failed: List of failed skill names
        statuses_before: Dict mapping skill names to status before upgrade
        dry_run: Whether this was a dry run
    """
    from rich.table import Table

    if not (changed or up_to_date or failed):
        return

    console.print(f"\n[bold]{title}:[/bold]\n")

    # Determine if this is hierarchical skills (need Type column)
    is_hierarchical = "Hierarchical" in title

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Skill", style="cyan")
    if is_hierarchical:
        table.add_column("Type")
    table.add_column("Status Before")
    table.add_column("Status After")

    def get_item_type(name: str) -> str:
        """Determine the type of hierarchical item based on name."""
        if name.endswith('.json'):
            return "[blue]JSON Config[/blue]"
        elif name.endswith('.md'):
            return "[magenta]Context[/magenta]"
        else:
            return "[cyan]Skill[/cyan]"

    # Show changed items
    for skill_name in sorted(changed):
        status_before = statuses_before.get(skill_name, "not_installed")

        if status_before == "not_installed":
            status_before_display = "[yellow]not installed[/yellow]"
            status_after_display = "[green]installed[/green]" if not dry_run else "[yellow]would install[/yellow]"
        else:
            status_before_display = "[yellow]outdated[/yellow]"
            status_after_display = "[green]upgraded[/green]" if not dry_run else "[yellow]would upgrade[/yellow]"

        if is_hierarchical:
            table.add_row(skill_name, get_item_type(skill_name), status_before_display, status_after_display)
        else:
            table.add_row(skill_name, status_before_display, status_after_display)

    # Show up-to-date items
    for skill_name in sorted(up_to_date):
        if is_hierarchical:
            table.add_row(skill_name, get_item_type(skill_name), "[green]up-to-date[/green]", "[dim]no change[/dim]")
        else:
            table.add_row(skill_name, "[green]up-to-date[/green]", "[dim]no change[/dim]")

    # Show failed items
    for skill_name in sorted(failed):
        status_before = statuses_before.get(skill_name, "unknown")
        if is_hierarchical:
            table.add_row(skill_name, get_item_type(skill_name), f"[dim]{status_before}[/dim]", "[red]failed[/red]")
        else:
            table.add_row(skill_name, f"[dim]{status_before}[/dim]", "[red]failed[/red]")

    console.print(table)
    console.print()


def _install_hierarchical_skills(dry_run: bool, sync_json: bool = True) -> None:
    """Install hierarchical skills from configuration files."""
    from devflow.utils.hierarchical_skills import (
        install_hierarchical_skills,
        get_hierarchical_skill_statuses
    )

    # Get status before installation
    statuses_before = get_hierarchical_skill_statuses()

    try:
        changed, up_to_date, failed = install_hierarchical_skills(
            dry_run=dry_run,
            quiet=False,
            sync_json=sync_json
        )

        # Display detailed table using shared function
        _print_skills_table(
            "Hierarchical Skills (from config files)",
            changed,
            up_to_date,
            failed,
            statuses_before,
            dry_run
        )

    except Exception as e:
        console.print(f"\n[red]✗[/red] Hierarchical skill installation failed: {e}")


def _list_skills(
    available: bool,
    installed: bool,
    agents: list,
    level: str,
    project_path: Optional[Path]
) -> None:
    """List available or installed skills."""
    from devflow.utils.claude_commands import get_bundled_skills_dir
    from devflow.agent.skill_directories import get_skill_install_paths
    from rich.table import Table

    # Default to showing available skills if neither flag is specified
    if not available and not installed:
        available = True

    # List available bundled skills
    if available:
        console.print("[bold cyan]Available Bundled Skills:[/bold cyan]\n")

        bundled_dir = get_bundled_skills_dir()
        skills = sorted([
            d.name for d in bundled_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ])

        if not skills:
            console.print("[dim]No bundled skills found[/dim]")
        else:
            table = Table(show_header=True, header_style="bold")
            table.add_column("Skill Name", style="cyan")
            table.add_column("Type", style="yellow")

            for skill in skills:
                # Determine type based on naming convention
                # Skills starting with "daf-" are user-invocable commands
                # Others (gh-cli, git-cli, glab-cli) are reference documentation
                if skill.startswith("daf-"):
                    skill_type = "Command"
                else:
                    skill_type = "Reference"

                table.add_row(skill, skill_type)

            console.print(table)
            console.print(f"\n[dim]Total: {len(skills)} skills[/dim]")

    # List installed skills
    if installed:
        if available:
            console.print()  # Add spacing between sections

        console.print("[bold cyan]Installed Skills:[/bold cyan]\n")

        try:
            install_paths = get_skill_install_paths(
                agents=agents,
                level=level,
                project_path=project_path
            )
        except ValueError as e:
            console.print(f"[red]✗[/red] Invalid configuration: {e}")
            return

        any_skills_found = False
        for agent_name, target_dir in install_paths:
            # Find all installed skills
            if not target_dir.exists():
                console.print(f"[bold]{agent_name}[/bold] ([dim]{target_dir}[/dim]): [dim]No skills directory[/dim]")
                continue

            skills = sorted([
                d.name for d in target_dir.iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()
            ])

            if not skills:
                console.print(f"[bold]{agent_name}[/bold] ([dim]{target_dir}[/dim]): [dim]No skills installed[/dim]")
            else:
                any_skills_found = True
                console.print(f"[bold]{agent_name}[/bold] ([dim]{target_dir}[/dim]):")
                for skill in skills:
                    console.print(f"  [green]✓[/green] {skill}")
                console.print(f"  [dim]Total: {len(skills)} skills[/dim]")

            console.print()  # Add spacing between agents

        if not any_skills_found:
            console.print("[yellow]⚠[/yellow] No skills installed for the specified agents and level")


def _list_config_backups() -> None:
    """List available config backups."""
    from devflow.utils.hierarchical_skills import list_backups
    from rich.table import Table

    console.print("[bold cyan]Available Config Backups:[/bold cyan]\n")

    backups = list_backups()  # List all backups

    if not backups:
        console.print("[dim]No backups found[/dim]")
        return

    # Group backups by original filename
    from collections import defaultdict
    backups_by_file = defaultdict(list)

    for backup_path in backups:
        # Extract original filename from backup
        # Format: filename.YYYY-MM-DDTHH:MM:SS.backup
        backup_name = backup_path.name
        if backup_name.endswith('.backup'):
            # Remove .backup extension and timestamp
            without_backup_ext = backup_name[:-7]
            parts = without_backup_ext.rsplit('.', 1)
            if len(parts) == 2:
                original_filename = parts[0]
                backups_by_file[original_filename].append(backup_path)

    # Display backups in a table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Original File", style="cyan")
    table.add_column("Backup Filename", style="yellow")
    table.add_column("Created", style="dim")

    for original_filename in sorted(backups_by_file.keys()):
        file_backups = sorted(backups_by_file[original_filename], key=lambda p: p.stat().st_mtime, reverse=True)

        for i, backup_path in enumerate(file_backups):
            import datetime
            mtime = datetime.datetime.fromtimestamp(backup_path.stat().st_mtime)
            created_str = mtime.strftime("%Y-%m-%d %H:%M:%S")

            # Only show original filename for first entry in group
            if i == 0:
                table.add_row(original_filename, backup_path.name, created_str)
            else:
                table.add_row("", backup_path.name, created_str)

    console.print(table)
    console.print(f"\n[dim]Total: {len(backups)} backup(s)[/dim]")
    console.print(f"[dim]To restore: daf assets --restore-backup <backup-filename>[/dim]")


def _restore_config_backup(backup_filename: str) -> None:
    """Restore a config file from backup."""
    from devflow.utils.hierarchical_skills import restore_backup, list_backups
    from devflow.utils.paths import get_cs_home

    cs_home = get_cs_home()
    backup_dir = cs_home / "backups"
    backup_path = backup_dir / backup_filename

    if not backup_path.exists():
        console.print(f"[red]✗[/red] Backup not found: {backup_filename}")
        console.print("\n[dim]Available backups:[/dim]")
        backups = list_backups()
        if backups:
            for backup in backups[:5]:  # Show first 5
                console.print(f"  [dim]{backup.name}[/dim]")
            if len(backups) > 5:
                console.print(f"  [dim]... and {len(backups) - 5} more[/dim]")
            console.print("\n[dim]Run 'daf assets --list-backups' to see all backups[/dim]")
        else:
            console.print("  [dim]No backups found[/dim]")
        return

    try:
        # Restore the backup
        restored_path = restore_backup(backup_path)
        console.print(f"[green]✓[/green] Restored {restored_path.name} from {backup_filename}")
        console.print(f"[dim]Location: {restored_path}[/dim]")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to restore backup: {e}")
