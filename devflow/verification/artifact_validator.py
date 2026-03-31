"""Artifact validator for feature verification.

Validates that required files exist and are substantial (not empty stubs).
"""

from pathlib import Path
from typing import List, Optional, Tuple


class ArtifactValidator:
    """Validate required files exist."""

    def __init__(self, project_path: str):
        """Initialize the artifact validator.

        Args:
            project_path: Path to the project directory
        """
        self.project_path = Path(project_path)

    def extract_artifacts_from_criteria(self, criteria: List[str]) -> List[str]:
        """Extract file/artifact names from acceptance criteria.

        Looks for patterns like:
        - "Create X.py file"
        - "Update docs/api.md"
        - "Add test_feature.py"

        Args:
            criteria: List of acceptance criteria strings

        Returns:
            List of potential file paths mentioned in criteria
        """
        import re

        artifacts = []

        # Common file extension patterns
        file_patterns = [
            r'(\w+\.(?:py|js|ts|jsx|tsx|go|rs|java|cpp|h|md|txt|json|yaml|yml|toml))',
            r'(\w+/[\w/]+\.(?:py|js|ts|jsx|tsx|go|rs|java|cpp|h|md|txt|json|yaml|yml|toml))',
        ]

        for criterion in criteria:
            for pattern in file_patterns:
                matches = re.findall(pattern, criterion, re.IGNORECASE)
                artifacts.extend(matches)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(artifacts))

    def validate_artifact(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Validate that a file exists and is substantial.

        Args:
            file_path: Relative or absolute file path

        Returns:
            Tuple of (valid: bool, note: Optional[str])
        """
        # Try both as absolute and relative to project
        paths_to_check = [
            Path(file_path),
            self.project_path / file_path,
        ]

        for path in paths_to_check:
            if path.exists() and path.is_file():
                # Check file size (should be > 10 bytes to not be a stub)
                size = path.stat().st_size

                if size == 0:
                    return False, f"File exists but is empty"
                elif size < 10:
                    return False, f"File exists but appears to be a stub ({size} bytes)"
                else:
                    # Count lines for better context
                    try:
                        with open(path, 'r') as f:
                            lines = len(f.readlines())
                        return True, f"{lines} lines"
                    except (UnicodeDecodeError, PermissionError):
                        # Binary file or no permission
                        return True, f"{size} bytes"

        return False, "File not found"

    def validate_artifacts(self, required_files: List[str]) -> Tuple[List[str], List[str]]:
        """Validate multiple artifacts.

        Args:
            required_files: List of file paths to validate

        Returns:
            Tuple of (validated_files: List[str], missing_files: List[str])
        """
        validated = []
        missing = []

        for file_path in required_files:
            valid, note = self.validate_artifact(file_path)

            if valid:
                validated.append(f"{file_path} ({note})")
            else:
                missing.append(f"{file_path} ({note})")

        return validated, missing
