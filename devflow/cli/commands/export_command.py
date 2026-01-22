"""Implementation of 'daf export' command."""

from pathlib import Path
from typing import List, Optional

from rich.console import Console

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.export.manager import ExportManager
from devflow.git.utils import GitUtils
from devflow.session.manager import SessionManager

console = Console()


@require_outside_claude
def export_sessions(
    issue_keys: Optional[List[str]] = None,
    all_sessions: bool = False,
    output: Optional[str] = None,
) -> None:
    """Export one or more sessions for team handoff.

    Always includes ALL conversations (all projects) and conversation history.
    Each session represents one issue tracker ticket's complete work.

    Args:
        issue_keys: List of session identifiers (names or JIRA keys) to export
        all_sessions: Export all sessions
        output: Output file path
    """
    if not issue_keys and not all_sessions:
        console.print("[red]✗[/red] Must specify session identifiers or --all flag")
        return

    config_loader = ConfigLoader()
    export_manager = ExportManager(config_loader)
    session_manager = SessionManager(config_loader)

    # Determine which sessions to export
    identifiers_to_export = None if all_sessions else issue_keys

    # Show what will be exported
    if all_sessions:
        console.print("[cyan]Exporting all sessions[/cyan]")
    else:
        console.print(f"[cyan]Exporting sessions: {', '.join(issue_keys)}[/cyan]")

    console.print("[dim]Including ALL conversations and conversation history[/dim]")

    # Sync git branches before export
    # Now syncs ALL conversations in multi-conversation sessions
    # Captures remote URLs for fork support
    if not all_sessions and issue_keys:
        for identifier in issue_keys:
            sessions = session_manager.index.get_sessions(identifier)
            if sessions:
                for session in sessions:
                    _sync_all_branches_for_export(session)
                    # Save session to persist remote URLs
                    session_manager.update_session(session)

    output_path = Path(output) if output else None

    try:
        export_file = export_manager.export_sessions(
            identifiers=identifiers_to_export,
            output_path=output_path,
        )

        console.print(f"[green]✓[/green] Export created successfully")
        console.print(f"Location: {export_file}")

        # Show export size
        size_mb = export_file.stat().st_size / (1024 * 1024)
        console.print(f"Size: {size_mb:.2f} MB")

    except ValueError as e:
        console.print(f"[red]✗[/red] Export failed: {e}")
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        raise


def _sync_all_branches_for_export(session) -> None:
    """Sync all conversation branches before export for team handoff.

    For multi-conversation sessions, syncs all branches across all conversations.
    For legacy single-conversation sessions, syncs the single branch.
    Captures remote URL for fork support.

    Args:
        session: Session object
    """
    # Multi-conversation support
    if session.conversations:
        console.print(f"\n[bold cyan]Syncing {len(session.conversations)} conversation(s) for {session.name}[/bold cyan]")
        for working_dir, conversation in session.conversations.items():
            # Access active_session
            active = conversation.active_session
            if active.project_path and active.branch:
                console.print(f"\n[cyan]→ {working_dir} (branch: {active.branch})[/cyan]")
                _sync_single_conversation_branch(
                    project_path=Path(active.project_path),
                    branch=active.branch,
                    session_name=session.name,
                    issue_key=session.issue_key,
                    working_dir_name=working_dir,
                    conversation=active,  # Pass active session to update remote_url
                )
    # Legacy single-conversation support (fallback for sessions without working_directory)
    elif session.active_conversation:
        active_conv = session.active_conversation
        if active_conv.project_path and active_conv.branch:
            console.print(f"\n[cyan]Syncing branch for {session.name}[/cyan]")
            _sync_single_conversation_branch(
                project_path=Path(active_conv.project_path),
                branch=active_conv.branch,
                session_name=session.name,
                issue_key=session.issue_key,
            )


