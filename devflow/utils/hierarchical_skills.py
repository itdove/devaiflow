"""Utilities for managing hierarchical skills from config files.

This module provides functionality to install organization-specific skills
referenced in hierarchical config files (ENTERPRISE.md, ORGANIZATION.md,
TEAM.md, USER.md).

Skills are installed to $DEVAIFLOW_HOME/.claude/skills/ with numbered prefixes
to guarantee load order.
"""

from pathlib import Path
from typing import Optional, List, Tuple, Literal
from rich.console import Console
from enum import Enum
import re
import requests

console = Console()


class RepositoryLayout(Enum):
    """Repository layout types for hierarchical config source."""
    STANDARD = "standard"  # Has configs/, context/, daf-skills/ subdirectories
    LEGACY = "legacy"      # Files at root with skill_url in frontmatter


def detect_repository_layout(config_source: str) -> RepositoryLayout:
    """Detect whether hierarchical config source uses standard or legacy layout.

    Standard layout:
        devflow-config/
        ├── configs/           # JSON config files
        ├── context/           # .md context files
        └── daf-skills/        # Skills directories

    Legacy layout:
        devflow-config/
        ├── ENTERPRISE.md      # Context files at root
        ├── ORGANIZATION.md
        └── ...

    Args:
        config_source: Base URL or path to config repository
                      Examples:
                      - https://github.com/org/devflow-config
                      - file:///path/to/configs
                      - /path/to/configs

    Returns:
        RepositoryLayout.STANDARD if configs/ directory exists,
        RepositoryLayout.LEGACY otherwise
    """
    # Handle plain local paths
    if not config_source.startswith(('file://', 'http://', 'https://')):
        local_path = Path(config_source).expanduser().resolve()
        # Check if standard layout subdirectories exist
        if (local_path / "configs").exists() or (local_path / "context").exists() or (local_path / "daf-skills").exists():
            return RepositoryLayout.STANDARD
        return RepositoryLayout.LEGACY

    if config_source.startswith('file://'):
        local_path = Path(config_source.replace('file://', ''))
        # Check if standard layout subdirectories exist
        if (local_path / "configs").exists() or (local_path / "context").exists() or (local_path / "daf-skills").exists():
            return RepositoryLayout.STANDARD
        return RepositoryLayout.LEGACY

    elif config_source.startswith('http://') or config_source.startswith('https://'):
        # For remote sources, try to detect by checking if configs/ exists
        # We'll do a simple HEAD request to configs/ subdirectory
        from devflow.utils.ssl_helper import get_ssl_verify_setting, get_request_timeout
        ssl_verify = get_ssl_verify_setting()
        timeout = get_request_timeout()

        try:
            # Construct URL to configs directory
            if 'github.com' in config_source:
                # For GitHub, convert to API check
                # We'll try to access configs/ directory via raw content
                raw_url = config_source.replace('github.com', 'raw.githubusercontent.com')
                parts = raw_url.replace('https://raw.githubusercontent.com/', '').split('/')

                if len(parts) >= 2:
                    # Check if third part looks like a branch
                    if len(parts) == 2 or not re.match(r'^(main|master|develop|v\d+).*', parts[2]):
                        # Try to access configs/enterprise.json as a test
                        test_url = f"https://raw.githubusercontent.com/{parts[0]}/{parts[1]}/main"
                        if len(parts) > 2:
                            test_url += "/" + "/".join(parts[2:])
                        test_url = test_url.rstrip('/') + '/configs/enterprise.json'
                    else:
                        test_url = raw_url.rstrip('/') + '/configs/enterprise.json'

                    # Try to fetch - if it exists, it's standard layout
                    response = requests.head(test_url, timeout=timeout, verify=ssl_verify, allow_redirects=True)
                    if response.status_code == 200:
                        return RepositoryLayout.STANDARD

            elif 'gitlab.com' in config_source:
                # For GitLab, try similar approach
                if '/-/raw/' not in config_source:
                    base_url = config_source.split('/tree/', 1)[0] if '/tree/' in config_source else config_source
                    test_url = base_url.rstrip('/') + '/-/raw/main/configs/enterprise.json'
                else:
                    test_url = config_source.rstrip('/') + '/configs/enterprise.json'

                response = requests.head(test_url, timeout=timeout, verify=ssl_verify, allow_redirects=True)
                if response.status_code == 200:
                    return RepositoryLayout.STANDARD

        except Exception:
            # If check fails, assume legacy layout (safer default)
            pass

        # Default to legacy if we can't detect or check fails
        return RepositoryLayout.LEGACY

    # Fallback
    return RepositoryLayout.LEGACY


