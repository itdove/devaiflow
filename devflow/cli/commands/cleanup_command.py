"""Implementation of 'daf cleanup-conversation' command."""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.utils.paths import get_cs_home
from devflow.utils.time_parser import parse_duration

console = Console()


@require_outside_claude
def cleanup_conversation(
    identifier: Optional[str] = None,
    older_than: Optional[str] = None,
    keep_last: Optional[int] = None,
    dry_run: bool = False,
    force: bool = False,
    list_backups: bool = False,
    restore_backup: Optional[str] = None,
    latest: bool = False,
) -> None:
    """Clean up Claude Code conversation history to reduce context size.

    Args:
        identifier: Session group name or issue tracker key (defaults to current session from env)
        older_than: Remove messages older than duration (e.g., "2h", "1d", "30m")
        keep_last: Keep only the last N messages
        dry_run: Show what would be removed without actually removing
        force: Skip confirmation prompt
        list_backups: List available backups for this session
        restore_backup: Restore from a specific backup (timestamp)
        latest: If True, use the most recently active session
    """
    config_loader = ConfigLoader()
    session_manager = SessionManager(config_loader)

    # Handle --latest flag
    if latest:
        sessions = session_manager.list_sessions()
        if not sessions:
            console.print("[red]No sessions found[/red]")
            return
        # Get most recent session
        most_recent = max(sessions, key=lambda s: s.last_active or s.created)
        identifier = most_recent.name
        issue_display = f" ({most_recent.issue_key})" if most_recent.issue_key else ""
        console.print(f"[dim]Using most recent session: {identifier}{issue_display}[/dim]\n")

    # Determine which session to cleanup
    if not identifier:
        console.print("[red]Error: Session name or issue key required[/red]")
        console.print("[dim]Usage: daf cleanup-conversation <NAME-or-JIRA-KEY> --older-than 8h[/dim]")
        console.print("[dim]Example: daf cleanup-conversation PROJ-12345 --older-than 8h[/dim]")
        console.print("[dim]Or use: daf cleanup-conversation --latest --older-than 8h[/dim]")
        return

    # Get session by identifier (handles multi-conversation sessions)
    sessions = session_manager.index.get_sessions(identifier)
    if not sessions:
        console.print(f"[red]Error: Session '{identifier}' not found[/red]")
        return

    # If multiple sessions, use the most recently active one
    if len(sessions) > 1:
        # Sort by last_active (most recent first)
        sessions.sort(key=lambda s: s.last_active or s.created, reverse=True)
        session = sessions[0]
        console.print(f"[yellow]Multiple sessions found for '{identifier}', using most recent:[/yellow]")
        console.print(f"  Working directory: {session.working_directory}")
        console.print()
    else:
        session = sessions[0]

    # Get Claude session ID from active conversation (handles multi-conversation sessions)
    # First try the active conversation, then fall back to deprecated field
    ai_agent_session_id = None
    if session.conversations:
        # Get the active conversation's Claude session ID
        active_conv = session.active_conversation
        if active_conv:
            ai_agent_session_id = active_conv.ai_agent_session_id

    if not ai_agent_session_id:
        console.print(f"[red]Error: Session '{identifier}' has no Claude session ID[/red]")
        console.print("[dim]This session has not been opened yet. Run 'daf open {identifier}' first.[/dim]")
        return

    # Handle list_backups mode
    if list_backups:
        _list_backups(ai_agent_session_id, session)
        return

    # Handle restore_backup mode
    if restore_backup:
        _restore_backup(ai_agent_session_id, restore_backup, session)
        return

    # Validate parameters
    if not older_than and not keep_last:
        console.print("[red]Error: Must specify either --older-than or --keep-last[/red]")
        console.print("[dim]Examples:[/dim]")
        console.print("[dim]  daf cleanup-conversation --older-than 2h[/dim]")
        console.print("[dim]  daf cleanup-conversation --keep-last 50[/dim]")
        return

    if older_than and keep_last:
        console.print("[red]Error: Cannot use both --older-than and --keep-last[/red]")
        return

    # Find conversation file
    conversation_file = _find_conversation_file(ai_agent_session_id)
    if not conversation_file:
        console.print(f"[red]Error: Conversation file not found for session {ai_agent_session_id}[/red]")
        console.print(f"[dim]Expected in: ~/.claude/projects/*/[/dim]")
        return

    # Show session info
    if session:
        console.print(f"\n[bold]Session:[/bold] {session.name}")
        if session.issue_key:
            console.print(f"[bold]JIRA:[/bold] {session.issue_key}")
        console.print(f"[bold]Goal:[/bold] {session.goal}")
    console.print(f"[bold]Claude Session ID:[/bold] {ai_agent_session_id}")
    console.print(f"[bold]Conversation file:[/bold] {conversation_file}")

    # Create backup directory for this session
    backup_dir = get_cs_home() / "backups" / ai_agent_session_id
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Backup conversation file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_file = backup_dir / f"{timestamp}.jsonl"

    if not dry_run:
        shutil.copy2(conversation_file, backup_file)
        console.print(f"[green]✓[/green] Created backup: {backup_file.relative_to(Path.home())}")

        # Cleanup old backups (keep last 5)
        _cleanup_old_backups(backup_dir, keep_count=5)

    # Read conversation
    messages = []
    try:
        with open(conversation_file, "r") as f:
            for line in f:
                if line.strip():
                    messages.append(json.loads(line))
    except Exception as e:
        console.print(f"[red]Error reading conversation file: {e}[/red]")
        return

    total_messages = len(messages)
    console.print(f"\n[bold]Total messages:[/bold] {total_messages}")

    # Determine which messages to keep
    if older_than:
        # Parse duration and calculate cutoff time
        try:
            duration_seconds = parse_duration(older_than)
            cutoff_time = datetime.now() - timedelta(seconds=duration_seconds)
        except Exception as e:
            console.print(f"[red]Error parsing duration '{older_than}': {e}[/red]")
            console.print("[dim]Examples: 30m, 2h, 1d, 1w[/dim]")
            return

        # Filter messages by timestamp
        kept_messages = []
        removed_count = 0

        for msg in messages:
            msg_time = _extract_message_time(msg)
            if msg_time and msg_time < cutoff_time:
                removed_count += 1
            else:
                kept_messages.append(msg)

        console.print(
            f"[yellow]Removing {removed_count} messages older than {older_than}[/yellow]"
        )
        console.print(f"[green]Keeping {len(kept_messages)} messages[/green]")

    elif keep_last:
        # Keep only last N messages
        if keep_last >= total_messages:
            console.print(
                f"[yellow]Requested to keep {keep_last} messages, but only {total_messages} exist[/yellow]"
            )
            console.print("[green]No cleanup needed[/green]")
            return

        kept_messages = messages[-keep_last:]
        removed_count = total_messages - keep_last

        console.print(f"[yellow]Removing {removed_count} oldest messages[/yellow]")
        console.print(f"[green]Keeping last {len(kept_messages)} messages[/green]")

    # Calculate size reduction
    original_size = conversation_file.stat().st_size
    estimated_new_size = sum(len(json.dumps(msg)) + 1 for msg in kept_messages)
    size_reduction = original_size - estimated_new_size
    reduction_pct = (size_reduction / original_size * 100) if original_size > 0 else 0

    console.print(f"\n[bold]Size reduction:[/bold]")
    console.print(f"  Original: {_format_size(original_size)}")
    console.print(f"  New: {_format_size(estimated_new_size)}")
    console.print(f"  Reduced by: {_format_size(size_reduction)} ({reduction_pct:.1f}%)")

    if dry_run:
        console.print("\n[yellow]DRY RUN - No changes made[/yellow]")
        console.print(f"[dim]Backup file would be: {backup_file}[/dim]")
        return

    # Confirm before proceeding (unless force is used)
    if not force:
        console.print()
        if not Confirm.ask(
            f"[yellow]Proceed with cleanup?[/yellow]",
            default=False,
        ):
            console.print("[dim]Cancelled[/dim]")
            # Remove backup if we're not proceeding
            backup_file.unlink()
            return

    # Write cleaned conversation
    try:
        with open(conversation_file, "w") as f:
            for msg in kept_messages:
                f.write(json.dumps(msg) + "\n")

        console.print(f"\n[green]✓[/green] Conversation cleaned successfully")
        console.print(f"[green]✓[/green] Removed {removed_count} messages")
        console.print(f"[green]✓[/green] Reduced file size by {_format_size(size_reduction)}")
        console.print(f"\n[dim]Backup: {backup_file.relative_to(Path.home())}[/dim]")

        # Show backup summary
        _display_backup_summary(backup_dir)

        console.print()
        console.print("[green]Next step:[/green]")
        console.print(f"  daf open {session.name if session else identifier}")
        console.print()
        console.print("[dim]Claude Code will load the cleaned conversation with reduced context.[/dim]")

    except Exception as e:
        console.print(f"\n[red]Error writing cleaned conversation: {e}[/red]")
        console.print(f"[yellow]Restoring from backup...[/yellow]")
        shutil.copy2(backup_file, conversation_file)
        console.print("[green]✓[/green] Restored from backup")


