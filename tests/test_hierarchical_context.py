"""Tests for hierarchical context file loading."""

from pathlib import Path
from typing import Optional

import pytest

from devflow.cli.commands.new_command import _load_hierarchical_context_files
from devflow.config.models import Config, JiraConfig, RepoConfig, RepoDetectionConfig


def _create_minimal_config():
    """Create minimal Config object for testing."""
    return Config(
        jira=JiraConfig(
            url="https://jira.example.com",
            user="test-user",
            transitions={}
        ),
        repos=RepoConfig(
            workspace="/tmp/workspace",
            detection=RepoDetectionConfig()
        )
    )


def test_load_hierarchical_context_files_with_all_files(temp_daf_home, monkeypatch):
    """Test loading all hierarchical context files when they all exist."""
    # Setup: Create all context files
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(exist_ok=True)

    (backends_dir / "JIRA.md").write_text("# JIRA Rules")
    (temp_daf_home / "ENTERPRISE.md").write_text("# Enterprise Standards")
    (temp_daf_home / "ORGANIZATION.md").write_text("# Org Standards")
    (temp_daf_home / "TEAM.md").write_text("# Team Conventions")
    (temp_daf_home / "USER.md").write_text("# My Notes")

    # Create a minimal config
    config = _create_minimal_config()

    # Execute: Load hierarchical context files
    result = _load_hierarchical_context_files(config)

    # Verify: All files are included in correct order
    assert len(result) == 5

    # Check order: backend -> enterprise -> organization -> team -> user
    assert result[0][1] == "JIRA backend integration rules"
    assert result[1][1] == "enterprise-wide policies and standards"
    assert result[2][1] == "organization coding standards"
    assert result[3][1] == "team conventions and workflows"
    assert result[4][1] == "personal notes and preferences"

    # Verify paths are absolute
    assert str(backends_dir / "JIRA.md") in result[0][0]
    assert str(temp_daf_home / "ENTERPRISE.md") in result[1][0]
    assert str(temp_daf_home / "ORGANIZATION.md") in result[2][0]
    assert str(temp_daf_home / "TEAM.md") in result[3][0]
    assert str(temp_daf_home / "USER.md") in result[4][0]


def test_load_hierarchical_context_files_with_some_files(temp_daf_home):
    """Test loading only the context files that exist."""
    # Setup: Create only backend and user context files
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(exist_ok=True)

    (backends_dir / "JIRA.md").write_text("# JIRA Rules")
    (temp_daf_home / "USER.md").write_text("# My Notes")

    # Note: ORGANIZATION.md and TEAM.md are NOT created

    # Create a minimal config
    config = _create_minimal_config()

    # Execute: Load hierarchical context files
    result = _load_hierarchical_context_files(config)

    # Verify: Only existing files are included
    assert len(result) == 2

    # Check order: backend -> user (org and team skipped)
    assert result[0][1] == "JIRA backend integration rules"
    assert result[1][1] == "personal notes and preferences"


def test_load_hierarchical_context_files_with_no_files(temp_daf_home):
    """Test loading when no hierarchical context files exist."""
    # Setup: Don't create any context files
    # Create a minimal config
    config = _create_minimal_config()

    # Execute: Load hierarchical context files
    result = _load_hierarchical_context_files(config)

    # Verify: Empty list returned
    assert len(result) == 0


def test_load_hierarchical_context_files_with_none_config(temp_daf_home):
    """Test loading when config is None (config is not required)."""
    # Setup: Create all context files
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(exist_ok=True)

    (backends_dir / "JIRA.md").write_text("# JIRA Rules")
    (temp_daf_home / "ORGANIZATION.md").write_text("# Org Standards")

    # Execute: Load with None config (function doesn't require config)
    result = _load_hierarchical_context_files(None)

    # Verify: Files are still loaded (config parameter is not used)
    assert len(result) == 2
    assert result[0][1] == "JIRA backend integration rules"
    assert result[1][1] == "organization coding standards"


def test_load_hierarchical_context_files_skips_directories(temp_daf_home):
    """Test that directories with same name as context files are skipped."""
    # Setup: Create directories instead of files
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(exist_ok=True)

    (backends_dir / "JIRA.md").mkdir(exist_ok=True)  # Directory, not file
    (temp_daf_home / "ORGANIZATION.md").mkdir(exist_ok=True)  # Directory, not file
    (temp_daf_home / "USER.md").write_text("# My Notes")  # File

    # Create a minimal config
    config = _create_minimal_config()

    # Execute: Load hierarchical context files
    result = _load_hierarchical_context_files(config)

    # Verify: Only the actual file is included
    assert len(result) == 1
    assert result[0][1] == "personal notes and preferences"


def test_load_hierarchical_context_files_order(temp_daf_home):
    """Test that files are loaded in the correct hierarchical order."""
    # Setup: Create files in reverse order to verify ordering is not filesystem-based
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(exist_ok=True)

    # Create in reverse order: USER -> TEAM -> ORGANIZATION -> ENTERPRISE -> JIRA
    (temp_daf_home / "USER.md").write_text("# User")
    (temp_daf_home / "TEAM.md").write_text("# Team")
    (temp_daf_home / "ORGANIZATION.md").write_text("# Org")
    (temp_daf_home / "ENTERPRISE.md").write_text("# Enterprise")
    (backends_dir / "JIRA.md").write_text("# JIRA")

    # Create a minimal config
    config = _create_minimal_config()

    # Execute: Load hierarchical context files
    result = _load_hierarchical_context_files(config)

    # Verify: Files are in correct order regardless of creation order
    assert len(result) == 5

    # Order must be: backend -> enterprise -> organization -> team -> user
    descriptions = [r[1] for r in result]
    assert descriptions == [
        "JIRA backend integration rules",
        "enterprise-wide policies and standards",
        "organization coding standards",
        "team conventions and workflows",
        "personal notes and preferences"
    ]


