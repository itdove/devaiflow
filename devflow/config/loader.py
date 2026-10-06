"""Configuration file loading and management."""

import json
import os
import shutil
import stat
import sys
import tempfile
import uuid
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, Mapping, Optional, Tuple, Union

from pydantic import ValidationError
from rich.console import Console

from devflow.utils.paths import get_cs_home, get_cs_config_home

from .models import Config, SessionIndex

if TYPE_CHECKING:
    from .models import (
        EnterpriseConfig,
        GitHubConfig,
        JiraBackendConfig,
        JiraConfig,
        OrganizationConfig,
        TeamConfig,
        UserConfig,
    )

console = Console(stderr=True)


class ConfigLoader:
    """Load and manage configuration files."""

    CONFIG_BACKUP_RETENTION_DAYS = 7
    _CONFIG_FILE_RELATIVE_PATHS = (
        Path("config.json"),
        Path("enterprise.json"),
        Path("organization.json"),
        Path("team.json"),
        Path("backends") / "jira.json",
    )

    # Class-level flag to track if validation warnings have been shown
    _validation_warnings_shown = False

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the config loader.

        Args:
            config_dir: Directory for config files. When None, uses XDG paths:
                config files → get_cs_config_home(), session data → get_cs_home().
                When explicit, all paths use the given directory (test compat).
        """
        if config_dir is None:
            self.config_dir = get_cs_config_home()
            session_home = get_cs_home()
        else:
            self.config_dir = config_dir
            session_home = config_dir
        self.config_file = self.config_dir / "config.json"
        self.backup_dir = self.config_dir / "backups"
        self._config_lock_file = self.config_dir / ".config.json.lock"
        self._config_transaction_file = self.config_dir / ".config-save.json"
        self.sessions_file = session_home / "sessions.json"
        self.sessions_dir = session_home / "sessions"
        self.session_home = session_home

        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._recover_pending_transaction()

    def _configuration_file_paths(self) -> Tuple[Path, ...]:
        """Return all configuration files managed by the split format."""
        return tuple(self.config_dir / relative for relative in self._CONFIG_FILE_RELATIVE_PATHS)

    @contextmanager
    def _configuration_lock(self) -> Iterator[None]:
        """Serialize configuration reads and writes across DAF processes.

        The lock is kept in a separate file so replacing any configuration file
        does not invalidate the lock held by another process. Unix uses
        ``fcntl.flock`` and Windows uses ``msvcrt.locking``.
        """
        with open(self._config_lock_file, "a+") as lock_file:
            if sys.platform != "win32":
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            else:
                import msvcrt

                lock_file.seek(0, 2)
                if lock_file.tell() == 0:
                    lock_file.write(" ")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)

            try:
                yield
            finally:
                if sys.platform != "win32":
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                else:
                    import msvcrt

                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)

    def _managed_config_path(self, path: Union[str, Path]) -> Path:
        """Resolve and validate a path beneath the configured config directory."""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.config_dir / candidate

        candidate = candidate.resolve()
        config_root = self.config_dir.resolve()
        try:
            candidate.relative_to(config_root)
        except ValueError as e:
            raise ValueError(f"Configuration path must be inside {config_root}: {path}") from e
        return candidate

    def _normalize_json_files(
        self, files: Mapping[Any, Any]
    ) -> Dict[Path, Any]:
        """Normalize and validate paths supplied to the persistence helpers."""
        if not files:
            raise ValueError("At least one configuration file is required")
        return {self._managed_config_path(path): data for path, data in files.items()}

    def save_json_files(
        self, files: Mapping[Any, Any]
    ) -> Optional[Path]:
        """Safely persist one or more managed JSON configuration files.

        Files are backed up before any replacement, written through fsynced
        temporary files, and replaced as one transaction under the configuration
        lock. If a later replacement fails, every file in the transaction is
        restored to its pre-save state.

        Args:
            files: Mapping of absolute or config-directory-relative paths to
                JSON-serializable values.

        Returns:
            The backup path for ``config.json`` when it existed, or the first
            backup created for the transaction. ``None`` means no input file
            existed before the save.
        """
        normalized_files = self._normalize_json_files(files)
        with self._configuration_lock():
            self._recover_pending_transaction_locked()
            return self._persist_json_files(normalized_files, lock_held=True)

    def create_config_backup(self) -> Optional[Path]:
        """Create a recoverable snapshot of the existing split configuration.

        The snapshot is stored in ``<config_dir>/backups``. Each file uses the
        same unique snapshot identifier, so the files can be restored together.
        Backups older than :attr:`CONFIG_BACKUP_RETENTION_DAYS` are removed.

        Returns:
            The backup path for ``config.json`` or the first existing config file.
        """
        with self._configuration_lock():
            self._recover_pending_transaction_locked()
            existing_paths = [
                path for path in self._configuration_file_paths() if path.exists()
            ]
            backups = self._create_config_backups(existing_paths)
            self._cleanup_old_backups()
            return self._first_backup_path(backups)

    def _first_backup_path(self, backups: Mapping[Path, Path]) -> Optional[Path]:
        """Return the primary backup path for a transaction."""
        if self.config_file in backups:
            return backups[self.config_file]
        return next(iter(backups.values()), None)

    def _new_backup_id(self) -> str:
        """Create a collision-resistant identifier for one backup snapshot."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        return f"{timestamp}-{uuid.uuid4().hex[:12]}"

    def _backup_name(self, path: Path, backup_id: str) -> str:
        """Return a flat, readable backup name for a config-relative path."""
        relative = path.relative_to(self.config_dir)
        stem = "-".join(relative.with_suffix("").parts)
        return f"{stem}-{backup_id}{path.suffix}"

    def _copy_backup(self, source: Path, destination: Path) -> None:
        """Copy a backup file and fail rather than continuing without recovery."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        # Backups are retained by creation time, not by the source file's
        # potentially old modification time copied by ``copy2``.
        os.utime(destination, None)

        # Ensure the completed backup is pushed through the OS before the
        # original file is eligible for replacement.
        # ``fsync`` works with a read-only descriptor on supported POSIX
        # filesystems. Keep the copied mode intact so read-only configurations
        # can still be backed up safely.
        with open(destination, "rb") as backup_file:
            os.fsync(backup_file.fileno())
        self._fsync_directory(destination.parent)

    def _write_transaction_journal(
        self,
        existed_before: Mapping[Path, bool],
        backups: Mapping[Path, Path],
    ) -> None:
        """Durably record enough state to recover an interrupted save."""
        entries = []
        for target_path, existed in existed_before.items():
            backup_path = backups.get(target_path)
            entries.append(
                {
                    "target": target_path.relative_to(self.config_dir).as_posix(),
                    "existed": existed,
                    "backup": (
                        backup_path.relative_to(self.backup_dir).as_posix()
                        if backup_path
                        else None
                    ),
                }
            )

        self._atomic_write_json(
            self._config_transaction_file,
            {"version": 1, "files": entries},
        )

    def _remove_transaction_journal(self) -> None:
        """Remove the completed-save journal and persist that removal."""
        try:
            self._config_transaction_file.unlink()
        except FileNotFoundError:
            return
        self._fsync_directory(self.config_dir)

    def _recover_pending_transaction(self) -> None:
        """Recover a save interrupted after its journal was committed."""
        with self._configuration_lock():
            self._recover_pending_transaction_locked()

    def _recover_pending_transaction_locked(self) -> None:
        """Recover a pending save while the configuration lock is held."""
        if not self._config_transaction_file.exists():
            return

        try:
            with open(self._config_transaction_file, "r", encoding="utf-8") as journal_file:
                journal = json.load(journal_file)
            if journal.get("version") != 1 or not isinstance(journal.get("files"), list):
                raise ValueError("Unsupported configuration save journal")

            for entry in journal["files"]:
                if not isinstance(entry, dict):
                    raise ValueError("Invalid configuration save journal entry")
                target_path = self._managed_config_path(entry["target"])
                if entry.get("existed"):
                    backup_name = entry.get("backup")
                    if not isinstance(backup_name, str) or Path(backup_name).name != backup_name:
                        raise ValueError("Invalid configuration backup reference")
                    backup_path = self.backup_dir / backup_name
                    if not backup_path.exists():
                        raise FileNotFoundError(f"Configuration backup not found: {backup_path}")
                    self._restore_file(backup_path, target_path)
                elif target_path.exists():
                    target_path.unlink()
                    self._fsync_directory(target_path.parent)
        except Exception as e:
            raise RuntimeError(
                "An interrupted configuration save could not be recovered; "
                f"inspect backups in {self.backup_dir}"
            ) from e

        self._remove_transaction_journal()

    def _create_config_backups(self, paths: list[Path]) -> Dict[Path, Path]:
        """Back up existing files for one save transaction."""
        existing_paths = [path for path in paths if path.exists()]
        if not existing_paths:
            return {}

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_id = self._new_backup_id()
        while any(
            (self.backup_dir / self._backup_name(source, backup_id)).exists()
            for source in existing_paths
        ):
            backup_id = f"{backup_id}-{uuid.uuid4().hex[:12]}"
        backups: Dict[Path, Path] = {}
        current_backup_path: Optional[Path] = None
        try:
            for source in existing_paths:
                backup_path = self.backup_dir / self._backup_name(source, backup_id)
                current_backup_path = backup_path
                self._copy_backup(source, backup_path)
                backups[source] = backup_path
                current_backup_path = None
        except BaseException:
            for backup_path in backups.values():
                try:
                    backup_path.unlink()
                except FileNotFoundError:
                    pass
            if current_backup_path is not None:
                try:
                    current_backup_path.unlink()
                except FileNotFoundError:
                    pass
            self._fsync_directory(self.backup_dir)
            raise

        return backups

    def _fsync_directory(self, directory: Path) -> None:
        """Fsync a directory after an atomic replacement where supported."""
        if sys.platform == "win32":
            return

        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            directory_fd = os.open(directory, flags)
        except OSError:
            return

        try:
            try:
                os.fsync(directory_fd)
            except OSError:
                # Some filesystems do not support directory fsync. The file
                # itself was already fsynced and atomically replaced.
                pass
        finally:
            os.close(directory_fd)

    def _atomic_write_json(self, path: Path, data: Any) -> None:
        """Write JSON to a temporary file and atomically replace the target."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Optional[Path] = None
        original_mode: Optional[int] = None
        if path.exists():
            original_mode = stat.S_IMODE(path.stat().st_mode)

        try:
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
                json.dump(data, temporary_file, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            if original_mode is not None:
                os.chmod(temporary_path, original_mode)
            os.replace(temporary_path, path)
            temporary_path = None
            self._fsync_directory(path.parent)
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass

    def _restore_file(self, backup_path: Path, target_path: Path) -> None:
        """Restore a backup through a temporary file and atomic replacement."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Optional[Path] = None
        try:
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target_path.name}.restore.",
                suffix=".tmp",
                dir=target_path.parent,
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(file_descriptor, "wb") as temporary_file:
                with open(backup_path, "rb") as source_file:
                    shutil.copyfileobj(source_file, temporary_file)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            shutil.copystat(backup_path, temporary_path)
            os.replace(temporary_path, target_path)
            temporary_path = None
            self._fsync_directory(target_path.parent)
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass

    def _rollback_json_files(
        self,
        existed_before: Mapping[Path, bool],
        backups: Mapping[Path, Path],
    ) -> None:
        """Restore every target to its state before a failed transaction."""
        for path, existed in existed_before.items():
            if existed:
                self._restore_file(backups[path], path)
            elif path.exists():
                path.unlink()
                self._fsync_directory(path.parent)

    def _persist_json_files(
        self,
        files: Mapping[Path, Any],
        *,
        lock_held: bool = False,
    ) -> Optional[Path]:
        """Persist normalized files, optionally assuming the config lock is held."""
        def persist() -> Optional[Path]:
            # Callers that already hold the lock can enter this helper from
            # import, initialization, or migration code. Recover here as a
            # final guard against a journal created after loader construction.
            self._recover_pending_transaction_locked()
            existed_before = {path: path.exists() for path in files}
            existing_paths = [path for path, existed in existed_before.items() if existed]
            backups = self._create_config_backups(existing_paths)

            try:
                self._write_transaction_journal(existed_before, backups)
                for path, data in files.items():
                    self._atomic_write_json(path, data)
            except BaseException:
                try:
                    self._rollback_json_files(existed_before, backups)
                except BaseException as rollback_error:
                    raise RuntimeError(
                        "Configuration save failed and rollback was unsuccessful; "
                        f"recover files from {self.backup_dir}"
                    ) from rollback_error
                try:
                    self._remove_transaction_journal()
                except BaseException as journal_error:
                    raise RuntimeError(
                        "Configuration save rolled back but its recovery journal "
                        f"could not be removed; inspect {self._config_transaction_file}"
                    ) from journal_error
                raise

            self._remove_transaction_journal()
            self._cleanup_old_backups()
            return self._first_backup_path(backups)

        if lock_held:
            return persist()
        with self._configuration_lock():
            return persist()

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
        with self._configuration_lock():
            self._recover_pending_transaction_locked()
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
        """Load configuration from legacy config.json or split files.

        Automatically detects format:
        - Old format: Single config.json with 'jira' section (backward compatible)
        - New format: Split into config.json, enterprise.json,
          organization.json, team.json, and backends/jira.json

        Args:
            validate: If True, validate config against schema before loading (default: True)
                     Set to False to skip validation (useful for migration/repair scenarios)

        Returns:
            Config object if file exists, None otherwise

        Raises:
            ValueError: If config file is invalid or validation fails
        """
        with self._configuration_lock():
            self._recover_pending_transaction_locked()
            if not self.config_file.exists():
                return None

            # Detect format and route to the appropriate loader while holding
            # the writer lock. This prevents a reader from observing a mixed
            # set of split files during a multi-file save.
            if self._is_old_format():
                # OLD FORMAT: Load from single config.json
                return self._load_old_format_config(validate)

            # NEW FORMAT: Load from the managed split files
            return self._load_new_format_config(lock_held=True)

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

            # Note: Old format validation removed - migrate to new 5-file format
            # Use validate_split_config_files() after migration

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

    def save_config(
        self,
        config: Config,
        validate: bool = True,
        additional_files: Optional[Mapping[Any, Any]] = None,
    ) -> Optional[Path]:
        """Save configuration (triggers migration from old to new format if needed).

        On first save after upgrade:
        - Detects old format
        - Creates a centralized recoverable backup
        - Splits config into the managed files (config.json, enterprise.json,
          organization.json, team.json, and backends/jira.json)

        On subsequent saves:
        - Saves to appropriate format (old or new)

        Args:
            config: Config object to save
            validate: If True, validate config before saving (default: True)
                     Set to False to skip validation (use with caution)
            additional_files: Optional managed JSON files to include in the same
                locked transaction. This is used by editors that maintain
                fields outside the merged ``Config`` model.

        Raises:
            ValueError: If validation fails (when validate=True)

        Returns:
            The backup path created for the save, or ``None`` when no existing
            configuration file needed a backup.
        """
        # Validate before saving (prevent writing invalid configs)
        if validate:
            config_dict = config.model_dump(by_alias=True, exclude_none=False)
            is_valid, error_message = self.validate_config_dict(config_dict)
            if not is_valid:
                raise ValueError(f"Cannot save invalid configuration:\n{error_message}")

        normalized_additional_files = (
            self._normalize_json_files(additional_files) if additional_files else {}
        )

        # Hold the lock while detecting the format, constructing the split
        # payload, creating backups, and replacing every file. This prevents two
        # processes from building payloads from different configuration states.
        with self._configuration_lock():
            self._recover_pending_transaction_locked()
            if self.config_file.exists() and self._is_old_format():
                # Old format exists - trigger migration to new format
                return self._migrate_to_new_format(
                    config,
                    lock_held=True,
                    additional_files=normalized_additional_files,
                )
            if self.config_file.exists():
                # Already new format - save normally
                return self._save_new_format_config(
                    config,
                    lock_held=True,
                    additional_files=normalized_additional_files,
                )

            # No config file exists - save as old format for backward
            # compatibility (tests and existing workflows expect old format by
            # default).
            return self._save_old_format_config(
                config,
                lock_held=True,
                additional_files=normalized_additional_files,
            )

    def update_last_used_workspace(self, workspace_name: str) -> None:
        """Persist only the last-used workspace preference.

        Workspace selection can happen in long-running, concurrent DAF
        processes. Updating the raw user-config field avoids serializing a
        stale full ``Config`` object over unrelated changes.

        Args:
            workspace_name: Name of the selected workspace.
        """
        def update(data: Dict[str, Any]) -> None:
            repos = data.setdefault("repos", {})
            if not isinstance(repos, dict):
                raise ValueError("Configuration field 'repos' must be an object")
            repos["last_used_workspace"] = workspace_name

        self._update_user_config_json(update)

    def update_last_used_repo(self, workspace_name: str, repository_name: str) -> None:
        """Persist only the last-used repository preference for a workspace.

        Args:
            workspace_name: Workspace containing the repository.
            repository_name: Selected repository name.
        """
        def update(data: Dict[str, Any]) -> None:
            prompts = data.setdefault("prompts", {})
            if not isinstance(prompts, dict):
                raise ValueError("Configuration field 'prompts' must be an object")
            last_used = prompts.setdefault("last_used_repo_per_workspace", {})
            if not isinstance(last_used, dict):
                raise ValueError(
                    "Configuration field 'last_used_repo_per_workspace' must be an object"
                )
            last_used[workspace_name] = repository_name

        self._update_user_config_json(update)

    def _update_user_config_json(
        self, update: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Atomically update selected fields in the user config file.

        A separate lock file keeps concurrent DAF processes from racing while
        ``config.json`` is atomically replaced. The update callback receives
        the raw user config so fields unknown to the current process remain
        untouched.
        """
        with self._configuration_lock():
            self._recover_pending_transaction_locked()
            if not self.config_file.exists():
                return

            with open(self.config_file, "r", encoding="utf-8") as config_file:
                data = json.load(config_file)
            if not isinstance(data, dict):
                raise ValueError("Configuration root must be an object")

            update(data)
            self._persist_json_files({self.config_file: data}, lock_held=True)

    def _save_old_format_config(
        self,
        config: Config,
        *,
        lock_held: bool = False,
        additional_files: Optional[Mapping[Path, Any]] = None,
    ) -> Optional[Path]:
        """Save configuration in old single-file format.

        Args:
            config: Config object to save
        """
        files: Dict[Path, Any] = {
            self.config_file: config.model_dump(by_alias=True, exclude_none=False)
        }
        if additional_files:
            files.update(additional_files)
        return self._persist_json_files(files, lock_held=lock_held)

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
        """Get the directory for a specific session.

        Args:
            session_name: Session name (primary identifier)

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
            WorkspaceDefinition,
        )

        default_config = Config(
            jira=JiraConfig(
                url="https://jira.example.com",
                project=None,
                transitions={
                    "on_start": JiraTransitionConfig.model_validate(
                        {"from": ["New", "To Do"], "to": "In Progress", "prompt": False}
                    ),
                    "on_complete": JiraTransitionConfig.model_validate(
                        {"from": ["In Progress"], "to": "", "prompt": True}
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
                workspaces=[
                    WorkspaceDefinition(
                        name="default",
                        path=str(Path.home() / "development")
                    )
                ],
                last_used_workspace="default",
                keywords={},
            ),
            time_tracking=TimeTrackingConfig(),
        )

        # Save the default config
        self.save_config(default_config)
        return default_config

    def _backup_config(self) -> Optional[Path]:
        """Compatibility wrapper for callers of the former single-file helper."""
        return self.create_config_backup()

    def _cleanup_old_backups(
        self, days: Optional[int] = None
    ) -> None:
        """Delete managed config backups older than the retention window.

        Only files produced by the centralized config backup naming scheme are
        removed. Session backups and hierarchical skill backups in nested or
        separately named locations are left untouched.
        """
        retention_days = (
            self.CONFIG_BACKUP_RETENTION_DAYS if days is None else days
        )
        if not self.backup_dir.exists():
            return

        cutoff_timestamp = (
            datetime.now(timezone.utc) - timedelta(days=retention_days)
        ).timestamp()
        managed_prefixes = (
            "config-",
            "enterprise-",
            "organization-",
            "team-",
            "backends-jira-",
        )

        for backup_file in self.backup_dir.iterdir():
            if not backup_file.is_file() or not backup_file.name.endswith(".json"):
                continue
            if not backup_file.name.startswith(managed_prefixes):
                continue
            try:
                if backup_file.stat().st_mtime < cutoff_timestamp:
                    backup_file.unlink()
            except OSError:
                # Cleanup is best effort and must not make a valid save fail.
                pass

    def _is_old_format(self) -> bool:
        """Check if config.json is in old format (contains 'jira' key).

        Returns:
            True if old format (single config.json with 'jira' section)
            False if new format (split into 5 managed files) or no config exists
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

    def _load_backend_config(self) -> "JiraBackendConfig":
        """Load JIRA backend configuration from backends/jira.json.

        Returns:
            JiraBackendConfig object with defaults if file doesn't exist
        """
        from .models import JiraBackendConfig

        backends_dir = self.config_dir / "backends"
        backend_file = backends_dir / "jira.json"

        if not backend_file.exists():
            # Return default backend config (only URL and field cache settings)
            return JiraBackendConfig(
                url="https://jira.example.com",
            )

        try:
            with open(backend_file, "r") as f:
                data = json.load(f)
            return JiraBackendConfig(**data)
        except Exception as e:
            from devflow.cli.utils import is_json_mode
            if not is_json_mode():
                console.print(f"[yellow]⚠[/yellow] Failed to load backend config: {e}")
                console.print("[dim]  Using default backend configuration[/dim]")
            return JiraBackendConfig(
                url="https://jira.example.com",
            )

    def _load_enterprise_config(self) -> "EnterpriseConfig":
        """Load enterprise configuration from enterprise.json.

        Returns:
            EnterpriseConfig object with defaults if file doesn't exist
        """
        from .models import EnterpriseConfig

        enterprise_file = self.config_dir / "enterprise.json"

        if not enterprise_file.exists():
            # Return default enterprise config
            return EnterpriseConfig()

        try:
            with open(enterprise_file, "r") as f:
                data = json.load(f)
            return EnterpriseConfig(**data)
        except Exception as e:
            from devflow.cli.utils import is_json_mode
            if not is_json_mode():
                console.print(f"[yellow]⚠[/yellow] Failed to load enterprise config: {e}")
                console.print("[dim]  Using default enterprise configuration[/dim]")
            return EnterpriseConfig()

    def _load_organization_config(self) -> "OrganizationConfig":
        """Load organization configuration from organization.json.

        Returns:
            OrganizationConfig object with defaults if file doesn't exist
        """
        from .models import OrganizationConfig, JiraTransitionConfig

        org_file = self.config_dir / "organization.json"

        if not org_file.exists():
            # Return default organization config with default workflow transitions
            return OrganizationConfig(
                transitions={
                    "on_start": JiraTransitionConfig.model_validate(
                        {"from": ["New", "To Do"], "to": "In Progress", "prompt": False}
                    ),
                    "on_complete": JiraTransitionConfig.model_validate(
                        {"from": ["In Progress"], "to": "", "prompt": True}
                    ),
                },
            )

        try:
            with open(org_file, "r") as f:
                data = json.load(f)
            return OrganizationConfig(**data)
        except Exception as e:
            from devflow.cli.utils import is_json_mode
            if not is_json_mode():
                console.print(f"[yellow]⚠[/yellow] Failed to load organization config: {e}")
                console.print("[dim]  Using default organization configuration[/dim]")
            return OrganizationConfig()


    def _load_team_config(self) -> "TeamConfig":
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
            from devflow.cli.utils import is_json_mode
            if not is_json_mode():
                console.print(f"[yellow]⚠[/yellow] Failed to load team config: {e}")
                console.print("[dim]  Using default team configuration[/dim]")
            return TeamConfig()

    def _load_user_config(self) -> "UserConfig":
        """Load user configuration from config.json (new format).

        Returns:
            UserConfig object with defaults if file doesn't exist
        """
        from .models import UserConfig, RepoConfig, WorkspaceDefinition

        if not self.config_file.exists():
            # Return default user config
            return UserConfig(
                repos=RepoConfig(
                    workspaces=[
                        WorkspaceDefinition(
                            name="default",
                            path=str(Path.home() / "development"),
                        )
                    ]
                )
            )

        try:
            with open(self.config_file, "r") as f:
                data = json.load(f)
            return UserConfig(**data)
        except Exception as e:
            from devflow.cli.utils import is_json_mode
            if not is_json_mode():
                console.print(f"[yellow]⚠[/yellow] Failed to load user config: {e}")
                console.print("[dim]  Using default user configuration[/dim]")
            return UserConfig(
                repos=RepoConfig(
                    workspaces=[
                        WorkspaceDefinition(
                            name="default",
                            path=str(Path.home() / "development"),
                        )
                    ]
                )
            )

    def _deep_merge_dicts(self, base: Any, override: Any) -> Any:
        """Deep merge two dictionaries, with override values taking precedence.

        This is a generic merge utility that can be used for any backend configuration.

        Args:
            base: Base dictionary (values will be overridden)
            override: Override dictionary (values take precedence)

        Returns:
            Merged result (dict if both inputs are dicts, otherwise override value)
        """
        if not isinstance(base, dict) or not isinstance(override, dict):
            # If either is not a dict, return the override value
            return override

        result = dict(base)
        for key, override_value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(override_value, dict):
                # Both are dicts - recurse
                result[key] = self._deep_merge_dicts(result[key], override_value)
            else:
                # Override the value
                result[key] = override_value

        return result

    def _apply_backend_overrides(self, backend_dict: Dict[str, Any], overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply organization backend overrides to backend configuration.

        This is a generic method that works for any issue tracker backend (JIRA, GitHub, etc.).

        Args:
            backend_dict: Backend configuration as a dictionary
            overrides: Override configuration from organization.json

        Returns:
            Merged backend configuration dictionary
        """
        if not overrides:
            return backend_dict

        return self._deep_merge_dicts(backend_dict, overrides)

    def _merge_jira_config(
        self,
        backend: "JiraBackendConfig",
        enterprise: "EnterpriseConfig",
        org: "OrganizationConfig",
        team: "TeamConfig",
        user: "UserConfig",
    ) -> "JiraConfig":
        """Merge backend, enterprise, organization, team, and user configs into unified JiraConfig.

        Args:
            backend: Backend configuration
            enterprise: Enterprise configuration
            org: Organization configuration
            team: Team configuration
            user: User configuration

        Returns:
            Merged JiraConfig object
        """
        from .models import JiraConfig

        # Convert backend to dict and apply enterprise overrides
        backend_dict = backend.model_dump(by_alias=True, exclude_none=False)
        merged_backend_dict = self._apply_backend_overrides(backend_dict, enterprise.backend_overrides)

        # Merge templates from configuration hierarchy
        # Priority: team.json > organization.json > enterprise.json
        merged_templates = {}
        if enterprise.jira_issue_templates:
            merged_templates.update(enterprise.jira_issue_templates)
        if org.jira_issue_templates:
            merged_templates.update(org.jira_issue_templates)
        if team.jira_issue_templates:
            merged_templates.update(team.jira_issue_templates)

        # Reconstruct backend config from merged dict (to ensure type safety)
        # Note: We only override specific fields, not the entire backend object
        return JiraConfig(
            # From backend (with organization overrides applied)
            url=merged_backend_dict.get("url", backend.url),
            field_mappings=merged_backend_dict.get("field_mappings", backend.field_mappings),
            field_cache_timestamp=merged_backend_dict.get("field_cache_timestamp", backend.field_cache_timestamp),
            field_cache_auto_refresh=merged_backend_dict.get("field_cache_auto_refresh", backend.field_cache_auto_refresh),
            field_cache_max_age_hours=merged_backend_dict.get("field_cache_max_age_hours", backend.field_cache_max_age_hours),
            # From organization (workflow policies)
            transitions=org.transitions,
            parent_field_mapping=org.parent_field_mapping,
            project=org.jira_project,
            filters=org.sync_filters,  # Renamed from 'filters' to 'sync_filters'
            issue_templates=merged_templates if merged_templates else None,
            # From team
            custom_field_defaults=team.jira_custom_field_defaults,
            system_field_defaults=team.jira_system_field_defaults,
            time_tracking=team.time_tracking_enabled,
            comment_visibility_type=team.jira_comment_visibility_type,
            comment_visibility_value=team.jira_comment_visibility_value,
            # From user
            affected_version=user.jira_affected_version,
        )

    def _merge_github_config(
        self,
        enterprise: "EnterpriseConfig",
        org: "OrganizationConfig",
        team: "TeamConfig",
    ) -> "GitHubConfig":
        """Merge enterprise, organization, and team configs into unified GitHubConfig.

        Args:
            enterprise: Enterprise configuration
            org: Organization configuration
            team: Team configuration

        Returns:
            Merged GitHubConfig object
        """
        from .models import GitHubConfig

        # Merge issue types with priority: Organization > Enterprise > Default
        # Organization can override enterprise types for specific projects
        issue_types = (
            org.github_issue_types
            or enterprise.github_issue_types
            or ["bug", "enhancement", "task", "spike", "epic"]
        )

        # Merge templates from configuration hierarchy
        # Priority: team.json > organization.json > enterprise.json
        merged_templates = {}
        # Note: Enterprise doesn't have github_issue_templates yet, only jira_issue_templates
        if org.github_issue_templates:
            merged_templates.update(org.github_issue_templates)
        if team.github_issue_templates:
            merged_templates.update(team.github_issue_templates)

        # Merge default labels
        # Priority: team.json > organization.json
        merged_labels = list(org.github_default_labels)  # Start with org labels
        merged_labels.extend(team.github_default_labels)  # Add team labels

        return GitHubConfig(
            repository=org.github_repository,
            default_labels=merged_labels,
            auto_close_on_complete=org.github_auto_close_on_complete,
            issue_templates=merged_templates if merged_templates else None,
            issue_types=issue_types,
        )

    def _load_new_format_config(self, lock_held: bool = False) -> Config:
        """Load configuration from 5 separate files (new format).

        Returns:
            Merged Config object from all 5 config files
        """
        # Load each config file
        user_config = self._load_user_config()
        backend_config = self._load_backend_config()
        enterprise_config = self._load_enterprise_config()
        org_config = self._load_organization_config()
        team_config = self._load_team_config()

        # Merge JIRA configs
        merged_jira = self._merge_jira_config(backend_config, enterprise_config, org_config, team_config, user_config)

        # Merge GitHub configs
        merged_github = self._merge_github_config(enterprise_config, org_config, team_config)

        # Merge agent_backend with priority: Enterprise > Team > User > default
        # Enterprise can enforce agent backend for all organizations
        # Team can enforce agent backend for that team
        # User can only choose if enterprise/team haven't enforced it
        agent_backend = (
            enterprise_config.agent_backend  # Enterprise takes highest precedence
            or team_config.agent_backend  # Then team
            or user_config.agent_backend  # Then user preference
            or "claude"  # Default to claude if not set anywhere
        )

        # Merge concurrency mode with priority: Enterprise > Team > User > default
        from .models import ConcurrencyConfig
        concurrency_mode = (
            enterprise_config.concurrency_mode
            or team_config.concurrency_mode
            or (user_config.concurrency.mode if hasattr(user_config, 'concurrency') else None)
            or "strict"
        )
        user_concurrency = user_config.concurrency if hasattr(user_config, 'concurrency') else ConcurrencyConfig()
        merged_concurrency = ConcurrencyConfig(
            mode=concurrency_mode,
            auto_clone_path=user_concurrency.auto_clone_path,
            cleanup_on_complete=user_concurrency.cleanup_on_complete,
        )

        # Merge model_provider with priority: Enterprise > Organization > Team > User
        # Enterprise can enforce model provider for compliance/cost control (company-wide)
        # Organization can enforce model provider if enterprise hasn't (project-specific budgets)
        # Team can enforce model provider if enterprise/org haven't enforced it
        # User can only choose if enterprise/org/team haven't enforced it
        from .models import ModelProviderConfig
        model_provider = (
            enterprise_config.model_provider  # Enterprise takes highest precedence
            or org_config.model_provider      # Then organization (project-specific)
            or team_config.model_provider     # Then team
            or user_config.model_provider     # Then user
            or ModelProviderConfig()          # Default if not set anywhere
        )

        # Merge per-backend model settings, allowing higher levels to override
        # individual values while preserving unspecified lower-level values.
        from .models import AgentModelConfig
        agent_models: Dict[str, AgentModelConfig] = {}
        for source in (
            user_config.agent_models,
            team_config.agent_models or {},
            org_config.agent_models or {},
            enterprise_config.agent_models or {},
        ):
            for backend, settings in source.items():
                current = agent_models.get(backend, AgentModelConfig())
                agent_models[backend] = AgentModelConfig(
                    **{**current.model_dump(), **settings.model_dump(exclude_none=True)}
                )

        # Construct final Config object
        config = Config(
            jira=merged_jira,
            github=merged_github,
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
            agent=user_config.agent,
            mock_services=user_config.mock_services,
            model_provider=model_provider,  # Merged from user/team/org/enterprise hierarchy (user takes priority)
            gcp_vertex_region=user_config.gcp_vertex_region,
            update_checker_timeout=user_config.update_checker_timeout,
            concurrency=merged_concurrency,  # Merged from enterprise/team/user hierarchy
            agent_models=agent_models,
        )

        # Auto-migrate hierarchical_config_source from organization.json to config.json
        # This was moved in v3.0 to enable better bootstrap workflow (#314)
        if org_config.hierarchical_config_source and not user_config.repos.hierarchical_config_source:
            # Read and update both files under the same lock as the atomic
            # transaction. Re-read the source while holding the lock so a
            # concurrent writer cannot be overwritten by a stale migration.
            migrated_source: Optional[str] = None
            lock_context = nullcontext() if lock_held else self._configuration_lock()
            with lock_context:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    user_config_data = json.load(f)

                org_config_path = self.config_dir / "organization.json"
                org_data: Dict[str, Any] = {}
                if org_config_path.exists():
                    with open(org_config_path, "r", encoding="utf-8") as f:
                        loaded_org_data = json.load(f)
                    if isinstance(loaded_org_data, dict):
                        org_data = loaded_org_data

                current_user_repos = user_config_data.get("repos", {})
                current_source = org_data.get("hierarchical_config_source")
                if (
                    isinstance(current_user_repos, dict)
                    and isinstance(current_source, str)
                    and current_source
                    and not current_user_repos.get("hierarchical_config_source")
                ):
                    current_user_repos["hierarchical_config_source"] = current_source
                    files_to_update: Dict[Path, Any] = {
                        self.config_file: user_config_data,
                    }
                    org_data.pop("hierarchical_config_source", None)
                    files_to_update[org_config_path] = org_data

                    # The migration is a configuration save too: create
                    # backups for every file it changes and replace both files
                    # atomically.
                    self._persist_json_files(files_to_update, lock_held=True)
                    migrated_source = current_source

            if migrated_source:
                config.repos.hierarchical_config_source = migrated_source
                console.print(
                    "[cyan]ℹ Migrated hierarchical_config_source from "
                    "organization.json to config.json[/cyan]"
                )

        # Validate configuration and show warnings (only once per command execution)
        from .validator import ConfigValidator
        validator = ConfigValidator(self.config_dir)
        validation_result = validator.validate_split_config_files()

        # Only show warnings once per command execution to avoid spam
        if not ConfigLoader._validation_warnings_shown:
            validator.print_validation_warnings_on_load(validation_result)
            ConfigLoader._validation_warnings_shown = True

        return config

    def _migrate_to_new_format(
        self,
        config: Config,
        *,
        lock_held: bool = False,
        additional_files: Optional[Mapping[Path, Any]] = None,
    ) -> Optional[Path]:
        """Migrate from old single-file format to new split format.

        Steps:
        1. Create backup of old config.json
        2. Split config into the managed configuration files
        3. Display migration summary

        Args:
            config: Config object to migrate and save
        """
        # Check if in JSON mode - suppress output if so
        show_output = True

        # Check for --json flag in sys.argv first (most reliable)
        if "--json" in sys.argv:
            show_output = False
        else:
            # Also try is_json_mode() as a backup
            try:
                from devflow.cli.utils import is_json_mode
                if is_json_mode():
                    show_output = False
            except ImportError:
                pass

        if show_output:
            console.print("\n[cyan]━━━ Configuration Migration ━━━[/cyan]")
            console.print("[yellow]Migrating from old format to new split format...[/yellow]")

        # The split-format save creates one centralized snapshot of every
        # existing file before replacing any of them.
        backup_file = self._save_new_format_config(
            config,
            lock_held=lock_held,
            additional_files=additional_files,
        )
        if show_output:
            if backup_file:
                console.print(
                    f"[green]✓[/green] Backed up existing config to: [dim]{backup_file}[/dim]"
                )
            else:
                console.print("[green]✓[/green] No existing configuration backup was needed")

        if show_output:
            console.print("[green]✓[/green] Migration complete! Configuration split into 5 files:")
            console.print(f"  [dim]• {self.config_file} (user preferences)[/dim]")
            console.print(f"  [dim]• {self.config_dir / 'enterprise.json'} (enterprise settings)[/dim]")
            console.print(f"  [dim]• {self.config_dir / 'organization.json'} (organization settings)[/dim]")
            console.print(f"  [dim]• {self.config_dir / 'team.json'} (team settings)[/dim]")
            console.print(f"  [dim]• {self.config_dir / 'backends' / 'jira.json'} (JIRA backend)[/dim]")
            console.print()

        return backup_file

    def _save_new_format_config(
        self,
        config: Config,
        *,
        lock_held: bool = False,
        additional_files: Optional[Mapping[Path, Any]] = None,
    ) -> Optional[Path]:
        """Save configuration in new 5-file format.

        Splits Config object into:
        - config.json: User preferences (UserConfig)
        - enterprise.json: Enterprise settings (EnterpriseConfig)
        - organization.json: Organization settings (OrganizationConfig)
        - team.json: Team settings (TeamConfig)
        - backends/jira.json: JIRA backend (JiraBackendConfig)

        Args:
            config: Config object to split and save
        """
        from .models import (
            UserConfig,
            EnterpriseConfig,
            OrganizationConfig,
            TeamConfig,
            JiraBackendConfig,
            ModelProviderConfig,
        )

        # Check if model_provider is enforced by enterprise, organization, or team
        # If enforced, don't save it in user config (prevent user override)
        enterprise_config = self._load_enterprise_config()
        organization_config = self._load_organization_config()
        team_config = self._load_team_config()
        user_model_provider: Optional[ModelProviderConfig] = config.model_provider
        if enterprise_config.model_provider or organization_config.model_provider or team_config.model_provider:
            # Model provider is enforced - don't save user override
            user_model_provider = None

        # Check if agent_backend is enforced by enterprise or team
        # If enforced, don't save it in user config (prevent user override)
        user_agent_backend: Optional[str] = config.agent_backend
        if enterprise_config.agent_backend or team_config.agent_backend:
            # agent_backend is enforced - don't save user override
            user_agent_backend = None

        # Extract user config
        user_config = UserConfig(
            agent_backend=user_agent_backend,  # User's agent backend choice (only if not enforced)
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
            model_provider=user_model_provider,  # Model provider profiles (only if not enforced)
            agent=config.agent,
            gcp_vertex_region=config.gcp_vertex_region,
            update_checker_timeout=config.update_checker_timeout,
            jira_affected_version=config.jira.affected_version,
            concurrency=config.concurrency,
            agent_models=config.agent_models,
        )

        # Extract backend config (only API metadata and technical settings)
        backend_config = JiraBackendConfig(
            url=config.jira.url,
            field_mappings=config.jira.field_mappings,
            field_cache_timestamp=config.jira.field_cache_timestamp,
            field_cache_auto_refresh=config.jira.field_cache_auto_refresh,
            field_cache_max_age_hours=config.jira.field_cache_max_age_hours,
        )

        backends_dir = self.config_dir / "backends"

        # Extract enterprise config — preserve existing values, never overwrite with user choices
        enterprise_file = self.config_dir / "enterprise.json"
        existing_enterprise_data = {}
        if enterprise_file.exists():
            try:
                with open(enterprise_file, "r") as f:
                    existing_enterprise_data = json.load(f)
            except Exception:
                pass

        enterprise_config_to_save = EnterpriseConfig(
            agent_backend=existing_enterprise_data.get("agent_backend"),
            backend_overrides=existing_enterprise_data.get("backend_overrides"),
            agent_models=existing_enterprise_data.get("agent_models"),
            model_provider=existing_enterprise_data.get("model_provider"),
        )

        # Extract organization config (workflow policies and project settings)
        org_config = OrganizationConfig(
            jira_project=config.jira.project,
            transitions=config.jira.transitions,
            parent_field_mapping=config.jira.parent_field_mapping,
            sync_filters=config.jira.filters,  # Renamed from 'filters' to 'sync_filters'
            status_grouping_field=None,  # Preserve existing if file exists
            status_totals_field=None,  # Preserve existing if file exists
            hierarchical_config_source=None,  # Preserve existing if file exists
            agent_models=None,
        )

        # If organization.json exists, preserve status fields and hierarchical_config_source
        org_file = self.config_dir / "organization.json"
        if org_file.exists():
            try:
                with open(org_file, "r") as f:
                    existing_data = json.load(f)
                if "status_grouping_field" in existing_data:
                    org_config.status_grouping_field = existing_data["status_grouping_field"]
                if "status_totals_field" in existing_data:
                    org_config.status_totals_field = existing_data["status_totals_field"]
                if "hierarchical_config_source" in existing_data:
                    org_config.hierarchical_config_source = existing_data["hierarchical_config_source"]
                if "agent_models" in existing_data:
                    org_config.agent_models = existing_data["agent_models"]
                if "model_provider" in existing_data:
                    org_config.model_provider = existing_data["model_provider"]
            except Exception:
                pass  # Ignore errors, will use default

        # Extract team config
        team_config = TeamConfig(
            jira_custom_field_defaults=config.jira.custom_field_defaults,
            jira_system_field_defaults=config.jira.system_field_defaults,
            time_tracking_enabled=config.jira.time_tracking,
            jira_comment_visibility_type=config.jira.comment_visibility_type,
            jira_comment_visibility_value=config.jira.comment_visibility_value,
            agent_models=None,
            model_provider=None,
        )

        team_file = self.config_dir / "team.json"
        if team_file.exists():
            try:
                with open(team_file, "r") as f:
                    existing_team_data = json.load(f)
                if "model_provider" in existing_team_data:
                    team_config.model_provider = existing_team_data["model_provider"]
            except Exception:
                pass

        files: Dict[Path, Any] = {
            self.config_file: user_config.model_dump(
                by_alias=True, exclude_none=False
            ),
            backends_dir / "jira.json": backend_config.model_dump(
                by_alias=True, exclude_none=False
            ),
            self.config_dir / "enterprise.json": enterprise_config_to_save.model_dump(
                by_alias=True, exclude_none=False
            ),
            self.config_dir / "organization.json": org_config.model_dump(
                by_alias=True, exclude_none=False
            ),
            self.config_dir / "team.json": team_config.model_dump(
                by_alias=True, exclude_none=False
            ),
        }
        if additional_files:
            files.update(additional_files)

        return self._persist_json_files(files, lock_held=lock_held)
