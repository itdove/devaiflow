"""Common utility functions for CLI commands."""

import functools
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import click
import requests
from rich.console import Console
from rich.prompt import Confirm, IntPrompt

from devflow.config.models import Config, ConversationContext, Session
from devflow.jira import JiraClient
from devflow.session.manager import SessionManager

console = Console()


def check_outside_ai_session() -> None:
    """Check if running inside an AI agent session and exit with error if so.

    This function checks for the DEVFLOW_IN_SESSION environment variable and
    exits with a clear error message if the command is run inside an AI agent session.

    This prevents data integrity issues from:
    - Nested session creation
    - Concurrent metadata modifications
    - Session state corruption

    Use this function for commands that modify session state but may have
    read-only modes (like daf release --dry-run).

    Raises:
        SystemExit: If running inside an AI agent session (exits with code 1)
    """
    if os.environ.get("DEVFLOW_IN_SESSION"):
        console.print("[red]Error: Cannot run this command while inside an AI agent session[/red]")
        console.print()
        console.print("[yellow]Why this fails:[/yellow]")
        console.print("  Running this command inside an AI session would cause data integrity issues,")
        console.print("  including nested sessions, concurrent modifications, and lost work.")
        console.print()
        console.print("[cyan]Solution:[/cyan]")
        console.print("  1. Exit your AI agent (Claude Code, Cursor, etc.) first")
        console.print("  2. Run this command from a regular terminal")
        console.print()
        console.print("[dim]Commands safe to run inside AI sessions:[/dim]")
        console.print("  [dim]daf active, daf status, daf list, daf info, daf notes,[/dim]")
        console.print("  [dim]daf jira view, daf config show[/dim]")
        sys.exit(1)


