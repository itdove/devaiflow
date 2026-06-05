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
from typing import Optional, Set, List, Dict, Any


class AgentInterface(ABC):
    """Abstract base class for AI agent backends.

    Defines the interface that all AI agent backends must implement.
    Allows swapping between Claude Code, GitHub Copilot, ChatGPT, or other AI agents.

    All methods should handle errors appropriately and raise exceptions when operations fail.
    """

    @abstractmethod
    def launch_session(self, project_path: str, env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
        """Launch a new agent session in a project directory.

        Args:
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the launched agent

        Raises:
            ToolNotFoundError: If agent command is not installed
            RuntimeError: If launch fails
        """
        pass

    @abstractmethod
    def launch_with_prompt(
        self,
        project_path: str,
        initial_prompt: str,
        session_id: str,
        model_provider_profile: Optional[Dict[str, Any]] = None,
        skills_dirs: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
        config = None,
        env: Optional[Dict[str, str]] = None,
        headless: bool = False,
        auto_approve: bool = False,
    ) -> subprocess.Popen:
        """Launch agent with initial prompt (for new sessions).

        This method is used when creating new sessions that need an initial prompt
        sent to the agent. It combines launching and sending the prompt in one operation.

        Args:
            project_path: Absolute path to project
            initial_prompt: Initial prompt to send to the agent
            session_id: Session UUID to use
            model_provider_profile: Model provider profile dict (optional)
                Contains: base_url, auth_token, api_key, model_name, use_vertex,
                         vertex_project_id, vertex_region, env_vars
            skills_dirs: List of skill directories to add (optional, will be auto-discovered if None)
            workspace_path: Workspace path for auto-discovering workspace skills (optional)
            config: Configuration object for context files discovery (optional)
            env: Environment variables dict (optional, defaults to os.environ)
            headless: Run without interactive UI (agent processes prompt and exits)
            auto_approve: Auto-approve all tool permissions (file edits, commands)

        Returns:
            Subprocess handle for the launched agent

        Raises:
            ToolNotFoundError: If agent command is not installed
            RuntimeError: If launch fails

        Note:
            Skills discovery order (if skills_dirs is None):
            1. User-level: ~/.claude/skills/
            2. Workspace-level: <workspace>/.claude/skills/
            3. Hierarchical: $DEVAIFLOW_HOME/.claude/skills/
            4. Project-level: <project>/.claude/skills/
        """
        pass

    @abstractmethod
    def resume_session(self, session_id: str, project_path: str, env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
        """Resume an existing agent session.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

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

    def uses_tui(self) -> bool:
        """Whether this agent uses a full-screen TUI (alternate screen buffer).

        TUI agents (e.g. OpenCode, Crush) take over the entire terminal with a
        full-screen interface built on frameworks like Bubble Tea. When they
        exit, they may leave splash art or residual output on the screen that
        garbles subsequent CLI output.

        Non-TUI agents (e.g. Claude Code, Aider) use a standard terminal REPL
        and do not leave splash art on exit.

        GUI/IDE agents (e.g. Cursor, Windsurf) open a separate window and do
        not interact with the terminal at all.

        Returns:
            True if the agent uses a full-screen TUI.
            False otherwise (default).
        """
        return False

    def supports_permission_prompts(self) -> bool:
        """Whether this agent prompts the user before modifying files or running commands.

        Agents like Claude Code prompt before each file write or shell command unless
        explicitly told to skip permissions. Agents that auto-approve all tool calls
        should return False so that callers can warn users.

        Returns:
            True if the agent has a built-in permission system (default).
            False if the agent auto-approves all tool calls without user confirmation.
        """
        return True

    @abstractmethod
    def extract_token_usage(self, session_id: str, project_path: str) -> Optional[Dict[str, Any]]:
        """Extract token usage statistics from a session.

        Parses the agent's conversation/session file to extract token usage data
        including input tokens, output tokens, cache tokens, etc.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Dictionary with token usage statistics, or None if:
            - Agent doesn't support token tracking
            - Session file doesn't exist
            - Session file has no token usage data

            Expected keys in returned dict (when supported):
            - input_tokens: Total input tokens consumed
            - output_tokens: Total output tokens generated
            - cache_creation_input_tokens: Tokens written to prompt cache
            - cache_read_input_tokens: Tokens read from cache (90% cost savings)
            - message_count: Number of messages with usage data
            - total_tokens: Sum of input + output tokens

        Note:
            Only Claude Code fully supports token tracking. Other agents
            (GitHub Copilot, Cursor, Windsurf) return None.
        """
        pass
