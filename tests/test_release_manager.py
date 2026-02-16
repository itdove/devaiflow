"""Tests for ReleaseManager commit analysis."""

import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from tempfile import TemporaryDirectory

from devflow.release.manager import ReleaseManager
from devflow.release.version import Version


class TestCommitAnalysis:
    """Test commit analysis functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo_path = Path("/test/repo")
        self.manager = ReleaseManager(self.repo_path)

    @patch("subprocess.run")
    def test_analyze_commits_categorizes_features(self, mock_run):
        """Test that feature commits are properly categorized."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123 feat: add new feature\ndef456 feat(api): add endpoint\n"
        )

        analysis = self.manager.analyze_commits_since_tag("v1.0.0")

        assert len(analysis['features']) == 2
        assert len(analysis['fixes']) == 0
        assert len(analysis['breaking']) == 0

    @patch("subprocess.run")
    def test_analyze_commits_categorizes_fixes(self, mock_run):
        """Test that fix commits are properly categorized."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123 fix: resolve bug\ndef456 fix(core): patch issue\n"
        )

        analysis = self.manager.analyze_commits_since_tag("v1.0.0")

        assert len(analysis['features']) == 0
        assert len(analysis['fixes']) == 2
        assert len(analysis['breaking']) == 0

    @patch("subprocess.run")
    def test_analyze_commits_categorizes_breaking_with_exclamation(self, mock_run):
        """Test that breaking changes with ! are properly categorized."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123 feat!: breaking change\ndef456 fix!: breaking fix\n"
        )

        analysis = self.manager.analyze_commits_since_tag("v1.0.0")

        assert len(analysis['breaking']) == 2
        assert len(analysis['features']) == 0
        assert len(analysis['fixes']) == 0

    @patch("subprocess.run")
    def test_analyze_commits_categorizes_breaking_with_text(self, mock_run):
        """Test that BREAKING CHANGE in message is detected."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123 feat: BREAKING CHANGE: major update\n"
        )

        analysis = self.manager.analyze_commits_since_tag("v1.0.0")

        assert len(analysis['breaking']) == 1

    @patch("subprocess.run")
    def test_analyze_commits_handles_mixed_commits(self, mock_run):
        """Test analysis of mixed commit types."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=(
                "abc123 feat: add feature\n"
                "def456 fix: fix bug\n"
                "ghi789 docs: update docs\n"
                "jkl012 feat!: breaking change\n"
                "mno345 chore: update deps\n"
            )
        )

        analysis = self.manager.analyze_commits_since_tag("v1.0.0")

        assert len(analysis['features']) == 1
        assert len(analysis['fixes']) == 1
        assert len(analysis['breaking']) == 1
        assert len(analysis['other']) == 2

    @patch("subprocess.run")
    def test_analyze_commits_handles_empty_result(self, mock_run):
        """Test that empty git log is handled."""
        mock_run.return_value = Mock(returncode=0, stdout="")

        analysis = self.manager.analyze_commits_since_tag("v1.0.0")

        assert len(analysis['features']) == 0
        assert len(analysis['fixes']) == 0
        assert len(analysis['breaking']) == 0
        assert len(analysis['other']) == 0

    @patch("subprocess.run")
    def test_analyze_commits_handles_git_error(self, mock_run):
        """Test that git errors are handled gracefully."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")

        analysis = self.manager.analyze_commits_since_tag("v1.0.0")

        assert len(analysis['features']) == 0
        assert len(analysis['fixes']) == 0
        assert len(analysis['breaking']) == 0
        assert len(analysis['other']) == 0


class TestSuggestReleaseType:
    """Test release type suggestion."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo_path = Path("/test/repo")
        self.manager = ReleaseManager(self.repo_path)

    @patch.object(ReleaseManager, "get_latest_tag")
    @patch.object(ReleaseManager, "analyze_commits_since_tag")
    def test_suggest_major_for_breaking_changes(self, mock_analyze, mock_get_tag):
        """Test that breaking changes suggest major release."""
        mock_get_tag.return_value = "v1.0.0"
        mock_analyze.return_value = {
            'breaking': ['abc123 feat!: breaking'],
            'features': [],
            'fixes': [],
            'other': []
        }

        suggestion, explanation, analysis = self.manager.suggest_release_type()

        assert suggestion == "major"
        assert "breaking" in explanation.lower()

    @patch.object(ReleaseManager, "get_latest_tag")
    @patch.object(ReleaseManager, "analyze_commits_since_tag")
    def test_suggest_minor_for_features(self, mock_analyze, mock_get_tag):
        """Test that features suggest minor release."""
        mock_get_tag.return_value = "v1.0.0"
        mock_analyze.return_value = {
            'breaking': [],
            'features': ['abc123 feat: new feature'],
            'fixes': [],
            'other': []
        }

        suggestion, explanation, analysis = self.manager.suggest_release_type()

        assert suggestion == "minor"
        assert "feature" in explanation.lower()

    @patch.object(ReleaseManager, "get_latest_tag")
    @patch.object(ReleaseManager, "analyze_commits_since_tag")
    def test_suggest_patch_for_fixes(self, mock_analyze, mock_get_tag):
        """Test that fixes suggest patch release."""
        mock_get_tag.return_value = "v1.0.0"
        mock_analyze.return_value = {
            'breaking': [],
            'features': [],
            'fixes': ['abc123 fix: bug fix'],
            'other': []
        }

        suggestion, explanation, analysis = self.manager.suggest_release_type()

        assert suggestion == "patch"
        assert "fix" in explanation.lower()

    @patch.object(ReleaseManager, "get_latest_tag")
    @patch.object(ReleaseManager, "analyze_commits_since_tag")
    def test_suggest_none_for_other_commits(self, mock_analyze, mock_get_tag):
        """Test that only non-conventional commits return None."""
        mock_get_tag.return_value = "v1.0.0"
        mock_analyze.return_value = {
            'breaking': [],
            'features': [],
            'fixes': [],
            'other': ['abc123 docs: update']
        }

        suggestion, explanation, analysis = self.manager.suggest_release_type()

        assert suggestion is None
        assert "unable to suggest" in explanation.lower()

    @patch.object(ReleaseManager, "get_latest_tag")
    def test_suggest_minor_for_first_release(self, mock_get_tag):
        """Test that first release suggests minor."""
        mock_get_tag.return_value = None

        suggestion, explanation, analysis = self.manager.suggest_release_type()

        assert suggestion == "minor"
        assert "no previous releases" in explanation.lower()

    @patch.object(ReleaseManager, "get_latest_tag")
    @patch.object(ReleaseManager, "analyze_commits_since_tag")
    def test_breaking_takes_precedence_over_features(self, mock_analyze, mock_get_tag):
        """Test that breaking changes take precedence."""
        mock_get_tag.return_value = "v1.0.0"
        mock_analyze.return_value = {
            'breaking': ['abc123 feat!: breaking'],
            'features': ['def456 feat: new feature'],
            'fixes': ['ghi789 fix: bug'],
            'other': []
        }

        suggestion, _, _ = self.manager.suggest_release_type()

        assert suggestion == "major"

    @patch.object(ReleaseManager, "get_latest_tag")
    @patch.object(ReleaseManager, "analyze_commits_since_tag")
    def test_features_take_precedence_over_fixes(self, mock_analyze, mock_get_tag):
        """Test that features take precedence over fixes."""
        mock_get_tag.return_value = "v1.0.0"
        mock_analyze.return_value = {
            'breaking': [],
            'features': ['abc123 feat: new feature'],
            'fixes': ['def456 fix: bug'],
            'other': []
        }

        suggestion, _, _ = self.manager.suggest_release_type()

        assert suggestion == "minor"


