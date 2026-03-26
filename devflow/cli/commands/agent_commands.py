"""Agent management commands for DevAIFlow.

This module provides commands to manage and switch between different AI agents:
- List available agents with installation status
- Set default agent backend
- Test agent availability
- Show detailed agent information
"""

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

from rich.console import Console
from rich.table import Table

from devflow.agent.factory import create_agent_client
from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.utils.dependencies import check_tool_available, get_tool_version

console = Console()


# Agent metadata mapping
AGENT_METADATA: Dict[str, Dict[str, Any]] = {
    "claude": {
        "name": "Claude Code",
        "description": "Anthropic's official Claude Code CLI",
        "cli_command": "claude",
        "install_url": "https://docs.claude.com/en/docs/claude-code/installation",
        "status": "fully-tested",
        "features": {
            "session_management": True,
            "conversation_export": True,
            "message_counting": True,
            "resume_support": True,
            "skills_support": True,
        },
    },
    "ollama": {
        "name": "Ollama + Claude Code",
        "description": "Local models via Ollama with Claude Code interface",
        "cli_command": "ollama",
        "install_url": "https://ollama.ai/download",
        "status": "fully-tested",
        "features": {
            "session_management": True,
            "conversation_export": True,
            "message_counting": True,
            "resume_support": True,
            "skills_support": True,
        },
        "notes": "Requires both 'ollama' and 'claude' CLI tools",
    },
    "github-copilot": {
        "name": "GitHub Copilot",
        "description": "GitHub Copilot in VS Code",
        "cli_command": "code",
        "install_url": "https://code.visualstudio.com/",
        "status": "experimental",
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "Limited integration - experimental support only",
    },
    "cursor": {
        "name": "Cursor",
        "description": "Cursor AI editor",
        "cli_command": "cursor",
        "install_url": "https://cursor.sh/",
        "status": "experimental",
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "Limited integration - experimental support only",
    },
    "windsurf": {
        "name": "Windsurf",
        "description": "Windsurf (Codeium) editor",
        "cli_command": "windsurf",
        "install_url": "https://codeium.com/windsurf",
        "status": "experimental",
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "Limited integration - experimental support only",
    },
    "aider": {
        "name": "Aider",
        "description": "AI pair programming in terminal",
        "cli_command": "aider",
        "install_url": "https://aider.chat/docs/install.html",
        "status": "experimental",
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "Git-first approach with chat history files",
    },
    "continue": {
        "name": "Continue",
        "description": "VS Code extension for AI assistance",
        "cli_command": "code",
        "install_url": "https://continue.dev/docs/quickstart",
        "status": "experimental",
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "VS Code extension - limited CLI integration",
    },
}


def detect_agent_installation(agent_key: str) -> Dict[str, Any]:
    """Detect if an agent is installed and get its details.

    Args:
        agent_key: Agent identifier (e.g., "claude", "ollama", "cursor")

    Returns:
        Dictionary with installation status:
        {
            "installed": bool,
            "cli_path": Optional[str],
            "version": Optional[str],
            "additional_requirements": List[str],  # Missing requirements
        }
    """
    metadata = AGENT_METADATA.get(agent_key, {})
    cli_command = metadata.get("cli_command")

    if not cli_command:
        return {
            "installed": False,
            "cli_path": None,
            "version": None,
            "additional_requirements": [],
        }

    # Check main CLI command
    cli_path = shutil.which(cli_command)
    installed = cli_path is not None
    version = get_tool_version(cli_command) if installed else None

    # Check additional requirements
    additional_requirements = []

    # Ollama requires both 'ollama' and 'claude'
    if agent_key == "ollama":
        if not shutil.which("claude"):
            additional_requirements.append("claude (Claude Code CLI)")

    return {
        "installed": installed,
        "cli_path": cli_path,
        "version": version,
        "additional_requirements": additional_requirements,
    }


def get_all_agents_status() -> Dict[str, Dict[str, Any]]:
    """Get status of all supported agents.

    Returns:
        Dictionary mapping agent keys to their status information
    """
    status = {}

    for agent_key, metadata in AGENT_METADATA.items():
        detection = detect_agent_installation(agent_key)

        status[agent_key] = {
            "name": metadata["name"],
            "description": metadata["description"],
            "status": metadata["status"],
            "installed": detection["installed"],
            "cli_path": detection["cli_path"],
            "version": detection["version"],
            "cli_command": metadata["cli_command"],
            "install_url": metadata["install_url"],
            "features": metadata["features"],
            "notes": metadata.get("notes"),
            "additional_requirements": detection["additional_requirements"],
        }

    return status


