"""Utility for loading hierarchical context files from DEVAIFLOW_HOME."""

from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from devflow.config.models import Config


def load_hierarchical_context_files(config: Optional['Config'] = None) -> list[tuple[str, str]]:
    """Load context files from hierarchical configuration.

    Returns list of (path, description) tuples for context files that EXIST.

    Checks for context files from:
    - Backend: backends/JIRA.md
    - Enterprise: ENTERPRISE.md
    - Organization: ORGANIZATION.md
    - Team: TEAM.md
    - User: USER.md

    Only returns files that physically exist on disk.
    Paths are resolved relative to DEVAIFLOW_HOME.

    Args:
        config: Configuration object (may be None, not used currently but kept for future use)

    Returns:
        List of (absolute_path, description) tuples for existing files only
    """
    from devflow.utils.paths import get_cs_home

    context_files = []
    cs_home = get_cs_home()

    # Backend context (JIRA backend specific)
    backend_path = cs_home / "backends" / "JIRA.md"
    if backend_path.exists() and backend_path.is_file():
        # Use absolute path so Claude can read it with Read tool
        context_files.append((str(backend_path), "JIRA backend integration rules"))

    # Enterprise context
    enterprise_path = cs_home / "ENTERPRISE.md"
    if enterprise_path.exists() and enterprise_path.is_file():
        context_files.append((str(enterprise_path), "enterprise-wide policies and standards"))

    # Organization context
    org_path = cs_home / "ORGANIZATION.md"
    if org_path.exists() and org_path.is_file():
        context_files.append((str(org_path), "organization coding standards"))

    # Team context
    team_path = cs_home / "TEAM.md"
    if team_path.exists() and team_path.is_file():
        context_files.append((str(team_path), "team conventions and workflows"))

    # User context
    user_path = cs_home / "USER.md"
    if user_path.exists() and user_path.is_file():
        context_files.append((str(user_path), "personal notes and preferences"))

    return context_files
