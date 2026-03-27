"""Tests for hierarchical context files loading."""

import pytest
import warnings
from pathlib import Path
from devflow.utils.context_files import load_hierarchical_context_files
from devflow.utils.paths import get_cs_home


def test_load_hierarchical_context_files_empty(temp_daf_home):
    """Test loading context files when none exist."""
    # With temp_daf_home fixture, DEVAIFLOW_HOME is empty
    # Verify deprecation warning is raised
    with pytest.warns(DeprecationWarning, match="load_hierarchical_context_files\\(\\) is deprecated"):
        context_files = load_hierarchical_context_files()

    # Should return empty list when no files exist
    assert context_files == []


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_load_hierarchical_context_files_with_daf_agents(temp_daf_home):
    """Test that DAF_AGENTS.md is loaded when it exists in DEVAIFLOW_HOME."""
    cs_home = get_cs_home()

    # Create DAF_AGENTS.md
    daf_agents_path = cs_home / "DAF_AGENTS.md"
    daf_agents_path.write_text("# DAF Tool Usage Guide")

    # Load context files
    context_files = load_hierarchical_context_files()

    # Should find DAF_AGENTS.md
    assert len(context_files) == 1
    path, description = context_files[0]
    assert path == str(daf_agents_path)
    assert description == "daf tool usage guide"


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_load_hierarchical_context_files_all_files(temp_daf_home):
    """Test loading all hierarchical context files."""
    cs_home = get_cs_home()

    # Create all context files
    (cs_home / "backends").mkdir(parents=True, exist_ok=True)
    (cs_home / "backends" / "JIRA.md").write_text("# JIRA Backend")
    (cs_home / "ENTERPRISE.md").write_text("# Enterprise")
    (cs_home / "ORGANIZATION.md").write_text("# Organization")
    (cs_home / "TEAM.md").write_text("# Team")
    (cs_home / "USER.md").write_text("# User")
    (cs_home / "DAF_AGENTS.md").write_text("# DAF Agents")

    # Load context files
    context_files = load_hierarchical_context_files()

    # Should find all 6 files
    assert len(context_files) == 6

    # Verify all expected descriptions are present
    descriptions = [desc for _, desc in context_files]
    assert "JIRA backend integration rules" in descriptions
    assert "enterprise-wide policies and standards" in descriptions
    assert "organization coding standards" in descriptions
    assert "team conventions and workflows" in descriptions
    assert "personal notes and preferences" in descriptions
    assert "daf tool usage guide" in descriptions


@pytest.mark.skip(reason="DAF_AGENTS.md removed - replaced by daf-workflow skill")
def test_load_hierarchical_context_files_order(temp_daf_home):
    """Test that context files are loaded in the expected order."""
    cs_home = get_cs_home()

    # Create files in random order
    (cs_home / "USER.md").write_text("# User")
    (cs_home / "DAF_AGENTS.md").write_text("# DAF Agents")
    (cs_home / "ENTERPRISE.md").write_text("# Enterprise")

    # Load context files
    context_files = load_hierarchical_context_files()

    # Should be in hierarchical order: backends, enterprise, organization, team, user, daf_agents
    descriptions = [desc for _, desc in context_files]

    # Verify order (only the ones that exist)
    assert descriptions[0] == "enterprise-wide policies and standards"  # ENTERPRISE.md
    assert descriptions[1] == "personal notes and preferences"  # USER.md
    assert descriptions[2] == "daf tool usage guide"  # DAF_AGENTS.md


def test_load_hierarchical_context_files_skip_directories(temp_daf_home):
    """Test that directories are skipped (only files are loaded)."""
    cs_home = get_cs_home()

    # Create a directory with the same name as a context file
    (cs_home / "DAF_AGENTS.md").mkdir()
    (cs_home / "ENTERPRISE.md").write_text("# Enterprise")

    # Load context files and verify deprecation warning
    with pytest.warns(DeprecationWarning, match="load_hierarchical_context_files\\(\\) is deprecated"):
        context_files = load_hierarchical_context_files()

    # Should only find ENTERPRISE.md (DAF_AGENTS.md is a directory, not a file)
    assert len(context_files) == 1
    _, description = context_files[0]
    assert description == "enterprise-wide policies and standards"
