"""Factory for creating AI agent clients.

This module provides a factory function for creating the appropriate agent client
based on configuration. It follows the same pattern as create_issue_tracker_client
from devflow/issue_tracker/__init__.py.
"""

import uuid
from pathlib import Path
from typing import Optional, Set

from rich.console import Console

from devflow.agent.interface import AgentInterface

console = Console()
from devflow.agent.claude_agent import ClaudeAgent
from devflow.agent.github_copilot_agent import GitHubCopilotAgent
from devflow.agent.cursor_agent import CursorAgent
from devflow.agent.windsurf_agent import WindsurfAgent
from devflow.agent.ollama_claude_agent import OllamaClaudeAgent
from devflow.agent.aider_agent import AiderAgent
from devflow.agent.continue_agent import ContinueAgent
from devflow.agent.crush_agent import CrushAgent
from devflow.agent.opencode_agent import OpenCodeAgent

# Canonical list of supported agent backend names (used for CLI validation)
SUPPORTED_BACKENDS = [
    "claude",
    "ollama",
    "ollama-claude",
    "github-copilot",
    "copilot",
    "cursor",
    "windsurf",
    "aider",
    "continue",
    "crush",
    "opencode",
    "opencode-ai",
]

# Human-readable display names for each backend (used in user-facing messages)
AGENT_DISPLAY_NAMES = {
    "claude": "Claude Code",
    "ollama": "Ollama + Claude Code",
    "ollama-claude": "Ollama + Claude Code",
    "github-copilot": "GitHub Copilot",
    "copilot": "GitHub Copilot",
    "cursor": "Cursor",
    "windsurf": "Windsurf",
    "aider": "Aider",
    "continue": "Continue",
    "crush": "Crush",
    "opencode": "OpenCode",
    "opencode-ai": "OpenCode",
}


# Backends that generate their own session IDs (not UUIDs)
# These agents create session IDs during launch (e.g., ses_ prefix for OpenCode)
# and need post-launch capture instead of pre-generated UUIDs
SELF_ID_BACKENDS = ("opencode", "opencode-ai")

# Placeholder value for agents that generate their own session IDs
PENDING_CAPTURE_PLACEHOLDER = "pending-capture"


def is_self_id_backend(backend: str) -> bool:
    """Check if an agent backend generates its own session IDs.

    Some agents (like OpenCode) generate their own session IDs during launch
    (e.g., ``ses_...`` format). For these backends, we use a placeholder
    instead of a pre-generated UUID and capture the real ID after launch.

    Args:
        backend: Agent backend identifier (e.g., "opencode", "claude")

    Returns:
        True if the backend generates its own session IDs
    """
    return backend.lower() in SELF_ID_BACKENDS


def generate_agent_session_id(agent_backend: str) -> str:
    """Generate a session ID appropriate for the agent backend.

    For most agents (Claude, Copilot, etc.), returns a UUID4 string.
    For agents that generate their own session IDs (OpenCode), returns
    a placeholder that will be replaced after launch via capture logic.

    Args:
        agent_backend: Agent backend identifier

    Returns:
        UUID string or placeholder depending on backend

    Examples:
        >>> generate_agent_session_id("claude")  # Returns UUID like "4b0eea04-..."
        >>> generate_agent_session_id("opencode")  # Returns "pending-capture"
    """
    if is_self_id_backend(agent_backend):
        return PENDING_CAPTURE_PLACEHOLDER
    return str(uuid.uuid4())


def is_pending_capture(session_id: str) -> bool:
    """Check if a session ID is the pending-capture placeholder.

    Args:
        session_id: Session ID to check

    Returns:
        True if the session ID is a pending-capture placeholder
    """
    return session_id == PENDING_CAPTURE_PLACEHOLDER


def snapshot_agent_sessions(
    agent: AgentInterface,
    agent_backend: str,
    launch_dir: str,
) -> Set[str]:
    """Take a snapshot of existing agent sessions before launch.

    For agents that generate their own session IDs (like OpenCode), this
    captures the set of existing sessions so we can detect newly created
    sessions after launch by computing the set difference.

    Args:
        agent: Agent client instance
        agent_backend: Agent backend identifier
        launch_dir: Directory where the agent will be launched

    Returns:
        Set of existing session IDs (empty for non-self-ID backends)
    """
    if not is_self_id_backend(agent_backend) or not launch_dir:
        return set()
    try:
        return agent.get_existing_sessions(launch_dir)
    except Exception:
        return set()


def capture_agent_session_id(
    agent: AgentInterface,
    agent_backend: str,
    launch_dir: str,
    active_conv,
    sessions_before: Set[str],
) -> bool:
    """Capture the real session ID after agent launch.

    For agents that generate their own session IDs (like OpenCode), this
    compares session lists before and after launch to find the new session.
    Updates ``active_conv.ai_agent_session_id`` in place.

    Args:
        agent: Agent client instance
        agent_backend: Agent backend identifier
        launch_dir: Directory where the agent was launched
        active_conv: Active conversation object to update
        sessions_before: Session snapshot taken before launch

    Returns:
        True if a new session ID was captured and stored
    """
    if not is_self_id_backend(agent_backend) or not launch_dir or not active_conv:
        return False
    try:
        sessions_after = agent.get_existing_sessions(launch_dir)
        new_sessions = sessions_after - sessions_before
        if new_sessions:
            real_session_id = new_sessions.pop()
            active_conv.ai_agent_session_id = real_session_id
            console.print(f"[dim]Captured {agent.get_agent_name()} session ID: {real_session_id}[/dim]")
            return True
        else:
            console.print(
                f"[yellow]Warning: Could not capture {agent.get_agent_name()} session ID. "
                f"Session will be captured on next open.[/yellow]"
            )
            return False
    except Exception as e:
        console.print(
            f"[yellow]Warning: Failed to capture {agent.get_agent_name()} session ID: {e}[/yellow]"
        )
        return False


