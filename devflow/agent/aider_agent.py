"""Aider agent implementation.

This module implements the AgentInterface for Aider, a command-line AI coding
assistant that uses a git-first approach.

⚠️  EXPERIMENTAL - NOT FULLY TESTED
This agent implementation has not been fully tested. It may have limitations or bugs.
Only Claude Code has been comprehensively tested. Use at your own risk.

Aider is a CLI-based AI pair programming tool that makes every AI edit a git commit.
It runs directly in the terminal and uses git branches for session management.
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, Set, List, Dict, Any

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class AiderAgent(AgentInterface):
    """Aider agent implementation.

    Provides integration with Aider AI coding assistant, a git-first CLI tool
    for AI pair programming.

    Aider operates as a command-line interface that directly modifies files and
    creates git commits for each change. It uses chat history files for persistence.

    Features:
    - Launch and manage Aider CLI sessions
    - Git-based workflow with automatic commits
    - Chat history persistence
    - Branch-based session isolation

    Limitations:
    - Session ID detection is timestamp-based (not true session IDs)
    - Chat history must be explicitly saved/loaded
    - Message counting approximates based on chat history files
    - Resume functionality requires manual chat history management
    - No built-in session tracking like Claude Code

    Note:
        Aider doesn't have traditional session IDs. Instead, sessions are
        identified by git branches and chat history files. This implementation
        uses timestamp-based identifiers for compatibility with DevAIFlow.
    """

    def __init__(self, aider_dir: Optional[Path] = None):
        """Initialize Aider agent.

        Args:
            aider_dir: Aider data directory. Defaults to ~/.aider
        """
        if aider_dir is None:
            aider_dir = Path.home() / ".aider"
        self.aider_dir = aider_dir
        self.chat_history_dir = aider_dir / "chat_history"

        # Ensure directories exist
        self.aider_dir.mkdir(parents=True, exist_ok=True)
        self.chat_history_dir.mkdir(parents=True, exist_ok=True)

    def launch_session(self, project_path: str, env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
        """Launch Aider in a project directory.

        Args:
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for Aider process

        Raises:
            ToolNotFoundError: If aider command is not installed
        """
        require_tool("aider", "launch Aider AI assistant")

        # Launch Aider in the project directory
        # Basic launch without specific files (user will add them in session)
        return subprocess.Popen(
            ["aider"],
            cwd=project_path,
            env=env,
            # Aider needs terminal interaction
        )

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
    ) -> subprocess.Popen:
        """Launch Aider with initial prompt.

        Note: Aider doesn't support sending prompts via CLI arguments in the same
        way as Claude Code. The initial_prompt is saved to a file, and the user
        must manually load it or paste it into the Aider chat interface.

        Args:
            project_path: Absolute path to project
            initial_prompt: Initial prompt (saved to file for user reference)
            session_id: Session UUID (used for chat history filename)
            model_provider_profile: Model provider profile (optional)
            skills_dirs: Skills directories (ignored - Aider doesn't support)
            workspace_path: Workspace path (ignored)
            config: Configuration object (ignored)
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for Aider process

        Raises:
            ToolNotFoundError: If aider command is not installed
        """
        require_tool("aider", "launch Aider AI assistant")

        # Save initial prompt to a file for user reference
        prompt_file = self.chat_history_dir / f"{session_id}_initial_prompt.txt"
        prompt_file.write_text(initial_prompt)

        # Build command with optional model specification
        cmd = ["aider"]

        # Add model if specified in profile
        if model_provider_profile and model_provider_profile.get("model_name"):
            cmd.extend(["--model", model_provider_profile["model_name"]])

        # Set chat history file for this session
        chat_history_file = self.chat_history_dir / f"{session_id}_chat.txt"
        cmd.extend(["--chat-history-file", str(chat_history_file)])

        # Launch Aider
        # Note: User will need to manually paste the initial prompt or use /load command
        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=env,
            # Aider needs terminal interaction
        )

    def resume_session(self, session_id: str, project_path: str, env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
        """Resume an Aider session.

        Aider sessions are resumed by loading the chat history file.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for Aider process

        Raises:
            ToolNotFoundError: If aider command is not installed
        """
        require_tool("aider", "resume Aider AI assistant")

        # Resume by loading chat history file
        chat_history_file = self.chat_history_dir / f"{session_id}_chat.txt"

        cmd = ["aider"]
        if chat_history_file.exists():
            cmd.extend(["--chat-history-file", str(chat_history_file)])

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=env,
            # Aider needs terminal interaction
        )

    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """Capture a session ID for Aider.

        Since Aider doesn't have traditional session IDs, this generates a
        timestamp-based identifier that can be used for chat history tracking.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds (unused)
            poll_interval: Time between polls in seconds (unused)

        Returns:
            Generated session identifier
        """
        # Generate timestamp-based session ID
        # Format: aider-{encoded_path}-{timestamp}
        encoded_path = self.encode_project_path(project_path)
        timestamp = int(time.time())
        session_id = f"aider-{encoded_path}-{timestamp}"

        return session_id

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to Aider's chat history file for this session.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            Path to chat history file
        """
        return self.chat_history_dir / f"{session_id}_chat.txt"

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if an Aider session's chat history exists.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            True if chat history file exists
        """
        chat_file = self.get_session_file_path(session_id, project_path)
        return chat_file.exists()

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs for a project.

        Searches for chat history files matching the project path.

        Args:
            project_path: Absolute path to project

        Returns:
            Set of session identifiers
        """
        encoded_path = self.encode_project_path(project_path)
        sessions = set()

        if not self.chat_history_dir.exists():
            return sessions

        # Look for chat files matching this project
        for chat_file in self.chat_history_dir.glob(f"aider-{encoded_path}-*_chat.txt"):
            # Extract session ID from filename
            # Format: aider-{encoded_path}-{timestamp}_chat.txt
            filename = chat_file.stem  # Remove .txt
            if filename.endswith("_chat"):
                session_id = filename[:-5]  # Remove _chat
                sessions.add(session_id)

        return sessions

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get approximate message count from Aider chat history.

        Counts lines in the chat history file as a rough approximation.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            Approximate message count (0 if file doesn't exist)
        """
        chat_file = self.get_session_file_path(session_id, project_path)

        if not chat_file.exists():
            return 0

        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                # Count non-empty lines as approximate message count
                return sum(1 for line in f if line.strip())
        except Exception:
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
        """Get Aider's home directory.

        Returns:
            Path to ~/.aider directory
        """
        return self.aider_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "aider"
        """
        return "aider"

    def extract_token_usage(self, session_id: str, project_path: str) -> Optional[Dict[str, Any]]:
        """Extract token usage statistics from session.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            None - Aider does not expose token usage data

        TODO: Implement token tracking if Aider provides usage data in chat history
        """
        return None