def _sync_single_conversation_branch(
    project_path: Path,
    branch: str,
    session_name: str,
    issue_key: Optional[str] = None,
    working_dir_name: Optional[str] = None,
    conversation = None,
) -> None:
    """Sync a single conversation's branch before export.

    NEW BEHAVIOR:
    1. Checkout session branch (ensure we're on correct branch)
    2. Fetch + pull latest from remote (ensure we have teammate's changes)
    3. Commit all uncommitted changes (REQUIRED, no prompt)
    4. Push branch to remote (REQUIRED, no prompt)
    5. Capture remote URL for fork support

    Fails export if any critical step fails.

    Args:
        project_path: Path to project directory
        branch: Git branch name
        session_name: Session name
        issue_key: Optional issue key
        working_dir_name: Optional working directory name (for multi-conversation sessions)
        conversation: Optional ConversationContext to update with remote URL

    Raises:
        ValueError: If checkout, commit, or push fails
    """
    working_dir = project_path

    # Check if this is a git repository
    if not GitUtils.is_git_repository(working_dir):
        console.print(f"[dim]Not a git repository - skipping branch sync[/dim]")
        return

    # Step 1: Checkout session branch
    current_branch = GitUtils.get_current_branch(working_dir)
    if current_branch != branch:
        console.print(f"[cyan]Checking out branch {branch}...[/cyan]")
        if not GitUtils.checkout_branch(working_dir, branch):
            raise ValueError(f"Cannot checkout branch '{branch}' in {working_dir_name or project_path.name}")
        console.print(f"[green]✓[/green] Checked out {branch}")

    # Step 2: Fetch + pull latest changes
    console.print(f"[cyan]Fetching latest from origin...[/cyan]")
    GitUtils.fetch_origin(working_dir)  # Non-critical if fails

    if GitUtils.is_branch_pushed(working_dir, branch):
        console.print(f"[cyan]Pulling latest changes...[/cyan]")
        if not GitUtils.pull_current_branch(working_dir):
            if GitUtils.has_merge_conflicts(working_dir):
                conflicted = GitUtils.get_conflicted_files(working_dir)
                raise ValueError(
                    f"Merge conflicts in {working_dir_name or branch}:\n"
                    f"  {', '.join(conflicted)}\n"
                    f"Resolve conflicts and try export again."
                )
            # Non-conflict pull failure - warn but continue
            console.print(f"[yellow]⚠[/yellow] Could not pull latest changes")
        else:
            console.print(f"[green]✓[/green] Branch up to date with remote")

    # Step 3: Check and commit uncommitted changes (REQUIRED)
    if GitUtils.has_uncommitted_changes(working_dir):
        console.print(f"[yellow]⚠[/yellow] Uncommitted changes detected:")
        status_summary = GitUtils.get_status_summary(working_dir)
        if status_summary:
            for line in status_summary.split('\n')[:5]:
                console.print(f"  {line}")
            line_count = len(status_summary.split('\n'))
            if line_count > 5:
                console.print(f"  [dim]... and {line_count - 5} more files[/dim]")

        console.print(f"[cyan]Committing all changes for export...[/cyan]")

        # Generate WIP commit message
        identifier = issue_key if issue_key else session_name
        dir_label = f" ({working_dir_name})" if working_dir_name else ""
        commit_message = f"""WIP: Export for {identifier}{dir_label}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

        # Commit all changes (REQUIRED)
        if not GitUtils.commit_all(working_dir, commit_message):
            raise ValueError(
                f"Failed to commit changes in {working_dir_name or branch}\n"
                f"Cannot export without committing all changes."
            )
        console.print(f"[green]✓[/green] Committed all changes")

    # Step 4: Push branch to remote (REQUIRED)
    if not GitUtils.is_branch_pushed(working_dir, branch):
        console.print(f"[cyan]Branch '{branch}' is not on remote[/cyan]")
        console.print(f"[cyan]Pushing {branch} to origin...[/cyan]")
        if not GitUtils.push_branch(working_dir, branch):
            raise ValueError(
                f"Failed to push branch '{branch}' to remote\n"
                f"Teammate needs branch on remote to import session.\n"
                f"Common causes: No remote configured, no push permissions, network issues"
            )
        console.print(f"[green]✓[/green] Pushed branch to origin")
    else:
        console.print(f"[cyan]Pushing latest commits to remote...[/cyan]")
        if not GitUtils.push_branch(working_dir, branch):
            raise ValueError(
                f"Failed to push to remote '{branch}'\n"
                f"Teammate may not have latest changes.\n"
                f"Check network and remote permissions."
            )
        console.print(f"[green]✓[/green] Branch synced with remote")

    # Step 5: Capture remote URL (for fork support)
    if conversation:
        remote_url = GitUtils.get_branch_remote_url(working_dir, branch)
        if remote_url:
            conversation.remote_url = remote_url
            console.print(f"[dim]Captured remote URL: {remote_url}[/dim]")
