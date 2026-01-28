"""Tests for hierarchical context loading in daf jira new command.

After PROJ-62988, acceptance criteria requirements are documented in ORGANIZATION.md
which is loaded via the hierarchical context system, not hardcoded in the prompt.
"""

import pytest
from devflow.cli.commands.jira_new_command import _build_ticket_creation_prompt, _load_hierarchical_context_files
from devflow.config.loader import ConfigLoader


class TestLoadHierarchicalContextFiles:
    """Test the _load_hierarchical_context_files function."""

    def test_loads_enterprise_md_when_exists(self, temp_daf_home):
        """Test that ENTERPRISE.md is loaded when it exists."""
        from devflow.utils.paths import get_cs_home

        cs_home = get_cs_home()
        enterprise_file = cs_home / "ENTERPRISE.md"
        enterprise_file.write_text("# Enterprise Policy")

        result = _load_hierarchical_context_files(None)

        # Should find ENTERPRISE.md
        enterprise_entries = [r for r in result if "ENTERPRISE.md" in r[0]]
        assert len(enterprise_entries) == 1
        assert enterprise_entries[0][1] == "enterprise-wide policies and standards"

    def test_loads_organization_md_when_exists(self, temp_daf_home):
        """Test that ORGANIZATION.md is loaded when it exists."""
        from devflow.utils.paths import get_cs_home

        cs_home = get_cs_home()
        org_file = cs_home / "ORGANIZATION.md"
        org_file.write_text("# Organization Policy\n\nAcceptance criteria are required.")

        result = _load_hierarchical_context_files(None)

        # Should find ORGANIZATION.md
        org_entries = [r for r in result if "ORGANIZATION.md" in r[0]]
        assert len(org_entries) == 1
        assert org_entries[0][1] == "organization-wide policies and requirements"

    def test_loads_team_md_when_exists(self, temp_daf_home):
        """Test that TEAM.md is loaded when it exists."""
        from devflow.utils.paths import get_cs_home

        cs_home = get_cs_home()
        team_file = cs_home / "TEAM.md"
        team_file.write_text("# Team Conventions")

        result = _load_hierarchical_context_files(None)

        # Should find TEAM.md
        team_entries = [r for r in result if "TEAM.md" in r[0]]
        assert len(team_entries) == 1
        assert team_entries[0][1] == "team conventions and workflows"

    def test_loads_config_md_when_exists(self, temp_daf_home):
        """Test that USER.md is loaded when it exists."""
        from devflow.utils.paths import get_cs_home

        cs_home = get_cs_home()
        user_file = cs_home / "USER.md"
        user_file.write_text("# Personal Notes")

        result = _load_hierarchical_context_files(None)

        # Should find USER.md
        user_entries = [r for r in result if "USER.md" in r[0]]
        assert len(user_entries) == 1
        assert user_entries[0][1] == "personal notes and preferences"

    def test_loads_jira_backend_md_when_exists(self, temp_daf_home):
        """Test that backends/JIRA.md is loaded when it exists."""
        from devflow.utils.paths import get_cs_home

        cs_home = get_cs_home()
        backends_dir = cs_home / "backends"
        backends_dir.mkdir(exist_ok=True)
        jira_file = backends_dir / "JIRA.md"
        jira_file.write_text("# JIRA Integration Rules")

        result = _load_hierarchical_context_files(None)

        # Should find JIRA.md
        jira_entries = [r for r in result if "JIRA.md" in r[0]]
        assert len(jira_entries) == 1
        assert jira_entries[0][1] == "JIRA backend integration rules"

    def test_returns_empty_when_no_files_exist(self, temp_daf_home):
        """Test that empty list is returned when no hierarchical files exist."""
        result = _load_hierarchical_context_files(None)
        assert result == []

    def test_loads_multiple_files_when_they_exist(self, temp_daf_home):
        """Test that all existing files are loaded."""
        from devflow.utils.paths import get_cs_home

        cs_home = get_cs_home()
        (cs_home / "ENTERPRISE.md").write_text("# Enterprise")
        (cs_home / "ORGANIZATION.md").write_text("# Org")
        (cs_home / "TEAM.md").write_text("# Team")
        (cs_home / "USER.md").write_text("# User")

        result = _load_hierarchical_context_files(None)

        assert len(result) == 4
        paths = [r[0] for r in result]
        assert any("ENTERPRISE.md" in p for p in paths)
        assert any("ORGANIZATION.md" in p for p in paths)
        assert any("TEAM.md" in p for p in paths)
        assert any("USER.md" in p for p in paths)


