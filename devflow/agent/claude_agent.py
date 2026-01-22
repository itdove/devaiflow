"""Claude Code agent implementation.

This module implements the AgentInterface for Claude Code, encapsulating all
Claude-specific logic that was previously in SessionCapture.
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, Set

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class ClaudeAgent(AgentInterface):
    """Claude Code agent implementation.

    Encapsulates all Claude Code-specific operations including:
    - Session launching and resuming
    - Session ID capture
    - Session file management
    - Project path encoding
    """

    def __init__(self, claude_dir: Optional[Path] = None):
        """Initialize Claude agent.

        Args:
            claude_dir: Claude Code directory. Defaults to ~/.claude
        """
        if claude_dir is None:
            claude_dir = Path.home() / ".claude"
        self.claude_dir = claude_dir
        self.projects_dir = claude_dir / "projects"

    def launch_session(self, project_path: str) -> subprocess.Popen:
        """Launch a new Claude Code session in a project directory.

        Args:
            project_path: Absolute path to project

        Returns:
            Subprocess handle for the launched Claude Code process

        Raises:
            ToolNotFoundError: If claude command is not installed
        """
        require_tool("claude", "launch Claude Code session")

        return subprocess.Popen(
            ["claude", "code"],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def resume_session(self, session_id: str, project_path: str) -> subprocess.Popen:
        """Resume an existing Claude Code session.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project

        Returns:
            Subprocess handle for the resumed Claude Code process

        Raises:
            ToolNotFoundError: If claude command is not installed
        """
        require_tool("claude", "resume Claude Code session")

        return subprocess.Popen(
            ["claude", "--resume", session_id],
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
        """Capture a new Claude Code session ID by monitoring file creation.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Session UUID if detected, None if timeout

        Raises:
            TimeoutError: If session not detected within timeout
        """
        # Get existing sessions before launch
        before = self.get_existing_sessions(project_path)

        # Launch Claude Code
        process = self.launch_session(project_path)

        # Poll for new session file
        elapsed = 0.0
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval

            after = self.get_existing_sessions(project_path)
            new_sessions = after - before

            if new_sessions:
                # Return the first new session found
                session_id = new_sessions.pop()
                return session_id

        # Timeout - session not detected
        session_dir = self._get_session_dir(project_path)
        encoded_path = self.encode_project_path(project_path)
        raise TimeoutError(
            f"Failed to detect new Claude Code session after {timeout}s.\n"
            f"Expected location: {session_dir}\n"
            f"Encoded path: {encoded_path}\n"
            f"You may need to enter the session ID manually.\n"
            f"Tip: Run 'claude --resume' to see available sessions."
        )

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to a Claude Code session file.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Path to the .jsonl session file
        """
        session_dir = self._get_session_dir(project_path)
        return session_dir / f"{session_id}.jsonl"

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a Claude Code session file exists.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            True if session file exists
        """
        session_file = self.get_session_file_path(session_id, project_path)
        return session_file.exists()

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing Claude Code session IDs for a project.

        Args:
            project_path: Absolute path to project

        Returns:
            Set of session UUIDs
        """
        session_dir = self._get_session_dir(project_path)
        if not session_dir.exists():
            return set()

        return {f.stem for f in session_dir.glob("*.jsonl")}

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get the number of messages in a Claude Code session.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Number of lines in the .jsonl file (approximate message count)
        """
        session_file = self.get_session_file_path(session_id, project_path)

        if not session_file.exists():
            return 0

        with open(session_file, "r") as f:
            return sum(1 for _ in f)

    def encode_project_path(self, project_path: str) -> str:
        """Encode project path the same way Claude Code does.

        Claude Code replaces / with - in paths (keeps the leading -)
        and also replaces _ with -.

        Args:
            project_path: Absolute path to project

        Returns:
            Encoded path string
        """
        # Claude Code replaces / with - in paths (keeps the leading -)
        # AND also replaces _ with -
        encoded = project_path.replace("/", "-").replace("_", "-")
        return encoded

    def get_agent_home_dir(self) -> Path:
        """Get the Claude Code home directory where it stores sessions.

        Returns:
            Path to ~/.claude directory
        """
        return self.claude_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "claude"
        """
        return "claude"

    def _get_session_dir(self, project_path: str) -> Path:
        """Get the session directory for a project.

        Args:
            project_path: Absolute path to project

        Returns:
            Path to sessions directory
        """
        encoded = self.encode_project_path(project_path)
        return self.projects_dir / encoded
