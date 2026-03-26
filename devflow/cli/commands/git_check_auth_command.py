"""Implementation of 'daf git check-auth' command."""

import subprocess
import sys
import click
from rich.console import Console
from rich.table import Table

from devflow.github.auth import check_gh_auth_for_repo
from devflow.utils.git_remote import GitRemoteDetector

console = Console()


@click.command(name="check-auth")
@click.argument('repository', required=False)
def check_auth_command(repository):
    """Check GitHub authentication and repository access.

    REPOSITORY: Optional repository in owner/repo format.
                If not provided, auto-detects from git remotes.

    Examples:
        daf git check-auth owner/repo
        daf git check-auth  # Auto-detect from git remote
    """
    # Auto-detect repository if not provided
    if not repository:
        detector = GitRemoteDetector()
        repository = detector.get_github_repository()

        if not repository:
            console.print("[red]✗[/red] No repository specified and auto-detection failed")
            console.print("\n[bold]Solutions:[/bold]")
            console.print("  1. Run command in a git repository with GitHub remote")
            console.print("  2. Specify repository explicitly:")
            console.print("     [cyan]daf git check-auth owner/repo[/cyan]")
            sys.exit(1)

    # Check if gh CLI is installed
    try:
        subprocess.run(['gh', '--version'], capture_output=True, check=True, timeout=5)
    except FileNotFoundError:
        console.print("[red]✗[/red] GitHub CLI (gh) not found")
        console.print("\n[bold]Install GitHub CLI:[/bold]")
        console.print("  https://cli.github.com/")
        sys.exit(1)
    except subprocess.CalledProcessError:
        pass  # Version command failed, but gh exists

    # Perform authentication check
    console.print(f"[bold]Checking GitHub authentication for:[/bold] {repository}\n")

    authenticated, error_type, error_message = check_gh_auth_for_repo(repository)

    if authenticated:
        console.print("[green]✓[/green] GitHub authentication: [green]OK[/green]")
        console.print("[green]✓[/green] Repository access: [green]OK[/green]")

        # Get additional details if possible
        try:
            # Get authenticated user
            result = subprocess.run(
                ['gh', 'api', '/user', '--jq', '.login'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                username = result.stdout.strip()
                console.print(f"\n[dim]Account:[/dim] {username}")

            # Get token type (check for fine-grained token scopes)
            result = subprocess.run(
                ['gh', 'auth', 'status'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                output = result.stdout + result.stderr
                if 'Token:' in output:
                    # Extract token type info
                    for line in output.split('\n'):
                        if 'Token:' in line or 'scopes:' in line.lower():
                            console.print(f"[dim]{line.strip()}[/dim]")

        except Exception:
            pass  # Best effort - don't fail if we can't get details

        sys.exit(0)

    else:
        console.print(f"[red]✗[/red] GitHub authentication: [red]FAILED[/red]")
        console.print(f"[red]✗[/red] Error type: {error_type}")
        console.print(f"[red]✗[/red] Error message: {error_message}\n")

        # Provide actionable guidance
        if error_type == 'fine_grained_required':
            console.print("[yellow]⚠[/yellow]  This repository requires a [bold]fine-grained personal access token[/bold].")
            console.print("\n[bold]Solution:[/bold]")
            console.print("  1. Create fine-grained token: https://github.com/settings/personal-access-tokens/new")
            console.print(f"  2. Grant access to: [cyan]{repository}[/cyan]")
            console.print("  3. Authenticate: [cyan]gh auth login[/cyan]")

        elif error_type == 'not_authenticated':
            console.print("[bold]Solution:[/bold]")
            console.print("  Run: [cyan]gh auth login[/cyan]")
            console.print("  Or set: [cyan]export GITHUB_TOKEN=ghp_xxxxxxxxxxxx[/cyan]")

        elif error_type == 'not_found':
            console.print("[bold]Troubleshooting:[/bold]")
            console.print("  • Verify repository name is correct")
            console.print("  • Check if you have access to this repository")
            console.print("  • Verify authentication: [cyan]gh auth status[/cyan]")

        else:
            console.print("[bold]Troubleshooting:[/bold]")
            console.print("  • Check authentication: [cyan]gh auth status[/cyan]")
            console.print("  • Re-authenticate: [cyan]gh auth login[/cyan]")

        sys.exit(1)