def require_outside_claude(f):
    """Decorator to prevent command from running inside an AI agent session.

    This decorator checks for the DEVFLOW_IN_SESSION environment variable and
    exits with a clear error message if the command is run inside an AI agent session
    (Claude Code, Cursor, GitHub Copilot, Windsurf, etc.).

    This prevents data integrity issues from:
    - Nested session creation
    - Concurrent metadata modifications
    - Session state corruption

    Use this decorator on all commands that modify session state (daf new, daf open,
    daf complete, daf sync, etc.). Commands that are read-only or specifically designed
    to run inside AI sessions (daf active, daf status, daf list, daf info, daf notes,
    daf jira view, daf config show) should NOT use this decorator.

    For commands with read-only modes (like daf release --dry-run), use check_outside_ai_session()
    directly in the function body with conditional logic instead of this decorator.

    Args:
        f: The function to wrap

    Returns:
        Wrapped function that checks for DEVFLOW_IN_SESSION before executing

    Examples:
        >>> @require_outside_claude
        ... def create_new_session(name, goal):
        ...     # This will error if run inside an AI agent session
        ...     pass
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        check_outside_ai_session()
        return f(*args, **kwargs)
    return wrapper


def resolve_goal_input(goal_text: str) -> str:
    """Resolve goal input from plain text, file path, or URL.

    Supports four input modes:
    1. Plain text: "Some goal description"
    2. File path with prefix: "file:///path/to/file.md" or "file://~/docs/spec.txt"
    3. Bare file path: "/path/to/file.md" or "~/docs/spec.txt" or "requirements.md"
    4. URL: "https://example.com/requirements.md"

    Args:
        goal_text: The raw goal string which may be plain text, file path, or URL

    Returns:
        Resolved goal content as a string

    Raises:
        click.ClickException: If file path is provided but file is not found or URL fetch fails

    Examples:
        >>> resolve_goal_input("Simple goal text")
        'Simple goal text'
        >>> resolve_goal_input("file:///tmp/requirements.md")
        '# Requirements\\n\\nFeature XYZ...'
        >>> resolve_goal_input("/tmp/requirements.md")
        '# Requirements\\n\\nFeature XYZ...'
        >>> resolve_goal_input("https://docs.example.com/spec.txt")
        'Specification: ...'
    """
    if not goal_text:
        return goal_text

    # Check if it's a URL (http:// or https://)
    parsed = urlparse(goal_text)
    if parsed.scheme in ("http", "https"):
        return _fetch_goal_from_url(goal_text)

    # Check if it's a file path (file:// prefix)
    if goal_text.startswith("file://"):
        file_path = goal_text[7:]  # Remove "file://" prefix
        return _read_goal_from_file(file_path)

    # A path must be a single token (no whitespace) to be considered a file path
    # Multi-word text is always treated as plain text, regardless of special characters
    if " " in goal_text or "\t" in goal_text or "\n" in goal_text:
        # Contains whitespace, treat as plain text
        return goal_text

    # Try to detect if it's a bare file path (single token only)
    # Expand ~ to home directory for checking
    potential_path = Path(goal_text).expanduser()

    # Check if this looks like a file path and the file exists
    if potential_path.exists():
        if potential_path.is_file():
            # It's a valid file, read it
            return _read_goal_from_file(goal_text)
        else:
            # It's a directory, not a file - treat as error since user likely meant a file
            raise click.ClickException(f"Path is a directory, not a file: {goal_text}")

    # Check if it looks like a file path but doesn't exist
    # Heuristic: contains path separators or common file extensions
    looks_like_path = (
        "/" in goal_text or
        "\\" in goal_text or
        goal_text.startswith("~") or
        goal_text.startswith(".") or
        any(goal_text.endswith(ext) for ext in [".md", ".txt", ".doc", ".docx", ".pdf", ".json", ".yaml", ".yml"])
    )

    if looks_like_path:
        # Looks like a file path but file doesn't exist - raise error
        raise click.ClickException(f"File not found: {goal_text}")

    # Plain text - return as-is
    return goal_text


def _read_goal_from_file(file_path: str) -> str:
    """Read goal content from a local file.

    Args:
        file_path: Path to the file (may include ~ for home directory)

    Returns:
        File content as string

    Raises:
        click.ClickException: If file is not found or cannot be read
    """
    # Expand ~ to home directory
    expanded_path = Path(file_path).expanduser()

    # Check if file exists
    if not expanded_path.exists():
        raise click.ClickException(f"File not found: {file_path}")

    if not expanded_path.is_file():
        raise click.ClickException(f"Path is not a file: {file_path}")

    # Read file content with UTF-8 encoding
    try:
        content = expanded_path.read_text(encoding="utf-8")
        return content
    except UnicodeDecodeError:
        # Try with error handling for non-UTF-8 files
        try:
            content = expanded_path.read_text(encoding="utf-8", errors="replace")
            console_print(
                f"[yellow]⚠[/yellow] Warning: File contains non-UTF-8 characters (replaced with \ufffd)"
            )
            return content
        except Exception as e:
            raise click.ClickException(f"Failed to read file {file_path}: {e}")
    except Exception as e:
        raise click.ClickException(f"Failed to read file {file_path}: {e}")


def _fetch_goal_from_url(url: str) -> str:
    """Fetch goal content from a URL.

    Args:
        url: HTTP or HTTPS URL to fetch

    Returns:
        Response content as string

    Raises:
        click.ClickException: If URL fetch fails or times out
    """
    try:
        # Fetch URL with 10 second timeout
        response = requests.get(url, timeout=10)

        # Check for HTTP errors
        if response.status_code != 200:
            raise click.ClickException(
                f"Failed to fetch URL (HTTP {response.status_code}): {url}\n"
                f"Error: {response.reason}"
            )

        # Return text content with UTF-8 encoding
        return response.text

    except requests.exceptions.Timeout:
        raise click.ClickException(f"Timeout fetching URL (10 second limit): {url}")
    except requests.exceptions.RequestException as e:
        raise click.ClickException(f"Failed to fetch URL: {url}\nError: {e}")
    except Exception as e:
        raise click.ClickException(f"Unexpected error fetching URL: {url}\nError: {e}")


def console_print(*args, **kwargs) -> None:
    """Print to console only if not in JSON mode.

    This is a wrapper around rich.console.Console.print() that respects
    the --json flag. When --json is active, this function does nothing.

    Args:
        *args: Positional arguments passed to console.print()
        **kwargs: Keyword arguments passed to console.print()

    Examples:
        console_print("[green]Success![/green]")
        console_print("Error:", error_msg, style="red")
    """
    if not is_json_mode():
        console.print(*args, **kwargs)


def is_json_mode() -> bool:
    """Check if --json flag is active by looking at Click context.

    This can be called from anywhere in the call stack to determine
    if output should be JSON instead of Rich formatted text.

    Returns:
        True if --json flag is present, False otherwise
    """
    try:
        ctx = click.get_current_context()
        return ctx.obj.get('output_json', False) if ctx.obj else False
    except RuntimeError:
        # No context available (e.g., called outside of Click command)
        # Fall back to checking sys.argv
        return "--json" in sys.argv


def get_status_display(status: str) -> tuple[str, str]:
    """Get status display text and color.

    Returns the status value as-is with appropriate color.

    Args:
        status: Session status ("created", "in_progress", "paused", or "complete")

    Returns:
        Tuple of (display_text, color) for use in rich console output

    Examples:
        >>> text, color = get_status_display("in_progress")
        >>> console.print(f"[{color}]{text}[/{color}]")
    """
    color_map = {
        "created": "cyan",
        "in_progress": "yellow",
        "paused": "blue",
        "complete": "green"
    }
    return status, color_map.get(status, "white")


def get_session_with_prompt(
    session_manager: SessionManager,
    identifier: str,
    session_id: Optional[int] = None,
    error_if_not_found: bool = True,
) -> Optional[Session]:
    """Get a session by identifier.

    Smart lookup strategy:
    1. Try as session name
    2. Try as issue tracker key

    Args:
        session_manager: SessionManager instance
        identifier: Session name or issue key
        session_id: Deprecated parameter (ignored, kept for backward compatibility)
        error_if_not_found: If True, print error message when no session found

    Returns:
        Session object, or None if not found
    """
    session = session_manager.get_session(identifier)

    if not session:
        if error_if_not_found:
            console.print(f"[red]No session found for '{identifier}'[/red]")
            console.print(
                f"[dim]Use 'daf new --name {identifier} --goal \"...\"' to create a session[/dim]"
            )
        return None

    return session


def display_session_header(session: Session) -> None:
    """Display standard session metadata header.

    This is the common pattern used when opening/resuming sessions.

    Args:
        session: Session object to display
    """
    issue_display = f" ({session.issue_key})" if session.issue_key else ""
    console.print(
        f"\n[bold]📋 Session: {session.name}{issue_display}[/bold]"
    )
    console.print(f"📁 Working Directory: {session.working_directory}")
    # Use conversation-based API for project_path and branch
    active_conv = session.active_conversation
    if active_conv and active_conv.project_path:
        console.print(f"📂 Path: {active_conv.project_path}")
    if active_conv and active_conv.branch:
        console.print(f"🌿 Branch: {active_conv.branch}")
    status_text, status_color = get_status_display(session.status)
    console.print(f"📊 Status: [{status_color}]{status_text}[/{status_color}]")

    # Display time information
    total_seconds = session.total_time_seconds()
    if total_seconds > 0:
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        time_by_user = session.time_by_user()

        if len(time_by_user) > 1:
            # Multiple users - show breakdown
            console.print(f"⏱️  Time: {hours}h {minutes}m total")
            for user, user_seconds in sorted(time_by_user.items(), key=lambda x: x[1], reverse=True):
                u_hours = int(user_seconds // 3600)
                u_minutes = int((user_seconds % 3600) // 60)
                console.print(f"   └─ {user}: {u_hours}h {u_minutes}m")
        else:
            # Single user - simple display
            console.print(f"⏱️  Time: {hours}h {minutes}m")

    # Use conversation-based API for message_count and ai_agent_session_id
    message_count = session.active_conversation.message_count if session.active_conversation else 0
    console.print(f"💬 Messages: {message_count}")
    console.print(f"📅 Last active: {session.last_active.strftime('%Y-%m-%d %H:%M')}")
    active_conv = session.active_conversation
    if active_conv and active_conv.ai_agent_session_id:
        console.print(f"🆔 Claude Session ID: {active_conv.ai_agent_session_id}")


def get_session_with_delete_all_option(
    session_manager: SessionManager,
    identifier: str,
) -> tuple[Optional[Session], bool]:
    """Get a session by identifier.

    Special variant used by delete command (kept for backward compatibility).

    Args:
        session_manager: SessionManager instance
        identifier: Session name or issue key

    Returns:
        Tuple of (Session or None, delete_all_flag)
        - delete_all_flag is always False (no longer used since session groups removed)
    """
    session = session_manager.get_session(identifier)

    if not session:
        console.print(f"[red]No session found for '{identifier}'[/red]")
        return None, False

    return session, False


def add_jira_comment(issue_key: str, comment: str, timeout: int = 10, silent_success: bool = False) -> bool:
    """Add a comment to a issue tracker ticket.

    Common pattern for adding comments to issue tracker tickets with proper error handling.

    Args:
        issue_key: issue tracker key (e.g., "PROJ-12345")
        comment: Comment text to add
        timeout: Command timeout in seconds
        silent_success: If True, don't print success message (caller will print custom message)

    Returns:
        True if comment was added successfully, False otherwise
    """
    from devflow.jira.exceptions import JiraError

    try:
        jira_client = JiraClient(timeout=timeout)
        jira_client.add_comment(issue_key, comment)

        if not silent_success:
            console.print(f"[green]✓[/green] Comment added to issue tracker ticket {issue_key}")
        return True

    except JiraError as e:
        console.print(f"[yellow]⚠[/yellow] Failed to add JIRA comment: {e}")
        return False
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] Failed to add JIRA comment: {e}")
        return False


def get_active_conversation(session_manager: SessionManager) -> Optional[Tuple[Session, ConversationContext, str]]:
    """Detect currently active AI agent conversation.

    Checks the AI_AGENT_SESSION_ID environment variable to find the active conversation.

    Args:
        session_manager: SessionManager instance

    Returns:
        Tuple of (Session, ConversationContext, working_directory) if active conversation found,
        None otherwise
    """
    # Get AI agent session ID from environment variable
    agent_session_id = os.environ.get("AI_AGENT_SESSION_ID")
    if not agent_session_id:
        return None

    # Search through all sessions to find matching conversation
    for session in session_manager.index.sessions.values():
        for working_dir, conversation in session.conversations.items():
            # Check all sessions (active + archived) in this Conversation
            for conv_ctx in conversation.get_all_sessions():
                if conv_ctx.ai_agent_session_id == agent_session_id:
                    return (session, conv_ctx, working_dir)

    return None


def json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for objects not serializable by default json module.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable representation of the object

    Raises:
        TypeError: If object type cannot be serialized
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    # Try to use Pydantic's model_dump if available
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    # Fallback to str for other types
    return str(obj)


def output_json(
    success: bool,
    data: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    error: Optional[Dict[str, Any]] = None,
) -> None:
    """Output standardized JSON format to stdout.

    This function outputs ONLY valid JSON to stdout, with no Rich formatting.
    All error details are sent to stderr, while the JSON error object goes to stdout.

    Args:
        success: Whether the operation was successful
        data: Data payload to include in the response
        metadata: Optional metadata (pagination, timestamps, etc.)
        error: Optional error information (message, code)

    Examples:
        # Success with data
        output_json(success=True, data={"session": session.model_dump(mode="json")})

        # Success with data and metadata
        output_json(
            success=True,
            data={"sessions": sessions_list},
            metadata={"total_count": 42, "page": 1}
        )

        # Error
        output_json(
            success=False,
            error={"message": "Session not found", "code": "SESSION_NOT_FOUND"}
        )
    """
    output = {"success": success}

    if data is not None:
        output["data"] = data

    if metadata is not None:
        output["metadata"] = metadata

    if error is not None:
        output["error"] = error

    # Output to stdout only
    print(json.dumps(output, indent=2, default=json_serializer))


def serialize_session(session: Session) -> Dict[str, Any]:
    """Serialize a Session object to JSON-compatible dict.

    Uses Pydantic's model_dump with mode='json' for proper serialization.

    Args:
        session: Session object to serialize

    Returns:
        JSON-compatible dictionary representation of the session
    """
    return session.model_dump(mode="json")


def serialize_sessions(sessions: list[Session]) -> list[Dict[str, Any]]:
    """Serialize a list of Session objects to JSON-compatible dicts.

    Args:
        sessions: List of Session objects to serialize

    Returns:
        List of JSON-compatible dictionary representations
    """
    return [serialize_session(s) for s in sessions]


def get_active_session_name() -> Optional[str]:
    """Get the active session name from the current Claude Code session.

    This function first checks CS_SESSION_NAME environment variable (set by daf jira new),
    then falls back to searching for AI_AGENT_SESSION_ID. This allows daf jira create to
    detect when it's being called from a ticket_creation session.

    Returns:
        Active session name if found, None otherwise

    Examples:
        >>> # When called from within a Claude Code session
        >>> get_active_session_name()
        'my-session'
        >>> # When called outside Claude Code
        >>> get_active_session_name()
        None
    """
    from devflow.config.loader import ConfigLoader
    import logging

    logger = logging.getLogger(__name__)

    # First check for CS_SESSION_NAME (more reliable, set explicitly by daf jira new)
    cs_session_name = os.environ.get("CS_SESSION_NAME")
    if cs_session_name:
        logger.debug(f"CS_SESSION_NAME from environment: {cs_session_name}")

        # Check if this session still exists or was renamed
        config_loader = ConfigLoader()
        session_manager = SessionManager(config_loader=config_loader)

        # Try to get the session by the name from environment
        session = session_manager.get_session(cs_session_name)

        if session:
            # Session found with original name - it hasn't been renamed yet
            logger.info(f"Found session with name from CS_SESSION_NAME: {cs_session_name}")
            return cs_session_name

        # Session not found with original name - it was likely renamed
        # This happens after daf jira create renames the session from temp name to creation-PROJ-*
        logger.debug(f"Session '{cs_session_name}' not found in index - it may have been renamed")

        # Since rename deletes the old group and creates a new one, we need to find the new name
        # We can't reliably determine which creation-* session is ours without more context
        # So we return None and let the command fail gracefully
        logger.warning(f"Session '{cs_session_name}' not found - it may have been renamed but we cannot determine the new name")
        return None

    # Fallback to AI_AGENT_SESSION_ID lookup (may not be exported by Claude Code)
    ai_agent_session_id = os.environ.get("AI_AGENT_SESSION_ID")
    logger.debug(f"AI_AGENT_SESSION_ID from environment: {ai_agent_session_id}")

    if not ai_agent_session_id:
        logger.debug("No AI_AGENT_SESSION_ID or CS_SESSION_NAME found in environment")
        return None

    # Load session index and search for matching conversation
    config_loader = ConfigLoader()
    session_index = config_loader.load_sessions()
    logger.debug(f"Loaded {len(session_index.sessions)} sessions")

    for session in session_index.sessions.values():
        for conversation in session.conversations.values():
            # Check all sessions (active + archived) in this Conversation
            for conv_ctx in conversation.get_all_sessions():
                if conv_ctx.ai_agent_session_id == ai_agent_session_id:
                    logger.info(f"Found matching session: {session.name} (session_type={session.session_type})")
                    return session.name

    logger.debug(f"No session found with ai_agent_session_id={ai_agent_session_id}")
    return None


def check_concurrent_session(
    session_manager: SessionManager,
    project_path: str,
    current_session_name: str,
    action: str = "create"
) -> bool:
    """Check for concurrent active sessions in the same project.

    This utility prevents branch switching conflicts by ensuring only one session
    is active in a project at a time. Called BEFORE any git operations.

    Args:
        session_manager: SessionManager instance
        project_path: Absolute path to the project directory
        current_session_name: Name of the session being created/opened
        action: Action being performed ("create" or "open") - used in error message

    Returns:
        True if no conflicts (safe to proceed), False if another session is active

    Examples:
        >>> # Before creating a new session
        >>> if not check_concurrent_session(mgr, "/path/to/repo", "session-a", "create"):
        ...     return  # Exit, another session is active
        >>> # Safe to proceed with git operations

        >>> # Before opening a session
        >>> if not check_concurrent_session(mgr, "/path/to/repo", "session-b", "open"):
        ...     return  # Exit, another session is active
    """
    active_session = session_manager.get_active_session_for_project(project_path)

    if active_session and active_session.name != current_session_name:
        console.print(f"\n[red]Error: Cannot {action} session - another session is already active in this project[/red]")
        console.print(f"\n[yellow]Active session:[/yellow] {active_session.name}")
        active_conv = active_session.active_conversation
        if active_conv and active_conv.branch:
            console.print(f"[yellow]Branch:[/yellow] {active_conv.branch}")
        console.print(f"\n[cyan]To resolve this:[/cyan]")
        console.print(f"  1. Resume the active session: [bold]daf open {active_session.name}[/bold]")
        console.print(f"  2. Complete it: [bold]daf complete {active_session.name}[/bold]")
        console.print(f"  3. Or pause it manually (exit Claude Code if running)")
        console.print(f"\n[dim]This prevents branch switching conflicts and mixed changes.[/dim]")
        return False

    return True


def should_launch_claude_code(config: Optional[Config] = None, mock_mode: bool = False) -> bool:
    """Check if AI agent should be launched based on config or user prompt.

    This shared utility consolidates the logic for determining whether to launch
    the AI agent across all commands (daf open, daf new, daf jira new).

    Supports backward compatibility with auto_launch_claude config field.

    Args:
        config: Optional Config object to check auto_launch_agent setting
        mock_mode: If True, check DAF_MOCK_MODE environment variable and return False if set

    Returns:
        True if AI agent should be launched, False otherwise

    Examples:
        >>> # In mock mode, always skip launch
        >>> should_launch_claude_code(mock_mode=True)  # with DAF_MOCK_MODE=1
        False

        >>> # With auto_launch_agent configured
        >>> should_launch_claude_code(config)  # config.prompts.auto_launch_agent = True
        True

        >>> # Backward compatibility with auto_launch_claude
        >>> should_launch_claude_code(config)  # config.prompts.auto_launch_claude = True
        True

        >>> # Without config, prompts user
        >>> should_launch_claude_code()  # Prompts: "Launch AI agent?"
    """
    # Check mock mode first
    from devflow.utils import is_mock_mode
    if mock_mode and is_mock_mode():
        console_print()
        console_print("[yellow]📝 Mock mode: Skipping AI agent launch[/yellow]")
        console_print("[dim]Session metadata updated. Use 'daf complete' or 'daf note' to continue.[/dim]")
        console_print()
        return False

    # Check config setting (with backward compatibility for auto_launch_claude)
    if config and config.prompts:
        # Check auto_launch_agent first (new field)
        if config.prompts.auto_launch_agent is not None:
            should_launch = config.prompts.auto_launch_agent
            agent_name = getattr(config, 'agent_backend', 'claude').capitalize()
            if should_launch:
                console_print(f"[dim]Automatically launching {agent_name} (configured in prompts)[/dim]")
            else:
                console_print(f"[dim]Skipping {agent_name} launch (configured in prompts)[/dim]")
            return should_launch
        # Fallback to auto_launch_claude for backward compatibility
        elif config.prompts.auto_launch_claude is not None:
            should_launch = config.prompts.auto_launch_claude
            if should_launch:
                console_print("[dim]Automatically launching Claude Code (configured in prompts)[/dim]")
            else:
                console_print("[dim]Skipping Claude Code launch (configured in prompts)[/dim]")
            return should_launch

    # Prompt user (only if not in JSON mode)
    if is_json_mode():
        # In JSON mode, default to True (launch) without prompting
        return True

    return Confirm.ask("\nLaunch Claude Code?", default=True)
