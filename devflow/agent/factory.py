"""Factory for creating AI agent clients.

This module provides a factory function for creating the appropriate agent client
based on configuration. It follows the same pattern as create_issue_tracker_client
from devflow/issue_tracker/__init__.py.
"""

from pathlib import Path
from typing import Optional

from devflow.agent.interface import AgentInterface
from devflow.agent.claude_agent import ClaudeAgent
from devflow.agent.github_copilot_agent import GitHubCopilotAgent
from devflow.agent.cursor_agent import CursorAgent
from devflow.agent.windsurf_agent import WindsurfAgent


def create_agent_client(backend: str = "claude", agent_home: Optional[Path] = None) -> AgentInterface:
    """Create an agent client for the specified backend.

    Args:
        backend: Agent backend to use ("claude", "github-copilot", "cursor", "windsurf")
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

        >>> # Create with custom home directory
        >>> agent = create_agent_client("claude", Path("/custom/path"))

    Note:
        Only Claude Code has been fully tested. Other agents (GitHub Copilot,
        Cursor, Windsurf) are experimental and may have limitations in session
        management, conversation export, and message counting capabilities.
    """
    backend = backend.lower()

    if backend == "claude":
        return ClaudeAgent(claude_dir=agent_home)
    elif backend in ("github-copilot", "copilot"):
        return GitHubCopilotAgent(copilot_dir=agent_home)
    elif backend == "cursor":
        return CursorAgent(cursor_dir=agent_home)
    elif backend == "windsurf":
        return WindsurfAgent(windsurf_dir=agent_home)
    else:
        raise ValueError(
            f"Unsupported agent backend: {backend}. "
            f"Supported backends: claude, github-copilot, cursor, windsurf"
        )
