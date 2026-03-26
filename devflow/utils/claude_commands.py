"""Utilities for managing bundled Claude Code skills.

This module provides functionality to install and upgrade the bundled skills
that ship with DevAIFlow.

Skills (including slash commands) are installed/upgraded to <workspace>/.claude/skills/
via the daf upgrade command or through the TUI upgrade button.

Note: As of Claude Code 2.1.3, slash commands and skills have been unified into
a single system. All slash commands are now skills with SKILL.md files.
"""

from pathlib import Path
from typing import List, Tuple, Optional, Dict
import shutil
from rich.console import Console

from devflow.utils.paths import get_claude_config_dir

console = Console()


def get_bundled_skills_dir() -> Path:
    """Get the path to the bundled skills directory.

    Returns:
        Path to devflow/cli_skills/ directory
    """
    # Get the daf package directory
    daf_package_dir = Path(__file__).parent.parent
    return daf_package_dir / "cli_skills"


def get_workspace_skills_dir(workspace: str) -> Path:
    """Get the path to the workspace .claude/skills directory.

    Args:
        workspace: Workspace root directory path

    Returns:
        Path to <workspace>/.claude/skills/ directory
    """
    workspace_path = Path(workspace).expanduser().resolve()
    return workspace_path / ".claude" / "skills"


def list_bundled_skills() -> List[Path]:
    """List all bundled skill directories.

    Returns:
        List of Path objects for skill directories in devflow/cli_skills/
    """
    bundled_dir = get_bundled_skills_dir()
    if not bundled_dir.exists():
        return []

    # Return only directories that contain a SKILL.md file
    return sorted([d for d in bundled_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()])


def _skill_has_name_field(skill_path: Path) -> bool:
    """Check if a skill has a 'name:' field in its SKILL.md frontmatter.

    DEPRECATED: Use _skill_is_user_invocable() instead.
    This function is kept for backwards compatibility.

    Args:
        skill_path: Path to skill directory

    Returns:
        True if skill has 'name:' field, False otherwise
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False

    content = skill_md.read_text()
    # Check for YAML frontmatter with name field
    if content.startswith("---\n"):
        try:
            # Extract frontmatter (between first two ---)
            parts = content.split("---\n", 2)
            if len(parts) >= 2:
                frontmatter = parts[1]
                # Simple check for name: field
                return "name:" in frontmatter
        except Exception:
            pass
    return False


def _skill_is_user_invocable(skill_path: Path) -> bool:
    """Check if a skill is user-invocable (can be invoked as slash command).

    Args:
        skill_path: Path to skill directory

    Returns:
        True if skill has 'user-invocable: true', False otherwise
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False

    content = skill_md.read_text()
    # Check for YAML frontmatter with user-invocable field
    if content.startswith("---\n"):
        try:
            # Extract frontmatter (between first two ---)
            parts = content.split("---\n", 2)
            if len(parts) >= 2:
                frontmatter = parts[1]
                # Check for user-invocable: true
                for line in frontmatter.split('\n'):
                    line = line.strip()
                    if line.startswith('user-invocable:'):
                        value = line.split(':', 1)[1].strip().lower()
                        return value == 'true'
        except Exception:
            pass
    return False


def list_slash_command_skills() -> List[Path]:
    """List bundled skills that are slash commands (user-invocable: true).

    Returns:
        List of Path objects for slash command skill directories
    """
    all_skills = list_bundled_skills()
    return [s for s in all_skills if _skill_is_user_invocable(s)]


def list_reference_skills() -> List[Path]:
    """List bundled skills that are reference skills (user-invocable: false).

    Returns:
        List of Path objects for reference skill directories
    """
    all_skills = list_bundled_skills()
    return [s for s in all_skills if not _skill_is_user_invocable(s)]


