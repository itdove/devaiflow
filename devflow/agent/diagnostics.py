"""Safe diagnostics for AI agent launch failures."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from devflow.exceptions import ToolNotFoundError

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|auth(?:entication)?[_-]?token|access[_-]?token|"
    r"client[_-]?secret|secret|password|passwd|credential|private[_-]?key)"
)
_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(\b(?:api[_-]?key|auth(?:entication)?[_-]?token|access[_-]?token|"
    r"client[_-]?secret|secret|password|passwd|credential|private[_-]?key)\b"
    r"\s*(?:=|:)\s*)([^\s,;]+)"
)
_AUTH_HEADER_PATTERN = re.compile(r"(?i)\b(?:bearer|basic)\s+[^\s,;]+")
_TOKEN_PATTERN = re.compile(
    r"(?i)\b(?:sk-(?:ant|proj)?-[A-Za-z0-9_-]{8,}|"
    r"gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,}|"
    r"xox[baprs]-[A-Za-z0-9-]{8,})\b"
)
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
_MAX_DIAGNOSTIC_LENGTH = 4000


@dataclass(frozen=True)
class AgentFailure:
    """Structured, sanitized information about an agent launch failure."""

    backend: str
    display_name: str
    phase: str
    executable: str
    exit_code: int | None = None
    diagnostics: str = ""
    code: str = "AGENT_LAUNCH_FAILED"
    missing_executable: bool = False
    install_url: str = ""

    @property
    def summary(self) -> str:
        """Return a concise failure summary without diagnostic payloads."""
        if self.missing_executable:
            return (
                f"{self.display_name} {self.phase} failed: executable "
                f"'{self.executable}' was not found on PATH. Install {self.display_name} "
                f"or add '{self.executable}' to PATH."
            )
        if self.exit_code is not None:
            return f"{self.display_name} {self.phase} failed with exit code {self.exit_code}."
        return f"{self.display_name} {self.phase} failed."

    @property
    def display_message(self) -> str:
        """Return the terminal message, including sanitized diagnostics."""
        if self.diagnostics:
            details = "\n".join(f"  {line}" for line in self.diagnostics.splitlines())
            return f"{self.summary}\nAgent diagnostics:\n{details}"
        return f"{self.summary}\nAgent diagnostics: (none provided)"

    def as_error(self) -> dict[str, Any]:
        """Return a machine-readable error payload."""
        error: dict[str, Any] = {
            "code": self.code,
            "message": self.summary,
            "backend": self.backend,
            "phase": self.phase,
            "executable": self.executable,
            "exit_code": self.exit_code,
            "diagnostics": self.diagnostics or "(none provided)",
        }
        if self.install_url:
            error["install_url"] = self.install_url
        if self.missing_executable:
            error["hint"] = (
                f"Install {self.display_name} or add '{self.executable}' to PATH."
            )
        return error

    def log_message(self) -> str:
        """Return a compact diagnostic-log entry."""
        return (
            f"agent_backend={self.backend} phase={self.phase} code={self.code} "
            f"executable={self.executable} exit_code={self.exit_code} "
            f"message={self.summary} diagnostics={self.diagnostics or '(none provided)'}"
        )


class AgentLaunchError(RuntimeError):
    """Raised after an agent process fails or cannot be started."""

    def __init__(self, failure: AgentFailure):
        self.failure = failure
        super().__init__(failure.display_message)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
            if isinstance(dumped, Mapping):
                return dumped
        except (AttributeError, TypeError, ValueError):
            pass
    return {}


def _text_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else ""


def _sensitive_values(env: Mapping[str, str] | None, profile: Any) -> set[str]:
    values: set[str] = set()

    for key, value in (env or {}).items():
        if _SENSITIVE_KEY_PATTERN.search(str(key)) and isinstance(value, str) and value:
            values.add(value)

    profile_data = _as_mapping(profile)
    for key, value in profile_data.items():
        if _SENSITIVE_KEY_PATTERN.search(str(key)) and isinstance(value, str) and value:
            values.add(value)

    profile_env = profile_data.get("env_vars")
    if isinstance(profile_env, Mapping):
        for key, value in profile_env.items():
            if (
                _SENSITIVE_KEY_PATTERN.search(str(key))
                and isinstance(value, str)
                and value
            ):
                values.add(value)

    return {value for value in values if len(value) >= 3}


def _redact_url(match: re.Match[str]) -> str:
    raw_url = match.group(0)
    try:
        parsed = urlsplit(raw_url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            if parsed.scheme and parsed.hostname:
                host = parsed.hostname
                if parsed.port:
                    host = f"{host}:{parsed.port}"
                return urlunsplit((parsed.scheme, host, parsed.path, "", ""))
            return "<redacted URL>"
    except (TypeError, ValueError):
        return "<redacted URL>"
    return raw_url


def sanitize_agent_diagnostics(
    value: Any,
    *,
    env: Mapping[str, str] | None = None,
    profile: Any = None,
) -> str:
    """Redact credentials and bound diagnostic output size."""
    text = _text_value(value).strip()
    if not text:
        return ""

    for secret in sorted(_sensitive_values(env, profile), key=len, reverse=True):
        text = text.replace(secret, "<redacted>")

    text = _SENSITIVE_ASSIGNMENT_PATTERN.sub(r"\1<redacted>", text)
    text = _AUTH_HEADER_PATTERN.sub("<redacted authorization>", text)
    text = _TOKEN_PATTERN.sub("<redacted token>", text)
    text = _URL_PATTERN.sub(_redact_url, text)

    if len(text) > _MAX_DIAGNOSTIC_LENGTH:
        text = text[:_MAX_DIAGNOSTIC_LENGTH].rstrip() + " ...[truncated]"
    return text


def _read_process_stream(stream: Any) -> str:
    if stream is None or stream is subprocess.DEVNULL:
        return ""
    if isinstance(stream, (str, bytes)):
        return _text_value(stream).strip()
    read = getattr(stream, "read", None)
    if not callable(read):
        return ""
    try:
        return _text_value(read()).strip()
    except (AttributeError, OSError, TypeError, ValueError):
        return ""


def collect_process_diagnostics(
    process: Any,
    *,
    env: Mapping[str, str] | None = None,
    profile: Any = None,
) -> str:
    """Read available process output without changing interactive streams."""
    output = []
    for stream_name in ("stderr", "stdout"):
        stream_output = _read_process_stream(getattr(process, stream_name, None))
        if stream_output:
            output.append(stream_output)
    return sanitize_agent_diagnostics("\n".join(output), env=env, profile=profile)


def failure_from_process(
    process: Any,
    *,
    backend: str,
    display_name: str,
    phase: str,
    executable: str,
    env: Mapping[str, str] | None = None,
    profile: Any = None,
) -> AgentFailure:
    """Build a failure from a non-zero process result."""
    return AgentFailure(
        backend=backend,
        display_name=display_name,
        phase=phase,
        executable=executable,
        exit_code=getattr(process, "returncode", None),
        diagnostics=collect_process_diagnostics(process, env=env, profile=profile),
        code="AGENT_PROCESS_EXITED",
    )


def failure_from_exception(
    error: BaseException,
    *,
    backend: str,
    display_name: str,
    phase: str,
    executable: str,
    env: Mapping[str, str] | None = None,
    profile: Any = None,
) -> AgentFailure:
    """Build a sanitized failure from a launch or resume exception."""
    if isinstance(error, ToolNotFoundError):
        missing_executable = error.tool or executable
        return AgentFailure(
            backend=backend,
            display_name=display_name,
            phase=phase,
            executable=missing_executable,
            code="AGENT_EXECUTABLE_NOT_FOUND",
            missing_executable=True,
            install_url=error.install_url,
        )

    if isinstance(error, FileNotFoundError):
        missing_executable = Path(error.filename).name if error.filename else executable
        if not error.filename or missing_executable == executable:
            return AgentFailure(
                backend=backend,
                display_name=display_name,
                phase=phase,
                executable=missing_executable,
                code="AGENT_EXECUTABLE_NOT_FOUND",
                missing_executable=True,
            )

    details = _text_value(getattr(error, "stderr", ""))
    if not details:
        details = _text_value(getattr(error, "output", ""))
    if not details:
        details = str(error)

    return AgentFailure(
        backend=backend,
        display_name=display_name,
        phase=phase,
        executable=executable,
        diagnostics=sanitize_agent_diagnostics(details, env=env, profile=profile),
    )