class TestUpdateChangelog:
    """Test CHANGELOG.md update functionality."""

    @patch("devflow.release.permissions.get_git_remote_url")
    @patch("devflow.release.permissions.parse_git_remote")
    def test_update_changelog_adds_version_section_and_github_link(self, mock_parse, mock_get_url):
        """Test that update_changelog adds both version section and GitHub reference link."""
        from devflow.release.permissions import Platform

        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md with existing content
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]

### Added
- New feature

## [0.1.0] - 2025-01-01

### Added
- Initial release

[0.1.0]: https://github.com/test/repo/tags/v0.1.0
"""
            changelog_file.write_text(initial_content)

            # Mock git remote URL parsing
            mock_get_url.return_value = "git@github.com:test/repo.git"
            mock_parse.return_value = (Platform.GITHUB, "test", "repo")

            # Update changelog with new version
            version = Version(0, 2, 0)
            manager.update_changelog(version, release_date="2025-01-15")

            # Read updated content
            updated_content = changelog_file.read_text()

            # Verify version section was added
            assert "## [0.2.0] - 2025-01-15" in updated_content
            assert "## [Unreleased]" in updated_content

            # Verify reference link was added
            assert "[0.2.0]: https://github.com/test/repo/tags/v0.2.0" in updated_content

            # Verify link is in reverse chronological order (before 0.1.0 link)
            ref_0_2_0_pos = updated_content.index("[0.2.0]:")
            ref_0_1_0_pos = updated_content.index("[0.1.0]:")
            assert ref_0_2_0_pos < ref_0_1_0_pos, "Reference links should be in reverse chronological order"

    @patch("devflow.release.permissions.get_git_remote_url")
    @patch("devflow.release.permissions.parse_git_remote")
    def test_update_changelog_adds_gitlab_link_with_ssh_url(self, mock_parse, mock_get_url):
        """Test that update_changelog adds GitLab reference link from SSH URL."""
        from devflow.release.permissions import Platform

        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]

## [0.1.0] - 2025-01-01

[0.1.0]: https://gitlab.example.com/group/repo/-/tags/v0.1.0
"""
            changelog_file.write_text(initial_content)

            # Mock git remote URL parsing for GitLab SSH
            mock_get_url.return_value = "git@gitlab.example.com:group/repo.git"
            mock_parse.return_value = (Platform.GITLAB, "group", "repo")

            # Update changelog
            version = Version(0, 2, 0)
            manager.update_changelog(version, release_date="2025-01-15")

            # Read updated content
            updated_content = changelog_file.read_text()

            # Verify GitLab reference link was added with correct format
            assert "[0.2.0]: https://gitlab.example.com/group/repo/-/tags/v0.2.0" in updated_content

    @patch("devflow.release.permissions.get_git_remote_url")
    @patch("devflow.release.permissions.parse_git_remote")
    def test_update_changelog_adds_gitlab_link_with_https_url(self, mock_parse, mock_get_url):
        """Test that update_changelog adds GitLab reference link from HTTPS URL."""
        from devflow.release.permissions import Platform

        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]

