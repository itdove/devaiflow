"""Abstract interface for AI agent backends.

This module defines the abstract base class that all AI agent backends must implement.
It provides a common interface for operations like:
- Launching agent sessions
- Resuming agent sessions
- Capturing session IDs
- Managing session files
- Checking session existence

Following the IssueTrackerClient pattern from devflow/issue_tracker/interface.py.
"""

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Set


class AgentInterface(ABC):
    """Abstract base class for AI agent backends.

    Defines the interface that all AI agent backends must implement.
    Allows swapping between Claude Code, GitHub Copilot, ChatGPT, or other AI agents.

    All methods should handle errors appropriately and raise exceptions when operations fail.
    """

    @abstractmethod
    def launch_session(self, project_path: str) -> subprocess.Popen:
        """Launch a new agent session in a project directory.

        Args:
            project_path: Absolute path to project

        Returns:
            Subprocess handle for the launched agent

        Raises:
            ToolNotFoundError: If agent command is not installed
            RuntimeError: If launch fails
        """
        pass

    @abstractmethod
    def resume_session(self, session_id: str, project_path: str) -> subprocess.Popen:
        """Resume an existing agent session.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project

        Returns:
            Subprocess handle for the resumed agent

        Raises:
            ToolNotFoundError: If agent command is not installed
            RuntimeError: If resume fails
        """
        pass

    @abstractmethod
    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """Capture a new agent session ID by monitoring file creation.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Session UUID if detected, None if timeout

        Raises:
            TimeoutError: If session not detected within timeout
        """
        pass

    @abstractmethod
    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to a session file.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Path to the session file
        """
        pass

    @abstractmethod
    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a session file exists.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            True if session file exists
        """
        pass

    @abstractmethod
    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs for a project.

        Args:
            project_path: Absolute path to project

        Returns:
            Set of session UUIDs
        """
        pass

    @abstractmethod
    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get the number of messages in a session.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Number of messages in the session (approximate)
        """
        pass

    @abstractmethod
    def encode_project_path(self, project_path: str) -> str:
        """Encode project path the same way the agent does.

        Different agents may encode project paths differently for their internal storage.

        Args:
            project_path: Absolute path to project

        Returns:
            Encoded path string
        """
        pass

    @abstractmethod
    def get_agent_home_dir(self) -> Path:
        """Get the agent's home directory where it stores sessions.

        Returns:
            Path to agent home directory (e.g., ~/.claude for Claude Code)
        """
        pass

    @abstractmethod
    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            Agent name (e.g., "claude", "copilot", "chatgpt")
        """
        pass
