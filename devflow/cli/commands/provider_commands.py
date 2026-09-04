"""Implementation of 'daf model' commands for managing model provider profiles."""

import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.config.models import ModelProviderProfile

console = Console()


def list_profiles(output_json: bool = False) -> None:
    """List all configured model provider profiles.

    Args:
        output_json: Output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        if output_json:
            json_output_func(success=False, error={"message": "No configuration found. Run 'daf init' first."})
        else:
            console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if output_json:
        # JSON output
        profiles_data = {}
        for name, profile in config.model_provider.profiles.items():
            profiles_data[name] = {
                "name": profile.name,
                "provider": profile.provider,
                "agent_backend": profile.agent_backend,
                "api_url": profile.api_url,
                "base_url": profile.base_url,
                "model_name": profile.model_name,
                "models": profile.models,
                "reasoning_efforts": profile.reasoning_efforts,
                "reasoning_effort": profile.reasoning_effort,
                "utility_reasoning_effort": profile.utility_reasoning_effort,
                "commit_message_model": profile.commit_message_model,
                "pr_template_model": profile.pr_template_model,
                "use_vertex": profile.use_vertex,
                "vertex_project_id": profile.vertex_project_id,
                "vertex_region": profile.vertex_region,
            }

        json_output_func(
            success=True,
            data={
                "default_profile": config.model_provider.default_profile,
                "profiles": profiles_data,
            }
        )
        return

    if not config.model_provider.profiles:
        console.print("\n[yellow]⚠[/yellow] No model provider profiles configured")
        console.print("[dim]Add a profile with: daf model add <name>[/dim]")
        return

    # Keep profile names visible even on narrow terminals where the detailed
    # table is truncated horizontally.
    console.print(f"[dim]Profiles: {', '.join(config.model_provider.profiles)}[/dim]")

    # Create table
    table = Table(title="\nConfigured Model Provider Profiles", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Provider", style="white")
    table.add_column("Agent", style="white")
    table.add_column("API URL", style="white")
    table.add_column("Default model", style="white")
    table.add_column("Command models", style="white")
    table.add_column("Reasoning strength", style="white")
    table.add_column("Default", style="green")

    for name, profile in config.model_provider.profiles.items():
        default_marker = "✓" if config.model_provider.default_profile == name else ""

        # Determine type
        profile_type = profile.provider or ("vertex" if profile.use_vertex else "anthropic")
        profile_type = {
            "vertex": "Vertex AI",
            "anthropic": "Anthropic",
            "openrouter": "OpenRouter",
            "llama.cpp": "llama.cpp",
            "ollama": "Ollama",
            "mlx": "MLX",
            "codex": "Codex",
        }.get(profile_type, profile_type)
        agent_backend = profile.agent_backend or {
            "codex": "codex",
            "openai": "codex",
            "ollama": "ollama",
        }.get(profile_type, "claude")
        command_models = ", ".join(
            f"{key}={value}" for key, value in profile.models.items() if value
        ) or "-"
        reasoning_efforts = ", ".join(
            f"{key}={value}" for key, value in profile.reasoning_efforts.items() if value
        ) or "-"

        table.add_row(
            name,
            profile_type,
            agent_backend,
            profile.api_url or "-",
            profile.model_name or "-",
            command_models,
            reasoning_efforts,
            default_marker
        )

    console.print(table)
    console.print()


@require_outside_claude
def add_profile(name: Optional[str] = None, interactive: bool = True, output_json: bool = False) -> None:
    """Add a new model provider profile.

    Args:
        name: Profile name
        interactive: Use interactive wizard
        output_json: Output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        if output_json:
            json_output_func(success=False, error={"message": "No configuration found. Run 'daf init' first."})
        else:
            console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    # Prompt for name if not provided
    if not name and interactive:
        console.print("\n[bold]Add Model Provider Profile[/bold]")
        console.print("[dim]Enter a unique name for this profile[/dim]\n")
        console.print("[dim]Examples:[/dim]")
        console.print("[dim]  vertex        - Google Vertex AI[/dim]")
        console.print("[dim]  llama-cpp     - Local llama.cpp server[/dim]")
        console.print("[dim]  openrouter    - OpenRouter API[/dim]")
        console.print("[dim]  codex         - OpenAI models for Codex[/dim]")
        console.print()
        name = Prompt.ask("Profile name")

    if not name or not name.strip():
        if output_json:
            json_output_func(success=False, error={"message": "Profile name cannot be empty"})
        else:
            console.print("[yellow]⚠[/yellow] Profile name cannot be empty")
        return

    name = name.strip()

    # Check if profile already exists
    if name in config.model_provider.profiles:
        if output_json:
            json_output_func(success=False, error={"message": f"Profile already exists: {name}"})
        else:
            console.print(f"[yellow]⚠[/yellow] Profile already exists: {name}")
        return

    # Interactive wizard
    if interactive:
        console.print(f"\n[bold]Configuring profile: {name}[/bold]\n")

        # Ask for provider type
        console.print("[cyan]Select provider type:[/cyan]")
        console.print("  1. Anthropic Claude (default)")
        console.print("  2. Google Vertex AI")
        console.print("  3. Local llama.cpp server")
        console.print("  4. Custom (OpenRouter, etc.)")
        console.print("  5. OpenAI / Codex")
        console.print()

        provider_type = Prompt.ask("Provider type", choices=["1", "2", "3", "4", "5"], default="1")

        # Initialize profile fields
        base_url = None
        auth_token = None
        api_key = None
        model_name = None
        use_vertex = False
        vertex_project_id = None
        vertex_region = None
        env_vars = {}
        provider = "anthropic"

        if provider_type == "1":
            # Anthropic Claude (default)
            console.print("\n[dim]Using default Anthropic configuration[/dim]")
            model_name = Prompt.ask("Model name (optional, e.g., 'claude-3-opus-20240229')", default="")
            if not model_name:
                model_name = None

        elif provider_type == "2":
            # Google Vertex AI
            provider = "vertex"
            use_vertex = True
            console.print("\n[yellow]Configuring Google Vertex AI[/yellow]")
            vertex_project_id = Prompt.ask("GCP Project ID")
            vertex_region = Prompt.ask("Vertex AI Region", default="us-east5")
            model_name = Prompt.ask("Model name (optional)", default="")
            if not model_name:
                model_name = None

        elif provider_type == "3":
            # Local llama.cpp
            provider = "llama.cpp"
            console.print("\n[yellow]Configuring local llama.cpp server[/yellow]")
            base_url = Prompt.ask("API URL", default="http://localhost:8000")
            auth_token = "llama-cpp"  # Special token for llama.cpp
            api_key = ""  # Empty string to disable API key
            model_name = Prompt.ask("Model name (e.g., 'devstral-small-2')", default="")
            if not model_name:
                model_name = None

        elif provider_type == "4":
            # Custom
            provider = "custom"
            console.print("\n[yellow]Configuring custom provider[/yellow]")
            base_url = Prompt.ask("Base URL (e.g., 'https://openrouter.ai/api/v1')")
            auth_token = Prompt.ask("Auth token (optional)", default="")
            if not auth_token:
                auth_token = None
            api_key = Prompt.ask("API key (optional, press Enter to use default)", default="")
            if not api_key:
                api_key = None
            model_name = Prompt.ask("Model name (optional)", default="")
            if not model_name:
                model_name = None

        elif provider_type == "5":
            provider = "codex"
            console.print("\n[yellow]Configuring OpenAI / Codex[/yellow]")
            api_key = Prompt.ask("OpenAI API key (optional)", default="")
            if not api_key:
                api_key = None
            model_name = Prompt.ask("Model name (optional)", default="")
            if not model_name:
                model_name = None

        # Ask if this should be the default profile
        set_default = False
        if not config.model_provider.profiles:  # First profile
            set_default = Confirm.ask("\nSet as default profile?", default=True)
        else:
            set_default = Confirm.ask("\nSet as default profile?", default=False)

        # Create profile
        profile = ModelProviderProfile(
            name=name,
            provider=provider,
            base_url=base_url,
            auth_token=auth_token,
            api_key=api_key,
            model_name=model_name,
            use_vertex=use_vertex,
            vertex_project_id=vertex_project_id,
            vertex_region=vertex_region,
            env_vars=env_vars,
        )

        # Add to config
        config.model_provider.profiles[name] = profile

        # Set as default if requested
        if set_default:
            config.model_provider.default_profile = name

        # Save config
        config_loader.save_config(config)

        if output_json:
            json_output_func(
                success=True,
                message=f"Added profile: {name}",
                data={"name": name, "default": set_default}
            )
        else:
            console.print(f"\n[green]✓[/green] Added profile: {name}")
            if base_url:
                console.print(f"[dim]Base URL: {base_url}[/dim]")
            if model_name:
                console.print(f"[dim]Model: {model_name}[/dim]")
            if set_default:
                console.print(f"[dim]Default: Yes[/dim]")
    else:
        # Non-interactive mode (for testing or scripting)
        if output_json:
            json_output_func(success=False, error={"message": "Non-interactive mode not yet implemented"})
        else:
            console.print("[yellow]⚠[/yellow] Non-interactive mode requires all parameters")


