"""Tests for daf git new command template support (Issue #517)."""

import os
import pytest
from unittest.mock import MagicMock

from devflow.cli.commands.git_new_command import (
    _build_issue_creation_prompt,
    DEFAULT_GITHUB_ISSUE_TEMPLATES,
)


class TestDefaultGitHubIssueTemplates:
    """Test the DEFAULT_GITHUB_ISSUE_TEMPLATES constant."""

    def test_has_bug_template(self):
        assert "bug" in DEFAULT_GITHUB_ISSUE_TEMPLATES
        assert "Bug Description" in DEFAULT_GITHUB_ISSUE_TEMPLATES["bug"]

    def test_has_enhancement_template(self):
        assert "enhancement" in DEFAULT_GITHUB_ISSUE_TEMPLATES
        assert "Acceptance Criteria" in DEFAULT_GITHUB_ISSUE_TEMPLATES["enhancement"]

    def test_has_task_template(self):
        assert "task" in DEFAULT_GITHUB_ISSUE_TEMPLATES
        assert "Acceptance Criteria" in DEFAULT_GITHUB_ISSUE_TEMPLATES["task"]

    def test_has_epic_template(self):
        assert "epic" in DEFAULT_GITHUB_ISSUE_TEMPLATES
        assert "Epic Summary" in DEFAULT_GITHUB_ISSUE_TEMPLATES["epic"]

    def test_all_templates_use_markdown(self):
        for type_name, template in DEFAULT_GITHUB_ISSUE_TEMPLATES.items():
            assert "##" in template, f"{type_name} template should use Markdown headers"
            assert "h2." not in template, f"{type_name} template should not use JIRA Wiki markup"
            assert "- [ ]" in template, f"{type_name} template should use Markdown checkboxes"


class TestBuildIssueCreationPrompt:
    """Test _build_issue_creation_prompt with template support."""

    @pytest.fixture
    def mock_config(self, temp_daf_home):
        config = MagicMock()
        config.context_files = None
        config.github = None
        return config

    def test_includes_default_template_for_bug(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix API timeout",
            config=mock_config,
            session_name="test-session",
        )
        assert "Bug Description" in prompt
        assert "built-in defaults" in prompt

    def test_includes_default_template_for_enhancement(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type="enhancement",
            goal="Add caching",
            config=mock_config,
            session_name="test-session",
        )
        assert "Proposed Solution" in prompt

    def test_includes_config_templates_when_set(self, mock_config):
        mock_config.github = MagicMock()
        mock_config.github.issue_templates = {"bug": "## Custom Bug Template\n\nCustom content"}
        mock_config.github.default_labels = []
        mock_config.github.repository = None

        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix API timeout",
            config=mock_config,
            session_name="test-session",
        )
        assert "Custom Bug Template" in prompt
        assert "configuration (organization/team config)" in prompt

    def test_config_templates_override_defaults(self, mock_config):
        mock_config.github = MagicMock()
        mock_config.github.issue_templates = {"bug": "## Custom Bug\n\nOverridden"}
        mock_config.github.default_labels = []
        mock_config.github.repository = None

        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix timeout",
            config=mock_config,
            session_name="test-session",
        )
        assert "Custom Bug" in prompt
        assert "built-in defaults" not in prompt

    def test_detects_github_issue_template_dir(self, mock_config, tmp_path):
        template_dir = tmp_path / ".github" / "ISSUE_TEMPLATE"
        template_dir.mkdir(parents=True)

        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix timeout",
            config=mock_config,
            session_name="test-session",
            project_path=str(tmp_path),
        )
        assert "Repository issue templates found" in prompt
        assert str(template_dir) in prompt

    def test_detects_gitlab_issue_template_dir(self, mock_config, tmp_path):
        template_dir = tmp_path / ".gitlab" / "issue_templates"
        template_dir.mkdir(parents=True)

        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix timeout",
            config=mock_config,
            session_name="test-session",
            project_path=str(tmp_path),
        )
        assert "Repository issue templates found" in prompt

    def test_no_repo_template_dir_when_absent(self, mock_config, tmp_path):
        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix timeout",
            config=mock_config,
            session_name="test-session",
            project_path=str(tmp_path),
        )
        assert "Repository issue templates found" not in prompt

    def test_includes_example_gh_command(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type="enhancement",
            goal="Add caching",
            config=mock_config,
            session_name="test-session",
        )
        assert "gh issue create" in prompt
        assert "glab issue create" in prompt

    def test_includes_issue_type_label_in_example(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix timeout",
            config=mock_config,
            session_name="test-session",
        )
        assert "--label" in prompt
        assert "bug" in prompt

    def test_includes_default_labels_in_example(self, mock_config):
        mock_config.github = MagicMock()
        mock_config.github.issue_templates = None
        mock_config.github.default_labels = ["team-backend", "priority-medium"]
        mock_config.github.repository = None

        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix timeout",
            config=mock_config,
            session_name="test-session",
        )
        assert "team-backend" in prompt
        assert "priority-medium" in prompt

    def test_no_issue_type_still_works(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type=None,
            goal="General improvement",
            config=mock_config,
            session_name="test-session",
        )
        assert "gh issue create" in prompt
        assert "ANALYSIS-ONLY session" in prompt
        assert "Available issue templates" in prompt

    def test_no_issue_type_no_label_flag(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type=None,
            goal="General improvement",
            config=mock_config,
            session_name="test-session",
        )
        assert "--label" not in prompt

    def test_includes_analysis_only_constraints(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type="task",
            goal="Refactor module",
            config=mock_config,
            session_name="test-session",
        )
        assert "ANALYSIS-ONLY session" in prompt
        assert "DO NOT modify any code" in prompt
        assert "READ-ONLY analysis" in prompt

    def test_parent_included_when_provided(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type="task",
            goal="Sub-task",
            config=mock_config,
            session_name="test-session",
            parent="#456",
        )
        assert "#456" not in prompt or "Create GitHub/GitLab" in prompt

    def test_template_case_insensitive_match(self, mock_config):
        mock_config.github = MagicMock()
        mock_config.github.issue_templates = {"Bug": "## Bug Template Content"}
        mock_config.github.default_labels = []
        mock_config.github.repository = None

        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix timeout",
            config=mock_config,
            session_name="test-session",
        )
        assert "Bug Template Content" in prompt

    def test_defaults_summary_with_config(self, mock_config):
        mock_config.github = MagicMock()
        mock_config.github.issue_templates = None
        mock_config.github.default_labels = ["v3"]
        mock_config.github.repository = "org/repo"

        prompt = _build_issue_creation_prompt(
            issue_type="task",
            goal="Some task",
            config=mock_config,
            session_name="test-session",
        )
        assert "default labels: v3" in prompt
        assert "repository: org/repo" in prompt

    def test_defaults_summary_no_config(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type="task",
            goal="Some task",
            config=mock_config,
            session_name="test-session",
        )
        assert "no defaults configured" in prompt

    def test_daf_link_instruction_present(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix it",
            config=mock_config,
            session_name="test-session",
        )
        assert "daf link" in prompt

    def test_daf_git_skill_reference(self, mock_config):
        prompt = _build_issue_creation_prompt(
            issue_type="bug",
            goal="Fix it",
            config=mock_config,
            session_name="test-session",
        )
        assert "daf-git skill" in prompt
