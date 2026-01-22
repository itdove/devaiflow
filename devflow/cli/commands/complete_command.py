"""Implementation of 'daf complete' command."""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
import urllib.request

from rich.console import Console
from rich.prompt import Confirm, Prompt

from devflow.cli.utils import add_jira_comment, get_session_with_prompt, get_status_display, require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.exceptions import ToolNotFoundError
from devflow.export.manager import ExportManager
from devflow.git.pr_template import fill_pr_template_with_ai
from devflow.git.utils import GitUtils
from devflow.jira import transition_on_complete
from devflow.jira.client import JiraClient
from devflow.jira.exceptions import JiraError, JiraAuthError, JiraApiError, JiraNotFoundError, JiraValidationError, JiraConnectionError
from devflow.jira.utils import merge_pr_urls
from devflow.session.manager import SessionManager
from devflow.utils.dependencies import require_tool

console = Console()


@require_outside_claude
def complete_session(
    identifier: Optional[str] = None,
    status: Optional[str] = None,
    attach_to_issue: bool = False,
    latest: bool = False,
    no_commit: bool = False,
    no_pr: bool = False,
    no_issue_update: bool = False
) -> None:
    """Mark a session as complete.

    Args:
        identifier: Session group name or issue tracker key (required if latest=False)
        status: Target JIRA status (Phase 2)
        attach_to_issue: Export session group and attach to issue tracker ticket
        latest: If True, complete the most recently active session
        no_commit: If True, skip git commit prompt
        no_pr: If True, skip PR/MR creation prompt
        no_issue_update: If True, skip JIRA update prompt
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Handle --latest flag
    if latest:
        # Get all sessions sorted by last_active (most recent first)
        all_sessions = session_manager.index.list_sessions()

        if not all_sessions:
            console.print("[yellow]⚠[/yellow] No sessions found")
            console.print("[dim]Use 'daf new' to create a session[/dim]")
            return

        # Get the most recently active session (first in the list)
        session = all_sessions[0]

        # Show session details and confirm
        issue_display = f" ({session.issue_key})" if session.issue_key else ""
        status_text, status_color = get_status_display(session.status)
        console.print(f"\n[bold]Completing most recently active session:[/bold]")
        console.print(f"  Session: {session.name}{issue_display}")
        console.print(f"  Working directory: {session.working_directory}")
        console.print(f"  Status: [{status_color}]{status_text}[/{status_color}]")
        if session.goal:
            console.print(f"  Goal: {session.goal}")
        console.print(f"  Last active: {session.last_active.strftime('%Y-%m-%d %H:%M:%S')}")

        if not Confirm.ask("\nContinue?", default=True):
            console.print("[dim]Cancelled[/dim]")
            return
    else:
        # Require identifier if --latest not specified
        if not identifier:
            console.print("[red]✗[/red] Error: IDENTIFIER is required when --latest is not specified")
            console.print("[dim]Usage: daf complete <identifier> or daf complete --latest[/dim]")
            return

        # Get session using common utility (handles multi-session selection)
        session = get_session_with_prompt(session_manager, identifier)
        if not session:
            return

    # End current work session (use session.name if we got it via --latest)
    session_identifier = session.name if latest else identifier
    session_manager.end_work_session(session_identifier)

    # Load config for prompt settings
    config = config_loader.load_config()

    # Get active conversation for accessing conversation-specific fields
    active_conv = session.active_conversation

    # IMPORTANT: Verify we're on the correct branch BEFORE marking as complete or attempting any commits
    # This prevents committing session changes to the wrong branch
    if active_conv and active_conv.project_path and active_conv.branch:
        working_dir = Path(active_conv.project_path)
        if GitUtils.is_git_repository(working_dir):
            current_git_branch = GitUtils.get_current_branch(working_dir)

            if current_git_branch != active_conv.branch:
                # User is on a different branch than the session branch
                console.print(f"\n[yellow]⚠[/yellow]  Branch mismatch detected:")
                console.print(f"  Session branch: {active_conv.branch}")
                console.print(f"  Current branch: {current_git_branch}")

                # Check if there are uncommitted changes
                if GitUtils.has_uncommitted_changes(working_dir):
                    # Cannot auto-switch because there are uncommitted changes
                    console.print(f"\n[red]✗[/red] Cannot complete session on wrong branch with uncommitted changes")
                    console.print(f"\n[yellow]To resolve this issue:[/yellow]")
                    console.print(f"  1. Commit or stash your changes on '{current_git_branch}'")
                    console.print(f"  2. Checkout the session branch: git checkout {active_conv.branch}")
                    console.print(f"  3. Run 'daf complete {identifier}' again")
                    console.print(f"\n[dim]Or manually switch branches and commit before completing.[/dim]")
                    return
                else:
                    # No uncommitted changes - we can auto-checkout the session branch
                    console.print(f"\n[cyan]Switching to session branch '{active_conv.branch}'...[/cyan]")
                    if GitUtils.checkout_branch(working_dir, active_conv.branch):
                        console.print(f"[green]✓[/green] Checked out branch '{active_conv.branch}'")
                    else:
                        console.print(f"[red]✗[/red] Failed to checkout branch '{active_conv.branch}'")
                        console.print(f"\n[yellow]To resolve this issue:[/yellow]")
                        console.print(f"  1. Manually checkout the session branch: git checkout {active_conv.branch}")
                        console.print(f"  2. Run 'daf complete {identifier}' again")
                        return

    # Branch check passed - now mark session as complete
    session.status = "complete"
    session_manager.update_session(session)

    # Clean up temporary directory if present (for ticket_creation sessions)
    if session.active_conversation and session.active_conversation.temp_directory:
        _cleanup_temp_directory(session.active_conversation.temp_directory)

    issue_display = f" ({session.issue_key})" if session.issue_key else ""
    console.print(f"[green]✓[/green] Session '{session.name}'{issue_display} marked as complete")

    # Show total time
    total_seconds = sum(
        (ws.end - ws.start).total_seconds() for ws in session.work_sessions if ws.end
    )
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    console.print(f"[green]✓[/green] Total time tracked: {hours}h {minutes}m")

    # Track whether commits were made during this completion cycle
    # This is used later to determine if we should prompt for PR/MR creation
    commit_made_this_cycle = False

    # Check for uncommitted changes and prompt to commit
    # Skip for ticket_creation and investigation sessions (analysis-only, no code changes expected)
    if session.session_type == "development" and active_conv and active_conv.project_path:
        working_dir = Path(active_conv.project_path)
        if GitUtils.is_git_repository(working_dir) and GitUtils.has_uncommitted_changes(working_dir):
            console.print("\n[yellow]⚠[/yellow]  You have uncommitted changes:")
            status_summary = GitUtils.get_status_summary(working_dir)
            if status_summary:
                # Indent each line for better display
                for line in status_summary.split('\n'):
                    console.print(f"  {line}")

            # Check if we should commit (or use configured default)
            should_commit = True
            if no_commit:
                should_commit = False
                console.print("\n[dim]Skipping commit (--no-commit flag)[/dim]")
            elif config and config.prompts and config.prompts.auto_commit_on_complete is not None:
                should_commit = config.prompts.auto_commit_on_complete
                if should_commit:
                    console.print("\n[dim]Automatically committing (configured in prompts)[/dim]")
            else:
                should_commit = Confirm.ask("\nCommit these changes now?", default=True)

            if should_commit:
                # Auto-generate commit message from session goal
                auto_message = _generate_commit_message(session)
                console.print(f"\n[dim]Suggested commit message:[/dim]")
                console.print(f"[cyan]{auto_message}[/cyan]")

                # Check if user wants to accept AI commit message automatically
                use_auto = True
                if config and config.prompts and config.prompts.auto_accept_ai_commit_message is not None:
                    use_auto = config.prompts.auto_accept_ai_commit_message
                    if use_auto:
                        console.print("\n[dim]Automatically accepting AI commit message (configured in prompts)[/dim]")
                    else:
                        console.print("\n[dim]Skipping AI commit message (configured in prompts)[/dim]")
                        commit_message_short = Prompt.ask("Commit message", default=auto_message)
                else:
                    # Ask user to confirm
                    use_auto = Confirm.ask("\nUse this commit message?", default=True)

                if use_auto:
                    commit_message_short = auto_message
                else:
                    commit_message_short = Prompt.ask("Commit message", default=auto_message)

                # Create commit with standard format
                full_message = f"""{commit_message_short}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

                if GitUtils.commit_all(working_dir, full_message):
                    console.print("[green]✓[/green] Changes committed")
                    commit_made_this_cycle = True  # Track that we made a commit

                    # Push commits to remote immediately after committing
                    # This ensures commits are backed up even if user declines PR creation
                    if GitUtils.has_unpushed_commits(working_dir, active_conv.branch):
                        # Check if auto_push_to_remote is configured
                        should_push = True
                        if config and config.prompts and config.prompts.auto_push_to_remote is not None:
                            should_push = config.prompts.auto_push_to_remote
                            if should_push:
                                console.print("\n[dim]Automatically pushing to remote (configured in prompts)[/dim]")
                        else:
                            should_push = Confirm.ask(f"\nPush commits to remote?", default=True)

                        if should_push:
                            console.print(f"[dim]Pushing {active_conv.branch} to origin...[/dim]")
                            if GitUtils.push_branch(working_dir, active_conv.branch):
                                console.print(f"[green]✓[/green] Commits pushed to remote")
                            else:
                                console.print(f"[yellow]⚠[/yellow] Failed to push commits to remote")
                                console.print(f"[dim]You can push manually later with: git push origin {active_conv.branch}[/dim]")
                        else:
                            console.print(f"[dim]Skipping push - commits remain local[/dim]")
                    else:
                        console.print(f"[dim]No unpushed commits - branch is up to date with remote[/dim]")
                else:
                    console.print("[yellow]⚠[/yellow] Failed to commit changes")

    # Check if PR/MR already exists for this session
    # Skip for ticket_creation and investigation sessions (analysis-only, no code changes)
    if session.session_type == "development" and active_conv and active_conv.project_path and active_conv.branch:
        working_dir = Path(active_conv.project_path)
        if GitUtils.is_git_repository(working_dir):
            # At this point, we've already verified and corrected the branch above
            # This defensive check should never fail, but we keep it for safety
            current_git_branch = GitUtils.get_current_branch(working_dir)
            if current_git_branch != active_conv.branch:
                # This should not happen since we verified the branch earlier
                console.print(f"\n[yellow]⚠[/yellow] Unexpected branch mismatch - skipping PR creation")
                console.print(f"[dim]Expected: {active_conv.branch}, Current: {current_git_branch}[/dim]")
            else:
                # Check if there are actually file changes to create a PR from
                # We always check for existing PRs (to update JIRA if needed)
                # But only prompt for PR creation if new work was done this cycle
                has_uncommitted = GitUtils.has_uncommitted_changes(working_dir)

                # Check if there's already a PR for the current branch
                pr_status = _get_pr_for_branch(working_dir, active_conv.branch)

                # Determine if we should enter PR creation/update flow
                # Only proceed if: uncommitted changes OR commit made this cycle OR existing PR found
                should_check_pr = has_uncommitted or commit_made_this_cycle or pr_status

                if should_check_pr:

                    if pr_status and pr_status['state'] == 'open':
                        # There's an open PR - offer to push latest commits to update it
                        console.print(f"\n[dim]Existing open PR/MR found for branch '{active_conv.branch}':[/dim]")
                        console.print(f"  {pr_status['url']}")

                        # Check if there are unpushed commits
                        if GitUtils.has_unpushed_commits(working_dir, active_conv.branch):
                            # Offer to push commits to update the PR
                            should_push = True
                            if no_pr:
                                should_push = False
                                console.print("\n[dim]Skipping PR update (--no-pr flag)[/dim]")
                            elif config and config.prompts and config.prompts.auto_push_to_remote is not None:
                                should_push = config.prompts.auto_push_to_remote
                                if should_push:
                                    console.print("\n[dim]Automatically pushing to remote (configured in prompts)[/dim]")
                            else:
                                should_push = Confirm.ask(f"\nPush latest commits to update PR/MR?", default=True)

                            if should_push:
                                console.print(f"[dim]Pushing {active_conv.branch} to origin...[/dim]")
                                if GitUtils.push_branch(working_dir, active_conv.branch):
                                    console.print(f"[green]✓[/green] PR/MR updated with latest commits")
                                else:
                                    console.print(f"[yellow]⚠[/yellow] Failed to push commits")
                        else:
                            console.print(f"[dim]Branch is up to date with remote - no push needed[/dim]")
                        # Update issue tracker ticket with MR URL if not already present
                        if session.issue_key and pr_status['url']:
                            _update_jira_pr_field(session.issue_key, pr_status['url'], no_issue_update)
                    elif pr_status and pr_status['state'] in ['merged', 'closed']:
                        # PR exists but is merged/closed
                        # Only prompt to create new PR if we have new work (commits or uncommitted changes)
                        if has_uncommitted or commit_made_this_cycle:
                            console.print(f"\n[dim]Previous PR/MR for this branch was {pr_status['state']}.[/dim]")
                            should_create_pr = True
                            if no_pr:
                                should_create_pr = False
                                console.print("[dim]Skipping PR creation (--no-pr flag)[/dim]")
                            elif config and config.prompts and config.prompts.auto_create_pr_on_complete is not None:
                                should_create_pr = config.prompts.auto_create_pr_on_complete
                                if should_create_pr:
                                    console.print("[dim]Automatically creating PR (configured in prompts)[/dim]")
                            else:
                                should_create_pr = Confirm.ask("Create a new PR/MR?", default=True)

                            if should_create_pr:
                                pr_url = _create_pr_mr(session, working_dir, session_manager)

                                # Update issue tracker ticket with PR URL if created successfully
                                if pr_url and session.issue_key:
                                    _update_jira_pr_field(session.issue_key, pr_url, no_issue_update)
                        else:
                            console.print(f"\n[dim]Previous PR/MR was {pr_status['state']} and no new commits - skipping PR creation.[/dim]")
                    else:
                        # No existing PR for this branch
                        # Only prompt to create PR if we have new work (commits or uncommitted changes)
                        if has_uncommitted or commit_made_this_cycle:
                            console.print("\n[dim]No PR/MR found for this branch.[/dim]")

                            should_create_pr = True
                            if no_pr:
                                should_create_pr = False
                                console.print("[dim]Skipping PR creation (--no-pr flag)[/dim]")
                            elif config and config.prompts and config.prompts.auto_create_pr_on_complete is not None:
                                should_create_pr = config.prompts.auto_create_pr_on_complete
                                if should_create_pr:
                                    console.print("[dim]Automatically creating PR (configured in prompts)[/dim]")
                            else:
                                should_create_pr = Confirm.ask("Create a PR/MR now?", default=True)

                            if should_create_pr:
                                pr_url = _create_pr_mr(session, working_dir, session_manager)

                                # Update issue tracker ticket with PR URL if created successfully
                                if pr_url and session.issue_key:
                                    _update_jira_pr_field(session.issue_key, pr_url, no_issue_update)
                        else:
                            console.print("\n[dim]No new commits - skipping PR creation.[/dim]")
                else:
                    console.print("\n[dim]No new commits - skipping PR creation.[/dim]")

    # Offer to add session summary to JIRA (only if session has issue key and meaningful activity)
    if session.issue_key:
        # Check if session has meaningful activity to warrant a JIRA comment
        has_meaningful_activity = (
            active_conv and active_conv.ai_agent_session_id and  # Claude was actually used
            (hours > 0 or minutes >= 5) and        # At least 5 minutes of work
            session.working_directory not in ["recent-dir", ".", "", None] and  # Not placeholder
            session.goal not in ["Recent session", "", None]  # Has real goal
        )

        if has_meaningful_activity:
            # Check if we should add JIRA summary (or use configured default)
            should_add_summary = True
            if no_issue_update:
                should_add_summary = False
                console.print("\n[dim]Skipping JIRA update (--no-issue-update flag)[/dim]")
            elif config and config.prompts and config.prompts.auto_add_issue_summary is not None:
                should_add_summary = config.prompts.auto_add_issue_summary
                if should_add_summary:
                    console.print("\n[dim]Automatically adding summary to JIRA (configured in prompts)[/dim]")
            else:
                should_add_summary = Confirm.ask("\nAdd session summary to JIRA?", default=True)

            if should_add_summary:
                _add_session_summary_to_jira(session.issue_key, session.name, session, hours, minutes, config_loader)
        else:
            console.print(f"[dim]Skipping JIRA summary - session has minimal activity (0h {minutes}m, no Claude interaction)[/dim]")
    else:
        console.print(f"[dim]Session has no issue key - skipping JIRA summary[/dim]")

    # Export and attach to JIRA if requested
    if attach_to_issue:
        if session.issue_key:
            _export_and_attach_to_issue(session.issue_key, session.name, config_loader)
        else:
            console.print(f"[yellow]⚠[/yellow] Cannot attach to JIRA - session has no issue key")

    # JIRA auto-transition: In Progress → Code Review/Done/Testing (LAST STEP)
    # This is done last, after all work is complete (commits, PR, summary, export)
    # Skip for ticket_creation and investigation sessions - they only analyze code, don't work on the parent ticket
    if config and session.issue_key and session.session_type == "development":
        transition_on_complete(session, config)
        # Save updated session (JIRA status may have changed)
        session_manager.update_session(session)


