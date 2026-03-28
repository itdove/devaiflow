"""Implementation of 'daf import' command."""

from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from devflow.cli.utils import require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.export.manager import ExportManager

console = Console()


@require_outside_claude
def import_sessions(
    export_file: str,
    merge: bool = True,
    force: bool = False,
) -> None:
    """Import sessions from an export file.

    Args:
        export_file: Path to export file
        merge: If True, merge with existing sessions
        force: Skip confirmation prompt
    """
    export_path = Path(export_file)

    if not export_path.exists():
        console.print(f"[red]✗[/red] Export file not found: {export_path}")
        return

    config_loader = ConfigLoader()
    export_manager = ExportManager(config_loader)

    # Peek at export file to show what will be imported
    try:
        peek_data = export_manager.peek_export_file(export_path)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to read export file: {e}")
        return

    session_count = peek_data["session_count"]
    session_keys = peek_data["session_keys"]

    # Check for conflicts with existing sessions
    existing_sessions = config_loader.load_sessions()
    conflicting_keys = [key for key in session_keys if key in existing_sessions.sessions]

    # Display export file contents
    console.print()
    console.print("[bold]Export file contains:[/bold]")
    console.print(f"  Sessions: [cyan]{session_count}[/cyan]")
    console.print(f"  Keys: [cyan]{', '.join(session_keys)}[/cyan]")
    console.print()

    # Display conflict information
    if conflicting_keys:
        console.print(f"[yellow]Existing sessions found:[/yellow] {', '.join(conflicting_keys)}")
        if merge:
            console.print("[dim]These will be skipped (existing sessions preserved)[/dim]")
        else:
            console.print("[bold red]These will be OVERWRITTEN[/bold red]")
        console.print()

    # Confirm import operation
    if not force:
        if merge:
            if conflicting_keys:
                message = "Proceed with import? (existing sessions will be preserved)"
            else:
                message = "Proceed with import?"
        else:
            if conflicting_keys:
                message = "[yellow]WARNING:[/yellow] Proceed with import? (conflicting sessions will be OVERWRITTEN)"
            else:
                message = "Proceed with import?"

        if not Confirm.ask(message):
            console.print("[dim]Import cancelled[/dim]")
            return

    console.print("[cyan]Importing sessions...[/cyan]")

    try:
        imported_keys = export_manager.import_sessions(export_path, merge=merge)

        console.print(f"[green]✓[/green] Import completed successfully")
        console.print(f"Imported {len(imported_keys)} session(s)")

        if imported_keys:
            console.print("\nImported sessions:")
            for key in imported_keys:
                console.print(f"  - {key}")

        if merge:
            console.print("\n[dim]Merged with existing sessions (duplicates skipped)[/dim]")
        else:
            console.print("\n[dim]Conflicting sessions replaced[/dim]")

        # Check if imported sessions belong to any features (experimental)
        _check_and_integrate_into_features(imported_keys, config_loader, force)

        # Remind user about branch sync on open
        if imported_keys:
            console.print(f"\n[cyan]→ Next: Open the session to sync git branch[/cyan]")
            console.print(f"  daf open {imported_keys[0]}")
            console.print(f"[dim]  (Branch will be automatically fetched from remote)[/dim]")

    except Exception as e:
        console.print(f"[red]✗[/red] Import failed: {e}")
        raise


