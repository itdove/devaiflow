"""Migration utilities for DAF_AGENTS.md to daf-workflow skill transition.

NOTE: DAF_AGENTS.md was deprecated in v0.2.0 and replaced by the daf-workflow skill.
This module helps users migrate by offering to delete old DAF_AGENTS.md files.

The daf-workflow skill provides all workflow guidance and is automatically loaded
by Claude Code, eliminating the need for DAF_AGENTS.md files.
"""

import importlib.resources
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Confirm

if TYPE_CHECKING:
    from devflow.config.loader import ConfigLoader
    from devflow.config.models import Session

console = Console()


def _install_bundled_cs_agents(destination: Path) -> tuple[bool, list[str]]:
    """Install bundled DAF_AGENTS.md to specified location.

    Tries multiple methods to find and copy the bundled DAF_AGENTS.md:
    1. importlib.resources (Python 3.9+)
    2. Relative path from package (development mode)

    Args:
        destination: Path where DAF_AGENTS.md should be installed

    Returns:
        Tuple of (success: bool, diagnostics: list of error messages)
    """
    diagnostics = []

    # Method 1: Try importlib.resources (works for installed package)
    method1_path = None
    try:
        if hasattr(importlib.resources, 'files'):
            daf_agents_resource = importlib.resources.files('devflow').parent / 'DAF_AGENTS.md'
            method1_path = str(daf_agents_resource)
            if daf_agents_resource is not None:
                with daf_agents_resource.open('rb') as src:
                    destination.write_bytes(src.read())
                return True, []
    except ImportError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): ImportError - {str(e)}")
    except AttributeError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): AttributeError - {str(e)}")
    except TypeError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): TypeError - {str(e)}")
    except FileNotFoundError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): FileNotFoundError - DAF_AGENTS.md not found")
        if method1_path:
            diagnostics.append(f"    Searched path: {method1_path}")
    except Exception as e:
        diagnostics.append(f"  Method 1 (importlib.resources): {type(e).__name__} - {str(e)}")

    # Method 2: Try relative path from package (development mode)
    try:
        # Navigate from devflow/utils/daf_agents_validation.py to repository root
        package_cs_agents = Path(__file__).parent.parent.parent / "DAF_AGENTS.md"
        diagnostics.append(f"  Method 2 (relative path): Searched: {package_cs_agents}")
        if package_cs_agents.exists():
            shutil.copy2(package_cs_agents, destination)
            return True, []
        else:
            diagnostics.append(f"  Method 2 (relative path): File does not exist")
    except PermissionError as e:
        diagnostics.append(f"  Method 2 (relative path): PermissionError - {str(e)}")
    except Exception as e:
        diagnostics.append(f"  Method 2 (relative path): {type(e).__name__} - {str(e)}")

    return False, diagnostics


def _get_bundled_daf_agents_content() -> tuple[str | None, list[str]]:
    """Read the bundled DAF_AGENTS.md content.

    Returns:
        Tuple of (content: str or None, diagnostics: list of error messages)
    """
    diagnostics = []

    # Method 1: Try importlib.resources (works for installed package)
    try:
        if hasattr(importlib.resources, 'files'):
            daf_agents_resource = importlib.resources.files('devflow').parent / 'DAF_AGENTS.md'
            if daf_agents_resource is not None:
                with daf_agents_resource.open('r', encoding='utf-8') as src:
                    return src.read(), []
    except ImportError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): ImportError - {str(e)}")
    except AttributeError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): AttributeError - {str(e)}")
    except TypeError as e:
        diagnostics.append(f"  Method 1 (importlib.resources): TypeError - {str(e)}")
    except FileNotFoundError:
        diagnostics.append(f"  Method 1 (importlib.resources): FileNotFoundError - DAF_AGENTS.md not found")
    except Exception as e:
        diagnostics.append(f"  Method 1 (importlib.resources): {type(e).__name__} - {str(e)}")

    # Method 2: Try relative path from package (development mode)
    try:
        # Navigate from devflow/utils/daf_agents_validation.py to repository root
        package_cs_agents = Path(__file__).parent.parent.parent / "DAF_AGENTS.md"
        diagnostics.append(f"  Method 2 (relative path): Searched: {package_cs_agents}")
        if package_cs_agents.exists():
            return package_cs_agents.read_text(encoding='utf-8'), []
        else:
            diagnostics.append(f"  Method 2 (relative path): File does not exist")
    except Exception as e:
        diagnostics.append(f"  Method 2 (relative path): {type(e).__name__} - {str(e)}")

    return None, diagnostics


