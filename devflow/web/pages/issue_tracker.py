"""Issue tracker page -- view JIRA/GitHub/GitLab tickets linked to sessions."""

from typing import Any, Dict, List

from nicegui import ui

from devflow.web.components.nav import create_header
from devflow.web.utils.data_bridge import DataBridge


def _create_issue_table(
    sessions: List[Dict[str, Any]],
    on_issue_click: Any,
) -> None:
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
        {
            "name": "issue_key",
            "label": "Issue Key",
            "field": "issue_key",
            "sortable": True,
            "align": "left",
        },
        {
            "name": "issue_tracker",
            "label": "Tracker",
            "field": "issue_tracker",
            "sortable": True,
            "align": "left",
        },
        {
            "name": "name",
            "label": "Session",
            "field": "name",
            "sortable": True,
            "align": "left",
        },
        {
            "name": "status",
            "label": "Status",
            "field": "status",
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
        if row:
            on_issue_click(row)

    table.on("rowClick", _on_click)
    table.classes("cursor-pointer")


def _create_issue_dialog(bridge: DataBridge) -> Any:
    """Create a dialog that loads issue details and accepts comments."""
    dialog = ui.dialog()
    with dialog:
        with ui.card().classes("w-full max-w-3xl"):
            content = ui.column().classes("w-full gap-3")
            with ui.row().classes("w-full justify-end"):
                ui.button("Close", on_click=dialog.close).props("flat")

    def show_issue(row: Dict[str, Any]) -> None:
        content.clear()
        with content:
            issue_key = row.get("issue_key", "")
            ui.label(issue_key).classes("text-2xl font-bold")
            ui.label(f"Tracker: {row.get('issue_tracker', 'unknown')}").classes(
                "text-gray-400"
            )
            if row.get("name"):
                ui.link("Open linked session", f"/session/{row['name']}").classes(
                    "text-blue-400"
                )
            details = bridge.get_issue_details(issue_key)
            if details is None:
                ui.label("Issue details could not be loaded.").classes("text-red-400")
            else:
                summary = details.get("summary") or row.get("goal") or "No summary"
                ui.label(summary).classes("text-xl")
                if details.get("status"):
                    ui.label(f"Status: {details['status']}").classes("text-gray-300")
                if details.get("description"):
                    ui.markdown(str(details["description"])).classes(
                        "w-full bg-gray-800 p-3 rounded"
                    )
                issue_url = details.get("url") or row.get("issue_url")
                if issue_url:
                    ui.link("Open in issue tracker", issue_url, new_tab=True).classes(
                        "text-blue-400"
                    )

                comments = details.get("comments", [])
                if comments:
                    ui.label("Comments").classes("text-lg font-bold")
                    for comment in comments:
                        author = comment.get("author", "unknown")
                        body = comment.get("body", "")
                        ui.markdown(f"**{author}**\n\n{body}").classes(
                            "w-full bg-gray-800 p-2 rounded"
                        )

            ui.separator()
            ui.label("Add Comment").classes("font-semibold")
            comment_input = ui.textarea(placeholder="Enter a comment...").classes(
                "w-full"
            )

            def add_comment() -> None:
                if not comment_input.value or not comment_input.value.strip():
                    ui.notify("Please enter a comment.", type="warning")
                    return
                if bridge.add_issue_comment(issue_key, comment_input.value):
                    ui.notify("Comment added.", type="positive")
                    comment_input.value = ""
                else:
                    ui.notify("Failed to add comment.", type="negative")

            ui.button("Add Comment", on_click=add_comment).classes("bg-blue-600")

        dialog.open()

    return show_issue


def create_issue_tracker_page(bridge: DataBridge) -> None:
    """Create the issue tracker view page.

    Shows all sessions that are linked to JIRA/GitHub/GitLab issues,
    with links to external issue trackers and session details.

    Args:
        bridge: DataBridge instance for data access.
    """
    create_header()

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-4"):
        ui.link("<< Back to Dashboard", "/").classes(
            "text-blue-400 hover:text-blue-300"
        )
        ui.label("Issue Tracker").classes("text-2xl font-bold")

        # Config summary
        config_summary = bridge.get_config_summary()
        ui.label(
            f"Backend: {config_summary.get('issue_tracker_backend', 'unknown')}"
        ).classes("text-gray-400")
        with ui.row().classes("gap-4"):
            if "jira" in config_summary:
                with ui.card().classes("bg-gray-800"):
                    ui.label("JIRA").classes("font-bold")
                    ui.label(
                        config_summary["jira"].get("url", "Not configured")
                    ).classes("text-sm text-gray-400")
                    ui.label(
                        f"Project: {config_summary['jira'].get('project', 'N/A')}"
                    ).classes("text-sm text-gray-400")
            if config_summary.get("github", {}).get("enabled"):
                with ui.card().classes("bg-gray-800"):
                    ui.label("GitHub").classes("font-bold")
                    ui.label(
                        config_summary["github"].get("repository", "Not configured")
                    ).classes("text-sm text-gray-400")
            if config_summary.get("gitlab", {}).get("enabled"):
                with ui.card().classes("bg-gray-800"):
                    ui.label("GitLab").classes("font-bold")
                    ui.label(
                        config_summary["gitlab"].get("repository", "Not configured")
                    ).classes("text-sm text-gray-400")

        show_issue = _create_issue_dialog(bridge)
        table_container = ui.column().classes("w-full")

        def refresh() -> None:
            table_container.clear()
            with table_container:
                _create_issue_table(bridge.list_sessions(), show_issue)

        refresh()

        # Auto-refresh
        ui.timer(15.0, refresh)
