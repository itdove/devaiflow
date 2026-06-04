"""Issue tracker page -- view JIRA/GitHub/GitLab tickets linked to sessions."""

from typing import Any, Dict, List

from nicegui import ui

from devflow.web.components.nav import create_header
from devflow.web.utils.data_bridge import DataBridge


def _create_issue_table(sessions: List[Dict[str, Any]]) -> None:
    """Create a table of sessions with issue tracker links.

    Args:
        sessions: List of session dictionaries.
    """
    # Filter to sessions with issue keys
    linked = [s for s in sessions if s.get("issue_key")]

    if not linked:
        ui.label("No sessions linked to issue tracker tickets.").classes(
            "text-gray-400 text-center py-8"
        )
        return

    columns = [
        {"name": "issue_key", "label": "Issue Key", "field": "issue_key", "sortable": True, "align": "left"},
        {"name": "name", "label": "Session", "field": "name", "sortable": True, "align": "left"},
        {"name": "status", "label": "Status", "field": "status", "sortable": True, "align": "left"},
        {"name": "goal", "label": "Goal", "field": "goal", "sortable": True, "align": "left"},
        {"name": "time", "label": "Time", "field": "time", "sortable": True, "align": "left"},
        {"name": "last_active", "label": "Last Active", "field": "last_active", "sortable": True, "align": "left"},
    ]

    table = ui.table(
        columns=columns,
        rows=linked,
        row_key="name",
        pagination={"rowsPerPage": 25, "sortBy": "last_active", "descending": True},
    ).classes("w-full")

    table.add_slot(
        "top-left",
        r"""
        <q-input dense outlined debounce="300" v-model="props.filter" placeholder="Search issues...">
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


def create_issue_tracker_page(bridge: DataBridge) -> None:
    """Create the issue tracker view page.

    Shows all sessions that are linked to JIRA/GitHub/GitLab issues,
    with links to external issue trackers and session details.

    Args:
        bridge: DataBridge instance for data access.
    """
    create_header()

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        ui.link("<< Back to Dashboard", "/").classes("text-blue-400 hover:text-blue-300")
        ui.label("Issue Tracker").classes("text-2xl font-bold")

        # Config summary
        config_summary = bridge.get_config_summary()
        with ui.row().classes("gap-4"):
            if "jira" in config_summary:
                with ui.card().classes("bg-gray-800"):
                    ui.label("JIRA").classes("font-bold")
                    ui.label(config_summary["jira"].get("url", "Not configured")).classes("text-sm text-gray-400")
                    ui.label(f"Project: {config_summary['jira'].get('project', 'N/A')}").classes("text-sm text-gray-400")
            if config_summary.get("github", {}).get("enabled"):
                with ui.card().classes("bg-gray-800"):
                    ui.label("GitHub").classes("font-bold")
                    ui.label(config_summary["github"].get("repository", "Not configured")).classes("text-sm text-gray-400")

        # Issue table
        sessions = bridge.list_sessions()
        _create_issue_table(sessions)

        # Auto-refresh
        ui.timer(15.0, lambda: None)  # Placeholder for future auto-refresh