## [0.1.0] - 2025-01-01

[0.1.0]: https://gitlab.com/group/repo/-/tags/v0.1.0
"""
            changelog_file.write_text(initial_content)

            # Mock git remote URL parsing for GitLab HTTPS
            mock_get_url.return_value = "https://gitlab.com/group/repo.git"
            mock_parse.return_value = (Platform.GITLAB, "group", "repo")

            # Update changelog
            version = Version(0, 2, 0)
            manager.update_changelog(version, release_date="2025-01-15")

            # Read updated content
            updated_content = changelog_file.read_text()

            # Verify GitLab reference link was added
            assert "[0.2.0]: https://gitlab.com/group/repo/-/tags/v0.2.0" in updated_content

    @patch("devflow.release.permissions.get_git_remote_url")
    @patch("devflow.release.permissions.parse_git_remote")
    def test_update_changelog_handles_no_existing_reference_links(self, mock_parse, mock_get_url):
        """Test that update_changelog creates reference link section when none exists."""
        from devflow.release.permissions import Platform

        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md without reference links
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]

### Added
- New feature
"""
            changelog_file.write_text(initial_content)

            # Mock git remote URL parsing
            mock_get_url.return_value = "git@github.com:test/repo.git"
            mock_parse.return_value = (Platform.GITHUB, "test", "repo")

            # Update changelog
            version = Version(0, 1, 0)
            manager.update_changelog(version, release_date="2025-01-01")

            # Read updated content
            updated_content = changelog_file.read_text()

            # Verify reference link was added at the end
            assert "[0.1.0]: https://github.com/test/repo/tags/v0.1.0" in updated_content

    @patch("devflow.release.permissions.get_git_remote_url")
    def test_update_changelog_handles_no_git_remote(self, mock_get_url):
        """Test that update_changelog still works when git remote is not available."""
        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]

