"""Version parsing and comparison utilities for release management."""

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class Version:
    """Semantic version representation."""

    major: int
    minor: int
    patch: int
    dev: bool = False

    @classmethod
    def parse(cls, version_string: str) -> "Version":
        """Parse a semantic version string.

        Args:
            version_string: Version string (e.g., "1.0.0", "1.2.0-dev")

        Returns:
            Parsed Version object

        Raises:
            ValueError: If version string is invalid
        """
        # Strip whitespace first
        version_string = version_string.strip()

        # Match X.Y.Z or X.Y.Z-dev
        pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-dev)?$"
        match = re.match(pattern, version_string)

        if not match:
            raise ValueError(
                f"Invalid version format: {version_string}. "
                "Expected format: X.Y.Z or X.Y.Z-dev"
            )

        major, minor, patch = match.groups()
        dev = version_string.endswith("-dev")

        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            dev=dev
        )

    def __str__(self) -> str:
        """Get string representation."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.dev:
            version += "-dev"
        return version

    def without_dev(self) -> "Version":
        """Return a copy of this version without the -dev suffix."""
        return Version(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            dev=False
        )

    def bump_major(self) -> "Version":
        """Return a new version with major bumped, minor and patch reset to 0."""
        return Version(major=self.major + 1, minor=0, patch=0, dev=False)

    def bump_minor(self) -> "Version":
        """Return a new version with minor bumped, patch reset to 0."""
        return Version(major=self.major, minor=self.minor + 1, patch=0, dev=False)

    def bump_patch(self) -> "Version":
        """Return a new version with patch bumped."""
        return Version(major=self.major, minor=self.minor, patch=self.patch + 1, dev=False)

    def with_dev(self) -> "Version":
        """Return a copy of this version with the -dev suffix."""
        return Version(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            dev=True
        )


def detect_release_type(current: Version, target: Version) -> str:
    """Detect the type of release from version comparison.

    Args:
        current: Current version
        target: Target release version

    Returns:
        Release type: "major", "minor", or "patch"

    Raises:
        ValueError: If version progression is invalid
    """
    # Remove -dev suffix for comparison
    curr = current.without_dev()

    # Validate target doesn't have -dev
    if target.dev:
        raise ValueError(f"Target version cannot have -dev suffix: {target}")

    # Special case: If current has -dev suffix and target equals current without -dev,
    # this is completing the current development cycle
    if current.dev and str(curr) == str(target):
        # Determine release type from version numbers
        if target.patch > 0:
            return "patch"
        elif target.minor > 0:
            return "minor"
        else:
            return "major"

    # Major release
    if target.major > curr.major:
        # Ensure minor and patch are 0 for major release
        if target.minor != 0 or target.patch != 0:
            raise ValueError(
                f"Major release should be {target.major}.0.0, not {target}"
            )
        return "major"

    # Minor release
    if target.major == curr.major and target.minor > curr.minor:
        # Ensure patch is 0 for minor release
        if target.patch != 0:
            raise ValueError(
                f"Minor release should be {target.major}.{target.minor}.0, not {target}"
            )
        return "minor"

    # Patch release
    if (target.major == curr.major and
        target.minor == curr.minor and
        target.patch > curr.patch):
        return "patch"

    # Invalid progression
    raise ValueError(
        f"Invalid version progression from {curr} to {target}. "
        f"Target must be greater than current version."
    )


def get_next_dev_version(release_version: Version, release_type: str) -> Version:
    """Get the next development version after a release.

    For release branches: bump patch and add -dev (e.g., 1.0.0 -> 1.0.1-dev)
    For main branch after minor/major: bump minor and add -dev (e.g., 1.0.0 -> 1.1.0-dev)

    Args:
        release_version: The version being released
        release_type: Type of release ("major", "minor", "patch")

    Returns:
        Next development version
    """
    if release_type == "patch":
        # For patch releases, bump patch for next dev version
        return release_version.bump_patch().with_dev()
    else:
        # For minor/major releases, bump minor for main branch dev version
        return release_version.bump_minor().with_dev()


def validate_version_files(
    init_version: str,
    setup_version: str
) -> Tuple[Version, bool]:
    """Validate that version files are in sync.

    Args:
        init_version: Version from devflow/__init__.py
        setup_version: Version from setup.py

    Returns:
        Tuple of (parsed_version, versions_match)

    Raises:
        ValueError: If either version is invalid
    """
    try:
        init_v = Version.parse(init_version)
        setup_v = Version.parse(setup_version)
    except ValueError as e:
        raise ValueError(f"Invalid version format: {e}")

    versions_match = str(init_v) == str(setup_v)

    return init_v, versions_match
