"""Time tracking visualization page."""

from typing import Any, Dict, List

from nicegui import ui

from devflow.web.components.nav import create_header
from devflow.web.utils.data_bridge import DataBridge


def _create_time_summary_cards(data: List[Dict[str, Any]]) -> None:
    """Create summary cards for time tracking.

    Args:
        data: Time tracking data from DataBridge.
    """
    total_minutes = sum(d["total_minutes"] for d in data)
    active_sessions = sum(1 for d in data if d["status"] == "in_progress")
    sessions_with_time = sum(1 for d in data if d["total_minutes"] > 0)

    hours = total_minutes // 60
    minutes = total_minutes % 60

    with ui.row().classes("w-full gap-4 mb-4"):
        with ui.card().classes("bg-blue-800 text-white min-w-[140px]"):
            ui.label(f"{hours}h {minutes}m").classes("text-3xl font-bold")
            ui.label("Total Time").classes("text-sm opacity-80")
        with ui.card().classes("bg-blue-600 text-white min-w-[140px]"):
            ui.label(str(active_sessions)).classes("text-3xl font-bold")
            ui.label("Active Sessions").classes("text-sm opacity-80")
        with ui.card().classes("bg-green-700 text-white min-w-[140px]"):
            ui.label(str(sessions_with_time)).classes("text-3xl font-bold")
            ui.label("Sessions with Time").classes("text-sm opacity-80")


def _create_time_table(data: List[Dict[str, Any]]) -> None:
    """Create a table of sessions with time data.

    Args:
        data: Time tracking data from DataBridge.
    """
    # Sort by total_minutes descending
    sorted_data = sorted(data, key=lambda d: d["total_minutes"], reverse=True)

    columns = [
        {"name": "name", "label": "Session", "field": "name", "sortable": True, "align": "left"},
        {"name": "issue_key", "label": "Issue", "field": "issue_key", "sortable": True, "align": "left"},
        {"name": "status", "label": "Status", "field": "status", "sortable": True, "align": "left"},
        {"name": "total_time", "label": "Total Time", "field": "total_time", "sortable": True, "align": "left"},
        {"name": "total_minutes", "label": "Minutes", "field": "total_minutes", "sortable": True, "align": "right"},
    ]

    table = ui.table(
        columns=columns,
        rows=sorted_data,
        row_key="name",
        pagination={"rowsPerPage": 25, "sortBy": "total_minutes", "descending": True},
    ).classes("w-full")

    table.add_slot(
        "top-left",
        r"""
        <q-input dense outlined debounce="300" v-model="props.filter" placeholder="Search sessions...">
            <template v-slot:append>
                <q-icon name="search" />
            </template>
        </q-input>
        """,
    )
    table.props("filter='' dense")

    def _on_click(e: Any) -> None:
        row = e.args[1]
        if row and "name" in row:
            ui.navigate.to(f"/session/{row['name']}")

    table.on("rowClick", _on_click)
    table.classes("cursor-pointer")


def _create_time_chart(data: List[Dict[str, Any]]) -> None:
    """Create a bar chart of time spent per session.

    Args:
        data: Time tracking data from DataBridge.
    """
    # Top 15 sessions by time
    top = sorted(data, key=lambda d: d["total_minutes"], reverse=True)[:15]
    if not top:
        return

    ui.label("Time by Session (Top 15)").classes("text-lg font-bold mt-4")

    chart_data = {
        "chart": {"type": "bar"},
        "title": {"text": ""},
        "xAxis": {
            "categories": [d["name"][:20] for d in top],
            "labels": {"rotation": -45, "style": {"fontSize": "10px"}},
        },
        "yAxis": {"title": {"text": "Minutes"}},
        "series": [
            {
                "name": "Time (minutes)",
                "data": [d["total_minutes"] for d in top],
                "color": "#3b82f6",
            }
        ],
        "legend": {"enabled": False},
    }

    ui.highchart(chart_data).classes("w-full h-80")


def create_time_tracking_page(bridge: DataBridge) -> None:
    """Create the time tracking visualization page.

    Displays time tracking summaries, a sortable table, and charts.

    Args:
        bridge: DataBridge instance for data access.
    """
    create_header()

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        ui.link("<< Back to Dashboard", "/").classes("text-blue-400 hover:text-blue-300")
        ui.label("Time Tracking").classes("text-2xl font-bold")

        data = bridge.get_time_tracking_data()

        if not data:
            ui.label("No session data available.").classes("text-gray-400 text-center py-8")
            return

        # Summary cards
        _create_time_summary_cards(data)

        # Chart
        _create_time_chart(data)

        # Detailed table
        ui.label("All Sessions").classes("text-lg font-bold mt-4")
        _create_time_table(data)
