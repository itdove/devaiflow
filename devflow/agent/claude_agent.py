"""Claude Code agent implementation.

This module implements the AgentInterface for Claude Code, encapsulating all
Claude-specific logic that was previously in SessionCapture.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Set, Dict, List, Any

from devflow.agent.interface import AgentInterface
from devflow.utils.dependencies import require_tool
from devflow.utils.paths import get_claude_config_dir


class ClaudeAgent(AgentInterface):
    """Claude Code agent implementation.

    Encapsulates all Claude Code-specific operations including:
    - Session launching and resuming
    - Session ID capture
    - Session file management
    - Project path encoding
    """

    def __init__(self, claude_dir: Optional[Path] = None):
        """Initialize Claude agent.

        Args:
            claude_dir: Claude Code directory. Defaults to ~/.claude or $CLAUDE_CONFIG_DIR
        """
        if claude_dir is None:
            claude_dir = get_claude_config_dir()
        self.claude_dir = claude_dir
        self.projects_dir = claude_dir / "projects"

    def launch_session(
        self,
        project_path: str,
        model_provider_profile: Optional[Dict[str, any]] = None,
        session_name: Optional[str] = None,
        profile_name: Optional[str] = None,
        enforcement_source: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen:
        """Launch a new Claude Code session in a project directory.

        Args:
            project_path: Absolute path to project
            model_provider_profile: Model provider profile dict (optional)
                Contains: base_url, auth_token, api_key, model_name, use_vertex,
                         vertex_project_id, vertex_region, env_vars
            session_name: Session name for audit logging (optional)
            profile_name: Profile name for audit logging (optional)
            enforcement_source: Enforcement source for audit logging (optional)
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the launched Claude Code process

        Raises:
            ToolNotFoundError: If claude command is not installed
        """
        require_tool("claude", "launch Claude Code session")

        # Audit log: Track model provider usage when launching session
        if session_name:
            from devflow.utils.audit_log import log_model_provider_usage
            log_model_provider_usage(
                event_type="session_launched",
                session_name=session_name,
                profile_name=profile_name,
                enforcement_source=enforcement_source,
                model_name=model_provider_profile.get("model_name") if model_provider_profile else None,
                base_url=model_provider_profile.get("base_url") if model_provider_profile else None,
                use_vertex=model_provider_profile.get("use_vertex", False) if model_provider_profile else False,
                vertex_region=model_provider_profile.get("vertex_region") if model_provider_profile else None,
                cost_per_million_input_tokens=model_provider_profile.get("cost_per_million_input_tokens") if model_provider_profile else None,
                cost_per_million_output_tokens=model_provider_profile.get("cost_per_million_output_tokens") if model_provider_profile else None,
                cost_center=model_provider_profile.get("cost_center") if model_provider_profile else None,
            )

        # Build environment and command based on profile
        final_env, cmd = self._build_env_and_cmd(model_provider_profile, base_env=env)

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=final_env,
            # Do NOT redirect stdout/stderr - Claude Code needs terminal interaction
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
        session_name: Optional[str] = None,
        profile_name: Optional[str] = None,
        enforcement_source: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen:
        """Launch Claude Code with initial prompt (for new sessions).

        Args:
            project_path: Absolute path to project
            initial_prompt: Initial prompt to send to Claude
            session_id: Session UUID to use
            model_provider_profile: Model provider profile dict (optional)
            skills_dirs: List of skill directories to add (optional, will be auto-discovered if None)
            workspace_path: Workspace path for auto-discovering workspace skills (optional)
            config: Configuration object for context files discovery (optional)
            session_name: Session name for audit logging (optional)
            profile_name: Profile name for audit logging (optional)
            enforcement_source: Enforcement source for audit logging (optional)
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the launched Claude Code process

        Raises:
            ToolNotFoundError: If claude command is not installed
        """
        require_tool("claude", "launch Claude Code session")

        # Audit log: Track model provider usage when launching session
        if session_name:
            from devflow.utils.audit_log import log_model_provider_usage
            log_model_provider_usage(
                event_type="session_launched",
                session_name=session_name,
                profile_name=profile_name,
                enforcement_source=enforcement_source,
                model_name=model_provider_profile.get("model_name") if model_provider_profile else None,
                base_url=model_provider_profile.get("base_url") if model_provider_profile else None,
                use_vertex=model_provider_profile.get("use_vertex", False) if model_provider_profile else False,
                vertex_region=model_provider_profile.get("vertex_region") if model_provider_profile else None,
                cost_per_million_input_tokens=model_provider_profile.get("cost_per_million_input_tokens") if model_provider_profile else None,
                cost_per_million_output_tokens=model_provider_profile.get("cost_per_million_output_tokens") if model_provider_profile else None,
                cost_center=model_provider_profile.get("cost_center") if model_provider_profile else None,
            )

        # Build environment and base command from profile
        final_env, base_cmd = self._build_env_and_cmd(model_provider_profile, base_env=env)

        # Build full command with session ID and prompt
        # Format: claude [--model model] --session-id <uuid> "<prompt>" --add-dir ...
        if model_provider_profile and model_provider_profile.get("model_name"):
            cmd = ["claude", "--model", model_provider_profile["model_name"], "--session-id", session_id, initial_prompt]
        else:
            cmd = ["claude", "--session-id", session_id, initial_prompt]

        # Discover and add skills directories if not provided
        if skills_dirs is None:
            skills_dirs = self._discover_skills_dirs(project_path, workspace_path, config)

        # Filter out skills that will be auto-loaded by Claude from cwd
        # Claude Code auto-loads <cwd>/.claude/skills/ where cwd=project_path
        # We don't want to add this via --add-dir as it would duplicate the loading
        cwd_skills = Path(project_path).resolve() / ".claude" / "skills"
        filtered_skills = [s for s in skills_dirs if Path(s).resolve() != cwd_skills]

        # Add filtered skills directories
        for skills_dir in filtered_skills:
            cmd.extend(["--add-dir", skills_dir])

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=final_env,
            # Do NOT redirect stdout/stderr - Claude Code needs terminal interaction
        )

    def resume_session(
        self,
        session_id: str,
        project_path: str,
        model_provider_profile: Optional[Dict[str, any]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> subprocess.Popen:
        """Resume an existing Claude Code session.

        Args:
            session_id: Session UUID to resume
            project_path: Absolute path to project
            model_provider_profile: Model provider profile dict (optional)
            env: Environment variables dict (optional, defaults to os.environ)

        Returns:
            Subprocess handle for the resumed Claude Code process

        Raises:
            ToolNotFoundError: If claude command is not installed
        """
        require_tool("claude", "resume Claude Code session")

        # Build environment (command is always claude --resume for resume)
        final_env, _ = self._build_env_and_cmd(model_provider_profile, base_env=env)
        cmd = ["claude", "--resume", session_id]

        return subprocess.Popen(
            cmd,
            cwd=project_path,
            env=final_env,
            # Do NOT redirect stdout/stderr - Claude Code needs terminal interaction
        )

    def capture_session_id(
        self,
        project_path: str,
        timeout: int = 10,
        poll_interval: float = 0.5,
    ) -> Optional[str]:
        """Capture a new Claude Code session ID by monitoring file creation.

        Args:
            project_path: Absolute path to project
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Session UUID if detected, None if timeout

        Raises:
            TimeoutError: If session not detected within timeout
        """
        # Get existing sessions before launch
        before = self.get_existing_sessions(project_path)

        # Launch Claude Code
        process = self.launch_session(project_path)

        # Poll for new session file
        elapsed = 0.0
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval

            after = self.get_existing_sessions(project_path)
            new_sessions = after - before

            if new_sessions:
                # Return the first new session found
                session_id = new_sessions.pop()
                return session_id

        # Timeout - session not detected
        session_dir = self._get_session_dir(project_path)
        encoded_path = self.encode_project_path(project_path)
        raise TimeoutError(
            f"Failed to detect new Claude Code session after {timeout}s.\n"
            f"Expected location: {session_dir}\n"
            f"Encoded path: {encoded_path}\n"
            f"You may need to enter the session ID manually.\n"
            f"Tip: Run 'claude --resume' to see available sessions."
        )

    def get_session_file_path(self, session_id: str, project_path: str) -> Path:
        """Get the path to a Claude Code session file.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Path to the .jsonl session file
        """
        session_dir = self._get_session_dir(project_path)
        return session_dir / f"{session_id}.jsonl"

    def session_exists(self, session_id: str, project_path: str) -> bool:
        """Check if a Claude Code session file exists.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            True if session file exists
        """
        session_file = self.get_session_file_path(session_id, project_path)
        return session_file.exists()

    def get_existing_sessions(self, project_path: str) -> Set[str]:
        """Get set of existing Claude Code session IDs for a project.

        Args:
            project_path: Absolute path to project

        Returns:
            Set of session UUIDs
        """
        session_dir = self._get_session_dir(project_path)
        if not session_dir.exists():
            return set()

        return {f.stem for f in session_dir.glob("*.jsonl")}

    def get_session_message_count(self, session_id: str, project_path: str) -> int:
        """Get the number of messages in a Claude Code session.

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Number of lines in the .jsonl file (approximate message count)
        """
        session_file = self.get_session_file_path(session_id, project_path)

        if not session_file.exists():
            return 0

        with open(session_file, "r") as f:
            return sum(1 for _ in f)

    def encode_project_path(self, project_path: str) -> str:
        """Encode project path the same way Claude Code does.

        Claude Code replaces / with - in paths (keeps the leading -)
        and also replaces _ with -.

        Resolves known symlinks (e.g., /var -> /private/var on macOS) to match
        how Claude Code encodes paths when it launches.

        Args:
            project_path: Absolute path to project

        Returns:
            Encoded path string
        """
        # Resolve known symlinks to match Claude Code's behavior
        # On macOS, /var is a symlink to private/var
        # We need to handle this even for non-existent paths (temp directories)
        resolved_path = project_path

        # Handle /var -> /private/var symlink on macOS
        if project_path.startswith("/var/"):
            # Check if /var is actually a symlink
            var_path = Path("/var")
            if var_path.is_symlink():
                # Replace /var/ with the resolved target
                target = var_path.resolve()
                resolved_path = str(target / project_path[5:])  # Skip "/var/"

        # Handle /tmp -> /private/tmp symlink on macOS
        elif project_path.startswith("/tmp/"):
            tmp_path = Path("/tmp")
            if tmp_path.is_symlink():
                target = tmp_path.resolve()
                resolved_path = str(target / project_path[5:])  # Skip "/tmp/"

        # Claude Code replaces / with - in paths (keeps the leading -)
        # AND also replaces _ with -
        encoded = resolved_path.replace("/", "-").replace("_", "-")
        return encoded

    def get_agent_home_dir(self) -> Path:
        """Get the Claude Code home directory where it stores sessions.

        Returns:
            Path to ~/.claude directory
        """
        return self.claude_dir

    def get_agent_name(self) -> str:
        """Get the name of the agent backend.

        Returns:
            "claude"
        """
        return "claude"

    def _get_session_dir(self, project_path: str) -> Path:
        """Get the session directory for a project.

        Args:
            project_path: Absolute path to project

        Returns:
            Path to sessions directory
        """
        encoded = self.encode_project_path(project_path)
        return self.projects_dir / encoded

    def _build_env_and_cmd(
        self,
        model_provider_profile: Optional[Dict[str, any]] = None,
        base_env: Optional[Dict[str, str]] = None
    ) -> tuple[Dict[str, str], list[str]]:
        """Build environment variables and command from model provider profile.

        Args:
            model_provider_profile: Model provider profile dict (optional)
            base_env: Base environment dict to start from (optional, defaults to os.environ)

        Returns:
            Tuple of (environment dict, command list)
        """
        # Start with copy of base environment (or current environment if not provided)
        if base_env is not None:
            env = base_env.copy()
        else:
            env = os.environ.copy()

        # Default command
        cmd = ["claude", "code"]

        # If no profile specified, return defaults
        if not model_provider_profile:
            return env, cmd

        # Apply profile settings
        if model_provider_profile.get("base_url"):
            env["ANTHROPIC_BASE_URL"] = model_provider_profile["base_url"]

        if model_provider_profile.get("auth_token"):
            env["ANTHROPIC_AUTH_TOKEN"] = model_provider_profile["auth_token"]

        if "api_key" in model_provider_profile and model_provider_profile["api_key"] is not None:
            env["ANTHROPIC_API_KEY"] = model_provider_profile["api_key"]

        if model_provider_profile.get("use_vertex"):
            env["CLAUDE_CODE_USE_VERTEX"] = "1"

            # Set Vertex-specific env vars if provided
            if model_provider_profile.get("vertex_project_id"):
                env["ANTHROPIC_VERTEX_PROJECT_ID"] = model_provider_profile["vertex_project_id"]

            if model_provider_profile.get("vertex_region"):
                env["ANTHROPIC_VERTEX_REGION"] = model_provider_profile["vertex_region"]
        else:
            # Explicitly unset Vertex flag if not using Vertex
            env.pop("CLAUDE_CODE_USE_VERTEX", None)

        # Apply additional environment variables
        if model_provider_profile.get("env_vars"):
            env.update(model_provider_profile["env_vars"])

        # Build command with model name if specified
        if model_provider_profile.get("model_name"):
            cmd = ["claude", "--model", model_provider_profile["model_name"]]

        return env, cmd

    def _discover_skills_dirs(
        self,
        project_path: str,
        workspace_path: Optional[str] = None,
        config = None,
    ) -> List[str]:
        """Discover skills directories in priority order.

        Skills discovery order (load order):
        1. User-level: ~/.claude/skills/ (generic skills)
        2. Workspace-level: <workspace>/.claude/skills/ (workspace-specific tools)
        3. Hierarchical: $DEVAIFLOW_HOME/.claude/skills/ (org-specific extensions)
        4. Project-level: <project>/.claude/skills/ (project-specific skills)

        Precedence rules (when same skill exists at multiple levels):
        - Later-loaded skills can override/extend earlier ones
        - Project > Hierarchical > Workspace > User
        - Organization-specific skills (hierarchical) extend generic skills
        - This is why generic skills are loaded first

        Duplicate prevention:
        - When cwd == project_path (single-project sessions), Claude Code
          auto-loads <project>/.claude/skills/ from the current directory
        - In this case, launch_with_prompt() filters out project-level skills
          to prevent duplicate loading via --add-dir
        - Multi-project sessions work correctly since cwd != project_path

        Args:
            project_path: Absolute path to project
            workspace_path: Workspace path (optional)
            config: Configuration object (optional)

        Returns:
            List of skill directory paths that exist (may include duplicates
            that will be filtered by caller based on cwd)
        """
        skills_dirs = []

        # 1. User-level skills: ~/.claude/skills/ (or $CLAUDE_CONFIG_DIR/skills/)
        claude_config = get_claude_config_dir()
        user_skills = claude_config / "skills"
        if user_skills.exists():
            skills_dirs.append(str(user_skills))

        # 2. Workspace-level skills: <workspace>/.claude/skills/
        if workspace_path:
            from devflow.utils.claude_commands import get_workspace_skills_dir
            workspace_skills = get_workspace_skills_dir(workspace_path)
            if workspace_skills.exists():
                skills_dirs.append(str(workspace_skills))

        # 3. Hierarchical skills: $DEVAIFLOW_HOME/.claude/skills/
        from devflow.utils.paths import get_cs_home
        cs_home = get_cs_home()
        hierarchical_skills = cs_home / ".claude" / "skills"
        if hierarchical_skills.exists():
            skills_dirs.append(str(hierarchical_skills))

        # 4. Project-level skills: <project>/.claude/skills/
        if project_path:
            project_skills = Path(project_path) / ".claude" / "skills"
            if project_skills.exists():
                skills_dirs.append(str(project_skills))

        # DEPRECATED: Auto-loading hierarchical context files is deprecated.
        # Context files (ENTERPRISE.md, ORGANIZATION.md, TEAM.md, USER.md) are no longer
        # automatically loaded into Claude sessions. Instead, use skills which are auto-loaded
        # from ~/.claude/skills/01-enterprise/, 02-organization/, etc.
        #
        # This provides better organization and avoids duplicating the same content in both
        # context files and skills. Skills are the single source of truth.
        #
        # The old behavior below is kept but commented out for backward compatibility reference:
        # if config:
        #     from devflow.utils.context_files import load_hierarchical_context_files
        #     hierarchical_files = load_hierarchical_context_files(config)
        #     if hierarchical_files and cs_home.exists():
        #         if str(cs_home) not in skills_dirs:
        #             skills_dirs.append(str(cs_home))

        return skills_dirs

    def extract_token_usage(self, session_id: str, project_path: str) -> Optional[Dict[str, Any]]:
        """Extract token usage statistics from Claude Code conversation file.

        Parses the .jsonl conversation file to extract token usage data from
        assistant messages. Each assistant message may contain a usage object with:
        - input_tokens: Input tokens consumed
        - output_tokens: Output tokens generated
        - cache_creation_input_tokens: Tokens written to prompt cache
        - cache_read_input_tokens: Tokens read from cache (90% cost savings)

        Args:
            session_id: Session UUID
            project_path: Absolute path to project

        Returns:
            Dictionary with aggregated token statistics, or None if:
            - Session file doesn't exist
            - Session file has no token usage data
            - Error parsing session file

            Returned dict contains:
            - input_tokens: Total input tokens
            - output_tokens: Total output tokens
            - cache_creation_input_tokens: Total cache creation tokens
            - cache_read_input_tokens: Total cache read tokens
            - message_count: Number of messages with usage data
            - total_tokens: Sum of input + output tokens
        """
        session_file = self.get_session_file_path(session_id, project_path)

        if not session_file.exists():
            return None

        # Aggregate token usage across all assistant messages
        total_input_tokens = 0
        total_output_tokens = 0
        total_cache_creation_tokens = 0
        total_cache_read_tokens = 0
        message_count = 0

        try:
            with open(session_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        msg = json.loads(line)

                        # Look for assistant messages with usage data
                        # Claude Code format: {"type": "assistant", "message": {"usage": {...}}}
                        if isinstance(msg, dict) and msg.get("type") == "assistant":
                            inner_msg = msg.get("message", {})
                            usage = inner_msg.get("usage")

                            if usage and isinstance(usage, dict):
                                # Extract token counts (default to 0 if missing)
                                total_input_tokens += usage.get("input_tokens", 0)
                                total_output_tokens += usage.get("output_tokens", 0)
                                total_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
                                total_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                                message_count += 1

                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue

        except (IOError, OSError):
            # File read error
            return None

        # Return None if no usage data found
        if message_count == 0:
            return None

        return {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cache_creation_input_tokens": total_cache_creation_tokens,
            "cache_read_input_tokens": total_cache_read_tokens,
            "message_count": message_count,
            "total_tokens": total_input_tokens + total_output_tokens,
        }