def _check_and_integrate_into_features(
    imported_keys: list,
    config_loader: ConfigLoader,
    force: bool = False,
) -> None:
    """Check if imported sessions belong to features and offer to integrate them.

    For team collaboration: When a teammate completes a session that's tracked
    in your feature's external_sessions, this integrates it into the feature.

    Args:
        imported_keys: List of imported session keys
        config_loader: ConfigLoader instance
        force: Skip confirmation prompts
    """
    try:
        from devflow.orchestration.feature import FeatureManager
        from devflow.session.manager import SessionManager

        session_manager = SessionManager(config_loader)
        feature_manager = FeatureManager(
            config_loader=config_loader,
            session_manager=session_manager,
        )

        # Get all features
        features = feature_manager.list_features()
        if not features:
            return

        # Check each imported session against features
        for issue_key in imported_keys:
            for feature in features:
                # Check if this issue_key is in external_sessions
                external_keys = [ext['key'] for ext in feature.external_sessions]
                if issue_key not in external_keys:
                    continue

                # Found a match!
                console.print(f"\n[bold yellow]⚠ Feature Integration Detected[/bold yellow]")
                console.print(f"Feature: [cyan]{feature.name}[/cyan]")
                console.print(f"Session: [cyan]{issue_key}[/cyan]")
                console.print(f"Status: This session is tracked as an external dependency\n")

                console.print("[dim]When you import a teammate's session, you can:[/dim]")
                console.print("  1. Add it to the feature (moves from external → your sessions)")
                console.print("  2. Mark it as completed (unblocks dependent sessions)")
                console.print("  3. Keep workflow progress intact")
                console.print()

                # Ask user if they want to integrate
                if not force:
                    if not Confirm.ask(f"Add {issue_key} to feature '{feature.name}'?", default=True):
                        console.print("[dim]Skipped feature integration[/dim]")
                        continue

                # Find the external session data
                external_session = None
                for ext in feature.external_sessions:
                    if ext['key'] == issue_key:
                        external_session = ext
                        break

                if not external_session:
                    continue

                # Determine actual session status
                # 1. Check imported session's status
                imported_session = session_manager.get_session(issue_key)
                actual_status = "completed"  # Default assumption

                if imported_session:
                    session_status = imported_session.status
                    # Map session status to feature status
                    if session_status in ["completed", "merged"]:
                        actual_status = "completed"
                    elif session_status in ["paused", "failed"]:
                        actual_status = "paused"
                    elif session_status in ["running", "active"]:
                        actual_status = "running"
                    else:
                        actual_status = "pending"

                    console.print(f"[dim]Session status: {session_status} → Feature status: {actual_status}[/dim]")

                # 2. Optionally check issue tracker for real status
                try:
                    from devflow.issue_tracker.factory import create_issue_tracker_client
                    from devflow.utils.backend_detection import detect_backend_from_key

                    config = config_loader.load_config()
                    backend = detect_backend_from_key(issue_key, config)
                    issue_tracker_client = create_issue_tracker_client(backend=backend)

                    ticket = issue_tracker_client.get_ticket(issue_key)
                    if ticket:
                        issue_status = ticket.get('status', '').lower()
                        console.print(f"[dim]Issue tracker status: {issue_status}[/dim]")

                        # Override with issue tracker status if done/closed
                        if issue_status in ['done', 'closed', 'resolved', 'merged']:
                            actual_status = "completed"
                            console.print(f"[dim]Using issue tracker status: completed[/dim]")
                except Exception:
                    # Issue tracker check is optional - continue with session status
                    pass

                # Add to feature sessions
                feature.sessions.append(issue_key)
                feature.session_statuses[issue_key] = actual_status

                # Add blocking relationships to metadata
                if not hasattr(feature, 'metadata') or not feature.metadata:
                    feature.metadata = {}
                if 'blocking_relationships' not in feature.metadata:
                    feature.metadata['blocking_relationships'] = {}

                feature.metadata['blocking_relationships'][issue_key] = {
                    'blocks': external_session.get('blocks', []),
                    'blocked_by': external_session.get('blocked_by', []),
                }

                # Remove from external_sessions
                feature.external_sessions = [
                    ext for ext in feature.external_sessions if ext['key'] != issue_key
                ]

                # Update feature
                feature_manager.update_feature(feature)

                console.print(f"[green]✓[/green] Added {issue_key} to feature '{feature.name}'")
                console.print(f"[green]✓[/green] Status: {actual_status}")
                console.print(f"[green]✓[/green] Removed from external dependencies")

                # Check if this unblocked any sessions (only if imported session is completed)
                if actual_status == "completed":
                    unblocked_sessions = []
                    for session_key in feature.sessions:
                        if feature.session_statuses.get(session_key) in ['pending', 'paused']:
                            if not feature.is_session_blocked(session_key):
                                unblocked_sessions.append(session_key)

                    if unblocked_sessions:
                        console.print(f"\n[bold green]🎉 Unblocked {len(unblocked_sessions)} session(s):[/bold green]")
                        for session_key in unblocked_sessions:
                            console.print(f"  • {session_key}")
                        console.print(f"\n[cyan]Resume feature with:[/cyan] daf -e feature resume {feature.name}")
                else:
                    console.print(f"\n[yellow]Note:[/yellow] Session is {actual_status}, not completed yet")
                    console.print(f"[dim]Dependent sessions remain blocked until completion[/dim]")

    except ImportError:
        # Feature orchestration not available (experimental)
        pass
    except Exception as e:
        # Don't fail import if feature integration fails
        console.print(f"[yellow]Warning:[/yellow] Could not integrate into feature: {e}")