def install_or_upgrade_slash_commands(
    dry_run: bool = False,
    quiet: bool = False,
    target_dir: Optional[Path] = None
) -> Tuple[List[str], List[str], List[str]]:
    """Install or upgrade bundled slash commands to specified directory.

    Slash commands are skills with a 'name:' field in their frontmatter that should be
    globally available across all projects.

    Args:
        dry_run: If True, only report what would be changed without actually changing
        quiet: If True, suppress console output (errors still shown)
        target_dir: Target directory for installation (default: ~/.claude/skills/)

    Returns:
        Tuple of (installed/upgraded, up_to_date, failed) skill names
    """
    slash_commands = list_slash_command_skills()
    if not slash_commands:
        return ([], [], [])

    # Install to specified directory or default to user-level ~/.claude/skills/
    if target_dir is None:
        claude_config = get_claude_config_dir()
        skills_dir = claude_config / "skills"
    else:
        skills_dir = target_dir

    if not dry_run:
        skills_dir.mkdir(parents=True, exist_ok=True)

    changed: List[str] = []
    up_to_date: List[str] = []
    failed: List[str] = []

    for src_dir in slash_commands:
        skill_name = src_dir.name
        dest_dir = skills_dir / skill_name

        try:
            # Check if skill directory exists and compare contents
            if dest_dir.exists():
                is_up_to_date = _are_skill_dirs_identical(src_dir, dest_dir)
                if is_up_to_date:
                    up_to_date.append(skill_name)
                    continue

            # Install or upgrade skill directory
            if not dry_run:
                # Remove old version if exists
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                # Copy entire directory tree
                shutil.copytree(src_dir, dest_dir)

            changed.append(skill_name)

        except Exception as e:
            if not quiet:
                console.print(f"[red]✗[/red] Failed to process {skill_name}: {e}")
            failed.append(skill_name)

    return (changed, up_to_date, failed)


def install_or_upgrade_reference_skills(
    dry_run: bool = False,
    quiet: bool = False,
    target_dir: Optional[Path] = None
) -> Tuple[List[str], List[str], List[str]]:
    """Install or upgrade bundled reference skills to specified directory.

    Reference skills are skills WITHOUT a 'name:' field that provide context and
    documentation (like daf-cli, gh-cli, git-cli, glab-cli).

    Args:
        dry_run: If True, only report what would be changed without actually changing
        quiet: If True, suppress console output (errors still shown)
        target_dir: Target directory for installation (default: ~/.claude/skills/)

    Returns:
        Tuple of (installed/upgraded, up_to_date, failed) skill names
    """
    # Only install reference skills (those without 'name:' field)
    bundled_skills = list_reference_skills()
    if not bundled_skills:
        return ([], [], [])

    # Install to specified directory or default to user-level ~/.claude/skills/
    if target_dir is None:
        claude_config = get_claude_config_dir()
        skills_dir = claude_config / "skills"
    else:
        skills_dir = target_dir

    if not dry_run:
        skills_dir.mkdir(parents=True, exist_ok=True)

    changed: List[str] = []
    up_to_date: List[str] = []
    failed: List[str] = []

    for src_dir in bundled_skills:
        skill_name = src_dir.name
        dest_dir = skills_dir / skill_name

        try:
            # Check if skill directory exists and compare contents
            if dest_dir.exists():
                is_up_to_date = _are_skill_dirs_identical(src_dir, dest_dir)
                if is_up_to_date:
                    up_to_date.append(skill_name)
                    continue

            # Install or upgrade skill directory
            if not dry_run:
                # Remove old version if exists
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                # Copy entire directory tree
                shutil.copytree(src_dir, dest_dir)

            changed.append(skill_name)

        except Exception as e:
            if not quiet:
                console.print(f"[red]✗[/red] Failed to process {skill_name}: {e}")
            failed.append(skill_name)

    return (changed, up_to_date, failed)


