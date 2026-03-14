"""Claude Code agent implementation.

This module implements the AgentInterface for Claude Code, encapsulating all
Claude-specific logic that was previously in SessionCapture.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Set, Dict

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

    def launch_session(
        self,
        project_path: str,
        model_provider_profile: Optional[Dict[str, any]] = None,
    ) -> subprocess.Popen:
        """Launch a new Claude Code session in a project directory.

        Args:
            project_path: Absolute path to project
            model_provider_profile: Model provider profile dict (optional)
                Contains: base_url, auth_token, api_key, model_name, use_vertex,
                         vertex_project_id, vertex_region, env_vars

        Returns:
            Subprocess handle for the launched Claude Code process

        Raises:
            ToolNotFoundError: If claude command is not installed
        """
        require_tool("claude", "launch Claude Code session")

        # Build environment and command based on profile
        env, cmd = self._build_env_and_cmd(model_provider_profile)

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def resume_session(
        self,
        session_id: str,
        project_path: str,
        model_provider_profile: Optional[Dict[str, any]] = None,
    ) -> subprocess.Popen:
        """Resume an existing Claude Code session.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project
            model_provider_profile: Model provider profile dict (optional)

        Returns:
            Subprocess handle for the resumed Claude Code process

        Raises:
            ToolNotFoundError: If claude command is not installed
        """
        require_tool("claude", "resume Claude Code session")

        # Build environment (command is always claude --resume for resume)
        env, _ = self._build_env_and_cmd(model_provider_profile)
        cmd = ["claude", "--resume", session_id]

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=env,
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

    def _build_env_and_cmd(
        self, model_provider_profile: Optional[Dict[str, any]] = None
    ) -> tuple[Dict[str, str], list[str]]:
        """Build environment variables and command from model provider profile.

        Args:
            model_provider_profile: Model provider profile dict (optional)

        Returns:
            Tuple of (environment dict, command list)
        """
        # Start with copy of current environment
        env = os.environ.copy()

        # Default command
        cmd = ["claude", "code"]

        # If no profile specified, return defaults
        if not model_provider_profile:
            return env, cmd

        # Apply profile settings
        if model_provider_profile.get("base_url"):
            env["ANTHROPIC_BASE_URL"] = model_provider_profile["base_url"]

        if model_provider_profile.get("auth_token"):
            env["ANTHROPIC_AUTH_TOKEN"] = model_provider_profile["auth_token"]

        if "api_key" in model_provider_profile and model_provider_profile["api_key"] is not None:
            env["ANTHROPIC_API_KEY"] = model_provider_profile["api_key"]

        if model_provider_profile.get("use_vertex"):
            env["CLAUDE_CODE_USE_VERTEX"] = "1"

            # Set Vertex-specific env vars if provided
            if model_provider_profile.get("vertex_project_id"):
                env["ANTHROPIC_VERTEX_PROJECT_ID"] = model_provider_profile["vertex_project_id"]

            if model_provider_profile.get("vertex_region"):
                env["ANTHROPIC_VERTEX_REGION"] = model_provider_profile["vertex_region"]
        else:
            # Explicitly unset Vertex flag if not using Vertex
            env.pop("CLAUDE_CODE_USE_VERTEX", None)

        # Apply additional environment variables
        if model_provider_profile.get("env_vars"):
            env.update(model_provider_profile["env_vars"])

        # Build command with model name if specified
        if model_provider_profile.get("model_name"):
            cmd = ["claude", "--model", model_provider_profile["model_name"]]

        return env, cmd
