"""Implementation of 'daf setup' command."""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.table import Table

console = Console()

BACKEND_ALIASES = {
    "opencode-ai": "opencode",
    "ollama-claude": "ollama",
    "copilot": "github-copilot",
}


def strip_jsonc_comments(text: str) -> str:
    """Strip // and /* */ comments from JSONC text, preserving strings."""
    result: List[str] = []
    i = 0
    length = len(text)
    while i < length:
        if text[i] == '"':
            j = i + 1
            while j < length:
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            result.append(text[i:j])
            i = j
        elif text[i:i+2] == '//':
            while i < length and text[i] != '\n':
                i += 1
        elif text[i:i+2] == '/*':
            end = text.find('*/', i + 2)
            i = end + 2 if end != -1 else length
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def load_overlay(backend: str) -> Optional[Dict[str, Any]]:
    """Load JSONC overlay template for a backend.

    Args:
        backend: Canonical backend name (after alias resolution).

    Returns:
        Parsed overlay dict, or None if no overlay exists.
    """
    overlays_dir = Path(__file__).parent.parent.parent / "templates" / "overlays"
    overlay_path = overlays_dir / f"{backend}.jsonc"

    if not overlay_path.exists():
        return None

    raw = overlay_path.read_text(encoding="utf-8")
    stripped = strip_jsonc_comments(raw)

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing overlay template {overlay_path}: {e}[/red]")
        return None


def deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Deep-merge overlay into base without overwriting existing keys.

    Args:
        base: Existing config dict (modified in place).
        overlay: Overlay dict to merge in.

    Returns:
        Tuple of (merged dict, list of added key paths).
    """
    added: List[str] = []
    _deep_merge_recursive(base, overlay, "", added)
    return base, added


def _deep_merge_recursive(
    base: Dict[str, Any], overlay: Dict[str, Any], prefix: str, added: List[str]
) -> None:
    for key, value in overlay.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in base:
            base[key] = value
            added.append(path)
        elif isinstance(value, dict) and isinstance(base[key], dict):
            _deep_merge_recursive(base[key], value, path, added)
        elif isinstance(value, list) and isinstance(base[key], list):
            for item in value:
                if item not in base[key]:
                    base[key].append(item)
                    added.append(f"{path}[]")
        elif isinstance(value, list) and isinstance(base[key], list):
            for item in value:
                if item not in base[key]:
                    base[key].append(item)
                    added.append(f"{path}[]")


def resolve_target_path(backend: str, scope: str) -> Path:
    """Determine target config file path for a backend.

    Args:
        backend: Canonical backend name.
        scope: 'project' or 'global'.

    Returns:
        Path to the target config file.
    """
    if backend == "opencode":
        if scope == "global":
            xdg = os.environ.get("XDG_CONFIG_HOME")
            if xdg:
                return Path(xdg) / "opencode" / "opencode.json"
            return Path.home() / ".config" / "opencode" / "opencode.json"
        return Path.cwd() / "opencode.json"

    if backend == "claude":
        if scope == "global":
            claude_dir = os.environ.get("CLAUDE_CONFIG_DIR")
            if claude_dir:
                return Path(claude_dir) / "settings.json"
            return Path.home() / ".claude" / "settings.json"
        if scope == "local":
            return Path.cwd() / ".claude" / "settings.local.json"
        return Path.cwd() / ".claude" / "settings.json"

    return Path.cwd() / f"{backend}.json"


SUPPORTED_OVERLAY_BACKENDS = ["claude", "opencode"]


def setup_agent_config(
    dry_run: bool = False,
    scope: str = "project",
    all_agents: bool = False,
    output_json: bool = False,
) -> int:
    """Configure agent integration by merging overlay template into agent config.

    Args:
        dry_run: Preview changes without writing.
        scope: 'project', 'local', or 'global'.
        all_agents: Configure all supported agents at once.
        output_json: Output JSON format.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    if all_agents:
        worst = 0
        for agent_backend in SUPPORTED_OVERLAY_BACKENDS:
            result = _setup_single_backend(
                agent_backend, dry_run=dry_run, scope=scope, output_json=output_json
            )
            if result > worst:
                worst = result
        return worst

    from devflow.config.loader import ConfigLoader

    try:
        config_loader = ConfigLoader()
        config = config_loader.load_config(validate=False)
        backend = config.agent_backend or "claude"
    except Exception:
        backend = "claude"

    canonical = BACKEND_ALIASES.get(backend, backend)
    return _setup_single_backend(
        canonical, dry_run=dry_run, scope=scope, output_json=output_json
    )


