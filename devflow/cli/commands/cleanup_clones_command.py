"""Review and explicitly remove retained managed clone-cache entries."""

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.prompt import Confirm, Prompt

from devflow.cli.utils import is_non_interactive, output_json, require_outside_claude
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager
from devflow.utils.clone_cache import CloneCache, CloneCacheEntry
from devflow.utils.clone_lifecycle import get_temp_directory_root

console = Console()


def _format_size(size: int | None) -> str:
    if size is None:
        return "unknown"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return "unknown"


def _session_names(
    entries: list[CloneCacheEntry], manager: SessionManager
) -> dict[Path, str]:
    names: dict[Path, str] = {}
    for session in manager.list_sessions():
        for conversation in session.conversations.values():
            for context in conversation.get_all_sessions():
                for value in (context.temp_directory, context.worktree_path):
                    if not value:
                        continue
                    try:
                        root = get_temp_directory_root(value)
                    except (OSError, RuntimeError):
                        continue
                    if any(entry.root == root for entry in entries):
                        names[root] = session.name
    return names


def _payload(entry: CloneCacheEntry, names: dict[Path, str]) -> dict[str, Any]:
    return {
        "session": names.get(entry.root),
        "path": str(entry.root),
        "size": entry.size,
        "last_activity": entry.last_used,
        "status": entry.status,
        "reason": entry.reason,
        "repositories": list(entry.repositories),
    }


def _print_entries(entries: list[CloneCacheEntry], names: dict[Path, str]) -> None:
    for index, entry in enumerate(entries, 1):
        session = names.get(entry.root, "unassociated")
        last = "unknown" if entry.last_used is None else f"{entry.last_used:.0f}"
        console.print(
            f"[{index}] {session} | {entry.status} | {_format_size(entry.size)} | "
            f"last activity {last}\n    {entry.root}\n    {entry.reason}"
        )


@require_outside_claude
def cleanup_clones(
    *,
    select: tuple[str, ...] = (),
    all_entries: bool = False,
    dry_run: bool = False,
    force: bool = False,
    output_json_mode: bool = False,
) -> None:
    """Review retained clone-cache entries and remove confirmed selections."""
    config_loader = ConfigLoader()
    config = config_loader.load_config()
    cache = CloneCache(config)
    entries = cache.inspect()
    manager = SessionManager(config_loader)
    names = _session_names(entries, manager)

    if output_json_mode:
        if not select and not all_entries:
            output_json(True, {"entries": [_payload(item, names) for item in entries]})
            return
    elif entries:
        _print_entries(entries, names)
    elif not output_json_mode:
        console.print("No managed clone-cache entries found.")

    eligible = [entry for entry in entries if entry.eligible]
    selected: list[CloneCacheEntry] = []
    if all_entries:
        selected = eligible
    elif select:
        by_path = {str(entry.root): entry for entry in eligible}
        by_index = {
            str(index): entry
            for index, entry in enumerate(entries, 1)
            if entry.eligible
        }
        for value in select:
            entry = by_path.get(value) or by_index.get(value)
            if entry and entry not in selected:
                selected.append(entry)
    elif not is_non_interactive(output_json_mode):
        answer = Prompt.ask("Select entries by number/path, or 'all'", default="")
        if answer.strip().lower() == "all":
            selected = eligible
        elif answer.strip():
            by_index = {
                str(index): entry
                for index, entry in enumerate(entries, 1)
                if entry.eligible
            }
            for value in answer.split(","):
                entry = by_index.get(value.strip())
                if entry and entry not in selected:
                    selected.append(entry)

    if not selected:
        if output_json_mode:
            output_json(
                True,
                {
                    "entries": [_payload(item, names) for item in entries],
                    "deleted": [],
                    "refused": [],
                },
            )
        return

    if not output_json_mode:
        console.print("\nSelected for deletion:")
        _print_entries(selected, names)
    if dry_run:
        if output_json_mode:
            output_json(
                True,
                {
                    "entries": [_payload(item, names) for item in entries],
                    "selected": [_payload(item, names) for item in selected],
                    "deleted": [],
                    "refused": [],
                },
            )
        else:
            console.print("Dry run: no entries were removed.")
        return
    if not force and (
        is_non_interactive(output_json_mode)
        or not Confirm.ask("Delete selected entries?", default=False)
    ):
        if output_json_mode:
            output_json(
                True,
                {
                    "entries": [_payload(item, names) for item in entries],
                    "selected": [_payload(item, names) for item in selected],
                    "deleted": [],
                    "refused": [
                        {"path": str(item.root), "reason": "confirmation declined"}
                        for item in selected
                    ],
                },
            )
        else:
            console.print("Cancelled; no entries were removed.")
        return

    deleted: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for entry in selected:
        removed, reason = cache.remove(entry.root)
        result = {"path": str(entry.root), "reason": reason}
        (deleted if removed else refused).append(result)
        if not output_json_mode:
            console.print(
                f"{'Removed' if removed else 'Preserved'}: {entry.root}{f' ({reason})' if reason else ''}"
            )
    if output_json_mode:
        output_json(
            True,
            {
                "entries": [_payload(item, names) for item in entries],
                "deleted": deleted,
                "refused": refused,
            },
        )
