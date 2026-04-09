#!/usr/bin/env python3
"""
Release Helper for DevAIFlow

This module provides automation utilities for the release skill to:
- Read and update version numbers in multiple files
- Update CHANGELOG.md with proper formatting
- Validate version consistency
- Calculate next version based on release type
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, List


class ReleaseHelper:
    """Helper class for managing DevAIFlow releases."""

    def __init__(self, repo_path: str = "."):
        """Initialize ReleaseHelper with repository path."""
        self.repo_path = Path(repo_path)
        self.pyproject_path = self.repo_path / "pyproject.toml"
        self.init_path = self.repo_path / "devflow" / "__init__.py"
        self.changelog_path = self.repo_path / "CHANGELOG.md"

    def get_current_version(self) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Get current version from both files.

        Returns:
            Tuple of (pyproject_version, init_version, versions_match)
        """
        pyproject_version = self._read_version_from_pyproject()
        init_version = self._read_version_from_init()
        versions_match = pyproject_version == init_version

        return pyproject_version, init_version, versions_match

    def _read_version_from_pyproject(self) -> Optional[str]:
        """Read version from pyproject.toml."""
        try:
            content = self.pyproject_path.read_text()
            match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
            return match.group(1) if match else None
        except Exception as e:
            print(f"Error reading pyproject.toml: {e}", file=sys.stderr)
            return None

    def _read_version_from_init(self) -> Optional[str]:
        """Read version from devflow/__init__.py."""
        try:
            content = self.init_path.read_text()
            match = re.search(r'^__version__\s*=\s*"([^"]+)"', content, re.MULTILINE)
            return match.group(1) if match else None
        except Exception as e:
            print(f"Error reading __init__.py: {e}", file=sys.stderr)
            return None

    def update_version(self, new_version: str) -> bool:
        """
        Update version in both pyproject.toml and __init__.py.

        Args:
            new_version: The new version string (e.g., "1.2.0")

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update pyproject.toml
            content = self.pyproject_path.read_text()
            updated_content = re.sub(
                r'^version\s*=\s*"[^"]+"',
                f'version = "{new_version}"',
                content,
                count=1,
                flags=re.MULTILINE
            )
            self.pyproject_path.write_text(updated_content)

            # Update __init__.py
            content = self.init_path.read_text()
            updated_content = re.sub(
                r'^__version__\s*=\s*"[^"]+"',
                f'__version__ = "{new_version}"',
                content,
                count=1,
                flags=re.MULTILINE
            )
            self.init_path.write_text(updated_content)

            # Verify update
            pyproject_ver, init_ver, match = self.get_current_version()
            if pyproject_ver == new_version and init_ver == new_version and match:
                return True
            else:
                print(f"Error: Version update verification failed", file=sys.stderr)
                print(f"  pyproject.toml: {pyproject_ver}", file=sys.stderr)
                print(f"  __init__.py: {init_ver}", file=sys.stderr)
                return False

        except Exception as e:
            print(f"Error updating version: {e}", file=sys.stderr)
            return False

    def calculate_next_version(self, current_version: str, release_type: str) -> Optional[str]:
        """
        Calculate next version based on current version and release type.

        Args:
            current_version: Current version (e.g., "1.1.0-dev")
            release_type: One of "major", "minor", "patch", "test"

        Returns:
            Next version string or None if invalid
        """
        # Remove -dev or -test* suffix
        base_version = re.sub(r'-dev|-test\d*', '', current_version)

        # Parse semantic version
        match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', base_version)
        if not match:
            print(f"Error: Invalid version format: {base_version}", file=sys.stderr)
            return None

        major, minor, patch = map(int, match.groups())

        if release_type == "major":
            return f"{major + 1}.0.0"
        elif release_type == "minor":
            return f"{major}.{minor + 1}.0"
        elif release_type == "patch":
            return f"{major}.{minor}.{patch + 1}"
        elif release_type == "test":
            # For test releases, keep the base version and add -test1
            return f"{major}.{minor}.{patch}-test1"
        else:
            print(f"Error: Invalid release type: {release_type}", file=sys.stderr)
            return None

    def update_changelog(self, version: str, date: Optional[str] = None) -> bool:
        """
        Update CHANGELOG.md by moving Unreleased section to new version.

        Args:
            version: New version (e.g., "1.2.0")
            date: Release date in YYYY-MM-DD format (defaults to today)

        Returns:
            True if successful, False otherwise
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        try:
            content = self.changelog_path.read_text()

            # Check if Unreleased section exists
            if "## [Unreleased]" not in content:
                print("Warning: No [Unreleased] section found in CHANGELOG.md", file=sys.stderr)
                return False

            # Find the Unreleased section content
            unreleased_pattern = r'## \[Unreleased\]\s*(.*?)(?=## \[|$)'
            unreleased_match = re.search(unreleased_pattern, content, re.DOTALL)

            if not unreleased_match:
                print("Warning: Could not parse Unreleased section", file=sys.stderr)
                return False

            unreleased_content = unreleased_match.group(1).strip()

            # Check if there's actual content (not just empty or whitespace)
            if not unreleased_content or unreleased_content.isspace():
                print("Warning: Unreleased section is empty", file=sys.stderr)
                return False

            # Create new version section
            version_section = f"## [{version}] - {date}\n\n{unreleased_content}\n\n"

            # Replace Unreleased section with new empty one + version section
            new_content = re.sub(
                r'## \[Unreleased\]\s*.*?(?=## \[|$)',
                f"## [Unreleased]\n\n{version_section}",
                content,
                count=1,
                flags=re.DOTALL
            )

            # Update version links at the bottom
            # Find existing links section
            links_pattern = r'\[Unreleased\]: .*?\n'
            existing_unreleased_link = re.search(links_pattern, new_content)

            if existing_unreleased_link:
                # Extract repo URL from existing link
                repo_url_match = re.search(
                    r'\[Unreleased\]: (https://github\.com/[^/]+/[^/]+)/compare/v([^.]+\.[^.]+\.[^.]+)\.\.\.HEAD',
                    new_content
                )

                if repo_url_match:
                    repo_url = repo_url_match.group(1)

                    # Update Unreleased link to compare from new version
                    new_content = re.sub(
                        r'\[Unreleased\]: .*?\n',
                        f'[Unreleased]: {repo_url}/compare/v{version}...HEAD\n',
                        new_content,
                        count=1
                    )

                    # Add new version link
                    new_version_link = f'[{version}]: {repo_url}/releases/tag/v{version}\n'
                    new_content = re.sub(
                        r'(\[Unreleased\]: .*?\n)',
                        f'\\1{new_version_link}',
                        new_content,
                        count=1
                    )

            self.changelog_path.write_text(new_content)
            return True

        except Exception as e:
            print(f"Error updating CHANGELOG.md: {e}", file=sys.stderr)
            return False

    def validate_prerequisites(self, release_type: str = "regular") -> Tuple[bool, List[str]]:
        """
        Validate prerequisites for a release.

        Args:
            release_type: "regular", "hotfix", or "test"

        Returns:
            Tuple of (all_valid, list_of_errors)
        """
        errors = []

        # Check version files exist
        if not self.pyproject_path.exists():
            errors.append("pyproject.toml not found")
        if not self.init_path.exists():
            errors.append("devflow/__init__.py not found")
        if not self.changelog_path.exists():
            errors.append("CHANGELOG.md not found")

        if errors:
            return False, errors

        # Check versions match
        pyproject_ver, init_ver, match = self.get_current_version()
        if not match:
            errors.append(
                f"Version mismatch: pyproject.toml={pyproject_ver}, __init__.py={init_ver}"
            )

        # For regular releases, check CHANGELOG has Unreleased section
        if release_type == "regular":
            try:
                content = self.changelog_path.read_text()
                if "## [Unreleased]" not in content:
                    errors.append("CHANGELOG.md missing [Unreleased] section")
                else:
                    # Check if Unreleased has content
                    unreleased_pattern = r'## \[Unreleased\]\s*(.*?)(?=## \[|$)'
                    match = re.search(unreleased_pattern, content, re.DOTALL)
                    if match:
                        unreleased_content = match.group(1).strip()
                        if not unreleased_content or unreleased_content.isspace():
                            errors.append("CHANGELOG.md [Unreleased] section is empty")
            except Exception as e:
                errors.append(f"Error reading CHANGELOG.md: {e}")

        return len(errors) == 0, errors


