"""Implementation of 'daf config context' commands."""

from rich.console import Console
from rich.prompt import Prompt

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.config.models import ContextFile

console = Console()


def list_context_files() -> None:
    """List all configured context files (including defaults)."""
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    # Default context files (always included)
    default_files = [
        ("AGENTS.md", "agent-specific instructions"),
        ("CLAUDE.md", "project guidelines and standards"),
    ]

    # User-configured context files
    configured_files = [(f.path, f.description) for f in config.context_files.files]

    console.print("\n[bold]Context Files for Initial Prompt[/bold]\n")

    # Show defaults
    console.print("[cyan]Default Files (always included):[/cyan]")
    for path, description in default_files:
        console.print(f"  • {path} - {description}")

    # Show configured files if any
    if configured_files:
        console.print("\n[cyan]Additional Configured Files:[/cyan]")
        for i, (path, description) in enumerate(configured_files, 1):
            console.print(f"  {i}. {path} - {description}")
    else:
        console.print("\n[dim]No additional context files configured[/dim]")

    console.print()
    console.print("[dim]Claude auto-detects which tool to use based on the path:[/dim]")
    console.print("[dim]  - Local paths → Read tool[/dim]")
    console.print("[dim]  - HTTP/HTTPS URLs → WebFetch tool[/dim]")
    console.print()


@require_outside_claude
def add_context_file(path: str, description: str) -> None:
    """Add a context file to the configuration.

    Args:
        path: File path (local) or URL (GitHub/GitLab)
        description: Human-readable description
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    # Prompt for path if not provided
    if not path:
        console.print("\n[bold]Add Context File[/bold]")
        console.print("[dim]Enter a local file path or URL[/dim]\n")
        console.print("[dim]Examples:[/dim]")
        console.print("[dim]  ARCHITECTURE.md[/dim]")
        console.print("[dim]  https://github.com/YOUR-ORG/.github/blob/main/STANDARDS.md[/dim]")
        console.print()
        path = Prompt.ask("File path or URL")

    if not path or not path.strip():
        console.print("[yellow]⚠[/yellow] Path cannot be empty")
        return

    path = path.strip()

    # Check if path already exists in configured files
    for existing_file in config.context_files.files:
        if existing_file.path == path:
            console.print(f"[yellow]⚠[/yellow] Context file already exists: {path}")
            return

    # Check if path is one of the default files (not allowed to add)
    default_paths = ["AGENTS.md", "CLAUDE.md"]
    if path in default_paths:
        console.print(f"[yellow]⚠[/yellow] {path} is a default context file (always included)")
        console.print("[dim]You don't need to add it explicitly[/dim]")
        return

    # Prompt for description if not provided
    if not description:
        console.print()
        console.print("[dim]Examples: 'coding standards', 'system architecture', 'internal docs'[/dim]")
        description = Prompt.ask("Description")

    if not description or not description.strip():
        console.print("[yellow]⚠[/yellow] Description cannot be empty")
        return

    description = description.strip()

    # Add to config
    context_file = ContextFile(path=path, description=description)
    config.context_files.files.append(context_file)

    # Save config
    config_loader.save_config(config)

    console.print(f"\n[green]✓[/green] Added context file: {path}")
    console.print(f"[dim]Description: {description}[/dim]")


@require_outside_claude
def remove_context_file(path: str) -> None:
    """Remove a context file from the configuration.

    Args:
        path: File path or URL to remove
    """
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.context_files.files:
        console.print("[yellow]⚠[/yellow] No configured context files to remove")
        return

    # If path not provided, show list and prompt for selection
    if not path:
        console.print("\n[bold]Remove Context File[/bold]\n")

        # Show configured files
        console.print("[cyan]Configured context files:[/cyan]")
        for i, context_file in enumerate(config.context_files.files, 1):
            console.print(f"  {i}. {context_file.path} - {context_file.description}")

        console.print()
        choice = Prompt.ask(
            "Enter number or path to remove (or 'cancel' to exit)",
            default="cancel"
        )

        if choice.lower() == "cancel":
            console.print("[dim]Cancelled[/dim]")
            return

        # Check if choice is a number
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(config.context_files.files):
                path = config.context_files.files[index].path
            else:
                console.print(f"[red]✗[/red] Invalid selection. Choose 1-{len(config.context_files.files)}")
                return
        else:
            path = choice.strip()

    # Find and remove the file
    original_count = len(config.context_files.files)
    config.context_files.files = [
        f for f in config.context_files.files if f.path != path
    ]

    if len(config.context_files.files) == original_count:
        console.print(f"[red]✗[/red] Context file not found: {path}")
        return

    # Save config
    config_loader.save_config(config)

    console.print(f"\n[green]✓[/green] Removed context file: {path}")


@require_outside_claude
def reset_context_files() -> None:
    """Reset context files to defaults (clear all configured files)."""
    from rich.prompt import Confirm

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.context_files.files:
        console.print("[yellow]⚠[/yellow] No configured context files to reset")
        console.print("[dim]Already using defaults only (AGENTS.md, CLAUDE.md)[/dim]")
        return

    # Confirm reset
    console.print(f"\n[yellow]This will remove {len(config.context_files.files)} configured context file(s)[/yellow]")
    console.print("[dim]Default files (AGENTS.md, CLAUDE.md) will still be included[/dim]")

    if not Confirm.ask("\nContinue?", default=False):
        console.print("[dim]Cancelled[/dim]")
        return

    # Clear configured files
    config.context_files.files = []

    # Save config
    config_loader.save_config(config)

    console.print("\n[green]✓[/green] Reset to default context files")
    console.print("[dim]Only AGENTS.md and CLAUDE.md will be included in initial prompts[/dim]")
