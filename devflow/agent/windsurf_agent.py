"""Windsurf agent implementation.

This module implements the AgentInterface for Windsurf, Codeium's AI-powered
code editor with advanced agentic coding capabilities.

⚠️  EXPERIMENTAL - NOT FULLY TESTED
This agent implementation has not been fully tested. It may have limitations or bugs.
Only Claude Code has been comprehensively tested. Use at your own risk.

Windsurf is built on VS Code and provides deep AI integration with features like
Cascade (agentic coding flows) and Supercomplete (advanced code completion).
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, Set

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class WindsurfAgent(AgentInterface):
    """Windsurf agent implementation.

    Provides integration with Windsurf editor, Codeium's AI-first code editor
    with agentic coding capabilities.

    Windsurf offers:
    - Cascade: Multi-step agentic coding workflows
    - Supercomplete: Advanced AI code completion
    - Built-in AI chat and code generation

    Session management uses Windsurf's workspace system, similar to VS Code
    but optimized for AI-driven development workflows.

    Limitations:
    - Session ID based on workspace identifiers
    - Conversation export depends on Windsurf's storage format
    - Message counting limited by internal state format
    """

    def __init__(self, windsurf_dir: Optional[Path] = None):
        """Initialize Windsurf agent.

        Args:
            windsurf_dir: Windsurf data directory. Defaults to ~/.windsurf
        """
        if windsurf_dir is None:
            windsurf_dir = Path.home() / ".windsurf"
        self.windsurf_dir = windsurf_dir
        self.workspace_storage = windsurf_dir / "User" / "workspaceStorage"

    def launch_session(self, project_path: str) -> subprocess.Popen:
        """Launch Windsurf in a project directory.

        Args:
            project_path: Absolute path to project

        Returns:
            Subprocess handle for Windsurf process

        Raises:
            ToolNotFoundError: If windsurf command is not installed
        """
        require_tool("windsurf", "launch Windsurf editor")

        return subprocess.Popen(
            ["windsurf", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def resume_session(self, session_id: str, project_path: str) -> subprocess.Popen:
        """Resume Windsurf in a project directory.

        Windsurf automatically restores the previous workspace state including
        AI chat history, Cascade workflows, and editor configuration.

        Args:
            session_id: Session identifier (tracked by DevAIFlow)
            project_path: Absolute path to project

        Returns:
            Subprocess handle for Windsurf process

        Raises:
            ToolNotFoundError: If windsurf command is not installed
        """
        require_tool("windsurf", "resume Windsurf editor")

        # Windsurf automatically restores workspace state
        return subprocess.Popen(
            ["windsurf", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """Capture a session ID for the current workspace.

        Generates a workspace-based identifier for tracking Windsurf sessions
        across DevAIFlow operations.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Generated session identifier
        """
        # Generate session ID: windsurf-{encoded_path}-{timestamp}
        encoded_path = self.encode_project_path(project_path)
        timestamp = int(time.time())
        session_id = f"windsurf-{encoded_path}-{timestamp}"

        return session_id

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to Windsurf's workspace state file.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            Path to workspace state database
        """
        # Windsurf stores workspace state similarly to VS Code
        encoded = self.encode_project_path(project_path)

        # Windsurf creates workspace storage with unique IDs
        if self.workspace_storage.exists():
            # Scan workspace storage for matching project
            for workspace_dir in self.workspace_storage.iterdir():
                if workspace_dir.is_dir():
                    # Check for workspace metadata
                    workspace_json = workspace_dir / "workspace.json"
                    if workspace_json.exists():
                        # Could parse to match project_path
                        # For now, return first valid state file
                        state_file = workspace_dir / "state.vscdb"
                        if state_file.exists():
                            return state_file

        # Fallback: return expected path
        return self.workspace_storage / encoded / "state.vscdb"

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a Windsurf workspace session exists.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            True if workspace storage exists
        """
        session_file = self.get_session_file_path(session_id, project_path)
        return session_file.exists() or session_file.parent.exists()

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs for a project.

        Note: Windsurf manages workspace sessions internally through workspace
        storage. Discrete session files are not maintained.

        Args:
            project_path: Absolute path to project

        Returns:
            Empty set (Windsurf uses workspace storage system)
        """
        # Windsurf doesn't maintain discrete session files
        # Sessions tracked through workspace storage directories
        return set()

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get approximate message count from Windsurf AI chat.

        Note: Windsurf stores AI chat and Cascade workflow history in workspace
        state, but the internal format is not publicly documented.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            0 (message counting not supported)
        """
        # Windsurf's AI chat history stored in workspace state database
        # Internal format not documented, cannot reliably count messages
        return 0

    def encode_project_path(self, project_path: str) -> str:
        """Encode project path for storage identifiers.

        Uses consistent encoding with other agents.

        Args:
            project_path: Absolute path to project

        Returns:
            Encoded path string
        """
        # Consistent encoding: replace / and _ with -
        encoded = project_path.replace("/", "-").replace("_", "-")
        return encoded

    def get_agent_home_dir(self) -> Path:
        """Get Windsurf's home directory.

        Returns:
            Path to ~/.windsurf directory
        """
        return self.windsurf_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "windsurf"
        """
        return "windsurf"