def test_load_hierarchical_context_files_backend_directory_missing(temp_daf_home):
    """Test loading when backends directory doesn't exist."""
    # Setup: Don't create backends directory
    (temp_daf_home / "ORGANIZATION.md").write_text("# Org Standards")

    # Create a minimal config
    config = _create_minimal_config()

    # Execute: Load hierarchical context files
    result = _load_hierarchical_context_files(config)

    # Verify: Only organization file is included
    assert len(result) == 1
    assert result[0][1] == "organization coding standards"


def test_load_hierarchical_context_files_returns_absolute_paths(temp_daf_home):
    """Test that returned paths are absolute, not relative."""
    # Setup: Create context files
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(exist_ok=True)

    (backends_dir / "JIRA.md").write_text("# JIRA Rules")
    (temp_daf_home / "USER.md").write_text("# My Notes")

    # Create a minimal config
    config = _create_minimal_config()

    # Execute: Load hierarchical context files
    result = _load_hierarchical_context_files(config)

    # Verify: All paths are absolute
    for path, description in result:
        assert Path(path).is_absolute()
        assert Path(path).exists()


def test_load_hierarchical_context_files_empty_files_are_loaded(temp_daf_home):
    """Test that empty context files are still loaded."""
    # Setup: Create empty context files
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(exist_ok=True)

    (backends_dir / "JIRA.md").write_text("")  # Empty file
    (temp_daf_home / "ORGANIZATION.md").write_text("")  # Empty file

    # Create a minimal config
    config = _create_minimal_config()

    # Execute: Load hierarchical context files
    result = _load_hierarchical_context_files(config)

    # Verify: Empty files are still loaded
    assert len(result) == 2
    assert result[0][1] == "JIRA backend integration rules"
    assert result[1][1] == "organization coding standards"


def test_load_hierarchical_context_files_integration_with_generate_prompt(temp_daf_home):
    """Integration test: Verify hierarchical files appear in generated prompt."""
    from devflow.cli.commands.new_command import _generate_initial_prompt

    # Setup: Create hierarchical context files
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(exist_ok=True)

    (backends_dir / "JIRA.md").write_text("# JIRA Rules")
    (temp_daf_home / "ENTERPRISE.md").write_text("# Enterprise Standards")
    (temp_daf_home / "ORGANIZATION.md").write_text("# Org Standards")
    (temp_daf_home / "TEAM.md").write_text("# Team Conventions")
    (temp_daf_home / "USER.md").write_text("# My Notes")

    # Execute: Generate initial prompt
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Test hierarchical context loading"
    )

    # Verify: Hierarchical files appear in prompt
    assert "backends/JIRA.md" in prompt
    assert "ENTERPRISE.md" in prompt
    assert "ORGANIZATION.md" in prompt
    assert "TEAM.md" in prompt
    assert "USER.md" in prompt

    # Verify descriptions are included
    assert "JIRA backend integration rules" in prompt
    assert "enterprise-wide policies and standards" in prompt
    assert "organization coding standards" in prompt
    assert "team conventions and workflows" in prompt
    assert "personal notes and preferences" in prompt


def test_load_hierarchical_context_files_integration_partial_files(temp_daf_home):
    """Integration test: Verify only existing files appear in generated prompt."""
    from devflow.cli.commands.new_command import _generate_initial_prompt

    # Setup: Create only some hierarchical context files
    backends_dir = temp_daf_home / "backends"
    backends_dir.mkdir(exist_ok=True)

    (backends_dir / "JIRA.md").write_text("# JIRA Rules")
    # Note: ORGANIZATION.md and TEAM.md are NOT created
    (temp_daf_home / "USER.md").write_text("# My Notes")

    # Execute: Generate initial prompt
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Test partial hierarchical context loading"
    )

    # Verify: Only existing files appear in prompt
    assert "backends/JIRA.md" in prompt
    assert "USER.md" in prompt

    # Verify missing files do NOT appear in prompt
    assert "ORGANIZATION.md" not in prompt
    assert "TEAM.md" not in prompt


def test_load_hierarchical_context_files_integration_no_files(temp_daf_home):
    """Integration test: Verify prompt works when no hierarchical files exist."""
    from devflow.cli.commands.new_command import _generate_initial_prompt

    # Setup: Don't create any hierarchical context files

    # Execute: Generate initial prompt
    prompt = _generate_initial_prompt(
        name="test-session",
        goal="Test with no hierarchical context"
    )

    # Verify: Prompt is generated successfully
    assert "Work on: Test with no hierarchical context" in prompt

    # Verify: Default files are still included
    assert "AGENTS.md" in prompt
    assert "CLAUDE.md" in prompt
    assert "DAF_AGENTS.md" in prompt

    # Verify: No hierarchical files appear
    assert "backends/JIRA.md" not in prompt
    assert "ORGANIZATION.md" not in prompt
    assert "TEAM.md" not in prompt
    assert "CONFIG.md" not in prompt