def _register_skills_as_context_files(workspace: str, bundled_skills: List[Path]) -> None:
    """Register installed skills as hidden context files in configuration.

    This ensures skills are loaded as context files in Claude sessions, using the
    same mechanism as AGENTS.md, CLAUDE.md, etc.

    Args:
        workspace: Workspace root directory path
        bundled_skills: List of bundled skill directories to register
    """
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import ContextFile

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config or not config.context_files:
        return

    skills_dir = get_workspace_skills_dir(workspace)

    # Build list of skill context files to add
    skill_context_files = []
    for src_dir in bundled_skills:
        skill_name = src_dir.name
        skill_path = skills_dir / skill_name / "SKILL.md"

        # Extract description from SKILL.md frontmatter
        description = f"{skill_name} skill"
        try:
            with open(src_dir / "SKILL.md", 'r') as f:
                lines = f.readlines()
                if lines and lines[0].strip() == '---':
                    for line in lines[1:]:
                        if line.strip() == '---':
                            break
                        if line.startswith('description:'):
                            description = line.split('description:', 1)[1].strip()
                            break
        except Exception:
            pass

        skill_context_files.append(ContextFile(
            path=str(skill_path.resolve()),
            description=description,
            hidden=True
        ))

    # Remove existing skill entries (marked as hidden) to avoid duplicates
    existing_files = [f for f in config.context_files.files if not f.hidden]

    # Add new skill entries
    config.context_files.files = existing_files + skill_context_files

    # Save updated config
    config_loader.save_config(config)


def _are_skill_dirs_identical(src_dir: Path, dest_dir: Path) -> bool:
    """Check if two skill directories have identical contents.

    Args:
        src_dir: Source skill directory
        dest_dir: Destination skill directory

    Returns:
        True if all files in src_dir exist in dest_dir with same content
    """
    # Get all files in source directory (recursively)
    src_files = [f for f in src_dir.rglob("*") if f.is_file()]

    for src_file in src_files:
        # Calculate relative path
        rel_path = src_file.relative_to(src_dir)
        dest_file = dest_dir / rel_path

        # Check if file exists in destination
        if not dest_file.exists():
            return False

        # Compare file contents
        try:
            if src_file.read_text() != dest_file.read_text():
                return False
        except Exception:
            # If we can't read/compare, consider them different
            return False

    return True