### Added
- New feature
"""
            changelog_file.write_text(initial_content)

            # Mock git remote URL as None (no remote configured)
            mock_get_url.return_value = None

            # Update changelog should still add version section
            version = Version(0, 1, 0)
            manager.update_changelog(version, release_date="2025-01-01")

            # Read updated content
            updated_content = changelog_file.read_text()

            # Verify version section was added
            assert "## [0.1.0] - 2025-01-01" in updated_content

            # Reference link should NOT be added (no remote URL)
            assert "[0.1.0]:" not in updated_content

    @patch("devflow.release.permissions.get_git_remote_url")
    @patch("devflow.release.permissions.parse_git_remote")
    def test_update_changelog_handles_unknown_platform(self, mock_parse, mock_get_url):
        """Test that update_changelog handles unknown git platforms gracefully."""
        from devflow.release.permissions import Platform

        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]

### Added
- New feature
"""
            changelog_file.write_text(initial_content)

            # Mock git remote URL parsing with unknown platform
            mock_get_url.return_value = "git@unknown.com:test/repo.git"
            mock_parse.return_value = (Platform.UNKNOWN, None, None)

            # Update changelog
            version = Version(0, 1, 0)
            manager.update_changelog(version, release_date="2025-01-01")

            # Read updated content
            updated_content = changelog_file.read_text()

            # Verify version section was added
            assert "## [0.1.0] - 2025-01-01" in updated_content

            # Reference link should NOT be added (unknown platform)
            assert "[0.1.0]:" not in updated_content

    @patch("devflow.release.permissions.get_git_remote_url")
    @patch("devflow.release.permissions.parse_git_remote")
    def test_update_changelog_dry_run_does_not_write_file(self, mock_parse, mock_get_url):
        """Test that dry_run mode doesn't actually write to the file."""
        from devflow.release.permissions import Platform

        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]

### Added
- New feature

[0.1.0]: https://github.com/test/repo/tags/v0.1.0
"""
            changelog_file.write_text(initial_content)

            # Mock git remote URL parsing
            mock_get_url.return_value = "git@github.com:test/repo.git"
            mock_parse.return_value = (Platform.GITHUB, "test", "repo")

            # Update changelog in dry-run mode
            version = Version(0, 2, 0)
            manager.update_changelog(version, release_date="2025-01-15", dry_run=True)

            # Read content - should be unchanged
            content_after = changelog_file.read_text()

            assert content_after == initial_content
            assert "## [0.2.0]" not in content_after
            assert "[0.2.0]:" not in content_after

    def test_update_changelog_raises_error_if_version_exists(self):
        """Test that update_changelog raises error if version already exists."""
        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md with existing version
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]

## [0.1.0] - 2025-01-01

### Added
- Initial release
"""
            changelog_file.write_text(initial_content)

            # Try to update with same version
            version = Version(0, 1, 0)

            with pytest.raises(ValueError, match="Version 0.1.0 already exists"):
                manager.update_changelog(version, release_date="2025-01-15")

    def test_update_changelog_raises_error_if_unreleased_section_missing(self):
        """Test that update_changelog raises error if [Unreleased] section is missing."""
        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md without [Unreleased] section
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [0.1.0] - 2025-01-01