def download_json_config(
    config_source: str,
    config_filename: str,
    layout: RepositoryLayout = RepositoryLayout.STANDARD
) -> Optional[dict]:
    """Download JSON config file from hierarchical config source.

    Args:
        config_source: Base URL or path to config repository
        config_filename: Name of JSON file (e.g., "enterprise.json")
        layout: Repository layout type (standard or legacy)

    Returns:
        Parsed JSON data as dict, or None if file doesn't exist

    Raises:
        ValueError: If JSON is malformed or download fails for other reasons
    """
    import json

    # Construct path based on layout
    if layout == RepositoryLayout.STANDARD:
        # Standard layout: files in configs/ subdirectory
        file_path = f"configs/{config_filename}"
    else:
        # Legacy layout: files at root
        file_path = config_filename

    # Handle plain local paths
    if not config_source.startswith(('file://', 'http://', 'https://')):
        local_path = Path(config_source).expanduser().resolve()
        json_file = local_path / file_path

        if not json_file.exists():
            return None

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON in {json_file}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to read {json_file}: {e}")

    if config_source.startswith('file://'):
        local_path = Path(config_source.replace('file://', ''))
        json_file = local_path / file_path

        if not json_file.exists():
            return None

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON in {json_file}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to read {json_file}: {e}")

    elif config_source.startswith('http://') or config_source.startswith('https://'):
        # HTTP(S) URL - download from remote
        from devflow.utils.ssl_helper import get_ssl_verify_setting, get_request_timeout
        ssl_verify = get_ssl_verify_setting()
        timeout = get_request_timeout()

        # Construct URL to JSON file
        if 'github.com' in config_source:
            # Convert to raw content URL
            raw_url = config_source.replace('github.com', 'raw.githubusercontent.com')
            parts = raw_url.replace('https://raw.githubusercontent.com/', '').split('/')

            if len(parts) >= 2:
                if len(parts) == 2 or not re.match(r'^(main|master|develop|v\d+).*', parts[2]):
                    raw_url = f"https://raw.githubusercontent.com/{parts[0]}/{parts[1]}/main"
                    if len(parts) > 2:
                        raw_url += "/" + "/".join(parts[2:])

            raw_url = raw_url.rstrip('/') + '/' + file_path

        elif 'gitlab.com' in config_source:
            # Convert to raw content URL
            if '/-/raw/' not in config_source:
                base_url = config_source.split('/tree/', 1)[0] if '/tree/' in config_source else config_source
                path = config_source.split('/tree/', 1)[1] if '/tree/' in config_source else ''

                raw_url = base_url.rstrip('/') + '/-/raw/main'
                if path:
                    raw_url += '/' + path
            else:
                raw_url = config_source

            raw_url = raw_url.rstrip('/') + '/' + file_path

        else:
            # Generic URL
            raw_url = config_source.rstrip('/') + '/' + file_path

        # Download content
        try:
            response = requests.get(raw_url, timeout=timeout, verify=ssl_verify)

            # 404 means file doesn't exist - return None
            if response.status_code == 404:
                return None

            response.raise_for_status()

            # Parse JSON
            try:
                return response.json()
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed JSON from {raw_url}: {e}")

        except requests.exceptions.SSLError as e:
            error_msg = (
                f"SSL certificate verification failed for {raw_url}\n"
                f"Error: {e}\n\n"
                f"See download_skill() error messages for SSL configuration guidance."
            )
            raise ValueError(error_msg)
        except requests.RequestException as e:
            if "404" not in str(e):  # Don't error on 404, just return None
                raise ValueError(f"Failed to download JSON config from {raw_url}: {e}")
            return None

    return None