def _find_session_by_claude_id(session_manager: SessionManager, claude_id: str):
    """Find a session by its Claude session ID.

    Args:
        session_manager: SessionManager instance
        claude_id: Claude session UUID

    Returns:
        Session if found, None otherwise
    """
    all_sessions = session_manager.list_sessions()
    for session in all_sessions:
        active_conv = session.active_conversation
        if active_conv and active_conv.ai_agent_session_id == claude_id:
            return session
    return None


def _find_conversation_file(ai_agent_session_id: str) -> Optional[Path]:
    """Find the conversation file for a Claude session.

    Args:
        ai_agent_session_id: Claude session UUID

    Returns:
        Path to conversation file if found, None otherwise
    """
    claude_projects = Path.home() / ".claude" / "projects"
    if not claude_projects.exists():
        return None

    # Search all project directories for the conversation file
    for project_dir in claude_projects.iterdir():
        if project_dir.is_dir():
            conv_file = project_dir / f"{ai_agent_session_id}.jsonl"
            if conv_file.exists():
                return conv_file

    return None


def _extract_message_time(message: dict) -> Optional[datetime]:
    """Extract timestamp from a message.

    Args:
        message: Message dict from conversation file

    Returns:
        datetime if found, None otherwise
    """
    # Try common timestamp fields
    timestamp_str = message.get("timestamp") or message.get("time") or message.get("created_at")

    if not timestamp_str:
        # Try nested snapshot timestamp
        if "snapshot" in message:
            timestamp_str = message["snapshot"].get("timestamp")

    if timestamp_str:
        try:
            # Handle ISO format timestamps
            if isinstance(timestamp_str, str):
                # Remove 'Z' and parse
                timestamp_str = timestamp_str.rstrip("Z")
                return datetime.fromisoformat(timestamp_str)
        except Exception:
            pass

    return None