def list_agents(output_json: bool = False) -> None:
    """List all supported agents with installation status.

    Args:
        output_json: If True, output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func

    # Get current default agent from config
    config_loader = ConfigLoader()
    try:
        config = config_loader.load_config()
        default_agent = config.agent_backend if config else "claude"
    except Exception:
        default_agent = "claude"

    # Get agent status
    agents = get_all_agents_status()

    if output_json:
        json_output_func(
            success=True,
            data={
                "default_agent": default_agent,
                "agents": agents,
            }
        )
        return

    # Display as table
    table = Table(title="Available AI Agents")
    table.add_column("Agent", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Status", style="yellow")
    table.add_column("Installed", style="green")
    table.add_column("Default", style="magenta")

    for agent_key, info in agents.items():
        installed_mark = "✓" if info["installed"] else "✗"
        installed_style = "green" if info["installed"] else "red"
        default_mark = "✓" if agent_key == default_agent else ""

        # Status badge
        status_badge = {
            "fully-tested": "[green]Stable[/green]",
            "experimental": "[yellow]Experimental[/yellow]",
        }.get(info["status"], "[dim]Unknown[/dim]")

        table.add_row(
            info["name"],
            info["description"],
            status_badge,
            f"[{installed_style}]{installed_mark}[/{installed_style}]",
            default_mark,
        )

    console.print(table)

    # Show additional notes
    console.print("\n[bold]Legend:[/bold]")
    console.print("  [green]Stable[/green] - Fully tested and supported")
    console.print("  [yellow]Experimental[/yellow] - Limited testing, may have issues")
    console.print()
    console.print("[dim]Note: Only Claude Code and Ollama have been fully tested.[/dim]")
    console.print("[dim]Other agents are experimental and may have limitations.[/dim]")


@require_outside_claude
def set_default_agent(agent_name: Optional[str] = None, output_json: bool = False) -> None:
    """Set the default agent backend.

    Args:
        agent_name: Agent to set as default (e.g., "claude", "ollama")
        output_json: If True, output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func, console_print
    from rich.prompt import Prompt

    # If no agent specified, prompt with list
    if not agent_name:
        agents = get_all_agents_status()
        console_print("\n[bold]Available agents:[/bold]")
        for i, (key, info) in enumerate(agents.items(), 1):
            installed = "✓" if info["installed"] else "✗"
            console_print(f"  {i}. {info['name']} ({key}) - {installed}")

        agent_name = Prompt.ask("\nEnter agent name")

    # Validate agent name
    agent_name = agent_name.lower()
    if agent_name not in AGENT_METADATA:
        valid_agents = ", ".join(AGENT_METADATA.keys())
        if output_json:
            json_output_func(
                success=False,
                error={
                    "code": "INVALID_AGENT",
                    "message": f"Invalid agent: {agent_name}",
                    "valid_agents": list(AGENT_METADATA.keys()),
                }
            )
        else:
            console.print(f"[red]✗[/red] Invalid agent: {agent_name}")
            console.print(f"[dim]Valid agents: {valid_agents}[/dim]")
        return

    # Check if agent is installed
    detection = detect_agent_installation(agent_name)
    if not detection["installed"]:
        metadata = AGENT_METADATA[agent_name]
        if output_json:
            json_output_func(
                success=False,
                error={
                    "code": "AGENT_NOT_INSTALLED",
                    "message": f"Agent '{metadata['name']}' is not installed",
                    "install_url": metadata["install_url"],
                    "cli_command": metadata["cli_command"],
                }
            )
        else:
            console.print(f"[red]✗[/red] Agent '{metadata['name']}' is not installed")
            console.print(f"[dim]Install from: {metadata['install_url']}[/dim]")
        return

    # Check additional requirements
    if detection["additional_requirements"]:
        if output_json:
            json_output_func(
                success=False,
                error={
                    "code": "MISSING_REQUIREMENTS",
                    "message": "Additional requirements missing",
                    "missing": detection["additional_requirements"],
                }
            )
        else:
            console.print(f"[red]✗[/red] Missing requirements:")
            for req in detection["additional_requirements"]:
                console.print(f"  - {req}")
        return

    # Update config
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        if output_json:
            json_output_func(
                success=False,
                error={
                    "code": "NO_CONFIG",
                    "message": "No configuration found. Run 'daf init' first.",
                }
            )
        else:
            console.print("[red]✗[/red] No configuration found")
            console.print("[dim]Run 'daf init' to create configuration[/dim]")
        return

    # Set agent backend
    config.agent_backend = agent_name
    config_loader.save_config(config)

    if output_json:
        json_output_func(
            success=True,
            data={
                "agent": agent_name,
                "agent_name": AGENT_METADATA[agent_name]["name"],
            }
        )
    else:
        console.print(f"[green]✓[/green] Default agent set to: {AGENT_METADATA[agent_name]['name']}")


