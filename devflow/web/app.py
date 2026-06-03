"""NiceGUI-based web dashboard for DevAIFlow.

Provides a browser-accessible dashboard for viewing and managing
DevAIFlow sessions, configuration, and issue tracker data.
"""

import atexit
import logging
import os
import signal
import socket
import sys
import webbrowser
from pathlib import Path
from typing import Optional

from devflow.utils.paths import get_cs_home
from devflow.web.utils.data_bridge import DataBridge

logger = logging.getLogger(__name__)


# -- State files --------------------------------------------------------------

def _get_state_dir() -> Path:
    """Get the dashboard state directory, creating it if needed."""
    state_dir = get_cs_home() / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _get_port_file() -> Path:
    """Get the path to the dashboard port file.

    Returns:
        Path to the port file in the DevAIFlow state directory.
    """
    return _get_state_dir() / "dashboard.port"


def _get_pid_file() -> Path:
    """Get the path to the dashboard PID file.

    Returns:
        Path to the PID file in the DevAIFlow state directory.
    """
    return _get_state_dir() / "dashboard.pid"


def _write_port(port: int) -> None:
    """Write the assigned port to a state file for discovery.

    Args:
        port: The port number the dashboard is listening on.
    """
    port_file = _get_port_file()
    port_file.parent.mkdir(parents=True, exist_ok=True)
    port_file.write_text(str(port))


def _write_pid(pid: int) -> None:
    """Write the dashboard process PID to a state file.

    Args:
        pid: Process ID of the running dashboard.
    """
    pid_file = _get_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid))


def _cleanup_state_files() -> None:
    """Remove port and PID files on exit."""
    _get_port_file().unlink(missing_ok=True)
    _get_pid_file().unlink(missing_ok=True)


# Keep old name for backward compat with tests
_cleanup_port_file = _cleanup_state_files


def _read_pid() -> Optional[int]:
    """Read the dashboard PID from the state file.

    Returns:
        PID as int, or None if file missing / invalid.
    """
    pid_file = _get_pid_file()
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def _read_port() -> Optional[int]:
    """Read the dashboard port from the state file.

    Returns:
        Port as int, or None if file missing / invalid.
    """
    port_file = _get_port_file()
    if not port_file.exists():
        return None
    try:
        return int(port_file.read_text().strip())
    except (ValueError, OSError):
        return None


def _is_process_running(pid: int) -> bool:
    """Check whether a process with the given PID is alive.

    Args:
        pid: Process ID to check.

    Returns:
        True if the process exists and is running.
    """
    try:
        os.kill(pid, 0)  # signal 0 = existence check
        return True
    except (OSError, ProcessLookupError):
        return False


def stop_dashboard() -> bool:
    """Stop a running background dashboard.

    Reads the PID file, sends SIGTERM (or SIGBREAK on Windows),
    and cleans up state files.

    Returns:
        True if a process was stopped, False if nothing was running.
    """
    pid = _read_pid()
    if pid is None:
        return False

    if not _is_process_running(pid):
        # Stale PID file
        _cleanup_state_files()
        return False

    try:
        if sys.platform == "win32":
            os.kill(pid, signal.SIGBREAK)  # type: ignore[attr-defined]
        else:
            os.kill(pid, signal.SIGTERM)
        _cleanup_state_files()
        return True
    except (OSError, ProcessLookupError):
        _cleanup_state_files()
        return False


def get_dashboard_status() -> Optional[dict]:
    """Return info about a running dashboard, or None.

    Returns:
        Dict with pid and port keys, or None.
    """
    pid = _read_pid()
    port = _read_port()
    if pid is None or not _is_process_running(pid):
        return None
    return {"pid": pid, "port": port}


class DashboardApp:
    """NiceGUI-based web dashboard application.

    Wraps the NiceGUI app setup, route registration, and lifecycle
    management for the DevAIFlow dashboard.
    """

    def __init__(self) -> None:
        """Initialize the dashboard application."""
        self.bridge = DataBridge()

    def _register_pages(self) -> None:
        """Register all page routes with NiceGUI."""
        from nicegui import ui

        @ui.page("/")
        def dashboard_page() -> None:
            from devflow.web.pages.dashboard import create_dashboard_page

            create_dashboard_page(self.bridge)

        @ui.page("/session/{name}")
        def session_detail_page(name: str) -> None:
            from devflow.web.pages.session_detail import create_session_detail_page

            create_session_detail_page(self.bridge, name)

        @ui.page("/config")
        def config_editor_page() -> None:
            from devflow.web.pages.config_editor import create_config_editor_page

            create_config_editor_page(self.bridge, advanced=False)

        @ui.page("/config/advanced")
        def config_editor_advanced_page() -> None:
            from devflow.web.pages.config_editor import create_config_editor_page

            create_config_editor_page(self.bridge, advanced=True)

        @ui.page("/issues")
        def issue_tracker_page() -> None:
            from devflow.web.pages.issue_tracker import create_issue_tracker_page

            create_issue_tracker_page(self.bridge)

        @ui.page("/time")
        def time_tracking_page() -> None:
            from devflow.web.pages.time_tracking import create_time_tracking_page

            create_time_tracking_page(self.bridge)

        @ui.page("/workspaces")
        def workspaces_page() -> None:
            from devflow.web.pages.workspaces import create_workspaces_page

            create_workspaces_page(self.bridge)

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        show: bool = True,
        reload: bool = False,
    ) -> None:
        """Start the dashboard web server.

        Args:
            host: Host to bind to. Defaults to 127.0.0.1 (localhost only).
            port: Port to bind to. 0 = OS-assigned random available port.
            show: Whether to auto-open the browser.
            reload: Whether to enable auto-reload for development.
        """
        from nicegui import app, ui

        # Security warning for non-localhost binding
        if host != "127.0.0.1":
            logger.warning(
                "Dashboard binding to %s -- exposed on network. "
                "Only bind to non-localhost addresses if you understand the security implications.",
                host,
            )

        # Dynamic port allocation
        if port == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((host, 0))
            port = sock.getsockname()[1]
            sock.close()

        # Write state files for discovery
        _write_port(port)
        _write_pid(os.getpid())
        atexit.register(_cleanup_state_files)

        # Register all pages
        self._register_pages()

        # Auto-open browser after server starts
        if show:
            url = f"http://{host}:{port}"
            app.on_startup(lambda: webbrowser.open(url))
            show = False  # Disable NiceGUI's built-in show

        ui.run(
            host=host,
            port=port,
            title="DevAIFlow Dashboard",
            dark=True,
            reload=reload,
            show=show,
            favicon="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#x1F4CA;</text></svg>",
        )