def create_backup(file_path: Path, backup_dir: Optional[Path] = None) -> Optional[Path]:
    """Create a timestamped backup of a file before overwriting.

    Args:
        file_path: Path to file to backup
        backup_dir: Directory to store backups (default: ~/.daf-sessions/backups/)

    Returns:
        Path to backup file, or None if source file doesn't exist

    Example:
        /path/to/enterprise.json → backups/enterprise.json.2026-03-26T19:45:00.backup
    """
    from datetime import datetime

    if not file_path.exists():
        return None

    # Default backup directory
    if backup_dir is None:
        from devflow.utils.paths import get_cs_home
        backup_dir = get_cs_home() / "backups"

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped backup filename
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    backup_name = f"{file_path.name}.{timestamp}.backup"
    backup_path = backup_dir / backup_name

    # Copy file to backup location
    import shutil
    shutil.copy2(file_path, backup_path)

    return backup_path


def list_backups(filename: Optional[str] = None, backup_dir: Optional[Path] = None) -> List[Path]:
    """List available backups.

    Args:
        filename: Filter backups for specific file (e.g., "enterprise.json")
                 If None, list all backups
        backup_dir: Directory to search (default: ~/.daf-sessions/backups/)

    Returns:
        List of backup file paths, sorted by timestamp (newest first)
    """
    # Default backup directory
    if backup_dir is None:
        from devflow.utils.paths import get_cs_home
        backup_dir = get_cs_home() / "backups"

    if not backup_dir.exists():
        return []

    # Find backup files
    if filename:
        # Filter for specific file
        pattern = f"{filename}.*.backup"
        backups = list(backup_dir.glob(pattern))
    else:
        # All backup files
        backups = list(backup_dir.glob("*.backup"))

    # Sort by modification time (newest first)
    backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return backups


