"""Session detail page -- displays full session information."""

from typing import Any, Dict, List, Optional

from nicegui import ui

from devflow.web.components.nav import create_header
from devflow.web.components.status_badge import (
    session_type_badge,
    status_badge,
)
from devflow.web.utils.data_bridge import DataBridge


def _create_metadata_section(session: Dict[str, Any]) -> None:
    """Create the session metadata section.

    Args:
        session: Session dictionary from DataBridge.
    """
    with ui.card().classes("w-full"):
        ui.label("Session Metadata").classes("text-lg font-bold mb-2")

        with ui.grid(columns=2).classes("w-full gap-2"):
            _field("Name", session.get("name", ""))
            _field("Status", "")
            # Place badge after the label
            with ui.row().classes("items-center"):
                status_badge(session.get("status", "unknown"))

            _field("Type", "")
            with ui.row().classes("items-center"):
                session_type_badge(session.get("session_type", "development"))

            _field("Issue Key", session.get("issue_key", "") or "None")
            _field("Workspace", session.get("workspace", "") or "None")
            _field("Goal", session.get("goal", ""))
            _field("Created", session.get("created", ""))
            _field("Last Active", session.get("last_active", ""))
            _field("Total Time", session.get("time", ""))
            _field(
                "Time Tracking",
                session.get("time_tracking_state", "paused").title(),
            )

        # Tags
        tags = session.get("tags", [])
        if tags:
            with ui.row().classes("mt-2 gap-1"):
                ui.label("Tags:").classes("font-semibold")
                for tag in tags:
                    ui.badge(tag).classes(
                        "bg-gray-600 text-white px-2 py-1 rounded"
                    )


def _field(label: str, value: str) -> None:
    """Create a labeled field display.

    Args:
        label: Field label.
        value: Field value.
    """
    ui.label(label).classes("font-semibold text-gray-400")
    ui.label(value).classes("text-white")


def _create_conversations_section(conversations: List[Dict[str, Any]]) -> None:
    """Create the conversations section.

    Args:
        conversations: List of conversation dictionaries.
    """
    with ui.card().classes("w-full"):
        ui.label("Conversations").classes("text-lg font-bold mb-2")

        if not conversations:
            ui.label("No conversations yet.").classes("text-gray-400")
            return

        for conv in conversations:
            with ui.card().classes("w-full bg-gray-800 mb-2"):
                with ui.grid(columns=2).classes("w-full gap-1"):
                    _field("Working Directory", conv.get("working_dir", ""))
                    _field("Project Path", conv.get("project_path", ""))
                    _field("Branch", conv.get("branch", ""))
                    _field("Session ID", conv.get("session_id", "")[:12] + "..." if len(conv.get("session_id", "")) > 12 else conv.get("session_id", ""))
                    _field("Messages", str(conv.get("message_count", 0)))

                # PRs
                prs = conv.get("prs", [])
                if prs:
                    with ui.row().classes("mt-1 gap-1"):
                        ui.label("PRs:").classes("font-semibold text-gray-400")
                        for pr in prs:
                            ui.link(pr, pr).classes("text-blue-400")


def _create_work_sessions_section(work_sessions: List[Dict[str, Any]]) -> None:
    """Create the work sessions / time tracking section.

    Args:
        work_sessions: List of work session dictionaries.
    """
    with ui.card().classes("w-full"):
        ui.label("Work Sessions").classes("text-lg font-bold mb-2")

        if not work_sessions:
            ui.label("No work sessions recorded.").classes("text-gray-400")
            return

        columns = [
            {"name": "start", "label": "Start", "field": "start", "align": "left"},
            {"name": "end", "label": "End", "field": "end", "align": "left"},
            {"name": "duration", "label": "Duration", "field": "duration", "align": "left"},
            {"name": "user", "label": "User", "field": "user", "align": "left"},
        ]

        ui.table(
            columns=columns,
            rows=work_sessions,
            row_key="start",
        ).classes("w-full").props("dense")


def _create_notes_section(
    bridge: DataBridge, session_name: str
) -> None:
    """Create the notes section with view and add functionality.

    Args:
        bridge: DataBridge instance.
        session_name: Session name for loading notes.
    """
    with ui.card().classes("w-full"):
        ui.label("Session Notes").classes("text-lg font-bold mb-2")

        # Notes display area
        notes_content = bridge.get_session_notes(session_name)
        notes_display = ui.markdown(notes_content or "*No notes yet.*").classes(
            "w-full bg-gray-800 p-3 rounded min-h-[100px]"
        )

        # Add note form
        ui.separator().classes("my-2")
        ui.label("Add Note").classes("font-semibold")

        with ui.row().classes("w-full items-end gap-2"):
            note_input = ui.input(
                placeholder="Enter a note...",
            ).classes("flex-grow")

            def add_note() -> None:
                """Add a note and refresh the display."""
                text = note_input.value
                if not text or not text.strip():
                    ui.notify("Please enter a note.", type="warning")
                    return

                success = bridge.add_session_note(session_name, text.strip())
                if success:
                    ui.notify("Note added.", type="positive")
                    note_input.value = ""
                    # Refresh notes display
                    new_notes = bridge.get_session_notes(session_name)
                    notes_display.set_content(new_notes or "*No notes yet.*")
                else:
                    ui.notify("Failed to add note.", type="negative")

            ui.button("Add", on_click=add_note).classes("bg-blue-600")


def create_session_detail_page(bridge: DataBridge, name: str) -> None:
    """Create the session detail page.

    Displays complete session information including metadata, conversations,
    work sessions, and notes. Supports adding new notes.

    Args:
        bridge: DataBridge instance for data access.
        name: Session name to display.
    """
    create_header()

    with ui.column().classes("w-full max-w-5xl mx-auto p-4 gap-4"):
        # Back navigation
        ui.link("<< Back to Dashboard", "/").classes(
            "text-blue-400 hover:text-blue-300 mb-2"
        )

        # Load session data
        session = bridge.get_session(name)

        if session is None:
            ui.label(f"Session '{name}' not found.").classes(
                "text-red-400 text-xl text-center py-8"
            )
            return

        # Page title
        ui.label(session.get("name", name)).classes("text-2xl font-bold")

        # Metadata
        _create_metadata_section(session)

        # Conversations
        _create_conversations_section(session.get("conversations", []))

        # Work Sessions
        _create_work_sessions_section(session.get("work_sessions", []))

        # Notes
        _create_notes_section(bridge, name)
