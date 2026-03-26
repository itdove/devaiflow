"""GitHub authentication and pre-flight checks.

This module provides authentication validation and smart error handling for GitHub operations.
Key features:
- Environment detection (CI/CD vs interactive)
- Pre-flight repository access checks
- Fine-grained token requirement detection
- Actionable error messages without auto-prompting
"""

import os
import subprocess
import sys
from typing import Tuple

from rich.console import Console

console = Console()


def is_interactive_environment() -> bool:
    """Detect if we're in an interactive terminal or automated environment.

    Returns:
        True if interactive, False if in CI/CD or non-interactive environment

    Checks:
        - CI/CD environment variables (CI, GITHUB_ACTIONS, GITLAB_CI, JENKINS_HOME)
        - stdin.isatty() to detect terminal
        - DAF_NO_PROMPT environment variable
    """
    # Check for CI/CD environments
    ci_env_vars = ['CI', 'GITHUB_ACTIONS', 'GITLAB_CI', 'JENKINS_HOME', 'CIRCLECI', 'TRAVIS']
    if any(os.getenv(var) for var in ci_env_vars):
        return False

    # Check if stdin is a terminal
    if not sys.stdin.isatty():
        return False

    # Check for explicit DAF_NO_PROMPT
    if os.getenv('DAF_NO_PROMPT') == '1':
        return False

    return True


def check_gh_auth_for_repo(repository: str) -> Tuple[bool, str, str]:
    """Check if gh is authenticated and has access to repository.

    Args:
        repository: Repository in owner/repo format

    Returns:
        Tuple of (authenticated, error_type, error_message)

        error_type values:
        - 'ok': Authentication successful
        - 'not_authenticated': Not logged in to GitHub
        - 'insufficient_permissions': Authentication invalid or expired
        - 'fine_grained_required': Repository requires fine-grained token
        - 'not_found': Repository not found or no access
        - 'unknown': Other error

    Examples:
        >>> check_gh_auth_for_repo("owner/repo")
        (True, 'ok', '')

        >>> check_gh_auth_for_repo("restricted-org/repo")
        (False, 'fine_grained_required', 'Repository requires fine-grained token')
    """
    # Quick check: is gh authenticated at all?
    result = subprocess.run(
        ['gh', 'auth', 'status'],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        return False, 'not_authenticated', 'Not logged in to GitHub'

    # Test repository access with minimal API call
    result = subprocess.run(
        ['gh', 'api', f'/repos/{repository}', '--jq', '.name'],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode == 0:
        return True, 'ok', ''

    # Parse error to determine specific issue
    stderr = result.stderr

    # Fine-grained token requirement
    if 'forbids access via a personal access token (classic)' in stderr:
        return False, 'fine_grained_required', 'Repository requires fine-grained token'

    # Not found or no access
    if 'Not Found' in stderr or '404' in stderr:
        return False, 'not_found', 'Repository not found or no access'

    # Bad credentials or expired token
    if 'Bad credentials' in stderr or '401' in stderr:
        return False, 'insufficient_permissions', 'Authentication invalid or expired'

    # Forbidden (different from 404)
    if 'Forbidden' in stderr or '403' in stderr:
        return False, 'insufficient_permissions', 'Insufficient permissions'

    # Unknown error
    return False, 'unknown', stderr.strip()


def handle_auth_error(repository: str, error_type: str, error_message: str) -> None:
    """Provide actionable error message based on environment and error type.

    Args:
        repository: Repository that failed authentication
        error_type: Error type from check_gh_auth_for_repo()
        error_message: Error message from check_gh_auth_for_repo()

    Raises:
        SystemExit: Always exits after displaying error message

    Displays different messages for interactive vs non-interactive environments.
    Never auto-prompts for browser login.
    """
    from devflow.issue_tracker.exceptions import IssueTrackerAuthError

    is_interactive = is_interactive_environment()

    console.print(f"\n[red]✗[/red] GitHub authentication failed for {repository}")
    console.print(f"[dim]Reason: {error_message}[/dim]\n")

    if error_type == 'not_authenticated':
        console.print("[bold]Solution:[/bold] Run the following command to authenticate:")
        console.print("  [cyan]gh auth login[/cyan]")
        console.print("\nOr set a personal access token:")
        console.print("  [cyan]export GITHUB_TOKEN=ghp_xxxxxxxxxxxx[/cyan]")

    elif error_type == 'fine_grained_required':
        console.print("[bold]Solution:[/bold] This repository requires a fine-grained personal access token.")
        console.print("\n[bold]1.[/bold] Create a fine-grained token:")
        console.print("   https://github.com/settings/personal-access-tokens/new")
        console.print(f"\n[bold]2.[/bold] Grant access to repository: [cyan]{repository}[/cyan]")
        console.print("\n[bold]3.[/bold] Authenticate with the new token:")
        console.print("   [cyan]gh auth login[/cyan]")
        console.print("   [dim]or[/dim]")
        console.print("   [cyan]export GITHUB_TOKEN=github_pat_xxxxxxxxxxxx[/cyan]")

    elif error_type == 'not_found':
        console.print("[bold]Troubleshooting:[/bold]")
        console.print("[bold]1.[/bold] Verify repository exists and you have access")
        console.print("[bold]2.[/bold] Check if you're authenticated to the correct GitHub account:")
        console.print("   [cyan]gh auth status[/cyan]")
        console.print("[bold]3.[/bold] For private repos, ensure your token has 'repo' scope")

    elif error_type == 'insufficient_permissions':
        console.print("[bold]Solution:[/bold] Re-authenticate with sufficient permissions:")
        console.print("  [cyan]gh auth refresh -s repo -s workflow[/cyan]")
        console.print("\nOr create a new token with 'repo' scope:")
        console.print("  https://github.com/settings/tokens/new")

    else:
        # Unknown error - show raw error
        console.print("[bold]Error details:[/bold]")
        console.print(f"  [dim]{error_message}[/dim]")
        console.print("\n[bold]Troubleshooting:[/bold]")
        console.print("[bold]1.[/bold] Check authentication status:")
        console.print("   [cyan]gh auth status[/cyan]")
        console.print("[bold]2.[/bold] Try re-authenticating:")
        console.print("   [cyan]gh auth login[/cyan]")

    # Only offer interactive help if truly interactive
    if is_interactive:
        console.print("\n[dim]Tip: Run 'gh auth login' to set up authentication interactively[/dim]")
    else:
        console.print("\n[dim]Note: Running in non-interactive mode (CI/automation detected)[/dim]")

    raise IssueTrackerAuthError(f"GitHub authentication required for {repository}")