@require_outside_claude
def remove_profile(name: Optional[str] = None, output_json: bool = False) -> None:
    """Remove a model provider profile.

    Args:
        name: Profile name to remove
        output_json: Output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        if output_json:
            json_output_func(success=False, error={"message": "No configuration found. Run 'daf init' first."})
        else:
            console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.model_provider.profiles:
        if output_json:
            json_output_func(success=False, error={"message": "No profiles configured to remove"})
        else:
            console.print("[yellow]⚠[/yellow] No profiles configured to remove")
        return

    # If name not provided, show list and prompt for selection
    if not name:
        console.print("\n[bold]Remove Model Provider Profile[/bold]\n")

        # Show configured profiles
        console.print("[cyan]Configured profiles:[/cyan]")
        profile_list = list(config.model_provider.profiles.keys())
        for i, profile_name in enumerate(profile_list, 1):
            default_marker = " [default]" if config.model_provider.default_profile == profile_name else ""
            console.print(f"  {i}. {profile_name}{default_marker}")

        console.print()
        choice = Prompt.ask(
            "Enter number or name to remove (or 'cancel' to exit)",
            default="cancel"
        )

        if choice.lower() == "cancel":
            console.print("[dim]Cancelled[/dim]")
            return

        # Check if choice is a number
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(profile_list):
                name = profile_list[index]
            else:
                console.print(f"[red]✗[/red] Invalid selection. Choose 1-{len(profile_list)}")
                return
        else:
            name = choice.strip()

    # Find profile
    if name not in config.model_provider.profiles:
        if output_json:
            json_output_func(success=False, error={"message": f"Profile not found: {name}"})
        else:
            console.print(f"[red]✗[/red] Profile not found: {name}")
        return

    # Confirm removal
    if not output_json:
        console.print(f"\n[yellow]Remove profile '{name}'?[/yellow]")
        if not Confirm.ask("Continue?", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

    # Remove profile
    was_default = (config.model_provider.default_profile == name)
    del config.model_provider.profiles[name]

    # If removed profile was default, set first remaining as default or "anthropic"
    if was_default:
        if config.model_provider.profiles:
            config.model_provider.default_profile = list(config.model_provider.profiles.keys())[0]
            if not output_json:
                console.print(f"[dim]Set '{config.model_provider.default_profile}' as new default[/dim]")
        else:
            config.model_provider.default_profile = "anthropic"
            if not output_json:
                console.print(f"[dim]Reset default to 'anthropic'[/dim]")

    # Save config
    config_loader.save_config(config)

    if output_json:
        json_output_func(success=True, message=f"Removed profile: {name}")
    else:
        console.print(f"\n[green]✓[/green] Removed profile: {name}")


@require_outside_claude
def set_default_profile(name: Optional[str] = None, output_json: bool = False) -> None:
    """Set a profile as the default.

    Args:
        name: Profile name to set as default
        output_json: Output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        if output_json:
            json_output_func(success=False, error={"message": "No configuration found. Run 'daf init' first."})
        else:
            console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.model_provider.profiles:
        if output_json:
            json_output_func(success=False, error={"message": "No profiles configured"})
        else:
            console.print("[yellow]⚠[/yellow] No profiles configured")
            console.print("[dim]Add a profile with: daf model add <name>[/dim]")
        return

    # If name not provided, show list and prompt for selection
    if not name:
        console.print("\n[bold]Set Default Model Provider Profile[/bold]\n")

        # Show configured profiles
        console.print("[cyan]Configured profiles:[/cyan]")
        profile_list = list(config.model_provider.profiles.keys())
        for i, profile_name in enumerate(profile_list, 1):
            default_marker = " [current default]" if config.model_provider.default_profile == profile_name else ""
            console.print(f"  {i}. {profile_name}{default_marker}")

        console.print()
        choice = Prompt.ask(
            "Enter number or name to set as default (or 'cancel' to exit)",
            default="cancel"
        )

        if choice.lower() == "cancel":
            console.print("[dim]Cancelled[/dim]")
            return

        # Check if choice is a number
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(profile_list):
                name = profile_list[index]
            else:
                console.print(f"[red]✗[/red] Invalid selection. Choose 1-{len(profile_list)}")
                return
        else:
            name = choice.strip()

    # Find profile
    if name not in config.model_provider.profiles:
        if output_json:
            json_output_func(success=False, error={"message": f"Profile not found: {name}"})
        else:
            console.print(f"[red]✗[/red] Profile not found: {name}")
        return

    # Already default?
    if config.model_provider.default_profile == name:
        if output_json:
            json_output_func(success=True, message=f"Profile '{name}' is already the default")
        else:
            console.print(f"[yellow]⚠[/yellow] Profile '{name}' is already the default")
        return

    # Set as default
    config.model_provider.default_profile = name

    # Save config
    config_loader.save_config(config)

    if output_json:
        json_output_func(success=True, message=f"Set '{name}' as default profile")
    else:
        console.print(f"\n[green]✓[/green] Set '{name}' as default profile")


