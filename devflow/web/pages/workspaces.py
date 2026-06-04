"""Workspaces management page."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from nicegui import ui

from devflow.web.components.nav import create_header
from devflow.web.utils.data_bridge import DataBridge


def _discover_repos(workspace_path: str) -> List[str]:
    """Discover git repositories in a workspace directory.

    Args:
        workspace_path: Path to workspace directory.

    Returns:
        List of repository directory names found.
    """
    repos = []
    try:
        ws_path = Path(workspace_path).expanduser().resolve()
        if ws_path.is_dir():
            for entry in sorted(ws_path.iterdir()):
                if entry.is_dir() and (entry / ".git").exists():
                    repos.append(entry.name)
    except Exception:
        pass
    return repos


def create_workspaces_page(bridge: DataBridge) -> None:
    """Create the workspaces management page.

    Displays configured workspaces, their repositories, and session counts.

    Args:
        bridge: DataBridge instance for data access.
    """
    create_header()

    config = bridge.load_config()

    with ui.column().classes("w-full max-w-5xl mx-auto p-4 gap-4"):
        ui.link("<< Back to Dashboard", "/").classes("text-blue-400 hover:text-blue-300")
        ui.label("Workspaces").classes("text-2xl font-bold")

        if config is None or not config.repos or not config.repos.workspaces:
            ui.label("No workspaces configured.").classes("text-gray-400 text-center py-8")
            ui.label("Use 'daf workspace add' or the Configuration Editor to add workspaces.").classes(
                "text-gray-500 text-center"
            )
            return

        last_used = config.repos.last_used_workspace
        sessions = bridge.list_sessions()

        for ws in config.repos.workspaces:
            is_default = ws.name == last_used
            repos = _discover_repos(ws.path)
            ws_sessions = [s for s in sessions if s.get("workspace") == ws.name]

            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(ws.name).classes("text-lg font-bold")
                        if is_default:
                            ui.badge("Default").classes("bg-yellow-600 text-white")
                    with ui.row().classes("gap-4"):
                        ui.label(f"{len(repos)} repos").classes("text-sm text-gray-400")
                        ui.label(f"{len(ws_sessions)} sessions").classes("text-sm text-gray-400")

                ui.label(ws.path).classes("text-sm text-gray-400 mt-1")

                # Repository list
                if repos:
                    with ui.expansion("Repositories", icon="folder").classes("w-full mt-2"):
                        for repo in repos:
                            ui.label(f"  {repo}").classes("text-sm font-mono")
                else:
                    ui.label("No git repositories found in this workspace.").classes(
                        "text-sm text-gray-500 mt-1"
                    )

                # Sessions in this workspace
                if ws_sessions:
                    with ui.expansion(f"Sessions ({len(ws_sessions)})", icon="assignment").classes("w-full mt-1"):
                        for s in ws_sessions:
                            with ui.row().classes("items-center gap-2"):
                                ui.badge(s["status"].replace("_", " ").title()).classes("text-xs")
                                ui.link(s["name"], f"/session/{s['name']}").classes("text-blue-400")
                                if s.get("issue_key"):
                                    ui.label(f"({s['issue_key']})").classes("text-sm text-gray-400")
