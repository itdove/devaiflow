"""Feature orchestration storage backend.

Handles persistence of feature orchestrations to disk.
Storage structure:
    $DEVAIFLOW_HOME/
    ├── features.json              # Index of all features
    └── features/
        └── <feature-name>/
            ├── metadata.json      # FeatureOrchestration data
            ├── state.md           # Current state (human-readable)
            ├── progress.md        # Session completion log
            └── verification/
                ├── <session-1>.md # Verification reports per session
                ├── <session-2>.md
                └── <session-3>.md
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from devflow.config.models import FeatureIndex, FeatureOrchestration, VerificationResult
from devflow.utils import get_cs_home


class FeatureStorage:
    """Storage backend for feature orchestrations."""

    def __init__(self, features_dir: Optional[Path] = None, features_file: Optional[Path] = None):
        """Initialize feature storage.

        Args:
            features_dir: Directory for feature data (defaults to $DEVAIFLOW_HOME/features)
            features_file: Path to features index (defaults to $DEVAIFLOW_HOME/features.json)
        """
        devaiflow_home = get_cs_home()

        if features_dir is None:
            self.features_dir = devaiflow_home / "features"
        else:
            self.features_dir = features_dir

        if features_file is None:
            self.features_file = devaiflow_home / "features.json"
        else:
            self.features_file = features_file

        # Create directories if they don't exist
        self.features_dir.mkdir(parents=True, exist_ok=True)

    def load_index(self) -> FeatureIndex:
        """Load the feature index.

        Returns:
            FeatureIndex object (empty if no features exist)
        """
        if not self.features_file.exists():
            return FeatureIndex()

        try:
            with open(self.features_file, "r") as f:
                data = json.load(f)
                return FeatureIndex(**data)
        except (json.JSONDecodeError, ValueError) as e:
            # If index is corrupted, return empty index
            # Log the error but don't fail
            print(f"Warning: Failed to load features index: {e}")
            return FeatureIndex()

    def save_index(self, index: FeatureIndex) -> None:
        """Save the feature index.

        Args:
            index: FeatureIndex object to save
        """
        data = index.model_dump(mode="json")

        # Write atomically
        temp_file = self.features_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

        # Atomic rename
        temp_file.replace(self.features_file)

    def load_feature_metadata(self, feature_name: str) -> Optional[FeatureOrchestration]:
        """Load feature metadata from storage.

        Args:
            feature_name: Feature name

        Returns:
            FeatureOrchestration or None if not found
        """
        feature_dir = self.get_feature_dir(feature_name)
        metadata_file = feature_dir / "metadata.json"

        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file, "r") as f:
                data = json.load(f)
                return FeatureOrchestration(**data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Failed to load feature metadata for '{feature_name}': {e}")
            return None

    def save_feature_metadata(self, feature: FeatureOrchestration) -> None:
        """Save feature metadata to storage.

        Args:
            feature: FeatureOrchestration object to save
        """
        feature_dir = self.get_feature_dir(feature.name)
        feature_dir.mkdir(parents=True, exist_ok=True)

        metadata_file = feature_dir / "metadata.json"
        data = feature.model_dump(mode="json")

        # Write atomically
        temp_file = metadata_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2, default=str)

        temp_file.replace(metadata_file)

    def get_feature_dir(self, feature_name: str) -> Path:
        """Get the directory path for feature data.

        Args:
            feature_name: Feature name

        Returns:
            Path to feature directory
        """
        return self.features_dir / feature_name

    def get_verification_dir(self, feature_name: str) -> Path:
        """Get the directory path for verification reports.

        Args:
            feature_name: Feature name

        Returns:
            Path to verification directory
        """
        verification_dir = self.get_feature_dir(feature_name) / "verification"
        verification_dir.mkdir(parents=True, exist_ok=True)
        return verification_dir

    def save_verification_report(
        self, feature_name: str, session_name: str, report_content: str
    ) -> Path:
        """Save a verification report for a session.

        Args:
            feature_name: Feature name
            session_name: Session name
            report_content: Markdown content for the report

        Returns:
            Path to saved verification report
        """
        verification_dir = self.get_verification_dir(feature_name)
        report_file = verification_dir / f"{session_name}.md"

        with open(report_file, "w") as f:
            f.write(report_content)

        return report_file

    def load_verification_report(self, feature_name: str, session_name: str) -> Optional[str]:
        """Load a verification report for a session.

        Args:
            feature_name: Feature name
            session_name: Session name

        Returns:
            Report content or None if not found
        """
        verification_dir = self.get_verification_dir(feature_name)
        report_file = verification_dir / f"{session_name}.md"

        if not report_file.exists():
            return None

        with open(report_file, "r") as f:
            return f.read()

    def save_state_file(self, feature_name: str, state_content: str) -> Path:
        """Save the STATE.md file for a feature.

        Args:
            feature_name: Feature name
            state_content: Markdown content for state file

        Returns:
            Path to saved state file
        """
        feature_dir = self.get_feature_dir(feature_name)
        state_file = feature_dir / "state.md"

        with open(state_file, "w") as f:
            f.write(state_content)

        return state_file

    def save_progress_file(self, feature_name: str, progress_content: str) -> Path:
        """Save the progress.md file for a feature.

        Args:
            feature_name: Feature name
            progress_content: Markdown content for progress log

        Returns:
            Path to saved progress file
        """
        feature_dir = self.get_feature_dir(feature_name)
        progress_file = feature_dir / "progress.md"

        # Append to existing progress
        mode = "a" if progress_file.exists() else "w"
        with open(progress_file, mode) as f:
            if mode == "a":
                f.write("\n\n" + progress_content)
            else:
                f.write(progress_content)

        return progress_file

    def delete_feature_data(self, feature_name: str) -> None:
        """Delete all data for a feature.

        Args:
            feature_name: Feature name
        """
        import shutil

        feature_dir = self.get_feature_dir(feature_name)

        if feature_dir.exists():
            shutil.rmtree(feature_dir)
