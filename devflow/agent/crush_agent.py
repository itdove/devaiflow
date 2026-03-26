"""Crush agent implementation.

This module implements the AgentInterface for Crush (formerly OpenCode), a glamorous
agentic coding CLI tool from Charmbracelet.

⚠️  EXPERIMENTAL - NOT FULLY TESTED
This agent implementation has not been fully tested. It may have limitations or bugs.
Only Claude Code has been comprehensively tested. Use at your own risk.

Crush is a terminal-based AI coding assistant with multi-model support, session-based
workflows, LSP integration, and MCP extensibility.
"""

import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Optional, Set, List, Dict, Any

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class CrushAgent(AgentInterface):
    """Crush agent implementation.

    Provides integration with Crush AI coding assistant, a TUI-based CLI tool
    for AI pair programming with multi-model support.

    Crush uses SQLite for session storage and supports multiple AI providers
    including OpenAI, Anthropic, Google Gemini, Groq, AWS Bedrock, and more.

    Features:
    - Launch and manage Crush CLI sessions
    - SQLite-based session storage
    - Multi-model AI support
    - LSP integration for code-aware context
    - MCP plugin extensibility

    Limitations:
    - Session detection may be challenging (SQLite-based, not file-based)
    - No built-in prompt passing via CLI (must use interactive mode)
    - Session resumption requires session UUID
    - Message counting requires SQLite queries

    Storage:
        Sessions are stored in SQLite database at:
        ~/.local/share/crush/crush.db (or custom --data-dir)

    Note:
        Crush doesn't have a specific home directory environment variable.
        It uses platform-specific defaults following XDG spec on Linux.
    """

    def __init__(self, crush_dir: Optional[Path] = None):
        """Initialize Crush agent.

        Args:
            crush_dir: Crush data directory. Defaults to ~/.local/share/crush
        """
        if crush_dir is None:
            # Follow XDG Base Directory Specification on Linux/Unix
            # On macOS/Windows, fallback to ~/.local/share/crush
            if os.environ.get("XDG_DATA_HOME"):
                crush_dir = Path(os.environ["XDG_DATA_HOME"]) / "crush"
            else:
                crush_dir = Path.home() / ".local" / "share" / "crush"

        self.crush_dir = Path(crush_dir)
        self.db_path = self.crush_dir / "crush.db"

    def launch_session(
        self,
        project_path: str,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen:
        """Launch a new Crush session in a project directory.

        Args:
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the launched Crush process

        Raises:
            ToolNotFoundError: If crush command is not installed
        """
        require_tool("crush", "launch Crush AI assistant")

        # Prepare environment
        final_env = env if env is not None else os.environ.copy()

        # Launch Crush in the project directory
        return subprocess.Popen(
            ["crush"],
            cwd=project_path,
            env=final_env,
            # Crush needs terminal interaction for TUI
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
        """Launch Crush with initial prompt.

        Note: Crush doesn't support sending prompts via CLI arguments in the same
        way as Claude Code. The session_id is used to resume a specific session,
        but the initial_prompt must be entered interactively by the user.

        Args:
            project_path: Absolute path to project
            initial_prompt: Initial prompt (user must enter manually in TUI)
            session_id: Session UUID (used for --session flag)
            model_provider_profile: Model provider profile (optional)
            skills_dirs: Skills directories (ignored - Crush doesn't support)
            workspace_path: Workspace path (ignored)
            config: Configuration object (ignored)
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for Crush process

        Raises:
            ToolNotFoundError: If crush command is not installed
        """
        require_tool("crush", "launch Crush AI assistant")

        # Prepare environment
        final_env = env if env is not None else os.environ.copy()

        # Build command
        # Crush doesn't support passing initial prompts via CLI
        # We can only open a specific session with --session flag
        cmd = ["crush", "--session", session_id]

        # Note: Skills directories are not supported by Crush
        # Model provider configuration would need to be set in ~/.config/crush/crush.json

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=final_env,
            # Crush needs terminal interaction for TUI
        )

    def resume_session(
        self,
        session_id: str,
        project_path: str,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen:
        """Resume an existing Crush session.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the resumed Crush process

        Raises:
            ToolNotFoundError: If crush command is not installed
        """
        require_tool("crush", "resume Crush AI assistant")

        # Prepare environment
        final_env = env if env is not None else os.environ.copy()

        # Resume session by UUID
        cmd = ["crush", "--session", session_id]

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=final_env,
            # Crush needs terminal interaction for TUI
        )

    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """Capture a new Crush session ID by monitoring SQLite database.

        This is challenging with Crush since sessions are stored in SQLite,
        not individual files. We'll need to query the database for new sessions.

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

        # Launch Crush
        process = self.launch_session(project_path)

        # Poll for new session in database
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
        raise TimeoutError(
            f"Failed to detect new Crush session after {timeout}s.\n"
            f"Database location: {self.db_path}\n"
            f"You may need to enter the session ID manually.\n"
            f"Tip: Run 'crush session list' to see available sessions."
        )

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to the session database.

        Note: Crush stores all sessions in a single SQLite database,
        not individual session files.

        Args:
            session_id: Session UUID (not used for path, all sessions in one DB)
            project_path: Absolute path to project (not used)

        Returns:
            Path to the Crush SQLite database
        """
        return self.db_path

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a session exists in the Crush database.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            True if session exists in database
        """
        if not self.db_path.exists():
            return False

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Query for session by ID
            cursor.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
            result = cursor.fetchone()

            conn.close()
            return result is not None
        except sqlite3.Error:
            return False

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs from Crush database.

        Args:
            project_path: Absolute path to project (not used, all sessions global)

        Returns:
            Set of session UUIDs
        """
        if not self.db_path.exists():
            return set()

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Get all session IDs
            cursor.execute("SELECT id FROM sessions")
            results = cursor.fetchall()

            conn.close()
            return {row[0] for row in results}
        except sqlite3.Error:
            return set()

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get the number of messages in a Crush session.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Number of messages in the session
        """
        if not self.db_path.exists():
            return 0

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Count messages for this session
            cursor.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                (session_id,)
            )
            result = cursor.fetchone()

            conn.close()
            return result[0] if result else 0
        except sqlite3.Error:
            return 0

    def encode_project_path(self, project_path: str) -> str:
        """Encode project path.

        Note: Crush doesn't encode project paths for storage since it uses
        a global SQLite database, not per-project directories.

        Args:
            project_path: Absolute path to project

        Returns:
            Original path (no encoding needed)
        """
        return project_path

    def get_agent_home_dir(self) -> Path:
        """Get the Crush data directory where it stores the database.

        Returns:
            Path to Crush data directory (e.g., ~/.local/share/crush)
        """
        return self.crush_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "crush"
        """
        return "crush"

    def extract_token_usage(self, session_id: str, project_path: str) -> Optional[Dict[str, Any]]:
        """Extract token usage statistics from session.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            None - Crush does not expose token usage data

        TODO: Implement token tracking if Crush SQLite database stores usage data
        """
        return None