def _add_session_summary_to_jira(issue_key: str, session_name: str, session, hours: int, minutes: int, config_loader) -> None:
    """Add session summary to JIRA as a comment.

    Args:
        issue_key: issue tracker key
        session_name: Session group name
        session: Session object
        hours: Total hours worked
        minutes: Total minutes worked
        config_loader: ConfigLoader instance
    """
    # Get active conversation for accessing conversation-specific fields
    active_conv = session.active_conversation

    try:
        from devflow.session.summary import generate_session_summary, generate_prose_summary

        # Generate AI-powered summary (default mode for complete)
        prose_summary = ""
        if active_conv and active_conv.ai_agent_session_id:
            try:
                summary_data = generate_session_summary(session)
                # Use AI mode for completion summaries (best quality)
                # Pass agent_backend for graceful degradation (non-Claude agents use local mode)
                config = config_loader.load_config()
                prose_summary = generate_prose_summary(
                    summary_data,
                    mode="ai",
                    agent_backend=config.agent_backend if config else None
                )
                if prose_summary:
                    # Add newlines before and after for better formatting
                    prose_summary = f"\n\n{prose_summary}\n"
            except Exception as e:
                # If AI summary fails, just continue without it
                console.print(f"[yellow]⚠[/yellow] Could not generate AI summary: {e}")

        # Read notes if they exist
        notes_section = ""
        session_dir = config_loader.get_session_dir(session_name)
        notes_file = session_dir / "notes.md"

        if notes_file.exists():
            with open(notes_file, "r") as f:
                notes_content = f.read()
                # Extract notes for this specific session
                notes_section = f"\n\n*Session Notes:*\n{notes_content}"

        # Build time summary with per-user breakdown
        time_by_user = session.time_by_user()
        if len(time_by_user) > 1:
            # Multiple contributors
            time_breakdown = f"{hours}h {minutes}m total\n"
            for user, user_seconds in sorted(time_by_user.items(), key=lambda x: x[1], reverse=True):
                u_hours = int(user_seconds // 3600)
                u_minutes = int((user_seconds % 3600) // 60)
                time_breakdown += f"  - {user}: {u_hours}h {u_minutes}m\n"
            time_summary = f"*Time Spent:*\n{time_breakdown}"
        else:
            # Single contributor
            time_summary = f"*Time Spent:* {hours}h {minutes}m"

        # Build summary comment
        summary = f"""✅ *Session Complete*

*Project:* {session.working_directory}
*Goal:* {session.goal}
{time_summary}*Branch:* {active_conv.branch if active_conv else 'N/A'}{prose_summary}{notes_section}

_Generated by DevAIFlow_"""

        # Add comment using common utility
        if add_jira_comment(issue_key, summary, silent_success=True):
            console.print(f"[green]✓[/green] Session summary added to JIRA")

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Failed to generate session summary: {e}")


def _sync_branch_for_export(session, issue_key: str, config_loader) -> None:
    """Sync branch before export for team handoff.

    Commits any uncommitted changes and pushes branch to remote.

    Args:
        session: Session object with project_path and branch
        issue_key: issue tracker key for commit message
        config_loader: ConfigLoader instance for accessing configuration
    """
    # Get active conversation for accessing conversation-specific fields
    active_conv = session.active_conversation

    # Skip if no active conversation
    if not active_conv or not active_conv.project_path:
        return

    working_dir = Path(active_conv.project_path)
    config = config_loader.load_config()

    # Check if this is a git repository
    if not GitUtils.is_git_repository(working_dir):
        console.print(f"[dim]Not a git repository - skipping branch sync[/dim]")
        return

    console.print(f"\n[cyan]Preparing branch for team handoff...[/cyan]")

    # Check for uncommitted changes
    if GitUtils.has_uncommitted_changes(working_dir):
        console.print(f"[yellow]⚠[/yellow] You have uncommitted changes:")
        status_summary = GitUtils.get_status_summary(working_dir)
        if status_summary:
            for line in status_summary.split('\n'):
                console.print(f"  {line}")

        if not Confirm.ask("\nCommit all changes before export for teammate handoff?", default=True):
            console.print(f"[dim]Skipping commit - changes will not be included in export[/dim]")
        else:
            # Create WIP commit
            commit_message = f"""WIP: Session export for {issue_key}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

            if GitUtils.commit_all(working_dir, commit_message):
                console.print(f"[green]✓[/green] Created WIP commit for export")
            else:
                console.print(f"[yellow]⚠[/yellow] Failed to commit changes")
                return

    # Push branch to remote
    branch = active_conv.branch
    if not GitUtils.is_branch_pushed(working_dir, branch):
        console.print(f"\n[cyan]Branch '{branch}' is not on remote[/cyan]")

        # Check if auto_push_to_remote is configured
        should_push = True
        if config and config.prompts and config.prompts.auto_push_to_remote is not None:
            should_push = config.prompts.auto_push_to_remote
            if should_push:
                console.print(f"[dim]Automatically pushing to remote (configured in prompts)[/dim]")
        else:
            should_push = Confirm.ask(f"Push branch to remote?", default=True)

        if should_push:
            console.print(f"[dim]Pushing {branch} to origin...[/dim]")
            if GitUtils.push_branch(working_dir, branch):
                console.print(f"[green]✓[/green] Pushed branch to origin")
            else:
                console.print(f"[yellow]⚠[/yellow] Failed to push branch")
                console.print(f"[yellow]Your teammate will need to get the branch another way[/yellow]")
    else:
        # Branch exists on remote - push any new commits
        console.print(f"\n[dim]Pushing latest commits to remote...[/dim]")
        if GitUtils.push_branch(working_dir, branch):
            console.print(f"[green]✓[/green] Branch '{branch}' synced with remote")
        else:
            console.print(f"[yellow]⚠[/yellow] Failed to push to remote")
            console.print(f"[yellow]Your teammate may not have the latest changes[/yellow]")


def _export_and_attach_to_issue(issue_key: str, session_name: str, config_loader) -> None:
    """Export session group and attach to issue tracker ticket.

    Args:
        issue_key: issue tracker key
        session_name: Session group name
        config_loader: ConfigLoader instance
    """
    try:
        import tempfile
        from datetime import datetime

        export_manager = ExportManager(config_loader)
        session_manager = SessionManager(config_loader)

        # Get all sessions in this group
        sessions = session_manager.index.get_sessions(session_name)
        if not sessions:
            console.print(f"[yellow]⚠[/yellow] No sessions found for export")
            return

        console.print(f"\n[cyan]Exporting session group: {session_name}[/cyan]")
        console.print(f"[dim]Sessions: {len(sessions)}[/dim]")
        console.print(f"[dim]JIRA: {issue_key}[/dim]")

        # Sync branch before export for team handoff
        # Get the first session with valid project path and branch
        session_with_branch = next(
            (s for s in sessions
             if s.active_conversation and s.active_conversation.project_path and s.active_conversation.branch),
            None
        )
        if session_with_branch:
            _sync_branch_for_export(session_with_branch, issue_key, config_loader)

        # Export with conversation history to temp directory
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        export_filename = f"{session_name}-{timestamp}.tar.gz"
        # Use system temp directory to avoid cluttering current directory
        temp_dir = Path(tempfile.gettempdir())
        export_file = export_manager.export_sessions(
            identifiers=[session_name],
            output_path=temp_dir / export_filename,
        )

        # Show export details
        size_mb = export_file.stat().st_size / (1024 * 1024)
        console.print(f"[green]✓[/green] Exported session group to: {export_file}")
        console.print(f"  Size: {size_mb:.2f} MB")
        console.print(f"  Includes conversation history")

        # Attach to JIRA using API
        console.print(f"\n[cyan]Attaching to issue tracker ticket {issue_key}...[/cyan]")

        from devflow.jira.client import JiraClient
        jira_client = JiraClient()

        try:
            jira_client.attach_file(issue_key, str(export_file))
            console.print(f"[green]✓[/green] Attached to JIRA: {export_filename}")

            # Add comment with import instructions
            session_list = "\n".join([
                f"  #{s.session_id} {s.working_directory} ({s.message_count or 0} messages)"
                for s in sessions
            ])

            total_time = sum(
                sum((ws.end - ws.start).total_seconds() for ws in s.work_sessions if ws.end)
                for s in sessions
            )
            hours = int(total_time // 3600)
            minutes = int((total_time % 3600) // 60)

            comment = f"""📦 *Session Group Export: {session_name}*

*Sessions included:*
{session_list}

*To continue this work:*
1. Download the attachment: {export_filename}
2. Run: daf import {export_filename}
3. Resume with: daf open {session_name}

*Total time tracked:* {hours}h {minutes}m

_Generated by DevAIFlow_"""

            # Add comment using common utility
            if add_jira_comment(issue_key, comment, silent_success=True):
                console.print(f"[green]✓[/green] Export instructions added to JIRA")

        except JiraValidationError as e:
            console.print(f"[yellow]⚠[/yellow] Failed to attach to JIRA: {e}")
            if e.field_errors:
                console.print("  [yellow]Field errors:[/yellow]")
                for field, msg in e.field_errors.items():
                    console.print(f"    [yellow]• {field}: {msg}[/yellow]")
        except JiraNotFoundError as e:
            console.print(f"[yellow]⚠[/yellow] issue tracker ticket not found: {e}")
        except (JiraAuthError, JiraApiError, JiraConnectionError) as e:
            console.print(f"[yellow]⚠[/yellow] JIRA API error: {e}")

    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Failed to export and attach: {e}")


def _get_pr_for_branch(working_dir: Path, branch_name: str) -> Optional[dict]:
    """Check if there's a PR/MR for the specified branch.

    Queries the git provider (GitHub/GitLab) directly to check for existing PRs.

    Args:
        working_dir: Working directory path
        branch_name: Branch name to check for PRs

    Returns:
        Dictionary with 'url' and 'state' if a PR exists, None otherwise
        State can be: 'open', 'merged', 'closed'
    """
    import json

    try:
        # Detect repository type
        repo_type = GitUtils.detect_repo_type(working_dir)

        if repo_type == "github":
            # Use gh CLI to list PRs for this branch (including closed/merged)
            result = subprocess.run(
                ['gh', 'pr', 'list', '--head', branch_name, '--state', 'all', '--json', 'url,state', '--jq', '.[0]'],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                pr_data = json.loads(result.stdout)
                state = pr_data.get('state', '').upper()
                # Map GitHub states to our standard states
                if state == 'OPEN':
                    state_normalized = 'open'
                elif state == 'MERGED':
                    state_normalized = 'merged'
                elif state == 'CLOSED':
                    state_normalized = 'closed'
                else:
                    state_normalized = state.lower()

                return {
                    'url': pr_data.get('url'),
                    'state': state_normalized
                }

        elif repo_type == "gitlab":
            # Use glab CLI to list MRs for this branch (all states)
            # Note: --hostname flag is not supported in glab v1.77.0 and earlier
            result = subprocess.run(
                ['glab', 'mr', 'list', '--source-branch', branch_name, '--all', '-F', 'json'],
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                mr_list = json.loads(result.stdout)
                # Get the most recent MR (first in list)
                if mr_list:
                    mr = mr_list[0]
                    state = mr.get('state', '').lower()
                    # Map GitLab states to our standard states
                    if state == 'opened':
                        state_normalized = 'open'
                    elif state == 'merged':
                        state_normalized = 'merged'
                    elif state in ['closed', 'locked']:
                        state_normalized = 'closed'
                    else:
                        state_normalized = state

                    return {
                        'url': mr.get('web_url'),
                        'state': state_normalized
                    }
            else:
                # Log failure reason for debugging
                if result.returncode != 0:
                    console.print(f"[dim]Failed to detect MR: glab command failed with return code {result.returncode}[/dim]")
                    if result.stderr:
                        console.print(f"[dim]Error: {result.stderr.strip()}[/dim]")

    except FileNotFoundError as e:
        # gh/glab CLI not found, provide clear message
        error_str = str(e)
        filename = getattr(e, 'filename', '')
        if 'gh' in error_str or (filename and 'gh' in filename):
            console.print("[yellow]⚠[/yellow] GitHub CLI ('gh') not found - install from https://cli.github.com/")
        elif 'glab' in error_str or (filename and 'glab' in filename):
            console.print("[yellow]⚠[/yellow] GitLab CLI ('glab') not found - install from https://gitlab.com/gitlab-org/cli")
        else:
            console.print(f"[yellow]⚠[/yellow] Required CLI tool not found: {e}")
    except json.JSONDecodeError as e:
        console.print(f"[yellow]⚠[/yellow] Failed to parse PR/MR response: {e}")
    except Exception as e:
        # Log errors instead of silently swallowing them
        console.print(f"[yellow]⚠[/yellow] Failed to detect PR/MR: {e}")

    return None


def _create_pr_mr(session, working_dir: Path, session_manager) -> Optional[str]:
    """Create PR or MR based on repository type.

    Args:
        session: Session object
        working_dir: Working directory path
        session_manager: SessionManager instance

    Returns:
        PR/MR URL if successful, None otherwise
    """
    # Detect repository type
    repo_type = GitUtils.detect_repo_type(working_dir)

    if not repo_type:
        console.print("[yellow]⚠[/yellow] Could not detect repository type (GitHub or GitLab)")
        return None

    console.print(f"\n[cyan]Repository type detected: {repo_type.upper()}[/cyan]")

    # Get active conversation for accessing conversation-specific fields
    active_conv = session.active_conversation
    if not active_conv or not active_conv.branch:
        console.print("[yellow]⚠[/yellow] No active conversation or branch - cannot create PR/MR")
        return None

    # Load config early for push prompt check
    config = session_manager.config_loader.load_config()

    # Push branch to remote if there are unpushed commits
    current_branch = active_conv.branch
    if GitUtils.has_unpushed_commits(working_dir, current_branch):
        # Check if auto_push_to_remote is configured
        should_push = True
        if config and config.prompts and config.prompts.auto_push_to_remote is not None:
            should_push = config.prompts.auto_push_to_remote
            if should_push:
                console.print(f"\n[dim]Automatically pushing to remote (configured in prompts)[/dim]")
        else:
            should_push = Confirm.ask(f"Push branch '{current_branch}' to remote?", default=True)

        if should_push:
            console.print(f"[dim]Pushing {current_branch} to origin...[/dim]")
            if GitUtils.push_branch(working_dir, current_branch):
                console.print("[green]✓[/green] Pushed branch to origin")
            else:
                console.print("[yellow]⚠[/yellow] Failed to push branch")
                return None
    else:
        console.print(f"[dim]Branch '{current_branch}' is up to date with remote[/dim]")

    # Generate PR/MR description from session data
    description = _generate_pr_description(session, working_dir, session_manager.config_loader)

    # Generate PR/MR title from session and git data
    title = _generate_pr_title(session, working_dir)

    # Create PR/MR with retry logic
    console.print(f"\n[cyan]Creating {repo_type.upper()} PR/MR...[/cyan]")

    max_retries = 3
    pr_url = None

    for attempt in range(max_retries):
        if repo_type == "github":
            pr_url = _create_github_pr(session, title, description, working_dir, config)
        elif repo_type == "gitlab":
            pr_url = _create_gitlab_mr(session, title, description, working_dir, config)
        else:
            console.print(f"[yellow]⚠[/yellow] Unknown repository type: {repo_type}")
            return None

        # If successful, break out of retry loop
        if pr_url:
            break

        # PR creation failed
        if attempt < max_retries - 1:  # Not the last attempt
            console.print("\n[yellow]⚠[/yellow] Failed to create PR/MR")
            console.print("[yellow]Common issues:[/yellow]")
            console.print("  - Repository credentials not configured (gh auth login / glab auth login)")
            console.print("  - VPN connection required for internal repos")
            console.print("  - Network connectivity issues")
            console.print("  - Insufficient repository permissions")

            if not Confirm.ask(f"\nWould you like to try again? (Attempt {attempt + 2}/{max_retries})", default=True):
                break

            console.print("\n[dim]Please check your credentials, VPN connection, and try again...[/dim]")
        else:
            # Last attempt failed
            console.print("\n[red]✗[/red] Failed to create PR/MR after multiple attempts")
            console.print("[yellow]Troubleshooting steps:[/yellow]")
            console.print("  1. Verify repository credentials:")
            if repo_type == "github":
                console.print("     gh auth login")
            elif repo_type == "gitlab":
                console.print("     glab auth login")
            console.print("  2. Check VPN connection if required")
            console.print("  3. Verify repository permissions")
            console.print("  4. Test connection manually:")
            if repo_type == "github":
                console.print("     gh repo view")
            elif repo_type == "gitlab":
                console.print("     glab repo view")
            console.print("\n[dim]You can create the PR/MR manually later using:[/dim]")
            console.print(f"[dim]  Title: {title}[/dim]")
            console.print(f"[dim]  Branch: {active_conv.branch}[/dim]")

    # Store PR URL in session if created successfully
    if pr_url:
        # Add PR URL to active conversation
        if session.active_conversation:
            session.active_conversation.prs.append(pr_url)
        session_manager.update_session(session)

    return pr_url


def _fetch_github_with_gh_cli(owner: str, repo: str, file_path: str) -> Optional[str]:
    """Fetch GitHub file using gh CLI (authenticated).

    Args:
        owner: Repository owner
        repo: Repository name
        file_path: Path to file in repository

    Returns:
        File content or None if fetch fails
    """
    try:
        result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo}/contents/{file_path}', '--jq', '.content'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            import base64
            content_base64 = result.stdout.strip()
            template_content = base64.b64decode(content_base64).decode('utf-8')
            return template_content
        else:
            # Don't print error here - let caller try other methods
            return None

    except FileNotFoundError:
        # gh CLI not installed - caller will try other methods
        return None
    except Exception:
        # Other errors - log but don't fail completely
        return None


def _fetch_github_with_api(owner: str, repo: str, file_path: str, branch: str) -> Optional[str]:
    """Fetch GitHub file using REST API without authentication (public repos only).

    Rate limit: 60 requests/hour without auth, 5000/hour with auth.

    Args:
        owner: Repository owner
        repo: Repository name
        file_path: Path to file in repository
        branch: Branch name

    Returns:
        File content or None if fetch fails
    """
    try:
        import requests
        import base64

        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
        params = {'ref': branch}
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'devaiflow'
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            content_base64 = data.get('content', '')
            template_content = base64.b64decode(content_base64).decode('utf-8')
            return template_content

        # Rate limit, not found, or other error - return None
        return None

    except Exception:
        return None


def _fetch_github_raw(owner: str, repo: str, file_path: str, branch: str) -> Optional[str]:
    """Fetch GitHub file from raw.githubusercontent.com (public repos only).

    Args:
        owner: Repository owner
        repo: Repository name
        file_path: Path to file in repository
        branch: Branch name

    Returns:
        File content or None if fetch fails
    """
    try:
        import requests

        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
        headers = {'User-Agent': 'devaiflow'}

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.text

        return None

    except Exception:
        return None


def _fetch_github_template(template_url: str) -> Optional[str]:
    """Fetch GitHub template with three-tier fallback.

    Tries (in order):
    1. gh CLI (authenticated, supports private repos)
    2. GitHub REST API (unauthenticated, public repos only)
    3. Raw GitHub URL (direct access, public repos only)

    Args:
        template_url: GitHub blob or raw URL

    Returns:
        Template content or None if all methods fail
    """
    import re

    # Parse URL to extract components
    if 'raw.githubusercontent.com' in template_url:
        match = re.match(
            r'https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)',
            template_url
        )
    else:
        match = re.match(
            r'https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)',
            template_url
        )

    if not match:
        console.print(f"[yellow]⚠[/yellow] Could not parse GitHub URL: {template_url}")
        return None

    owner, repo, branch, file_path = match.groups()

    # Method 1: Try gh CLI (authenticated, supports private repos)
    content = _fetch_github_with_gh_cli(owner, repo, file_path)
    if content:
        console.print("[dim]✓ Template fetched successfully (gh CLI)[/dim]")
        return content

    # Method 2: Try GitHub REST API (unauthenticated, public repos only)
    console.print("[dim]Trying unauthenticated GitHub API...[/dim]")
    content = _fetch_github_with_api(owner, repo, file_path, branch)
    if content:
        console.print("[dim]✓ Template fetched successfully (GitHub API)[/dim]")
        return content

    # Method 3: Try raw URL (direct access, public repos only)
    console.print("[dim]Trying raw GitHub URL...[/dim]")
    content = _fetch_github_raw(owner, repo, file_path, branch)
    if content:
        console.print("[dim]✓ Template fetched successfully (raw URL)[/dim]")
        return content

    # All methods failed
    console.print(
        f"[yellow]⚠[/yellow] Could not fetch template from GitHub. "
        f"If this is a private repository, ensure 'gh' CLI is installed and authenticated."
    )
    return None


def _fetch_gitlab_template(template_url: str) -> Optional[str]:
    """Fetch GitLab template using glab CLI.

    Args:
        template_url: GitLab blob URL

    Returns:
        Template content or None if fetch fails
    """
    import re

    # Match any GitLab instance (gitlab.com, self-hosted, etc.)
    match = re.match(r'https://([^/]+)/([^/]+/[^/]+)/-/blob/([^/]+)/(.+)', template_url)

    if not match or 'gitlab' not in match.group(1).lower():
        console.print(f"[yellow]⚠[/yellow] Could not parse GitLab URL: {template_url}")
        return None

    hostname, project_path, branch, file_path = match.groups()

    # Extract hostname for --hostname parameter (for non-gitlab.com instances)
    hostname_param = None
    if hostname != 'gitlab.com':
        hostname_param = hostname

    # Build glab command
    glab_cmd = ['glab', 'api', f'projects/{project_path.replace("/", "%2F")}/repository/files/{file_path.replace("/", "%2F")}/raw', '--field', f'ref={branch}']

    # Add hostname if non-standard GitLab instance
    if hostname_param:
        glab_cmd.extend(['--hostname', hostname_param])

    # Use glab CLI to fetch file content
    result = subprocess.run(
        glab_cmd,
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode == 0:
        template_content = result.stdout
        console.print("[dim]✓ Template fetched successfully[/dim]")
        return template_content
    else:
        console.print(f"[yellow]⚠[/yellow] glab CLI error: {result.stderr}")
        return None


def _fetch_pr_template(template_url: str) -> Optional[str]:
    """Fetch PR/MR template from a URL with multiple fallback methods.

    For GitHub URLs, tries (in order):
    1. gh CLI (authenticated, supports private repos)
    2. GitHub REST API (unauthenticated, public repos only)
    3. Raw GitHub URL (direct access, public repos only)

    For GitLab URLs:
    1. glab CLI (authenticated)

    For other URLs:
    1. urllib (direct HTTP fetch)

    Args:
        template_url: GitHub/GitLab URL to the template file
                     (e.g., https://github.com/org/repo/blob/main/path/to/file.md)

    Returns:
        Template content as string or None if fetch fails
    """
    try:
        console.print(f"[dim]Fetching PR template from {template_url}...[/dim]")

        # GitHub URLs
        if 'github.com' in template_url or 'raw.githubusercontent.com' in template_url:
            return _fetch_github_template(template_url)

        # GitLab URLs (any instance)
        elif 'gitlab' in template_url.lower():
            return _fetch_gitlab_template(template_url)

        # Other URLs - direct fetch (keep existing urllib fallback)
        else:
            with urllib.request.urlopen(template_url, timeout=10) as response:
                template_content = response.read().decode('utf-8')
                console.print("[dim]✓ Template fetched successfully[/dim]")
                return template_content

    except FileNotFoundError as e:
        # Keep existing error messages
        if 'gh' in str(e):
            console.print("[yellow]⚠[/yellow] GitHub CLI ('gh') not found. Install: https://cli.github.com/")
        elif 'glab' in str(e):
            console.print("[yellow]⚠[/yellow] GitLab CLI ('glab') not found. Install: https://gitlab.com/gitlab-org/cli")
        return None
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not fetch template: {e}")
        return None


def _fill_pr_template(template_content: str, session, working_dir: Path, git_context: dict) -> str:
    """Fill in PR/MR template using AI to understand and populate all fields.

    This is a wrapper around the AI-powered template filling module that replaces
    the old hardcoded pattern matching approach.

    Args:
        template_content: Raw template content with placeholders
        session: Session object
        working_dir: Working directory path
        git_context: Dictionary with git information (commits, files, branches)

    Returns:
        AI-filled template ready for PR/MR creation
    """
    # Use AI-powered template filling
    return fill_pr_template_with_ai(template_content, session, working_dir, git_context)


def _generate_pr_description(session, working_dir: Path, config_loader: ConfigLoader) -> str:
    """Generate PR/MR description from session data using AI analysis and template.

    Args:
        session: Session object
        working_dir: Working directory path for git analysis
        config_loader: ConfigLoader instance to get template URL from config

    Returns:
        Formatted PR/MR description with AI-generated summary
    """
    # Get active conversation for accessing conversation-specific fields
    active_conv = session.active_conversation

    # Try to fetch PR template from config
    config = config_loader.load_config()
    template_content = None

    # If no template URL configured, prompt the user
    if config and not config.pr_template_url:
        console.print("\n[yellow]No PR/MR template URL configured.[/yellow]")
        if Confirm.ask("Would you like to configure a PR/MR template URL now?", default=True):
            console.print(f"\n[dim]Example: https://raw.githubusercontent.com/YOUR-ORG/.github/main/.github/PULL_REQUEST_TEMPLATE.md[/dim]")
            template_url = Prompt.ask("Enter PR/MR template URL (leave empty to skip)", default="")
            if template_url and template_url.strip():
                config.pr_template_url = template_url.strip()

            # Save updated config
            if config.pr_template_url:
                config_loader.save_config(config)
                console.print(f"[green]✓[/green] Saved PR template URL to config")

    if config and config.pr_template_url:
        template_content = _fetch_pr_template(config.pr_template_url)

    # Gather git context for AI template filling
    base_branch = GitUtils.get_default_branch(working_dir)
    commit_log = GitUtils.get_commit_log(working_dir, base_branch)
    changed_files = GitUtils.get_changed_files(working_dir, base_branch)

    git_context = {
        'commit_log': commit_log,
        'changed_files': changed_files,
        'base_branch': base_branch,
        'current_branch': active_conv.branch if active_conv else None
    }

    # If we have a template, use AI to fill it; otherwise use default format
    if template_content:
        # Use AI-powered template filling
        description = _fill_pr_template(template_content, session, working_dir, git_context)
    else:
        # Fallback to built-in template
        jira_section = ""
        if session.issue_key:
            jira_url = config.jira.url if config and config.jira else None
            if jira_url:
                jira_section = f"Jira Issue: {jira_url}/browse/{session.issue_key}\n\n"

        # Try to generate AI-powered summary from session and git data
        summary_bullets = _generate_pr_summary_bullets(session, working_dir)

        # If AI summary failed, fall back to session goal
        if not summary_bullets:
            description_content = session.goal
        else:
            description_content = f"## Summary\n{summary_bullets}\n"

        description = f"""{jira_section}{description_content}

## Test plan
- [ ] Pull down the PR and verify changes build successfully
- [ ] Test the modified functionality
- [ ] Verify no regressions in related features

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

    return description


def _generate_pr_summary_bullets(session, working_dir: Path) -> Optional[str]:
    """Generate bullet point summary for PR/MR description using AI.

    Analyzes both git commits and session conversation to create a meaningful summary.

    Args:
        session: Session object
        working_dir: Working directory path for git analysis

    Returns:
        Bullet point summary (markdown format) or None if generation fails
    """
    # Get active conversation for accessing conversation-specific fields
    active_conv = session.active_conversation

    try:
        import subprocess
        from devflow.session.summary import generate_session_summary

        # Gather git commit information
        base_branch = GitUtils.get_default_branch(working_dir)
        commit_log = GitUtils.get_commit_log(working_dir, base_branch)
        changed_files = GitUtils.get_changed_files(working_dir, base_branch)

        # Gather session conversation summary
        session_summary = None
        if active_conv and active_conv.ai_agent_session_id:
            try:
                session_summary = generate_session_summary(session)
            except Exception:
                pass

        # Build context for AI
        context_parts = []

        if commit_log:
            context_parts.append(f"Commits:\n{commit_log}")

        if changed_files:
            files_str = "\n".join(changed_files[:20])
            context_parts.append(f"Files changed ({len(changed_files)}):\n{files_str}")
            if len(changed_files) > 20:
                context_parts.append(f"... and {len(changed_files) - 20} more")

        if session_summary:
            if session_summary.last_assistant_message:
                context_parts.append(f"Session context:\n{session_summary.last_assistant_message[:500]}")

        if not context_parts:
            return None

        context = "\n\n".join(context_parts)

        # Build prompt for Claude CLI
        prompt = f"""Based on this pull request data, generate a concise summary in bullet point format.

{context}

Generate a summary with 2-4 bullet points that:
- Start each bullet with an action verb (Add, Fix, Update, Refactor, Remove, Implement, etc.)
- Are specific about what changed (mention key files/components if relevant)
- Focus on WHAT was done, not WHY
- Are technical and precise

Format as markdown bullets. Return ONLY the bullet points, nothing else."""

        # Try using Claude CLI for best quality
        result = subprocess.run(
            ["claude"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            summary = result.stdout.strip()
            # Clean up any extra formatting
            if summary:
                console.print("[dim]Generated PR summary using AI[/dim]")
                return summary

        return None

    except FileNotFoundError:
        # Claude CLI not installed, try Anthropic API
        return _generate_pr_summary_with_api(session, working_dir)
    except Exception as e:
        console.print(f"[dim]PR summary generation failed: {e}[/dim]")
        return None


def _generate_pr_title(session, working_dir: Path) -> str:
    """Generate PR/MR title from session and git data.

    Uses the issue key if available, plus an AI-generated or goal-based description.

    Args:
        session: Session object
        working_dir: Working directory path for git analysis

    Returns:
        PR/MR title string
    """
    # Start with issue key if available
    title_prefix = f"{session.issue_key}: " if session.issue_key else ""

    # Try to generate a concise title from commits
    try:
        base_branch = GitUtils.get_default_branch(working_dir)
        commit_log = GitUtils.get_commit_log(working_dir, base_branch)
        changed_files = GitUtils.get_changed_files(working_dir, base_branch)

        if commit_log:
            # Get the most recent commit as a base
            commits = [c.strip() for c in commit_log.split('\n') if c.strip()]

            # If there's only one commit and it doesn't start with issue key, use it
            if len(commits) == 1:
                commit_msg = commits[0]
                # Remove issue key prefix if present
                if session.issue_key and commit_msg.startswith(session.issue_key):
                    commit_msg = commit_msg[len(session.issue_key):].strip(': ')
                # Remove leading/trailing backticks from markdown code fences
                commit_msg = commit_msg.strip('`').strip()
                if commit_msg:
                    return f"{title_prefix}{commit_msg}"

            # For multiple commits, try to generate a summary title
            if len(commits) > 1 and changed_files:
                # Look for common patterns in commits
                all_commits = " ".join(commits).lower()

                # Detect type of work based on commits and files
                if "fix" in all_commits or "bug" in all_commits:
                    action = "Fix"
                elif "add" in all_commits or "implement" in all_commits:
                    action = "Add"
                elif "update" in all_commits or "improve" in all_commits:
                    action = "Update"
                elif "refactor" in all_commits:
                    action = "Refactor"
                elif "remove" in all_commits or "delete" in all_commits:
                    action = "Remove"
                else:
                    action = "Update"

                # Try to identify the main component being changed
                # Look at the most common directory or file prefix
                if changed_files:
                    first_file = changed_files[0]
                    # Extract component from path (e.g., "devflow/cli/commands" -> "commands")
                    parts = first_file.split('/')
                    if len(parts) > 1:
                        component = parts[-2] if parts[-1].endswith('.py') else parts[-1]
                        return f"{title_prefix}{action} {component} functionality"

                return f"{title_prefix}{action} multiple components"

    except Exception:
        pass

    # Fallback: use session goal
    goal = session.goal

    # Remove issue key from goal if present
    if session.issue_key and goal.startswith(f"{session.issue_key}:"):
        goal = goal[len(session.issue_key) + 1:].strip()
    elif session.issue_key and goal.startswith(session.issue_key):
        goal = goal[len(session.issue_key):].strip()

    # Capitalize first letter if needed
    if goal and not goal[0].isupper():
        goal = goal[0].upper() + goal[1:]

    return f"{title_prefix}{goal}"


def _generate_pr_summary_with_api(session, working_dir: Path) -> Optional[str]:
    """Generate PR summary using Anthropic API as fallback.

    Args:
        session: Session object
        working_dir: Working directory path for git analysis

    Returns:
        Bullet point summary or None if generation fails
    """
    # Get active conversation for accessing conversation-specific fields
    active_conv = session.active_conversation

    try:
        import anthropic
        import os
        from devflow.session.summary import generate_session_summary

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None

        # Gather git commit information
        base_branch = GitUtils.get_default_branch(working_dir)
        commit_log = GitUtils.get_commit_log(working_dir, base_branch)
        changed_files = GitUtils.get_changed_files(working_dir, base_branch)

        # Gather session conversation summary
        session_summary = None
        if active_conv and active_conv.ai_agent_session_id:
            try:
                session_summary = generate_session_summary(session)
            except Exception:
                pass

        # Build context for AI
        context_parts = []

        if commit_log:
            context_parts.append(f"Commits:\n{commit_log}")

        if changed_files:
            files_str = "\n".join(changed_files[:20])
            context_parts.append(f"Files changed ({len(changed_files)}):\n{files_str}")
            if len(changed_files) > 20:
                context_parts.append(f"... and {len(changed_files) - 20} more")

        if session_summary:
            if session_summary.last_assistant_message:
                context_parts.append(f"Session context:\n{session_summary.last_assistant_message[:500]}")

        if not context_parts:
            return None

        context = "\n\n".join(context_parts)

        # Call Anthropic API
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Based on this pull request data, generate a concise summary in bullet point format.

{context}

Generate a summary with 2-4 bullet points that:
- Start each bullet with an action verb (Add, Fix, Update, Refactor, Remove, Implement, etc.)
- Are specific about what changed (mention key files/components if relevant)
- Focus on WHAT was done, not WHY
- Are technical and precise

Format as markdown bullets. Return ONLY the bullet points, nothing else."""
            }]
        )

        if message.content and len(message.content) > 0:
            summary = message.content[0].text.strip()
            console.print("[dim]Generated PR summary using Anthropic API[/dim]")
            return summary

        return None

    except Exception as e:
        console.print(f"[dim]API summary generation failed: {e}[/dim]")
        return None


def _create_github_pr(session, title: str, description: str, working_dir: Path, config=None) -> Optional[str]:
    """Create GitHub PR using gh CLI.

    Automatically detects if working in a fork and creates PR to upstream repository.

    Args:
        session: Session object
        title: PR title
        description: PR description
        working_dir: Working directory path
        config: Config object (optional, used for auto_create_pr_status)

    Returns:
        PR URL if successful, None otherwise

    Raises:
        ToolNotFoundError: If gh CLI is not installed
    """
    try:
        require_tool("gh", "create GitHub pull request")
    except ToolNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        console.print("[yellow]⚠[/yellow] Install gh CLI to enable GitHub PR creation")
        return None
    # Determine if PR should be created as draft
    create_as_draft = True  # default
    if config and config.prompts:
        pr_status = config.prompts.auto_create_pr_status
        if pr_status == "draft":
            create_as_draft = True
            console.print("[dim]Creating as draft (configured in prompts)[/dim]")
        elif pr_status == "ready":
            create_as_draft = False
            console.print("[dim]Creating as ready for review (configured in prompts)[/dim]")
        else:  # "prompt"
            create_as_draft = Confirm.ask("Create PR as draft?", default=True)

    # Detect if this is a fork and get upstream info
    # prompt_for_remote=True asks user which remote is upstream if auto-detection fails
    upstream_info = GitUtils.get_fork_upstream_info(working_dir, prompt_for_remote=True)

    try:
        # Build command with or without --draft flag
        cmd = ["gh", "pr", "create"]
        if create_as_draft:
            cmd.append("--draft")
        cmd.extend(["--title", title, "--body", description])

        # If fork detected, add base repository
        if upstream_info:
            base_repo = f"{upstream_info['upstream_owner']}/{upstream_info['upstream_repo']}"
            cmd.extend(["--repo", base_repo])
            if upstream_info['detection_method'] == 'user_prompt':
                console.print(f"[dim]Creating PR to user-specified upstream: {base_repo}[/dim]")
            else:
                console.print(f"[dim]Detected fork - creating PR to upstream: {base_repo}[/dim]")

        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            # Extract PR URL from output (gh pr create returns URL)
            pr_url = result.stdout.strip()
            console.print(f"[green]✓[/green] Created PR: {pr_url}")
            return pr_url
        else:
            console.print(f"[yellow]⚠[/yellow] Failed to create PR: {result.stderr}")
            return None

    except FileNotFoundError:
        console.print("[yellow]⚠[/yellow] 'gh' CLI not found. Please install GitHub CLI: https://cli.github.com/")
        return None
    except subprocess.TimeoutExpired:
        console.print("[yellow]⚠[/yellow] PR creation timed out")
        return None
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Exception creating PR: {e}")
        return None


def _create_gitlab_mr(session, title: str, description: str, working_dir: Path, config=None) -> Optional[str]:
    """Create GitLab MR using glab CLI.

    Automatically detects if working in a fork and creates MR to upstream repository.

    Args:
        session: Session object
        title: MR title
        description: MR description
        working_dir: Working directory path
        config: Config object (optional, used for auto_create_pr_status)

    Returns:
        MR URL if successful, None otherwise

    Raises:
        ToolNotFoundError: If glab CLI is not installed
    """
    try:
        require_tool("glab", "create GitLab merge request")
    except ToolNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        console.print("[yellow]⚠[/yellow] Install glab CLI to enable GitLab MR creation")
        return None
    # Determine if MR should be created as draft
    create_as_draft = True  # default
    if config and config.prompts:
        pr_status = config.prompts.auto_create_pr_status
        if pr_status == "draft":
            create_as_draft = True
            console.print("[dim]Creating as draft (configured in prompts)[/dim]")
        elif pr_status == "ready":
            create_as_draft = False
            console.print("[dim]Creating as ready for review (configured in prompts)[/dim]")
        else:  # "prompt"
            create_as_draft = Confirm.ask("Create MR as draft?", default=True)

    # Detect if this is a fork and get upstream info
    # prompt_for_remote=True asks user which remote is upstream if auto-detection fails
    upstream_info = GitUtils.get_fork_upstream_info(working_dir, prompt_for_remote=True)

    try:
        # Build command with or without --draft flag
        cmd = ["glab", "mr", "create"]
        if create_as_draft:
            cmd.append("--draft")
        cmd.extend(["--title", title, "--description", description])

        # If fork detected, add target project
        if upstream_info:
            # For GitLab, use --target-project to specify upstream repo
            target_project = f"{upstream_info['upstream_owner']}/{upstream_info['upstream_repo']}"
            cmd.extend(["--target-project", target_project])
            if upstream_info['detection_method'] == 'user_prompt':
                console.print(f"[dim]Creating MR to user-specified upstream: {target_project}[/dim]")
            else:
                console.print(f"[dim]Detected fork - creating MR to upstream: {target_project}[/dim]")

        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            # Extract MR URL from output
            # glab mr create typically outputs the URL in the last line
            output_lines = result.stdout.strip().split('\n')
            mr_url = None
            for line in reversed(output_lines):
                if "http" in line.lower():
                    mr_url = line.strip()
                    break

            if mr_url:
                console.print(f"[green]✓[/green] Created MR: {mr_url}")
                return mr_url
            else:
                console.print(f"[yellow]⚠[/yellow] MR created but could not extract URL")
                console.print(f"[dim]{result.stdout}[/dim]")
                return None
        else:
            console.print(f"[yellow]⚠[/yellow] Failed to create MR: {result.stderr}")
            return None

    except FileNotFoundError:
        console.print("[yellow]⚠[/yellow] 'glab' CLI not found. Please install GitLab CLI: https://gitlab.com/gitlab-org/cli")
        return None
    except subprocess.TimeoutExpired:
        console.print("[yellow]⚠[/yellow] MR creation timed out")
        return None
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Exception creating MR: {e}")
        return None


def _generate_commit_message(session) -> str:
    """Generate commit message from git diff instead of conversation history.

    This ensures commit messages describe only uncommitted changes being committed,
    not the entire session history.

    Args:
        session: Session object

    Returns:
        Auto-generated commit message
    """
    # Get active conversation for accessing conversation-specific fields
    active_conv = session.active_conversation

    # Try AI-powered commit message generation from git diff
    if active_conv and active_conv.project_path:
        try:
            import logging
            from devflow.utils.paths import get_cs_home

            # Set up logging for diagnostics
            log_dir = get_cs_home() / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "complete.log"

            # Create logger
            logger = logging.getLogger("devflow.complete")
            logger.setLevel(logging.DEBUG)

            # Remove existing handlers to avoid duplicates
            logger.handlers.clear()

            # Add file handler
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            logger.addHandler(fh)

            console.print("[dim]Analyzing git diff to generate commit message...[/dim]")
            logger.info(f"Starting commit message generation for session: {session.name}")
            logger.debug(f"Session details: project_path={active_conv.project_path}")

            working_dir = Path(active_conv.project_path)

            # Check if this is a git repository
            if not GitUtils.is_git_repository(working_dir):
                logger.warning(f"Not a git repository: {working_dir}")
                console.print("[yellow]⚠[/yellow]  Not a git repository - using simple commit message")
                # Fall through to fallback
            else:
                # Get uncommitted diff (both staged and unstaged changes)
                diff_content = GitUtils.get_uncommitted_diff(working_dir)

                if not diff_content:
                    logger.warning("No uncommitted changes found in git diff")
                    console.print("[yellow]⚠[/yellow]  No uncommitted changes - using simple commit message")
                    # Fall through to fallback
                else:
                    logger.info(f"Found git diff (size: {len(diff_content)} chars)")

                    # Get list of changed files for context
                    status_summary = GitUtils.get_status_summary(working_dir)
                    logger.debug(f"Status summary: {status_summary}")

                    # Generate commit message from diff using AI
                    logger.debug("Generating commit message from git diff...")
                    commit_message = _generate_commit_message_from_diff(diff_content, status_summary)

                    if commit_message:
                        logger.info("Successfully generated AI commit message from git diff")
                        logger.debug(f"Commit message: {commit_message[:100]}...")
                        return commit_message
                    else:
                        logger.warning("Failed to generate commit message from diff")
                        console.print("[yellow]⚠[/yellow]  Failed to generate commit message from diff - using simple commit message")

        except Exception as e:
            # If AI generation fails, fall back to simple method
            import logging
            import traceback

            # Log the full error
            logger = logging.getLogger("devflow.complete")
            logger.error(f"Exception during AI commit message generation: {e}")
            logger.error(traceback.format_exc())

            console.print(f"[yellow]⚠[/yellow]  Could not generate AI commit message: {type(e).__name__}")
            console.print(f"[dim]Using simple commit message based on session goal[/dim]")
            from devflow.utils.paths import get_cs_home
            log_path = get_cs_home() / "logs" / "complete.log"
            console.print(f"[dim]Check logs for details: {log_path}[/dim]")

    # Fallback: Use session goal
    message = session.goal

    # If goal starts with issue key format, remove it
    if session.issue_key and message.startswith(f"{session.issue_key}:"):
        message = message[len(session.issue_key) + 1:].strip()
    elif session.issue_key and message.startswith(session.issue_key):
        message = message[len(session.issue_key):].strip()

    # Capitalize first letter if needed
    if message and not message[0].isupper():
        message = message[0].upper() + message[1:]

    return message


def _generate_commit_message_from_diff(diff_content: str, status_summary: str) -> Optional[str]:
    """Generate commit message from git diff using Claude CLI.

    Args:
        diff_content: Git diff output (both staged and unstaged changes)
        status_summary: Git status --short output

    Returns:
        Generated commit message or None if generation fails
    """
    try:
        # Truncate diff if it's too large (keep first 5000 chars for context)
        # This prevents token limits while still providing sufficient context
        truncated_diff = diff_content[:5000]
        if len(diff_content) > 5000:
            truncated_diff += "\n\n... (diff truncated for analysis)"

        # Build prompt for Claude CLI
        prompt = f"""Based on this git diff, generate a commit message in conventional commit format.

Git Status:
{status_summary}

Git Diff:
{truncated_diff}

Generate a commit message with:
- First line: Imperative verb + brief description (max 72 chars)
- Blank line
- 2-4 bullet points describing what changed
- Focus on WHAT changed, not WHY
- NO JIRA keys or ticket numbers

Return ONLY the commit message."""

        # Call Claude CLI
        result = subprocess.run(
            ["claude"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            commit_text = result.stdout.strip()
            # Clean up any code fences
            commit_text = commit_text.strip('`').strip()
            if commit_text.startswith('```'):
                lines = commit_text.split('\n')
                commit_text = '\n'.join(line for line in lines if not line.strip().startswith('```'))
                commit_text = commit_text.strip()
            return commit_text

        return None

    except FileNotFoundError:
        # Claude CLI not installed, try Anthropic API
        return _generate_commit_message_from_diff_api(diff_content, status_summary)
    except Exception:
        return None


def _generate_commit_message_from_diff_api(diff_content: str, status_summary: str) -> Optional[str]:
    """Generate commit message from git diff using Anthropic API.

    Args:
        diff_content: Git diff output
        status_summary: Git status --short output

    Returns:
        Generated commit message or None if generation fails
    """
    try:
        import anthropic
        import os

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None

        # Truncate diff if too large
        truncated_diff = diff_content[:5000]
        if len(diff_content) > 5000:
            truncated_diff += "\n\n... (diff truncated for analysis)"

        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Based on this git diff, generate a commit message in conventional commit format.

Git Status:
{status_summary}

Git Diff:
{truncated_diff}

Generate a commit message with:
- First line: Imperative verb + brief description (max 72 chars)
- Blank line
- 2-4 bullet points describing what changed
- Focus on WHAT changed, not WHY
- NO JIRA keys or ticket numbers

Return ONLY the commit message."""
            }]
        )

        if message.content and len(message.content) > 0:
            commit_text = message.content[0].text.strip()
            # Clean up any code fences
            commit_text = commit_text.strip('`').strip()
            if commit_text.startswith('```'):
                lines = commit_text.split('\n')
                commit_text = '\n'.join(line for line in lines if not line.strip().startswith('```'))
                commit_text = commit_text.strip()
            return commit_text

        return None

    except Exception:
        return None


def _convert_summary_to_commit_message(prose_summary: str, summary_data) -> Optional[str]:
    """Convert prose summary into commit message format using claude CLI.

    DEPRECATED: This function is no longer used. Commit messages are now generated
    from git diff instead of conversation history.

    Args:
        prose_summary: Prose summary from generate_prose_summary
        summary_data: SessionSummary object

    Returns:
        Formatted commit message or None if conversion fails
    """
    try:
        # Get files changed for context
        files_changed = list(summary_data.files_created) + list(summary_data.files_modified)
        files_context = f"Files modified: {', '.join(files_changed[:10])}" if files_changed else ""

        # Build prompt for Claude CLI to convert summary to commit message
        prompt = f"""Based on this session summary, generate a git commit message in conventional commit format.

Session Summary:
{prose_summary[:500]}

{files_context}

Generate a commit message with:
- First line: Imperative verb + brief description (max 72 chars)
- Blank line
- 2-4 bullet points describing what changed
- NO JIRA keys or ticket numbers

Return ONLY the commit message."""

        # Call Claude CLI
        result = subprocess.run(
            ["claude"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=30,
        )


        if result.returncode == 0:
            commit_text = result.stdout.strip()
            return commit_text

        return None

    except FileNotFoundError:
        # Claude CLI not installed, return None to use fallback
        return None
    except Exception:
        return None


def _generate_commit_with_claude_cli(summary_data) -> Optional[str]:
    """Generate commit message using Claude CLI.

    Args:
        summary_data: SessionSummary object from generate_session_summary

    Returns:
        Generated commit message or None if CLI not available
    """
    try:
        # Check if there's actually any meaningful data
        has_file_changes = (summary_data.files_created or summary_data.files_modified)
        has_tool_activity = bool(summary_data.tool_call_stats)

        if not has_file_changes and not has_tool_activity:
            return None

        # Combine files created and modified
        files_changed = list(summary_data.files_created) + list(summary_data.files_modified)

        # Build context for AI
        context_parts = []

        if files_changed:
            context_parts.append(f"Files changed ({len(files_changed)}): {', '.join(files_changed[:15])}")

        if summary_data.tool_call_stats:
            stats_str = ", ".join([f"{tool}: {count}" for tool, count in summary_data.tool_call_stats.items()])
            context_parts.append(f"Tool usage: {stats_str}")

        if summary_data.commands_run:
            commands = [cmd.command for cmd in summary_data.commands_run[:5]]
            context_parts.append(f"Commands: {', '.join(commands)}")

        if summary_data.last_assistant_message:
            msg_snippet = summary_data.last_assistant_message[:300]
            context_parts.append(f"Summary: {msg_snippet}")

        if not context_parts:
            return None

        context = "\n".join(context_parts)

        # Build prompt for Claude CLI
        prompt = f"""Based on this development session, generate a detailed git commit message following conventional commit format.

{context}

The commit message should have:

**FIRST LINE (required):**
- Start with an imperative verb (Add, Fix, Update, Refactor, Remove, etc.)
- Be specific and descriptive (up to 72 characters)
- NOT include any JIRA keys or ticket numbers

**BODY (required, after blank line):**
- Provide 2-4 bullet points explaining what was changed
- Focus on WHAT changed, not WHY
- Be specific about key changes, new features, or fixes
- Mention important files or components affected

Format:
```
Short descriptive title (max 72 chars)

- First major change or addition
- Second important modification
- Third key update (if applicable)
- Fourth detail (if applicable)
```

Return ONLY the commit message in this exact format, nothing else."""

        # Call Claude CLI
        result = subprocess.run(
            ["claude"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            commit_text = result.stdout.strip()

            # Clean up any code fences or extra formatting
            commit_text = commit_text.strip('`').strip()
            if commit_text.startswith('```'):
                lines = commit_text.split('\n')
                commit_text = '\n'.join(line for line in lines if not line.strip().startswith('```'))
                commit_text = commit_text.strip()

            console.print(f"[dim]Generated commit message using Claude CLI[/dim]")
            return commit_text

        return None

    except FileNotFoundError:
        # Claude CLI not installed
        return None
    except Exception as e:
        console.print(f"[dim]Claude CLI generation failed: {e}[/dim]")
        return None


def _generate_commit_from_summary(summary_data) -> Optional[str]:
    """Generate commit message from conversation summary using AI.

    Args:
        summary_data: SessionSummary object from generate_session_summary

    Returns:
        Generated commit message or None if generation fails
    """
    try:
        import anthropic
        import os

        # Check if there's actually any meaningful data in the summary
        has_file_changes = (summary_data.files_created or summary_data.files_modified)
        has_tool_activity = bool(summary_data.tool_call_stats)


        # If no file changes and no tool activity, don't bother with AI
        if not has_file_changes and not has_tool_activity:
            return None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None


        client = anthropic.Anthropic(api_key=api_key)

        # Combine files created and modified
        files_changed = list(summary_data.files_created) + list(summary_data.files_modified)

        # Build context for AI with actual data from the session
        context_parts = []

        if files_changed:
            context_parts.append(f"Files changed ({len(files_changed)}): {', '.join(files_changed[:15])}")

        if summary_data.tool_call_stats:
            stats_str = ", ".join([f"{tool}: {count}" for tool, count in summary_data.tool_call_stats.items()])
            context_parts.append(f"Tool usage: {stats_str}")

        if summary_data.commands_run:
            commands = [cmd.command for cmd in summary_data.commands_run[:5]]
            context_parts.append(f"Commands: {', '.join(commands)}")

        if summary_data.last_assistant_message:
            # Include a snippet of the last message for context
            msg_snippet = summary_data.last_assistant_message[:300]
            context_parts.append(f"Summary: {msg_snippet}")

        if not context_parts:
            # No meaningful context
            return None

        context = "\n".join(context_parts)

        # Request commit message from Claude
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Based on this development session, generate a detailed git commit message following conventional commit format.

{context}

The commit message should have:

**FIRST LINE (required):**
- Start with an imperative verb (Add, Fix, Update, Refactor, Remove, etc.)
- Be specific and descriptive (up to 72 characters)
- NOT include any JIRA keys or ticket numbers

**BODY (required, after blank line):**
- Provide 2-4 bullet points explaining what was changed
- Focus on WHAT changed, not WHY
- Be specific about key changes, new features, or fixes
- Mention important files or components affected

Format:
```
Short descriptive title (max 72 chars)

- First major change or addition
- Second important modification
- Third key update (if applicable)
- Fourth detail (if applicable)
```

Return ONLY the commit message in this exact format, nothing else."""
            }]
        )

        # Extract the commit message
        commit_text = message.content[0].text.strip()

        # Clean up any code fences or extra formatting
        commit_text = commit_text.strip('`').strip()
        if commit_text.startswith('```'):
            # Remove code fence markers
            lines = commit_text.split('\n')
            commit_text = '\n'.join(line for line in lines if not line.strip().startswith('```'))
            commit_text = commit_text.strip()

        return commit_text

    except Exception as e:
        console.print(f"[dim]AI commit message generation failed: {e}[/dim]")
        return None


def _update_jira_pr_field(issue_key: str, pr_url: str, no_issue_update: bool = False) -> None:
    """Update JIRA Git Pull Request field with PR/MR URL.

    Args:
        issue_key: issue tracker key
        pr_url: PR/MR URL to add
        no_issue_update: If True, skip JIRA update
    """
    # Check if we should update (or use configured default)
    should_update = True
    config_loader = ConfigLoader()
    config = config_loader.load_config()

    if no_issue_update:
        should_update = False
        console.print("\n[dim]Skipping JIRA PR update (--no-issue-update flag)[/dim]")
    elif config and config.prompts and config.prompts.auto_update_jira_pr_url is not None:
        should_update = config.prompts.auto_update_jira_pr_url
        if should_update:
            console.print("\nAutomatically updating JIRA with PR URL (configured in prompts)")
    else:
        should_update = Confirm.ask(f"\nUpdate issue tracker ticket {issue_key} with PR URL?", default=True)

    if not should_update:
        return

    try:
        # Get field mappings from config
        field_mappings = config.jira.field_mappings if config else None

        client = JiraClient()

        # Get current PR URLs from JIRA
        current_pr_urls = client.get_ticket_pr_links(issue_key, field_mappings=field_mappings)

        # Merge new PR URL with existing ones (handles duplicates, whitespace, and list formats)
        updated_pr_urls = merge_pr_urls(current_pr_urls, pr_url)

        # Resolve field ID from field_mappings
        git_pr_field = None
        if field_mappings:
            git_pr_field = field_mappings.get("git_pull_request", {}).get("id")

        # If not found in cached mappings, discover editable fields dynamically
        if not git_pr_field:
            console.print(f"[dim]Git Pull Request field not in cache, discovering editable fields...[/dim]")
            try:
                from devflow.jira.field_mapper import JiraFieldMapper

                field_mapper = JiraFieldMapper(client, field_mappings)
                editable_mappings = field_mapper.discover_editable_fields(issue_key)

                if "git_pull_request" in editable_mappings:
                    git_pr_field = editable_mappings["git_pull_request"]["id"]
                    console.print(f"[dim]✓ Found Git Pull Request field: {git_pr_field}[/dim]")
                else:
                    console.print(f"[yellow]⚠[/yellow] Git Pull Request field not available for this ticket")
                    console.print(f"[dim]You can add the PR URL manually in JIRA[/dim]")
                    return
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Could not discover Git Pull Request field: {e}")
                console.print(f"[dim]You can add the PR URL manually in JIRA[/dim]")
                return

        # Update issue tracker ticket
        try:
            client.update_ticket_field(issue_key, git_pr_field, updated_pr_urls)
            console.print(f"[green]✓[/green] Updated JIRA Git Pull Request field")
        except Exception as update_error:
            console.print(f"[yellow]⚠[/yellow] Failed to update issue tracker ticket: {update_error}")

    except RuntimeError as e:
        console.print(f"[yellow]⚠[/yellow] JIRA API error: {e}")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Failed to update JIRA: {e}")


def _cleanup_temp_directory(temp_dir: Optional[str]) -> None:
    """Clean up a temporary directory.

    Args:
        temp_dir: Path to temporary directory (can be None)
    """
    import shutil
    from pathlib import Path

    if not temp_dir:
        return

    try:
        if Path(temp_dir).exists():
            console.print(f"[dim]Cleaning up temporary directory: {temp_dir}[/dim]")
            shutil.rmtree(temp_dir)
            console.print(f"[green]✓[/green] Temporary directory removed")
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Could not remove temporary directory: {e}")
        console.print(f"[dim]You may need to manually delete: {temp_dir}[/dim]")