def install_skills_to_agents(
    agents: List[str],
    level: str = 'global',
    project_path: Optional[Path] = None,
    skip_confirmation: bool = False,
    dry_run: bool = False,
    quiet: bool = False
) -> Dict[str, Tuple[List[str], List[str], List[str]]]:
    """Install bundled skills to multiple AI agents.

    This function installs both slash commands and reference skills to the specified
    agents at the specified level (global, project, or both).

    Args:
        agents: List of agent names (e.g., ['claude', 'cursor', 'windsurf'])
        level: Installation level - 'global', 'project', or 'both'
        project_path: Project directory path (required for 'project' and 'both' levels)
        skip_confirmation: Skip user confirmation prompt (for automation)
        dry_run: If True, only report what would be changed without actually changing
        quiet: If True, suppress console output (errors still shown)

    Returns:
        Dictionary mapping agent name to tuple of (changed, up_to_date, failed) skill names

    Raises:
        ValueError: If level is invalid or project_path is missing when required

    Example:
        >>> results = install_skills_to_agents(
        ...     agents=['claude', 'cursor'],
        ...     level='global'
        ... )
        >>> results['claude']  # (changed, up_to_date, failed)
        (['daf-cli', 'git-cli'], ['commit'], [])
    """
    from devflow.agent.skill_directories import get_skill_install_paths, validate_agent_names

    # Validate and normalize agent names
    validated_agents = validate_agent_names(agents)

    # Get installation paths for all agents
    try:
        install_paths = get_skill_install_paths(
            agents=validated_agents,
            level=level,
            project_path=project_path
        )
    except ValueError as e:
        raise ValueError(f"Invalid configuration: {e}")

    # Ask for confirmation unless skipped
    if not skip_confirmation and not dry_run and not quiet:
        from rich.prompt import Confirm

        console.print(f"\n[bold]Installing skills to {len(install_paths)} location(s):[/bold]")
        for agent, path in install_paths:
            console.print(f"  • {agent}: {path}")

        if not Confirm.ask("\nProceed with installation?", default=True):
            console.print("[yellow]Installation cancelled.[/yellow]")
            return {}

    # Track results per agent
    results_by_agent: Dict[str, Tuple[List[str], List[str], List[str]]] = {}

    # Get all bundled skills
    all_skills = list_bundled_skills()

    if not all_skills:
        if not quiet:
            console.print("[yellow]No bundled skills found to install.[/yellow]")
        return results_by_agent

    # Install to each agent and path
    for agent, target_dir in install_paths:
        if not quiet:
            console.print(f"\n[bold cyan]Installing to {agent} ({target_dir})...[/bold cyan]")

        # Create target directory
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        changed: List[str] = []
        up_to_date: List[str] = []
        failed: List[str] = []

        # Install each skill
        for src_dir in all_skills:
            skill_name = src_dir.name
            dest_dir = target_dir / skill_name

            try:
                # Check if skill directory exists and compare contents
                if dest_dir.exists():
                    is_up_to_date = _are_skill_dirs_identical(src_dir, dest_dir)
                    if is_up_to_date:
                        up_to_date.append(skill_name)
                        if not quiet:
                            console.print(f"  [dim]✓ {skill_name} (up-to-date)[/dim]")
                        continue

                # Install or upgrade skill directory
                if not dry_run:
                    # Remove old version if exists
                    if dest_dir.exists():
                        shutil.rmtree(dest_dir)
                    # Copy entire directory tree
                    shutil.copytree(src_dir, dest_dir)

                changed.append(skill_name)
                if not quiet:
                    action = "Would install" if dry_run else "Installed"
                    console.print(f"  [green]✓[/green] {action} {skill_name}")

            except Exception as e:
                if not quiet:
                    console.print(f"  [red]✗[/red] Failed to process {skill_name}: {e}")
                failed.append(skill_name)

        # Store results for this agent
        if agent not in results_by_agent:
            results_by_agent[agent] = ([], [], [])

        # Merge results (for 'both' level where same agent appears twice)
        prev_changed, prev_up_to_date, prev_failed = results_by_agent[agent]
        results_by_agent[agent] = (
            prev_changed + changed,
            prev_up_to_date + up_to_date,
            prev_failed + failed
        )

    # Print summary unless quiet
    if not quiet and not dry_run:
        console.print("\n[bold]Installation Summary:[/bold]")
        for agent, (changed, up_to_date, failed) in results_by_agent.items():
            total = len(changed) + len(up_to_date) + len(failed)
            console.print(f"\n{agent}:")
            if changed:
                console.print(f"  [green]✓[/green] Installed/Updated: {len(changed)}")
            if up_to_date:
                console.print(f"  [dim]Already up-to-date: {len(up_to_date)}[/dim]")
            if failed:
                console.print(f"  [red]✗[/red] Failed: {len(failed)}")

    elif not quiet and dry_run:
        console.print("\n[bold yellow]Dry run complete. No changes were made.[/bold yellow]")

    return results_by_agent


def get_skill_status(workspace: str, skill_name: str) -> Optional[str]:
    """Check if a skill is installed and whether it matches the bundled version.

    Args:
        workspace: Workspace root directory path
        skill_name: Name of skill directory (e.g., "daf-cli", "git-cli")

    Returns:
        "not_installed", "up_to_date", "outdated", or None if skill doesn't exist in bundle
    """
    bundled_dir = get_bundled_skills_dir()
    bundled_skill = bundled_dir / skill_name

    if not bundled_skill.exists() or not (bundled_skill / "SKILL.md").exists():
        return None

    skills_dir = get_workspace_skills_dir(workspace)
    installed_skill = skills_dir / skill_name

    if not installed_skill.exists():
        return "not_installed"

    # Compare directory contents
    if _are_skill_dirs_identical(bundled_skill, installed_skill):
        return "up_to_date"
    else:
        return "outdated"


