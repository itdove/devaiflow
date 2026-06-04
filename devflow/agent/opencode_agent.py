"""OpenCode agent implementation.

This module implements the AgentInterface for OpenCode (anomalyco/opencode), an open
source terminal-based AI coding agent supporting multiple model providers.

⚠️  EXPERIMENTAL - NOT FULLY TESTED
This agent implementation has not been fully tested. It may have limitations or bugs.
Only Claude Code has been comprehensively tested. Use at your own risk.

OpenCode is a terminal-based AI coding agent with multi-provider support (Anthropic,
OpenAI, Google, etc.), session management, MCP support, and JSON output capabilities.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Set, List, Dict, Any

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class OpenCodeAgent(AgentInterface):
    """OpenCode agent implementation.

    Provides integration with OpenCode AI coding assistant, a terminal-based CLI tool
    for AI pair programming with multi-provider support.

    OpenCode provides rich CLI capabilities including session management, non-interactive
    mode, JSON output, and built-in token/cost statistics.

    Features:
    - Launch and manage OpenCode sessions
    - Non-interactive prompt passing via ``opencode run``
    - Session resume via ``--session`` or ``--continue``
    - Session listing with JSON output
    - Token/cost statistics via ``opencode stats``
    - MCP server management

    Limitations:
    - Session detection relies on CLI output parsing
    - Skills support is TBD (uses .opencode/ directory)
    - Token extraction depends on ``opencode stats`` CLI availability

    Storage:
        OpenCode stores data at ~/.config/opencode/ by default.

    Note:
        OpenCode (anomalyco/opencode) is NOT the same as Charmbracelet's Crush
        (formerly also called "opencode"). See CrushAgent for Crush support.
    """

    def __init__(self, opencode_dir: Optional[Path] = None):
        """Initialize OpenCode agent.

        Args:
            opencode_dir: OpenCode config directory. Defaults to ~/.config/opencode
        """
        if opencode_dir is None:
            if os.environ.get("XDG_CONFIG_HOME"):
                opencode_dir = Path(os.environ["XDG_CONFIG_HOME"]) / "opencode"
            else:
                opencode_dir = Path.home() / ".config" / "opencode"

        self.opencode_dir = Path(opencode_dir)

    # Trigger line appended to the project's AGENTS.md so OpenCode
    # discovers the daf-workflow skill on startup without --prompt.
    AGENTS_MD_TRIGGER = (
        "When DAF_SESSION_NAME environment variable is set, "
        "immediately follow the daf-workflow skill instructions."
    )

    def ensure_agents_md_trigger(self, project_path: str) -> bool:
        """Ensure the project's AGENTS.md contains the daf-workflow trigger.

        Checks if ``AGENTS.md`` in *project_path* already contains the trigger
        line.  If the file exists but the line is missing, it is appended.  If
        the file does not exist it is created with just the trigger line.

        The operation is idempotent -- calling it multiple times on the same
        project is safe and will not duplicate the trigger.

        Args:
            project_path: Absolute path to the project directory whose
                ``AGENTS.md`` should be updated.

        Returns:
            ``True`` if the file was created or modified, ``False`` if the
            trigger was already present.
        """
        agents_md = Path(project_path) / "AGENTS.md"

        if agents_md.exists():
            content = agents_md.read_text()
            if self.AGENTS_MD_TRIGGER not in content:
                with open(agents_md, "a") as f:
                    f.write(f"\n\n{self.AGENTS_MD_TRIGGER}\n")
                return True
            return False

        # File does not exist -- create it with the trigger line.
        agents_md.write_text(f"{self.AGENTS_MD_TRIGGER}\n")
        return True

    def launch_session(
        self,
        project_path: str,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen:
        """Launch a new OpenCode session in a project directory.

        Args:
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the launched OpenCode process

        Raises:
            ToolNotFoundError: If opencode command is not installed
        """
        require_tool("opencode", "launch OpenCode AI assistant")

        final_env = env if env is not None else os.environ.copy()

        return subprocess.Popen(
            ["opencode"],
            cwd=project_path,
            env=final_env,
        )

    def launch_with_prompt(
        self,
        project_path: str,
        initial_prompt: str,
        session_id: str,
        model_provider_profile: Optional[Dict[str, Any]] = None,
        skills_dirs: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
        config=None,
        env: Optional[Dict[str, str]] = None,
        headless: bool = False,
        auto_approve: bool = False,
    ) -> subprocess.Popen:
        """Launch OpenCode with initial prompt.

        In **interactive** mode the prompt is NOT passed via ``--prompt``.
        Instead, the project's ``AGENTS.md`` is updated with a daf-workflow
        trigger (idempotent) so that OpenCode discovers the session context
        on its own.  This preserves OpenCode's native permission system --
        the LLM no longer interprets a ``--prompt`` flag as blanket
        authorisation to modify files.

        In **headless** mode (``headless=True``) the prompt is still passed
        via ``opencode run <prompt>`` because there is no human present to
        interact with permission dialogs.

        Args:
            project_path: Absolute path to project
            initial_prompt: Initial prompt to send to the agent
            session_id: Session UUID (used for --session flag if resuming)
            model_provider_profile: Model provider profile (optional)
            skills_dirs: Skills directories (optional, OpenCode support TBD)
            workspace_path: Workspace path (ignored)
            config: Configuration object (ignored)
            env: Environment variables dict (optional, defaults to os.environ)
            headless: Run non-interactively (opencode run), exits after completion
            auto_approve: Auto-approve all tool permissions

        Returns:
            Subprocess handle for OpenCode process

        Raises:
            ToolNotFoundError: If opencode command is not installed
        """
        require_tool("opencode", "launch OpenCode AI assistant")

        final_env = env if env is not None else os.environ.copy()

        if headless:
            # Non-interactive: prompt must be passed directly.
            cmd = ["opencode", "run", initial_prompt]
        else:
            # Interactive: rely on AGENTS.md trigger + daf-workflow skill.
            # Do NOT pass --prompt so OpenCode's permission system stays intact.
            self.ensure_agents_md_trigger(project_path)
            cmd = ["opencode"]

        if session_id and session_id.startswith("ses"):
            cmd.extend(["--session", session_id])

        if model_provider_profile:
            model_name = model_provider_profile.get("model_name")
            if model_name:
                cmd.extend(["--model", model_name])

        if auto_approve:
            cmd.append("--dangerously-skip-permissions")

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=final_env,
        )

    def resume_session(
        self,
        session_id: str,
        project_path: str,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen:
        """Resume an existing OpenCode session.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the resumed OpenCode process

        Raises:
            ToolNotFoundError: If opencode command is not installed
        """
        require_tool("opencode", "resume OpenCode AI assistant")

        final_env = env if env is not None else os.environ.copy()

        cmd = ["opencode", "--session", session_id]

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=final_env,
        )

    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """Capture a new OpenCode session ID by polling session list.

        Queries ``opencode session list --format json`` to detect new sessions.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Session UUID if detected, None if timeout

        Raises:
            TimeoutError: If session not detected within timeout
        """
        before = self.get_existing_sessions(project_path)

        elapsed = 0.0
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval

            after = self.get_existing_sessions(project_path)
            new_sessions = after - before

            if new_sessions:
                return new_sessions.pop()

        raise TimeoutError(
            f"Failed to detect new OpenCode session after {timeout}s.\n"
            f"You may need to enter the session ID manually.\n"
            f"Tip: Run 'opencode session list' to see available sessions."
        )

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to the OpenCode data directory.

        OpenCode stores sessions in its database. This returns the db path.

        Args:
            session_id: Session UUID (not used for path)
            project_path: Absolute path to project (not used)

        Returns:
            Path to the OpenCode data directory
        """
        return self._get_db_path()

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a session exists by querying OpenCode CLI.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            True if session exists
        """
        try:
            sessions = self.get_existing_sessions(project_path)
            return session_id in sessions
        except Exception:
            return False

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs from OpenCode.

        Parses ``opencode session list --format json`` output.

        Args:
            project_path: Absolute path to project (passed as cwd)

        Returns:
            Set of session UUIDs
        """
        try:
            result = subprocess.run(
                ["opencode", "session", "list", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=project_path,
            )
            if result.returncode != 0:
                return set()

            sessions_data = json.loads(result.stdout)
            if isinstance(sessions_data, list):
                return {s.get("id", "") for s in sessions_data if s.get("id")}
            return set()
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
            return set()

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get the number of messages in an OpenCode session.

        Uses ``opencode export`` or database query to count messages.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Number of messages in the session
        """
        try:
            result = subprocess.run(
                ["opencode", "export", session_id, "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=project_path,
            )
            if result.returncode != 0:
                return 0

            data = json.loads(result.stdout)
            if isinstance(data, dict) and "messages" in data:
                return len(data["messages"])
            if isinstance(data, list):
                return len(data)
            return 0
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
            return 0

    def encode_project_path(self, project_path: str) -> str:
        """Encode project path.

        OpenCode does not encode project paths for storage.

        Args:
            project_path: Absolute path to project

        Returns:
            Original path (no encoding needed)
        """
        return project_path

    def get_agent_home_dir(self) -> Path:
        """Get the OpenCode config directory.

        Returns:
            Path to OpenCode config directory (e.g., ~/.config/opencode)
        """
        return self.opencode_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "opencode"
        """
        return "opencode"

    def supports_permission_prompts(self) -> bool:
        """OpenCode supports permission prompts when launched without ``--prompt``.

        When launched interactively (without ``--prompt``), OpenCode shows
        permission prompts for file edits and shell commands, identical to
        standalone usage.  The ``--prompt`` flag is only used in headless mode
        where no human is present.

        Returns:
            True — OpenCode has a permission prompt system.
        """
        return True

    def extract_token_usage(self, session_id: str, project_path: str) -> Optional[Dict[str, Any]]:
        """Extract token usage statistics using ``opencode stats``.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Dictionary with token usage, or None if unavailable
        """
        try:
            result = subprocess.run(
                ["opencode", "stats", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=project_path,
            )
            if result.returncode != 0:
                return None

            stats = json.loads(result.stdout)
            if isinstance(stats, dict):
                return {
                    "input_tokens": stats.get("input_tokens", 0),
                    "output_tokens": stats.get("output_tokens", 0),
                    "total_tokens": stats.get("total_tokens", 0),
                    "total_cost": stats.get("total_cost"),
                }
            return None
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
            return None

    def _get_db_path(self) -> Path:
        """Get the path to OpenCode's database.

        Tries ``opencode db path`` first, falls back to default location.

        Returns:
            Path to database file or config directory
        """
        try:
            result = subprocess.run(
                ["opencode", "db", "path"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return self.opencode_dir
