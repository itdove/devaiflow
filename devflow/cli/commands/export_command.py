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

    # Check if sessions belong to features and handle handoff (experimental)
    if not all_sessions and issue_keys:
        _check_and_handle_feature_handoff(issue_keys, config_loader, session_manager)

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
    # Check if this is a multi-project session (new architecture)
    active_conv = session.active_conversation
    if active_conv and active_conv.is_multi_project and active_conv.projects:
        console.print(f"\n[bold cyan]Syncing {len(active_conv.projects)} project(s) for {session.name}[/bold cyan]")
        for proj_name, proj_info in active_conv.projects.items():
            if proj_info.project_path and proj_info.branch:
                console.print(f"\n[cyan]→ {proj_name} (branch: {proj_info.branch})[/cyan]")
                _sync_single_conversation_branch(
                    project_path=Path(proj_info.project_path),
                    branch=proj_info.branch,
                    session_name=session.name,
                    issue_key=session.issue_key,
                    working_dir_name=proj_name,
                    conversation=active_conv,  # Pass conversation to update remote_url
                )
    # Multi-conversation support (old architecture - backward compatibility)
    elif session.conversations:
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
        success, error_msg = GitUtils.checkout_branch(working_dir, branch)
        if not success:
            error_detail = f": {error_msg}" if error_msg else ""
            raise ValueError(f"Cannot checkout branch '{branch}' in {working_dir_name or project_path.name}{error_detail}")
        console.print(f"[green]✓[/green] Checked out {branch}")

    # Step 2: Fetch + pull latest changes
    console.print(f"[cyan]Fetching latest from origin...[/cyan]")
    GitUtils.fetch_origin(working_dir)  # Non-critical if fails - ignore return value

    if GitUtils.is_branch_pushed(working_dir, branch):
        console.print(f"[cyan]Pulling latest changes...[/cyan]")
        success, error_msg = GitUtils.pull_current_branch(working_dir)
        if not success:
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
        success, error_msg = GitUtils.commit_all(working_dir, commit_message)
        if not success:
            error_detail = f"\n{error_msg}" if error_msg else ""
            raise ValueError(
                f"Failed to commit changes in {working_dir_name or branch}\n"
                f"Cannot export without committing all changes.{error_detail}"
            )
        console.print(f"[green]✓[/green] Committed all changes")

    # Step 4: Push branch to remote (REQUIRED)
    if not GitUtils.is_branch_pushed(working_dir, branch):
        console.print(f"[cyan]Branch '{branch}' is not on remote[/cyan]")
        console.print(f"[cyan]Pushing {branch} to origin...[/cyan]")
        success, error_msg = GitUtils.push_branch(working_dir, branch)
        if not success:
            error_detail = f"\nError: {error_msg}" if error_msg else ""
            raise ValueError(
                f"Failed to push branch '{branch}' to remote\n"
                f"Teammate needs branch on remote to import session.\n"
                f"Common causes: No remote configured, no push permissions, network issues{error_detail}"
            )
        console.print(f"[green]✓[/green] Pushed branch to origin")
    else:
        console.print(f"[cyan]Pushing latest commits to remote...[/cyan]")
        success, error_msg = GitUtils.push_branch(working_dir, branch)
        if not success:
            error_detail = f"\nError: {error_msg}" if error_msg else ""
            raise ValueError(
                f"Failed to push to remote '{branch}'\n"
                f"Teammate may not have latest changes.{error_detail}\n"
                f"Check network and remote permissions."
            )
        console.print(f"[green]✓[/green] Branch synced with remote")

    # Step 5: Capture remote URL (for fork support)
    if conversation:
        remote_url = GitUtils.get_branch_remote_url(working_dir, branch)
        if remote_url:
            conversation.remote_url = remote_url
            console.print(f"[dim]Captured remote URL: {remote_url}[/dim]")


