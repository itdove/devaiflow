"""Backend-aware issue status checks used by destructive lifecycle operations."""

from collections.abc import Mapping
from typing import Any

_KNOWN_CLOSED_STATUSES = {"closed", "done", "resolved", "complete", "completed"}


def issue_is_closed(ticket: Mapping[str, Any], backend: str) -> bool:
    """Return true only when a standardized ticket explicitly reports closure.

    JIRA workflows use custom status names, so its status category is preferred
    when available. Name-based fallbacks are intentionally limited to common
    terminal names; unknown or missing values fail closed.
    """
    status = ticket.get("status")
    if isinstance(status, Mapping):
        status = status.get("name")
    status_name = status.strip().casefold() if isinstance(status, str) else ""

    if backend in {"github", "gitlab"}:
        return status_name == "closed"

    if backend == "jira":
        category = ticket.get("status_category")
        if isinstance(category, Mapping):
            category = category.get("key")
        if isinstance(category, str) and category.strip():
            return category.strip().casefold() == "done"
        return status_name in _KNOWN_CLOSED_STATUSES

    if backend == "mock":
        return status_name in _KNOWN_CLOSED_STATUSES

    return False


def ticket_matches_closed_transition(
    ticket: Mapping[str, Any], backend: str, requested_status: str | None = None
) -> bool:
    """Confirm closure and, for JIRA, that the selected target is what was applied."""
    if not issue_is_closed(ticket, backend):
        return False
    if backend != "jira" or requested_status is None:
        return True

    actual_status = ticket.get("status")
    return (
        isinstance(actual_status, str)
        and actual_status.strip().casefold() == requested_status.strip().casefold()
    )
