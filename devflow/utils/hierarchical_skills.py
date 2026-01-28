"""Utilities for managing hierarchical skills from config files.

This module provides functionality to install organization-specific skills
referenced in hierarchical config files (ENTERPRISE.md, ORGANIZATION.md,
TEAM.md, USER.md).

Skills are installed to $DEVAIFLOW_HOME/.claude/skills/ with numbered prefixes
to guarantee load order.
"""

from pathlib import Path
from typing import Optional, List, Tuple
from rich.console import Console
import re
import requests

console = Console()


def extract_skill_url(config_path: Path) -> Optional[str]:
    """Extract skill_url from config file frontmatter.

    Args:
        config_path: Path to config file (e.g., ENTERPRISE.md)

    Returns:
        skill_url string if found in frontmatter, None otherwise

    Example frontmatter:
        ---
        skill_url: https://github.com/redhat/daf-skills/rh-enterprise
        ---
    """
    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not read {config_path.name}: {e}")
        return None

    # Check for YAML frontmatter (starts with ---)
    if not content.startswith('---\n'):
        return None

    # Extract frontmatter (between first and second ---)
    parts = content.split('---\n', 2)
    if len(parts) < 3:
        return None

    frontmatter = parts[1]

    # Parse skill_url from frontmatter
    # Support both YAML-style and simple key:value
    for line in frontmatter.split('\n'):
        line = line.strip()
        if line.startswith('skill_url:'):
            # Extract value after 'skill_url:'
            url = line.split('skill_url:', 1)[1].strip()
            # Remove quotes if present
            url = url.strip('"').strip("'")
            return url if url else None

    return None