def _check_and_upgrade_daf_agents(installed_file: Path, location: str) -> bool:
    """Check if installed DAF_AGENTS.md is outdated and offer upgrade or deletion.

    If bundled DAF_AGENTS.md no longer exists, offers to delete the installed copy
    (migration to daf-workflow skill). Otherwise, offers to upgrade if outdated.

    Args:
        installed_file: Path to the installed DAF_AGENTS.md
        location: Human-readable location description (e.g., "repository", "workspace")

    Returns:
        True if file is up-to-date, successfully upgraded, or successfully deleted
        False if user declined or operation failed
    """
    # Get bundled content for comparison
    bundled_content, diagnostics = _get_bundled_daf_agents_content()
    if bundled_content is None:
        # Bundled file not found - DAF_AGENTS.md has been removed from package
        # Offer to delete installed copy (migration to daf-workflow skill)
        console.print(f"\n[cyan]ℹ DAF_AGENTS.md has been replaced by daf-workflow skill[/cyan]")
        console.print(f"[dim]Workflow guidance is now in ~/.claude/skills/daf-workflow/ (auto-loaded)[/dim]")
        console.print(f"\n[dim]Found old DAF_AGENTS.md at: {installed_file}[/dim]")

        from devflow.utils import is_mock_mode
        mock_mode = is_mock_mode()

        should_delete = True
        if not mock_mode:
            console.print(f"\n[bold]Delete old DAF_AGENTS.md file?[/bold]")
            console.print(f"[dim]This file is no longer used. Run 'daf upgrade' to install daf-workflow skill.[/dim]")
            from rich.prompt import Confirm
            should_delete = Confirm.ask("Delete old file?", default=True)
        else:
            console.print(f"[dim]Mock mode: Auto-deleting old DAF_AGENTS.md[/dim]")

        if should_delete:
            try:
                installed_file.unlink()
                console.print(f"[green]✓ Deleted old DAF_AGENTS.md from {location}[/green]")
                console.print(f"[dim]  Run 'daf upgrade' to ensure daf-workflow skill is installed[/dim]")
                return True
            except Exception as e:
                console.print(f"[yellow]⚠ Could not delete {installed_file}: {e}[/yellow]")
                console.print(f"[dim]You can manually delete this file - it's no longer needed[/dim]")
                return True  # Don't block session opening
        else:
            console.print(f"[dim]Keeping old file (will prompt again on next session)[/dim]")
            return True

    # Read installed content
    try:
        installed_content = installed_file.read_text(encoding='utf-8')
    except Exception as e:
        console.print(f"[yellow]⚠ Could not read installed DAF_AGENTS.md: {e}[/yellow]")
        return True

    # Compare contents
    if bundled_content == installed_content:
        # Up to date
        return True

    # File is outdated - prompt for upgrade
    console.print(f"\n[yellow]⚠ DAF_AGENTS.md has been updated[/yellow]")
    console.print(f"[dim]The bundled version contains newer documentation and command updates.[/dim]")

    # In mock mode, auto-upgrade without prompting
    from devflow.utils import is_mock_mode
    mock_mode = is_mock_mode()

    should_upgrade = True
    if not mock_mode:
        console.print(f"\n[bold]Upgrade DAF_AGENTS.md to the latest version?[/bold]")
        console.print(f"[dim]This will replace: {installed_file}[/dim]")
        should_upgrade = Confirm.ask("Upgrade to latest version?", default=True)
    else:
        console.print(f"[dim]Mock mode: Auto-upgrading DAF_AGENTS.md at {installed_file}[/dim]")

    if not should_upgrade:
        console.print(f"[dim]Continuing with current version[/dim]")
        return True

    # Perform upgrade
    success, install_diagnostics = _install_bundled_cs_agents(installed_file)
    if success:
        console.print(f"[green]✓ Upgraded DAF_AGENTS.md in {location}[/green]")
        console.print(f"[dim]  Location: {installed_file}[/dim]")
        return True
    else:
        console.print(f"\n[red]✗ Failed to upgrade DAF_AGENTS.md[/red]")
        if install_diagnostics:
            console.print(f"\n[yellow]Debug information:[/yellow]")
            for diag in install_diagnostics:
                console.print(f"[dim]{diag}[/dim]")
        console.print(f"[dim]Continuing with current version[/dim]")
        return True  # Don't block session opening


