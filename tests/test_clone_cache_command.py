"""Tests for retained clone review and explicit cleanup."""

import json
from pathlib import Path
from types import SimpleNamespace

from devflow.cli.commands import cleanup_clones_command as command
from devflow.utils.clone_cache import CloneCacheEntry


def _entry(path: Path, status: str = "eligible") -> CloneCacheEntry:
    return CloneCacheEntry(
        root=path,
        last_used=1_700_000_000,
        size=1024,
        status=status,
        reason="ready for explicit removal" if status == "eligible" else "active lease",
        repositories=("repo",),
    )


def test_cleanup_clones_json_lists_entries_without_selecting(
    monkeypatch, capsys, tmp_path
):
    entry = _entry(tmp_path / "daf-session-a")
    monkeypatch.setattr(
        command, "ConfigLoader", lambda: SimpleNamespace(load_config=lambda: None)
    )
    monkeypatch.setattr(
        command, "CloneCache", lambda _config: SimpleNamespace(inspect=lambda: [entry])
    )
    monkeypatch.setattr(
        command, "SessionManager", lambda _loader: SimpleNamespace(list_sessions=list)
    )
    monkeypatch.delenv("DEVAIFLOW_IN_SESSION", raising=False)

    command.cleanup_clones(output_json_mode=True)

    result = json.loads(capsys.readouterr().out)
    assert result["success"] is True
    assert result["data"]["entries"][0]["path"] == str(entry.root)


def test_cleanup_clones_reports_partial_removal(monkeypatch, capsys, tmp_path):
    removable = _entry(tmp_path / "daf-session-a")
    protected = _entry(tmp_path / "daf-session-b", "protected")
    cache = SimpleNamespace(
        inspect=lambda: [removable, protected],
        remove=lambda root: (
            root == removable.root,
            None if root == removable.root else "active lease",
        ),
    )
    monkeypatch.setattr(
        command, "ConfigLoader", lambda: SimpleNamespace(load_config=lambda: None)
    )
    monkeypatch.setattr(command, "CloneCache", lambda _config: cache)
    monkeypatch.setattr(
        command, "SessionManager", lambda _loader: SimpleNamespace(list_sessions=list)
    )
    monkeypatch.delenv("DEVAIFLOW_IN_SESSION", raising=False)

    command.cleanup_clones(
        select=(str(removable.root),), force=True, output_json_mode=True
    )

    result = json.loads(capsys.readouterr().out)
    assert [item["path"] for item in result["data"]["deleted"]] == [str(removable.root)]
    assert result["data"]["refused"] == []
