"""Agent interface abstraction for DevAIFlow.

This module provides abstractions for AI agent backends (e.g., Claude Code, GitHub Copilot, etc.).
It allows swapping between different AI agents while maintaining a consistent interface.

Supported Agents:
- Claude Code (fully tested)
- Ollama + Claude Code (fully tested - local models)
- GitHub Copilot (experimental)
- Cursor (experimental)
- Windsurf (experimental)
- Aider (experimental)
- Continue (experimental)
- Crush (experimental)
- OpenCode (experimental)

Note: Only Claude Code and Ollama have been fully tested. Other agents are experimental implementations
that may have limitations in session management, conversation export, and message counting.
"""

from devflow.agent.interface import AgentInterface
from devflow.agent.claude_agent import ClaudeAgent
from devflow.agent.ollama_claude_agent import OllamaClaudeAgent
from devflow.agent.github_copilot_agent import GitHubCopilotAgent
from devflow.agent.cursor_agent import CursorAgent
from devflow.agent.windsurf_agent import WindsurfAgent
from devflow.agent.aider_agent import AiderAgent
from devflow.agent.continue_agent import ContinueAgent
from devflow.agent.crush_agent import CrushAgent
from devflow.agent.opencode_agent import OpenCodeAgent
from devflow.agent.factory import (
    create_agent_client,
    SUPPORTED_BACKENDS,
    AGENT_DISPLAY_NAMES,
    SELF_ID_BACKENDS,
    PENDING_CAPTURE_PLACEHOLDER,
    get_agent_display_name,
    validate_agent_backend,
    is_self_id_backend,
    generate_agent_session_id,
    is_pending_capture,
    snapshot_agent_sessions,
    capture_agent_session_id,
    launch_and_capture,
)

__all__ = [
    "AgentInterface",
    "ClaudeAgent",
    "OllamaClaudeAgent",
    "GitHubCopilotAgent",
    "CursorAgent",
    "WindsurfAgent",
    "AiderAgent",
    "ContinueAgent",
    "CrushAgent",
    "OpenCodeAgent",
    "create_agent_client",
    "SUPPORTED_BACKENDS",
    "AGENT_DISPLAY_NAMES",
    "SELF_ID_BACKENDS",
    "PENDING_CAPTURE_PLACEHOLDER",
    "get_agent_display_name",
    "validate_agent_backend",
    "is_self_id_backend",
    "generate_agent_session_id",
    "is_pending_capture",
    "snapshot_agent_sessions",
    "capture_agent_session_id",
    "launch_and_capture",
]
