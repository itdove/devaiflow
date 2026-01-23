"""Cursor agent implementation.

This module implements the AgentInterface for Cursor, an AI-first code editor
built on VS Code with integrated AI capabilities.

⚠️  EXPERIMENTAL - NOT FULLY TESTED
This agent implementation has not been fully tested. It may have limitations or bugs.
Only Claude Code has been comprehensively tested. Use at your own risk.

Cursor provides a CLI and session management similar to VS Code but with
enhanced AI integration features.
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, Set

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class CursorAgent(AgentInterface):
    """Cursor agent implementation.

    Provides integration with Cursor AI editor, which offers built-in AI chat
    and code generation capabilities.

    Cursor operates similarly to VS Code but with native AI integration.
    Session management uses Cursor's workspace system.

    Features:
    - Launch and resume Cursor editor sessions
    - Workspace-based session identification
    - Integration with Cursor's AI chat

    Limitations:
    - Session ID detection limited to workspace-based identifiers
    - Conversation export depends on Cursor's internal storage format
    - Message counting may not reflect exact AI chat history
    """

    def __init__(self, cursor_dir: Optional[Path] = None):
        """Initialize Cursor agent.

        Args:
            cursor_dir: Cursor data directory. Defaults to ~/.cursor
        """
        if cursor_dir is None:
            cursor_dir = Path.home() / ".cursor"
        self.cursor_dir = cursor_dir
        self.workspace_storage = cursor_dir / "User" / "workspaceStorage"

    def launch_session(self, project_path: str) -> subprocess.Popen:
        """Launch Cursor in a project directory.

        Args:
            project_path: Absolute path to project

        Returns:
            Subprocess handle for Cursor process

        Raises:
            ToolNotFoundError: If cursor command is not installed
        """
        require_tool("cursor", "launch Cursor editor")

        return subprocess.Popen(
            ["cursor", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def resume_session(self, session_id: str, project_path: str) -> subprocess.Popen:
        """Resume Cursor in a project directory.

        Cursor automatically restores the previous workspace state including
        open files, AI chat history, and editor layout.

        Args:
            session_id: Session identifier (used for tracking, Cursor manages state)
            project_path: Absolute path to project

        Returns:
            Subprocess handle for Cursor process

        Raises:
            ToolNotFoundError: If cursor command is not installed
        """
        require_tool("cursor", "resume Cursor editor")

        # Cursor automatically restores previous workspace session
        return subprocess.Popen(
            ["cursor", project_path],
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

        Generates a workspace-based identifier that can be used to track
        Cursor sessions across DevAIFlow operations.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Generated session identifier
        """
        # Generate session ID based on workspace and timestamp
        # Format: cursor-{encoded_path}-{timestamp}
        encoded_path = self.encode_project_path(project_path)
        timestamp = int(time.time())
        session_id = f"cursor-{encoded_path}-{timestamp}"

        return session_id

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to Cursor's workspace state file.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            Path to workspace state database
        """
        # Cursor stores workspace state in workspace storage
        encoded = self.encode_project_path(project_path)

        # Look for workspace storage directory matching this project
        if self.workspace_storage.exists():
            # Cursor creates unique IDs for workspaces, scan for matching folder
            for workspace_dir in self.workspace_storage.iterdir():
                if workspace_dir.is_dir():
                    workspace_json = workspace_dir / "workspace.json"
                    if workspace_json.exists():
                        # Could parse workspace.json to match project_path
                        # For now, return first matching state file
                        state_file = workspace_dir / "state.vscdb"
                        if state_file.exists():
                            return state_file

        # Fallback: return expected path even if it doesn't exist yet
        return self.workspace_storage / encoded / "state.vscdb"

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a Cursor workspace session exists.

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

        Note: Cursor manages workspace sessions internally. This returns an empty
        set as discrete session files are not maintained.

        Args:
            project_path: Absolute path to project

        Returns:
            Empty set (Cursor manages sessions via workspace storage)
        """
        # Cursor doesn't maintain discrete session files
        # Sessions are tracked via workspace storage directories
        return set()

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get approximate message count from Cursor AI chat.

        Note: Cursor stores AI chat history in workspace state, but the format
        is not publicly documented. Returns 0 as precise counting is not supported.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            0 (message counting not supported)
        """
        # Cursor's AI chat history is stored in workspace state database
        # Format is not publicly documented, so we cannot reliably count messages
        return 0

    def encode_project_path(self, project_path: str) -> str:
        """Encode project path for storage identifiers.

        Uses the same encoding as Claude Code for consistency.

        Args:
            project_path: Absolute path to project

        Returns:
            Encoded path string
        """
        # Same encoding as Claude Code: replace / and _ with -
        encoded = project_path.replace("/", "-").replace("_", "-")
        return encoded

    def get_agent_home_dir(self) -> Path:
        """Get Cursor's home directory.

        Returns:
            Path to ~/.cursor directory
        """
        return self.cursor_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "cursor"
        """
        return "cursor"
