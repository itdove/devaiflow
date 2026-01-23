"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from devflow.config.models import Session, SessionIndex

from .filters import SessionFilters


class StorageBackend(ABC):
    """Abstract base class for session storage backends.

    Defines the interface that all storage backends must implement.
    Allows swapping between file-based, database, or other storage mechanisms.
    """

    @abstractmethod
    def load_index(self) -> SessionIndex:
        """Load the session index.

        Returns:
            SessionIndex object (empty if no sessions exist)

        Raises:
            Exception: If loading fails
        """
        pass

    @abstractmethod
    def save_index(self, index: SessionIndex) -> None:
        """Save the session index.

        Args:
            index: SessionIndex object to save

        Raises:
            Exception: If saving fails
        """
        pass

    @abstractmethod
    def load_session_metadata(self, session_name: str) -> Optional[Dict]:
        """Load session metadata from storage.

        Args:
            session_name: Session name

        Returns:
            Dictionary of session metadata or None if not found

        Raises:
            Exception: If loading fails
        """
        pass

    @abstractmethod
    def save_session_metadata(self, session: Session) -> None:
        """Save session metadata to storage.

        Args:
            session: Session object to save

        Raises:
            Exception: If saving fails
        """
        pass

    @abstractmethod
    def delete_session_data(self, session_name: str) -> None:
        """Delete all data for a session.

        Args:
            session_name: Session name

        Raises:
            Exception: If deletion fails
        """
        pass

    @abstractmethod
    def get_session_dir(self, session_name: str) -> Path:
        """Get the directory path for session data.

        Args:
            session_name: Session name

        Returns:
            Path to session directory

        Raises:
            Exception: If directory creation fails
        """
        pass

    @abstractmethod
    def add_note(self, session: Session, note: str) -> None:
        """Add a note to a session.

        Args:
            session: Session object
            note: Note text to add

        Raises:
            Exception: If note addition fails
        """
        pass

    @abstractmethod
    def list_sessions(self, index: SessionIndex, filters: SessionFilters) -> List[Session]:
        """List sessions with optional filters.

        Args:
            index: SessionIndex to filter
            filters: Filter criteria

        Returns:
            List of Session objects matching the filters

        Raises:
            Exception: If filtering fails
        """
        pass

    @abstractmethod
    def rename_session(self, old_name: str, new_name: str, session: Session) -> None:
        """Rename a session and its associated data.

        Args:
            old_name: Current session name
            new_name: New session name
            session: Session object being renamed

        Raises:
            ValueError: If old session doesn't exist or new name already exists
            Exception: If renaming fails
        """
        pass
