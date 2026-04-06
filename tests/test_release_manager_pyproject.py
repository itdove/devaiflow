"""Tests for ReleaseManager with pyproject.toml support."""

import re
from pathlib import Path

import pytest

from devflow.release.manager import ReleaseManager
from devflow.release.version import Version


def test_read_version_from_pyproject_toml(tmp_path):
    """Test reading version from pyproject.toml."""
    # Create test files
    init_file = tmp_path / "devflow" / "__init__.py"
    init_file.parent.mkdir(parents=True)
    init_file.write_text('__version__ = "1.2.3-dev"')

    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("""[project]
name = "devaiflow"
version = "1.2.3-dev"
""")

    # Test reading version
    manager = ReleaseManager(tmp_path)
    init_version, package_version = manager.read_current_version()

    assert init_version == "1.2.3-dev"
    assert package_version == "1.2.3-dev"


def test_read_version_fallback_to_setup_py(tmp_path):
    """Test falling back to setup.py when pyproject.toml doesn't have version."""
    # Create test files
    init_file = tmp_path / "devflow" / "__init__.py"
    init_file.parent.mkdir(parents=True)
    init_file.write_text('__version__ = "1.2.3-dev"')

    # pyproject.toml exists but has no version field
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("""[build-system]
requires = ["setuptools"]
""")

    setup_file = tmp_path / "setup.py"
    setup_file.write_text('from setuptools import setup\nsetup(version="1.2.3-dev")')

    # Test reading version
    manager = ReleaseManager(tmp_path)
    init_version, package_version = manager.read_current_version()

    assert init_version == "1.2.3-dev"
    assert package_version == "1.2.3-dev"


def test_read_version_only_setup_py(tmp_path):
    """Test reading version from setup.py when pyproject.toml doesn't exist."""
    # Create test files
    init_file = tmp_path / "devflow" / "__init__.py"
    init_file.parent.mkdir(parents=True)
    init_file.write_text('__version__ = "1.2.3-dev"')

    setup_file = tmp_path / "setup.py"
    setup_file.write_text('from setuptools import setup\nsetup(version="1.2.3-dev")')

    # Test reading version
    manager = ReleaseManager(tmp_path)
    init_version, package_version = manager.read_current_version()

    assert init_version == "1.2.3-dev"
    assert package_version == "1.2.3-dev"


def test_update_version_in_pyproject_toml(tmp_path):
    """Test updating version in pyproject.toml."""
    # Create test files
    init_file = tmp_path / "devflow" / "__init__.py"
    init_file.parent.mkdir(parents=True)
    init_file.write_text('__version__ = "1.2.3-dev"')

    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_content = """[project]
name = "devaiflow"
version = "1.2.3-dev"
description = "test"
"""
    pyproject_file.write_text(pyproject_content)

    # Update version
    manager = ReleaseManager(tmp_path)
    new_version = Version(major=2, minor=0, patch=0, dev=False)
    manager.update_version_files(new_version, dry_run=False)

    # Verify updates
    assert '__version__ = "2.0.0"' in init_file.read_text()
    assert 'version = "2.0.0"' in pyproject_file.read_text()
    # Verify other fields weren't changed
    assert 'name = "devaiflow"' in pyproject_file.read_text()
    assert 'description = "test"' in pyproject_file.read_text()


def test_update_version_in_setup_py_when_pyproject_has_no_version(tmp_path):
    """Test updating setup.py when pyproject.toml exists but has no version."""
    # Create test files
    init_file = tmp_path / "devflow" / "__init__.py"
    init_file.parent.mkdir(parents=True)
    init_file.write_text('__version__ = "1.2.3-dev"')

    # pyproject.toml exists but has no version
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("""[build-system]
requires = ["setuptools"]
""")

    setup_file = tmp_path / "setup.py"
    setup_file.write_text('from setuptools import setup\nsetup(version="1.2.3-dev")')

    # Update version
    manager = ReleaseManager(tmp_path)
    new_version = Version(major=2, minor=0, patch=0, dev=False)
    manager.update_version_files(new_version, dry_run=False)

    # Verify updates
    assert '__version__ = "2.0.0"' in init_file.read_text()
    assert 'version="2.0.0"' in setup_file.read_text()


def test_update_version_skips_empty_setup_py(tmp_path):
    """Test that empty setup.py files are skipped during update."""
    # Create test files
    init_file = tmp_path / "devflow" / "__init__.py"
    init_file.parent.mkdir(parents=True)
    init_file.write_text('__version__ = "1.2.3-dev"')

    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("""[project]
name = "devaiflow"
version = "1.2.3-dev"
""")

    # Create empty setup.py (modern format after pyproject.toml migration)
    setup_file = tmp_path / "setup.py"
    setup_file.write_text('from setuptools import setup\nsetup()')

    # Update version
    manager = ReleaseManager(tmp_path)
    new_version = Version(major=2, minor=0, patch=0, dev=False)
    manager.update_version_files(new_version, dry_run=False)

    # Verify pyproject.toml was updated
    assert 'version = "2.0.0"' in pyproject_file.read_text()
    # Verify setup.py was NOT modified (still just has setup())
    setup_content = setup_file.read_text()
    assert 'version' not in setup_content.lower() or setup_content == 'from setuptools import setup\nsetup()'


def test_error_when_no_version_files_exist(tmp_path):
    """Test error when neither pyproject.toml nor setup.py have version."""
    # Create test files
    init_file = tmp_path / "devflow" / "__init__.py"
    init_file.parent.mkdir(parents=True)
    init_file.write_text('__version__ = "1.2.3-dev"')

    # pyproject.toml exists but has no version
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("""[build-system]
requires = ["setuptools"]
""")

    # setup.py exists but has no version (empty setup())
    setup_file = tmp_path / "setup.py"
    setup_file.write_text('from setuptools import setup\nsetup()')

    # Test reading version
    manager = ReleaseManager(tmp_path)
    with pytest.raises(ValueError, match="Could not find version"):
        manager.read_current_version()


def test_error_when_setup_py_missing_and_pyproject_has_no_version(tmp_path):
    """Test error when pyproject.toml has no version and setup.py doesn't exist."""
    # Create test files
    init_file = tmp_path / "devflow" / "__init__.py"
    init_file.parent.mkdir(parents=True)
    init_file.write_text('__version__ = "1.2.3-dev"')

    # pyproject.toml exists but has no version
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text("""[build-system]
requires = ["setuptools"]
""")

    # Test reading version
    manager = ReleaseManager(tmp_path)
    with pytest.raises(FileNotFoundError, match="Package file not found"):
        manager.read_current_version()