def get_agent_display_name(backend: Optional[str] = None) -> str:
    """Get the human-readable display name for an agent backend.

    Args:
        backend: Agent backend identifier (e.g., "claude", "opencode").
                 If None, defaults to "claude".

    Returns:
        Human-readable name (e.g., "Claude Code", "OpenCode")

    Examples:
        >>> get_agent_display_name("claude")
        'Claude Code'
        >>> get_agent_display_name("opencode")
        'OpenCode'
        >>> get_agent_display_name("github-copilot")
        'GitHub Copilot'
        >>> get_agent_display_name(None)
        'Claude Code'
    """
    if backend is None:
        backend = "claude"
    return AGENT_DISPLAY_NAMES.get(backend.lower(), backend)


def validate_agent_backend(backend: str) -> str:
    """Validate and normalize an agent backend name.

    Args:
        backend: Agent backend name to validate

    Returns:
        Lowercased backend name

    Raises:
        click.BadParameter: If backend is not supported
    """
    import click

    normalized = backend.lower()
    if normalized not in SUPPORTED_BACKENDS:
        raise click.BadParameter(
            f"Unsupported agent backend: '{backend}'. "
            f"Supported: {', '.join(sorted(set(SUPPORTED_BACKENDS) - {'ollama-claude', 'copilot', 'opencode-ai'}))}"
        )
    return normalized


def create_agent_client(backend: str = "claude", agent_home: Optional[Path] = None) -> AgentInterface:
    """Create an agent client for the specified backend.

    Args:
        backend: Agent backend to use ("claude", "ollama", "github-copilot", "cursor", "windsurf", "aider", "continue", "crush", "opencode")
        agent_home: Optional custom home directory for the agent

    Returns:
        AgentInterface implementation for the specified backend

    Raises:
        ValueError: If backend is not supported

    Examples:
        >>> # Create Claude Code agent
        >>> agent = create_agent_client("claude")
        >>> agent.get_agent_name()
        'claude'

        >>> # Create Ollama + Claude Code agent (local models)
        >>> agent = create_agent_client("ollama")
        >>> agent.get_agent_name()
        'ollama'

        >>> # Create GitHub Copilot agent
        >>> agent = create_agent_client("github-copilot")
        >>> agent.get_agent_name()
        'github-copilot'

        >>> # Create Cursor agent
        >>> agent = create_agent_client("cursor")
        >>> agent.get_agent_name()
        'cursor'

        >>> # Create Windsurf agent
        >>> agent = create_agent_client("windsurf")
        >>> agent.get_agent_name()
        'windsurf'

        >>> # Create Aider agent
        >>> agent = create_agent_client("aider")
        >>> agent.get_agent_name()
        'aider'

        >>> # Create Continue agent
        >>> agent = create_agent_client("continue")
        >>> agent.get_agent_name()
        'continue'

        >>> # Create Crush agent
        >>> agent = create_agent_client("crush")
        >>> agent.get_agent_name()
        'crush'

        >>> # Create OpenCode agent
        >>> agent = create_agent_client("opencode")
        >>> agent.get_agent_name()
        'opencode'

        >>> # Create with custom home directory
        >>> agent = create_agent_client("claude", Path("/custom/path"))

    Note:
        Only Claude Code and Ollama have been fully tested. Other agents (GitHub Copilot,
        Cursor, Windsurf, Aider, Continue, Crush, OpenCode) are experimental and may have
        limitations in session management, conversation export, and message counting capabilities.
    """
    backend = backend.lower()

    if backend == "claude":
        return ClaudeAgent(claude_dir=agent_home)
    elif backend in ("ollama", "ollama-claude"):
        return OllamaClaudeAgent(ollama_dir=agent_home)
    elif backend in ("github-copilot", "copilot"):
        return GitHubCopilotAgent(copilot_dir=agent_home)
    elif backend == "cursor":
        return CursorAgent(cursor_dir=agent_home)
    elif backend == "windsurf":
        return WindsurfAgent(windsurf_dir=agent_home)
    elif backend == "aider":
        return AiderAgent(aider_dir=agent_home)
    elif backend == "continue":
        return ContinueAgent(continue_dir=agent_home)
    elif backend == "crush":
        return CrushAgent(crush_dir=agent_home)
    elif backend in ("opencode", "opencode-ai"):
        return OpenCodeAgent(opencode_dir=agent_home)
    else:
        raise ValueError(
            f"Unsupported agent backend: {backend}. "
            f"Supported backends: claude, ollama, github-copilot, cursor, windsurf, aider, continue, crush, opencode"
        )
