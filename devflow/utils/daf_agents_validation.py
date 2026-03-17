"""Utility functions for validating DAF_AGENTS.md context files."""

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
    """Check if installed DAF_AGENTS.md is outdated and offer upgrade.

    Args:
        installed_file: Path to the installed DAF_AGENTS.md
        location: Human-readable location description (e.g., "repository", "workspace")

    Returns:
        True if file is up-to-date or successfully upgraded, False if user declined or upgrade failed
    """
    # Get bundled content for comparison
    bundled_content, diagnostics = _get_bundled_daf_agents_content()
    if bundled_content is None:
        # Can't check version if we can't read bundled file
        # Continue anyway - don't block session opening
        if diagnostics:
            console.print(f"[yellow]⚠ Could not check for DAF_AGENTS.md updates[/yellow]")
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
    """Validate that required context files exist before launching Claude.

    Checks for DAF_AGENTS.md in this order:
    1. DEVAIFLOW_HOME directory (centralized, recommended)
    2. Repository directory (project-specific customization, backward compatibility)
    3. Workspace directory (shared across projects, backward compatibility)
    4. Offer to auto-install bundled DAF_AGENTS.md if not found

    If found, checks if installed version is outdated and prompts for upgrade.

    For ticket_creation and investigation sessions with temp directories:
    - Checks DEVAIFLOW_HOME first, then workspace (temp directory doesn't persist)
    - Does not try to install to temp directory

    Args:
        session: Session object
        config_loader: Config loader to get workspace path

    Returns:
        True if DAF_AGENTS.md is found or successfully installed, False otherwise
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

        # Not found - offer to install to DEVAIFLOW_HOME (recommended location)
        console.print(f"\n[yellow]⚠ DAF_AGENTS.md not found[/yellow]")
        console.print(f"\n[dim]DAF_AGENTS.md provides daf tool usage instructions to Claude.[/dim]")
        console.print(f"\nSearched locations:")
        console.print(f"  1. DEVAIFLOW_HOME: {daf_agents_home}")
        if config and config.repos and config.repos.get_default_workspace_path():
            console.print(f"  2. Workspace:      {cs_agents_workspace}")
        console.print(f"\n[dim]Note: Cannot install to temporary directory (session_type: {session.session_type})[/dim]")

        from devflow.utils import is_mock_mode
        mock_mode = is_mock_mode()

        should_install = True
        if not mock_mode:
            console.print(f"\n[bold]Install DAF_AGENTS.md to DEVAIFLOW_HOME?[/bold]")
            console.print(f"[dim]This will copy the bundled DAF_AGENTS.md to: {daf_agents_home}[/dim]")
            console.print(f"[dim]Recommended: Centralized location for all projects[/dim]")
            should_install = Confirm.ask("Install DAF_AGENTS.md to DEVAIFLOW_HOME?", default=True)
        else:
            console.print(f"[dim]Mock mode: Auto-installing DAF_AGENTS.md to {daf_agents_home}[/dim]")

        if not should_install:
            console.print(f"\n[yellow]Cannot continue without DAF_AGENTS.md[/yellow]")
            console.print(f"\n[bold]Manual installation:[/bold]")
            console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {cs_home}/")
            console.print(f"\nSee: https://github.com/itdove/devaiflow/blob/main/docs/02-installation.md")
            return False

        # Install bundled DAF_AGENTS.md to DEVAIFLOW_HOME
        success, diagnostics = _install_bundled_cs_agents(daf_agents_home)
        if success:
            console.print(f"[green]✓ Installed DAF_AGENTS.md to DEVAIFLOW_HOME[/green]")
            console.print(f"[dim]  Location: {daf_agents_home}[/dim]")
            return True
        else:
            console.print(f"\n[red]✗ Failed to install DAF_AGENTS.md[/red]")
            if diagnostics:
                console.print(f"\n[yellow]Debug information:[/yellow]")
                for diag in diagnostics:
                    console.print(f"[dim]{diag}[/dim]")
            console.print(f"\n[bold]Manual installation:[/bold]")
            console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {cs_home}/")
            console.print(f"\nSee: https://github.com/itdove/devaiflow/blob/main/docs/02-installation.md")
            return False

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

            # Not found - offer to install to DEVAIFLOW_HOME (recommended location)
            console.print(f"\n[yellow]⚠ DAF_AGENTS.md not found[/yellow]")
            console.print(f"\n[dim]DAF_AGENTS.md provides daf tool usage instructions to Claude.[/dim]")
            console.print(f"\nSearched locations:")
            console.print(f"  1. DEVAIFLOW_HOME: {daf_agents_home}")
            console.print(f"  2. Workspace:      {cs_agents_workspace}")
            console.print(f"\n[dim]Note: Multi-project sessions use DEVAIFLOW_HOME for centralized management[/dim]")

            from devflow.utils import is_mock_mode
            mock_mode = is_mock_mode()

            should_install = True
            if not mock_mode:
                console.print(f"\n[bold]Install DAF_AGENTS.md to DEVAIFLOW_HOME?[/bold]")
                console.print(f"[dim]This will copy the bundled DAF_AGENTS.md to: {daf_agents_home}[/dim]")
                console.print(f"[dim]Recommended: Centralized location for all projects[/dim]")
                should_install = Confirm.ask("Install DAF_AGENTS.md to DEVAIFLOW_HOME?", default=True)
            else:
                console.print(f"[dim]Mock mode: Auto-installing DAF_AGENTS.md to {daf_agents_home}[/dim]")

            if not should_install:
                console.print(f"\n[yellow]Cannot continue without DAF_AGENTS.md[/yellow]")
                console.print(f"\n[bold]Manual installation:[/bold]")
                console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {cs_home}/")
                console.print(f"\nSee: https://github.com/itdove/devaiflow/blob/main/docs/02-installation.md")
                return False

            # Install bundled DAF_AGENTS.md to DEVAIFLOW_HOME
            success, diagnostics = _install_bundled_cs_agents(daf_agents_home)
            if success:
                console.print(f"[green]✓ Installed DAF_AGENTS.md to DEVAIFLOW_HOME[/green]")
                console.print(f"[dim]  Location: {daf_agents_home}[/dim]")
                return True
            else:
                console.print(f"\n[red]✗ Failed to install DAF_AGENTS.md[/red]")
                if diagnostics:
                    console.print(f"\n[yellow]Debug information:[/yellow]")
                    for diag in diagnostics:
                        console.print(f"[dim]{diag}[/dim]")
                console.print(f"\n[bold]Manual installation:[/bold]")
                console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {cs_home}/")
                console.print(f"\nSee: https://github.com/itdove/devaiflow/blob/main/docs/02-installation.md")
                return False

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

    # Not found - offer to install bundled DAF_AGENTS.md to DEVAIFLOW_HOME (recommended)
    console.print(f"\n[yellow]⚠ DAF_AGENTS.md not found[/yellow]")
    console.print(f"\n[dim]DAF_AGENTS.md provides daf tool usage instructions to Claude.[/dim]")
    console.print(f"\nSearched locations:")
    console.print(f"  1. DEVAIFLOW_HOME: {daf_agents_home}")
    console.print(f"  2. Repository:     {cs_agents_repo}")
    if config and config.repos and config.repos.get_default_workspace_path():
        console.print(f"  3. Workspace:      {cs_agents_workspace}")

    # Offer to install bundled DAF_AGENTS.md
    # In mock mode, auto-install without prompting
    from devflow.utils import is_mock_mode
    mock_mode = is_mock_mode()

    should_install = True
    if not mock_mode:
        console.print(f"\n[bold]Install DAF_AGENTS.md to DEVAIFLOW_HOME?[/bold]")
        console.print(f"[dim]This will copy the bundled DAF_AGENTS.md to: {daf_agents_home}[/dim]")
        console.print(f"[dim]Recommended: Centralized location for all projects[/dim]")
        should_install = Confirm.ask("Install DAF_AGENTS.md to DEVAIFLOW_HOME?", default=True)
    else:
        console.print(f"[dim]Mock mode: Auto-installing DAF_AGENTS.md to {daf_agents_home}[/dim]")

    if not should_install:
        console.print(f"\n[yellow]Cannot continue without DAF_AGENTS.md[/yellow]")
        console.print(f"\n[bold]Manual installation options:[/bold]")
        console.print(f"\n  Option 1: Copy to DEVAIFLOW_HOME (recommended, centralized)")
        console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {cs_home}/")
        console.print(f"\n  Option 2: Copy to repository (project-specific)")
        console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {repo_path}/")
        console.print(f"\n  Option 3: Copy to workspace (shared across all projects)")
        if config and config.repos and config.repos.get_default_workspace_path():
            console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {workspace_path}/")
        console.print(f"\nSee: https://github.com/itdove/devaiflow/blob/main/docs/02-installation.md")
        return False

    # Install bundled DAF_AGENTS.md to DEVAIFLOW_HOME
    success, diagnostics = _install_bundled_cs_agents(daf_agents_home)
    if success:
        console.print(f"[green]✓ Installed DAF_AGENTS.md to DEVAIFLOW_HOME[/green]")
        console.print(f"[dim]  Location: {daf_agents_home}[/dim]")
        console.print(f"\n[dim]You can customize DAF_AGENTS.md for your organization's needs.[/dim]")
        console.print(f"[dim]See: docs/02-installation.md#customizing-for-your-organization[/dim]")
        return True
    else:
        console.print(f"\n[red]✗ Failed to install DAF_AGENTS.md[/red]")

        if diagnostics:
            console.print(f"\n[yellow]Debug information:[/yellow]")
            for diag in diagnostics:
                console.print(f"[dim]{diag}[/dim]")

        console.print(f"\n[yellow]This may indicate:[/yellow]")
        console.print(f"  • DAF_AGENTS.md is not included in the package distribution (check setup.py)")
        console.print(f"  • Package was installed incorrectly")
        console.print(f"  • File permissions issue")

        console.print(f"\n[bold]Manual installation options:[/bold]")
        console.print(f"\n  Option 1: Copy to DEVAIFLOW_HOME (recommended, centralized)")
        console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {cs_home}/")
        console.print(f"\n  Option 2: Copy to repository (project-specific)")
        console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {repo_path}/")
        console.print(f"\n  Option 3: Copy to workspace (shared across all projects)")
        if config and config.repos and config.repos.get_default_workspace_path():
            console.print(f"    cp /path/to/devaiflow/DAF_AGENTS.md {workspace_path}/")
        console.print(f"\nSee: https://github.com/itdove/devaiflow/blob/main/docs/02-installation.md")
        return False
