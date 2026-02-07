"""Unified signal handler for CLI commands that launch Claude sessions."""

import signal
import sys
from typing import Optional, TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from devflow.session.manager import SessionManager
    from devflow.session.models import Session
    from devflow.config.models import Config

console = Console()

# Global variables for signal handler cleanup
_cleanup_session: Optional['Session'] = None
_cleanup_session_manager: Optional['SessionManager'] = None
_cleanup_identifier: Optional[str] = None  # Can be session name or ID
_cleanup_config: Optional['Config'] = None
_cleanup_done: bool = False


def _log_error(message: str) -> None:
    """Log error message to stderr for debugging.

    Used by signal handlers to log cleanup steps. Logs go to stderr
    so they don't interfere with JSON output or regular console output.

    Args:
        message: Error/debug message to log
    """
    import sys
    print(f"[DEBUG] {message}", file=sys.stderr, flush=True)


def _cleanup_on_signal(signum, frame):
    """Handle signals by performing cleanup before exit.

    This is the unified signal handler used by all CLI commands that launch Claude sessions.
    Handles cleanup for:
    - Regular sessions (daf open, daf new)
    - Ticket creation sessions (daf jira new)
    - Investigation sessions (daf investigate)

    Cleanup steps:
    1. Update session status to "paused"
    2. Handle session renaming (for ticket_creation sessions)
    3. End work session
    4. Save conversation files
    5. Clean up temporary directories
    6. Prompt for session completion
    """
    global _cleanup_done

    console.print(f"\n[yellow]Received signal {signum}, cleaning up...[/yellow]")

    if _cleanup_session and _cleanup_session_manager and _cleanup_identifier:
        try:
            console.print(f"[green]✓[/green] Claude session completed")

            # Reload index from disk before checking for rename
            # This is critical because the child process (Claude) may have renamed the session
            # and we need to see the latest state from disk, not our stale in-memory index
            _cleanup_session_manager.index = _cleanup_session_manager.config_loader.load_sessions()

            # Check if session was renamed during execution (ticket_creation sessions can be renamed)
            current_session = _cleanup_session_manager.get_session(_cleanup_identifier)
            actual_identifier = _cleanup_identifier

            if not current_session:
                # Session not found with original name - it was likely renamed
                console.print(f"[dim]Detecting renamed session...[/dim]")
                all_sessions = _cleanup_session_manager.list_sessions()
                # Match by Claude session ID which doesn't change during rename
                cleanup_claude_id = (_cleanup_session.active_conversation.ai_agent_session_id
                                    if _cleanup_session.active_conversation else None)
                for s in all_sessions:
                    s_claude_id = s.active_conversation.ai_agent_session_id if s.active_conversation else None
                    if (s_claude_id and cleanup_claude_id and
                        s_claude_id == cleanup_claude_id):
                        # Check for ticket_creation sessions (which can be renamed)
                        if (s.session_type == "ticket_creation" and
                            s.name.startswith("creation-")):
                            actual_identifier = s.name
                            current_session = s
                            console.print(f"[dim]Session was renamed to: {actual_identifier}[/dim]")
                            break
                        # Also handle regular sessions that might have been renamed
                        actual_identifier = s.name
                        current_session = s
                        console.print(f"[dim]Session was renamed to: {actual_identifier}[/dim]")
                        break

            # If we found the session (renamed or not), update its status
            session_to_update = current_session if current_session else _cleanup_session

            # Update session status to paused
            # CRITICAL: Explicitly set status before calling update_session
            session_to_update.status = "paused"

            # Log the update for debugging
            _log_error(f"Signal handler: Updating session {session_to_update.name} to paused status")

            # Update session (this now includes explicit fsync to prevent data loss)
            _cleanup_session_manager.update_session(session_to_update)

            # Verify the update was persisted (for debugging intermittent issues)
            _log_error(f"Signal handler: Session update completed for {session_to_update.name}")

            # End work session
            try:
                _cleanup_session_manager.end_work_session(actual_identifier)
            except ValueError as e:
                # Session name or ID mismatch - log but continue cleanup
                console.print(f"[yellow]⚠[/yellow] Could not end work session: {e}")

            console.print(f"[dim]Resume anytime with: daf open {session_to_update.name}[/dim]")

            # Save conversation file to stable location before cleaning up temp directory
            if session_to_update.active_conversation and session_to_update.active_conversation.temp_directory:
                from devflow.cli.commands.open_command import _copy_conversation_from_temp
                _copy_conversation_from_temp(session_to_update, session_to_update.active_conversation.temp_directory)

            # Clean up temporary directory if present
            if session_to_update.active_conversation and session_to_update.active_conversation.temp_directory:
                try:
                    from devflow.utils.temp_directory import cleanup_temp_directory
                    cleanup_temp_directory(session_to_update.active_conversation.temp_directory)
                except ImportError:
                    # Fallback for older code that might not have temp_directory module
                    from devflow.cli.commands.open_command import _cleanup_temp_directory_on_exit
                    _cleanup_temp_directory_on_exit(session_to_update.active_conversation.temp_directory)

            # Call the complete prompt
            # IMPORTANT: Do NOT wrap this in a broad exception handler
            # KeyboardInterrupt and EOFError should propagate to allow proper cleanup
            # Any exceptions from _prompt_for_complete_on_exit are already handled inside that function
            from devflow.cli.commands.open_command import _prompt_for_complete_on_exit
            _prompt_for_complete_on_exit(session_to_update, _cleanup_config)

            # Mark cleanup as done so finally block doesn't repeat it
            _cleanup_done = True

        except Exception as e:
            console.print(f"[red]Error during cleanup: {e}[/red]")
            import traceback
            error_details = traceback.format_exc()
            console.print(f"[dim]{error_details}[/dim]")
            _log_error(f"Signal handler error: {e}\n{error_details}")

    # Exit gracefully
    sys.exit(0)


def setup_signal_handlers(
    session: 'Session',
    session_manager: 'SessionManager',
    identifier: str,
    config: 'Config'
) -> None:
    """Set up signal handlers for graceful cleanup on interrupt.

    This should be called by CLI commands before launching Claude sessions.
    Registers signal handlers for SIGINT and SIGTERM to ensure proper cleanup.

    Args:
        session: The session object being worked on
        session_manager: SessionManager instance for session operations
        identifier: Session name or ID (used for session lookup)
        config: Configuration object for accessing settings
    """
    global _cleanup_session, _cleanup_session_manager, _cleanup_identifier, _cleanup_config, _cleanup_done

    _cleanup_session = session
    _cleanup_session_manager = session_manager
    _cleanup_identifier = identifier
    _cleanup_config = config
    _cleanup_done = False

    # Register signal handlers
    signal.signal(signal.SIGINT, _cleanup_on_signal)
    signal.signal(signal.SIGTERM, _cleanup_on_signal)


def is_cleanup_done() -> bool:
    """Check if cleanup has been performed.

    Returns:
        True if cleanup was already done, False otherwise
    """
    return _cleanup_done


def reset_cleanup_state() -> None:
    """Reset the cleanup state.

    This can be called after cleanup completes to reset global state.
    Useful for testing or when running multiple commands in sequence.
    """
    global _cleanup_session, _cleanup_session_manager, _cleanup_identifier, _cleanup_config, _cleanup_done

    _cleanup_session = None
    _cleanup_session_manager = None
    _cleanup_identifier = None
    _cleanup_config = None
    _cleanup_done = False
