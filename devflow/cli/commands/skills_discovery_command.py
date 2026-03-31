"""Implementation of 'daf skills' command for discovery and inspection."""

import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import re

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from devflow.config.loader import ConfigLoader
from devflow.utils.paths import get_claude_config_dir, get_cs_home

console = Console()


@click.command()
@click.argument("skill_name", required=False)
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def skills(skill_name: Optional[str], output_json: bool) -> None:
    """List and inspect available skills.

    When run without arguments, lists all available skills grouped by level.
    When given a skill name, shows detailed information about that skill.

    \b
    Examples:
        # List all skills
        daf skills

        # Inspect specific skill
        daf skills daf-cli

        # JSON output
        daf skills --json
        daf skills daf-cli --json
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    # Get workspace path if available
    workspace_path = None
    if config and config.repos and config.repos.workspaces:
        # Use default workspace or first workspace
        default_workspace = next(
            (ws for ws in config.repos.workspaces if ws.name == config.repos.last_used_workspace),
            None
        ) or config.repos.workspaces[0] if config.repos.workspaces else None
        if default_workspace:
            workspace_path = default_workspace.path

    # Discover all skills
    skills_by_level = _discover_all_skills(workspace_path)

    if skill_name:
        # Inspect specific skill
        _inspect_skill(skill_name, skills_by_level, output_json)
    else:
        # List all skills
        _list_all_skills(skills_by_level, output_json)


def _discover_all_skills(workspace_path: Optional[str] = None) -> Dict[str, List[Dict]]:
    """Discover all skills grouped by level.

    Returns:
        Dict mapping level name to list of skill info dicts
    """
    skills_by_level = {
        "user": [],
        "workspace": [],
        "hierarchical": [],
        "project": []
    }

    # 1. User-level skills: ~/.claude/skills/
    claude_config = get_claude_config_dir()
    user_skills_dir = claude_config / "skills"
    if user_skills_dir.exists():
        skills_by_level["user"] = _discover_skills_in_dir(user_skills_dir, "user")

    # 2. Workspace-level skills: <workspace>/.claude/skills/
    if workspace_path:
        workspace_skills_dir = Path(workspace_path).expanduser().resolve() / ".claude" / "skills"
        if workspace_skills_dir.exists():
            skills_by_level["workspace"] = _discover_skills_in_dir(workspace_skills_dir, "workspace")

    # 3. Hierarchical skills: $DEVAIFLOW_HOME/.claude/skills/
    cs_home = get_cs_home()
    hierarchical_skills_dir = cs_home / ".claude" / "skills"
    if hierarchical_skills_dir.exists():
        skills_by_level["hierarchical"] = _discover_skills_in_dir(hierarchical_skills_dir, "hierarchical")

    # 4. Project-level skills: <project>/.claude/skills/
    # Note: We check current directory for project-level skills
    project_skills_dir = Path.cwd() / ".claude" / "skills"
    if project_skills_dir.exists():
        skills_by_level["project"] = _discover_skills_in_dir(project_skills_dir, "project")

    return skills_by_level


def _discover_skills_in_dir(skills_dir: Path, level: str) -> List[Dict]:
    """Discover all skills in a directory.

    Returns:
        List of skill info dicts with keys: name, description, level, location, file_path, frontmatter
    """
    skills = []

    for skill_path in sorted(skills_dir.iterdir()):
        if not skill_path.is_dir():
            continue

        skill_file = skill_path / "SKILL.md"
        if not skill_file.exists():
            continue

        # Parse skill file
        frontmatter, description = _parse_skill_file(skill_file)

        # Extract description from frontmatter or first non-empty line
        # Clean control characters from description
        skill_description = frontmatter.get("description", "")
        if not skill_description:
            skill_description = description

        # Remove control characters from description for clean JSON output
        skill_description = skill_description.replace("\n", " ").replace("\r", " ").replace("\t", " ")

        skills.append({
            "name": skill_path.name,
            "description": skill_description,
            "level": level,
            "location": str(skills_dir),
            "file_path": str(skill_file),
            "frontmatter": frontmatter
        })

    return skills


def _parse_skill_file(skill_file: Path) -> Tuple[Dict, str]:
    """Parse a SKILL.md file and extract frontmatter and description.

    Returns:
        Tuple of (frontmatter_dict, first_line_description)
    """
    frontmatter = {}
    description = ""

    try:
        content = skill_file.read_text(encoding="utf-8")

        # Check for YAML frontmatter
        if content.startswith("---\n"):
            # Extract frontmatter
            parts = content.split("---\n", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                body = parts[2]

                # Parse YAML frontmatter
                try:
                    import yaml
                    frontmatter = yaml.safe_load(frontmatter_text) or {}
                except ImportError:
                    # yaml not available, parse manually
                    for line in frontmatter_text.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            frontmatter[key.strip()] = value.strip()
                except Exception:
                    # If YAML parsing fails, parse manually
                    for line in frontmatter_text.split("\n"):
                        if ":" in line:
                            key, value = line.split(":", 1)
                            frontmatter[key.strip()] = value.strip()
            else:
                body = content
        else:
            body = content

        # Extract first non-empty line as description fallback
        for line in body.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                # Replace newlines and tabs with spaces for single-line description
                description = line.replace("\n", " ").replace("\t", " ").replace("\r", " ")[:100]
                break

    except Exception as e:
        console.print(f"[yellow]Warning:[/yellow] Failed to parse {skill_file}: {e}", err=True)

    return frontmatter, description


def _list_all_skills(skills_by_level: Dict[str, List[Dict]], output_json: bool) -> None:
    """List all skills grouped by level."""
    if output_json:
        _list_skills_json(skills_by_level)
    else:
        _list_skills_table(skills_by_level)


def _list_skills_json(skills_by_level: Dict[str, List[Dict]]) -> None:
    """Output skills list in JSON format."""
    # Calculate totals
    level_counts = {level: len(skills) for level, skills in skills_by_level.items()}
    total_skills = sum(level_counts.values())

    output = {
        "skills": [],
        "total": total_skills,
        "levels": level_counts
    }

    # Flatten skills list
    for level, skills in skills_by_level.items():
        for skill in skills:
            # Sanitize description for JSON (remove control characters)
            description = skill["description"].replace("\n", " ").replace("\r", " ").replace("\t", " ")

            output["skills"].append({
                "name": skill["name"],
                "description": description,
                "level": skill["level"],
                "location": skill["location"],
                "file_path": skill["file_path"],
                "frontmatter": skill["frontmatter"]
            })

    # Sort by name
    output["skills"].sort(key=lambda s: s["name"])

    # Use print() instead of console.print() to avoid Rich wrapping the JSON
    print(json.dumps(output, indent=2))


def _list_skills_table(skills_by_level: Dict[str, List[Dict]]) -> None:
    """Output skills list in table format."""
    console.print("\n[bold cyan]Available Skills (sorted by name)[/bold cyan]\n")

    # Collect all skills for sorted display
    all_skills = []
    for level, skills in skills_by_level.items():
        all_skills.extend(skills)

    # Sort by name
    all_skills.sort(key=lambda s: s["name"])

    # Group by level for display
    level_display = {
        "user": f"User-level ({get_claude_config_dir() / 'skills'}):",
        "workspace": "Workspace-level (<workspace>/.claude/skills/):",
        "hierarchical": f"Hierarchical ({get_cs_home() / '.claude/skills'}):",
        "project": "Project-level (<project>/.claude/skills/):"
    }

    # Display skills grouped by level
    for level_key in ["user", "workspace", "hierarchical", "project"]:
        level_skills = [s for s in all_skills if s["level"] == level_key]

        if level_skills:
            console.print(f"\n[bold]{level_display[level_key]}[/bold]")
            for skill in level_skills:
                console.print(f"  [cyan]• {skill['name']}[/cyan] - {skill['description']}")

    # Show total count
    total = len(all_skills)
    level_counts = {level: len([s for s in all_skills if s["level"] == level]) for level in ["user", "workspace", "hierarchical", "project"]}

    console.print(f"\n[bold]Total: {total} skills[/bold]")
    console.print(f"[dim]  User: {level_counts['user']}, Workspace: {level_counts['workspace']}, "
                  f"Hierarchical: {level_counts['hierarchical']}, Project: {level_counts['project']}[/dim]\n")


def _inspect_skill(skill_name: str, skills_by_level: Dict[str, List[Dict]], output_json: bool) -> None:
    """Inspect a specific skill."""
    # Find the skill (search all levels)
    found_skills = []
    for level, skills in skills_by_level.items():
        for skill in skills:
            if skill["name"] == skill_name:
                found_skills.append(skill)

    if not found_skills:
        if output_json:
            # Use print() instead of console.print() to avoid Rich wrapping the JSON
            print(json.dumps({"error": f"Skill '{skill_name}' not found"}, indent=2))
        else:
            console.print(f"[red]✗[/red] Skill '{skill_name}' not found")
            console.print(f"\n[dim]Run 'daf skills' to see all available skills[/dim]")
        return

    if len(found_skills) > 1:
        # Multiple skills found at different levels
        if output_json:
            _inspect_skill_json_multiple(found_skills)
        else:
            _inspect_skill_table_multiple(found_skills)
    else:
        # Single skill found
        if output_json:
            _inspect_skill_json(found_skills[0])
        else:
            _inspect_skill_table(found_skills[0])


def _inspect_skill_json(skill: Dict) -> None:
    """Output skill details in JSON format."""
    # Read full content
    content_preview = ""
    try:
        full_content = Path(skill["file_path"]).read_text(encoding="utf-8")
        # Skip frontmatter for preview
        if full_content.startswith("---\n"):
            parts = full_content.split("---\n", 2)
            if len(parts) >= 3:
                content_preview = parts[2][:500]  # First 500 chars
            else:
                content_preview = full_content[:500]
        else:
            content_preview = full_content[:500]
    except Exception:
        content_preview = ""

    # Sanitize description for JSON
    description = skill["description"].replace("\n", " ").replace("\r", " ").replace("\t", " ")

    output = {
        "name": skill["name"],
        "description": description,
        "level": skill["level"],
        "location": skill["location"],
        "file_path": skill["file_path"],
        "frontmatter": skill["frontmatter"],
        "content_preview": content_preview
    }

    # Use print() instead of console.print() to avoid Rich wrapping the JSON
    print(json.dumps(output, indent=2))


def _inspect_skill_json_multiple(skills: List[Dict]) -> None:
    """Output multiple skill instances in JSON format."""
    output = {
        "name": skills[0]["name"],
        "found_at_levels": len(skills),
        "instances": []
    }

    for skill in skills:
        # Read content preview
        content_preview = ""
        try:
            full_content = Path(skill["file_path"]).read_text(encoding="utf-8")
            if full_content.startswith("---\n"):
                parts = full_content.split("---\n", 2)
                if len(parts) >= 3:
                    content_preview = parts[2][:500]
                else:
                    content_preview = full_content[:500]
            else:
                content_preview = full_content[:500]
        except Exception:
            content_preview = ""

        # Sanitize description for JSON
        description = skill["description"].replace("\n", " ").replace("\r", " ").replace("\t", " ")

        output["instances"].append({
            "level": skill["level"],
            "location": skill["location"],
            "file_path": skill["file_path"],
            "description": description,
            "frontmatter": skill["frontmatter"],
            "content_preview": content_preview
        })

    # Use print() instead of console.print() to avoid Rich wrapping the JSON
    print(json.dumps(output, indent=2))


def _inspect_skill_table(skill: Dict) -> None:
    """Output skill details in table format."""
    console.print(f"\n[bold cyan]Skill: {skill['name']}[/bold cyan]\n")
    console.print(f"[bold]Location:[/bold] {skill['location']}")
    console.print(f"[bold]File:[/bold] {skill['file_path']}")
    console.print(f"[bold]Level:[/bold] {skill['level']}")

    # Display frontmatter
    if skill["frontmatter"]:
        console.print(f"\n[bold]Frontmatter:[/bold]")
        for key, value in skill["frontmatter"].items():
            console.print(f"  [cyan]{key}:[/cyan] {value}")

    # Display content preview
    try:
        full_content = Path(skill["file_path"]).read_text(encoding="utf-8")

        # Skip frontmatter
        if full_content.startswith("---\n"):
            parts = full_content.split("---\n", 2)
            if len(parts) >= 3:
                content = parts[2]
            else:
                content = full_content
        else:
            content = full_content

        # Show first ~20 lines
        lines = content.split("\n")
        preview_lines = lines[:20]

        console.print(f"\n[bold]Content preview:[/bold]")
        console.print("[dim]" + "-" * 60 + "[/dim]")
        for line in preview_lines:
            console.print(line)

        if len(lines) > 20:
            console.print(f"[dim]... ({len(lines) - 20} more lines)[/dim]")
        console.print("[dim]" + "-" * 60 + "[/dim]")

        console.print(f"\n[dim]To view full content: cat {skill['file_path']}[/dim]\n")

    except Exception as e:
        console.print(f"\n[yellow]Warning:[/yellow] Could not read file content: {e}\n")


def _inspect_skill_table_multiple(skills: List[Dict]) -> None:
    """Output multiple skill instances in table format."""
    console.print(f"\n[bold cyan]Skill: {skills[0]['name']}[/bold cyan]")
    console.print(f"[yellow]⚠[/yellow] Found at {len(skills)} levels (precedence: Project > Hierarchical > Workspace > User)\n")

    # Show each instance
    for i, skill in enumerate(skills, 1):
        console.print(f"\n[bold]Instance #{i} ({skill['level']} level):[/bold]")
        console.print(f"  [bold]Location:[/bold] {skill['location']}")
        console.print(f"  [bold]File:[/bold] {skill['file_path']}")

        if skill["frontmatter"]:
            console.print(f"  [bold]Frontmatter:[/bold]")
            for key, value in skill["frontmatter"].items():
                console.print(f"    [cyan]{key}:[/cyan] {value}")

    console.print(f"\n[dim]To view full content of a specific instance:[/dim]")
    for skill in skills:
        console.print(f"[dim]  cat {skill['file_path']}[/dim]")
    console.print()
