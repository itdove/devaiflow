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
- Session detection relies on Codex's local database and rollout metadata
- Skills support is TBD (uses --add-dir flag)
- Token extraction depends on CLI availability

Storage:
    Codex stores data at ~/.codex/ by default.

Note:
    Codex is different from OpenCode (anomalyco/opencode). They are separate tools.
"""

import json
import os
import re
import shlex
import subprocess
import time
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
            if os.environ.get("CODEX_HOME"):
                codex_dir = Path(os.environ["CODEX_HOME"])
            elif os.environ.get("XDG_CONFIG_HOME"):
                codex_dir = Path(os.environ["XDG_CONFIG_HOME"]) / "codex"
            else:
                codex_dir = Path.home() / ".codex"

        self.codex_dir = Path(codex_dir)

    @staticmethod
    def _build_launch_env(env: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Prepare an environment for an independent Codex process.

        DevAIFlow can itself be launched from Codex.  Parent-session markers
        must not be inherited by the child, otherwise Codex may treat the
        invocation as a nested/CI process and exit instead of opening its TUI.
        """
        final_env = (env if env is not None else os.environ).copy()
        for key in (
            "CODEX_CI",
            "CODEX_PERMISSION_PROFILE",
            "CODEX_THREAD_ID",
            "CODEX_SESSION_ID",
            "CODEX_SANDBOX_NETWORK_DISABLED",
        ):
            final_env.pop(key, None)
        return final_env

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

        final_env = self._build_launch_env(env)

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
        reasoning_effort: Optional[str] = None,
        model_override: Optional[str] = None,
        display_name: Optional[str] = None,
        **kwargs,
    ) -> subprocess.Popen:
        """Launch Codex with initial prompt.

        Uses ``codex exec`` for non-interactive mode when headless=True.

        Args:
            project_path: Absolute path to project
            initial_prompt: Initial prompt to send to the agent
            session_id: Session UUID. A non-pending value resumes the existing
                session; ``pending-capture`` starts a new session.
            model_provider_profile: Model provider profile (optional)
            skills_dirs: Skills directories (optional, Codex support via --add-dir)
            workspace_path: Workspace path (passed via -C/--cd flag)
            config: Configuration object (ignored)
            env: Environment variables dict (optional, defaults to os.environ)
            headless: Run non-interactively (codex exec), exits after completion
            auto_approve: Auto-approve all tool permissions via --approve-for-me
            reasoning_effort: Model reasoning effort (e.g., "low", "high", "max")
            model_override: Override default model (e.g., "codex/o3")
            display_name: Display name for the session (passed to --name flag)

        Returns:
            Subprocess handle for Codex process

        Raises:
            ToolNotFoundError: If codex command is not installed
        """
        require_tool("codex", "launch Codex AI assistant")

        final_env = self._build_launch_env(env)
        from devflow.agent.model_config import get_agent_model_config
        settings = get_agent_model_config(config, self.get_agent_name())

        is_resume = bool(session_id and not session_id.startswith("pending"))

        if headless:
            cmd = ["codex", "exec", initial_prompt]
        else:
            cmd = ["codex", initial_prompt]

        if is_resume:
            # Keep this path consistent with resume_session(). Investigation
            # sessions can be reopened from a fresh clone, so Codex must use
            # the selected project and avoid its own cwd-selection prompt.
            cmd = [
                "codex",
                "resume",
                "--cd",
                project_path,
                "-c",
                'tui.resume_cwd="current"',
            ]

        if model_provider_profile:
            model_name = model_override or model_provider_profile.get("model_name")
            if model_name:
                cmd.extend(["--model", model_name])
        elif model_override or settings["model"]:
            cmd.extend(["--model", model_override or settings["model"]])

        effective_reasoning = reasoning_effort or settings["reasoning_effort"]
        if effective_reasoning:
            cmd.extend(["-c", f'model_reasoning_effort="{effective_reasoning}"'])

        if skills_dirs:
            for skill_dir in skills_dirs:
                cmd.extend(["--add-dir", skill_dir])

        if auto_approve:
            cmd.extend(["--approve-for-me"])

        if is_resume:
            # Keep the positional session ID after all resume options so the
            # Codex CLI parses it consistently across supported versions.
            cmd.append(session_id)

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

        final_env = self._build_launch_env(env)

        # DevAIFlow may intentionally replace the project directory between
        # launches (for example, investigation sessions are re-cloned into a
        # fresh temporary directory). Codex otherwise compares the new cwd
        # with the last cwd recorded in the session and opens its own cwd
        # selection prompt. The project_path supplied by DevAIFlow is the
        # authoritative directory for this resume, so make that choice
        # explicit for this invocation.
        cmd = [
            "codex",
            "resume",
            "--cd",
            project_path,
            "-c",
            "tui.resume_cwd=\"current\"",
            session_id,
        ]

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

        Queries the Codex thread history database and rollout filenames for
        thread IDs. Rollout metadata records the working directory, which is
        used to keep session discovery scoped to the directory that DevAIFlow
        launched. This matters because Codex stores sessions globally and a
        different recently opened Codex session must not be captured here.

        The SQLite projection can lag behind the rollout file (or be
        unavailable while Codex is shutting down), so rollout files are used
        for project association. The database remains a fallback only when no
        rollout metadata is available at all.

        Args:
            project_path: Absolute path to project used to scope rollout metadata

        Returns:
            Set of session thread IDs
        """
        import sqlite3 as _sqlite3

        database_sessions: Set[str] = set()
        db_path = self.codex_dir / "thread_history_1.sqlite"
        if db_path.exists():
            try:
                conn = _sqlite3.connect(str(db_path), timeout=5)
                cursor = conn.execute("SELECT DISTINCT thread_id FROM thread_turns")
                database_sessions.update(row[0] for row in cursor.fetchall() if row[0])
                conn.close()
            except Exception:
                # The rollout files remain usable when the projection database
                # is locked, read-only, or from a different Codex version.
                pass

        rollout_sessions = self._get_rollout_sessions()

        # Without a project path there is no scope to apply. This branch also
        # preserves the complete global-session behavior for callers that need
        # to inspect Codex's entire history.
        if not project_path:
            return database_sessions | set(rollout_sessions)

        matching_rollouts = {
            session_id
            for session_id, recorded_cwd in rollout_sessions.items()
            if not recorded_cwd or self._paths_match(recorded_cwd, project_path)
        }

        if rollout_sessions:
            # A database-only session has no cwd information, so it cannot be
            # safely associated with this project. It will be picked up on a
            # later poll once Codex writes its rollout metadata.
            return matching_rollouts

        # If no rollout files are available at all, retain the database
        # fallback. There is no metadata to use for filtering in that case.
        return database_sessions

    @staticmethod
    def _paths_match(first: str, second: str) -> bool:
        """Compare project paths after resolving symlinks and relative parts."""
        try:
            return Path(first).expanduser().resolve() == Path(second).expanduser().resolve()
        except (OSError, RuntimeError, TypeError):
            return os.path.normcase(os.path.abspath(os.path.expanduser(first))) == os.path.normcase(
                os.path.abspath(os.path.expanduser(second))
            )

    def _get_rollout_sessions(self) -> Dict[str, Optional[str]]:
        """Return rollout session IDs mapped to their recorded working directory."""
        sessions_dir = self.codex_dir / "sessions"
        result: Dict[str, Optional[str]] = {}
        if sessions_dir.exists():
            thread_id_pattern = re.compile(
                r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$",
                re.IGNORECASE,
            )
            try:
                rollouts = sessions_dir.rglob("rollout-*.jsonl")
                for rollout in rollouts:
                    match = thread_id_pattern.search(rollout.name)
                    if not match:
                        continue

                    session_id = match.group(1)
                    recorded_cwd = None
                    try:
                        with rollout.open(encoding="utf-8") as rollout_file:
                            first_record = json.loads(rollout_file.readline())
                        payload = (
                            first_record.get("payload", {})
                            if isinstance(first_record, dict)
                            else {}
                        )
                        if isinstance(payload, dict) and isinstance(payload.get("cwd"), str):
                            recorded_cwd = payload["cwd"]
                    except (OSError, TypeError, ValueError):
                        # The filename still provides a usable session ID when
                        # a rollout is incomplete or from an older format.
                        pass

                    # A session should normally have one rollout file. Prefer
                    # a path-bearing record if duplicate/partial files exist.
                    if session_id not in result or (
                        result[session_id] is None and recorded_cwd
                    ):
                        result[session_id] = recorded_cwd
            except OSError:
                pass

        return result

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

    def generate_text(
        self,
        prompt: str,
        timeout: int = 30,
        display_name: Optional[str] = None,
        config=None,
        model_provider_profile: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate text using codex exec (non-interactive mode)."""
        try:
            from devflow.agent.model_config import get_agent_model_config
            settings = get_agent_model_config(
                config,
                self.get_agent_name(),
                utility=True,
                command="pr_template",
                provider_profile=model_provider_profile,
            )
            from devflow.utils.model_provider import build_env_from_profile, get_model_name_from_profile

            cmd = ["codex", "exec"]
            model = get_model_name_from_profile(
                model_provider_profile,
                command="pr_template",
                utility=True,
            ) or settings["model"] or ("gpt-5.6-luna" if config is None else None)
            if model:
                cmd.extend(["--model", model])
            reasoning = settings["reasoning_effort"] or ("low" if config is None else None)
            if reasoning:
                cmd.extend(["-c", f'model_reasoning_effort="{reasoning}"'])
            cmd.append(prompt)
            run_kwargs = {"capture_output": True, "text": True, "timeout": timeout}
            if model_provider_profile:
                run_kwargs["env"] = build_env_from_profile(model_provider_profile)
            result = subprocess.run(cmd, **run_kwargs)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            # Fallback to default model if luna not available
            result = subprocess.run(["codex", "exec", prompt], **run_kwargs)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def get_manual_resume_command(self, session_id: str, project_path: str) -> str:
        resume_cwd_config = shlex.quote('tui.resume_cwd="current"')
        return (
            f"codex resume --cd {shlex.quote(project_path)} "
            f"-c {resume_cwd_config} {shlex.quote(session_id)}"
        )

    def uses_file_based_sessions(self) -> bool:
        """Codex stores sessions in a database (not files).

        Returns:
            False
        """
        return False