class TestBuildTicketCreationPrompt:
    """Test the _build_ticket_creation_prompt function."""

    @pytest.fixture
    def mock_config(self, temp_daf_home):
        """Create a mock config for testing."""
        config_loader = ConfigLoader()
        config = config_loader.create_default_config()
        config.jira.project = "PROJ"
        config.jira.custom_field_defaults = {"workstream": "Platform"}
        config_loader.save_config(config)
        return config_loader.load_config()

    def test_includes_organization_md_in_context_files(self, mock_config, temp_daf_home):
        """Test that ORGANIZATION.md is included in context files when it exists."""
        from devflow.utils.paths import get_cs_home

        cs_home = get_cs_home()
        org_file = cs_home / "ORGANIZATION.md"
        org_file.write_text("# Organization Policy")

        prompt = _build_ticket_creation_prompt(
            issue_type="epic",
            parent=None,
            goal="Test epic goal",
            config=mock_config,
            session_name="test-session",
            project_path=None
        )

        # Verify ORGANIZATION.md is listed in context files
        assert "ORGANIZATION.md" in prompt
        assert "organization-wide policies and requirements" in prompt

    def test_does_not_include_hardcoded_acceptance_criteria_warning(self, mock_config, temp_daf_home):
        """Test that the old hardcoded AC warning is NOT in the prompt."""
        prompt = _build_ticket_creation_prompt(
            issue_type="bug",
            parent="PROJ-12345",
            goal="Test bug goal",
            config=mock_config,
            session_name="test-session",
            project_path=None
        )

        # The old hardcoded warning should NOT be present
        assert "⚠️  CRITICAL: Acceptance Criteria Field Requirements" not in prompt
        assert "For all issue types (epic/story/spike/bug/task), --acceptance-criteria is REQUIRED" not in prompt

    def test_includes_default_context_files(self, mock_config, temp_daf_home):
        """Test that default context files are included."""
        prompt = _build_ticket_creation_prompt(
            issue_type="story",
            parent="PROJ-12345",
            goal="Test goal",
            config=mock_config,
            session_name="test-session",
            project_path=None
        )

        # Verify default files are mentioned
        assert "AGENTS.md" in prompt
        assert "CLAUDE.md" in prompt
        assert "DAF_AGENTS.md" in prompt

    def test_includes_analysis_only_constraints(self, mock_config, temp_daf_home):
        """Test that analysis-only constraints are in the prompt."""
        prompt = _build_ticket_creation_prompt(
            issue_type="task",
            parent="PROJ-12345",
            goal="Test goal",
            config=mock_config,
            session_name="test-session",
            project_path=None
        )

        # Verify analysis-only constraints
        assert "ANALYSIS-ONLY session" in prompt
        assert "DO NOT modify any code" in prompt
        assert "DO NOT make any file changes" in prompt
        assert "READ-ONLY analysis" in prompt

    def test_prompt_includes_jira_project_and_workstream(self, mock_config, temp_daf_home):
        """Test that the prompt includes the configured project and custom field defaults."""
        prompt = _build_ticket_creation_prompt(
            issue_type="story",
            parent="PROJ-12345",
            goal="Test goal",
            config=mock_config,
            session_name="test-session",
            project_path=None
        )

        # Verify project and custom fields are mentioned
        assert "project: PROJ" in prompt
        assert "custom fields: workstream=Platform" in prompt

    def test_prompt_includes_parent_when_provided(self, mock_config, temp_daf_home):
        """Test that the prompt includes parent reference when provided."""
        prompt = _build_ticket_creation_prompt(
            issue_type="story",
            parent="PROJ-62787",
            goal="Test goal",
            config=mock_config,
            session_name="test-session",
            project_path=None
        )

        # Verify parent is referenced
        assert "PROJ-62787" in prompt
        assert "--parent PROJ-62787" in prompt

    def test_hierarchical_files_appear_with_absolute_paths(self, mock_config, temp_daf_home):
        """Test that hierarchical files are listed with absolute paths."""
        from devflow.utils.paths import get_cs_home

        cs_home = get_cs_home()
        org_file = cs_home / "ORGANIZATION.md"
        org_file.write_text("# Organization Policy")

        prompt = _build_ticket_creation_prompt(
            issue_type="epic",
            parent=None,
            goal="Test goal",
            config=mock_config,
            session_name="test-session",
            project_path=None
        )

        # Hierarchical files should appear with absolute paths (containing cs_home path)
        assert str(cs_home) in prompt
        assert "ORGANIZATION.md" in prompt