def main():
    """CLI interface for release helper."""
    import argparse

    parser = argparse.ArgumentParser(description="DevAIFlow Release Helper")
    parser.add_argument("--repo", default=".", help="Repository path (default: current directory)")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Get version command
    subparsers.add_parser("get-version", help="Get current version from both files")

    # Update version command
    update_parser = subparsers.add_parser("update-version", help="Update version in both files")
    update_parser.add_argument("version", help="New version (e.g., 1.2.0)")

    # Calculate next version
    calc_parser = subparsers.add_parser("calc-version", help="Calculate next version")
    calc_parser.add_argument("current", help="Current version")
    calc_parser.add_argument("type", choices=["major", "minor", "patch", "test"], help="Release type")

    # Update changelog
    changelog_parser = subparsers.add_parser("update-changelog", help="Update CHANGELOG.md")
    changelog_parser.add_argument("version", help="Version to release")
    changelog_parser.add_argument("--date", help="Release date (YYYY-MM-DD, default: today)")

    # Validate prerequisites
    validate_parser = subparsers.add_parser("validate", help="Validate release prerequisites")
    validate_parser.add_argument("--type", default="regular", choices=["regular", "hotfix", "test"],
                                 help="Release type")

    args = parser.parse_args()

    helper = ReleaseHelper(args.repo)

    if args.command == "get-version":
        pyproject_ver, init_ver, match = helper.get_current_version()
        print(f"pyproject.toml: {pyproject_ver}")
        print(f"__init__.py: {init_ver}")
        print(f"Match: {match}")
        sys.exit(0 if match else 1)

    elif args.command == "update-version":
        success = helper.update_version(args.version)
        sys.exit(0 if success else 1)

    elif args.command == "calc-version":
        next_version = helper.calculate_next_version(args.current, args.type)
        if next_version:
            print(next_version)
            sys.exit(0)
        else:
            sys.exit(1)

    elif args.command == "update-changelog":
        success = helper.update_changelog(args.version, args.date)
        sys.exit(0 if success else 1)

    elif args.command == "validate":
        valid, errors = helper.validate_prerequisites(args.type)
        if valid:
            print("✓ All prerequisites validated")
            sys.exit(0)
        else:
            print("✗ Validation failed:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
