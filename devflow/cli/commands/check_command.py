"""Implementation of 'daf check' command."""

import json
import sys
from typing import Dict

from rich.console import Console
from rich.table import Table

from devflow.utils.dependencies import get_all_tools_status

console = Console()


def check_dependencies(output_json: bool = False) -> int:
    """Check status of all external tool dependencies.

    Args:
        output_json: If True, output JSON format instead of text

    Returns:
        Exit code: 0 if all required tools available, 1 otherwise
    """
    tools_status = get_all_tools_status()

    if output_json:
        # JSON output for machine-readable format
        print(json.dumps({
            "success": True,
            "data": {
                "tools": tools_status,
                "all_required_available": all(
                    status["available"] == "true"
                    for tool, status in tools_status.items()
                    if status["required"] == "true"
                )
            }
        }, indent=2))
        return 0 if all(
            status["available"] == "true"
            for tool, status in tools_status.items()
            if status["required"] == "true"
        ) else 1

    # Text output with rich formatting
    console.print("\n[bold]Checking dependencies for DevAIFlow...[/bold]\n")

    # Separate required and optional tools
    required_tools = {
        tool: status for tool, status in tools_status.items()
        if status["required"] == "true"
    }
    optional_tools = {
        tool: status for tool, status in tools_status.items()
        if status["required"] == "false"
    }

    # Display required dependencies
    console.print("[bold cyan]Required Dependencies:[/bold cyan]")
    _display_tools_table(required_tools)
    console.print()

    # Display optional dependencies
    console.print("[bold cyan]Optional Dependencies:[/bold cyan]")
    _display_tools_table(optional_tools)
    console.print()

    # Summary
    required_missing = [
        tool for tool, status in required_tools.items()
        if status["available"] == "false"
    ]
    optional_missing = [
        tool for tool, status in optional_tools.items()
        if status["available"] == "false"
    ]

    if not required_missing:
        console.print("[bold green]✓ All required dependencies available[/bold green]")
    else:
        console.print(f"[bold red]✗ Missing required dependencies: {', '.join(required_missing)}[/bold red]")
        return 1

    if optional_missing:
        console.print(
            f"[yellow]⚠ Some optional features unavailable: {', '.join(optional_missing)}[/yellow]"
        )

    return 0


def _display_tools_table(tools: Dict[str, Dict[str, str]]) -> None:
    """Display a table of tools and their status.

    Args:
        tools: Dictionary of tool names to status information
    """
    table = Table(show_header=True, header_style="bold")
    table.add_column("Tool", style="cyan", width=12)
    table.add_column("Status", width=10)
    table.add_column("Version", width=20)
    table.add_column("Description", width=30)

    for tool, status in tools.items():
        available = status["available"] == "true"
        version = status["version"] if available else ""
        description = status["description"]

        if available:
            status_icon = "[green]✓[/green]"
        else:
            status_icon = "[red]✗[/red]"
            install_url = status.get("install_url", "")
            if install_url:
                description += f"\n[dim]Install: {install_url}[/dim]"

        table.add_row(
            tool,
            status_icon,
            version,
            description
        )

    console.print(table)
