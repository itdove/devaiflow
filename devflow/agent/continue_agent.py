"""Continue agent implementation.

This module implements the AgentInterface for Continue, an open-source AI code
assistant that integrates with VS Code and JetBrains IDEs.

⚠️  EXPERIMENTAL - NOT FULLY TESTED
This agent implementation has not been fully tested. It may have limitations or bugs.
Only Claude Code has been comprehensively tested. Use at your own risk.

Continue is primarily a VS Code/JetBrains extension that provides AI-powered code
assistance. It also has a CLI component for CI/CD integration. This implementation
focuses on the VS Code integration.
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, Set, List, Dict, Any

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool


class ContinueAgent(AgentInterface):
    """Continue agent implementation.

    Provides integration with Continue AI coding assistant, which runs as a
    VS Code or JetBrains extension with additional CLI capabilities.

    Continue uses a message-passing architecture with core, extension, and GUI
    components. Sessions are managed by the IDE workspace storage.

    Features:
    - Launch VS Code with Continue extension
    - Workspace-based session management
    - Integration with Continue's agent and chat modes
    - Support for multiple AI models

    Limitations:
    - Session ID detection is workspace-based (not discrete session files)
    - Requires VS Code to be installed and Continue extension enabled
    - Message counting not available (internal to extension storage)
    - Session state managed by VS Code, not directly accessible
    - No direct CLI for session management (uses VS Code CLI)
    - Initial prompts must be sent manually through VS Code UI

    Note:
        Continue doesn't provide discrete session files or IDs. Sessions are
        tied to VS Code workspaces. This implementation uses workspace-based
        identifiers for compatibility with DevAIFlow.
    """

    def __init__(self, continue_dir: Optional[Path] = None):
        """Initialize Continue agent.

        Args:
            continue_dir: Continue data directory. Defaults to ~/.continue
                         (VS Code extension data is in ~/.vscode)
        """
        if continue_dir is None:
            continue_dir = Path.home() / ".continue"
        self.continue_dir = continue_dir

        # VS Code stores Continue extension data in workspace storage
        self.vscode_dir = Path.home() / ".vscode"
        self.workspace_storage = self.vscode_dir / "User" / "workspaceStorage"

    def launch_session(self, project_path: str) -> subprocess.Popen:
        """Launch VS Code with Continue extension in a project directory.

        Args:
            project_path: Absolute path to project

        Returns:
            Subprocess handle for VS Code process

        Raises:
            ToolNotFoundError: If code command is not installed
        """
        require_tool("code", "launch VS Code with Continue extension")

        # Launch VS Code in the project directory
        # Continue extension will automatically activate
        return subprocess.Popen(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def launch_with_prompt(
        self,
        project_path: str,
        initial_prompt: str,
        session_id: str,
        model_provider_profile: Optional[Dict[str, Any]] = None,
        skills_dirs: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
        config = None,
    ) -> subprocess.Popen:
        """Launch VS Code with Continue extension.

        Note: Continue doesn't support sending initial prompts via CLI.
        The initial_prompt is saved to a file for user reference, but must
        be manually pasted into the Continue chat interface after VS Code opens.

        Args:
            project_path: Absolute path to project
            initial_prompt: Initial prompt (saved to file for reference)
            session_id: Session UUID (used for prompt filename)
            model_provider_profile: Model provider profile (ignored)
            skills_dirs: Skills directories (ignored)
            workspace_path: Workspace path (ignored)
            config: Configuration object (ignored)

        Returns:
            Subprocess handle for VS Code process

        Raises:
            ToolNotFoundError: If code command is not installed
        """
        require_tool("code", "launch VS Code with Continue extension")

        # Save initial prompt to a file for user reference
        self.continue_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = self.continue_dir / f"{session_id}_initial_prompt.txt"
        prompt_file.write_text(initial_prompt)

        # Launch VS Code - user will need to manually open Continue and paste prompt
        return subprocess.Popen(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def resume_session(self, session_id: str, project_path: str) -> subprocess.Popen:
        """Resume VS Code with Continue extension.

        VS Code and Continue automatically restore the previous workspace state
        including chat history.

        Args:
            session_id: Session identifier (used for tracking)
            project_path: Absolute path to project

        Returns:
            Subprocess handle for VS Code process

        Raises:
            ToolNotFoundError: If code command is not installed
        """
        require_tool("code", "resume VS Code with Continue extension")

        # VS Code automatically restores workspace state and Continue chat history
        return subprocess.Popen(
            ["code", project_path],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """Capture a session ID for Continue.

        Since Continue doesn't provide discrete session IDs, this generates a
        workspace-based identifier.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds (unused)
            poll_interval: Time between polls in seconds (unused)

        Returns:
            Generated session identifier
        """
        # Generate workspace-based session ID
        # Format: continue-{encoded_path}-{timestamp}
        encoded_path = self.encode_project_path(project_path)
        timestamp = int(time.time())
        session_id = f"continue-{encoded_path}-{timestamp}"

        return session_id

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to Continue's workspace state.

        Continue stores session data in VS Code's workspace storage, which is
        managed internally by the extension.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            Path to workspace storage directory (may not exist)
        """
        # VS Code creates unique IDs for workspaces
        # We can't directly map project_path to workspace storage directory
        # Return expected location even if it doesn't exist
        encoded = self.encode_project_path(project_path)
        return self.workspace_storage / encoded

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a Continue workspace session exists.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            True if workspace storage exists or if VS Code is likely installed
        """
        # Check if workspace storage directory exists
        session_path = self.get_session_file_path(session_id, project_path)

        # Also check if any workspace storage exists (indicates VS Code is set up)
        return session_path.exists() or (
            self.workspace_storage.exists() and
            any(self.workspace_storage.iterdir())
        )

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing session IDs for a project.

        Note: Continue manages sessions via VS Code workspace storage.
        This returns an empty set as discrete session tracking is not available.

        Args:
            project_path: Absolute path to project

        Returns:
            Empty set (Continue manages sessions via workspace storage)
        """
        # Continue doesn't maintain discrete session files
        # Sessions are managed by VS Code workspace storage
        return set()

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get message count from Continue chat history.

        Note: Continue stores chat history in the VS Code extension's internal
        storage, which is not directly accessible. Returns 0 as message counting
        is not supported.

        Args:
            session_id: Session identifier
            project_path: Absolute path to project

        Returns:
            0 (message counting not supported)
        """
        # Continue's chat history is stored in VS Code extension storage
        # The format is internal to the extension and not publicly documented
        return 0

    def encode_project_path(self, project_path: str) -> str:
        """Encode project path for storage identifiers.

        Uses the same encoding as Claude Code for consistency.

        Args:
            project_path: Absolute path to project

        Returns:
            Encoded path string
        """
        # Same encoding as Claude Code: replace / and _ with -
        encoded = project_path.replace("/", "-").replace("_", "-")
        return encoded

    def get_agent_home_dir(self) -> Path:
        """Get Continue's home directory.

        Returns:
            Path to ~/.continue directory
        """
        return self.continue_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "continue"
        """
        return "continue"
