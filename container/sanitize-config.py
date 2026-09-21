#!/usr/bin/env python3
"""Copy a DevAIFlow config snapshot without copying credential values."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


SENSITIVE_EXACT_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth_token",
    "authorization",
    "client_secret",
    "credentials",
    "env_vars",
    "password",
    "passwd",
    "private_key",
    "refresh_token",
    "secret",
    "token",
}
SENSITIVE_FILE_NAMES = {
    ".env",
    ".env.local",
    "auth.json",
    "credentials.json",
}
TEXT_SECRET_LINE = re.compile(
    r"(?im)^(?P<prefix>\s*(?:export\s+)?[A-Za-z][A-Za-z0-9_.-]*"
    r"(?:api[_-]?key|auth[_-]?token|access[_-]?token|refresh[_-]?token|"
    r"password|passwd|secret|private[_-]?key|credential|authorization)"
    r"[A-Za-z0-9_.-]*\s*[:=]\s*)(?P<value>.*?)(?P<newline>\r?\n|$)"
)


def _is_sensitive_key(key: str) -> bool:
    """Return whether a structured config key can contain a credential."""
    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    if normalized in SENSITIVE_EXACT_KEYS:
        return True
    parts = set(part for part in normalized.split("_") if part)
    return (
        "password" in parts
        or "passwd" in parts
        or "secret" in parts
        or "credential" in parts
        or "credentials" in parts
        or "authorization" in parts
        or "token" in parts
        or ("api" in parts and "key" in parts)
        or ("private" in parts and "key" in parts)
    )


def _sanitize_json(value: Any) -> Any:
    """Recursively remove credential-bearing keys from JSON data."""
    if isinstance(value, dict):
        return {
            key: _sanitize_json(item)
            for key, item in value.items()
            if not _is_sensitive_key(str(key))
        }
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    return value


def _sanitize_text(data: str) -> str:
    """Redact common credential assignments in non-JSON text files."""
    return TEXT_SECRET_LINE.sub(
        lambda match: f'{match.group("prefix")}"<redacted>"{match.group("newline")}',
        data,
    )


def _remove_destination(destination: Path) -> None:
    if destination.is_dir() and not destination.is_symlink():
        shutil.rmtree(destination)
    elif destination.exists() or destination.is_symlink():
        destination.unlink()


def _copy_file(source: Path, destination: Path) -> None:
    """Copy one text config file after removing credential values."""
    lower_name = source.name.lower()
    if (
        lower_name in SENSITIVE_FILE_NAMES
        or lower_name.startswith(".env")
        or any(
            part in lower_name
            for part in ("credential", "secret", "token", "private")
        )
    ):
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".json":
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            # A malformed JSON config cannot be safely inspected. Omitting it
            # is safer than uploading an opaque file to the sandbox.
            return
        content = json.dumps(_sanitize_json(value), indent=2, sort_keys=True)
        content += "\n"
    else:
        try:
            content = _sanitize_text(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return

    destination.write_text(content, encoding="utf-8")
    shutil.copymode(source, destination)


def _copy_entry(source: Path, destination: Path) -> None:
    """Recursively copy a config entry while ignoring symlinks and secrets."""
    if source.is_symlink():
        return
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir(), key=lambda path: path.name):
            _copy_entry(child, destination / child.name)
        shutil.copymode(source, destination)
    elif source.is_file():
        _copy_file(source, destination)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {Path(sys.argv[0]).name} SOURCE DESTINATION", file=sys.stderr)
        return 2

    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    if not source.exists() and not source.is_symlink():
        print(f"Source does not exist: {source}", file=sys.stderr)
        return 1

    _remove_destination(destination)
    _copy_entry(source, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
