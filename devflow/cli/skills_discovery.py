"""Utility for discovering skills from all hierarchical locations."""

from pathlib import Path
from typing import Optional


def discover_skills(project_path: Optional[str] = None, workspace: Optional[str] = None) -> list[tuple[str, str]]:
    """Discover all skills from user-level, workspace-level, hierarchical (DEVAIFLOW_HOME), and project-level locations.

    Discovery order (guarantees load order - generic skills before organization-specific extensions):
    1. User-level generic skills: ~/.claude/skills/ (alphabetical)
    2. Workspace-level skills: <workspace>/.claude/skills/ (alphabetical) - generic tool skills (daf-cli, gh-cli, etc.)
    3. Hierarchical skills: $DEVAIFLOW_HOME/.claude/skills/ (numbered: 01-enterprise, 02-organization, etc.) - extends generic skills
    4. Project-level skills: <project>/.claude/skills/ (alphabetical)

    Rationale: Hierarchical skills extend generic skills (see "Extends: daf-cli" in skill frontmatter),
    so generic skills must be loaded first.

    Args:
        project_path: Project directory path (for project-level skills)
        workspace: Workspace directory path (for workspace-level skills)

    Returns:
        List of tuples (skill_path, description) for all discovered skills in load order
    """
    discovered_skills = []

    def _scan_skill_dir(skill_file: Path, skill_dir_name: str) -> Optional[tuple[str, str]]:
        """Scan a single skill directory and extract description."""
        if not skill_file.exists():
            return None

        description = f"{skill_dir_name} skill"
        # Try to extract description from YAML frontmatter
        try:
            with open(skill_file, 'r') as f:
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

        return (str(skill_file.resolve()), description)

    # 1. User-level skills: ~/.claude/skills/ (generic skills like daf-cli, git-cli)
    user_skills_dir = Path.home() / ".claude" / "skills"
    if user_skills_dir.exists():
        for skill_dir in sorted(user_skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                result = _scan_skill_dir(skill_file, skill_dir.name)
                if result:
                    discovered_skills.append(result)

    # 2. Workspace-level skills: <workspace>/.claude/skills/ (generic tool skills)
    if workspace:
        from devflow.utils.claude_commands import get_workspace_skills_dir
        workspace_skills_dir = get_workspace_skills_dir(workspace)
        if workspace_skills_dir.exists():
            for skill_dir in sorted(workspace_skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    result = _scan_skill_dir(skill_file, skill_dir.name)
                    if result:
                        discovered_skills.append(result)

    # 3. Hierarchical skills: $DEVAIFLOW_HOME/.claude/skills/ (organization-specific skills that extend generic ones)
    # These are numbered (01-enterprise, 02-organization, 03-team, 04-user) to guarantee order
    from devflow.utils.paths import get_cs_home
    cs_home = get_cs_home()
    hierarchical_skills_dir = cs_home / ".claude" / "skills"
    if hierarchical_skills_dir.exists():
        # Sort to ensure numbered order (01-, 02-, 03-, 04-)
        for skill_dir in sorted(hierarchical_skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                result = _scan_skill_dir(skill_file, skill_dir.name)
                if result:
                    discovered_skills.append(result)

    # 4. Project-level skills: <project>/.claude/skills/
    if project_path:
        project_skills_dir = Path(project_path) / ".claude" / "skills"
        if project_skills_dir.exists():
            for skill_dir in sorted(project_skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    result = _scan_skill_dir(skill_file, skill_dir.name)
                    if result:
                        discovered_skills.append(result)

    return discovered_skills
