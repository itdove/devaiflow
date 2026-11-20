"""Kilo CLI agent implementation.

Kilo has OpenCode ancestry but owns a separate CLI, database, config directory,
and daemon lifecycle. This adapter deliberately speaks only the Kilo contract.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import socket
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool

logger = logging.getLogger(__name__)

_VERSION_PATTERN = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?:[-+][\w.-]+)?")
_SESSION_ID_PATTERN = re.compile(r"^ses_[A-Za-z0-9_-]+$")


class KiloCompatibilityError(RuntimeError):
    """Raised when the installed Kilo CLI does not meet DAF's requirements."""


class KiloSessionQueryError(RuntimeError):
    """A Kilo session query failed without exposing session contents."""


class KiloAgent(AgentInterface):
    """Experimental adapter for Kilo Code CLI (``kilo``)."""

    def __init__(self, kilo_dir: Path | None = None):
        if kilo_dir is None:
            if os.environ.get("XDG_CONFIG_HOME"):
                kilo_dir = Path(os.environ["XDG_CONFIG_HOME"]).expanduser() / "kilo"
            else:
                kilo_dir = Path.home() / ".config" / "kilo"

        self.kilo_dir = Path(kilo_dir)
        self._kilo_version: tuple[int, int, int] | None = None
        self._db_path: Path | None = None

    def get_kilo_version(self, *, timeout: float = 5) -> tuple[int, int, int]:
        """Return the installed Kilo CLI version, requiring Kilo 1.0 or newer."""
        if self._kilo_version is not None:
            return self._kilo_version

        try:
            result = subprocess.run(
                ["kilo", "--version"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise KiloCompatibilityError(
                "Kilo CLI was not found; install the `kilo` command"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise KiloCompatibilityError("Kilo version detection timed out") from exc
        except OSError as exc:
            raise KiloCompatibilityError(
                "Kilo version detection could not run"
            ) from exc

        if result.returncode != 0:
            raise KiloCompatibilityError(
                "Kilo version detection failed; check the Kilo installation"
            )

        output = "\n".join((result.stdout or "", result.stderr or ""))
        match = _VERSION_PATTERN.search(output)
        if not match:
            raise KiloCompatibilityError("Kilo returned an unrecognized version")

        version = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if version < (1, 0, 0):
            raise KiloCompatibilityError("DevAIFlow requires Kilo CLI 1.0 or newer")

        self._kilo_version = version
        return version

    @staticmethod
    def _valid_session_id(session_id: Any) -> bool:
        return isinstance(session_id, str) and bool(
            _SESSION_ID_PATTERN.fullmatch(session_id)
        )

    @staticmethod
    def _paths_match(first: str, second: str) -> bool:
        """Compare Kilo directory metadata canonically, including symlinks."""
        try:
            return (
                Path(first).expanduser().resolve()
                == Path(second).expanduser().resolve()
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            try:
                return os.path.normcase(
                    os.path.abspath(os.path.expanduser(first))
                ) == os.path.normcase(os.path.abspath(os.path.expanduser(second)))
            except (TypeError, ValueError):
                return False

    @staticmethod
    def _environment(
        env: dict[str, str] | None, isolated_workspace: bool = False
    ) -> dict[str, str]:
        final_env = dict(env) if env is not None else os.environ.copy()
        if isolated_workspace:
            # Kilo otherwise attaches to its persistent daemon, which can keep
            # processes using a DAF-managed clone after the UI exits.
            final_env["KILO_NO_DAEMON"] = "1"
        return final_env

    @staticmethod
    def _profile_environment(
        profile: dict[str, Any] | None,
        base_env: dict[str, str],
        isolated_workspace: bool,
    ) -> dict[str, str]:
        """Apply provider credentials while retaining clone daemon isolation."""
        if profile:
            from devflow.utils.model_provider import build_env_from_profile

            base_env = build_env_from_profile(profile, base_env=base_env)
        if isolated_workspace:
            base_env["KILO_NO_DAEMON"] = "1"
        return base_env

    @staticmethod
    def _profile_model(profile: dict[str, Any] | None) -> str | None:
        if not profile:
            return None
        from devflow.utils.model_provider import (
            get_model_name_from_profile,
            qualify_model_for_agent,
        )

        model = get_model_name_from_profile(profile)
        if not model:
            model = profile.get("model_name")
        return qualify_model_for_agent(model, "kilo", profile)

    @staticmethod
    def _reasoning_variant(reasoning_effort: str | None) -> str | None:
        if not reasoning_effort:
            return None
        return reasoning_effort.strip()

    def _create_session_with_title(
        self,
        title: str,
        project_path: str,
        env: dict[str, str],
        on_session_id: Callable[[str], None] | None = None,
    ) -> str | None:
        """Create a titled session through Kilo's local session HTTP API."""
        try:
            result = self._session_api_request(
                "POST",
                "/session",
                project_path,
                env,
                {"title": title},
            )
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
            logger.debug("Unable to pre-create a titled Kilo session", exc_info=True)
            return None

        if not isinstance(result, dict):
            return None
        nested_result = result.get("data")
        result_data = nested_result if isinstance(nested_result, dict) else result
        session_id = result_data.get("id")
        recorded_directory = result_data.get("directory")
        if not isinstance(session_id, str) or not self._valid_session_id(session_id):
            return None
        if not isinstance(recorded_directory, str) or not self._paths_match(
            recorded_directory, project_path
        ):
            logger.warning(
                "Kilo created a session without matching project-directory metadata"
            )
            return None

        if on_session_id:
            on_session_id(session_id)
        return session_id

    def update_session_title(
        self,
        session_id: str,
        title: str,
        project_path: str,
        env: dict[str, str] | None = None,
    ) -> bool:
        """Best-effort update of an existing Kilo session's title."""
        if not self._valid_session_id(session_id):
            return False
        final_env = self._environment(env)
        try:
            result = self._session_api_request(
                "PATCH",
                f"/session/{quote(session_id, safe='')}",
                project_path,
                final_env,
                {"title": title},
            )
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
            logger.debug("Unable to update the Kilo session title", exc_info=True)
            return False
        return isinstance(result, dict)

    def _session_api_request(
        self,
        method: str,
        path: str,
        project_path: str,
        env: dict[str, str],
        payload: dict[str, Any],
    ) -> Any:
        """Run a short-lived Kilo server and issue one directory-scoped request.

        This owns only the server process it starts. It never connects to or
        stops Kilo's reusable local daemon.
        """
        require_tool("kilo", "manage Kilo session titles")
        self.get_kilo_version()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_socket:
            port_socket.bind(("127.0.0.1", 0))
            port = port_socket.getsockname()[1]

        server_env = self._environment(env, isolated_workspace=True)
        server = subprocess.Popen(
            ["kilo", "serve", "--hostname", "127.0.0.1", "--port", str(port)],
            cwd=project_path,
            env=server_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base_url = f"http://127.0.0.1:{port}"
        headers = {"Content-Type": "application/json"}
        password = server_env.get("KILO_SERVER_PASSWORD")
        if password:
            username = server_env.get("KILO_SERVER_USERNAME", "kilo")
            token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
            headers["Authorization"] = f"Basic {token}"

        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError("Kilo session API server exited during startup")
                try:
                    health_request = Request(
                        f"{base_url}/global/health",
                        headers=headers,
                    )
                    with urlopen(health_request, timeout=0.25):
                        break
                except (HTTPError, OSError, URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                raise RuntimeError("Kilo session API server did not become ready")

            query = urlencode(
                {"directory": str(Path(project_path).expanduser().resolve())}
            )
            request = Request(
                f"{base_url}{path}?{query}",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method=method,
            )
            with urlopen(request, timeout=5) as response:
                response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body.strip() else {}
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=3)

    def launch_session(
        self,
        project_path: str,
        env: dict[str, str] | None = None,
        model_provider_profile: dict[str, Any] | None = None,
        display_name: str | None = None,
        isolated_workspace: bool = False,
        on_session_id: Callable[[str], None] | None = None,
    ) -> subprocess.Popen:
        """Launch a new interactive Kilo session."""
        require_tool("kilo", "launch Kilo Code")
        self.get_kilo_version()
        final_env = self._profile_environment(
            model_provider_profile,
            self._environment(env, isolated_workspace),
            isolated_workspace,
        )
        from devflow.utils.model_provider import get_profile_arguments

        # The root command starts Kilo's full TUI. `kilo run --interactive`
        # starts the compact split-footer interface instead.
        command = ["kilo"]
        command.extend(
            get_profile_arguments(model_provider_profile, self.get_agent_name())
        )
        model_name = self._profile_model(model_provider_profile)
        session_id = None
        if display_name:
            session_id = self._create_session_with_title(
                display_name,
                project_path,
                final_env,
                on_session_id,
            )
        if session_id:
            command.extend(["--session", session_id])
        elif display_name:
            logger.warning(
                "Kilo's full TUI has no CLI title fallback; session title "
                "pre-creation failed"
            )

        if model_name:
            command.extend(["--model", model_name])

        return subprocess.Popen(command, cwd=project_path, env=final_env)

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
        model_override: str | None = None,
        reasoning_effort: str | None = None,
        display_name: str | None = None,
        isolated_workspace: bool = False,
        on_session_id: Callable[[str], None] | None = None,
        on_launch: Callable[[], None] | None = None,
        **kwargs,
    ) -> subprocess.Popen:
        """Launch Kilo with an initial prompt in interactive or headless mode."""
        require_tool("kilo", "launch Kilo Code")
        self.get_kilo_version()
        final_env = self._environment(env, isolated_workspace)

        from devflow.agent.model_config import get_agent_model_config
        from devflow.utils.model_provider import (
            get_model_name_from_profile,
            get_profile_arguments,
        )

        settings = get_agent_model_config(
            config,
            self.get_agent_name(),
            provider_profile=model_provider_profile,
            model_override=model_override,
        )
        model_name = model_override or get_model_name_from_profile(
            model_provider_profile
        )
        model_name = (
            model_name
            or settings.get("model")
            or self._profile_model(model_provider_profile)
        )
        if model_name:
            from devflow.utils.model_provider import qualify_model_for_agent

            model_name = qualify_model_for_agent(
                model_name, self.get_agent_name(), model_provider_profile
            )
        profile_arguments = get_profile_arguments(
            model_provider_profile, self.get_agent_name()
        )
        effective_reasoning = reasoning_effort or settings.get("reasoning_effort")
        final_env = self._profile_environment(
            model_provider_profile,
            final_env,
            isolated_workspace,
        )
        existing_session = session_id if self._valid_session_id(session_id) else None
        interactive_prompt = not headless and bool(initial_prompt)
        if interactive_prompt and existing_session:
            raise KiloCompatibilityError(
                "Kilo's full TUI only auto-submits --prompt when starting a new "
                "session; it ignores the initial prompt when --session is used. "
                "Resume the existing session without an initial prompt or start "
                "a new DAF conversation."
            )

        if on_launch:
            on_launch()

        if display_name and existing_session:
            self.update_session_title(
                existing_session, display_name, project_path, final_env
            )
        elif display_name and not interactive_prompt:
            created_session = self._create_session_with_title(
                display_name,
                project_path,
                final_env,
                on_session_id,
            )
            if created_session:
                existing_session = created_session

        if headless:
            command = ["kilo", "run", *profile_arguments]
            command.extend(["--format", "json"])
        else:
            # The root command opens the full TUI; `kilo run --interactive`
            # uses Kilo's compact split-footer mode.
            command = ["kilo", *profile_arguments]

        if existing_session:
            command.extend(["--session", existing_session])
        elif display_name:
            if headless:
                command.extend(["--title", display_name])
            else:
                logger.warning(
                    "Kilo's full TUI has no CLI title fallback; session title "
                    "pre-creation failed"
                )
        if model_name:
            command.extend(["--model", model_name])
        variant = self._reasoning_variant(effective_reasoning)
        if variant and headless:
            command.extend(["--variant", variant])
        elif variant:
            logger.warning(
                "Kilo's full TUI does not support a launch-time reasoning "
                "variant; select it in the TUI"
            )
        if auto_approve:
            command.append("--auto")
        if initial_prompt:
            if headless:
                command.append(initial_prompt)
            else:
                command.extend(["--prompt", initial_prompt])

        return subprocess.Popen(command, cwd=project_path, env=final_env)

    def resume_session(
        self,
        session_id: str,
        project_path: str,
        env: dict[str, str] | None = None,
        model_provider_profile: dict[str, Any] | None = None,
        display_name: str | None = None,
        isolated_workspace: bool = False,
    ) -> subprocess.Popen:
        """Resume a specific Kilo session without consulting another backend."""
        require_tool("kilo", "resume Kilo Code")
        self.get_kilo_version()
        if not self._valid_session_id(session_id):
            raise ValueError("Refusing an invalid Kilo session ID")
        final_env = self._profile_environment(
            model_provider_profile,
            self._environment(env, isolated_workspace),
            isolated_workspace,
        )
        from devflow.utils.model_provider import get_profile_arguments

        command = ["kilo"]
        command.extend(
            get_profile_arguments(model_provider_profile, self.get_agent_name())
        )
        model_name = self._profile_model(model_provider_profile)
        if model_name:
            command.extend(["--model", model_name])
        command.extend(["--session", session_id])
        if display_name:
            self.update_session_title(session_id, display_name, project_path, final_env)

        return subprocess.Popen(command, cwd=project_path, env=final_env)

    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> str | None:
        """Return a new Kilo session ID by comparing scoped session snapshots."""
        before = self.get_existing_sessions(project_path, strict=True)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
            after = self.get_existing_sessions(
                project_path,
                timeout=max(0.1, deadline - time.monotonic()),
                strict=True,
            )
            new_sessions = after - before
            if len(new_sessions) == 1:
                return next(iter(new_sessions))
            if len(new_sessions) > 1:
                return None
        return None

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Return Kilo's SQLite database path (not an individual transcript)."""
        return self._get_db_path()

    def _get_db_path(self) -> Path:
        if self._db_path is not None:
            return self._db_path
        try:
            result = subprocess.run(
                ["kilo", "db", "path"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            output_path = (result.stdout or "").strip()
            if result.returncode == 0 and output_path:
                self._db_path = Path(output_path).expanduser()
                return self._db_path
        except (OSError, subprocess.SubprocessError):
            pass

        data_home = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
        data_dir = data_home / "kilo"
        override = os.environ.get("KILO_DB")
        if override:
            override_path = Path(override).expanduser()
            self._db_path = (
                override_path
                if override_path.is_absolute()
                else data_dir / override_path
            )
        else:
            self._db_path = data_dir / "kilo.db"
        return self._db_path

    def get_existing_sessions(
        self,
        project_path: str,
        *,
        timeout: float = 10,
        strict: bool = False,
    ) -> set[str]:
        """List session IDs whose Kilo directory metadata matches the project.

        Kilo returns no stdout for a successful empty list, so an empty response
        is treated as an empty result only when the CLI exits successfully.
        """
        if not project_path:
            return set()
        deadline = time.monotonic() + timeout
        error: str | None = None
        try:
            if timeout <= 0:
                raise KiloSessionQueryError(
                    "Kilo session query has no time budget remaining"
                )
            remaining = deadline - time.monotonic()
            self.get_kilo_version(timeout=min(5, remaining))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise KiloSessionQueryError(
                    "Kilo session query exceeded its time budget"
                )

            result = subprocess.run(
                ["kilo", "session", "list", "--format", "json", "--all"],
                capture_output=True,
                text=True,
                timeout=remaining,
                cwd=project_path,
                env=self._environment(None, isolated_workspace=True),
                check=False,
            )
            if result.returncode != 0:
                raise KiloSessionQueryError(
                    f"Kilo session list failed (exit code {result.returncode}); "
                    "check the Kilo installation and session-list command"
                )

            output = (result.stdout or "").strip()
            if not output:
                return set()
            sessions_data = json.loads(output)
            if not isinstance(sessions_data, list):
                raise KiloSessionQueryError(
                    "Kilo session list returned an unexpected JSON shape"
                )

            sessions: set[str] = set()
            for session in sessions_data:
                if not isinstance(session, dict):
                    continue
                session_id = session.get("id")
                recorded_directory = session.get("directory")
                if (
                    isinstance(session_id, str)
                    and self._valid_session_id(session_id)
                    and isinstance(recorded_directory, str)
                    and recorded_directory
                    and self._paths_match(recorded_directory, project_path)
                ):
                    sessions.add(session_id)
            return sessions
        except subprocess.TimeoutExpired:
            error = "Kilo session query timed out within its time budget"
        except json.JSONDecodeError:
            error = "Kilo session list returned invalid JSON"
        except FileNotFoundError:
            error = "Kilo session list could not run; check that the `kilo` executable is installed"
        except OSError:
            error = "Kilo session list could not run; check the executable and project directory"
        except KiloCompatibilityError:
            error = (
                "Kilo version detection failed; verify the installed Kilo CLI version"
            )
        except KiloSessionQueryError as exc:
            error = str(exc)

        if strict:
            raise KiloSessionQueryError(error or "Kilo session query failed") from None
        return set()

    def session_exists(self, session_id: str, project_path: str) -> bool:
        return session_id in self.get_existing_sessions(project_path, strict=True)

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Count messages from Kilo's JSON export without exposing transcript data."""
        if not self._valid_session_id(session_id):
            return 0
        try:
            if session_id not in self.get_existing_sessions(project_path, strict=True):
                return 0
            result = subprocess.run(
                ["kilo", "export", session_id],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=project_path,
                env=self._environment(None, isolated_workspace=True),
                check=False,
            )
            if result.returncode != 0:
                return 0
            exported = json.loads(result.stdout)
            if isinstance(exported, list):
                return len(exported)
            if isinstance(exported, dict) and isinstance(
                exported.get("messages"), list
            ):
                return len(exported["messages"])
        except (
            KiloSessionQueryError,
            json.JSONDecodeError,
            OSError,
            subprocess.SubprocessError,
        ):
            return 0
        return 0

    def encode_project_path(self, project_path: str) -> str:
        """Kilo stores the canonical project directory directly in session info."""
        return project_path

    def get_agent_home_dir(self) -> Path:
        """Return Kilo's global configuration directory."""
        return self.kilo_dir

    def get_agent_name(self) -> str:
        return "kilo"

    def uses_tui(self) -> bool:
        return True

    def supports_permission_prompts(self) -> bool:
        return True

    def get_manual_resume_command(self, session_id: str, project_path: str) -> str:
        if not self._valid_session_id(session_id):
            raise ValueError(
                "Refusing to build a resume command for an invalid Kilo session ID"
            )
        return f"kilo --session {session_id}"

    def uses_file_based_sessions(self) -> bool:
        return False

    def extract_token_usage(
        self, session_id: str, project_path: str
    ) -> dict[str, Any] | None:
        """Kilo does not currently expose machine-readable token statistics."""
        return None

    def generate_text(
        self,
        prompt: str,
        timeout: int = 30,
        display_name: str | None = None,
        config=None,
        model_provider_profile: dict[str, Any] | None = None,
    ) -> str | None:
        """Generate utility text from Kilo's structured JSON event stream."""
        try:
            require_tool("kilo", "generate text with Kilo Code")
            self.get_kilo_version(timeout=min(timeout, 5))
            from devflow.agent.model_config import get_agent_model_config
            from devflow.utils.model_provider import (
                build_env_from_profile,
                get_model_name_from_profile,
                get_profile_arguments,
            )

            settings = get_agent_model_config(
                config,
                self.get_agent_name(),
                utility=True,
                command="commit_message",
                provider_profile=model_provider_profile,
            )
            command = ["kilo", "run", "--format", "json"]
            command.extend(
                get_profile_arguments(model_provider_profile, self.get_agent_name())
            )
            model = get_model_name_from_profile(
                model_provider_profile,
                command="commit_message",
                utility=True,
            ) or settings.get("model")
            model = (
                self._profile_model(
                    {**(model_provider_profile or {}), "model_name": model}
                )
                if model
                else None
            )
            if model:
                command.extend(["--model", model])
            variant = self._reasoning_variant(settings.get("reasoning_effort"))
            if variant:
                command.extend(["--variant", variant])
            if display_name:
                command.extend(["--title", display_name])
            command.append(prompt)
            base_env = (
                build_env_from_profile(model_provider_profile)
                if model_provider_profile
                else os.environ.copy()
            )
            # Utility runs are one-shot DAF operations; don't leave their
            # working directory attached to Kilo's persistent daemon.
            run_env = self._environment(base_env, isolated_workspace=True)
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=run_env,
                check=False,
            )
            if result.returncode != 0:
                logger.warning(
                    "Kilo utility generation failed (exit code %s)", result.returncode
                )
                return None

            text_parts: list[str] = []
            for line in (result.stdout or "").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict) or event.get("type") != "text":
                    continue
                part = event.get("part")
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
            text = "".join(text_parts).strip()
            return text or None
        except (
            FileNotFoundError,
            KiloCompatibilityError,
            OSError,
            subprocess.SubprocessError,
            ValueError,
        ) as exc:
            logger.warning(
                "Kilo utility generation is unavailable (%s)", type(exc).__name__
            )
            return None


__all__ = ["KiloAgent", "KiloCompatibilityError", "KiloSessionQueryError"]