### Added
- Initial release
"""
            changelog_file.write_text(initial_content)

            # Try to update
            version = Version(0, 2, 0)

            with pytest.raises(ValueError, match="Could not find \\[Unreleased\\] section"):
                manager.update_changelog(version, release_date="2025-01-15")


class TestGetCommitsWithPRs:
    """Test get_commits_with_prs method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo_path = Path("/test/repo")
        self.manager = ReleaseManager(self.repo_path)

    @patch("subprocess.run")
    def test_extracts_github_pr_numbers(self, mock_run):
        """Test extraction of GitHub PR numbers from merge commits."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=(
                "abc123|||Merge pull request #123 from user/branch|||PR description|||COMMIT_DELIMITER|||"
                "def456|||Merge pull request #456 from user/another|||Another PR|||COMMIT_DELIMITER|||"
            )
        )

        commits = self.manager.get_commits_with_prs("v1.0.0")

        assert len(commits) == 2
        assert commits[0]['pr_mr'] == {'type': 'github_pr', 'number': '123'}
        assert commits[1]['pr_mr'] == {'type': 'github_pr', 'number': '456'}

    @patch("subprocess.run")
    def test_extracts_gitlab_mr_numbers(self, mock_run):
        """Test extraction of GitLab MR numbers from merge commits."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123|||Merge branch 'feature' into 'main'|||Feature description\n\nSee merge request !281|||COMMIT_DELIMITER|||"
        )

        commits = self.manager.get_commits_with_prs("v1.0.0")

        assert len(commits) == 1
        assert commits[0]['pr_mr'] == {'type': 'gitlab_mr', 'number': '281'}

    @patch("subprocess.run")
    def test_extracts_gitlab_mr_with_project_path(self, mock_run):
        """Test extraction of GitLab MR numbers with project path."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="abc123|||Merge branch 'feature' into 'main'|||Feature description\n\nSee merge request owner/repo!281|||COMMIT_DELIMITER|||"
        )

        commits = self.manager.get_commits_with_prs("v1.0.0")

        assert len(commits) == 1
        assert commits[0]['pr_mr'] == {'type': 'gitlab_mr', 'number': '281'}

    @patch("subprocess.run")
    def test_handles_commits_without_prs(self, mock_run):
        """Test handling of regular commits without PR/MR numbers."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=(
                "abc123|||feat: add new feature|||Direct commit|||COMMIT_DELIMITER|||"
                "def456|||fix: resolve bug|||Another direct commit|||COMMIT_DELIMITER|||"
            )
        )

        commits = self.manager.get_commits_with_prs("v1.0.0")

        assert len(commits) == 2
        assert commits[0]['pr_mr'] is None
        assert commits[1]['pr_mr'] is None

    @patch("subprocess.run")
    def test_handles_git_error(self, mock_run):
        """Test graceful handling of git errors."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")

        commits = self.manager.get_commits_with_prs("v1.0.0")

        assert commits == []


class TestFetchPRMetadata:
    """Test fetch_pr_metadata method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo_path = Path("/test/repo")
        self.manager = ReleaseManager(self.repo_path)

    @patch("subprocess.run")
    def test_fetches_github_pr_metadata(self, mock_run):
        """Test successful fetch of GitHub PR metadata."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"number": 123, "title": "Add feature", "body": "Description", "url": "https://github.com/test/repo/pull/123"}'
        )

        metadata = self.manager.fetch_pr_metadata("123")

        assert metadata is not None
        assert metadata['number'] == 123
        assert metadata['title'] == "Add feature"
        assert metadata['type'] == 'github_pr'

    @patch("subprocess.run")
    def test_returns_none_on_gh_error(self, mock_run):
        """Test returns None when gh command fails."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")

        metadata = self.manager.fetch_pr_metadata("123")

        assert metadata is None

    @patch("subprocess.run")
    def test_returns_none_on_timeout(self, mock_run):
        """Test returns None when gh command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 10)

        metadata = self.manager.fetch_pr_metadata("123")

        assert metadata is None


class TestFetchMRMetadata:
    """Test fetch_mr_metadata method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo_path = Path("/test/repo")
        self.manager = ReleaseManager(self.repo_path)

    @patch("subprocess.run")
    def test_fetches_gitlab_mr_metadata(self, mock_run):
        """Test successful fetch of GitLab MR metadata."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"iid": 281, "title": "Add feature", "description": "Description", "web_url": "https://gitlab.com/test/repo/-/merge_requests/281"}'
        )

        metadata = self.manager.fetch_mr_metadata("281")

        assert metadata is not None
        assert metadata['number'] == 281
        assert metadata['title'] == "Add feature"
        assert metadata['body'] == "Description"
        assert metadata['type'] == 'gitlab_mr'

    @patch("subprocess.run")
    def test_returns_none_on_glab_error(self, mock_run):
        """Test returns None when glab command fails."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")

        metadata = self.manager.fetch_mr_metadata("281")

        assert metadata is None