def download_skill(skill_url: str, config_file_path: Optional[Path] = None) -> str:
    """Download skill content from URL or read from local path.

    Supports:
    - file:// URLs (local filesystem)
    - http:// and https:// URLs (GitHub, GitLab, etc.)
    - Relative paths (resolved relative to config file location)

    Args:
        skill_url: URL or file path to skill
                   Examples:
                   - file:///path/to/skills/rh-enterprise
                   - https://github.com/redhat/daf-skills/enterprise
                   - ../daf-skills/enterprise (relative path)
        config_file_path: Path to the config file (needed for resolving relative paths)

    Returns:
        Content of SKILL.md file as string

    Raises:
        ValueError: If URL format is unsupported
        FileNotFoundError: If file:// path doesn't exist
        requests.HTTPError: If HTTP request fails
    """
    # Handle relative paths
    if not skill_url.startswith(('file://', 'http://', 'https://')):
        # Relative path - resolve relative to config file location
        if not config_file_path:
            raise ValueError(f"Relative skill_url '{skill_url}' requires config_file_path to be provided")

        # Resolve relative to config file's directory
        skill_path = (config_file_path.parent / skill_url).resolve()
        skill_file = skill_path / "SKILL.md"

        if not skill_file.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_file}")

        return skill_file.read_text(encoding='utf-8')

    if skill_url.startswith('file://'):
        # Local file path
        local_path = Path(skill_url.replace('file://', ''))
        skill_file = local_path / "SKILL.md"

        if not skill_file.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_file}")

        return skill_file.read_text(encoding='utf-8')

    elif skill_url.startswith('http://') or skill_url.startswith('https://'):
        # HTTP(S) URL - download from remote
        import requests

        # Construct URL to SKILL.md
        if 'github.com' in skill_url:
            # Convert GitHub repo URL to raw content URL
            # https://github.com/user/repo/path → https://raw.githubusercontent.com/user/repo/main/path/SKILL.md
            raw_url = skill_url.replace('github.com', 'raw.githubusercontent.com')

            # If URL doesn't contain a branch, assume 'main'
            # Pattern: raw.githubusercontent.com/user/repo/...
            # We need: raw.githubusercontent.com/user/repo/main/...
            parts = raw_url.replace('https://raw.githubusercontent.com/', '').split('/')
            if len(parts) >= 2:
                # Check if third part looks like a branch name
                # If not, insert 'main'
                if len(parts) == 2 or not re.match(r'^(main|master|develop|v\d+).*', parts[2]):
                    # Insert 'main' after repo name
                    raw_url = f"https://raw.githubusercontent.com/{parts[0]}/{parts[1]}/main"
                    if len(parts) > 2:
                        raw_url += "/" + "/".join(parts[2:])

            # Add SKILL.md if not already there
            if not raw_url.endswith('SKILL.md'):
                raw_url = raw_url.rstrip('/') + '/SKILL.md'

        elif 'gitlab.com' in skill_url:
            # Convert GitLab repo URL to raw content URL
            # https://gitlab.com/user/repo/path → https://gitlab.com/user/repo/-/raw/main/path/SKILL.md
            if '/-/raw/' not in skill_url:
                # Insert /-/raw/main/ before path
                base_url = skill_url.split('/tree/', 1)[0] if '/tree/' in skill_url else skill_url
                path = skill_url.split('/tree/', 1)[1] if '/tree/' in skill_url else ''

                raw_url = base_url.rstrip('/') + '/-/raw/main'
                if path:
                    raw_url += '/' + path
            else:
                raw_url = skill_url

            if not raw_url.endswith('SKILL.md'):
                raw_url = raw_url.rstrip('/') + '/SKILL.md'

        else:
            # Generic URL - assume it points to SKILL.md or directory
            raw_url = skill_url.rstrip('/') + '/SKILL.md' if not skill_url.endswith('.md') else skill_url

        # Download content
        try:
            response = requests.get(raw_url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise ValueError(f"Failed to download skill from {raw_url}: {e}")

    else:
        raise ValueError(
            f"Unsupported skill_url format: {skill_url}\n"
            "Supported formats:\n"
            "  - file:///path/to/skill/directory\n"
            "  - https://github.com/user/repo/path\n"
            "  - https://gitlab.com/user/repo/path"
        )


def download_hierarchical_config_file(config_url: str, config_filename: str) -> str:
    """Download hierarchical config file (.md) from URL or read from local path.

    Supports:
    - file:// URLs (local filesystem)
    - http:// and https:// URLs (GitHub, GitLab, etc.)
    - Plain local paths (e.g., /path/to/configs or ~/path/to/configs)

    Args:
        config_url: Base URL or path to config files directory
                    Examples:
                    - file:///path/to/configs
                    - /path/to/configs (plain path)
                    - ~/path/to/configs (home directory expansion)
                    - https://github.com/ansible-saas/devflow-for-red-hatters/configs
        config_filename: Name of config file to download (e.g., "ENTERPRISE.md")

    Returns:
        Content of config file as string

    Raises:
        ValueError: If URL format is unsupported
        FileNotFoundError: If local path doesn't exist
        requests.HTTPError: If HTTP request fails
    """
    # Handle plain local paths (without file:// scheme)
    if not config_url.startswith(('file://', 'http://', 'https://')):
        # Plain local path - expand user directory and resolve
        local_path = Path(config_url).expanduser().resolve()
        config_file = local_path / config_filename

        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        return config_file.read_text(encoding='utf-8')

    if config_url.startswith('file://'):
        # Local file path
        local_path = Path(config_url.replace('file://', ''))
        config_file = local_path / config_filename

        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        return config_file.read_text(encoding='utf-8')

    elif config_url.startswith('http://') or config_url.startswith('https://'):
        # HTTP(S) URL - download from remote

        # Construct URL to config file
        if 'github.com' in config_url:
            # Convert GitHub repo URL to raw content URL
            # https://github.com/user/repo/path → https://raw.githubusercontent.com/user/repo/main/path/ENTERPRISE.md
            raw_url = config_url.replace('github.com', 'raw.githubusercontent.com')

            # If URL doesn't contain a branch, assume 'main'
            parts = raw_url.replace('https://raw.githubusercontent.com/', '').split('/')
            if len(parts) >= 2:
                # Check if third part looks like a branch name
                if len(parts) == 2 or not re.match(r'^(main|master|develop|v\d+).*', parts[2]):
                    # Insert 'main' after repo name
                    raw_url = f"https://raw.githubusercontent.com/{parts[0]}/{parts[1]}/main"
                    if len(parts) > 2:
                        raw_url += "/" + "/".join(parts[2:])

            # Add config filename
            if not raw_url.endswith(config_filename):
                raw_url = raw_url.rstrip('/') + '/' + config_filename

        elif 'gitlab.com' in config_url:
            # Convert GitLab repo URL to raw content URL
            if '/-/raw/' not in config_url:
                base_url = config_url.split('/tree/', 1)[0] if '/tree/' in config_url else config_url
                path = config_url.split('/tree/', 1)[1] if '/tree/' in config_url else ''

                raw_url = base_url.rstrip('/') + '/-/raw/main'
                if path:
                    raw_url += '/' + path
            else:
                raw_url = config_url

            if not raw_url.endswith(config_filename):
                raw_url = raw_url.rstrip('/') + '/' + config_filename

        else:
            # Generic URL - assume it points to directory
            raw_url = config_url.rstrip('/') + '/' + config_filename

        # Download content
        try:
            response = requests.get(raw_url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise ValueError(f"Failed to download config file from {raw_url}: {e}")

    else:
        # This branch should never be reached now that we handle plain paths
        raise ValueError(
            f"Unsupported hierarchical_config_source format: {config_url}\n"
            "Supported formats:\n"
            "  - /path/to/configs (plain path)\n"
            "  - ~/path/to/configs (home directory)\n"
            "  - file:///path/to/configs\n"
            "  - https://github.com/user/repo/path\n"
            "  - https://gitlab.com/user/repo/path"
        )


def install_hierarchical_skills(
    dry_run: bool = False,
    quiet: bool = False
) -> Tuple[List[str], List[str], List[str]]:
    """Install organization-specific skills from hierarchical config files.

    First checks if hierarchical_config_source is configured in organization.json.
    If yes, downloads the .md config files from that source to $DEVAIFLOW_HOME.
    Then reads ENTERPRISE.md, ORGANIZATION.md, TEAM.md, USER.md from $DEVAIFLOW_HOME
    and installs skills referenced in their frontmatter to
    $DEVAIFLOW_HOME/.claude/skills/ with numbered prefixes.

    Args:
        dry_run: If True, only report what would be installed without installing
        quiet: If True, suppress console output (errors still shown)

    Returns:
        Tuple of (changed, up_to_date, failed) skill names
        - changed: Skills that were installed or updated
        - up_to_date: Skills that were already up-to-date (not applicable for now)
        - failed: Skills that failed to install
    """
    from devflow.utils.paths import get_cs_home
    from devflow.config.loader import ConfigLoader

    cs_home = get_cs_home()
    skills_install_dir = cs_home / ".claude" / "skills"

    # Define hierarchy order (order number, config file, level name)
    hierarchy = [
        (1, "ENTERPRISE.md", "enterprise"),
        (2, "ORGANIZATION.md", "organization"),
        (3, "TEAM.md", "team"),
        (4, "USER.md", "user"),
    ]

    changed = []
    up_to_date = []
    failed = []

    # Check if hierarchical_config_source is configured in organization.json
    # We need to read organization.json directly, not the merged config
    config_loader = ConfigLoader()

    # Read organization.json directly
    from devflow.utils.paths import get_cs_home
    org_config_path = get_cs_home() / "organization.json"
    config_source = None

    if org_config_path.exists():
        import json
        try:
            with open(org_config_path, 'r') as f:
                org_config = json.load(f)
                config_source = org_config.get('hierarchical_config_source')
        except Exception as e:
            if not quiet:
                console.print(f"[yellow]⚠[/yellow] Could not read organization.json: {e}")

    if config_source:

        if not quiet:
            console.print(f"[cyan]Downloading hierarchical config files from:[/cyan] {config_source}")

        # For each config file: download, extract skill_url, install skill, then save config
        for order_num, config_file, level_name in hierarchy:
            try:
                if dry_run:
                    if not quiet:
                        console.print(f"[yellow]Would download:[/yellow] {config_file}")
                    # In dry-run, check if skill_url would be found
                    config_path = cs_home / config_file
                    if config_path.exists():
                        skill_url = extract_skill_url(config_path)
                        if skill_url:
                            if not quiet:
                                console.print(f"[cyan]Installing {level_name} skill from:[/cyan] {skill_url}")
                            skill_dir_name = f"{order_num:02d}-{level_name}"
                            skill_install_path = skills_install_dir / skill_dir_name
                            if not quiet:
                                console.print(f"[yellow]Would install to:[/yellow] {skill_install_path}")
                            changed.append(skill_dir_name)
                else:
                    # Download config content
                    config_content = download_hierarchical_config_file(config_source, config_file)

                    # Create a temporary Path object to represent the source location
                    # This is used for resolving relative paths in skill_url
                    if config_source.startswith('file://'):
                        source_base = Path(config_source.replace('file://', ''))
                    elif not config_source.startswith(('http://', 'https://')):
                        # Plain local path - use it directly (expand ~ and resolve)
                        source_base = Path(config_source).expanduser().resolve()
                    else:
                        # For remote sources (http/https), we can't resolve relative paths
                        # relative paths only work with local file sources
                        source_base = cs_home

                    temp_config_path = source_base / config_file

                    # Extract skill_url from the downloaded content
                    # We need to parse it directly from content since the file isn't written yet
                    skill_url = None
                    if config_content.startswith('---\n'):
                        parts = config_content.split('---\n', 2)
                        if len(parts) >= 3:
                            frontmatter = parts[1]
                            for line in frontmatter.split('\n'):
                                line = line.strip()
                                if line.startswith('skill_url:'):
                                    url = line.split('skill_url:', 1)[1].strip()
                                    skill_url = url.strip('"').strip("'")
                                    break

                    # If skill_url found, download and install skill BEFORE writing config
                    if skill_url:
                        skill_dir_name = f"{order_num:02d}-{level_name}"
                        skill_install_path = skills_install_dir / skill_dir_name

                        try:
                            # Download skill content (pass temp_config_path for relative URL resolution)
                            skill_content = download_skill(skill_url, config_file_path=temp_config_path)

                            # Check if skill already exists and is up-to-date
                            skill_file = skill_install_path / "SKILL.md"
                            needs_update = True

                            if skill_file.exists():
                                # Compare content
                                existing_content = skill_file.read_text(encoding='utf-8')
                                if existing_content == skill_content:
                                    needs_update = False
                                    up_to_date.append(skill_dir_name)

                            if needs_update:
                                # Only print "Installing..." if we're actually installing
                                if not quiet:
                                    console.print(f"[cyan]Installing {level_name} skill from:[/cyan] {skill_url}")
                                # Create skill directory
                                skill_install_path.mkdir(parents=True, exist_ok=True)

                                # Write SKILL.md
                                skill_file.write_text(skill_content, encoding='utf-8')

                                if not quiet:
                                    console.print(f"[green]✓[/green] Installed {level_name} skill to: {skill_install_path}")

                                changed.append(skill_dir_name)

                        except Exception as e:
                            if not quiet:
                                console.print(f"[red]✗[/red] Failed to install {level_name} skill: {e}")
                            failed.append(skill_dir_name)

                    # Write config to $DEVAIFLOW_HOME
                    config_path = cs_home / config_file
                    config_path.write_text(config_content, encoding='utf-8')

                    if not quiet:
                        console.print(f"[green]✓[/green] Downloaded {config_file} to: {config_path}")

            except Exception as e:
                if not quiet:
                    console.print(f"[yellow]⚠[/yellow] Could not download {config_file}: {e}")
                # Continue with next file even if this one fails

    # Also install skills from config files that are already in $DEVAIFLOW_HOME
    # (but weren't downloaded from hierarchical_config_source)
    # Skip this if we already processed files from hierarchical_config_source
    if not config_source:
        for order_num, config_file, level_name in hierarchy:
            config_path = cs_home / config_file

            if not config_path.exists():
                if not quiet:
                    console.print(f"[dim]No {config_file} found, skipping {level_name} skills[/dim]")
                continue

            # Check if we already processed this file (it was downloaded from source)
            skill_dir_name = f"{order_num:02d}-{level_name}"
            if skill_dir_name in changed or skill_dir_name in failed:
                # Already processed during download phase
                continue

            # Extract skill_url from frontmatter
            skill_url = extract_skill_url(config_path)

            if not skill_url:
                if not quiet:
                    console.print(f"[dim]No skill_url in {config_file}, skipping {level_name} skills[/dim]")
                continue

            skill_install_path = skills_install_dir / skill_dir_name

            if dry_run:
                if not quiet:
                    console.print(f"[cyan]Installing {level_name} skill from:[/cyan] {skill_url}")
                    console.print(f"[yellow]Would install to:[/yellow] {skill_install_path}")
                changed.append(skill_dir_name)
                continue

            try:
                # Download skill content (pass config_path for relative URL resolution)
                skill_content = download_skill(skill_url, config_file_path=config_path)

                # Check if skill already exists and is up-to-date
                skill_file = skill_install_path / "SKILL.md"
                needs_update = True

                if skill_file.exists():
                    # Compare content
                    existing_content = skill_file.read_text(encoding='utf-8')
                    if existing_content == skill_content:
                        needs_update = False
                        up_to_date.append(skill_dir_name)

                if needs_update:
                    # Only print "Installing..." if we're actually installing
                    if not quiet:
                        console.print(f"[cyan]Installing {level_name} skill from:[/cyan] {skill_url}")
                    # Create skill directory
                    skill_install_path.mkdir(parents=True, exist_ok=True)

                    # Write SKILL.md
                    skill_file.write_text(skill_content, encoding='utf-8')

                    if not quiet:
                        console.print(f"[green]✓[/green] Installed {level_name} skill to: {skill_install_path}")

                    changed.append(skill_dir_name)

            except Exception as e:
                if not quiet:
                    console.print(f"[red]✗[/red] Failed to install {level_name} skill: {e}")
                failed.append(skill_dir_name)

    return changed, up_to_date, failed


def get_hierarchical_skill_statuses() -> dict:
    """Get installation status of hierarchical skills.

    Returns:
        Dict mapping skill names to status:
        - "installed": Skill is installed
        - "not_installed": Skill directory doesn't exist
        - "no_url": Config file exists but has no skill_url
        - "no_config": Config file doesn't exist
    """
    from devflow.utils.paths import get_cs_home

    cs_home = get_cs_home()
    skills_dir = cs_home / ".claude" / "skills"

    hierarchy = [
        (1, "ENTERPRISE.md", "enterprise"),
        (2, "ORGANIZATION.md", "organization"),
        (3, "TEAM.md", "team"),
        (4, "USER.md", "user"),
    ]

    statuses = {}

    for order_num, config_file, level_name in hierarchy:
        skill_dir_name = f"{order_num:02d}-{level_name}"
        config_path = cs_home / config_file
        skill_path = skills_dir / skill_dir_name

        if not config_path.exists():
            statuses[skill_dir_name] = "no_config"
        elif not extract_skill_url(config_path):
            statuses[skill_dir_name] = "no_url"
        elif skill_path.exists() and (skill_path / "SKILL.md").exists():
            statuses[skill_dir_name] = "installed"
        else:
            statuses[skill_dir_name] = "not_installed"

    return statuses
