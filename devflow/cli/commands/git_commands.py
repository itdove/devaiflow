"""Git-based issue tracker CLI command group for DevAIFlow.

This module provides issue tracker integration commands for git-based platforms
(GitHub Issues, GitLab Issues).
"""

import click


@click.group()
def git():
    """Git-based issue tracker commands (GitHub/GitLab).

    Commands for managing GitHub Issues and GitLab Issues workflows in DevAIFlow.
    Automatically detects the platform from your repository.

    Requirements:
    - GitHub: GitHub CLI (gh) installed and authenticated
    - GitLab: GitLab CLI (glab) installed and authenticated
    """
    pass
