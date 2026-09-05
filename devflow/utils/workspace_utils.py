"""Utilities for workspace management and auto-upgrade."""

from pathlib import Path
from typing import Any, Optional, Tuple
from rich.console import Console

console = Console()


def ensure_workspace_skills_and_commands(
    workspace_path: str,
    quiet: bool = True,
    config: Any = None,
) -> Tuple[bool, Optional[str]]:
    """Ensure bundled skills are up-to-date for configured AI agents.

    The configured agent homes are detected automatically. When no agent is
    configured or installed, Claude is used as the backwards-compatible fallback.
    The configured ``AgentConfig.install_level`` controls whether installation is
    global, project-level, or both.

    ``workspace_path`` remains required because it is used to validate the
    workspace and for project-level installations.

    Args:
        workspace_path: Path to workspace directory (for validation and
            project-level installations)
        quiet: If True, suppress console output (default: True for auto-operations)
        config: Optional loaded DevAIFlow configuration. If omitted, the current
            configuration is loaded when available.

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
        - (True, None) if skills are up-to-date or were successfully installed
        - (False, error_message) if installation failed

    Example:
        >>> success, error = ensure_workspace_skills_and_commands("/path/to/workspace")
        >>> if not success:
        ...     console.print(f"[red]✗[/red] {error}")
    """
    workspace = Path(workspace_path).expanduser().resolve()

    # Check if workspace exists
    if not workspace.exists():
        return False, f"Workspace directory does not exist: {workspace_path}"

    try:
        if config is None:
            from devflow.config.loader import ConfigLoader

            try:
                config_loader = ConfigLoader()
                if config_loader.config_file.exists():
                    config = config_loader.load_config()
            except Exception:
                # A stale or partially written config must not prevent the
                # automatic bundled-skill upgrade from using detected agents.
                config = None

        from devflow.agent.skill_directories import detect_configured_agents
        from devflow.utils.claude_commands import install_skills_to_agents

        agents = detect_configured_agents(config=config)
        agent_config = getattr(config, 'agent', None)
        install_level = getattr(agent_config, 'install_level', 'global') or 'global'
        if install_level not in ('global', 'project', 'both'):
            install_level = 'global'

        project_path = workspace if install_level in ('project', 'both') else None
        results = install_skills_to_agents(
            agents=agents,
            level=install_level,
            project_path=project_path,
            skip_confirmation=True,
            dry_run=False,
            quiet=quiet,
        )

        failed_by_agent = {
            agent: failed
            for agent, (_, _, failed) in results.items()
            if failed
        }
        if failed_by_agent:
            failures = [
                f"{agent}: {', '.join(failed)}"
                for agent, failed in failed_by_agent.items()
            ]
            return False, f"Failed to install/upgrade ({'; '.join(failures)})"

        if not quiet:
            changed_count = sum(len(changed) for changed, _, _ in results.values())
            if changed_count:
                locations = ', '.join(agents)
                scope = 'global' if install_level == 'global' else install_level
                console.print(
                    f"[green]✓[/green] Installed/upgraded {changed_count} "
                    f"skills for {locations} ({scope})"
                )

        return True, None

    except Exception as e:
        return False, f"Error installing skills: {e}"
