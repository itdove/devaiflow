"""Factory for creating AI agent clients.

This module provides a factory function for creating the appropriate agent client
based on configuration. It follows the same pattern as create_issue_tracker_client
from devflow/issue_tracker/__init__.py.

The ``AGENT_REGISTRY`` dict is the single source of truth for all backend
metadata.  Derived constants (``SUPPORTED_BACKENDS``, ``AGENT_DISPLAY_NAMES``,
``SELF_ID_BACKENDS``) are computed from it for backward compatibility.
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from devflow.agent.interface import AgentInterface
from devflow.agent.claude_agent import ClaudeAgent
from devflow.agent.github_copilot_agent import GitHubCopilotAgent
from devflow.agent.cursor_agent import CursorAgent
from devflow.agent.windsurf_agent import WindsurfAgent
from devflow.agent.ollama_claude_agent import OllamaClaudeAgent
from devflow.agent.aider_agent import AiderAgent
from devflow.agent.continue_agent import ContinueAgent
from devflow.agent.crush_agent import CrushAgent
from devflow.agent.opencode_agent import OpenCodeAgent

# ---------------------------------------------------------------------------
# Unified agent metadata registry
# ---------------------------------------------------------------------------
# Every supported backend has exactly one entry here.  Aliases (e.g.
# "copilot" -> "github-copilot") live in AGENT_ALIASES below.
#
# Fields:
#   display_name  – human-readable name shown in messages/tables
#   description   – one-line agent description
#   cli_binary    – executable used for subprocess AI operations
#   cli_command   – executable checked for install detection
#   project_url   – agent project URL (for "Generated with" attribution)
#   install_url   – installation docs URL
#   status        – "fully-tested" or "experimental"
#   self_id       – True if the agent generates its own session IDs
#   features      – capability flags
#   notes         – (optional) extra context
# ---------------------------------------------------------------------------

AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "claude": {
        "display_name": "Claude Code",
        "description": "Anthropic's official Claude Code CLI",
        "cli_binary": "claude",
        "cli_command": "claude",
        "project_url": "https://claude.ai/code",
        "install_url": "https://docs.claude.com/en/docs/claude-code/installation",
        "status": "fully-tested",
        "self_id": False,
        "features": {
            "session_management": True,
            "conversation_export": True,
            "message_counting": True,
            "resume_support": True,
            "skills_support": True,
        },
    },
    "ollama": {
        "display_name": "Ollama + Claude Code",
        "description": "Local models via Ollama with Claude Code interface",
        "cli_binary": "claude",
        "cli_command": "ollama",
        "project_url": "https://claude.ai/code",
        "install_url": "https://ollama.ai/download",
        "status": "fully-tested",
        "self_id": False,
        "features": {
            "session_management": True,
            "conversation_export": True,
            "message_counting": True,
            "resume_support": True,
            "skills_support": True,
        },
        "notes": "Requires both 'ollama' and 'claude' CLI tools",
    },
    "github-copilot": {
        "display_name": "GitHub Copilot",
        "description": "GitHub Copilot in VS Code",
        "cli_binary": "claude",
        "cli_command": "code",
        "project_url": "https://github.com/features/copilot",
        "install_url": "https://code.visualstudio.com/",
        "status": "experimental",
        "self_id": False,
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "Limited integration - experimental support only",
    },
    "cursor": {
        "display_name": "Cursor",
        "description": "Cursor AI editor",
        "cli_binary": "claude",
        "cli_command": "cursor",
        "project_url": "https://cursor.com",
        "install_url": "https://cursor.sh/",
        "status": "experimental",
        "self_id": False,
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "Limited integration - experimental support only",
    },
    "windsurf": {
        "display_name": "Windsurf",
        "description": "Windsurf (Codeium) editor",
        "cli_binary": "claude",
        "cli_command": "windsurf",
        "project_url": "https://codeium.com/windsurf",
        "install_url": "https://codeium.com/windsurf",
        "status": "experimental",
        "self_id": False,
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "Limited integration - experimental support only",
    },
    "aider": {
        "display_name": "Aider",
        "description": "AI pair programming in terminal",
        "cli_binary": "aider",
        "cli_command": "aider",
        "project_url": "https://aider.chat",
        "install_url": "https://aider.chat/docs/install.html",
        "status": "experimental",
        "self_id": False,
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "Git-first approach with chat history files",
    },
    "continue": {
        "display_name": "Continue",
        "description": "VS Code extension for AI assistance",
        "cli_binary": "claude",
        "cli_command": "code",
        "project_url": "https://continue.dev",
        "install_url": "https://continue.dev/docs/quickstart",
        "status": "experimental",
        "self_id": False,
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "VS Code extension - limited CLI integration",
    },
    "crush": {
        "display_name": "Crush",
        "description": "Crush AI coding assistant",
        "cli_binary": "claude",
        "cli_command": "crush",
        "project_url": "https://crush.ai",
        "install_url": "https://crush.ai",
        "status": "experimental",
        "self_id": False,
        "features": {
            "session_management": False,
            "conversation_export": False,
            "message_counting": False,
            "resume_support": False,
            "skills_support": False,
        },
        "notes": "Limited integration - experimental support only",
    },
    "opencode": {
        "display_name": "OpenCode",
        "description": "Open source terminal AI coding agent by Anomaly (multi-provider)",
        "cli_binary": "opencode",
        "cli_command": "opencode",
        "project_url": "https://opencode.ai",
        "install_url": "https://opencode.ai",
        "status": "experimental",
        "self_id": True,
        "features": {
            "session_management": True,
            "conversation_export": True,
            "message_counting": True,
            "resume_support": True,
            "skills_support": False,
        },
    },
}

AGENT_ALIASES: Dict[str, str] = {
    "ollama-claude": "ollama",
    "copilot": "github-copilot",
    "opencode-ai": "opencode",
}

# ---------------------------------------------------------------------------
# Derived constants (backward-compatible)
# ---------------------------------------------------------------------------

SUPPORTED_BACKENDS: List[str] = list(AGENT_REGISTRY) + list(AGENT_ALIASES)

AGENT_DISPLAY_NAMES: Dict[str, str] = {
    name: entry["display_name"] for name, entry in AGENT_REGISTRY.items()
}
for _alias, _canonical in AGENT_ALIASES.items():
    AGENT_DISPLAY_NAMES[_alias] = AGENT_REGISTRY[_canonical]["display_name"]

SELF_ID_BACKENDS: tuple = tuple(
    name for name, entry in AGENT_REGISTRY.items() if entry.get("self_id")
) + tuple(
    alias for alias, canonical in AGENT_ALIASES.items()
    if AGENT_REGISTRY[canonical].get("self_id")
)

PENDING_CAPTURE_PLACEHOLDER = "pending-capture"


def _resolve_alias(backend: str) -> str:
    """Resolve an alias to its canonical backend name."""
    return AGENT_ALIASES.get(backend.lower(), backend.lower())


def get_agent_metadata(backend: str) -> Dict[str, Any]:
    """Get the full metadata dict for a backend, resolving aliases.

    Returns an empty dict for unknown backends.
    """
    return AGENT_REGISTRY.get(_resolve_alias(backend), {})


def get_agent_cli_binary(backend: Optional[str] = None) -> str:
    """Get the CLI binary name used for subprocess AI operations.

    Args:
        backend: Agent backend identifier. Defaults to "claude".

    Returns:
        CLI binary name (e.g., "claude", "opencode", "aider")
    """
    meta = get_agent_metadata(backend or "claude")
    return meta.get("cli_binary", "claude")


def get_agent_project_url(backend: Optional[str] = None) -> str:
    """Get the project URL for a backend (used in attribution).

    Args:
        backend: Agent backend identifier. Defaults to "claude".

    Returns:
        Project URL string, or empty string if unknown.
    """
    meta = get_agent_metadata(backend or "claude")
    return meta.get("project_url", "")


def get_generated_with_line(backend: Optional[str] = None) -> str:
    """Build the 'Generated with' attribution line for commits and PRs.

    Args:
        backend: Agent backend identifier. Defaults to "claude".

    Returns:
        Attribution string like '🤖 Generated with [Claude Code](https://claude.ai/code)'
    """
    agent_name = get_agent_display_name(backend)
    url = get_agent_project_url(backend)
    if url:
        return f"🤖 Generated with [{agent_name}]({url})"
    return f"🤖 Generated with {agent_name}"


def resolve_agent_backend(
    cli_override: Optional[str] = None,
    session=None,
    config=None,
) -> str:
    """Resolve the effective agent backend from the fallback chain.

    Priority: cli_override > session.agent_backend > config.agent_backend > "claude"

    Args:
        cli_override: Explicit backend from CLI ``--agent`` flag.
        session: Session object with an ``agent_backend`` attribute.
        config: Config object with an ``agent_backend`` attribute.

    Returns:
        Resolved backend identifier, never ``None``.
    """
    if cli_override:
        return cli_override
    if session:
        backend = getattr(session, "agent_backend", None)
        if backend:
            return backend
    if config:
        backend = getattr(config, "agent_backend", None)
        if backend:
            return backend
    return "claude"


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
    from rich.console import Console
    console = Console()
    try:
        sessions_after = agent.get_existing_sessions(launch_dir)
        new_sessions = sessions_after - sessions_before
        if new_sessions:
            if len(new_sessions) > 1:
                console.print(
                    f"[yellow]Warning: Multiple new {agent.get_agent_name()} sessions detected "
                    f"({len(new_sessions)}). Using most recent. "
                    f"Session will be verified on next open.[/yellow]"
                )
            real_session_id = sorted(new_sessions)[-1]
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


def launch_and_capture(
    agent: AgentInterface,
    agent_backend: str,
    project_path: str,
    active_conversation,
    *,
    initial_prompt: str,
    session_id: str,
    model_provider_profile=None,
    workspace_path: str = None,
    config=None,
    env: dict = None,
    headless: bool = False,
    auto_approve: bool = False,
) -> None:
    """Snapshot sessions, launch agent, wait for exit, capture session ID.

    Wraps the standard agent launch lifecycle used by all daf commands:
    snapshot existing sessions, launch via ``launch_with_prompt``, wait
    for exit, then capture any newly created session ID.

    Callers should wrap this in their own try/finally for command-specific
    post-exit cleanup (updating session status, ending work sessions, etc.).
    """
    sessions_before = snapshot_agent_sessions(agent, agent_backend, project_path)
    try:
        process = agent.launch_with_prompt(
            project_path=project_path,
            initial_prompt=initial_prompt,
            session_id=session_id,
            model_provider_profile=model_provider_profile,
            skills_dirs=None,
            workspace_path=workspace_path,
            config=config,
            env=env,
            headless=headless,
            auto_approve=auto_approve,
        )
        agent.wait_for_exit(process, headless)
    finally:
        capture_agent_session_id(
            agent, agent_backend, project_path,
            active_conversation, sessions_before,
        )


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
            f"Supported: {', '.join(sorted(set(SUPPORTED_BACKENDS) - set(AGENT_ALIASES)))}"
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
