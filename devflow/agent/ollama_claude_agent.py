"""Ollama + Claude Code agent implementation.

This module implements the AgentInterface for Ollama's Claude Code launcher,
enabling local model support through the `ollama launch claude` command.

Ollama provides the simplest way to use local models with Claude Code:
- Zero configuration required (no environment variables)
- Automatic server management (Ollama handles the API server)
- Works with any Ollama model
- Full Claude Code integration (sessions, skills, resume)

Model Selection Priority:
1. DAF config (`config.ollama.default_model` or model provider profile)
2. Environment variable (`OLLAMA_MODEL`)
3. Ollama default from `~/.ollama/config.json`
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Set, List, Dict, Any

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class OllamaClaudeAgent(AgentInterface):
    """Ollama + Claude Code agent implementation.

    Uses `ollama launch claude` to run Claude Code with local models.
    This is simpler than using llama.cpp with environment variables:
    - No ANTHROPIC_BASE_URL configuration needed
    - No server management required
    - Automatic model selection from config/env/default

    Example usage:
        >>> from devflow.agent import create_agent_client
        >>> agent = create_agent_client("ollama")
        >>> agent.launch_session("/path/to/project")

    Note:
        Ollama must be installed and running. Install from: https://ollama.com
    """

    def __init__(self, ollama_dir: Optional[Path] = None):
        """Initialize Ollama Claude agent.

        Args:
            ollama_dir: Ollama data directory. Defaults to ~/.ollama
        """
        if ollama_dir is None:
            ollama_dir = Path.home() / ".ollama"
        self.ollama_dir = ollama_dir

        # Claude Code sessions are stored in the same location regardless of launcher
        self.claude_dir = Path.home() / ".claude"
        self.projects_dir = self.claude_dir / "projects"

    def launch_session(
        self,
        project_path: str,
        model_provider_profile: Optional[Dict[str, Any]] = None,
        session_name: Optional[str] = None,
        profile_name: Optional[str] = None,
        enforcement_source: Optional[str] = None,
    ) -> subprocess.Popen:
        """Launch Claude Code via Ollama with a local model.

        Args:
            project_path: Absolute path to project
            model_provider_profile: Model provider profile dict (optional)
                Contains: model_name (Ollama model to use)
            session_name: Session name for audit logging (optional)
            profile_name: Profile name for audit logging (optional)
            enforcement_source: Enforcement source for audit logging (optional)

        Returns:
            Subprocess handle for the launched process

        Raises:
            ToolNotFoundError: If ollama command is not installed
        """
        require_tool("ollama", "launch Claude Code with Ollama")

        # Audit log: Track model provider usage when launching session
        if session_name:
            from devflow.utils.audit_log import log_model_provider_usage
            model_name = self._get_model_name(model_provider_profile)
            log_model_provider_usage(
                event_type="session_launched",
                session_name=session_name,
                profile_name=profile_name,
                enforcement_source=enforcement_source,
                model_name=model_name,
                base_url="ollama://local",
                use_vertex=False,
            )

        # Build command: ollama launch claude [--model <model>]
        cmd = ["ollama", "launch", "claude"]

        # Determine model from config/env/default (priority order)
        model = self._get_model_name(model_provider_profile)
        if model:
            cmd.extend(["--model", model])

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=os.environ.copy(),
            # Do NOT redirect stdout/stderr - Claude Code needs terminal interaction
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
        session_name: Optional[str] = None,
        profile_name: Optional[str] = None,
        enforcement_source: Optional[str] = None,
    ) -> subprocess.Popen:
        """Launch Claude Code via Ollama with initial prompt (for new sessions).

        Note: The ollama launch claude command doesn't currently support
        --session-id or --add-dir flags directly. This implementation will
        launch Claude Code and users will need to manually send the prompt.

        In the future, when Ollama supports these flags, this can be updated
        to pass them through.

        Args:
            project_path: Absolute path to project
            initial_prompt: Initial prompt (currently not sent automatically)
            session_id: Session UUID (currently not used)
            model_provider_profile: Model provider profile dict (optional)
            skills_dirs: Skills directories (currently not used)
            session_name: Session name for audit logging (optional)
            profile_name: Profile name for audit logging (optional)
            enforcement_source: Enforcement source for audit logging (optional)
            workspace_path: Workspace path (currently not used)
            config: Configuration object (currently not used)

        Returns:
            Subprocess handle for the launched process

        Raises:
            ToolNotFoundError: If ollama command is not installed

        TODO: Update when ollama launch claude supports --session-id and --add-dir
        """
        # For now, ollama launch claude doesn't support --session-id or initial prompts
        # We launch Claude Code and rely on Claude's session management
        # Users will need to send the initial prompt manually

        require_tool("ollama", "launch Claude Code with Ollama")

        # Audit log: Track model provider usage when launching session
        if session_name:
            from devflow.utils.audit_log import log_model_provider_usage
            model_name = self._get_model_name(model_provider_profile)
            log_model_provider_usage(
                event_type="session_launched",
                session_name=session_name,
                profile_name=profile_name,
                enforcement_source=enforcement_source,
                model_name=model_name,
                base_url="ollama://local",
                use_vertex=False,
            )

        # Build command: ollama launch claude [--model <model>]
        cmd = ["ollama", "launch", "claude"]

        # Determine model from config/env/default (priority order)
        model = self._get_model_name(model_provider_profile)
        if model:
            cmd.extend(["--model", model])

        # TODO: When ollama supports these flags, add them:
        # cmd.extend(["--session-id", session_id, initial_prompt])
        # for skills_dir in skills_dirs or []:
        #     cmd.extend(["--add-dir", skills_dir])

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=os.environ.copy(),
            # Do NOT redirect stdout/stderr - Claude Code needs terminal interaction
        )

    def resume_session(
        self,
        session_id: str,
        project_path: str,
        model_provider_profile: Optional[Dict[str, Any]] = None,
    ) -> subprocess.Popen:
        """Resume an existing Claude Code session via Ollama.

        Note: Session resume works the same as regular Claude Code since
        sessions are stored in ~/.claude regardless of how Claude was launched.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project
            model_provider_profile: Model provider profile dict (optional)

        Returns:
            Subprocess handle for the resumed process

        Raises:
            ToolNotFoundError: If ollama or claude command is not installed
        """
        # Try ollama launch claude first, fall back to regular claude --resume
        try:
            require_tool("ollama", "resume Claude Code session with Ollama")
            cmd = ["ollama", "launch", "claude"]

            # Determine model from config/env/default
            model = self._get_model_name(model_provider_profile)
            if model:
                cmd.extend(["--model", model])

            # TODO: When ollama supports --resume, use it:
            # cmd.extend(["--resume", session_id])

            return subprocess.Popen(
                cmd,
                cwd=project_path,
                env=os.environ.copy(),
                # Do NOT redirect stdout/stderr - Claude Code needs terminal interaction
            )
        except Exception:
            # Fall back to regular claude --resume
            require_tool("claude", "resume Claude Code session")
            return subprocess.Popen(
                ["claude", "--resume", session_id],
                cwd=project_path,
                env=os.environ.copy(),
                # Do NOT redirect stdout/stderr - Claude Code needs terminal interaction
            )

    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """Capture a new session ID by monitoring Claude file creation.

        Sessions are stored in ~/.claude/projects regardless of launcher,
        so this uses the same logic as ClaudeAgent.

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

        # Launch Claude Code via Ollama
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
            f"Tip: Check ~/.claude/projects/ for session files."
        )

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to a session file.

        Sessions are stored in ~/.claude regardless of how Claude was launched.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Path to the .jsonl session file
        """
        session_dir = self._get_session_dir(project_path)
        return session_dir / f"{session_id}.jsonl"

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a session file exists.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            True if session file exists
        """
        session_file = self.get_session_file_path(session_id, project_path)
        return session_file.exists()

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs for a project.

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
        """Get the number of messages in a session.

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
        # Same encoding as Claude Code
        encoded = project_path.replace("/", "-").replace("_", "-")
        return encoded

    def get_agent_home_dir(self) -> Path:
        """Get the Ollama home directory.

        Returns:
            Path to ~/.ollama directory
        """
        return self.ollama_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "ollama"
        """
        return "ollama"

    def _get_session_dir(self, project_path: str) -> Path:
        """Get the session directory for a project.

        Sessions are stored in ~/.claude/projects even when using Ollama.

        Args:
            project_path: Absolute path to project

        Returns:
            Path to sessions directory
        """
        encoded = self.encode_project_path(project_path)
        return self.projects_dir / encoded

    def _get_model_name(self, model_provider_profile: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get model name from config/env/default in priority order.

        Model selection priority:
        1. model_provider_profile['model_name'] (from DAF config)
        2. OLLAMA_MODEL environment variable
        3. None (let Ollama use its default from ~/.ollama/config.json)

        Args:
            model_provider_profile: Model provider profile dict (optional)

        Returns:
            Model name if specified, None to use Ollama default
        """
        # Priority 1: DAF config via model_provider_profile
        if model_provider_profile and model_provider_profile.get("model_name"):
            return model_provider_profile["model_name"]

        # Priority 2: Environment variable
        if "OLLAMA_MODEL" in os.environ:
            return os.environ["OLLAMA_MODEL"]

        # Priority 3: Let Ollama use its default
        # (from ~/.ollama/config.json or Ollama's built-in default)
        return None
