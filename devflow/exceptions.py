"""Custom exceptions for daf tool."""


class ToolNotFoundError(Exception):
    """Raised when a required external tool is not found.

    Attributes:
        tool: Name of the missing tool (e.g., "git", "claude", "gh", "glab")
        operation: Operation that requires the tool (e.g., "create branch", "launch session")
        install_url: URL where the tool can be downloaded/installed
    """

    def __init__(self, tool: str, operation: str, install_url: str = None):
        """Initialize tool not found error.

        Args:
            tool: Name of the missing tool
            operation: Operation that requires the tool
            install_url: URL where the tool can be downloaded
        """
        self.tool = tool
        self.operation = operation
        self.install_url = install_url or ""

        message = f"{tool} command not found"
        if operation:
            message += f"\nRequired for: {operation}"
        if install_url:
            message += f"\nInstall from: {install_url}"

        super().__init__(message)