def test_agent(agent_name: Optional[str] = None, output_json: bool = False) -> None:
    """Test if an agent is available and working.

    Args:
        agent_name: Agent to test (e.g., "claude", "ollama")
        output_json: If True, output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func, console_print
    from rich.prompt import Prompt

    # If no agent specified, use default from config
    if not agent_name:
        config_loader = ConfigLoader()
        try:
            config = config_loader.load_config()
            agent_name = config.agent_backend if config else "claude"
        except Exception:
            agent_name = "claude"

        console_print(f"[dim]Testing default agent: {agent_name}[/dim]\n")

    # Validate agent name
    agent_name = agent_name.lower()
    if agent_name not in AGENT_METADATA:
        if output_json:
            json_output_func(
                success=False,
                error={
                    "code": "INVALID_AGENT",
                    "message": f"Invalid agent: {agent_name}",
                }
            )
        else:
            console.print(f"[red]✗[/red] Invalid agent: {agent_name}")
        return

    metadata = AGENT_METADATA[agent_name]
    detection = detect_agent_installation(agent_name)

    # Test results
    results = {
        "agent": agent_name,
        "agent_name": metadata["name"],
        "installed": detection["installed"],
        "cli_path": detection["cli_path"],
        "version": detection["version"],
        "tests": {
            "cli_available": detection["installed"],
            "requirements_met": len(detection["additional_requirements"]) == 0,
        },
    }

    if output_json:
        json_output_func(success=True, data=results)
        return

    # Display test results
    console.print(f"[bold]Testing {metadata['name']}[/bold]\n")

    # CLI availability
    if results["tests"]["cli_available"]:
        console.print(f"[green]✓[/green] CLI available: {detection['cli_path']}")
        if detection["version"]:
            console.print(f"[dim]  Version: {detection['version']}[/dim]")
    else:
        console.print(f"[red]✗[/red] CLI not found: {metadata['cli_command']}")
        console.print(f"[dim]  Install from: {metadata['install_url']}[/dim]")

    # Additional requirements
    if results["tests"]["requirements_met"]:
        console.print("[green]✓[/green] All requirements met")
    else:
        console.print("[red]✗[/red] Missing requirements:")
        for req in detection["additional_requirements"]:
            console.print(f"  - {req}")

    # Overall status
    console.print()
    if all(results["tests"].values()):
        console.print(f"[green]✓[/green] {metadata['name']} is ready to use")
    else:
        console.print(f"[red]✗[/red] {metadata['name']} is not ready")


def show_agent_info(agent_name: Optional[str] = None, output_json: bool = False) -> None:
    """Show detailed information about an agent.

    Args:
        agent_name: Agent to show info for (e.g., "claude", "ollama")
        output_json: If True, output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func, console_print
    from rich.prompt import Prompt

    # If no agent specified, use default from config
    if not agent_name:
        config_loader = ConfigLoader()
        try:
            config = config_loader.load_config()
            agent_name = config.agent_backend if config else "claude"
        except Exception:
            agent_name = "claude"

        console_print(f"[dim]Showing default agent: {agent_name}[/dim]\n")

    # Validate agent name
    agent_name = agent_name.lower()
    if agent_name not in AGENT_METADATA:
        if output_json:
            json_output_func(
                success=False,
                error={
                    "code": "INVALID_AGENT",
                    "message": f"Invalid agent: {agent_name}",
                }
            )
        else:
            console.print(f"[red]✗[/red] Invalid agent: {agent_name}")
        return

    metadata = AGENT_METADATA[agent_name]
    detection = detect_agent_installation(agent_name)

    info = {
        "agent": agent_name,
        "name": metadata["name"],
        "description": metadata["description"],
        "status": metadata["status"],
        "cli_command": metadata["cli_command"],
        "install_url": metadata["install_url"],
        "installed": detection["installed"],
        "cli_path": detection["cli_path"],
        "version": detection["version"],
        "features": metadata["features"],
        "notes": metadata.get("notes"),
        "additional_requirements": detection["additional_requirements"],
    }

    if output_json:
        json_output_func(success=True, data=info)
        return

    # Display information
    console.print(f"[bold]{metadata['name']}[/bold]")
    console.print(f"{metadata['description']}\n")

    # Status
    status_badge = {
        "fully-tested": "[green]Stable[/green]",
        "experimental": "[yellow]Experimental[/yellow]",
    }.get(metadata["status"], "[dim]Unknown[/dim]")
    console.print(f"Status: {status_badge}")

    # Installation
    if detection["installed"]:
        console.print(f"[green]✓[/green] Installed: {detection['cli_path']}")
        if detection["version"]:
            console.print(f"[dim]  Version: {detection['version']}[/dim]")
    else:
        console.print(f"[red]✗[/red] Not installed")
        console.print(f"[dim]  CLI command: {metadata['cli_command']}[/dim]")

    console.print(f"\n[bold]Installation:[/bold]")
    console.print(f"  {metadata['install_url']}")

    # Features
    console.print(f"\n[bold]Supported Features:[/bold]")
    for feature, supported in metadata["features"].items():
        mark = "✓" if supported else "✗"
        style = "green" if supported else "red"
        feature_name = feature.replace("_", " ").title()
        console.print(f"  [{style}]{mark}[/{style}] {feature_name}")

    # Additional requirements
    if detection["additional_requirements"]:
        console.print(f"\n[bold]Additional Requirements:[/bold]")
        for req in detection["additional_requirements"]:
            console.print(f"  [red]✗[/red] {req}")

    # Notes
    if metadata.get("notes"):
        console.print(f"\n[bold]Notes:[/bold]")
        console.print(f"  {metadata['notes']}")
