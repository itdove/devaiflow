"""Implementation of 'daf rebuild-index' command."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from devflow.cli.utils import require_outside_claude
from devflow.utils.paths import get_cs_home

console = Console()


@require_outside_claude
def rebuild_index(dry_run: bool = False, force: bool = False) -> None:
    """Rebuild sessions.json index from session directories.

    This command scans all session directories and rebuilds the sessions.json
    index file from their metadata.json files. This is useful when:
    - The sessions.json file was corrupted or deleted
    - Sessions exist but don't appear in 'daf list'
    - The index got out of sync with actual session data

    Args:
        dry_run: Show what would be rebuilt without actually rebuilding
        force: Skip confirmation prompt
    """
    cs_home = get_cs_home()
    sessions_dir = cs_home / "sessions"
    sessions_file = cs_home / "sessions.json"

    if not sessions_dir.exists():
        console.print("[yellow]No sessions directory found[/yellow]")
        console.print(f"[dim]Expected at: {sessions_dir}[/dim]")
        return

    console.print("\n[bold]Scanning session directories...[/bold]\n")
    console.print(f"[dim]Sessions directory: {sessions_dir}[/dim]\n")

    rebuilt_sessions: Dict = {}
    skipped: List[str] = []
    errors: List[Tuple[str, str]] = []
    total_dirs = 0
    convs_from_metadata = 0

    # Scan all directories
    for session_dir in sessions_dir.iterdir():
        if not session_dir.is_dir():
            continue

        total_dirs += 1
        metadata_file = session_dir / "metadata.json"

        if not metadata_file.exists():
            skipped.append(session_dir.name)
            continue

        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)

            session_name = metadata.get('name', session_dir.name)

            # Get datetime fields, provide defaults if None
            created = metadata.get("created") or datetime.now().isoformat()
            started = metadata.get("started")
            last_active = metadata.get("last_active") or created

            # Get conversations from metadata (if stored)
            conversations = metadata.get("conversations", {})
            if conversations and len(conversations) > 0:
                convs_from_metadata += 1

            # Build session object for index
            session_obj = {
                "name": session_name,
                "goal": metadata.get("goal", ""),
                "session_type": metadata.get("session_type", "development"),
                "status": metadata.get("status", "created"),
                "created": created,
                "started": started,
                "last_active": last_active,
                "work_sessions": metadata.get("work_sessions", []),
                "time_tracking_state": metadata.get("time_tracking_state", "inactive"),
                "tags": metadata.get("tags", []),
                "related_sessions": metadata.get("related_sessions", []),
                "conversations": conversations,
                "working_directory": metadata.get("working_directory"),
                "workspace_name": metadata.get("workspace_name"),
                "issue_tracker": metadata.get("issue_tracker", "jira"),
                "issue_key": metadata.get("issue_key"),
                "issue_updated": metadata.get("issue_updated"),
                "issue_metadata": metadata.get("issue_metadata", {})
            }

            rebuilt_sessions[session_name] = session_obj

        except Exception as e:
            errors.append((session_dir.name, str(e)))

    console.print(f"[dim]Scanned {total_dirs} directories[/dim]\n")

    # Show summary
    console.print(f"[green]✓[/green] Found {len(rebuilt_sessions)} sessions with valid metadata")

    if convs_from_metadata > 0:
        console.print(f"[green]✓[/green] Loaded conversation data for {convs_from_metadata} sessions from metadata.json")

    if skipped:
        console.print(f"[yellow]⚠[/yellow]  Skipped {len(skipped)} directories without metadata.json")

    if errors:
        console.print(f"[red]✗[/red] Errors reading {len(errors)} session metadata files")

    console.print()

    # Show details if there are issues
    if skipped and len(skipped) <= 10:
        console.print("[yellow]Skipped directories:[/yellow]")
        for name in skipped:
            console.print(f"  [dim]• {name}[/dim]")
        console.print()
    elif skipped and len(skipped) > 10:
        console.print(f"[yellow]Skipped {len(skipped)} directories (first 10):[/yellow]")
        for name in skipped[:10]:
            console.print(f"  [dim]• {name}[/dim]")
        console.print(f"  [dim]... and {len(skipped) - 10} more[/dim]\n")

    if errors and len(errors) <= 5:
        console.print("[red]Errors:[/red]")
        for name, error in errors:
            console.print(f"  [dim]• {name}: {error}[/dim]")
        console.print()
    elif errors and len(errors) > 5:
        console.print(f"[red]Errors (first 5):[/red]")
        for name, error in errors[:5]:
            console.print(f"  [dim]• {name}: {error}[/dim]")
        console.print(f"  [dim]... and {len(errors) - 5} more[/dim]\n")

    if dry_run:
        console.print("[yellow]DRY RUN - No changes will be made[/yellow]\n")
        console.print("[bold]What would be rebuilt:[/bold]")
        console.print(f"  • sessions.json with {len(rebuilt_sessions)} sessions")
        if sessions_file.exists():
            console.print(f"  • Existing sessions.json would be backed up to sessions.json.backup")
        console.print(f"  • File location: {sessions_file}")
        return

    # Confirm rebuild
    if not force:
        console.print("[bold]This will:[/bold]")
        console.print(f"  • Rebuild sessions.json with {len(rebuilt_sessions)} sessions")
        if sessions_file.exists():
            console.print(f"  • Backup existing sessions.json to sessions.json.backup")
        console.print(f"  • File location: {sessions_file}")
        console.print()

        if not Confirm.ask("[yellow]Proceed with rebuild?[/yellow]", default=False):
            console.print("[dim]Cancelled[/dim]")
            return

    # Backup existing sessions.json if it exists and try to preserve conversations
    old_conversations: Dict = {}
    if sessions_file.exists():
        backup_file = sessions_file.with_suffix('.json.backup')
        console.print(f"\n[cyan]Backing up existing sessions.json...[/cyan]")

        # Try to preserve conversation data from existing file
        try:
            with open(sessions_file) as f:
                old_data = json.load(f)
            # Extract conversation data from old sessions
            for name, session in old_data.get('sessions', {}).items():
                convs = session.get('conversations', {})
                if convs and len(convs) > 0:
                    old_conversations[name] = convs
            if old_conversations:
                console.print(f"[dim]Found conversation data for {len(old_conversations)} sessions[/dim]")
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow]  Could not preserve conversations: {e}")

        sessions_file.rename(backup_file)
        console.print(f"[green]✓[/green] Backup created: {backup_file}\n")

    # Merge preserved conversation data back into rebuilt sessions
    if old_conversations:
        console.print(f"[cyan]Merging conversation data from backup...[/cyan]")
        merged = 0
        migrated = 0
        for name, convs in old_conversations.items():
            if name in rebuilt_sessions:
                # Migrate old conversation format if needed
                migrated_convs = {}
                for repo_key, conv_data in convs.items():
                    # Old format: conversations[repo] = ConversationContext
                    # New format: conversations[repo] = Conversation{active_session, archived_sessions}

                    if isinstance(conv_data, dict):
                        # Check if already in new format
                        if 'active_session' in conv_data:
                            migrated_convs[repo_key] = conv_data
                        else:
                            # Migrate from old format
                            # Rename claude_session_id -> ai_agent_session_id if present
                            if 'claude_session_id' in conv_data:
                                conv_data['ai_agent_session_id'] = conv_data.pop('claude_session_id')
                                migrated += 1

                            # Wrap in new Conversation structure
                            migrated_convs[repo_key] = {
                                'active_session': conv_data,
                                'archived_sessions': []
                            }
                    else:
                        # Unexpected format, skip
                        continue

                rebuilt_sessions[name]['conversations'] = migrated_convs
                merged += 1

        console.print(f"[green]✓[/green] Merged {merged} additional conversations from backup")
        if migrated > 0:
            console.print(f"[dim]Migrated {migrated} conversations from old format[/dim]")
        console.print()

        total_with_convs = sum(1 for s in rebuilt_sessions.values() if s.get('conversations') and len(s['conversations']) > 0)
        console.print(f"[bold]Total sessions with conversations: {total_with_convs}[/bold]")
        console.print(f"  [dim]• From metadata.json: {convs_from_metadata}[/dim]")
        console.print(f"  [dim]• From backup merge: {merged}[/dim]")
        console.print()

    # Create index structure
    index = {"sessions": rebuilt_sessions}

    # Write new sessions.json
    console.print("[cyan]Writing new sessions.json...[/cyan]")
    with open(sessions_file, 'w') as f:
        json.dump(index, f, indent=2, default=str)

    console.print(f"[green]✓[/green] Rebuilt sessions.json with {len(rebuilt_sessions)} sessions\n")

    console.print("[bold]Next steps:[/bold]")
    console.print("  • Run 'daf list' to verify all sessions are visible")
    console.print(f"  • If needed, restore from backup: {sessions_file.with_suffix('.json.backup')}")