def _check_and_handle_feature_handoff(
    issue_keys: List[str],
    config_loader: ConfigLoader,
    session_manager: SessionManager,
) -> None:
    """Check if exported sessions belong to features and handle work handoff.

    For team collaboration: When you export an incomplete session that's part
    of your feature, this offers to mark it as external (handing off to teammate).

    Args:
        issue_keys: List of session identifiers being exported
        config_loader: ConfigLoader instance
        session_manager: SessionManager instance
    """
    try:
        from rich.prompt import Confirm
        from devflow.orchestration.feature import FeatureManager

        feature_manager = FeatureManager(
            config_loader=config_loader,
            session_manager=session_manager,
        )

        # Get all features
        features = feature_manager.list_features()
        if not features:
            return

        # Check each exported session against features
        for identifier in issue_keys:
            # Get session(s) for this identifier
            sessions = session_manager.index.get_sessions(identifier)
            if not sessions:
                continue

            session = sessions[0]  # Use first matching session
            issue_key = session.issue_key

            for feature in features:
                # Check if this issue_key is in feature.sessions (not external)
                if issue_key not in feature.sessions:
                    continue

                # Found a match!
                # Determine actual session status
                feature_status = feature.session_statuses.get(issue_key, "pending")
                actual_status = session.status  # Get from session object

                console.print(f"\n[dim]Session {issue_key} is part of feature '{feature.name}'[/dim]")
                console.print(f"[dim]Session status: {actual_status}, Feature status: {feature_status}[/dim]")

                # Check issue tracker for real status
                is_completed = False
                try:
                    from devflow.utils.backend_detection import detect_backend_from_key
                    from devflow.issue_tracker.factory import create_issue_tracker_client

                    config = config_loader.load_config()
                    backend = detect_backend_from_key(issue_key, config)
                    issue_tracker_client = create_issue_tracker_client(backend=backend)

                    ticket = issue_tracker_client.get_ticket(issue_key)
                    if ticket:
                        issue_status = ticket.get('status', '').lower()
                        console.print(f"[dim]Issue tracker status: {issue_status}[/dim]")

                        # Check if done/closed
                        if issue_status in ['done', 'closed', 'resolved', 'merged']:
                            is_completed = True
                        elif actual_status in ["completed", "merged"]:
                            is_completed = True
                except Exception:
                    # Issue tracker check is optional
                    if actual_status in ["completed", "merged"] or feature_status == "completed":
                        is_completed = True

                # Only offer handoff for incomplete sessions
                if is_completed:
                    console.print(f"[dim]Exporting completed work (no handoff needed)[/dim]")
                    continue

                # Incomplete session - offer to hand off
                console.print(f"\n[bold yellow]⚠ Feature Handoff Detected[/bold yellow]")
                console.print(f"Feature: [cyan]{feature.name}[/cyan]")
                console.print(f"Session: [cyan]{issue_key}[/cyan]")
                console.print(f"Status: [yellow]{actual_status}[/yellow] (incomplete)\n")

                console.print("[dim]You're exporting incomplete work. Options:[/dim]")
                console.print("  1. Mark as external (handing off to teammate)")
                console.print("     → Removes from your sessions")
                console.print("     → Tracks as external dependency")
                console.print("     → Dependent sessions may be blocked")
                console.print("  2. Keep in your sessions (you'll continue working on it)")
                console.print("     → Share for review/collaboration only")
                console.print()

                if not Confirm.ask(f"Hand off {issue_key} to teammate (mark as external)?", default=False):
                    console.print("[dim]Keeping in your sessions[/dim]")
                    continue

                # Get assignee for external session (prompt user)
                from rich.prompt import Prompt
                assignee = Prompt.ask("Teammate's name/username", default="teammate")

                # Get blocking relationships from metadata
                blocking_relationships = {}
                if hasattr(feature, 'metadata') and feature.metadata:
                    blocking_relationships = feature.metadata.get('blocking_relationships', {})

                blocks = blocking_relationships.get(issue_key, {}).get('blocks', [])
                blocked_by = blocking_relationships.get(issue_key, {}).get('blocked_by', [])

                # Get actual status from issue tracker
                external_status = "In Progress"  # Default
                try:
                    from devflow.utils.backend_detection import detect_backend_from_key
                    from devflow.issue_tracker.factory import create_issue_tracker_client

                    config = config_loader.load_config()
                    backend = detect_backend_from_key(issue_key, config)
                    issue_tracker_client = create_issue_tracker_client(backend=backend)

                    ticket = issue_tracker_client.get_ticket(issue_key)
                    if ticket:
                        external_status = ticket.get('status', 'In Progress')
                        console.print(f"[dim]Using issue tracker status: {external_status}[/dim]")
                except Exception:
                    # Use default if issue tracker check fails
                    console.print(f"[dim]Using default status: {external_status}[/dim]")

                # Create external session entry
                external_session = {
                    'key': issue_key,
                    'assignee': assignee,
                    'status': external_status,
                    'summary': session.goal,
                    'blocks': blocks,
                    'blocked_by': blocked_by,
                }

                # Add to external_sessions
                feature.external_sessions.append(external_session)

                # Remove from sessions
                feature.sessions.remove(issue_key)
                del feature.session_statuses[issue_key]

                # Remove from blocking_relationships metadata
                if hasattr(feature, 'metadata') and feature.metadata:
                    if 'blocking_relationships' in feature.metadata:
                        feature.metadata['blocking_relationships'].pop(issue_key, None)

                # Update feature
                feature_manager.update_feature(feature)

                console.print(f"[green]✓[/green] Moved {issue_key} to external sessions")
                console.print(f"[green]✓[/green] Assigned to: {assignee}")
                console.print(f"[green]✓[/green] Updated feature '{feature.name}'")

                # Check if this blocks any of your sessions
                blocking_sessions = []
                for session_key in feature.sessions:
                    blocking_rels = blocking_relationships.get(session_key, {})
                    if issue_key in blocking_rels.get('blocked_by', []):
                        blocking_sessions.append(session_key)

                if blocking_sessions:
                    console.print(f"\n[yellow]Note:[/yellow] These sessions are now blocked until {assignee} completes {issue_key}:")
                    for session_key in blocking_sessions:
                        console.print(f"  • {session_key}")

    except ImportError:
        # Feature orchestration not available (experimental)
        pass
    except Exception as e:
        # Don't fail export if feature handoff fails
        console.print(f"[yellow]Warning:[/yellow] Could not handle feature handoff: {e}")
