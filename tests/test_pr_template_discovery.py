"""Tests for PR template auto-discovery functionality."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil

import pytest

from devflow.cli.commands.complete_command import (
    _try_discover_repo_template,
    _try_discover_org_template,
    _generate_pr_description,
)
from devflow.config.loader import ConfigLoader
from devflow.session.manager import SessionManager


class TestRepoTemplateDiscovery:
    """Tests for _try_discover_repo_template function."""

    def test_discovers_template_in_github_directory(self, tmp_path):
        """Test template discovery from .github/PULL_REQUEST_TEMPLATE.md"""
        # Create template file
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "PULL_REQUEST_TEMPLATE.md"
        template_content = "## Test Template\nFrom .github directory"
        template_file.write_text(template_content, encoding='utf-8')

        # Test discovery
        result = _try_discover_repo_template(tmp_path)
        assert result == template_content

    def test_discovers_template_in_docs_directory(self, tmp_path):
        """Test template discovery from docs/PULL_REQUEST_TEMPLATE.md"""
        # Create template file
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        template_file = docs_dir / "PULL_REQUEST_TEMPLATE.md"
        template_content = "## Docs Template\nFrom docs directory"
        template_file.write_text(template_content, encoding='utf-8')

        # Test discovery
        result = _try_discover_repo_template(tmp_path)
        assert result == template_content

    def test_discovers_template_in_root_directory(self, tmp_path):
        """Test template discovery from root PULL_REQUEST_TEMPLATE.md"""
        # Create template file in root
        template_file = tmp_path / "PULL_REQUEST_TEMPLATE.md"
        template_content = "## Root Template"
        template_file.write_text(template_content, encoding='utf-8')

        # Test discovery
        result = _try_discover_repo_template(tmp_path)
        assert result == template_content

    def test_priority_order_github_over_docs(self, tmp_path):
        """Test that .github/ template has priority over docs/"""
        # Create both templates
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        github_template = github_dir / "PULL_REQUEST_TEMPLATE.md"
        github_template.write_text("GitHub template", encoding='utf-8')

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        docs_template = docs_dir / "PULL_REQUEST_TEMPLATE.md"
        docs_template.write_text("Docs template", encoding='utf-8')

        # Should return .github version
        result = _try_discover_repo_template(tmp_path)
        assert result == "GitHub template"

    def test_priority_order_docs_over_root(self, tmp_path):
        """Test that docs/ template has priority over root"""
        # Create both templates
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        docs_template = docs_dir / "PULL_REQUEST_TEMPLATE.md"
        docs_template.write_text("Docs template", encoding='utf-8')

        root_template = tmp_path / "PULL_REQUEST_TEMPLATE.md"
        root_template.write_text("Root template", encoding='utf-8')

        # Should return docs version
        result = _try_discover_repo_template(tmp_path)
        assert result == "Docs template"

    def test_returns_none_when_no_template_found(self, tmp_path):
        """Test returns None when no template exists"""
        result = _try_discover_repo_template(tmp_path)
        assert result is None

    def test_handles_unicode_decode_error(self, tmp_path):
        """Test gracefully handles files with encoding issues"""
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        template_file = github_dir / "PULL_REQUEST_TEMPLATE.md"

        # Write binary content that will fail UTF-8 decode
        template_file.write_bytes(b'\x80\x81\x82\x83')

        # Should return None instead of crashing
        result = _try_discover_repo_template(tmp_path)
        assert result is None


class TestOrgTemplateDiscovery:
    """Tests for _try_discover_org_template function."""

    @patch('devflow.cli.commands.complete_command.GitUtils.get_remote_url')
    @patch('devflow.cli.commands.complete_command._fetch_github_template')
    def test_discovers_github_org_template(self, mock_fetch, mock_get_url, tmp_path):
        """Test organization template discovery for GitHub"""
        # Mock git remote URL
        mock_get_url.return_value = "git@github.com:myorg/myrepo.git"

        # Mock successful template fetch
        template_content = "## Organization Template\nEnforced by org"
        mock_fetch.return_value = template_content

        # Test discovery
        result = _try_discover_org_template(tmp_path)

        # Verify correct URL was constructed with silent=True
        expected_url = "https://github.com/myorg/.github/blob/main/.github/PULL_REQUEST_TEMPLATE.md"
        mock_fetch.assert_called_once_with(expected_url, silent=True)
        assert result == template_content

    @patch('devflow.cli.commands.complete_command.GitUtils.get_remote_url')
    @patch('devflow.cli.commands.complete_command._fetch_github_template')
    def test_handles_https_github_url(self, mock_fetch, mock_get_url, tmp_path):
        """Test handles HTTPS GitHub URLs"""
        # Mock HTTPS URL
        mock_get_url.return_value = "https://github.com/acme-corp/product.git"

        # Mock successful fetch
        template_content = "## Acme Template"
        mock_fetch.return_value = template_content

        result = _try_discover_org_template(tmp_path)

        expected_url = "https://github.com/acme-corp/.github/blob/main/.github/PULL_REQUEST_TEMPLATE.md"
        mock_fetch.assert_called_once_with(expected_url, silent=True)
        assert result == template_content

    @patch('devflow.cli.commands.complete_command.GitUtils.get_remote_url')
    @patch('devflow.cli.commands.complete_command._fetch_gitlab_template')
    def test_discovers_gitlab_org_template(self, mock_fetch, mock_get_url, tmp_path):
        """Test organization template discovery for GitLab"""
        # Mock GitLab remote URL
        mock_get_url.return_value = "git@gitlab.com:myorg/myrepo.git"

        # Mock successful fetch
        template_content = "## GitLab Org Template"
        mock_fetch.return_value = template_content

        result = _try_discover_org_template(tmp_path)

        expected_url = "https://gitlab.com/myorg/.github/-/blob/main/.github/PULL_REQUEST_TEMPLATE.md"
        mock_fetch.assert_called_once_with(expected_url, silent=True)
        assert result == template_content

    @patch('devflow.cli.commands.complete_command.GitUtils.get_remote_url')
    @patch('devflow.cli.commands.complete_command._fetch_gitlab_template')
    def test_handles_self_hosted_gitlab(self, mock_fetch, mock_get_url, tmp_path):
        """Test handles self-hosted GitLab instances"""
        # Mock self-hosted GitLab URL
        mock_get_url.return_value = "git@gitlab.example.com:engineering/backend.git"

        # Mock successful fetch
        template_content = "## Self-hosted GitLab Template"
        mock_fetch.return_value = template_content

        result = _try_discover_org_template(tmp_path)

        # Should detect hostname from URL
        expected_url = "https://gitlab.example.com/engineering/.github/-/blob/main/.github/PULL_REQUEST_TEMPLATE.md"
        mock_fetch.assert_called_once_with(expected_url, silent=True)
        assert result == template_content

    @patch('devflow.cli.commands.complete_command.GitUtils.get_remote_url')
    def test_returns_none_when_no_remote(self, mock_get_url, tmp_path):
        """Test returns None when no git remote configured"""
        mock_get_url.return_value = None

        result = _try_discover_org_template(tmp_path)
        assert result is None

    @patch('devflow.cli.commands.complete_command.GitUtils.get_remote_url')
    @patch('devflow.cli.commands.complete_command._fetch_github_template')
    def test_returns_none_when_org_template_not_found(self, mock_fetch, mock_get_url, tmp_path):
        """Test returns None when organization doesn't have .github repo"""
        mock_get_url.return_value = "git@github.com:solo-dev/personal-project.git"
        mock_fetch.return_value = None  # Template not found

        result = _try_discover_org_template(tmp_path)
        assert result is None

    @patch('devflow.cli.commands.complete_command.GitUtils.get_remote_url')
    def test_handles_invalid_remote_url_format(self, mock_get_url, tmp_path):
        """Test gracefully handles malformed remote URLs"""
        mock_get_url.return_value = "not-a-valid-git-url"

        result = _try_discover_org_template(tmp_path)
        assert result is None