def restore_backup(backup_path: Path, target_path: Optional[Path] = None) -> Path:
    """Restore a file from backup.

    Args:
        backup_path: Path to backup file
        target_path: Where to restore the file (if None, extracts from backup filename)

    Returns:
        Path to restored file

    Raises:
        FileNotFoundError: If backup doesn't exist
        ValueError: If backup filename format is invalid

    Example:
        backups/enterprise.json.2026-03-26T19:45:00.backup → enterprise.json
    """
    import shutil

    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    # Extract original filename from backup
    if target_path is None:
        # Remove timestamp and .backup extension
        # Format: filename.YYYY-MM-DDTHH:MM:SS.backup
        backup_name = backup_path.name

        if not backup_name.endswith('.backup'):
            raise ValueError(f"Invalid backup filename: {backup_name}")

        # Remove .backup extension
        without_backup_ext = backup_name[:-7]  # Remove '.backup'

        # Find last dot before timestamp (YYYY-MM-DD...)
        # Split on dots and rejoin all but the last part (timestamp)
        parts = without_backup_ext.rsplit('.', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid backup filename format: {backup_name}")

        original_filename = parts[0]

        # Restore to config directory
        from devflow.utils.paths import get_cs_home
        target_path = get_cs_home() / original_filename

    # Copy backup to target location
    shutil.copy2(backup_path, target_path)

    return target_path


def list_remote_skills(
    config_source: str,
    layout: RepositoryLayout = RepositoryLayout.STANDARD
) -> List[str]:
    """Dynamically discover all skills in daf-skills/ directory.

    Args:
        config_source: Base URL or path to config repository
        layout: Repository layout type (only STANDARD supports this)

    Returns:
        List of skill directory names (e.g., ["enterprise", "organization", "custom-workflow"])

    Note:
        For legacy layout, returns empty list (skills are referenced in frontmatter)
    """
    if layout == RepositoryLayout.LEGACY:
        # Legacy layout doesn't have daf-skills/ directory
        return []

    skills_path = "daf-skills"

    # Handle plain local paths
    if not config_source.startswith(('file://', 'http://', 'https://')):
        local_path = Path(config_source).expanduser().resolve()
        skills_dir = local_path / skills_path

        if not skills_dir.exists():
            return []

        # List subdirectories that contain SKILL.md
        skill_dirs = []
        for item in skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skill_dirs.append(item.name)

        return sorted(skill_dirs)

    if config_source.startswith('file://'):
        local_path = Path(config_source.replace('file://', ''))
        skills_dir = local_path / skills_path

        if not skills_dir.exists():
            return []

        # List subdirectories that contain SKILL.md
        skill_dirs = []
        for item in skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skill_dirs.append(item.name)

        return sorted(skill_dirs)

    elif config_source.startswith('http://') or config_source.startswith('https://'):
        # HTTP(S) URL - use API to list directories
        from devflow.utils.ssl_helper import get_ssl_verify_setting, get_request_timeout
        ssl_verify = get_ssl_verify_setting()
        timeout = get_request_timeout()

        try:
            if 'github.com' in config_source:
                # Use GitHub API to list directory contents
                # Convert repo URL to API URL
                # https://github.com/user/repo → https://api.github.com/repos/user/repo/contents/daf-skills

                # Extract owner/repo from URL
                parts = config_source.replace('https://github.com/', '').split('/')
                if len(parts) < 2:
                    return []

                owner = parts[0]
                repo = parts[1]

                # Build API URL
                api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{skills_path}"

                # If there's a path after repo name, include it
                if len(parts) > 2:
                    # Check if it's a branch or path
                    if not re.match(r'^(main|master|develop|v\d+).*', parts[2]):
                        # It's a path
                        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{'/'.join(parts[2:])}/{skills_path}"

                response = requests.get(api_url, timeout=timeout, verify=ssl_verify)

                if response.status_code == 404:
                    return []

                response.raise_for_status()
                items = response.json()

                # Filter for directories only
                skill_dirs = [item['name'] for item in items if item.get('type') == 'dir']
                return sorted(skill_dirs)

            elif 'gitlab.com' in config_source:
                # Use GitLab API to list directory contents
                # https://gitlab.com/user/repo → https://gitlab.com/api/v4/projects/user%2Frepo/repository/tree?path=daf-skills

                # Extract project path from URL
                parts = config_source.replace('https://gitlab.com/', '').replace('/-/raw/', '/').split('/')
                if len(parts) < 2:
                    return []

                # Build project path (URL-encoded)
                from urllib.parse import quote_plus
                project_path = quote_plus('/'.join(parts[:2]))

                # Build API URL
                api_url = f"https://gitlab.com/api/v4/projects/{project_path}/repository/tree"
                params = {'path': skills_path, 'per_page': 100}

                response = requests.get(api_url, params=params, timeout=timeout, verify=ssl_verify)

                if response.status_code == 404:
                    return []

                response.raise_for_status()
                items = response.json()

                # Filter for directories only
                skill_dirs = [item['name'] for item in items if item.get('type') == 'tree']
                return sorted(skill_dirs)

        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Could not list skills from {config_source}: {e}")
            return []

    return []


def has_file_changed(file_path: Path, new_content: str) -> bool:
    """Check if file content has changed by comparing checksums.

    Args:
        file_path: Path to existing file
        new_content: New content to compare against

    Returns:
        True if content differs or file doesn't exist, False if identical
    """
    if not file_path.exists():
        return True  # File doesn't exist, so it's "changed"

    try:
        existing_content = file_path.read_text(encoding='utf-8')
        return existing_content != new_content
    except Exception:
        # If we can't read the file, assume it's changed
        return True


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
            from devflow.utils.ssl_helper import get_ssl_verify_setting, get_request_timeout
            ssl_verify = get_ssl_verify_setting()
            timeout = get_request_timeout()

            response = requests.get(raw_url, timeout=timeout, verify=ssl_verify)
            response.raise_for_status()
            return response.text
        except requests.exceptions.SSLError as e:
            # SSL certificate verification failed - provide helpful guidance
            error_msg = (
                f"SSL certificate verification failed for {raw_url}\n"
                f"Error: {e}\n\n"
                f"Solutions:\n"
                f"  1. Use custom CA bundle (RECOMMENDED for production):\n"
                f"     export DAF_SSL_VERIFY=/path/to/ca-bundle.crt\n"
                f"     daf upgrade\n\n"
                f"  2. Disable SSL verification (INSECURE - testing only):\n"
                f"     export DAF_SSL_VERIFY=false\n"
                f"     daf upgrade\n\n"
                f"  3. Configure permanently in organization.json:\n"
                f"     {{\n"
                f"       \"http_client\": {{\n"
                f"         \"ssl_verify\": \"/path/to/ca-bundle.crt\"\n"
                f"       }}\n"
                f"     }}\n\n"
                f"See docs/ssl-configuration.md for more information."
            )
            raise ValueError(error_msg)
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


def download_hierarchical_config_file(
    config_url: str,
    config_filename: str,
    layout: RepositoryLayout = RepositoryLayout.LEGACY
) -> str:
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
        layout: Repository layout type (standard uses context/ subdirectory)

    Returns:
        Content of config file as string

    Raises:
        ValueError: If URL format is unsupported
        FileNotFoundError: If local path doesn't exist
        requests.HTTPError: If HTTP request fails
    """
    # Determine file path based on layout
    if layout == RepositoryLayout.STANDARD:
        # Standard layout: context files in context/ subdirectory
        file_path = f"context/{config_filename}"
    else:
        # Legacy layout: files at root
        file_path = config_filename

    # Handle plain local paths (without file:// scheme)
    if not config_url.startswith(('file://', 'http://', 'https://')):
        # Plain local path - expand user directory and resolve
        local_path = Path(config_url).expanduser().resolve()
        config_file = local_path / file_path

        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        return config_file.read_text(encoding='utf-8')

    if config_url.startswith('file://'):
        # Local file path
        local_path = Path(config_url.replace('file://', ''))
        config_file = local_path / file_path

        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        return config_file.read_text(encoding='utf-8')

    elif config_url.startswith('http://') or config_url.startswith('https://'):
        # HTTP(S) URL - download from remote

        # Construct URL to config file
        if 'github.com' in config_url:
            # Convert GitHub repo URL to raw content URL
            # https://github.com/user/repo/path → https://raw.githubusercontent.com/user/repo/main/path/context/ENTERPRISE.md
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

            # Add file path (includes context/ for standard layout)
            raw_url = raw_url.rstrip('/') + '/' + file_path

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

            # Add file path (includes context/ for standard layout)
            raw_url = raw_url.rstrip('/') + '/' + file_path

        else:
            # Generic URL - assume it points to directory
            raw_url = config_url.rstrip('/') + '/' + file_path

        # Download content
        try:
            from devflow.utils.ssl_helper import get_ssl_verify_setting, get_request_timeout
            ssl_verify = get_ssl_verify_setting()
            timeout = get_request_timeout()

            response = requests.get(raw_url, timeout=timeout, verify=ssl_verify)
            response.raise_for_status()
            return response.text
        except requests.exceptions.SSLError as e:
            # SSL certificate verification failed - provide helpful guidance
            error_msg = (
                f"SSL certificate verification failed for {raw_url}\n"
                f"Error: {e}\n\n"
                f"Solutions:\n"
                f"  1. Use custom CA bundle (RECOMMENDED for production):\n"
                f"     export DAF_SSL_VERIFY=/path/to/ca-bundle.crt\n"
                f"     daf upgrade\n\n"
                f"  2. Disable SSL verification (INSECURE - testing only):\n"
                f"     export DAF_SSL_VERIFY=false\n"
                f"     daf upgrade\n\n"
                f"  3. Configure permanently in organization.json:\n"
                f"     {{\n"
                f"       \"http_client\": {{\n"
                f"         \"ssl_verify\": \"/path/to/ca-bundle.crt\"\n"
                f"       }}\n"
                f"     }}\n\n"
                f"See docs/ssl-configuration.md for more information."
            )
            raise ValueError(error_msg)
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
    quiet: bool = False,
    sync_json: bool = True
) -> Tuple[List[str], List[str], List[str]]:
    """Install organization-specific skills from hierarchical config files.

    Supports two repository layouts:
    1. Standard (v3.0+): configs/, context/, daf-skills/ subdirectories
       - Downloads JSON configs from configs/ with automatic backups
       - Downloads context files from context/
       - Dynamically discovers and installs ALL skills from daf-skills/

    2. Legacy: Files at root with skill_url in frontmatter
       - Downloads context files from root
       - Installs skills referenced in frontmatter

    Args:
        dry_run: If True, only report what would be installed without installing
        quiet: If True, suppress console output (errors still shown)
        sync_json: If True, download and update JSON config files (standard layout only)

    Returns:
        Tuple of (changed, up_to_date, failed) skill/config names
        - changed: Items that were installed or updated
        - up_to_date: Items that were already up-to-date
        - failed: Items that failed to install
    """
    import json
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

    # JSON config files to sync (standard layout only)
    json_configs = ["enterprise.json", "organization.json", "team.json"]

    changed = []
    up_to_date = []
    failed = []

    # Check if hierarchical_config_source is configured
    # NEW LOCATION (since v3.0): config.json (user config) - repos.hierarchical_config_source
    # OLD LOCATION (deprecated): organization.json - hierarchical_config_source
    # Try new location first, fall back to old location for backward compatibility
    user_config_path = cs_home / "config.json"
    org_config_path = cs_home / "organization.json"
    config_source = None

    # Try new location first (config.repos.hierarchical_config_source)
    if user_config_path.exists():
        try:
            with open(user_config_path, 'r') as f:
                user_config = json.load(f)
                repos = user_config.get('repos', {})
                config_source = repos.get('hierarchical_config_source')
        except Exception as e:
            if not quiet:
                console.print(f"[yellow]⚠[/yellow] Could not read config.json: {e}")

    # Fall back to old location for backward compatibility (organization.json)
    if not config_source and org_config_path.exists():
        try:
            with open(org_config_path, 'r') as f:
                org_config = json.load(f)
                old_source = org_config.get('hierarchical_config_source')
                if old_source:
                    if not quiet:
                        console.print("[yellow]⚠ hierarchical_config_source in organization.json is deprecated[/yellow]")
                        console.print("[yellow]  Please move it to config.json under repos.hierarchical_config_source[/yellow]")
                    config_source = old_source
        except Exception as e:
            if not quiet:
                console.print(f"[yellow]⚠[/yellow] Could not read organization.json: {e}")

    if config_source:
        if not quiet:
            console.print(f"[cyan]Syncing from:[/cyan] {config_source}")

        # Detect repository layout
        layout = detect_repository_layout(config_source)
        if not quiet:
            layout_name = "standard" if layout == RepositoryLayout.STANDARD else "legacy"
            console.print(f"[dim]Detected {layout_name} repository layout[/dim]")

        # ============================================================
        # STEP 1: Download JSON config files (STANDARD LAYOUT ONLY)
        # ============================================================
        if layout == RepositoryLayout.STANDARD and sync_json:
            if not quiet:
                console.print("\n[bold cyan]Syncing JSON configuration files...[/bold cyan]")

            for json_file in json_configs:
                try:
                    # Download JSON config
                    json_data = download_json_config(config_source, json_file, layout)

                    if json_data is None:
                        # File doesn't exist in repo - that's OK
                        if not quiet:
                            console.print(f"[dim]No {json_file} in repository, skipping[/dim]")
                        continue

                    target_path = cs_home / json_file

                    # Check if file would change
                    json_str = json.dumps(json_data, indent=2)
                    if has_file_changed(target_path, json_str):
                        if dry_run:
                            if not quiet:
                                console.print(f"[yellow]Would update:[/yellow] {json_file}")
                            changed.append(json_file)
                        else:
                            # Create backup before overwriting
                            if target_path.exists():
                                backup_path = create_backup(target_path)
                                if not quiet and backup_path:
                                    console.print(f"[dim]Backed up to: {backup_path.name}[/dim]")

                            # Write updated JSON
                            target_path.write_text(json_str + '\n', encoding='utf-8')

                            if not quiet:
                                console.print(f"[green]✓[/green] Updated {json_file}")
                            changed.append(json_file)
                    else:
                        if not quiet:
                            console.print(f"[dim]{json_file} is up-to-date[/dim]")
                        up_to_date.append(json_file)

                except Exception as e:
                    if not quiet:
                        console.print(f"[red]✗[/red] Failed to sync {json_file}: {e}")
                    failed.append(json_file)

        # ============================================================
        # STEP 2: Download context files (.md)
        # ============================================================
        if not quiet:
            console.print("\n[bold cyan]Syncing context files...[/bold cyan]")

        for order_num, config_file, level_name in hierarchy:
            try:
                # Download context file
                config_content = download_hierarchical_config_file(config_source, config_file, layout)

                target_path = cs_home / config_file

                # Check if file would change
                if has_file_changed(target_path, config_content):
                    if dry_run:
                        if not quiet:
                            console.print(f"[yellow]Would update:[/yellow] {config_file}")
                        changed.append(config_file)
                    else:
                        # Write context file
                        target_path.write_text(config_content, encoding='utf-8')
                        if not quiet:
                            console.print(f"[green]✓[/green] Updated {config_file}")
                        changed.append(config_file)
                else:
                    if not quiet:
                        console.print(f"[dim]{config_file} is up-to-date[/dim]")
                    up_to_date.append(config_file)

            except FileNotFoundError:
                # File doesn't exist in repo - that's OK
                if not quiet:
                    console.print(f"[dim]No {config_file} in repository, skipping[/dim]")
            except Exception as e:
                if not quiet:
                    console.print(f"[yellow]⚠[/yellow] Could not download {config_file}: {e}")
                # Continue with next file even if this one fails

        # ============================================================
        # STEP 3: Install skills
        # ============================================================
        if not quiet:
            console.print("\n[bold cyan]Installing skills...[/bold cyan]")

        if layout == RepositoryLayout.STANDARD:
            # STANDARD LAYOUT: Dynamically discover and install ALL skills from daf-skills/
            skill_dirs = list_remote_skills(config_source, layout)

            if not skill_dirs:
                if not quiet:
                    console.print("[dim]No skills found in daf-skills/ directory[/dim]")
            else:
                if not quiet:
                    console.print(f"[dim]Discovered {len(skill_dirs)} skill(s)[/dim]")

                for skill_dir_name in skill_dirs:
                    try:
                        # Construct skill URL
                        if config_source.startswith('http://') or config_source.startswith('https://'):
                            # For remote, construct URL to skill directory
                            if 'github.com' in config_source:
                                # GitHub raw URL
                                raw_url = config_source.replace('github.com', 'raw.githubusercontent.com')
                                parts = raw_url.replace('https://raw.githubusercontent.com/', '').split('/')
                                if len(parts) >= 2:
                                    if len(parts) == 2 or not re.match(r'^(main|master|develop|v\d+).*', parts[2]):
                                        raw_url = f"https://raw.githubusercontent.com/{parts[0]}/{parts[1]}/main"
                                        if len(parts) > 2:
                                            raw_url += "/" + "/".join(parts[2:])
                                skill_url = raw_url.rstrip('/') + f'/daf-skills/{skill_dir_name}'
                            elif 'gitlab.com' in config_source:
                                # GitLab raw URL
                                if '/-/raw/' not in config_source:
                                    base_url = config_source.split('/tree/', 1)[0] if '/tree/' in config_source else config_source
                                    skill_url = base_url.rstrip('/') + f'/-/raw/main/daf-skills/{skill_dir_name}'
                                else:
                                    skill_url = config_source.rstrip('/') + f'/daf-skills/{skill_dir_name}'
                            else:
                                skill_url = config_source.rstrip('/') + f'/daf-skills/{skill_dir_name}'
                        else:
                            # For local paths
                            if config_source.startswith('file://'):
                                local_base = Path(config_source.replace('file://', ''))
                            else:
                                local_base = Path(config_source).expanduser().resolve()
                            skill_url = str(local_base / 'daf-skills' / skill_dir_name)

                        # Download skill content
                        if dry_run:
                            if not quiet:
                                console.print(f"[yellow]Would install:[/yellow] {skill_dir_name}")
                            changed.append(skill_dir_name)
                        else:
                            skill_content = download_skill(skill_url)

                            # Install to ~/.claude/skills/{skill_dir_name}/
                            skill_install_path = skills_install_dir / skill_dir_name
                            skill_file = skill_install_path / "SKILL.md"

                            # Check if skill has changed
                            if has_file_changed(skill_file, skill_content):
                                # Create skill directory
                                skill_install_path.mkdir(parents=True, exist_ok=True)

                                # Write SKILL.md
                                skill_file.write_text(skill_content, encoding='utf-8')

                                if not quiet:
                                    console.print(f"[green]✓[/green] Installed skill: {skill_dir_name}")
                                changed.append(skill_dir_name)
                            else:
                                if not quiet:
                                    console.print(f"[dim]{skill_dir_name} is up-to-date[/dim]")
                                up_to_date.append(skill_dir_name)

                    except Exception as e:
                        if not quiet:
                            console.print(f"[red]✗[/red] Failed to install skill {skill_dir_name}: {e}")
                        failed.append(skill_dir_name)

        else:
            # LEGACY LAYOUT: Install skills from frontmatter references
            # Create a temporary Path object for relative URL resolution
            if config_source.startswith('file://'):
                source_base = Path(config_source.replace('file://', ''))
            elif not config_source.startswith(('http://', 'https://')):
                source_base = Path(config_source).expanduser().resolve()
            else:
                source_base = cs_home

            for order_num, config_file, level_name in hierarchy:
                config_path = cs_home / config_file

                if not config_path.exists():
                    continue

                # Extract skill_url from frontmatter
                skill_url = extract_skill_url(config_path)

                if not skill_url:
                    continue

                skill_dir_name = f"{order_num:02d}-{level_name}"
                skill_install_path = skills_install_dir / skill_dir_name

                try:
                    temp_config_path = source_base / config_file

                    if dry_run:
                        if not quiet:
                            console.print(f"[yellow]Would install:[/yellow] {skill_dir_name} from {skill_url}")
                        changed.append(skill_dir_name)
                    else:
                        # Download skill content
                        skill_content = download_skill(skill_url, config_file_path=temp_config_path)

                        # Check if skill has changed
                        skill_file = skill_install_path / "SKILL.md"

                        if has_file_changed(skill_file, skill_content):
                            # Create skill directory
                            skill_install_path.mkdir(parents=True, exist_ok=True)

                            # Write SKILL.md
                            skill_file.write_text(skill_content, encoding='utf-8')

                            if not quiet:
                                console.print(f"[green]✓[/green] Installed skill: {skill_dir_name}")
                            changed.append(skill_dir_name)
                        else:
                            if not quiet:
                                console.print(f"[dim]{skill_dir_name} is up-to-date[/dim]")
                            up_to_date.append(skill_dir_name)

                except Exception as e:
                    if not quiet:
                        console.print(f"[red]✗[/red] Failed to install skill {skill_dir_name}: {e}")
                    failed.append(skill_dir_name)

    # Also install skills from config files that are already in $DEVAIFLOW_HOME
    # (but weren't downloaded from hierarchical_config_source)
    # This handles the case where user has local config files without config_source
    elif not config_source:
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