def show_profile(name: Optional[str] = None, output_json: bool = False) -> None:
    """Show configuration for a specific profile.

    Args:
        name: Profile name to show
        output_json: Output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        if output_json:
            json_output_func(success=False, error={"message": "No configuration found. Run 'daf init' first."})
        else:
            console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.model_provider.profiles:
        if output_json:
            json_output_func(success=False, error={"message": "No profiles configured"})
        else:
            console.print("[yellow]⚠[/yellow] No profiles configured")
        return

    # If name not provided, show default profile
    if not name:
        name = config.model_provider.default_profile

    # Find profile
    if name not in config.model_provider.profiles:
        if output_json:
            json_output_func(success=False, error={"message": f"Profile not found: {name}"})
        else:
            console.print(f"[red]✗[/red] Profile not found: {name}")
        return

    profile = config.model_provider.profiles[name]

    if output_json:
        json_output_func(
            success=True,
            data={
                "name": profile.name,
                "provider": profile.provider,
                "agent_backend": profile.agent_backend,
                "api_url": profile.api_url,
                "base_url": profile.base_url,
                "auth_token": profile.auth_token if profile.auth_token else None,
                "api_key": "***" if profile.api_key else None,
                "model_name": profile.model_name,
                "models": profile.models,
                "reasoning_efforts": profile.reasoning_efforts,
                "reasoning_effort": profile.reasoning_effort,
                "utility_reasoning_effort": profile.utility_reasoning_effort,
                "commit_message_model": profile.commit_message_model,
                "pr_template_model": profile.pr_template_model,
                "use_vertex": profile.use_vertex,
                "vertex_project_id": profile.vertex_project_id,
                "vertex_region": profile.vertex_region,
                "env_vars": profile.env_vars,
                "is_default": config.model_provider.default_profile == name,
            }
        )
        return

    # Display profile configuration
    console.print(f"\n[bold cyan]Profile: {name}[/bold cyan]")
    if config.model_provider.default_profile == name:
        console.print("[green]✓ Default profile[/green]")
    console.print()

    # Determine type
    provider = profile.provider or ("vertex" if profile.use_vertex else "anthropic")
    provider = {
        "vertex": "Vertex AI",
        "anthropic": "Anthropic",
        "openrouter": "OpenRouter",
        "llama.cpp": "llama.cpp",
        "ollama": "Ollama",
        "mlx": "MLX",
        "codex": "Codex",
    }.get(provider, provider)
    console.print(f"[yellow]Provider:[/yellow] {provider}")
    console.print(f"[yellow]Agent adapter:[/yellow] {profile.agent_backend or ('codex' if provider in {'codex', 'openai'} else 'ollama' if provider == 'ollama' else 'claude')}")

    console.print()
    console.print("[bold]Configuration:[/bold]")

    if profile.api_url:
        console.print(f"  API URL: {profile.api_url}")
    if profile.auth_token:
        console.print(f"  Auth Token: {profile.auth_token}")
    if profile.api_key is not None:
        console.print(f"  API Key: {'(empty)' if profile.api_key == '' else '***'}")
    if profile.model_name:
        console.print(f"  Model Name: {profile.model_name}")
    if profile.models:
        console.print("  Command Models:")
        for command, model in profile.models.items():
            console.print(f"    {command}: {model}")
    if profile.reasoning_efforts:
        console.print("  Reasoning Strengths:")
        for command, strength in profile.reasoning_efforts.items():
            console.print(f"    {command}: {strength}")
    if profile.use_vertex:
        console.print(f"  Vertex Project ID: {profile.vertex_project_id}")
        console.print(f"  Vertex Region: {profile.vertex_region}")
    if profile.env_vars:
        console.print(f"  Additional Environment Variables:")
        for key, value in profile.env_vars.items():
            console.print(f"    {key}={value}")

    console.print()


def test_profile(name: Optional[str] = None, output_json: bool = False) -> None:
    """Test connectivity and validate a profile.

    Args:
        name: Profile name to test
        output_json: Output in JSON format
    """
    from devflow.cli.utils import output_json as json_output_func

    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if not config:
        if output_json:
            json_output_func(success=False, error={"message": "No configuration found. Run 'daf init' first."})
        else:
            console.print("[red]✗[/red] No configuration found. Run [cyan]daf init[/cyan] first.")
        return

    if not config.model_provider.profiles:
        if output_json:
            json_output_func(success=False, error={"message": "No profiles configured"})
        else:
            console.print("[yellow]⚠[/yellow] No profiles configured")
        return

    # If name not provided, test default profile
    if not name:
        name = config.model_provider.default_profile

    # Find profile
    if name not in config.model_provider.profiles:
        if output_json:
            json_output_func(success=False, error={"message": f"Profile not found: {name}"})
        else:
            console.print(f"[red]✗[/red] Profile not found: {name}")
        return

    profile = config.model_provider.profiles[name]

    if not output_json:
        console.print(f"\n[bold]Testing profile: {name}[/bold]\n")

    # Validation checks
    issues = []
    warnings = []

    # Check Vertex AI configuration
    if profile.use_vertex:
        if not profile.vertex_project_id:
            issues.append("Vertex AI enabled but vertex_project_id not set")
        if not profile.vertex_region:
            warnings.append("Vertex AI enabled but vertex_region not set (will use default)")

    # Check custom base URL
    if profile.base_url:
        if not profile.base_url.startswith(("http://", "https://")):
            issues.append(f"Invalid base_url format: {profile.base_url}")

    # Report results
    if output_json:
        json_output_func(
            success=len(issues) == 0,
            data={
                "profile": name,
                "valid": len(issues) == 0,
                "issues": issues,
                "warnings": warnings,
            }
        )
    else:
        if issues:
            console.print("[red]✗ Validation failed[/red]\n")
            console.print("[bold]Issues:[/bold]")
            for issue in issues:
                console.print(f"  [red]•[/red] {issue}")
        else:
            console.print("[green]✓ Profile configuration is valid[/green]\n")

        if warnings:
            console.print("\n[bold]Warnings:[/bold]")
            for warning in warnings:
                console.print(f"  [yellow]•[/yellow] {warning}")

        if not issues:
            console.print("\n[dim]Note: This command validates configuration only.[/dim]")
            console.print("[dim]To test actual connectivity, use the profile with your AI agent.[/dim]")

        console.print()
