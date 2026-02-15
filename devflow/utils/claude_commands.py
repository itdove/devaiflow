"""Utilities for managing bundled Claude Code skills.

This module provides functionality to install and upgrade the bundled skills
that ship with DevAIFlow.

Skills (including slash commands) are installed/upgraded to <workspace>/.claude/skills/
via the daf upgrade command or through the TUI upgrade button.

Note: As of Claude Code 2.1.3, slash commands and skills have been unified into
a single system. All slash commands are now skills with SKILL.md files.
"""

from pathlib import Path
from typing import List, Tuple, Optional
import shutil
from rich.console import Console

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


def install_or_upgrade_skills(
    workspace: str,
    dry_run: bool = False,
    quiet: bool = False
) -> Tuple[List[str], List[str], List[str]]:
    """Install or upgrade bundled skills to workspace .claude/skills directory.

    This function installs skill directories with all their contents and also
    registers them as hidden context files in the configuration.

    Args:
        workspace: Workspace root directory path
        dry_run: If True, only report what would be changed without actually changing
        quiet: If True, suppress console output (errors still shown)

    Returns:
        Tuple of (installed/upgraded, up_to_date, failed) skill names

    Raises:
        FileNotFoundError: If workspace directory doesn't exist
    """
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import ContextFile

    workspace_path = Path(workspace).expanduser().resolve()
    if not workspace_path.exists():
        raise FileNotFoundError(f"Workspace directory does not exist: {workspace}")

    bundled_skills = list_bundled_skills()
    if not bundled_skills:
        return ([], [], [])

    # Ensure .claude/skills directory exists
    skills_dir = get_workspace_skills_dir(workspace)
    if not dry_run:
        skills_dir.mkdir(parents=True, exist_ok=True)

    changed: List[str] = []  # Installed or upgraded
    up_to_date: List[str] = []  # Already up-to-date
    failed: List[str] = []

    for src_dir in bundled_skills:
        skill_name = src_dir.name
        dest_dir = skills_dir / skill_name

        try:
            # Check if skill directory exists and compare contents
            if dest_dir.exists():
                # Compare by checking if all files in source exist in dest with same content
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

    # After installing/upgrading skills, register them as hidden context files
    if not dry_run and (changed or up_to_date):
        try:
            _register_skills_as_context_files(workspace, bundled_skills)
        except Exception as e:
            if not quiet:
                console.print(f"[yellow]⚠[/yellow] Warning: Could not register skills in config: {e}")

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
    config = None
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

    Returns:
        List of command arguments ready for subprocess.run()
    """
    # Build base command: prompt must come BEFORE --add-dir flags (positional argument)
    cmd = ["claude", "--session-id", session_id, initial_prompt]

    # Collect all skills directories
    skills_dirs = []

    # 1. User-level skills: ~/.claude/skills/
    user_skills = Path.home() / ".claude" / "skills"
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
