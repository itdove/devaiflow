"""Web-based Dashboard for DevAIFlow (NiceGUI)."""

try:
    from devflow.web.app import DashboardApp

    HAS_NICEGUI = True
except ImportError:
    HAS_NICEGUI = False
    DashboardApp = None  # type: ignore[assignment,misc]

__all__ = ["DashboardApp", "HAS_NICEGUI"]
