"""GitHub Copilot agent implementation.

This module implements the AgentInterface for GitHub Copilot Chat, enabling
session management with GitHub's AI coding assistant.

⚠️  EXPERIMENTAL - NOT FULLY TESTED
This agent implementation has not been fully tested. It may have limitations or bugs.
Only Claude Code has been comprehensively tested. Use at your own risk.

Note: GitHub Copilot primarily operates through IDE extensions (VS Code, JetBrains, etc.)
rather than a standalone CLI. This implementation provides basic integration but may have
limitations compared to Claude Code.
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, Set

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class GitHubCopilotAgent(AgentInterface):
    """GitHub Copilot agent implementation.

    Provides integration with GitHub Copilot Chat through VS Code CLI.

    Note: GitHub Copilot operates primarily through IDE extensions. This implementation
    supports launching VS Code with Copilot extension. Session management capabilities
    are limited compared to Claude Code.

    Limitations:
    - No native session resume capability (VS Code manages editor sessions)
    - Session ID capture not directly supported (uses workspace-based detection)
    - Conversation export/import limited to VS Code extension data
    """

    def __init__(self, copilot_dir: Optional[Path] = None):
        """Initialize GitHub Copilot agent.

        Args:
            copilot_dir: GitHub Copilot data directory. Defaults to ~/.vscode/extensions/github.copilot-*
        """
        if copilot_dir is None:
            # Default to VS Code extension data directory
            vscode_dir = Path.home() / ".vscode"
            self.copilot_dir = vscode_dir
        else:
            self.copilot_dir = copilot_dir

    def launch_session(self, project_path: str) -> subprocess.Popen:
        """Launch VS Code with GitHub Copilot in a project directory.

        Args:
            project_path: Absolute path to project

        Returns:
            Subprocess handle for VS Code process

        Raises:
            ToolNotFoundError: If code command is not installed
        """
        require_tool("code", "launch VS Code with GitHub Copilot")

        return subprocess.Popen(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def resume_session(self, session_id: str, project_path: str) -> subprocess.Popen:
        """Resume VS Code in a project directory.

        Note: VS Code manages its own window sessions. The session_id parameter
        is currently ignored as VS Code will restore the last workspace state.

        Args:
            session_id: Session identifier (currently unused)
            project_path: Absolute path to project

        Returns:
            Subprocess handle for VS Code process

        Raises:
            ToolNotFoundError: If code command is not installed
        """
        require_tool("code", "resume VS Code with GitHub Copilot")

        # VS Code automatically restores previous session
        return subprocess.Popen(
            ["code", project_path],
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
        """Capture a session ID.

        Note: GitHub Copilot doesn't have a direct session ID concept like Claude Code.
        This implementation generates a workspace-based identifier.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds (unused for GitHub Copilot)
            poll_interval: Time between polls in seconds (unused)

        Returns:
            Generated session identifier based on workspace path and timestamp
        """
        # Generate a deterministic session ID based on workspace and current time
        # Format: copilot-{encoded_path}-{timestamp}
        encoded_path = self.encode_project_path(project_path)
        timestamp = int(time.time())
        session_id = f"copilot-{encoded_path}-{timestamp}"

        return session_id

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to a session file.

        Note: GitHub Copilot stores session data in VS Code workspace storage.
        This returns an approximate path.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            Path to workspace storage directory
        """
        # VS Code workspace storage
        workspace_storage = self.copilot_dir / "User" / "workspaceStorage"
        encoded = self.encode_project_path(project_path)
        return workspace_storage / encoded / "state.vscdb"

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a session exists.

        Note: For GitHub Copilot, we check if the workspace storage exists.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            True if workspace storage exists
        """
        session_file = self.get_session_file_path(session_id, project_path)
        # Check if workspace storage directory exists
        return session_file.parent.exists()

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs for a project.

        Note: GitHub Copilot doesn't maintain discrete session files.
        Returns empty set as sessions are managed by VS Code.

        Args:
            project_path: Absolute path to project

        Returns:
            Empty set (VS Code manages sessions internally)
        """
        # GitHub Copilot doesn't have discrete session files like Claude Code
        # VS Code manages workspace sessions internally
        return set()

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get the number of messages in a session.

        Note: GitHub Copilot doesn't expose conversation history in a parseable format.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            0 (message counting not supported)
        """
        # GitHub Copilot doesn't expose conversation history in a standard format
        return 0

    def encode_project_path(self, project_path: str) -> str:
        """Encode project path for storage identifiers.

        Uses simple encoding similar to Claude Code.

        Args:
            project_path: Absolute path to project

        Returns:
            Encoded path string
        """
        # Simple encoding: replace / and _ with -
        encoded = project_path.replace("/", "-").replace("_", "-")
        return encoded

    def get_agent_home_dir(self) -> Path:
        """Get the GitHub Copilot/VS Code home directory.

        Returns:
            Path to ~/.vscode directory
        """
        return self.copilot_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "github-copilot"
        """
        return "github-copilot"
