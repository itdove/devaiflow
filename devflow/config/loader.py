"""Configuration file loading and management."""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pydantic import ValidationError
from rich.console import Console

from devflow.utils.paths import get_cs_home

from .models import Config, SessionIndex

console = Console()


class ConfigLoader:
    """Load and manage configuration files."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the config loader.

        Args:
            config_dir: Directory for config files. Defaults to DEVAIFLOW_HOME or ~/.daf-sessions
        """
        if config_dir is None:
            config_dir = get_cs_home()
        self.config_dir = config_dir
        self.config_file = config_dir / "config.json"
        self.sessions_file = config_dir / "sessions.json"
        self.sessions_dir = config_dir / "sessions"
        self.session_home = config_dir  # Alias for compatibility

        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def validate_config_dict(self, config_dict: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a configuration dictionary against the Pydantic model.

        Args:
            config_dict: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if validation passed
            - error_message: None if valid, error message string if invalid
        """
        try:
            # Pydantic validation happens automatically when constructing the model
            Config(**config_dict)
            return (True, None)
        except ValidationError as e:
            # Format validation errors nicely
            error_lines = []
            for error in e.errors():
                loc = " -> ".join(str(l) for l in error["loc"])
                msg = error["msg"]
                error_lines.append(f"  {loc}: {msg}")

            error_message = "Configuration validation failed:\n" + "\n".join(error_lines)
            return (False, error_message)
        except Exception as e:
            return (False, f"Unexpected validation error: {str(e)}")

    def validate_config_file(self) -> Tuple[bool, Optional[str]]:
        """Validate the configuration file.

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if validation passed
            - error_message: None if valid, error message string if invalid
        """
        if not self.config_file.exists():
            return (False, f"Config file not found: {self.config_file}")

        try:
            with open(self.config_file, "r") as f:
                config_dict = json.load(f)
        except json.JSONDecodeError as e:
            return (False, f"Invalid JSON in config file: {e}")
        except Exception as e:
            return (False, f"Error reading config file: {e}")

        return self.validate_config_dict(config_dict)

    def load_config(self, validate: bool = True) -> Optional[Config]:
        """Load configuration from config.json or 4 separate files.

        Automatically detects format:
        - Old format: Single config.json with 'jira' section (backward compatible)
        - New format: Split into config.json + organization.json + team.json + backends/jira.json

        Args:
            validate: If True, validate config against schema before loading (default: True)
                     Set to False to skip validation (useful for migration/repair scenarios)

        Returns:
            Config object if file exists, None otherwise

        Raises:
            ValueError: If config file is invalid or validation fails
        """
        if not self.config_file.exists():
            return None

        # Detect format and route to appropriate loader
        if self._is_old_format():
            # OLD FORMAT: Load from single config.json
            return self._load_old_format_config(validate)
        else:
            # NEW FORMAT: Load from 4 separate files
            return self._load_new_format_config()

    def _load_old_format_config(self, validate: bool = True) -> Optional[Config]:
        """Load configuration from old single config.json format.

        Args:
            validate: If True, validate config against schema before loading

        Returns:
            Config object

        Raises:
            ValueError: If config file is invalid or validation fails
        """
        try:
            with open(self.config_file, "r") as f:
                data = json.load(f)

            # Optional pre-validation check (provides better error messages)
            if validate:
                is_valid, error_message = self.validate_config_dict(data)
                if not is_valid:
                    raise ValueError(error_message)

            config = Config(**data)

            # Validate configuration and show warnings
            from .validator import ConfigValidator
            validator = ConfigValidator(self.config_dir)
            validation_result = validator.validate_merged_config(config)
            validator.print_validation_warnings_on_load(validation_result)

            return config
        except ValidationError as e:
            # Pydantic validation error - format nicely
            error_lines = []
            for error in e.errors():
                loc = " -> ".join(str(l) for l in error["loc"])
                msg = error["msg"]
                error_lines.append(f"  {loc}: {msg}")
            raise ValueError("Configuration validation failed:\n" + "\n".join(error_lines))
        except Exception as e:
            raise ValueError(f"Failed to load config: {e}")

    def save_config(self, config: Config, validate: bool = True) -> None:
        """Save configuration (triggers migration from old to new format if needed).

        On first save after upgrade:
        - Detects old format
        - Creates timestamped backup
        - Moves local patches to .deprecated/ with warning
        - Splits config into 4 files (config.json, organization.json, team.json, backends/jira.json)

        On subsequent saves:
        - Saves to appropriate format (old or new)

        Args:
            config: Config object to save
            validate: If True, validate config before saving (default: True)
                     Set to False to skip validation (use with caution)

        Raises:
            ValueError: If validation fails (when validate=True)
        """
        # Validate before saving (prevent writing invalid configs)
        if validate:
            config_dict = config.model_dump(by_alias=True, exclude_none=False)
            is_valid, error_message = self.validate_config_dict(config_dict)
            if not is_valid:
                raise ValueError(f"Cannot save invalid configuration:\n{error_message}")

        # Check if migration is needed
        if self.config_file.exists() and self._is_old_format():
            # Old format exists - trigger migration to new format
            self._migrate_to_new_format(config)
        elif self.config_file.exists() and not self._is_old_format():
            # Already new format - save normally
            self._save_new_format_config(config)
        else:
            # No config file exists - save as old format for backward compatibility
            # (Tests and existing workflows expect old format by default)
            self._save_old_format_config(config)

    def _save_old_format_config(self, config: Config) -> None:
        """Save configuration in old single-file format.

        Args:
            config: Config object to save
        """
        # Create backup before saving
        self._backup_config()

        with open(self.config_file, "w") as f:
            # Use exclude_none=False to preserve ALL fields including None values
            # This prevents data loss when fields are explicitly set to None
            json.dump(config.model_dump(by_alias=True, exclude_none=False), f, indent=2)

        # Clean up old backups (keep only last 7 days)
        self._cleanup_old_backups(days=7)

    def load_sessions(self) -> SessionIndex:
        """Load session index from sessions.json.

        If mock mode is enabled (DAF_MOCK_MODE=1), loads from mock storage instead.

        Returns:
            SessionIndex object (empty if file doesn't exist)
        """
        from devflow.utils import is_mock_mode

        # Check if mock mode is enabled via environment variable
        if is_mock_mode():
            from devflow.mocks.persistence import MockDataStore
            store = MockDataStore()
            mock_data = store.load_session_index()
            if mock_data:
                return SessionIndex(**mock_data)
            return SessionIndex()

        # Normal (non-mock) behavior
        if not self.sessions_file.exists():
            return SessionIndex()

        try:
            with open(self.sessions_file, "r") as f:
                data = json.load(f)
            return SessionIndex(**data)
        except Exception as e:
            raise ValueError(f"Failed to load sessions: {e}")

    def save_sessions(self, index: SessionIndex) -> None:
        """Save session index to sessions.json with file locking.

        If mock mode is enabled (DAF_MOCK_MODE=1), saves to mock storage instead.

        Uses file locking (fcntl.flock on Unix) to prevent simultaneous writes
        from multiple processes.

        Args:
            index: SessionIndex object to save
        """
        from devflow.utils import is_mock_mode
        import os
        import sys

        # Check if mock mode is enabled via environment variable
        if is_mock_mode():
            from devflow.mocks.persistence import MockDataStore
            store = MockDataStore()
            store.save_session_index(index.model_dump())
            return

        # Normal (non-mock) behavior with file locking
        with open(self.sessions_file, "w") as f:
            # Acquire exclusive lock on Unix/Linux/macOS
            # Windows doesn't support fcntl, so we skip locking there
            if sys.platform != "win32":
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)

            try:
                json.dump(index.model_dump(), f, indent=2, default=str)
                f.flush()  # Explicitly flush to ensure data is written
                os.fsync(f.fileno())  # Force OS to write to disk (prevents data loss on signal)
            finally:
                # Release lock (happens automatically on close, but explicit is better)
                if sys.platform != "win32":
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_session_dir(self, session_name: str) -> Path:
        """Get the directory for a specific session group.

        Args:
            session_name: Session group name (primary identifier)

        Returns:
            Path to session directory
        """
        session_dir = self.sessions_dir / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def create_default_config(self) -> Config:
        """Create a default configuration.

        Returns:
            Default Config object
        """
        from .models import (
            JiraConfig,
            JiraFiltersConfig,
            JiraTransitionConfig,
            RepoConfig,
            TimeTrackingConfig,
        )

        default_config = Config(
            jira=JiraConfig(
                url="https://jira.example.com",
                user="your-username",
                project=None,
                workstream=None,
                transitions={
                    "on_start": JiraTransitionConfig(
                        from_status=["New", "To Do"],
                        to="In Progress",
                        prompt=False,
                    ),
                    "on_complete": JiraTransitionConfig(
                        from_status=["In Progress"],
                        to="",
                        prompt=True,
                    ),
                },
                filters={
                    "sync": JiraFiltersConfig(
                        status=["New", "To Do", "In Progress"],
                        required_fields=[],
                        assignee="currentUser()",
                    )
                },
                field_mappings=None,
                field_cache_timestamp=None,
            ),
            repos=RepoConfig(
                workspace=str(Path.home() / "development"),
                keywords={},
            ),
            time_tracking=TimeTrackingConfig(),
        )

        # Save the default config
        self.save_config(default_config)
        return default_config

    def _backup_config(self) -> None:
        """Create a timestamped backup of config.json before saving.

        Backups are stored as config.json.YYYYMMDD_HHMMSS in the same directory.
        """
        from datetime import datetime
        import shutil

        if not self.config_file.exists():
            return  # No config to backup

        # Create timestamp: YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.config_dir / f"config.json.{timestamp}"

        try:
            shutil.copy2(self.config_file, backup_file)
        except Exception as e:
            # Don't fail the save if backup fails, just warn
            console.print(f"[yellow]⚠[/yellow] [dim]Could not create config backup: {e}[/dim]")

    def _cleanup_old_backups(self, days: int = 7) -> None:
        """Delete config backups older than specified number of days.

        Args:
            days: Number of days to keep backups (default: 7)
        """
        from datetime import datetime, timedelta

        if not self.config_dir.exists():
            return

        cutoff_date = datetime.now() - timedelta(days=days)

        # Find all backup files
        backup_pattern = "config.json.*"
        for backup_file in self.config_dir.glob(backup_pattern):
            # Skip the main config file
            if backup_file.name == "config.json":
                continue

            try:
                # Get file modification time
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)

                # Delete if older than cutoff
                if mtime < cutoff_date:
                    backup_file.unlink()
            except Exception:
                # Ignore errors when cleaning up backups
                pass

    def _is_old_format(self) -> bool:
        """Check if config.json is in old format (contains 'jira' key).

        Returns:
            True if old format (single config.json with 'jira' section)
            False if new format (split into 4 files) or no config exists
        """
        if not self.config_file.exists():
            return False

        try:
            with open(self.config_file, "r") as f:
                data = json.load(f)
            # Old format has 'jira' key directly in config.json
            return "jira" in data
        except Exception:
            # If we can't read the file, assume old format for safety
            return True

    def _load_backend_config(self) -> Optional["JiraBackendConfig"]:
        """Load JIRA backend configuration from backends/jira.json.

        Returns:
            JiraBackendConfig object with defaults if file doesn't exist
        """
        from .models import JiraBackendConfig, JiraTransitionConfig

        backends_dir = self.config_dir / "backends"
        backend_file = backends_dir / "jira.json"

        if not backend_file.exists():
            # Return default backend config
            return JiraBackendConfig(
                url="https://jira.example.com",
                user="",
                transitions={
                    "on_start": JiraTransitionConfig(
                        from_status=["New", "To Do"],
                        to="In Progress",
                        prompt=False,
                    ),
                    "on_complete": JiraTransitionConfig(
                        from_status=["In Progress"],
                        to="",
                        prompt=True,
                    ),
                },
            )

        try:
            with open(backend_file, "r") as f:
                data = json.load(f)
            return JiraBackendConfig(**data)
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Failed to load backend config: {e}")
            console.print("[dim]  Using default backend configuration[/dim]")
            return JiraBackendConfig(
                url="https://jira.example.com",
                user="",
                transitions={},
            )

    def _load_organization_config(self) -> Optional["OrganizationConfig"]:
        """Load organization configuration from organization.json.

        Returns:
            OrganizationConfig object with defaults if file doesn't exist
        """
        from .models import OrganizationConfig

        org_file = self.config_dir / "organization.json"

        if not org_file.exists():
            # Return default organization config
            return OrganizationConfig()

        try:
            with open(org_file, "r") as f:
                data = json.load(f)
            return OrganizationConfig(**data)
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Failed to load organization config: {e}")
            console.print("[dim]  Using default organization configuration[/dim]")
            return OrganizationConfig()

    def _load_team_config(self) -> Optional["TeamConfig"]:
        """Load team configuration from team.json.

        Returns:
            TeamConfig object with defaults if file doesn't exist
        """
        from .models import TeamConfig

        team_file = self.config_dir / "team.json"

        if not team_file.exists():
            # Return default team config
            return TeamConfig()

        try:
            with open(team_file, "r") as f:
                data = json.load(f)
            return TeamConfig(**data)
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Failed to load team config: {e}")
            console.print("[dim]  Using default team configuration[/dim]")
            return TeamConfig()

    def _load_user_config(self) -> Optional["UserConfig"]:
        """Load user configuration from config.json (new format).

        Returns:
            UserConfig object with defaults if file doesn't exist
        """
        from .models import UserConfig, RepoConfig

        if not self.config_file.exists():
            # Return default user config
            return UserConfig(
                repos=RepoConfig(workspace=str(Path.home() / "development"))
            )

        try:
            with open(self.config_file, "r") as f:
                data = json.load(f)
            return UserConfig(**data)
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Failed to load user config: {e}")
            console.print("[dim]  Using default user configuration[/dim]")
            return UserConfig(
                repos=RepoConfig(workspace=str(Path.home() / "development"))
            )

    def _merge_jira_config(
        self,
        backend: "JiraBackendConfig",
        org: "OrganizationConfig",
        team: "TeamConfig",
    ) -> "JiraConfig":
        """Merge backend, organization, and team configs into unified JiraConfig.

        Args:
            backend: Backend configuration
            org: Organization configuration
            team: Team configuration

        Returns:
            Merged JiraConfig object
        """
        from .models import JiraConfig

        return JiraConfig(
            # From backend
            url=backend.url,
            user=backend.user,
            transitions=backend.transitions,
            field_mappings=backend.field_mappings,
            field_cache_timestamp=backend.field_cache_timestamp,
            field_cache_auto_refresh=backend.field_cache_auto_refresh,
            field_cache_max_age_hours=backend.field_cache_max_age_hours,
            parent_field_mapping=backend.parent_field_mapping,
            # From organization
            project=org.jira_project,
            affected_version=org.jira_affected_version,
            acceptance_criteria_field=org.jira_acceptance_criteria_field,
            epic_link_field=org.jira_epic_link_field,
            filters=org.sync_filters,  # Renamed from 'filters' to 'sync_filters'
            # Use organization's workstream_field if available, fallback to team's
            workstream_field=org.jira_workstream_field or team.jira_workstream_field,
            # From team
            workstream=team.jira_workstream,
            time_tracking=team.time_tracking_enabled,
            comment_visibility_type=team.jira_comment_visibility_type,
            comment_visibility_value=team.jira_comment_visibility_value,
        )

    def _load_new_format_config(self) -> Optional[Config]:
        """Load configuration from 4 separate files (new format).

        Returns:
            Merged Config object from all 4 config files
        """
        # Load each config file
        user_config = self._load_user_config()
        backend_config = self._load_backend_config()
        org_config = self._load_organization_config()
        team_config = self._load_team_config()

        # Merge JIRA configs
        merged_jira = self._merge_jira_config(backend_config, org_config, team_config)

        # Merge agent_backend with priority: Organization > Team > User
        # Organization can enforce agent backend for all teams
        # Team can enforce agent backend for that team
        # User can only choose if org/team haven't enforced it
        agent_backend = (
            org_config.agent_backend  # Organization takes precedence
            or team_config.agent_backend  # Then team
            or "claude"  # Default to claude if not set anywhere
        )

        # Construct final Config object
        config = Config(
            jira=merged_jira,
            repos=user_config.repos,
            time_tracking=user_config.time_tracking,
            session_summary=user_config.session_summary,
            templates=user_config.templates,
            context_files=user_config.context_files,
            prompts=user_config.prompts,
            pr_template_url=user_config.pr_template_url,
            storage=user_config.storage,  # Storage backend config
            backend_config_source=user_config.backend_config_source,
            agent_backend=agent_backend,  # Merged from org/team/user hierarchy
            mock_services=user_config.mock_services,
            gcp_vertex_region=user_config.gcp_vertex_region,
            update_checker_timeout=user_config.update_checker_timeout,
        )

        # Validate configuration and show warnings
        from .validator import ConfigValidator
        validator = ConfigValidator(self.config_dir)
        validation_result = validator.validate_split_config_files()
        validator.print_validation_warnings_on_load(validation_result)

        return config

    def _migrate_to_new_format(self, config: Config) -> None:
        """Migrate from old single-file format to new 4-file format.

        Steps:
        1. Create backup of old config.json
        2. Split config into 4 files
        3. Display migration summary

        Args:
            config: Config object to migrate and save
        """
        from datetime import datetime
        import shutil

        # Check if in JSON mode - suppress output if so
        show_output = True
        try:
            from devflow.cli.utils import is_json_mode
            if is_json_mode():
                show_output = False
        except ImportError:
            pass

        if show_output:
            console.print("\n[cyan]━━━ Configuration Migration ━━━[/cyan]")
            console.print("[yellow]Migrating from old format to new 4-file format...[/yellow]")

        # STEP 1: Create backup
        backup_dir = self.config_dir / ".deprecated"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"config.json.{timestamp}"

        shutil.copy2(self.config_file, backup_file)
        if show_output:
            console.print(f"[green]✓[/green] Backed up old config to: [dim]{backup_file}[/dim]")

        # STEP 3: Split config into 4 files
        self._save_new_format_config(config)

        if show_output:
            console.print("[green]✓[/green] Migration complete! Configuration split into 4 files:")
            console.print(f"  [dim]• {self.config_file} (user preferences)[/dim]")
            console.print(f"  [dim]• {self.config_dir / 'organization.json'} (organization settings)[/dim]")
            console.print(f"  [dim]• {self.config_dir / 'team.json'} (team settings)[/dim]")
            console.print(f"  [dim]• {self.config_dir / 'backends' / 'jira.json'} (JIRA backend)[/dim]")
            console.print()

    def _save_new_format_config(self, config: Config) -> None:
        """Save configuration in new 4-file format.

        Splits Config object into:
        - config.json: User preferences (UserConfig)
        - organization.json: Organization settings (OrganizationConfig)
        - team.json: Team settings (TeamConfig)
        - backends/jira.json: JIRA backend (JiraBackendConfig)

        Args:
            config: Config object to split and save
        """
        from .models import (
            UserConfig,
            OrganizationConfig,
            TeamConfig,
            JiraBackendConfig,
        )

        # Extract user config
        user_config = UserConfig(
            backend_config_source=config.backend_config_source,
            repos=config.repos,
            time_tracking=config.time_tracking,
            session_summary=config.session_summary,
            templates=config.templates,
            context_files=config.context_files,
            prompts=config.prompts,
            pr_template_url=config.pr_template_url,
            storage=config.storage,  # Storage backend config
            mock_services=config.mock_services,
            gcp_vertex_region=config.gcp_vertex_region,
            update_checker_timeout=config.update_checker_timeout,
        )

        # Save user config (config.json)
        with open(self.config_file, "w") as f:
            json.dump(user_config.model_dump(by_alias=True, exclude_none=False), f, indent=2)

        # Extract backend config
        backend_config = JiraBackendConfig(
            url=config.jira.url,
            user=config.jira.user,
            transitions=config.jira.transitions,
            field_mappings=config.jira.field_mappings,
            field_cache_timestamp=config.jira.field_cache_timestamp,
            field_cache_auto_refresh=config.jira.field_cache_auto_refresh,
            field_cache_max_age_hours=config.jira.field_cache_max_age_hours,
            parent_field_mapping=config.jira.parent_field_mapping,
        )

        # Save backend config (backends/jira.json)
        backends_dir = self.config_dir / "backends"
        backends_dir.mkdir(exist_ok=True)

        with open(backends_dir / "jira.json", "w") as f:
            json.dump(backend_config.model_dump(by_alias=True, exclude_none=False), f, indent=2)

        # Extract organization config
        org_config = OrganizationConfig(
            jira_project=config.jira.project,
            jira_affected_version=config.jira.affected_version,
            jira_acceptance_criteria_field=config.jira.acceptance_criteria_field,
            jira_workstream_field=config.jira.workstream_field,
            jira_epic_link_field=config.jira.epic_link_field,
            sync_filters=config.jira.filters,  # Renamed from 'filters' to 'sync_filters'
        )

        # Save organization config (organization.json)
        with open(self.config_dir / "organization.json", "w") as f:
            json.dump(org_config.model_dump(by_alias=True, exclude_none=False), f, indent=2)

        # Extract team config
        team_config = TeamConfig(
            jira_workstream=config.jira.workstream,
            jira_workstream_field=config.jira.workstream_field,  # Kept for backward compat
            time_tracking_enabled=config.jira.time_tracking,
            jira_comment_visibility_type=config.jira.comment_visibility_type,
            jira_comment_visibility_value=config.jira.comment_visibility_value,
        )

        # Save team config (team.json)
        with open(self.config_dir / "team.json", "w") as f:
            json.dump(team_config.model_dump(by_alias=True, exclude_none=False), f, indent=2)
