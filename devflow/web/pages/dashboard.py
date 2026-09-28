"""Dashboard page -- main entry point showing session overview."""

from typing import Any, Dict, List

from nicegui import ui

from devflow.web.components.nav import create_header
from devflow.web.components.session_table import create_session_table
from devflow.web.utils.data_bridge import DataBridge


def _create_status_cards(counts: Dict[str, int]) -> None:
    """Create status summary cards at the top of the dashboard.

    Args:
        counts: Dictionary mapping status to session count.
    """
    total = sum(counts.values())
    in_progress = counts.get("in_progress", 0)
    paused = counts.get("paused", 0)
    complete = counts.get("complete", 0)
    created = counts.get("created", 0)

    with ui.row().classes("w-full gap-4 mb-4"):
        _stat_card("Total Sessions", str(total), "bg-blue-800")
        _stat_card("In Progress", str(in_progress), "bg-blue-600")
        _stat_card("Paused", str(paused), "bg-yellow-700")
        _stat_card("Complete", str(complete), "bg-green-700")
        _stat_card("Created", str(created), "bg-gray-600")


def _stat_card(label: str, value: str, color_class: str) -> None:
    """Create a single status summary card.

    Args:
        label: Card label text.
        value: Card value text.
        color_class: Tailwind CSS background color class.
    """
    with ui.card().classes(f"{color_class} text-white min-w-[140px]"):
        ui.label(value).classes("text-3xl font-bold")
        ui.label(label).classes("text-sm opacity-80")


def create_dashboard_page(bridge: DataBridge) -> None:
    """Create the main dashboard page.

    Displays session status summary cards, filter controls, and a sortable
    session table. Supports auto-refresh and navigation to session detail pages.

    Args:
        bridge: DataBridge instance for data access.
    """
    create_header()

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        all_sessions = bridge.list_sessions()

        # Status summary cards are rebuilt during each refresh so the overview
        # stays consistent with the session table.
        cards_container = ui.row().classes("w-full gap-4 mb-4")

        def refresh_cards() -> None:
            cards_container.clear()
            with cards_container:
                _create_status_cards(bridge.get_session_count_by_status())

        refresh_cards()

        # Filter controls
        with ui.row().classes("w-full flex-wrap gap-3"):
            status_filter = ui.select(
                label="Filter by Status",
                options=["All", "created", "in_progress", "paused", "complete"],
                value="All",
            ).classes("w-48")
            workspace_filter = ui.select(
                label="Filter by Workspace",
                options=_filter_options(all_sessions, "workspace", "Unassigned"),
                value="All",
            ).classes("w-48")
            tracker_filter = ui.select(
                label="Filter by Issue Tracker",
                options=_filter_options(all_sessions, "issue_tracker"),
                value="All",
            ).classes("w-48")

        # Session table container
        table_container = ui.column().classes("w-full")

        def load_sessions() -> None:
            """Load and display sessions based on current filter."""
            table_container.clear()
            status = None if status_filter.value == "All" else status_filter.value
            workspace = (
                None
                if workspace_filter.value == "All"
                else (
                    ""
                    if workspace_filter.value == "Unassigned"
                    else workspace_filter.value
                )
            )
            issue_tracker = (
                None if tracker_filter.value == "All" else tracker_filter.value
            )
            sessions = bridge.list_sessions(
                status=status,
                workspace=workspace,
                issue_tracker=issue_tracker,
            )

            with table_container:
                if not sessions:
                    ui.label("No sessions found.").classes(
                        "text-gray-400 text-center py-8"
                    )
                else:
                    create_session_table(
                        sessions=sessions,
                        on_row_click=lambda name: ui.navigate.to(f"/session/{name}"),
                    )

        # Reload when filter changes
        status_filter.on_value_change(lambda _: load_sessions())
        workspace_filter.on_value_change(lambda _: load_sessions())
        tracker_filter.on_value_change(lambda _: load_sessions())

        # Initial load
        load_sessions()

        # Auto-refresh timer (every 10 seconds)
        def refresh() -> None:
            refresh_cards()
            load_sessions()

        ui.timer(10.0, refresh)


def _filter_options(
    sessions: List[Dict[str, Any]], key: str, empty_label: str = ""
) -> List[str]:
    """Build a stable select list from the current session data."""
    values = {
        session.get(key) or empty_label
        for session in sessions
        if session.get(key) or empty_label
    }
    return ["All", *sorted(values)]
