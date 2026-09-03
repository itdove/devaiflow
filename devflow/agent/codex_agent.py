"""Codex agent implementation.

This module implements the AgentInterface for Codex, an AI coding assistant
by OpenAI that provides terminal-based interaction with rich CLI capabilities.

⚠️  EXPERIMENTAL - NOT FULLY TESTED
This agent implementation has not been fully tested. It may have limitations or bugs.
Only Claude Code and OpenCode have been comprehensively tested. Use at your own risk.

Codex is an AI coding assistant with:
- Terminal-based TUI (Bubble Tea)
- Session management (agents, resume, archive)
- Non-interactive mode via ``codex exec``
- MCP server support
- Web search capabilities
- Sandbox for command execution

Limitations:
- Session detection relies on CLI output parsing
- Skills support is TBD (uses --add-dir flag)
- Token extraction depends on CLI availability

Storage:
    Codex stores data at ~/.codex/ by default.

Note:
    Codex is different from OpenCode (anomalyco/opencode). They are separate tools.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional, Set, List, Dict, Any

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class CodexAgent(AgentInterface):
    """Codex agent implementation.

    Provides integration with Codex AI coding assistant, an AI pair programmer
    with terminal-based CLI, session management, and MCP support.

    Features:
    - Launch and manage Codex sessions via ``codex`` CLI
    - Non-interactive prompt passing via ``codex exec``
    - Session resume via ``codex resume``
    - Session listing via ``codex agents``
    - Web search and MCP server support

    Limitations:
    - Session detection relies on CLI output parsing
    - Skills support TBD (uses --add-dir flag)
    - Token extraction depends on CLI availability

    Storage:
        Codex stores data at ~/.codex/ by default.

    Note:
        Codex (OpenAI) is NOT the same as OpenCode (anomalyco/opencode).
        They are separate tools with different capabilities.
    """

    def __init__(self, codex_dir: Optional[Path] = None):
        """Initialize Codex agent.

        Args:
            codex_dir: Codex config directory. Defaults to ~/.codex
        """
        if codex_dir is None:
            if os.environ.get("XDG_CONFIG_HOME"):
                codex_dir = Path(os.environ["XDG_CONFIG_HOME"]) / "codex"
            else:
                codex_dir = Path.home() / ".codex"

        self.codex_dir = Path(codex_dir)

    def launch_session(
        self,
        project_path: str,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen:
        """Launch a new Codex session in a project directory.

        Args:
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the launched Codex process

        Raises:
            ToolNotFoundError: If codex command is not installed
        """
        require_tool("codex", "launch Codex AI assistant")

        final_env = env if env is not None else os.environ.copy()

        return subprocess.Popen(
            ["codex"],
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
        **kwargs,
    ) -> subprocess.Popen:
        """Launch Codex with initial prompt.

        Uses ``codex exec`` for non-interactive mode when headless=True.

        Args:
            project_path: Absolute path to project
            initial_prompt: Initial prompt to send to the agent
            session_id: Session UUID (used for --session flag if resuming)
            model_provider_profile: Model provider profile (optional)
            skills_dirs: Skills directories (optional, Codex support via --add-dir)
            workspace_path: Workspace path (passed via -C/--cd flag)
            config: Configuration object (ignored)
            env: Environment variables dict (optional, defaults to os.environ)
            headless: Run non-interactively (codex exec), exits after completion
            auto_approve: Auto-approve all tool permissions via --approve-for-me

        Returns:
            Subprocess handle for Codex process

        Raises:
            ToolNotFoundError: If codex command is not installed
        """
        require_tool("codex", "launch Codex AI assistant")

        final_env = env if env is not None else os.environ.copy()

        if headless:
            cmd = ["codex", "exec", initial_prompt]
        else:
            cmd = ["codex", initial_prompt]

        if session_id and session_id.startswith("ses"):
            # Codex resume accepts session ID as argument
            cmd = ["codex", "resume", session_id]

        if model_provider_profile:
            model_name = model_provider_profile.get("model_name")
            if model_name:
                cmd.extend(["--model", model_name])

        if skills_dirs:
            for skill_dir in skills_dirs:
                cmd.extend(["--add-dir", skill_dir])

        if auto_approve:
            cmd.extend(["--approve-for-me"])

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
        """Resume an existing Codex session.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the resumed Codex process

        Raises:
            ToolNotFoundError: If codex command is not installed
        """
        require_tool("codex", "resume Codex AI assistant")

        final_env = env if env is not None else os.environ.copy()

        cmd = ["codex", "resume", session_id]

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
        """Capture a new Codex session ID by polling agent list.

        Queries ``codex agents`` to detect new sessions.
        Codex stores sessions in a database; we parse the CLI output.

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
            f"Failed to detect new Codex session after {timeout}s.\n"
            f"You may need to enter the session ID manually.\n"
            f"Tip: Run 'codex agents' to see available sessions."
        )

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to the Codex data directory.

        Codex stores sessions in its database. This returns the db path.

        Args:
            session_id: Session UUID (not used for path)
            project_path: Absolute path to project (not used)

        Returns:
            Path to the Codex data directory
        """
        return self.codex_dir

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a session exists in the Codex thread history database.

        Args:
            session_id: Session thread ID
            project_path: Absolute path to project (unused — Codex sessions are global)

        Returns:
            True if session exists
        """
        import sqlite3 as _sqlite3
        db_path = self.codex_dir / "thread_history_1.sqlite"
        if not db_path.exists():
            return False
        try:
            conn = _sqlite3.connect(str(db_path), timeout=5)
            cursor = conn.execute(
                "SELECT 1 FROM thread_turns WHERE thread_id = ? LIMIT 1",
                (session_id,),
            )
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception:
            return False

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs from Codex.

        Queries the Codex thread_history SQLite database for thread IDs.

        Args:
            project_path: Absolute path to project (unused — Codex sessions are global)

        Returns:
            Set of session thread IDs
        """
        import sqlite3 as _sqlite3
        db_path = self.codex_dir / "thread_history_1.sqlite"
        if not db_path.exists():
            return set()
        try:
            conn = _sqlite3.connect(str(db_path), timeout=5)
            cursor = conn.execute("SELECT DISTINCT thread_id FROM thread_turns")
            result = {row[0] for row in cursor.fetchall()}
            conn.close()
            return result
        except Exception:
            return set()

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get the number of messages in a Codex session.

        Uses ``codex export`` to retrieve session data and count messages.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Number of messages in the session
        """
        try:
            result = subprocess.run(
                ["codex", "export", session_id, "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
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

        Codex does not encode project paths for storage.

        Args:
            project_path: Absolute path to project

        Returns:
            Original path (no encoding needed)
        """
        return project_path

    def get_agent_home_dir(self) -> Path:
        """Get the Codex config directory.

        Returns:
            Path to Codex config directory (e.g., ~/.codex)
        """
        return self.codex_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "codex"
        """
        return "codex"

    def uses_tui(self) -> bool:
        """Codex uses a full-screen TUI (Bubble Tea).

        Returns:
            True
        """
        return True

    def supports_permission_prompts(self) -> bool:
        """Codex supports permission prompts when configured.

        Permission prompts for file edits and shell commands are controlled
        by the user's ``~/.codex/config.toml`` and sandbox settings.

        Returns:
            True — Codex has a permission prompt system.
        """
        return True

    def extract_token_usage(self, session_id: str, project_path: str) -> Optional[Dict[str, Any]]:
        """Extract token usage statistics from Codex export.

        Codex includes token usage in its export output.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Dictionary with token usage, or None if unavailable
        """
        try:
            result = subprocess.run(
                ["codex", "export", session_id, "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)
            if isinstance(data, dict) and "messages" in data:
                total_input = 0
                total_output = 0
                for msg in data["messages"]:
                    if "tokens" in msg:
                        total_input += msg["tokens"].get("input", 0)
                        total_output += msg["tokens"].get("output", 0)

                return {
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                    "total_tokens": total_input + total_output,
                }
            return None
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError):
            return None

    def get_session_model_id(self, session_id: str, project_path: str) -> Optional[str]:
        """Get model from Codex rollout JSONL session_meta."""
        from pathlib import Path as _Path
        sessions_dir = self.codex_dir / "sessions"
        if not sessions_dir.exists():
            return None
        try:
            for rollout in sorted(sessions_dir.rglob(f"*{session_id}*.jsonl")):
                with open(rollout) as f:
                    first_line = json.loads(f.readline())
                    if first_line.get("type") == "session_meta":
                        provenance = (first_line.get("payload", {})
                                      .get("base_instructions", {})
                                      .get("provenance", {}))
                        return provenance.get("model")
        except Exception:
            pass
        return None

    def generate_text(self, prompt: str, timeout: int = 30, display_name: Optional[str] = None) -> Optional[str]:
        """Generate text using codex exec (non-interactive mode)."""
        try:
            result = subprocess.run(
                ["codex", "exec", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def get_manual_resume_command(self, session_id: str, project_path: str) -> str:
        return f"codex resume {session_id}"

    def uses_file_based_sessions(self) -> bool:
        """Codex stores sessions in a database (not files).

        Returns:
            False
        """
        return False
