"""Status badge component for session status display."""

from nicegui import ui

# Map session statuses to Tailwind CSS color classes
STATUS_COLORS = {
    "created": "bg-gray-500",
    "in_progress": "bg-blue-600",
    "paused": "bg-yellow-600",
    "complete": "bg-green-600",
    "unknown": "bg-gray-400",
}

SESSION_TYPE_COLORS = {
    "development": "bg-indigo-600",
    "ticket_creation": "bg-purple-600",
    "investigation": "bg-teal-600",
}


def status_badge(status: str) -> ui.badge:
    """Create a colored badge for a session status.

    Args:
        status: Session status string.

    Returns:
        NiceGUI badge element.
    """
    color_class = STATUS_COLORS.get(status, STATUS_COLORS["unknown"])
    label = status.replace("_", " ").title()
    return ui.badge(label).classes(f"{color_class} text-white px-2 py-1 rounded")


def session_type_badge(session_type: str) -> ui.badge:
    """Create a colored badge for a session type.

    Args:
        session_type: Session type string.

    Returns:
        NiceGUI badge element.
    """
    color_class = SESSION_TYPE_COLORS.get(
        session_type, SESSION_TYPE_COLORS["development"]
    )
    label = session_type.replace("_", " ").title()
    return ui.badge(label).classes(f"{color_class} text-white px-2 py-1 rounded")