class TestPRDescriptionGenerationCascade:
    """Tests for _generate_pr_description with template discovery cascade."""

    @patch('devflow.cli.commands.complete_command._try_discover_org_template')
    @patch('devflow.cli.commands.complete_command._try_discover_repo_template')
    @patch('devflow.cli.commands.complete_command._fill_pr_template')
    @patch('devflow.cli.commands.complete_command.GitUtils')
    def test_uses_org_template_when_available(
        self, mock_git, mock_fill, mock_repo, mock_org, tmp_path, temp_daf_home
    ):
        """Test organization template has highest priority"""
        # Setup
        org_template = "## Org Template (Enforced)"
        mock_org.return_value = org_template
        mock_repo.return_value = "## Repo Template"
        mock_fill.return_value = "Filled template"

        # Mock git operations
        mock_git.get_commit_log.return_value = "commit log"
        mock_git.get_changed_files.return_value = ["file1.py"]

        # Create session
        config_loader = ConfigLoader()
        config_loader.config_dir.mkdir(parents=True, exist_ok=True)
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-session",
            goal="Test",
            working_directory="test",
            project_path=str(tmp_path),
            ai_agent_session_id="uuid-1"
        )

        # Generate description
        result = _generate_pr_description(session, tmp_path, config_loader)

        # Verify org template was used (not repo template)
        mock_fill.assert_called_once()
        call_args = mock_fill.call_args[0]
        assert call_args[0] == org_template

    @patch('devflow.cli.commands.complete_command._try_discover_org_template')
    @patch('devflow.cli.commands.complete_command._try_discover_repo_template')
    @patch('devflow.cli.commands.complete_command._fill_pr_template')
    @patch('devflow.cli.commands.complete_command.GitUtils')
    def test_uses_repo_template_when_no_org_template(
        self, mock_git, mock_fill, mock_repo, mock_org, tmp_path, temp_daf_home
    ):
        """Test repository template used when no organization template"""
        # Setup
        mock_org.return_value = None  # No org template
        repo_template = "## Repo Template"
        mock_repo.return_value = repo_template
        mock_fill.return_value = "Filled template"

        # Mock git operations
        mock_git.get_commit_log.return_value = "commit log"
        mock_git.get_changed_files.return_value = ["file1.py"]

        # Create session
        config_loader = ConfigLoader()
        config_loader.config_dir.mkdir(parents=True, exist_ok=True)
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-session",
            goal="Test",
            working_directory="test",
            project_path=str(tmp_path),
            ai_agent_session_id="uuid-1"
        )

        # Generate description
        result = _generate_pr_description(session, tmp_path, config_loader)

        # Verify repo template was used
        mock_fill.assert_called_once()
        call_args = mock_fill.call_args[0]
        assert call_args[0] == repo_template

    @patch('devflow.cli.commands.complete_command._try_discover_org_template')
    @patch('devflow.cli.commands.complete_command._try_discover_repo_template')
    @patch('devflow.cli.commands.complete_command._fetch_pr_template')
    @patch('devflow.cli.commands.complete_command._fill_pr_template')
    @patch('devflow.cli.commands.complete_command.GitUtils')
    @patch('devflow.cli.commands.complete_command.Confirm.ask')
    def test_uses_user_config_when_no_auto_discovered_templates(
        self, mock_confirm, mock_git, mock_fill, mock_fetch, mock_repo, mock_org, tmp_path, temp_daf_home
    ):
        """Test user-configured URL used when no auto-discovered templates"""
        # Setup
        mock_org.return_value = None  # No org template
        mock_repo.return_value = None  # No repo template
        user_template = "## User Template"
        mock_fetch.return_value = user_template
        mock_fill.return_value = "Filled template"
        mock_confirm.return_value = False  # Don't prompt for new URL

        # Mock git operations
        mock_git.get_commit_log.return_value = "commit log"
        mock_git.get_changed_files.return_value = ["file1.py"]

        # Create config with pr_template_url
        config_loader = ConfigLoader()
        config_loader.config_dir.mkdir(parents=True, exist_ok=True)
        config = config_loader.create_default_config()
        config.pr_template_url = "https://example.com/template.md"
        config_loader.save_config(config)

        # Create session
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-session",
            goal="Test",
            working_directory="test",
            project_path=str(tmp_path),
            ai_agent_session_id="uuid-1"
        )

        # Generate description
        result = _generate_pr_description(session, tmp_path, config_loader)

        # Verify user-configured template was fetched and used
        mock_fetch.assert_called_once_with("https://example.com/template.md")
        mock_fill.assert_called_once()
        call_args = mock_fill.call_args[0]
        assert call_args[0] == user_template

    @patch('devflow.cli.commands.complete_command._try_discover_org_template')
    @patch('devflow.cli.commands.complete_command._try_discover_repo_template')
    @patch('devflow.cli.commands.complete_command.GitUtils')
    @patch('devflow.cli.commands.complete_command.Confirm.ask')
    def test_uses_default_template_when_no_templates_found(
        self, mock_confirm, mock_git, mock_repo, mock_org, tmp_path, temp_daf_home
    ):
        """Test default built-in template used as final fallback"""
        # Setup
        mock_org.return_value = None
        mock_repo.return_value = None
        mock_confirm.return_value = False  # Don't configure new URL

        # Mock git operations
        mock_git.get_commit_log.return_value = "commit log"
        mock_git.get_changed_files.return_value = ["file1.py"]

        # Create session without pr_template_url
        config_loader = ConfigLoader()
        config_loader.config_dir.mkdir(parents=True, exist_ok=True)
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-session",
            goal="Test goal",
            working_directory="test",
            project_path=str(tmp_path),
            ai_agent_session_id="uuid-1"
        )

        # Generate description
        result = _generate_pr_description(session, tmp_path, config_loader)

        # Verify default template structure is present
        assert "## Test plan" in result
        assert "Claude Code" in result
        assert "Co-Authored-By: Claude" in result

    @patch('devflow.cli.commands.complete_command._try_discover_org_template')
    @patch('devflow.cli.commands.complete_command._try_discover_repo_template')
    @patch('devflow.cli.commands.complete_command._fetch_pr_template')
    @patch('devflow.cli.commands.complete_command.GitUtils')
    def test_org_template_overrides_user_config(
        self, mock_git, mock_fetch, mock_repo, mock_org, tmp_path, temp_daf_home
    ):
        """Test organization template overrides user configuration (enforcement)"""
        # Setup
        org_template = "## Org Template (Enforced)"
        mock_org.return_value = org_template
        mock_repo.return_value = None
        # Note: mock_fetch should NOT be called when org template exists

        # Mock git operations
        mock_git.get_commit_log.return_value = "commit log"
        mock_git.get_changed_files.return_value = ["file1.py"]

        # Create config with pr_template_url (should be ignored)
        config_loader = ConfigLoader()
        config_loader.config_dir.mkdir(parents=True, exist_ok=True)
        config = config_loader.create_default_config()
        config.pr_template_url = "https://example.com/my-template.md"
        config_loader.save_config(config)

        # Create session
        session_manager = SessionManager(config_loader)
        session = session_manager.create_session(
            name="test-session",
            goal="Test",
            working_directory="test",
            project_path=str(tmp_path),
            ai_agent_session_id="uuid-1"
        )

        # Generate description
        with patch('devflow.cli.commands.complete_command._fill_pr_template') as mock_fill:
            mock_fill.return_value = "Filled template"
            result = _generate_pr_description(session, tmp_path, config_loader)

            # Verify user template was NOT fetched
            mock_fetch.assert_not_called()

            # Verify org template was used
            mock_fill.assert_called_once()
            call_args = mock_fill.call_args[0]
            assert call_args[0] == org_template
