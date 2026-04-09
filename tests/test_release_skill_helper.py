#!/usr/bin/env python3
"""
Tests for release skill helper module.

This test suite verifies the release skill helper functionality for:
- Version reading and updating
- CHANGELOG.md management
- Version calculation
- Prerequisites validation

NOTE: These tests verify the .claude/skills/release/release_helper.py module
which is part of the release skill for DevAIFlow.
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Try to import release_helper from project skills directory
try:
    # Get project root (parent of tests directory)
    project_root = Path(__file__).parent.parent
    skills_path = project_root / ".claude" / "skills" / "release"

    sys.path.insert(0, str(skills_path))
    from release_helper import ReleaseHelper
    RELEASE_HELPER_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    RELEASE_HELPER_AVAILABLE = False
    ReleaseHelper = None

# Skip all tests if release_helper is not available
pytestmark = pytest.mark.skipif(
    not RELEASE_HELPER_AVAILABLE,
    reason="release_helper module not available (.claude/skills/release/ not found)"
)


def create_test_repo(tmp_path):
    """Create a minimal test repository structure for DevAIFlow."""
    # Create directory structure
    devflow_dir = tmp_path / "devflow"
    devflow_dir.mkdir(parents=True)

    # Create pyproject.toml
    pyproject_content = """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "devaiflow"
version = "2.1.0-dev"
description = "AI-Powered Development Workflow Manager"
"""
    (tmp_path / "pyproject.toml").write_text(pyproject_content)

    # Create __init__.py
    init_content = '''"""DevAIFlow - AI-Powered Development Workflow Manager."""

__version__ = "2.1.0-dev"
'''
    (devflow_dir / "__init__.py").write_text(init_content)

    # Create CHANGELOG.md
    changelog_content = """# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- New feature X
- New feature Y

### Fixed
- Bug fix Z

## [2.0.0] - 2026-01-01

### Added
- Initial release

[Unreleased]: https://github.com/itdove/devaiflow/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/itdove/devaiflow/releases/tag/v2.0.0
"""
    (tmp_path / "CHANGELOG.md").write_text(changelog_content)

    return tmp_path


def test_get_current_version():
    """Test getting current version from both files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_repo(tmp_path)

        helper = ReleaseHelper(tmp_path)
        pyproject_ver, init_ver, match = helper.get_current_version()

        assert pyproject_ver == "2.1.0-dev"
        assert init_ver == "2.1.0-dev"
        assert match is True


def test_version_mismatch_detection():
    """Test detection of version mismatch between files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_repo(tmp_path)

        # Manually update only one file to create mismatch
        init_path = tmp_path / "devflow" / "__init__.py"
        content = init_path.read_text()
        content = content.replace('__version__ = "2.1.0-dev"', '__version__ = "2.2.0-dev"')
        init_path.write_text(content)

        helper = ReleaseHelper(tmp_path)
        pyproject_ver, init_ver, match = helper.get_current_version()

        assert pyproject_ver == "2.1.0-dev"
        assert init_ver == "2.2.0-dev"
        assert match is False


def test_update_version():
    """Test updating version in both files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_repo(tmp_path)

        helper = ReleaseHelper(tmp_path)
        success = helper.update_version("2.2.0")

        assert success is True

        # Verify both files updated
        pyproject_ver, init_ver, match = helper.get_current_version()
        assert pyproject_ver == "2.2.0"
        assert init_ver == "2.2.0"
        assert match is True


def test_calculate_next_version_minor():
    """Test calculating next minor version."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        helper = ReleaseHelper(tmp_path)

        next_ver = helper.calculate_next_version("2.1.0-dev", "minor")
        assert next_ver == "2.2.0"


def test_calculate_next_version_major():
    """Test calculating next major version."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        helper = ReleaseHelper(tmp_path)

        next_ver = helper.calculate_next_version("2.1.0-dev", "major")
        assert next_ver == "3.0.0"


def test_calculate_next_version_patch():
    """Test calculating next patch version."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        helper = ReleaseHelper(tmp_path)

        next_ver = helper.calculate_next_version("2.1.0", "patch")
        assert next_ver == "2.1.1"


def test_calculate_next_version_test():
    """Test calculating test version."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        helper = ReleaseHelper(tmp_path)

        next_ver = helper.calculate_next_version("2.2.0-dev", "test")
        assert next_ver == "2.2.0-test1"


def test_update_changelog():
    """Test updating CHANGELOG.md."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_repo(tmp_path)

        helper = ReleaseHelper(tmp_path)
        success = helper.update_changelog("2.1.0", "2026-04-08")

        assert success is True

        # Verify CHANGELOG updated
        changelog = (tmp_path / "CHANGELOG.md").read_text()
        assert "## [2.1.0] - 2026-04-08" in changelog
        assert "### Added" in changelog
        assert "- New feature X" in changelog
        assert "[2.1.0]: https://github.com/itdove/devaiflow/releases/tag/v2.1.0" in changelog
        assert "[Unreleased]: https://github.com/itdove/devaiflow/compare/v2.1.0...HEAD" in changelog


def test_validate_prerequisites_success():
    """Test successful prerequisites validation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_repo(tmp_path)

        helper = ReleaseHelper(tmp_path)
        valid, errors = helper.validate_prerequisites("regular")

        assert valid is True
        assert len(errors) == 0


def test_validate_prerequisites_version_mismatch():
    """Test prerequisites validation detects version mismatch."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        create_test_repo(tmp_path)

        # Create version mismatch
        init_path = tmp_path / "devflow" / "__init__.py"
        content = init_path.read_text()
        content = content.replace('__version__ = "2.1.0-dev"', '__version__ = "2.2.0-dev"')
        init_path.write_text(content)

        helper = ReleaseHelper(tmp_path)
        valid, errors = helper.validate_prerequisites("regular")

        assert valid is False
        assert len(errors) > 0
        assert any("mismatch" in err.lower() for err in errors)
