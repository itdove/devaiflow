"""Session ID capture logic for detecting new AI agent sessions.

This module provides a wrapper around AgentInterface for backward compatibility.
It delegates all operations to the configured AI agent backend.
"""

import subprocess
from pathlib import Path
from typing import Optional, Set

from devflow.agent import AgentInterface, create_agent_client


class SessionCapture:
    """Capture AI agent session IDs.

    This class provides backward compatibility while delegating to AgentInterface.
    """

    def __init__(self, claude_dir: Optional[Path] = None, agent: Optional[AgentInterface] = None):
        """Initialize session capture.

        Args:
            claude_dir: Agent home directory. Defaults to ~/.claude for Claude backend
            agent: Optional AgentInterface implementation. If not provided, defaults to Claude backend
        """
        if agent is not None:
            self.agent = agent
        else:
            # Default to Claude backend for backward compatibility
            self.agent = create_agent_client("claude", agent_home=claude_dir)

        # Store for backward compatibility (deprecated)
        self.claude_dir = self.agent.get_agent_home_dir()
        self.projects_dir = self.claude_dir / "projects"

    def encode_project_path(self, project_path: str) -> str:
        """Encode project path the same way the AI agent does.

        Args:
            project_path: Absolute path to project

        Returns:
            Encoded path string
        """
        return self.agent.encode_project_path(project_path)

    def get_session_dir(self, project_path: str) -> Path:
        """Get the session directory for a project.

        Args:
            project_path: Absolute path to project

        Returns:
            Path to sessions directory
        """
        encoded = self.encode_project_path(project_path)
        return self.projects_dir / encoded

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs for a project.

        Args:
            project_path: Absolute path to project

        Returns:
            Set of session UUIDs
        """
        return self.agent.get_existing_sessions(project_path)

    def launch_claude_code(self, project_path: str) -> subprocess.Popen:
        """Launch AI agent in a project directory.

        Deprecated: This method name is kept for backward compatibility.
        Use agent.launch_session() instead.

        Args:
            project_path: Absolute path to project

        Returns:
            Subprocess handle

        Raises:
            ToolNotFoundError: If agent command is not installed
        """
        return self.agent.launch_session(project_path)

    def capture_new_session(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """Capture a new AI agent session ID by monitoring file creation.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Session UUID if detected, None if timeout

        Raises:
            TimeoutError: If session not detected within timeout
        """
        return self.agent.capture_session_id(project_path, timeout, poll_interval)

    def resume_claude_code(self, session_id: str, project_path: str) -> subprocess.Popen:
        """Resume an existing AI agent session.

        Deprecated: This method name is kept for backward compatibility.
        Use agent.resume_session() instead.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project

        Returns:
            Subprocess handle

        Raises:
            ToolNotFoundError: If agent command is not installed
        """
        return self.agent.resume_session(session_id, project_path)

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a session file exists.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            True if session file exists
        """
        return self.agent.session_exists(session_id, project_path)

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get the number of messages in a session.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Number of lines in the file (approximate message count)
        """
        return self.agent.get_session_message_count(session_id, project_path)
