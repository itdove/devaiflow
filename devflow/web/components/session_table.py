"""Session list table component with filtering and sorting."""

from typing import Any, Callable, Dict, List, Optional

from nicegui import ui


COLUMNS = [
    {
        "name": "status",
        "label": "Status",
        "field": "status",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "name",
        "label": "Name",
        "field": "name",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "workspace",
        "label": "Workspace",
        "field": "workspace",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "issue_key",
        "label": "Issue Key",
        "field": "issue_key",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "goal",
        "label": "Goal",
        "field": "goal",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "time",
        "label": "Time",
        "field": "time",
        "sortable": True,
        "align": "left",
    },
    {
        "name": "last_active",
        "label": "Last Active",
        "field": "last_active",
        "sortable": True,
        "align": "left",
    },
]


def create_session_table(
    sessions: List[Dict[str, Any]],
    on_row_click: Optional[Callable[[str], None]] = None,
) -> ui.table:
    """Create a sortable, filterable session table.

    Args:
        sessions: List of session dictionaries from DataBridge.
        on_row_click: Optional callback when a row is clicked (receives session name).

    Returns:
        NiceGUI table element.
    """
    table = ui.table(
        columns=COLUMNS,
        rows=sessions,
        row_key="name",
        pagination={"rowsPerPage": 25, "sortBy": "last_active", "descending": True},
    ).classes("w-full")

    # Add search/filter input
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

    # Make rows clickable
    if on_row_click:

        def handle_click(e: Any) -> None:
            row = e.args[1]  # Second arg is the row data
            if row and "name" in row:
                on_row_click(row["name"])

        table.on("rowClick", handle_click)
        table.classes("cursor-pointer")

    return table
