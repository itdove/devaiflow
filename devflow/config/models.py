"""Configuration models for DevAIFlow."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class JiraTransitionConfig(BaseModel):
    """Configuration for issue tracker ticket transitions."""

    from_status: List[str] = Field(alias="from", default=["New", "To Do"])
    to: str = ""  # Target status for automatic transitions (when prompt=False)
    prompt: bool = False
    on_fail: str = "warn"
    options: Optional[List[str]] = None  # Deprecated - transitions now fetched dynamically from JIRA API


class JiraFiltersConfig(BaseModel):
    """Configuration for issue tracker ticket filters."""

    status: List[str] = ["New", "To Do", "In Progress"]
    required_fields: List[str] = ["sprint", "story-points"]
    assignee: str = "currentUser()"


class JiraBackendConfig(BaseModel):
    """JIRA backend-specific configuration (backends/jira.json).

    Contains JIRA instance settings that are common across an organization
    using the same JIRA instance (URL, field mappings, transitions).
    """

    url: str
    transitions: Dict[str, JiraTransitionConfig] = Field(default_factory=dict)
    field_mappings: Optional[Dict[str, Dict[str, Any]]] = None  # Cached field mappings (creation fields only)
    field_cache_timestamp: Optional[str] = None  # ISO timestamp of last field discovery
    field_cache_auto_refresh: bool = True  # Auto-refresh field mappings when stale
    field_cache_max_age_hours: int = 24  # Maximum age in hours before cache is stale (default: 24h)
    parent_field_mapping: Optional[Dict[str, str]] = Field(
        default_factory=lambda: {
            "story": "epic_link",
            "task": "epic_link",
            "bug": "epic_link",
            "spike": "epic_link",
            "sub-task": "parent"
        }
    )  # Maps issue types to logical field names


class EnterpriseConfig(BaseModel):
    """Enterprise-wide configuration (enterprise.json).

    Contains company/enterprise-level settings that apply across
    all organizations and projects (AI backend enforcement, backend overrides).
    """

    agent_backend: Optional[str] = None  # AI agent backend enforced by enterprise (e.g., "claude", "github-copilot")
    backend_overrides: Optional[Dict[str, Any]] = None  # Override any fields from backend configs (backends/*.json). Example: {"field_mappings": {"components": {"required_for": ["Bug", "Story"]}}}


class OrganizationConfig(BaseModel):
    """Organization/Project-specific JIRA configuration (organization.json).

    Contains organization or project-specific settings that should be
    shared across teams (project key, field aliases, sync filters).
    """

    jira_project: Optional[str] = None  # JIRA project key (e.g., "PROJ")
    sync_filters: Dict[str, JiraFiltersConfig] = Field(default_factory=dict)  # Renamed from 'filters'
    status_grouping_field: Optional[str] = None  # Field to group by in status dashboard (e.g., "sprint", "iteration", "release") - None means no grouping
    status_totals_field: Optional[str] = None  # Field to sum for totals in status dashboard (e.g., "points", "story_points", "effort") - None means no totals
    hierarchical_config_source: Optional[str] = None  # URL or path to hierarchical config files (ENTERPRISE.md, ORGANIZATION.md, TEAM.md, USER.md). Supports file://, http://, https://. Example: "https://github.com/ansible-saas/devflow-for-red-hatters/configs" or "file:///path/to/configs"


class TeamConfig(BaseModel):
    """Team-specific JIRA configuration (team.json).

    Contains team-specific settings that may vary between teams
    (custom field defaults, comment visibility, time tracking preferences).
    """

    jira_custom_field_defaults: Optional[Dict[str, Any]] = None  # Default values for custom fields (e.g., {"workstream": "Platform"})
    jira_system_field_defaults: Optional[Dict[str, Any]] = None  # Default values for JIRA system fields (e.g., {"components": ["ansible-saas"], "labels": ["backend"]})
    time_tracking_enabled: bool = True  # Team-wide time tracking preference
    jira_comment_visibility_type: Optional[str] = None  # Comment visibility type: 'group' or 'role'
    jira_comment_visibility_value: Optional[str] = None  # Comment visibility value (group/role name)
    agent_backend: Optional[str] = None  # AI agent backend enforced by team (e.g., "claude", "github-copilot")


class JiraConfig(BaseModel):
    """JIRA integration configuration (merged view from backend/org/team configs).

    This is the unified configuration model that combines data from:
    - JiraBackendConfig (backends/jira.json)
    - OrganizationConfig (organization.json)
    - TeamConfig (team.json)

    Used for backward compatibility with existing code.
    """

    url: str
    transitions: Dict[str, JiraTransitionConfig]
    time_tracking: bool = True
    filters: Dict[str, JiraFiltersConfig] = Field(default_factory=dict)
    project: Optional[str] = None  # JIRA project key (e.g., "PROJ")
    custom_field_defaults: Optional[Dict[str, Any]] = None  # Default values for custom fields (e.g., {"workstream": "Platform", "affected_version": "v1.0"})
    system_field_defaults: Optional[Dict[str, Any]] = None  # Default values for JIRA system fields (e.g., {"components": ["ansible-saas"], "labels": ["backend"]})
    affected_version: Optional[str] = None  # Default affected version for bugs (e.g., "v1.0.0")
    field_mappings: Optional[Dict[str, Dict[str, Any]]] = None  # Cached field mappings (creation fields only)
    field_cache_timestamp: Optional[str] = None  # ISO timestamp of last field discovery
    field_cache_auto_refresh: bool = True  # Auto-refresh field mappings when stale
    field_cache_max_age_hours: int = 24  # Maximum age in hours before cache is stale (default: 24h)
    comment_visibility_type: Optional[str] = None  # Comment visibility type: 'group' or 'role'
    comment_visibility_value: Optional[str] = None  # Comment visibility value (group/role name)
    parent_field_mapping: Optional[Dict[str, str]] = Field(
        default_factory=lambda: {
            "story": "epic_link",
            "task": "epic_link",
            "bug": "epic_link",
            "spike": "epic_link",
            "sub-task": "parent"
        }
    )  # Maps issue types to logical field names


class RepoDetectionConfig(BaseModel):
    """Repository detection configuration."""

    method: str = "keyword_match"
    fallback: str = "prompt"


class WorkspaceDefinition(BaseModel):
    """Definition for a named workspace directory.

    Workspaces allow managing multiple repository locations for concurrent
    multi-branch development or product/feature grouping (like VSCode workspaces).
    """

    name: str = Field(description="Unique workspace name (e.g., 'primary', 'product-a', 'feat-caching')")
    path: str = Field(description="Absolute or home-relative path to workspace directory")

    @field_validator('path')
    @classmethod
    def expand_path(cls, v: str) -> str:
        """Expand ~ and environment variables in path."""
        from pathlib import Path
        return str(Path(v).expanduser())


class RepoConfig(BaseModel):
    """Repository configuration."""

    workspaces: List[WorkspaceDefinition] = Field(default_factory=list)
    last_used_workspace: Optional[str] = None  # Name of last used workspace
    detection: RepoDetectionConfig = Field(default_factory=RepoDetectionConfig)
    keywords: Dict[str, List[str]] = Field(default_factory=dict)

    def get_workspace_by_name(self, name: str) -> Optional[WorkspaceDefinition]:
        """Get a workspace by name.

        Args:
            name: Workspace name to find

        Returns:
            WorkspaceDefinition or None if not found
        """
        for workspace in self.workspaces:
            if workspace.name == name:
                return workspace
        return None

    def get_default_workspace_path(self) -> Optional[str]:
        """Get the last used workspace path.

        Returns:
            Workspace path string or None if no last used workspace is set
        """
        if self.last_used_workspace:
            workspace = self.get_workspace_by_name(self.last_used_workspace)
            if workspace:
                return workspace.path
        return None


class TimeTrackingConfig(BaseModel):
    """Time tracking configuration."""

    auto_start: bool = True
    auto_pause_after: Optional[str] = "30m"
    reminder_interval: Optional[str] = "2h"


class SessionSummaryConfig(BaseModel):
    """Session summary configuration."""

    mode: str = "local"  # "local" | "ai" | "both"
    api_key_env: str = "ANTHROPIC_API_KEY"  # Environment variable name for Claude API


class TemplateConfig(BaseModel):
    """Template auto-creation and auto-use configuration."""

    auto_create: bool = Field(
        True, description="Automatically create templates when creating sessions in new directories"
    )
    auto_use: bool = Field(True, description="Automatically use matching templates when creating sessions")


class ContextFile(BaseModel):
    """Configuration for a single context file to include in initial prompts."""

    path: str = Field(description="File path (local) or URL (GitHub/GitLab)")
    description: str = Field(description="Human-readable description of the context file")
    hidden: bool = Field(default=False, description="Hide from TUI (used for auto-managed files like skills)")


class ContextFilesConfig(BaseModel):
    """Configuration for context files in initial prompts."""

    files: List[ContextFile] = Field(
        default_factory=list, description="Additional context files to include (beyond AGENTS.md and CLAUDE.md)"
    )


class PromptsConfig(BaseModel):
    """User prompt preferences configuration.

    Allows users to configure automatic answers for common prompts
    to skip repetitive questions in daf new/open/complete commands.
    """

    auto_commit_on_complete: Optional[bool] = None
    auto_accept_ai_commit_message: Optional[bool] = None  # Accept AI-generated commit message without asking
    auto_create_pr_on_complete: Optional[bool] = None
    auto_create_pr_status: str = "prompt"  # "draft", "ready", or "prompt" - controls PR/MR creation status
    auto_add_issue_summary: Optional[bool] = None
    auto_update_jira_pr_url: Optional[bool] = None
    auto_push_to_remote: Optional[bool] = None  # Auto-push branches to remote: True (always), False (never), None (prompt)
    auto_launch_claude: Optional[bool] = None  # Deprecated - use auto_launch_agent instead
    auto_launch_agent: Optional[bool] = None  # Auto-launch AI agent: True (always), False (never), None (prompt)
    auto_checkout_branch: Optional[bool] = None
    auto_sync_with_base: Optional[str] = None  # "always", "never", or None (prompt)
    auto_complete_on_exit: Optional[bool] = None  # Automatically run 'daf complete' when AI agent exits
    default_branch_strategy: Optional[str] = None  # "from_default" or "from_current"
    remember_last_repo_per_project: Dict[str, str] = Field(default_factory=dict)  # Map: {"PROJ": "backend-api"}
    show_prompt_unit_tests: bool = True  # Show testing instructions in initial prompt for development sessions
    auto_load_related_conversations: bool = False  # Auto-prompt AI agent to read other conversations in multi-project sessions

    @field_validator('auto_create_pr_status', mode='before')
    @classmethod
    def validate_pr_status(cls, v: Any) -> str:
        """Validate auto_create_pr_status field.

        Ensures only valid values ("draft", "ready", "prompt") are accepted.
        Falls back to "prompt" for invalid or None values.
        """
        if v is None or v not in ["draft", "ready", "prompt"]:
            return "prompt"
        return v


class MockServicesConfig(BaseModel):
    """Mock services configuration model (reserved for future use).

    Note: Mock mode is currently activated via the DAF_MOCK_MODE=1 environment variable
    and does not require configuration. This class is reserved for potential future
    configuration options.
    """

    enabled: bool = False
    data_file: str = Field(description="Path to persistent mock data file")
    services: Dict[str, bool] = Field(
        default_factory=dict,
        description="Map of service name to enabled status (jira, github, gitlab, claude)"
    )


class StorageConfig(BaseModel):
    """Storage backend configuration.

    Controls which storage backend to use for session persistence.
    """

    backend: str = "file"  # "file" | "django" (future)


class UserConfig(BaseModel):
    """User personal preferences configuration (config.json).

    Contains user-specific settings that should never be shared
    (workspace path, personal prompts, context files).
    """

    backend_config_source: str = "local"  # "local" or "central_db" (future)
    repos: RepoConfig
    time_tracking: TimeTrackingConfig = Field(default_factory=TimeTrackingConfig)
    session_summary: SessionSummaryConfig = Field(default_factory=SessionSummaryConfig)
    templates: TemplateConfig = Field(default_factory=TemplateConfig)
    context_files: ContextFilesConfig = Field(default_factory=ContextFilesConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)
    pr_template_url: Optional[str] = None  # URL to PR/MR template
    storage: StorageConfig = Field(default_factory=StorageConfig)  # Storage backend config
    mock_services: Optional[MockServicesConfig] = None  # Reserved for future use
    gcp_vertex_region: Optional[str] = None  # GCP Vertex AI region
    update_checker_timeout: int = 10  # Timeout in seconds for update check requests
    jira_affected_version: Optional[str] = None  # User's current affected version for bug creation (e.g., "v1.0.0")


class Config(BaseModel):
    """Main configuration for DevAIFlow (merged view from all config files).

    This is the unified configuration model used throughout the application.
    In the new format, it combines data from:
    - config.json (user preferences)
    - backends/jira.json (backend settings)
    - organization.json (org settings)
    - team.json (team settings)

    For backward compatibility, it can also load from the old single config.json format.
    """

    jira: JiraConfig
    repos: RepoConfig
    time_tracking: TimeTrackingConfig = Field(default_factory=TimeTrackingConfig)
    session_summary: SessionSummaryConfig = Field(default_factory=SessionSummaryConfig)
    templates: TemplateConfig = Field(default_factory=TemplateConfig)
    context_files: ContextFilesConfig = Field(default_factory=ContextFilesConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)
    pr_template_url: Optional[str] = None  # URL to PR/MR template
    storage: StorageConfig = Field(default_factory=StorageConfig)  # Storage backend config
    backend_config_source: str = "local"  # "local" or "central_db" (future) - NEW in PROJ-62719
    issue_tracker_backend: str = "jira"  # Issue tracker backend: "jira", "github", "gitlab", etc. - NEW in PROJ-63197
    agent_backend: str = "claude"  # AI agent backend: "claude", "copilot", etc. - NEW in PROJ-63294
    mock_services: Optional[MockServicesConfig] = None  # Reserved for future use (mock mode uses DAF_MOCK_MODE env var)
    gcp_vertex_region: Optional[str] = None  # GCP Vertex AI region (e.g., "us-central1", "europe-west4")
    update_checker_timeout: int = 10  # Timeout in seconds for update check requests (default: 10)


    class Config:
        populate_by_name = True


class WorkSession(BaseModel):
    """A single work session with start/end times."""

    start: datetime
    end: Optional[datetime] = None
    duration: Optional[str] = None
    user: Optional[str] = None  # Username of person who worked on this session

    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.end is None:
            return (datetime.now() - self.start).total_seconds()
        return (self.end - self.start).total_seconds()


class ConversationContext(BaseModel):
    """Context for a single AI agent conversation within a session.

    Each conversation represents work in one repository/directory for a session.
    A session can have multiple conversations (one per repository) when working
    on cross-repository features.

    Multi-Agent-Session Support:
    - Each repository can have multiple AI agent sessions over time
    - archived field marks whether this is the active conversation or historical
    - conversation_history tracks all AI agent session IDs created for this conversation

    Portable Path Storage:
    - New sessions store repo_name + relative_path for portability
    - Sessions can use project_path as fallback

    Fork Support:
    - remote_url stores the git remote URL where the branch was pushed
    - Enables collaboration across forks (different users have different origins)
    - If not set, defaults to 'origin' remote
    """

    ai_agent_session_id: str  # UUID for AI agent conversation (current/active)
    project_path: Optional[str] = None  # Full path to repo (legacy, still used as fallback)
    branch: Optional[str] = None  # Git branch for this repo (None for ticket_creation sessions)
    base_branch: str = "main"  # Base branch
    remote_url: Optional[str] = None  # Git remote URL where branch was pushed (for fork support)
    created: datetime = Field(default_factory=datetime.now)
    last_active: datetime = Field(default_factory=datetime.now)
    message_count: int = 0
    prs: List[str] = Field(default_factory=list)

    # Multi-Agent-Session Support
    archived: bool = False  # True if this conversation is archived (not active)
    conversation_history: List[str] = Field(default_factory=list)  # All AI agent session IDs (chronological)
    summary: Optional[str] = Field(
        default=None,
        description="Summary of work done in this conversation (auto-generated or user-provided)"
    )

    # Portable path fields
    repo_name: Optional[str] = Field(default=None)  # Repository directory name
    relative_path: Optional[str] = Field(default=None)  # Path relative to workspace root

    # Temporary directory support for ticket_creation sessions
    temp_directory: Optional[str] = Field(default=None)  # Path to temporary directory (if using temp clone)
    original_project_path: Optional[str] = Field(default=None)  # Original project path (before temp clone)

    def get_project_path(self, workspace: Optional[str] = None) -> str:
        """Get the full project path, reconstructing from relative path if available.

        Args:
            workspace: Workspace root directory. If None, falls back to project_path.

        Returns:
            Full absolute path to the project

        Raises:
            ValueError: If no path information is available
        """
        # Prefer relative_path if available and workspace is provided
        if self.relative_path and workspace:
            from pathlib import Path
            return str(Path(workspace).expanduser().resolve() / self.relative_path)

        # Fallback to stored absolute path
        if self.project_path:
            return self.project_path

        # Should not happen, but provide clear error
        raise ValueError("No project path information available")

    def get_repo_name(self) -> str:
        """Get the repository name.

        Returns:
            Repository directory name
        """
        if self.repo_name:
            return self.repo_name

        # Fallback: extract from original_project_path (prioritize over temp directories)
        from pathlib import Path
        if self.original_project_path:
            return Path(self.original_project_path).name

        # Fallback: extract from project_path
        if self.project_path:
            return Path(self.project_path).name

        # Last resort: extract from relative_path
        if self.relative_path:
            return Path(self.relative_path).name

        raise ValueError("No repository name available")

    @model_validator(mode='after')
    def populate_conversation_history(self) -> 'ConversationContext':
        """Auto-populate conversation_history if empty (for backward compatibility).

        For existing conversations loaded from disk that don't have conversation_history,
        we initialize it with the current ai_agent_session_id.
        """
        if not self.conversation_history and self.ai_agent_session_id:
            self.conversation_history = [self.ai_agent_session_id]
        return self

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        # Allow extra fields in JSON to be ignored (for forward compatibility)
        extra = "ignore"


class Conversation(BaseModel):
    """Container for active and archived Claude Code conversations in a repository.

    This class manages multiple Claude Code sessions over time for a single repository.
    When the context gets too long, users can create a new session which archives the
    current one.

    Architecture:
    - active_session: The current Claude Code conversation (NOT archived)
    - archived_sessions: List of previous conversations in chronological order

    This design provides:
    - Direct access to active session (no looping needed)
    - Clear separation between active and archived
    - Simple swapping between sessions
    """

    active_session: ConversationContext
    archived_sessions: List[ConversationContext] = Field(default_factory=list)

    def get_all_sessions(self) -> List[ConversationContext]:
        """Get all sessions (active + archived) in chronological order.

        Returns:
            List with archived sessions first, then active session
        """
        return self.archived_sessions + [self.active_session]

    def archive_active_and_set_new(self, new_session: ConversationContext) -> None:
        """Archive the current active session and set a new one.

        Args:
            new_session: The new conversation context to make active
        """
        # Mark current active as archived and add to list
        self.active_session.archived = True
        self.archived_sessions.append(self.active_session)

        # Set new session as active
        new_session.archived = False
        self.active_session = new_session

    def swap_active_session(self, session_id: str) -> bool:
        """Swap the active session with an archived one by UUID.

        Args:
            session_id: Claude session UUID to make active

        Returns:
            True if swap succeeded, False if session not found
        """
        # Check if the requested session is already active
        if self.active_session.ai_agent_session_id == session_id:
            return True

        # Find the session in archived list
        for i, archived_session in enumerate(self.archived_sessions):
            if archived_session.ai_agent_session_id == session_id:
                # Swap: current active becomes archived, archived becomes active
                old_active = self.active_session
                old_active.archived = True

                new_active = self.archived_sessions.pop(i)
                new_active.archived = False

                self.archived_sessions.append(old_active)
                self.active_session = new_active
                return True

        return False

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        # Allow extra fields in JSON to be ignored (for forward compatibility)
        extra = "ignore"


class Session(BaseModel):
    """A Claude Code session, optionally mapped to a issue tracker ticket.

    Each session has a unique name (identifier).

    Multi-Conversation Architecture :
    - A session can have multiple conversations (one per repository)
    - Each repository can have multiple Claude Code sessions over time
    - conversations: Dict[str, Conversation] - maps repo to Conversation object
    - Each Conversation has active_session + archived_sessions list
    - Direct access to active session (no looping), simple swapping
    - Old single-conversation sessions are auto-migrated on load

    Workspace Support (AAP-63377):
    - workspace_name: Optional[str] - Selected workspace for this session
    - Enables concurrent sessions on same project in different workspaces
    - Session remembers workspace selection for automatic use on reopen
    """

    name: str  # Session name (primary identifier, must be unique)
    goal: Optional[str] = None  # Optional session goal (uses issue tracker title if not provided)
    session_type: str = "development"  # Session type: "development" (default), "ticket_creation", "investigation", etc.
    status: str = "created"
    created: datetime = Field(default_factory=datetime.now)
    started: Optional[datetime] = None
    last_active: datetime = Field(default_factory=datetime.now)
    work_sessions: List[WorkSession] = Field(default_factory=list)
    time_tracking_state: str = "paused"
    tags: List[str] = Field(default_factory=list)
    related_sessions: List[str] = Field(default_factory=list)

    # Multi-conversation support
    # Dict maps working_dir to Conversation (contains active + archived sessions)
    # During deserialization, accepts both old format (ConversationContext) and new format (Conversation)
    conversations: Dict[str, Union[ConversationContext, Conversation]] = Field(default_factory=dict)
    working_directory: Optional[str] = None  # Tracks active conversation

    # Workspace support (AAP-63377)
    workspace_name: Optional[str] = None  # Selected workspace name for this session

    # Issue tracker abstraction
    # Replaces JIRA-specific fields with tracker-agnostic structure
    issue_tracker: str = "jira"  # "jira" | "github" | "gitlab" | etc.
    issue_key: Optional[str] = None  # Tracker issue identifier (e.g., "PROJ-12345", "org/repo#123")
    issue_updated: Optional[str] = None  # ISO timestamp of last issue update (for sync)
    issue_metadata: Dict[str, Any] = Field(default_factory=dict)  # Tracker-specific metadata
    # For JIRA, issue_metadata contains: {summary, type, status, sprint, points, assignee, epic}
    # For GitHub, issue_metadata might contain: {title, state, labels, milestone, assignees}

    def time_by_user(self) -> Dict[str, float]:
        """Calculate total seconds worked by each user.

        Returns:
            Dictionary mapping username to total seconds worked
        """
        user_time: Dict[str, float] = {}
        for ws in self.work_sessions:
            if ws.end:  # Only count completed sessions
                user = ws.user or "unknown"
                user_time[user] = user_time.get(user, 0.0) + ws.duration_seconds()
        return user_time

    def total_time_seconds(self) -> float:
        """Calculate total time across all users."""
        return sum(self.time_by_user().values())


    @property
    def active_conversation(self) -> Optional[ConversationContext]:
        """Get the active conversation based on working_directory.

        Returns:
            Active ConversationContext or None if no active conversation

        Note: Direct access to active_session in Conversation object.
        """
        if self.working_directory and self.working_directory in self.conversations:
            return self.conversations[self.working_directory].active_session
        # Fallback: if only one repository exists, return its active session
        if len(self.conversations) == 1:
            conversation = list(self.conversations.values())[0]
            return conversation.active_session
        return None

    def get_conversation(self, working_dir: str) -> Optional[ConversationContext]:
        """Get the active conversation for a working directory.

        Args:
            working_dir: Working directory name (e.g., "backend-api")

        Returns:
            Active ConversationContext or None if not found

        Note: Direct access to active_session.
        """
        conversation = self.conversations.get(working_dir)
        return conversation.active_session if conversation else None

    def add_conversation(
        self,
        working_dir: str,
        ai_agent_session_id: str,
        project_path: str,
        branch: str,
        base_branch: str = "main",
        remote_url: Optional[str] = None,
        temp_directory: Optional[str] = None,
        original_project_path: Optional[str] = None,
        workspace: Optional[str] = None,
    ) -> ConversationContext:
        """Add a new conversation to this session.

        Args:
            working_dir: Working directory name (e.g., "backend-api")
            ai_agent_session_id: UUID for Claude Code conversation
            project_path: Full path to repository
            branch: Git branch for this conversation
            base_branch: Base branch (default: "main")
            remote_url: Optional git remote URL where branch is pushed (for fork support)
            temp_directory: Optional temporary directory path (for ticket_creation sessions)
            original_project_path: Optional original project path (before temp clone)
            workspace: Optional workspace root for computing relative path

        Returns:
            The created ConversationContext

        Note: Creates a Conversation object with this as the active_session.
        If a conversation already exists for this working_dir, raises error.
        """
        from pathlib import Path

        # Check if conversation already exists for this directory (should use create_new_conversation instead)
        if working_dir in self.conversations:
            raise ValueError(
                f"Conversation already exists for directory '{working_dir}'. "
                f"Use create_new_conversation() to add additional Claude sessions."
            )

        # Compute relative_path and repo_name if workspace is provided
        relative_path = None
        repo_name = None

        if workspace:
            workspace_path = Path(workspace).expanduser().resolve()
            abs_project_path = Path(project_path).expanduser().resolve()

            # Try to compute relative path
            try:
                rel_path = abs_project_path.relative_to(workspace_path)
                relative_path = str(rel_path)
                repo_name = abs_project_path.name
            except ValueError:
                # Project not in workspace, keep absolute path only
                repo_name = abs_project_path.name
        else:
            # No workspace provided, just extract repo name
            repo_name = Path(project_path).name

        # Override repo_name with original_project_path if using temp directory
        if original_project_path:
            repo_name = Path(original_project_path).name

        conversation_context = ConversationContext(
            ai_agent_session_id=ai_agent_session_id,
            project_path=project_path,
            branch=branch,
            base_branch=base_branch,
            remote_url=remote_url,
            temp_directory=temp_directory,
            original_project_path=original_project_path,
            repo_name=repo_name,
            relative_path=relative_path,
        )

        # Create a new Conversation object with this as the active session
        conversation = Conversation(
            active_session=conversation_context,
            archived_sessions=[]
        )
        self.conversations[working_dir] = conversation
        return conversation_context

    def get_all_conversations(self) -> List[ConversationContext]:
        """Get all conversations across all repositories (both active and archived).

        Returns:
            List of all ConversationContext objects

        Note: Returns conversations from all repositories in chronological order.
        """
        all_convs = []
        for conversation in self.conversations.values():
            all_convs.extend(conversation.get_all_sessions())
        # Sort by created date (oldest first)
        all_convs.sort(key=lambda c: c.created)
        return all_convs

    def get_conversation_by_uuid(self, ai_agent_session_id: str) -> Optional[ConversationContext]:
        """Find a conversation by its Claude session UUID.

        Args:
            ai_agent_session_id: Claude session UUID to find

        Returns:
            ConversationContext if found, None otherwise

        Note: Searches across all repositories and all conversations.
        """
        for conversation in self.conversations.values():
            for conv in conversation.get_all_sessions():
                if conv.ai_agent_session_id == ai_agent_session_id:
                    return conv
        return None

    def create_new_conversation(
        self,
        working_dir: str,
        project_path: str,
        branch: str,
        base_branch: str = "main",
        remote_url: Optional[str] = None,
        workspace: Optional[str] = None,
    ) -> ConversationContext:
        """Create a new conversation and archive the current active one.

        This is the main method for implementing --new-conversation functionality.

        Args:
            working_dir: Working directory name (e.g., "backend-api")
            project_path: Full path to repository
            branch: Git branch for this conversation
            base_branch: Base branch (default: "main")
            remote_url: Optional git remote URL where branch is pushed
            workspace: Optional workspace root for computing relative path

        Returns:
            The newly created ConversationContext

        Note: Archives the current active conversation and creates a new one
        with a fresh Claude session UUID.
        """
        import uuid
        from pathlib import Path

        # Check if conversation exists for this directory
        if working_dir not in self.conversations:
            raise ValueError(
                f"No conversation exists for directory '{working_dir}'. "
                f"Use add_conversation() to create the first conversation."
            )

        # Generate new Claude session UUID
        new_ai_agent_session_id = str(uuid.uuid4())

        # Compute relative_path and repo_name if workspace is provided
        relative_path = None
        repo_name = None

        if workspace:
            workspace_path = Path(workspace).expanduser().resolve()
            abs_project_path = Path(project_path).expanduser().resolve()

            # Try to compute relative path
            try:
                rel_path = abs_project_path.relative_to(workspace_path)
                relative_path = str(rel_path)
                repo_name = abs_project_path.name
            except ValueError:
                # Project not in workspace, keep absolute path only
                repo_name = abs_project_path.name
        else:
            # No workspace provided, just extract repo name
            repo_name = Path(project_path).name

        # Create new conversation context
        new_conversation_context = ConversationContext(
            ai_agent_session_id=new_ai_agent_session_id,
            project_path=project_path,
            branch=branch,
            base_branch=base_branch,
            remote_url=remote_url,
            repo_name=repo_name,
            relative_path=relative_path,
        )

        # Update conversation_history
        if not new_conversation_context.conversation_history:
            new_conversation_context.conversation_history = []
        new_conversation_context.conversation_history.append(new_ai_agent_session_id)

        # Auto-generate summary for the conversation being archived
        # This helps users understand what work was done in archived sessions
        current_active = self.conversations[working_dir].active_session
        if current_active and not current_active.summary:
            # Attempt to auto-generate summary using helper method
            summary = self._generate_conversation_summary(current_active)
            if summary:
                current_active.summary = summary

        # Archive current active and set new one
        self.conversations[working_dir].archive_active_and_set_new(new_conversation_context)

        return new_conversation_context

    def reactivate_conversation(self, ai_agent_session_id: str) -> bool:
        """Reactivate an archived conversation by its UUID.

        This is the main method for implementing --conversation-id functionality.

        Args:
            ai_agent_session_id: Claude session UUID to reactivate

        Returns:
            True if conversation was reactivated, False if not found

        Note: Archives the current active conversation and reactivates
        the specified one.
        """
        # Find which working directory contains this conversation
        target_working_dir = None

        for working_dir, conversation in self.conversations.items():
            # Check if this conversation (active or archived) contains the UUID
            for conv in conversation.get_all_sessions():
                if conv.ai_agent_session_id == ai_agent_session_id:
                    target_working_dir = working_dir
                    break
            if target_working_dir:
                break

        if not target_working_dir:
            return False

        # Swap the active session using Conversation's method
        success = self.conversations[target_working_dir].swap_active_session(ai_agent_session_id)

        if success:
            # Update working_directory to point to this conversation
            self.working_directory = target_working_dir

        return success

    def _generate_conversation_summary(self, conversation: ConversationContext) -> Optional[str]:
        """Generate summary for a conversation using existing summary generation code.

        This is a helper method for auto-generating summaries when archiving conversations.

        Args:
            conversation: ConversationContext to generate summary for

        Returns:
            Generated summary text or None if generation fails
        """
        try:
            # Import here to avoid circular dependency
            from devflow.session.summary import generate_session_summary, generate_prose_summary

            # Create temporary Session-like structure for summary generation
            # We need to create a minimal Session with just this conversation
            temp_session = type('obj', (object,), {
                'name': self.name,
                'goal': self.goal,
                'working_directory': self.working_directory,
                'conversations': {self.working_directory: type('obj', (object,), {
                    'active_session': conversation,
                    'get_all_sessions': lambda: [conversation]
                })()},
                'active_conversation': conversation
            })()

            # Generate summary using "local" mode (no AI calls for archived summaries)
            summary_data = generate_session_summary(temp_session)
            prose_summary = generate_prose_summary(summary_data, mode="local")

            if prose_summary and prose_summary.strip():
                return prose_summary.strip()

            return None
        except Exception:
            # If summary generation fails, return None
            # User can manually add summary later
            return None

    @model_validator(mode='after')
    def migrate_conversations(self) -> 'Session':
        """Auto-migrate old conversation format to new Conversation class format.

        Old format: Dict[str, ConversationContext]
        New format: Dict[str, Conversation]

        This validator ensures backward compatibility by detecting old sessions
        and converting them to the new format automatically on load.
        """
        migrated = False
        new_conversations = {}

        for working_dir, value in list(self.conversations.items()):
            if isinstance(value, ConversationContext):
                # Old format detected - migrate to Conversation object
                conversation = Conversation(
                    active_session=value,
                    archived_sessions=[]
                )
                new_conversations[working_dir] = conversation
                migrated = True
            elif isinstance(value, Conversation):
                # Already in new format
                new_conversations[working_dir] = value
            else:
                # Unexpected format - keep as-is (will likely fail validation)
                new_conversations[working_dir] = value

        if migrated:
            self.conversations = new_conversations

        return self

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class SessionIndex(BaseModel):
    """Index of all sessions.

    Each session has a unique name (identifier). Sessions are stored as a dictionary
    mapping session name to Session object.
    """

    sessions: Dict[str, Session] = Field(default_factory=dict)

    def add_session(self, session: Session) -> None:
        """Add a session to the index.

        Args:
            session: Session object to add

        Raises:
            ValueError: If a session with this name already exists
        """
        if session.name in self.sessions:
            raise ValueError(f"Session '{session.name}' already exists")
        self.sessions[session.name] = session

    def get_session(self, identifier: str) -> Optional[Session]:
        """Get a session by name or issue key.

        Smart lookup: tries session name first, then issue key.

        Args:
            identifier: Session name or issue tracker key

        Returns:
            Session object or None if not found
        """
        # Try as session name first
        if identifier in self.sessions:
            return self.sessions[identifier]

        # Try as issue key - find first session with matching issue key
        for session in self.sessions.values():
            if session.issue_key == identifier:
                return session

        return None

    def get_sessions(self, identifier: str) -> List[Session]:
        """Get all sessions for a session name or issue key.

        Note: This method now returns a list with at most one session for backward compatibility.
        Use get_session() for more efficient single-session retrieval.

        Args:
            identifier: Session name or issue tracker key

        Returns:
            List containing the Session object if found, empty list otherwise
        """
        session = self.get_session(identifier)
        return [session] if session else []

    def remove_session(self, identifier: str) -> None:
        """Remove a session from the index.

        Smart lookup: tries session name first, then issue key.

        Args:
            identifier: Session name or issue tracker key
        """
        # Try as session name first
        if identifier in self.sessions:
            del self.sessions[identifier]
            return

        # Try as issue key - find and remove first session with matching issue key
        for name, session in self.sessions.items():
            if session.issue_key == identifier:
                del self.sessions[name]
                return

    def list_sessions(
        self,
        status: Optional[str] = None,
        working_directory: Optional[str] = None,
        issue_metadata_filters: Optional[Dict[str, str]] = None,
        issue_status: Optional[str] = None,
        since: Optional[datetime] = None,
        before: Optional[datetime] = None,
    ) -> List[Session]:
        """List sessions with optional filters.

        Args:
            status: Filter by session status (comma-separated for multiple)
            working_directory: Filter by working directory
            issue_metadata_filters: Filter by custom fields (e.g., {"sprint": "Sprint 1", "severity": "Critical"})
            issue_status: Filter by issue tracker status (comma-separated for multiple)
            since: Filter by sessions active since this datetime
            before: Filter by sessions active before this datetime

        Returns:
            List of Session objects matching all filters
        """
        # Get all sessions
        all_sessions = list(self.sessions.values())

        # Multiple status filtering (comma-separated)
        if status:
            status_list = [s.strip() for s in status.split(",")]
            all_sessions = [s for s in all_sessions if s.status in status_list]

        # Multiple JIRA status filtering (comma-separated)
        if issue_status:
            issue_status_list = [js.strip() for js in issue_status.split(",")]
            all_sessions = [
                s for s in all_sessions
                if s.issue_metadata.get("status") in issue_status_list
            ]

        if working_directory:
            all_sessions = [s for s in all_sessions if s.working_directory == working_directory]

        # Custom field filtering
        if issue_metadata_filters:
            for field_name, field_value in issue_metadata_filters.items():
                all_sessions = [
                    s for s in all_sessions
                    if s.issue_metadata.get(field_name) == field_value
                ]

        # Time-based filtering
        if since:
            all_sessions = [s for s in all_sessions if s.last_active >= since]

        if before:
            all_sessions = [s for s in all_sessions if s.last_active <= before]

        # Sort by last_active (most recent first)
        all_sessions.sort(key=lambda s: s.last_active, reverse=True)
        return all_sessions