def get_all_skill_statuses(workspace: str) -> dict[str, str]:
    """Get status of all bundled skills for a workspace.

    Args:
        workspace: Workspace root directory path

    Returns:
        Dictionary mapping skill names to their status
        ("not_installed", "up_to_date", "outdated")
    """
    bundled_skills = list_bundled_skills()
    statuses = {}

    for skill_path in bundled_skills:
        skill_name = skill_path.name
        status = get_skill_status(workspace, skill_name)
        if status:
            statuses[skill_name] = status

    return statuses


def build_claude_command(
    session_id: str,
    initial_prompt: str,
    project_path: Optional[str] = None,
    workspace_path: Optional[str] = None,
    config = None,
    model_provider_profile: Optional[dict] = None
) -> list:
    """Build Claude Code command with all necessary --add-dir flags for skills and context files.

    This centralizes the logic for building Claude commands to ensure all session types
    (daf new, daf jira new, daf investigate, daf open) consistently include all skills
    and context files.

    Skills discovery order (load order - generic before organization-specific):
    1. User-level: ~/.claude/skills/
    2. Workspace-level: <workspace>/.claude/skills/
    3. Hierarchical: $DEVAIFLOW_HOME/.claude/skills/ (organization-specific)
    4. Project-level: <project>/.claude/skills/

    Args:
        session_id: Claude session ID (UUID)
        initial_prompt: Initial prompt to send to Claude
        project_path: Project directory path (for project-level skills)
        workspace_path: Workspace directory path (for workspace-level skills)
        config: Configuration object (for hierarchical context files)
        model_provider_profile: Model provider profile dict (for --model flag)

    Returns:
        List of command arguments ready for subprocess.run()
    """
    # Build base command with model flag if specified
    if model_provider_profile and model_provider_profile.get("model_name"):
        cmd = ["claude", "--model", model_provider_profile["model_name"], "--session-id", session_id, initial_prompt]
    else:
        # Default: prompt must come BEFORE --add-dir flags (positional argument)
        cmd = ["claude", "--session-id", session_id, initial_prompt]

    # Collect all skills directories
    skills_dirs = []

    # 1. User-level skills: ~/.claude/skills/ (or $CLAUDE_CONFIG_DIR/skills/)
    claude_config = get_claude_config_dir()
    user_skills = claude_config / "skills"
    if user_skills.exists():
        skills_dirs.append(str(user_skills))

    # 2. Workspace-level skills: <workspace>/.claude/skills/
    if workspace_path:
        workspace_skills = get_workspace_skills_dir(workspace_path)
        if workspace_skills.exists():
            skills_dirs.append(str(workspace_skills))

    # 3. Hierarchical skills: $DEVAIFLOW_HOME/.claude/skills/ (organization-specific)
    from devflow.utils.paths import get_cs_home
    cs_home = get_cs_home()
    hierarchical_skills = cs_home / ".claude" / "skills"
    if hierarchical_skills.exists():
        skills_dirs.append(str(hierarchical_skills))

    # 4. Project-level skills: <project>/.claude/skills/
    if project_path:
        project_skills = Path(project_path) / ".claude" / "skills"
        if project_skills.exists():
            skills_dirs.append(str(project_skills))

    # Add all discovered skills directories
    for skills_dir in skills_dirs:
        cmd.extend(["--add-dir", skills_dir])

    # Add DEVAIFLOW_HOME for hierarchical context files (if they exist)
    # This allows reading ENTERPRISE.md, ORGANIZATION.md, TEAM.md, USER.md
    if config:
        from devflow.utils.context_files import load_hierarchical_context_files
        hierarchical_files = load_hierarchical_context_files(config)
        if hierarchical_files and cs_home.exists():
            # Only add if not already added (avoid duplication)
            if str(cs_home) not in skills_dirs:
                cmd.extend(["--add-dir", str(cs_home)])

    return cmd
