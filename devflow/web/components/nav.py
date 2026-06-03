"""Navigation component for the web dashboard."""

from nicegui import ui

import devflow


def create_header(title: str = "DevAIFlow Dashboard") -> None:
    """Create the page header with navigation links for all pages.

    Args:
        title: Page title to display.
    """
    with ui.header().classes("bg-blue-900 text-white items-center justify-between"):
        with ui.row().classes("items-center gap-4"):
            ui.link("DevAIFlow", "/").classes(
                "text-xl font-bold text-white no-underline hover:text-blue-200"
            )
            ui.separator().props("vertical").classes("bg-blue-700")
            ui.link("Dashboard", "/").classes(
                "text-white no-underline hover:text-blue-200"
            )
            ui.link("Config", "/config").classes(
                "text-white no-underline hover:text-blue-200"
            )
            ui.link("Issues", "/issues").classes(
                "text-white no-underline hover:text-blue-200"
            )
            ui.link("Time", "/time").classes(
                "text-white no-underline hover:text-blue-200"
            )
            ui.link("Workspaces", "/workspaces").classes(
                "text-white no-underline hover:text-blue-200"
            )
        with ui.row().classes("items-center gap-2"):
            ui.label(f"v{devflow.__version__}").classes("text-xs text-blue-300")