def _format_size(bytes: int) -> str:
    """Format bytes as human-readable size.

    Args:
        bytes: Number of bytes

    Returns:
        Formatted string (e.g., "1.2 KB", "3.4 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"


def _cleanup_old_backups(backup_dir: Path, keep_count: int = 5) -> None:
    """Remove old backups, keeping only the most recent ones.

    Args:
        backup_dir: Directory containing backup files
        keep_count: Number of most recent backups to keep
    """
    try:
        # Get all backup files sorted by modification time (newest first)
        backups = sorted(
            backup_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        # Remove old backups beyond keep_count
        removed_count = 0
        removed_size = 0

        for old_backup in backups[keep_count:]:
            removed_size += old_backup.stat().st_size
            old_backup.unlink()
            removed_count += 1

        if removed_count > 0:
            console.print(
                f"[dim]Cleaned up {removed_count} old backup(s), "
                f"freed {_format_size(removed_size)}[/dim]"
            )

    except Exception as e:
        # Don't fail the main operation if backup cleanup fails
        console.print(f"[yellow]Warning: Failed to cleanup old backups: {e}[/yellow]")


def _display_backup_summary(backup_dir: Path) -> None:
    """Display summary of backups for this session.

    Args:
        backup_dir: Directory containing backup files
    """
    try:
        backups = list(backup_dir.glob("*.jsonl"))
        if not backups:
            return

        total_size = sum(b.stat().st_size for b in backups)

        console.print()
        console.print(f"[bold]Backup Summary:[/bold]")
        console.print(f"  Total backups: {len(backups)}")
        console.print(f"  Total size: {_format_size(total_size)}")
        console.print(f"  Location: {backup_dir.relative_to(Path.home())}")

    except Exception:
        # Silently ignore if we can't display the summary
        pass


def _list_backups(ai_agent_session_id: str, session) -> None:
    """List all available backups for a session.

    Args:
        ai_agent_session_id: Claude session UUID
        session: Session object
    """
    backup_dir = get_cs_home() / "backups" / ai_agent_session_id

    # Show session info
    console.print(f"\n[bold]Session:[/bold] {session.name}")
    if session.issue_key:
        console.print(f"[bold]JIRA:[/bold] {session.issue_key}")
    console.print(f"[bold]Claude Session ID:[/bold] {ai_agent_session_id}")
    console.print()

    if not backup_dir.exists():
        console.print("[yellow]No backups found for this session[/yellow]")
        console.print(f"[dim]Backup directory: {backup_dir.relative_to(Path.home())}[/dim]")
        return

    # Get all backup files sorted by modification time (newest first)
    backups = sorted(
        backup_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not backups:
        console.print("[yellow]No backups found for this session[/yellow]")
        console.print(f"[dim]Backup directory: {backup_dir.relative_to(Path.home())}[/dim]")
        return

    console.print(f"[bold]Available backups ({len(backups)}):[/bold]\n")

    total_size = 0
    for backup in backups:
        timestamp = backup.stem  # Extract timestamp from filename
        size = backup.stat().st_size
        total_size += size
        modified_time = datetime.fromtimestamp(backup.stat().st_mtime)

        # Parse timestamp to make it more readable
        try:
            dt = datetime.strptime(timestamp, "%Y%m%d-%H%M%S")
            readable_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            readable_time = timestamp

        console.print(f"  [cyan]{timestamp}[/cyan]")
        console.print(f"    Date: {readable_time}")
        console.print(f"    Size: {_format_size(size)}")
        console.print(f"    Modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print()

    console.print(f"[bold]Total:[/bold] {len(backups)} backups, {_format_size(total_size)}")
    console.print(f"[dim]Location: {backup_dir.relative_to(Path.home())}[/dim]")
    console.print()
    console.print("[bold]To restore a backup:[/bold]")
    console.print(f"  daf cleanup-conversation {session.name if session else ai_agent_session_id} --restore-backup <timestamp>")


def _restore_backup(ai_agent_session_id: str, timestamp: str, session) -> None:
    """Restore conversation from a specific backup.

    Args:
        ai_agent_session_id: Claude session UUID
        timestamp: Backup timestamp to restore
        session: Session object
    """
    # Check if running inside Claude Code
    if os.environ.get("AI_AGENT_SESSION_ID"):
        console.print("[red]Error: Cannot restore backup while Claude Code is active[/red]")
        console.print()
        console.print("[yellow]Why this fails:[/yellow]")
        console.print("  Claude Code caches the conversation in memory and will")
        console.print("  overwrite the restore when it exits.")
        console.print()
        console.print("[green]To restore backup:[/green]")
        console.print("  1. Exit Claude Code completely")
        console.print("  2. Run: daf cleanup-conversation <NAME-or-JIRA-KEY> --restore-backup <timestamp>")
        console.print("  3. Reopen Claude Code with: daf open <NAME-or-JIRA-KEY>")
        return

    backup_dir = get_cs_home() / "backups" / ai_agent_session_id
    backup_file = backup_dir / f"{timestamp}.jsonl"

    # Show session info
    console.print(f"\n[bold]Session:[/bold] {session.name}")
    if session.issue_key:
        console.print(f"[bold]JIRA:[/bold] {session.issue_key}")
    console.print(f"[bold]Claude Session ID:[/bold] {ai_agent_session_id}")
    console.print()

    if not backup_file.exists():
        console.print(f"[red]Error: Backup not found: {timestamp}[/red]")
        console.print()
        console.print("[dim]List available backups with:[/dim]")
        console.print(f"  daf cleanup-conversation {session.name if session else ai_agent_session_id} --list-backups")
        return

    # Find conversation file
    conversation_file = _find_conversation_file(ai_agent_session_id)
    if not conversation_file:
        console.print(f"[red]Error: Conversation file not found for session {ai_agent_session_id}[/red]")
        console.print(f"[dim]Expected in: ~/.claude/projects/*/[/dim]")
        return

    # Show backup info
    backup_size = backup_file.stat().st_size
    backup_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)

    console.print(f"[bold]Backup file:[/bold] {timestamp}.jsonl")
    console.print(f"[bold]Backup size:[/bold] {_format_size(backup_size)}")
    console.print(f"[bold]Created:[/bold] {backup_mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print()
    console.print(f"[bold]Current conversation:[/bold] {conversation_file}")

    # Create a backup of the current conversation before restoring
    current_backup_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    current_backup_file = backup_dir / f"{current_backup_timestamp}.jsonl"

    try:
        # Backup current conversation
        console.print(f"\n[cyan]Creating backup of current conversation...[/cyan]")
        shutil.copy2(conversation_file, current_backup_file)
        console.print(f"[green]✓[/green] Saved current conversation as: {current_backup_timestamp}.jsonl")

        # Confirm restore
        if not Confirm.ask(f"\n[yellow]Restore from backup {timestamp}?[/yellow]", default=False):
            console.print("[dim]Restore cancelled[/dim]")
            # Remove the backup we just created since we're not proceeding
            current_backup_file.unlink()
            return

        # Restore from backup
        console.print(f"\n[cyan]Restoring from backup...[/cyan]")
        shutil.copy2(backup_file, conversation_file)

        console.print(f"\n[green]✓[/green] Conversation restored from backup {timestamp}")
        console.print(f"[green]✓[/green] Previous conversation saved as: {current_backup_timestamp}.jsonl")
        console.print()
        console.print("[green]Next step:[/green]")
        console.print(f"  daf open {session.name if session else ai_agent_session_id}")
        console.print()
        console.print("[dim]Claude Code will load the restored conversation.[/dim]")

        # Cleanup old backups (keep last 5)
        _cleanup_old_backups(backup_dir, keep_count=5)

    except Exception as e:
        console.print(f"\n[red]Error restoring backup: {e}[/red]")
        # Try to restore from the backup we just created
        if current_backup_file.exists():
            console.print(f"[yellow]Restoring previous state...[/yellow]")
            try:
                shutil.copy2(current_backup_file, conversation_file)
                console.print("[green]✓[/green] Restored previous conversation")
            except Exception as restore_error:
                console.print(f"[red]Failed to restore previous state: {restore_error}[/red]")