def validate_daf_agents_md(session: 'Session', config_loader: 'ConfigLoader') -> bool:
    """Validate DAF_AGENTS.md context files and handle migration to daf-workflow skill.

    Checks for DAF_AGENTS.md in this order:
    1. DEVAIFLOW_HOME directory (centralized, recommended)
    2. Repository directory (project-specific customization, backward compatibility)
    3. Workspace directory (shared across projects, backward compatibility)

    If found, checks if it should be deleted (migration to daf-workflow skill).
    If bundled version still exists, offers upgrade if outdated.

    NOTE: DAF_AGENTS.md is being phased out in favor of the daf-workflow skill.
    This function handles the migration by offering to delete old files.

    For ticket_creation and investigation sessions with temp directories:
    - Checks DEVAIFLOW_HOME first, then workspace (temp directory doesn't persist)
    - Does not try to install to temp directory

    Args:
        session: Session object
        config_loader: Config loader to get workspace path

    Returns:
        True (always succeeds - DAF_AGENTS.md is optional, daf-workflow skill is primary)
    """
    # For ticket_creation and investigation sessions with temp directories,
    # check DEVAIFLOW_HOME first, then workspace (temp directory is transient and gets deleted)
    active_conv = session.active_conversation
    is_temp_session = (
        session.session_type in ("ticket_creation", "investigation") and
        active_conv and
        active_conv.temp_directory
    )

    if is_temp_session:
        # Check DEVAIFLOW_HOME first (centralized location)
        from devflow.utils.paths import get_cs_home
        cs_home = get_cs_home()
        daf_agents_home = cs_home / "DAF_AGENTS.md"

        if daf_agents_home.exists():
            console.print(f"[dim]✓ Found DAF_AGENTS.md in DEVAIFLOW_HOME (centralized)[/dim]")
            console.print(f"[dim]  Location: {daf_agents_home}[/dim]")
            # Check if upgrade is needed
            if not _check_and_upgrade_daf_agents(daf_agents_home, "DEVAIFLOW_HOME"):
                return False
            return True

        # Check workspace as fallback for backward compatibility
        config = config_loader.load_config()
        if config and config.repos and config.repos.get_default_workspace_path():
            workspace_path = config.repos.get_default_workspace_path()
            if workspace_path:
                workspace_path = Path(workspace_path).expanduser()
                cs_agents_workspace = workspace_path / "DAF_AGENTS.md"

                if cs_agents_workspace.exists():
                    console.print(f"[dim]✓ Found DAF_AGENTS.md in workspace (shared)[/dim]")
                    console.print(f"[dim]  Location: {cs_agents_workspace}[/dim]")
                    # Check if upgrade is needed
                    if not _check_and_upgrade_daf_agents(cs_agents_workspace, "workspace"):
                        return False
                    return True

        # Not found - DAF_AGENTS.md has been replaced by daf-workflow skill
        console.print(f"\n[dim]ℹ Using daf-workflow skill for workflow guidance[/dim]")
        console.print(f"[dim]  Run 'daf upgrade' to ensure daf-workflow skill is installed[/dim]")
        return True

    # Multi-project session: check DEVAIFLOW_HOME first, then workspace
    # (Claude launches from workspace root for multi-project sessions)
    if active_conv and active_conv.is_multi_project:
        # Check DEVAIFLOW_HOME first (centralized location)
        from devflow.utils.paths import get_cs_home
        cs_home = get_cs_home()
        daf_agents_home = cs_home / "DAF_AGENTS.md"

        if daf_agents_home.exists():
            console.print(f"[dim]✓ Found DAF_AGENTS.md in DEVAIFLOW_HOME (centralized, multi-project)[/dim]")
            console.print(f"[dim]  Location: {daf_agents_home}[/dim]")
            # Check if upgrade is needed
            if not _check_and_upgrade_daf_agents(daf_agents_home, "DEVAIFLOW_HOME"):
                return False
            return True

        # Check workspace as fallback for backward compatibility
        workspace_path_from_session = active_conv.workspace_path
        if workspace_path_from_session:
            workspace_path = Path(workspace_path_from_session).expanduser()
            cs_agents_workspace = workspace_path / "DAF_AGENTS.md"

            if cs_agents_workspace.exists():
                console.print(f"[dim]✓ Found DAF_AGENTS.md in workspace (multi-project)[/dim]")
                console.print(f"[dim]  Location: {cs_agents_workspace}[/dim]")
                # Check if upgrade is needed
                if not _check_and_upgrade_daf_agents(cs_agents_workspace, "workspace"):
                    return False
                return True

            # Not found - DAF_AGENTS.md has been replaced by daf-workflow skill
            console.print(f"\n[dim]ℹ Using daf-workflow skill for workflow guidance (multi-project)[/dim]")
            console.print(f"[dim]  Run 'daf upgrade' to ensure daf-workflow skill is installed[/dim]")
            return True

        # No workspace path in multi-project session
        console.print(f"\n[red]✗ Multi-project session missing workspace_path[/red]")
        return False

    # Normal single-project session: check DEVAIFLOW_HOME first, then repository, then workspace
    project_path = active_conv.project_path if active_conv else None
    if not project_path:
        return False

    # Check DEVAIFLOW_HOME first (centralized location, recommended)
    from devflow.utils.paths import get_cs_home
    cs_home = get_cs_home()
    daf_agents_home = cs_home / "DAF_AGENTS.md"

    if daf_agents_home.exists():
        console.print(f"[dim]✓ Found DAF_AGENTS.md in DEVAIFLOW_HOME (centralized)[/dim]")
        console.print(f"[dim]  Location: {daf_agents_home}[/dim]")
        # Check if upgrade is needed
        if not _check_and_upgrade_daf_agents(daf_agents_home, "DEVAIFLOW_HOME"):
            return False
        return True

    # Check repository directory (project-specific, backward compatibility)
    repo_path = Path(project_path)
    cs_agents_repo = repo_path / "DAF_AGENTS.md"

    if cs_agents_repo.exists():
        console.print(f"[dim]✓ Found DAF_AGENTS.md in repository (project-specific)[/dim]")
        console.print(f"[dim]  Location: {cs_agents_repo}[/dim]")
        # Check if upgrade is needed
        if not _check_and_upgrade_daf_agents(cs_agents_repo, "repository"):
            return False
        return True

    # Check workspace directory as fallback (backward compatibility)
    config = config_loader.load_config()
    if config and config.repos and config.repos.get_default_workspace_path():
        workspace_path = config.repos.get_default_workspace_path()

        if not workspace_path:
            console.print("[yellow]⚠[/yellow] No default workspace configured")
            return None

        workspace_path = Path(workspace_path).expanduser()
        cs_agents_workspace = workspace_path / "DAF_AGENTS.md"

        if cs_agents_workspace.exists():
            console.print(f"[dim]✓ Found DAF_AGENTS.md in workspace (shared)[/dim]")
            console.print(f"[dim]  Location: {cs_agents_workspace}[/dim]")
            # Check if upgrade is needed
            if not _check_and_upgrade_daf_agents(cs_agents_workspace, "workspace"):
                return False
            return True

    # Not found - DAF_AGENTS.md has been replaced by daf-workflow skill
    console.print(f"\n[dim]ℹ Using daf-workflow skill for workflow guidance[/dim]")
    console.print(f"[dim]  Run 'daf upgrade' to ensure daf-workflow skill is installed[/dim]")
    return True
