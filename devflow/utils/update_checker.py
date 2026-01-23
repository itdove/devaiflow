"""Update checker for DevAIFlow.

Checks GitHub releases for new versions and caches results to avoid slowing down commands.
Only checks when installed via pip (not in development/editable mode).
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import requests

from devflow import __version__


def _is_development_install() -> bool:
    """Check if daf is installed in development/editable mode.

    Returns:
        True if installed in editable mode, False otherwise
    """
    # Check if installed in editable mode by looking for .egg-link file
    # or if running from source directory
    try:
        import devflow
        daf_path = Path(devflow.__file__).parent.parent

        # If we can find setup.py in the parent directory, it's likely a dev install
        if (daf_path / "setup.py").exists():
            return True

        # Check for .egg-link in site-packages
        import site
        for site_packages in site.getsitepackages() + [site.getusersitepackages()]:
            if site_packages and Path(site_packages).exists():
                egg_link = Path(site_packages) / "devaiflow.egg-link"
                if egg_link.exists():
                    return True

        return False
    except Exception:
        # If we can't determine, assume it's a regular install to be safe
        return False


def _get_cache_file() -> Path:
    """Get path to version check cache file.

    Returns:
        Path to cache file
    """
    # Use the same session home as devflow tool
    from devflow.utils.paths import get_cs_home
    cache_dir = get_cs_home()

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "version_check_cache.json"


def _read_cache() -> Optional[dict]:
    """Read cached version check data.

    Returns:
        Cached data dict or None if cache doesn't exist or is invalid
    """
    cache_file = _get_cache_file()

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _write_cache(data: dict) -> None:
    """Write version check data to cache.

    Args:
        data: Data to cache
    """
    cache_file = _get_cache_file()

    try:
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
    except IOError:
        # Silently fail if we can't write cache
        pass


def _is_cache_valid(cache: dict, max_age_hours: int = 24) -> bool:
    """Check if cache is still valid.

    Args:
        cache: Cached data dict
        max_age_hours: Maximum age in hours before cache is stale

    Returns:
        True if cache is valid, False if stale
    """
    if not cache or "timestamp" not in cache:
        return False

    try:
        cached_time = datetime.fromisoformat(cache["timestamp"])
        age = datetime.now() - cached_time
        return age < timedelta(hours=max_age_hours)
    except (ValueError, TypeError):
        return False


def _parse_version(version: str) -> Tuple[int, ...]:
    """Parse version string into tuple of integers for comparison.

    Args:
        version: Version string (e.g., "1.0.0", "1.0.0-dev")

    Returns:
        Tuple of version numbers (e.g., (1, 0, 0))
    """
    if not version or not isinstance(version, str):
        return (0, 0, 0)

    # Remove -dev suffix if present
    version = version.split("-")[0]

    try:
        return tuple(int(x) for x in version.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _get_timeout_from_config() -> int:
    """Load update checker timeout from config.

    Returns:
        Timeout in seconds (default: 10)
    """
    try:
        from devflow.config.loader import ConfigLoader

        config_loader = ConfigLoader()
        config = config_loader.load_config()
        return config.update_checker_timeout
    except Exception:
        # If config loading fails, use default timeout
        return 10


def _fetch_latest_version_from_github(timeout: int = 10) -> Tuple[Optional[str], bool]:
    """Fetch latest release version from GitHub releases API.

    Args:
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Tuple of (version_string, network_error):
            - version_string: Latest version (e.g., "1.0.0") or None if fetch failed
            - network_error: True if error was network-related (connectivity), False otherwise
    """
    # GitHub API details
    github_api = "api.github.com"
    repo_path = "itdove/devaiflow"

    # GitHub API endpoint for latest release
    api_url = f"https://{github_api}/repos/{repo_path}/releases/latest"

    try:
        # Make request with configurable timeout
        response = requests.get(api_url, timeout=timeout)

        if response.status_code != 200:
            return None, False

        release = response.json()

        if not release or not isinstance(release, dict):
            return None, False

        # Extract tag name (should be like "v1.0.0")
        tag_name = release.get("tag_name", "")

        # Remove "v" prefix if present
        if tag_name.startswith("v"):
            tag_name = tag_name[1:]

        return (tag_name if tag_name else None), False

    except requests.ConnectionError:
        # Connection error - actual network connectivity issue
        return None, True
    except (requests.Timeout, requests.HTTPError, requests.TooManyRedirects, requests.RequestException):
        # Other request failures (timeout, HTTP errors, SSL errors, etc.) - not network issues
        # Handle silently without showing warning
        return None, False
    except (json.JSONDecodeError, KeyError):
        # JSON parsing error or unexpected response structure (not a network issue)
        return None, False


def check_for_updates() -> Tuple[Optional[str], bool]:
    """Check if a newer version is available.

    This function:
    1. Skips check if installed in development mode
    2. Uses cached result if available and fresh (< 24 hours old)
    3. Fetches latest version from GitHub releases API
    4. Caches the result for future checks

    Returns:
        Tuple of (latest_version, network_error):
            - latest_version: Latest version string if update available, None otherwise
            - network_error: True if GitHub was unreachable (network issue), False otherwise
    """
    # Skip check in development mode
    if _is_development_install():
        return None, False

    # Check cache first
    cache = _read_cache()
    if cache and _is_cache_valid(cache):
        latest_version = cache.get("latest_version")
        if latest_version:
            # Compare with current version
            current = _parse_version(__version__)
            latest = _parse_version(latest_version)

            if latest > current:
                return latest_version, False
        return None, False

    # Load timeout from config (default: 10 seconds)
    timeout = _get_timeout_from_config()

    # Fetch latest version from GitHub
    latest_version, network_error = _fetch_latest_version_from_github(timeout=timeout)

    # If network error (connectivity issue), don't cache and return error flag
    if network_error:
        return None, True

    # Cache the result (only if no network error)
    cache_data = {
        "timestamp": datetime.now().isoformat(),
        "latest_version": latest_version,
        "current_version": __version__
    }
    _write_cache(cache_data)

    # Compare versions if we got a result
    if latest_version:
        current = _parse_version(__version__)
        latest = _parse_version(latest_version)

        if latest > current:
            return latest_version, False

    return None, False


def show_update_notification(latest_version: str) -> None:
    """Display update notification to user.

    Args:
        latest_version: The latest available version
    """
    from rich.console import Console

    console = Console()
    console.print()
    console.print(f"[yellow]╭─ Update Available ──────────────────────────────────────────╮[/yellow]")
    console.print(f"[yellow]│[/yellow]  A new version of daf is available: [green]{latest_version}[/green] (current: {__version__})  [yellow]│[/yellow]")
    console.print(f"[yellow]│[/yellow]  Run [cyan]pip install --upgrade --force-reinstall .[/cyan]               [yellow]│[/yellow]")
    console.print(f"[yellow]╰─────────────────────────────────────────────────────────────╯[/yellow]")
    console.print()


def show_network_warning() -> None:
    """Display warning when GitHub is unreachable (network connectivity issue)."""
    from rich.console import Console

    console = Console()
    console.print()
    console.print(f"[yellow]⚠️  Unable to check for updates - GitHub not reachable[/yellow]")
    console.print(f"[dim]   (Check network connectivity to check for new versions)[/dim]")
    console.print()
