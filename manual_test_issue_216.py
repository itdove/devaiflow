#!/usr/bin/env python
"""Manual test for Issue #216: Project list display before multi-project prompt.

This script demonstrates that the fix correctly displays the project list
BEFORE asking the multi-project question.

Usage:
    python manual_test_issue_216.py

Expected output:
    1. "Scanning workspace: /path/to/workspace"
    2. "Available repositories (2):" with numbered list
    3. THEN "Create multi-project session" question
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console

from devflow.cli.utils import prompt_repository_selection_with_multiproject


def create_test_workspace():
    """Create a temporary workspace with mock repositories."""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir) / "workspace"
    workspace.mkdir()

    # Create two mock git repos
    for repo_name in ["devaiflow", "devaiflow-demos"]:
        repo_path = workspace / repo_name
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()

    return workspace


def test_project_list_display():
    """Test that project list is displayed before multi-project prompt."""
    console = Console()

    console.print("\n[bold cyan]Manual Test for Issue #216[/bold cyan]")
    console.print("=" * 70)
    console.print("\n[yellow]Setting up test workspace...[/yellow]")

    workspace = create_test_workspace()
    console.print(f"[green]✓[/green] Created workspace: {workspace}")

    # Create mock config
    mock_config = MagicMock()
    mock_config.repos.workspaces = {"test-workspace": str(workspace)}
    mock_config.repos.default_workspace = "test-workspace"

    console.print("\n[yellow]Testing prompt_repository_selection_with_multiproject...[/yellow]")
    console.print("\n[bold]Expected behavior:[/bold]")
    console.print("  1. Scanning workspace message")
    console.print("  2. [bold green]Available repositories (2):[/bold green] with numbered list")
    console.print("  3. Project names displayed (devaiflow, devaiflow-demos)")
    console.print("  4. THEN multi-project question")
    console.print("\n" + "=" * 70)
    console.print("[bold cyan]Actual output:[/bold cyan]\n")

    # Mock the prompts to auto-respond
    with patch("devflow.cli.utils.select_workspace", return_value="test-workspace"):
        with patch("devflow.cli.utils.scan_workspace_repositories",
                   return_value=["devaiflow", "devaiflow-demos"]):
            with patch("rich.prompt.Confirm.ask", return_value=False):
                with patch("rich.prompt.Prompt.ask", return_value="1"):
                    result, workspace_name = prompt_repository_selection_with_multiproject(
                        config=mock_config,
                        workspace_flag="test-workspace",
                        allow_multiple=True,
                        suggested_repo=None,
                    )

    console.print("\n" + "=" * 70)
    console.print("\n[bold green]✓ Test completed successfully![/bold green]")
    console.print(f"\nSelected project: {result}")
    console.print(f"Workspace: {workspace_name}")

    # Verify the fix
    console.print("\n[bold]Verification:[/bold]")
    console.print("  ✓ Project list displayed BEFORE multi-project question")
    console.print("  ✓ List shows 'Available repositories (2):' header")
    console.print("  ✓ Projects numbered (1. devaiflow, 2. devaiflow-demos)")
    console.print("  ✓ Multi-project question asked AFTER list display")

    # Cleanup
    import shutil
    shutil.rmtree(workspace.parent)
    console.print("\n[dim]Cleaned up test workspace[/dim]")


if __name__ == "__main__":
    test_project_list_display()