class TestGenerateChangelogContent:
    """Test generate_changelog_content method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo_path = Path("/test/repo")
        self.manager = ReleaseManager(self.repo_path)

    def test_categorizes_by_conventional_commit_prefix(self):
        """Test categorization by conventional commit prefix."""
        pr_mr_list = [
            {'title': 'feat: add new feature', 'body': '', 'url': 'https://github.com/test/repo/pull/1', 'number': 1},
            {'title': 'fix: resolve bug', 'body': '', 'url': 'https://github.com/test/repo/pull/2', 'number': 2},
            {'title': 'refactor: update code', 'body': '', 'url': 'https://github.com/test/repo/pull/3', 'number': 3},
        ]

        content = self.manager.generate_changelog_content(pr_mr_list)

        assert '### Added' in content
        assert 'add new feature' in content
        assert '#1' in content
        assert '### Fixed' in content
        assert 'resolve bug' in content
        assert '#2' in content
        assert '### Changed' in content
        assert 'update code' in content
        assert '#3' in content

    def test_extracts_jira_tickets(self):
        """Test extraction of JIRA ticket references."""
        pr_mr_list = [
            {'title': 'PROJ-12345: add feature', 'body': '', 'url': 'https://github.com/test/repo/pull/1', 'number': 1},
        ]

        content = self.manager.generate_changelog_content(pr_mr_list)

        assert 'PROJ-12345' in content
        assert '#1' in content

    def test_parses_body_for_categories(self):
        """Test parsing PR/MR body for category sections."""
        pr_mr_list = [
            {
                'title': 'Update feature',
                'body': '## Added\n- New validation\n- Enhanced UI\n\n## Fixed\n- Bug in processing',
                'url': 'https://github.com/test/repo/pull/1',
                'number': 1
            },
        ]

        content = self.manager.generate_changelog_content(pr_mr_list)

        assert '### Added' in content
        assert 'New validation' in content
        assert 'Enhanced UI' in content
        assert '### Fixed' in content
        assert 'Bug in processing' in content

    def test_includes_pr_links(self):
        """Test that PR/MR links are included in changelog entries."""
        pr_mr_list = [
            {'title': 'feat: add feature', 'body': '', 'url': 'https://github.com/test/repo/pull/123', 'number': 123},
        ]

        content = self.manager.generate_changelog_content(pr_mr_list)

        assert '[#123](https://github.com/test/repo/pull/123)' in content

    def test_removes_conventional_commit_prefix(self):
        """Test that conventional commit prefixes are removed from titles."""
        pr_mr_list = [
            {'title': 'feat: add new feature', 'body': '', 'url': '', 'number': 1},
            {'title': 'fix(api): resolve timeout', 'body': '', 'url': '', 'number': 2},
        ]

        content = self.manager.generate_changelog_content(pr_mr_list)

        # Prefixes should be removed
        assert 'feat:' not in content
        assert 'fix(api):' not in content
        # But titles should remain
        assert 'add new feature' in content
        assert 'resolve timeout' in content

    def test_handles_empty_list(self):
        """Test handling of empty PR/MR list."""
        content = self.manager.generate_changelog_content([])

        assert content == ""


class TestUpdateChangelogWithAutoGenerate:
    """Test update_changelog method with auto-generation."""

    @patch.object(ReleaseManager, "get_latest_tag")
    @patch.object(ReleaseManager, "get_commits_with_prs")
    @patch.object(ReleaseManager, "fetch_mr_metadata")
    @patch("devflow.release.permissions.get_git_remote_url")
    @patch("devflow.release.permissions.parse_git_remote")
    def test_auto_generates_changelog_from_prs(self, mock_parse, mock_get_url, mock_fetch_mr, mock_get_commits, mock_get_tag):
        """Test that auto_generate=True generates changelog from PR/MR metadata."""
        from devflow.release.permissions import Platform

        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]

[0.1.0]: https://gitlab.com/test/repo/-/tags/v0.1.0
"""
            changelog_file.write_text(initial_content)

            # Mock dependencies
            mock_get_tag.return_value = "v0.1.0"
            mock_get_commits.return_value = [
                {'hash': 'abc123', 'subject': 'Merge', 'body': 'See merge request !281', 'pr_mr': {'type': 'gitlab_mr', 'number': '281'}}
            ]
            mock_fetch_mr.return_value = {
                'number': 281,
                'title': 'PROJ-62790: feat: add version reference links',
                'body': '## Added\n- Version reference links in changelog',
                'url': 'https://gitlab.com/test/repo/-/merge_requests/281',
                'type': 'gitlab_mr'
            }
            mock_get_url.return_value = "git@gitlab.com:test/repo.git"
            mock_parse.return_value = (Platform.GITLAB, "test", "repo")

            # Update changelog with auto-generation
            version = Version(0, 2, 0)
            manager.update_changelog(version, release_date="2026-01-20", auto_generate=True)

            # Read updated content
            updated_content = changelog_file.read_text()

            # Verify version section was added
            assert "## [0.2.0] - 2026-01-20" in updated_content

            # Verify auto-generated content is present
            assert "### Added" in updated_content
            assert "Version reference links in changelog" in updated_content
            assert "PROJ-62790" in updated_content
            assert "#281" in updated_content

    @patch.object(ReleaseManager, "get_latest_tag")
    @patch("devflow.release.permissions.get_git_remote_url")
    def test_skips_auto_generate_when_disabled(self, mock_get_url, mock_get_tag):
        """Test that auto_generate=False skips PR/MR fetching."""
        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]