def _setup_single_backend(
    canonical: str,
    dry_run: bool = False,
    scope: str = "project",
    output_json: bool = False,
) -> int:
    """Configure a single agent backend."""
    overlay = load_overlay(canonical)

    if overlay is None:
        if output_json:
            print(json.dumps({
                "success": False,
                "message": f"No overlay template for backend '{canonical}'",
            }, indent=2))
        else:
            console.print(
                f"[yellow]No overlay template available for agent backend "
                f"'[cyan]{canonical}[/cyan]'[/yellow]"
            )
            console.print(
                "[dim]Overlay templates are in devflow/templates/overlays/[/dim]"
            )
        return 0

    target_path = resolve_target_path(canonical, scope)

    existing: Dict[str, Any] = {}
    if target_path.exists():
        try:
            raw = target_path.read_text(encoding="utf-8")
            stripped = strip_jsonc_comments(raw)
            existing = json.loads(stripped)
        except (json.JSONDecodeError, OSError) as e:
            if output_json:
                print(json.dumps({
                    "success": False,
                    "error": f"Failed to read {target_path}: {e}",
                }, indent=2))
            else:
                console.print(f"[red]Failed to read {target_path}: {e}[/red]")
            return 1

    skip_keys = {"$schema"}
    overlay_filtered = {k: v for k, v in overlay.items() if k not in skip_keys}

    if "$schema" in overlay and "$schema" not in existing:
        existing["$schema"] = overlay["$schema"]

    merged, added = deep_merge(existing, overlay_filtered)

    if output_json:
        print(json.dumps({
            "success": True,
            "backend": canonical,
            "target": str(target_path),
            "scope": scope,
            "dry_run": dry_run,
            "added": added,
            "skipped": _count_skipped(overlay_filtered, added),
        }, indent=2))
        if not dry_run and added:
            _write_config(target_path, merged)
        return 0

    from devflow.agent.factory import AGENT_DISPLAY_NAMES
    display_name = AGENT_DISPLAY_NAMES.get(canonical, canonical)
    console.print(f"\n[bold]Setting up {display_name} integration[/bold]")
    console.print(f"  Backend: [cyan]{canonical}[/cyan]")
    console.print(f"  Scope:   [cyan]{scope}[/cyan]")
    console.print(f"  Target:  [cyan]{target_path}[/cyan]")

    if not added:
        console.print("\n[green]All overlay rules already present. Nothing to do.[/green]")
        return 0

    table = Table(title="Rules to add", show_header=True, header_style="bold")
    table.add_column("Path", style="cyan")
    table.add_column("Status", width=10)

    for path in added:
        table.add_row(path, "[green]+ add[/green]")

    console.print()
    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run — no changes written.[/yellow]")
        return 0

    if _write_config(target_path, merged):
        console.print(f"\n[green]Wrote {len(added)} rule(s) to {target_path}[/green]")
        return 0

    return 1


def _count_skipped(overlay: Dict[str, Any], added: List[str]) -> int:
    """Count leaf keys in overlay that were skipped (already existed)."""
    total = _count_leaves(overlay, "")
    return total - len(added)


def _count_leaves(d: Dict[str, Any], prefix: str) -> int:
    count = 0
    for key, value in d.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            count += _count_leaves(value, path)
        else:
            count += 1
    return count


def _write_config(path: Path, data: Dict[str, Any]) -> bool:
    """Write config JSON to file, creating parent directories if needed."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True
    except OSError as e:
        console.print(f"[red]Failed to write {path}: {e}[/red]")
        return False
