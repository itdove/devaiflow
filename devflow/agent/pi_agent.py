"""Pi coding agent implementation.

This module integrates Pi (pi.dev), a terminal coding agent with project-scoped
JSONL sessions, provider/model selection, and non-interactive print mode.
"""

import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class PiAgent(AgentInterface):
    """Agent adapter for Pi coding agent."""

    def __init__(self, pi_dir: Path | None = None):
        """Initialize Pi storage paths.

        Args:
            pi_dir: Pi configuration directory. Defaults to ``PI_CODING_AGENT_DIR``
                or ``~/.pi/agent``.
        """
        if pi_dir is None:
            pi_dir = Path(
                os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".pi" / "agent")
            )
        self.pi_dir = Path(pi_dir).expanduser()
        session_dir = os.environ.get("PI_CODING_AGENT_SESSION_DIR")
        self.session_dir = (
            Path(session_dir).expanduser() if session_dir else self.pi_dir / "sessions"
        )

    def _build_env(self, env: dict[str, str] | None) -> dict[str, str]:
        """Build a child environment using this adapter's storage directory."""
        final_env = (env if env is not None else os.environ).copy()
        final_env["PI_CODING_AGENT_DIR"] = str(self.pi_dir)
        final_env.setdefault("PI_CODING_AGENT_SESSION_DIR", str(self.session_dir))
        return final_env

    def _project_session_dir(self, project_path: str) -> Path:
        """Return Pi's session directory for a project path."""
        normalized = str(Path(project_path).expanduser().resolve())
        encoded = normalized.strip("/\\").replace("/", "-").replace("\\", "-")
        return self.session_dir / f"--{encoded}--"

    @staticmethod
    def _session_id_from_path(session_file: Path) -> str:
        """Extract the Pi session ID from a timestamp-prefixed filename."""
        return session_file.stem.rsplit("_", 1)[-1]

    def _session_files(self, project_path: str | None = None) -> list[Path]:
        """Return session files, optionally scoped to a project."""
        if project_path:
            session_dirs = [self._project_session_dir(project_path)]
        elif self.session_dir.exists():
            session_dirs = [
                path for path in self.session_dir.iterdir() if path.is_dir()
            ]
        else:
            session_dirs = []

        files: list[Path] = []
        for session_dir in session_dirs:
            if session_dir.exists():
                files.extend(session_dir.glob("*.jsonl"))
        return files

    def _find_session_file(
        self, session_id: str, project_path: str | None = None
    ) -> Path | None:
        """Find a Pi session file by its session ID."""
        for session_file in self._session_files(project_path):
            if self._session_id_from_path(session_file) == session_id:
                return session_file
        return None

    @staticmethod
    def _profile_value(profile: dict[str, Any] | None, key: str) -> Any:
        """Read a value from a provider profile without assuming its type."""
        if not profile:
            return None
        if not isinstance(profile, dict) and hasattr(profile, "model_dump"):
            profile = profile.model_dump()
        return profile.get(key)

    def _append_profile_options(
        self,
        command: list[str],
        model_provider_profile: dict[str, Any] | None,
        *,
        reasoning_effort: str | None = None,
        model_override: str | None = None,
        config=None,
        utility: bool = False,
    ) -> None:
        """Add Pi provider, model, and thinking options to a command."""
        from devflow.agent.model_config import get_agent_model_config
        from devflow.utils.model_provider import (
            get_model_name_from_profile,
            get_reasoning_effort_from_profile,
        )

        settings = get_agent_model_config(
            config,
            self.get_agent_name(),
            utility=utility,
            command="pr_template" if utility else None,
            provider_profile=model_provider_profile,
            model_override=model_override,
        )
        provider = self._profile_value(model_provider_profile, "provider")
        model = (
            model_override
            or get_model_name_from_profile(
                model_provider_profile,
                command="pr_template" if utility else None,
                utility=utility,
            )
            or settings.get("model")
        )
        thinking = (
            reasoning_effort
            or get_reasoning_effort_from_profile(
                model_provider_profile,
                command="pr_template" if utility else None,
                utility=utility,
            )
            or settings.get("reasoning_effort")
        )

        if provider:
            command.extend(["--provider", str(provider)])
        if model:
            command.extend(["--model", str(model)])
        if thinking:
            command.extend(["--thinking", str(thinking)])
        api_key = self._profile_value(
            model_provider_profile, "api_key"
        ) or self._profile_value(model_provider_profile, "auth_token")
        if api_key:
            command.extend(["--api-key", str(api_key)])

    def launch_session(
        self,
        project_path: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.Popen:
        """Launch a new interactive Pi session."""
        require_tool("pi", "launch Pi AI assistant")
        command = [
            "pi",
            "--session-dir",
            str(self.get_session_dir(project_path)),
        ]
        return subprocess.Popen(command, cwd=project_path, env=self._build_env(env))

    def launch_with_prompt(
        self,
        project_path: str,
        initial_prompt: str,
        session_id: str,
        model_provider_profile: dict[str, Any] | None = None,
        skills_dirs: list[str] | None = None,
        workspace_path: str | None = None,
        config=None,
        env: dict[str, str] | None = None,
        headless: bool = False,
        auto_approve: bool = False,
        reasoning_effort: str | None = None,
        model_override: str | None = None,
        display_name: str | None = None,
        **kwargs,
    ) -> subprocess.Popen:
        """Launch Pi with an initial prompt or in print mode."""
        require_tool("pi", "launch Pi AI assistant")
        command = [
            "pi",
            "--session-dir",
            str(self.get_session_dir(project_path)),
        ]
        if headless:
            command.append("--print")
        if session_id and not session_id.startswith("pending"):
            command.extend(["--session-id", session_id])
        if display_name:
            command.extend(["--name", display_name])
        self._append_profile_options(
            command,
            model_provider_profile,
            reasoning_effort=reasoning_effort,
            model_override=model_override,
            config=config,
        )
        if skills_dirs:
            for skill_dir in skills_dirs:
                command.extend(["--skill", skill_dir])
        if auto_approve:
            command.append("--approve")
        if initial_prompt:
            command.extend(["--", initial_prompt])

        return subprocess.Popen(command, cwd=project_path, env=self._build_env(env))

    def resume_session(
        self,
        session_id: str,
        project_path: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.Popen:
        """Resume an existing Pi session."""
        require_tool("pi", "resume Pi AI assistant")
        return subprocess.Popen(
            [
                "pi",
                "--session-dir",
                str(self.get_session_dir(project_path)),
                "--session",
                session_id,
            ],
            cwd=project_path,
            env=self._build_env(env),
        )

    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> str | None:
        """Capture the newest Pi session created after launch."""
        before = self.get_existing_sessions(project_path)
        elapsed = 0.0
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval
            new_sessions = self.get_existing_sessions(project_path) - before
            if new_sessions:
                candidates = [
                    path
                    for path in self._session_files(project_path)
                    if self._session_id_from_path(path) in new_sessions
                ]
                if candidates:
                    newest = max(candidates, key=lambda path: path.stat().st_mtime)
                    return self._session_id_from_path(newest)
                return max(new_sessions)

        raise TimeoutError(
            f"Failed to detect new Pi session after {timeout}s. "
            "You may need to enter the session ID manually."
        )

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to a Pi JSONL session file."""
        existing = self._find_session_file(session_id, project_path or None)
        if existing:
            return existing
        if project_path:
            return self._project_session_dir(project_path) / f"{session_id}.jsonl"
        return self.session_dir / f"{session_id}.jsonl"

    def get_session_dir(self, project_path: str) -> Path:
        """Get Pi's project-scoped session directory."""
        return self._project_session_dir(project_path)

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check whether a Pi session exists."""
        return self._find_session_file(session_id, project_path) is not None

    def get_existing_sessions(self, project_path: str) -> set[str]:
        """Return Pi session IDs stored for a project."""
        return {
            self._session_id_from_path(path)
            for path in self._session_files(project_path)
        }

    def get_session_files(self) -> list[Path]:
        """Return all Pi session files for discovery and archive operations."""
        return self._session_files()

    @staticmethod
    def _read_records(session_file: Path) -> list[dict[str, Any]]:
        """Read valid JSON records from a Pi JSONL session."""
        records: list[dict[str, Any]] = []
        try:
            with session_file.open(encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict):
                        records.append(record)
        except (OSError, UnicodeError):
            return []
        return records

    @staticmethod
    def _message_record(record: dict[str, Any]) -> dict[str, Any] | None:
        """Return a nested Pi message payload when present."""
        message = record.get("message")
        return message if isinstance(message, dict) else None

    @staticmethod
    def _usage_int(usage: dict[str, Any], *keys: str) -> int:
        """Read a numeric usage field while tolerating missing/malformed data."""
        for key in keys:
            value = usage.get(key)
            if value in (None, ""):
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
        return 0

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Count message records in a Pi session."""
        session_file = self._find_session_file(session_id, project_path)
        if not session_file:
            return 0
        records = self._read_records(session_file)
        count = 0
        for record in records:
            if (
                record.get("type") == "message"
                or isinstance(record.get("message"), dict)
                and record["message"].get("role")
                in {
                    "user",
                    "assistant",
                    "toolResult",
                }
            ):
                count += 1
        return count

    def encode_project_path(self, project_path: str) -> str:
        """Return Pi's wrapped, slash-separated project directory name."""
        normalized = str(Path(project_path).expanduser().resolve())
        encoded = normalized.strip("/\\").replace("/", "-").replace("\\", "-")
        return f"--{encoded}--"

    def get_agent_home_dir(self) -> Path:
        """Return Pi's configuration directory."""
        return self.pi_dir

    def get_agent_name(self) -> str:
        """Return the backend identifier."""
        return "pi"

    def uses_tui(self) -> bool:
        """Pi provides an interactive terminal UI."""
        return True

    def supports_permission_prompts(self) -> bool:
        """Pi supports project trust and permission prompts."""
        return True

    def extract_token_usage(
        self, session_id: str, project_path: str
    ) -> dict[str, Any] | None:
        """Extract aggregated token usage from Pi message records."""
        session_file = self._find_session_file(session_id, project_path)
        if not session_file:
            return None

        totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "total_tokens": 0,
            "message_count": 0,
        }
        saw_usage = False
        for record in self._read_records(session_file):
            message = self._message_record(record) or record
            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue
            saw_usage = True
            input_tokens = self._usage_int(usage, "input", "inputTokens")
            output_tokens = self._usage_int(usage, "output", "outputTokens")
            cache_read = self._usage_int(usage, "cacheRead", "cache_read_input_tokens")
            cache_write = self._usage_int(
                usage, "cacheWrite", "cache_creation_input_tokens"
            )
            total = self._usage_int(usage, "totalTokens", "total_tokens")
            totals["input_tokens"] += input_tokens
            totals["output_tokens"] += output_tokens
            totals["cache_read_input_tokens"] += cache_read
            totals["cache_creation_input_tokens"] += cache_write
            totals["total_tokens"] += total or input_tokens + output_tokens
            totals["message_count"] += 1

        return totals if saw_usage else None

    def get_session_model_id(self, session_id: str, project_path: str) -> str | None:
        """Return the latest provider/model identifier recorded by Pi."""
        session_file = self._find_session_file(session_id, project_path)
        if not session_file:
            return None
        model_id = None
        for record in self._read_records(session_file):
            message = self._message_record(record) or record
            model = (
                message.get("model") or message.get("modelId") or record.get("model")
            )
            provider = message.get("provider") or record.get("provider")
            if model:
                model_id = f"{provider}/{model}" if provider else str(model)
        return model_id

    def generate_text(
        self,
        prompt: str,
        timeout: int = 30,
        display_name: str | None = None,
        config=None,
        model_provider_profile: dict[str, Any] | None = None,
    ) -> str | None:
        """Generate text using Pi's non-interactive print mode."""
        try:
            command = ["pi", "--print"]
            self._append_profile_options(
                command,
                model_provider_profile,
                config=config,
                utility=True,
            )
            command.extend(["--", prompt])
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._build_env(None),
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None
        return None

    def get_manual_resume_command(self, session_id: str, project_path: str) -> str:
        """Return a shell-safe manual resume command."""
        if project_path:
            session_dir = shlex.quote(str(self.get_session_dir(project_path)))
            return f"pi --session-dir {session_dir} --session {shlex.quote(session_id)}"
        return f"pi --session {shlex.quote(session_id)}"

    def uses_file_based_sessions(self) -> bool:
        """Pi stores sessions as JSONL files."""
        return True