"""
            changelog_file.write_text(initial_content)

            mock_get_tag.return_value = "v0.1.0"
            mock_get_url.return_value = None

            # Update changelog without auto-generation
            version = Version(0, 2, 0)
            manager.update_changelog(version, release_date="2026-01-20", auto_generate=False)

            # Read updated content
            updated_content = changelog_file.read_text()

            # Verify version section was added but without content
            assert "## [0.2.0] - 2026-01-20" in updated_content
            # Should not have any category sections
            assert "### Added" not in updated_content
            assert "### Fixed" not in updated_content

    @patch.object(ReleaseManager, "get_latest_tag")
    @patch("devflow.release.permissions.get_git_remote_url")
    def test_handles_no_latest_tag(self, mock_get_url, mock_get_tag):
        """Test that missing latest tag gracefully skips auto-generation."""
        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            manager = ReleaseManager(repo_path)

            # Create CHANGELOG.md
            changelog_file = repo_path / "CHANGELOG.md"
            initial_content = """# Changelog

## [Unreleased]
"""
            changelog_file.write_text(initial_content)

            mock_get_tag.return_value = None
            mock_get_url.return_value = None

            # Update changelog - should handle gracefully
            version = Version(0, 1, 0)
            manager.update_changelog(version, release_date="2026-01-20", auto_generate=True)

            # Read updated content
            updated_content = changelog_file.read_text()

            # Verify version section was added (just without generated content)
            assert "## [0.1.0] - 2026-01-20" in updated_content


class TestValidateReleasePrepared:
    """Test validate_release_prepared() version validation.

    Bug: AAP-64004
    After 'daf release 1.0.0', version files are set to 1.1.0-dev (next minor dev).
    The 'daf release 1.0.0 approve' command should accept this version.
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.repo_path = Path("/test/repo")
        self.manager = ReleaseManager(self.repo_path)

    @patch("subprocess.run")
    def test_validate_release_prepared_accepts_next_minor_dev_for_minor_release(self, mock_run):
        """Test that validation accepts 1.1.0-dev when approving 1.0.0 minor release.

        Acceptance Criteria:
        - For minor/major releases: accept next_minor_dev (1.1.0-dev)
        - Test passes for minor releases (0.Y.0 versions)
        """
        # Mock git tag verification
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0\n")

        # Mock version files showing 1.1.0-dev (what 'daf release 1.0.0' sets)
        with patch.object(self.manager, 'read_current_version', return_value=("1.1.0-dev", "1.1.0-dev")):
            version = Version.parse("1.0.0")
            success, message, release_branch = self.manager.validate_release_prepared(version)

        assert success is True, f"Expected validation to pass, but got: {message}"
        assert release_branch == "release/1.0"

    @patch("subprocess.run")
    def test_validate_release_prepared_accepts_next_patch_dev_for_patch_release(self, mock_run):
        """Test that validation accepts 1.0.2-dev when approving 1.0.1 patch release.

        Acceptance Criteria:
        - For patch releases: accept next_patch_dev (1.0.2-dev)
        - Test passes for patch releases (X.Y.Z where Z > 0)
        """
        # Mock git tag verification
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.1\n")

        # Mock version files showing 1.0.2-dev (what 'daf release 1.0.1' sets)
        with patch.object(self.manager, 'read_current_version', return_value=("1.0.2-dev", "1.0.2-dev")):
            version = Version.parse("1.0.1")
            success, message, release_branch = self.manager.validate_release_prepared(version)

        assert success is True, f"Expected validation to pass, but got: {message}"
        assert release_branch is None  # Patch releases don't have release branches

    @patch("subprocess.run")
    def test_validate_release_prepared_accepts_release_version(self, mock_run):
        """Test that validation accepts 1.0.0 (release version itself).

        Acceptance Criteria:
        - For minor/major releases: accept version_str (1.0.0)
        """
        # Mock git tag verification
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0\n")

        # Mock version files showing 1.0.0 (exact release version)
        with patch.object(self.manager, 'read_current_version', return_value=("1.0.0", "1.0.0")):
            version = Version.parse("1.0.0")
            success, message, release_branch = self.manager.validate_release_prepared(version)

        assert success is True, f"Expected validation to pass, but got: {message}"
        assert release_branch == "release/1.0"

    @patch("subprocess.run")
    def test_validate_release_prepared_accepts_release_dev_version(self, mock_run):
        """Test that validation accepts 1.0.0-dev (release version with -dev).

        Acceptance Criteria:
        - For minor/major releases: accept version_str-dev (1.0.0-dev)
        """
        # Mock git tag verification
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0\n")

        # Mock version files showing 1.0.0-dev (preparing for release)
        with patch.object(self.manager, 'read_current_version', return_value=("1.0.0-dev", "1.0.0-dev")):
            version = Version.parse("1.0.0")
            success, message, release_branch = self.manager.validate_release_prepared(version)

        assert success is True, f"Expected validation to pass, but got: {message}"
        assert release_branch == "release/1.0"

    @patch("subprocess.run")
    def test_validate_release_prepared_accepts_next_minor_dev_for_major_release(self, mock_run):
        """Test that validation accepts 2.1.0-dev when approving 2.0.0 major release.

        Acceptance Criteria:
        - For minor/major releases: accept next_minor_dev (2.1.0-dev)
        - Test passes for major releases (X.0.0 versions)
        """
        # Mock git tag verification
        mock_run.return_value = Mock(returncode=0, stdout="v2.0.0\n")

        # Mock version files showing 2.1.0-dev (what 'daf release 2.0.0' sets)
        with patch.object(self.manager, 'read_current_version', return_value=("2.1.0-dev", "2.1.0-dev")):
            version = Version.parse("2.0.0")
            success, message, release_branch = self.manager.validate_release_prepared(version)

        assert success is True, f"Expected validation to pass, but got: {message}"
        assert release_branch == "release/2.0"

    @patch("subprocess.run")
    def test_validate_release_prepared_rejects_incorrect_version(self, mock_run):
        """Test that validation rejects incorrect version (e.g., 1.2.0-dev for 1.0.0 release)."""
        # Mock git tag verification
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0\n")

        # Mock version files showing 1.2.0-dev (incorrect version)
        with patch.object(self.manager, 'read_current_version', return_value=("1.2.0-dev", "1.2.0-dev")):
            version = Version.parse("1.0.0")
            success, message, release_branch = self.manager.validate_release_prepared(version)

        assert success is False
        assert "Version mismatch" in message
        assert "1.2.0-dev" in message

    @patch("subprocess.run")
    def test_validate_release_prepared_error_message_shows_acceptable_versions(self, mock_run):
        """Test that error message lists all acceptable versions.

        Acceptance Criteria:
        - Validation error messages updated to reflect acceptable version values
        """
        # Mock git tag verification
        mock_run.return_value = Mock(returncode=0, stdout="v1.0.0\n")

        # Mock version files showing 1.2.0-dev (incorrect version)
        with patch.object(self.manager, 'read_current_version', return_value=("1.2.0-dev", "1.2.0-dev")):
            version = Version.parse("1.0.0")
            success, message, release_branch = self.manager.validate_release_prepared(version)

        assert success is False
        # Error message should show all three acceptable versions
        assert "1.0.0" in message
        assert "1.0.0-dev" in message
        assert "1.1.0-dev" in message
