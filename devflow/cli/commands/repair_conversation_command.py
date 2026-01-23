"""CLI command for repairing corrupted Claude Code conversation files."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.session.repair import (
    ConversationRepairError,
    detect_corruption,
    get_conversation_file_path,
    is_valid_uuid,
    repair_conversation_file,
    scan_all_conversations,
)

console = Console()


@require_outside_claude
def repair_conversation(
    identifier: Optional[str],
    conversation_id: Optional[int],
    max_size: int,
    check_all: bool,
    repair_all: bool,
    dry_run: bool,
    latest: bool = False,
) -> None:
    """Repair corrupted Claude Code conversation files.

    Args:
        identifier: Session name, issue key, or Claude session UUID
        conversation_id: Specific conversation ID to repair
        max_size: Maximum size for content truncation
        check_all: Check all sessions for corruption (dry run)
        repair_all: Repair all corrupted sessions found
        dry_run: Report issues without making changes
        latest: If True, use the most recently active session
    """
    config_loader = ConfigLoader()
    manager = SessionManager(config_loader)

    # Handle --check-all flag
    if check_all:
        console.print("\n[bold]Scanning all Claude Code conversations for corruption...[/bold]\n")

        corrupted_files = scan_all_conversations()

        if not corrupted_files:
            console.print("[green]✓[/green] No corrupted conversation files found")
            return

        console.print(f"[yellow]⚠[/yellow] Found {len(corrupted_files)} corrupted conversation(s):\n")

        table = Table(show_header=True, header_style="bold")
        table.add_column("UUID", style="cyan")
        table.add_column("Issues", style="yellow")
        table.add_column("Invalid Lines", style="red")
        table.add_column("Truncations Needed", style="yellow")

        for uuid, file_path, corruption_info in corrupted_files:
            table.add_row(
                uuid,
                "\n".join(corruption_info['issues']),
                str(len(corruption_info['invalid_lines'])),
                str(len(corruption_info['truncation_needed'])),
            )

        console.print(table)
        console.print()

        if repair_all:
            console.print(f"\nRepairing {len(corrupted_files)} corrupted conversation(s)...")
        else:
            console.print("\nUse --all to repair all corrupted conversations")

        return

    # Handle --all flag (repair all corrupted)
    if repair_all:
        console.print("\n[bold]Scanning for corrupted conversations...[/bold]\n")

        corrupted_files = scan_all_conversations()

        if not corrupted_files:
            console.print("[green]✓[/green] No corrupted conversation files found")
            return

        console.print(f"Found {len(corrupted_files)} corrupted conversation(s)")

        if not dry_run:
            if not Confirm.ask(f"Repair all {len(corrupted_files)} corrupted conversation(s)?", default=True):
                console.print("Cancelled")
                return

        console.print()

        for uuid, file_path, corruption_info in corrupted_files:
            console.print(f"[bold]Repairing {uuid}...[/bold]")

            try:
                result = repair_conversation_file(file_path, max_size=max_size, dry_run=dry_run)

                if result['success']:
                    if dry_run:
                        console.print(f"  [dim]Would repair {result['lines_repaired']} line(s)[/dim]")
                    else:
                        console.print(f"  [green]✓[/green] Repaired {result['lines_repaired']} line(s)")
                        if result['backup_path']:
                            console.print(f"  [dim]Backup: {result['backup_path'].name}[/dim]")
                else:
                    console.print(f"  [yellow]{result.get('message', 'No changes needed')}[/yellow]")

                if result.get('truncations'):
                    console.print(f"  [dim]Truncated {len(result['truncations'])} large content block(s)[/dim]")

            except ConversationRepairError as e:
                console.print(f"  [red]✗[/red] {e}")

            console.print()

        console.print("[green]✓[/green] Scan complete")
        return

    # Handle --latest flag
    if latest:
        sessions = manager.list_sessions()
        if not sessions:
            console.print("[red]No sessions found[/red]")
            return
        # Get most recent session
        most_recent = max(sessions, key=lambda s: s.last_active or s.created)
        identifier = most_recent.name
        issue_display = f" ({most_recent.issue_key})" if most_recent.issue_key else ""
        console.print(f"[dim]Using most recent session: {identifier}{issue_display}[/dim]\n")

    # Handle identifier-based repair
    if not identifier:
        console.print("[red]✗[/red] Please provide a session identifier, UUID, or use --check-all/--all/--latest")
        console.print("\nExamples:")
        console.print("  daf repair-conversation PROJ-60039")
        console.print("  daf repair-conversation --latest")
        console.print("  daf repair-conversation my-session")
        console.print("  daf repair-conversation f545206f-480f-4c2d-8823-c6643f0e693d")
        console.print("  daf repair-conversation --check-all")
        console.print("  daf repair-conversation --all")
        return

    # Try to find session by name or issue key first
    session = manager.get_session(identifier)

    if session:
        # Found session - repair its conversation(s)
        console.print(f"\n[bold]Found session:[/bold] {session.name}")
        if session.issue_key:
            console.print(f"[dim]JIRA: {session.issue_key}[/dim]")

        if not session.conversations:
            console.print("[yellow]⚠[/yellow] Session has no conversations")
            return

        console.print(f"[dim]{len(session.conversations)} conversation(s) found[/dim]\n")

        # If conversation_id specified, repair only that one
        if conversation_id:
            # Flatten all conversations into a single list
            all_conversations = []
            for working_dir, conversation in session.conversations.items():
                # Process all sessions (active + archived) in this Conversation
                for conv in conversation.get_all_sessions():
                    all_conversations.append(conv)

            if conversation_id < 1 or conversation_id > len(all_conversations):
                console.print(f"[red]✗[/red] Conversation #{conversation_id} not found")
                console.print(f"\nAvailable conversations:")
                for i, conv in enumerate(all_conversations, 1):
                    status = " (archived)" if conv.archived else ""
                    console.print(f"  #{i}: {conv.project_path}{status}")
                return

            conversation = all_conversations[conversation_id - 1]
            _repair_single_conversation(conversation.ai_agent_session_id, max_size, dry_run)

        else:
            # Repair all conversations in session
            conv_number = 1
            for working_dir, conversation in session.conversations.items():
                # Process all sessions (active + archived) in this Conversation
                for conv in conversation.get_all_sessions():
                    status = " (archived)" if conv.archived else ""
                    console.print(f"[bold]Conversation #{conv_number}:[/bold] {conv.ai_agent_session_id}{status}")
                    console.print(f"[dim]Path: {conv.project_path}[/dim]")

                    _repair_single_conversation(conv.ai_agent_session_id, max_size, dry_run)
                    console.print()
                    conv_number += 1

            console.print("[green]✓[/green] All conversations processed")

    else:
        # Not found as session - check if it's a direct UUID
        if is_valid_uuid(identifier):
            console.print(f"\n[dim]Session not found in index, treating as direct UUID[/dim]\n")
            _repair_single_conversation(identifier, max_size, dry_run)
        else:
            console.print(f"[red]✗[/red] Session '{identifier}' not found and not a valid UUID")
            console.print("\nTry:")
            console.print("  - Checking the session name or issue key")
            console.print("  - Using 'daf list' to see available sessions")
            console.print("  - Providing a valid Claude session UUID")


def _repair_single_conversation(ai_agent_session_id: str, max_size: int, dry_run: bool) -> None:
    """Repair a single conversation by UUID.

    Args:
        ai_agent_session_id: Claude Code session UUID
        max_size: Maximum size for truncation
        dry_run: Report issues without making changes
    """
    # Find conversation file
    conv_file = get_conversation_file_path(ai_agent_session_id)

    if not conv_file:
        console.print(f"[red]✗[/red] Conversation file not found for UUID: {ai_agent_session_id}")
        return

    console.print(f"[dim]File: {conv_file}[/dim]")

    # Check for corruption
    corruption_info = detect_corruption(conv_file)

    if not corruption_info['is_corrupt']:
        console.print("[green]✓[/green] No corruption detected")
        return

    # Display corruption details
    console.print(f"[yellow]⚠[/yellow] Corruption detected:")
    for issue in corruption_info['issues']:
        console.print(f"  - {issue}")

    if corruption_info['invalid_lines']:
        console.print(f"\n[bold]Invalid lines:[/bold]")
        for line_num, error in corruption_info['invalid_lines'][:5]:  # Show first 5
            console.print(f"  Line {line_num}: {error}")
        if len(corruption_info['invalid_lines']) > 5:
            console.print(f"  ... and {len(corruption_info['invalid_lines']) - 5} more")

    if corruption_info['truncation_needed']:
        console.print(f"\n[bold]Content requiring truncation:[/bold]")
        for line_num, size, content_type in corruption_info['truncation_needed'][:5]:
            console.print(f"  Line {line_num}: {content_type} ({size:,} chars)")
        if len(corruption_info['truncation_needed']) > 5:
            console.print(f"  ... and {len(corruption_info['truncation_needed']) - 5} more")

    console.print()

    # Repair the file
    if dry_run:
        console.print("[dim]Dry run - no changes made[/dim]")
        return

    try:
        result = repair_conversation_file(conv_file, max_size=max_size, dry_run=dry_run)

        if result['success']:
            console.print(f"[green]✓[/green] Repaired {result['lines_repaired']} line(s)")

            if result['backup_path']:
                console.print(f"[dim]Backup created: {result['backup_path']}[/dim]")

            if result['truncations']:
                console.print(f"[dim]Truncated {len(result['truncations'])} content block(s):[/dim]")
                for line_num, old_size, new_size in result['truncations'][:3]:
                    console.print(f"  Line {line_num}: {old_size:,} → {new_size:,} chars")
                if len(result['truncations']) > 3:
                    console.print(f"  ... and {len(result['truncations']) - 3} more")

            if result['errors_fixed']:
                console.print(f"[dim]Fixed {len(result['errors_fixed'])} JSON error(s)[/dim]")

            console.print(f"\n[bold]Validated {result['total_lines']} lines[/bold]")

        else:
            console.print(f"[yellow]{result.get('message', 'No changes needed')}[/yellow]")

    except ConversationRepairError as e:
        console.print(f"[red]✗[/red] Repair failed: {e}")
